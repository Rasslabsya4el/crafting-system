"""Command-line presentation for the reviewed policy-evaluator result contract."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from numbers import Real
import os
from pathlib import Path
import subprocess
import shutil
from typing import Any

from craftoracle.actions import load_action_data
from craftoracle.distributions import OutcomeClass
from craftoracle.item_model import ItemState
from craftoracle.plan_inputs import ItemSpec, Loadout, load_loadout, load_spec
from craftoracle.quality import plan_catalyst
from craftoracle.reporting import build_report, render_report


_SCHEMA_VERSION = 1


class PlanInputError(ValueError):
    """A validated input or evaluator result cannot produce a plan."""


Evaluator = Callable[[ItemSpec, Loadout, object], Mapping[str, Any]]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse a repository-local command and return its exit status."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "quality":
            document = evaluate_quality(
                arguments.base,
                arguments.item_level,
                arguments.catalyst,
                arguments.target_quality,
                arguments.price,
            )
            renderer = format_quality
        elif arguments.command == "plan":
            document = evaluate_plan(
                arguments.spec,
                arguments.loadout,
                arguments.threshold,
                compare_thresholds=arguments.compare_thresholds,
                item_level_range=arguments.item_level_range,
            )
            renderer = format_plan
        else:
            _repository_path(arguments.spec, "spec")
            _repository_path(arguments.loadout, "loadout")
            _report_output_dir(arguments.output_dir)
            if arguments.evidence_dir:
                _repository_path(arguments.evidence_dir, "evidence")
            document = evaluate_plan(
                arguments.spec, arguments.loadout, arguments.threshold,
                compare_thresholds=arguments.compare_thresholds,
            )
            output_dir = _report_output_dir(arguments.output_dir)
            evidence = _load_evidence(arguments.evidence_dir) if arguments.evidence_dir else None
            data = load_action_data(Path(__file__).resolve().parents[2])
            report_loadout = load_loadout(arguments.loadout)
            context = {
                "action_rules": data.rules,
                "essence_names": {key: row.get("name", key) for key, row in data.essences.items()},
                "envy_id": "Metadata/Items/Currency/CurrencyEssenceEnvy3",
                "bench_recipes": report_loadout.bench_recipes,
                "fossil_names": _fossil_names(),
                "bench_names": {str(index): str(row.get("stat_text", f"bench {index}")) for index, row in data.bench.items()},
                "generation": {"commit": _git_commit(), "generated_at": datetime.now(timezone.utc).isoformat()},
                "target": _report_target(arguments.spec, data),
            }
            report = build_report(document, context, evidence)
            output_dir.mkdir(parents=True, exist_ok=True)
            if arguments.evidence_dir:
                _copy_evidence_artifacts(_repository_path(arguments.evidence_dir, "evidence"), output_dir, evidence or {})
            plan_path, index_path = output_dir / "plan.json", output_dir / "index.html"
            plan_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            index_path.write_text(render_report(report), encoding="utf-8")
            print(index_path)
            print(plan_path)
            return 0
        if arguments.json:
            print(json.dumps(document, indent=2, sort_keys=True, allow_nan=False))
        else:
            print(renderer(document))
    except (PlanInputError, ValueError, NotImplementedError) as error:
        parser.error(str(error))
    return 0


def evaluate_plan(
    spec_path: str | Path,
    loadout_path: str | Path,
    threshold: float | None = None,
    *,
    compare_thresholds: str | Sequence[float] | None = None,
    item_level_range: str | Sequence[int] | None = None,
    evaluator: Evaluator | None = None,
) -> dict[str, Any]:
    """Load validated inputs, evaluate policies, and return the JSON document."""
    root = Path(__file__).resolve().parents[2]
    data = load_action_data(root)
    spec = load_spec(spec_path, data.mods)
    loadout = load_loadout(loadout_path)
    spec = _with_threshold(spec, threshold)
    thresholds = _parse_comparison_thresholds(spec, compare_thresholds)
    if not loadout.allowed_actions:
        raise PlanInputError("loadout permits no crafting actions")

    if evaluator is not None:
        if thresholds is not None:
            raise PlanInputError("threshold comparison requires the frontier evaluator")
        if item_level_range is not None:
            raise PlanInputError("item-level search requires the optimizer evaluator")
        result = evaluator(spec, loadout, data)
    else:
        result = _load_evaluator()(spec, loadout, data, thresholds=thresholds, item_level_range=item_level_range)
    return plan_document(spec, loadout, result)


def evaluate_quality(
    base: str = "Vermillion Ring",
    item_level: int = 86,
    catalyst: str = "Fertile",
    target_quality: int = 20,
    price: float = 0.0,
) -> dict[str, Any]:
    """Plan a finite ordinary-catalyst quality finish from a zero-quality rare."""
    root = Path(__file__).resolve().parents[2]
    item = ItemState(base, item_level, "rare")
    plan = plan_catalyst(item, load_action_data(root), catalyst, target_quality, price)
    return {
        "input": {
            "base": base,
            "item_level": item_level,
            "rarity": "rare",
            "quality": 0,
            "catalyst": catalyst,
            "target_quality": target_quality,
            "unit_price": price,
        },
        "steps": list(plan["steps"]),
        "count_distribution": [
            {"applications": applications, "probability": probability}
            for applications, probability in sorted(plan["count_distribution"].items())
        ],
        "cost_distribution": [
            {"cost": cost, "probability": probability}
            for cost, probability in sorted(plan["cost_distribution"].items())
        ],
        "final_quality_distribution": [
            {
                "quality": state.quality,
                "catalyst": state.catalyst_type,
                "probability": probability,
            }
            for state, probability in sorted(
                plan["final_quality_distribution"].items(), key=lambda entry: entry[0].quality
            )
        ],
        "expected_applications": plan["expected_applications"],
        "applications_p90": plan["applications_p90"],
        "expected_cost": plan["expected_cost"],
        "cost_p90": plan["cost_p90"],
        "source_confidence": plan["source_confidence"],
        "sources": plan["sources"],
        "price_disclaimer": plan["price_disclaimer"],
    }


def plan_document(
    spec: ItemSpec, loadout: Loadout, result: Mapping[str, Any]
) -> dict[str, Any]:
    """Add input provenance to a complete, JSON-safe evaluator result."""
    if not isinstance(result, Mapping):
        raise PlanInputError("policy evaluator must return an object")
    ranked = result.get("ranked")
    unavailable = result.get("unavailable")
    assumptions = result.get("assumptions")
    if not isinstance(ranked, list) or not isinstance(unavailable, list) or not isinstance(assumptions, list):
        raise PlanInputError("policy evaluator result requires ranked, unavailable, and assumptions lists")
    if not ranked:
        reasons = _unavailable_reasons(unavailable)
        suffix = f": {reasons}" if reasons else ""
        raise PlanInputError(f"no reachable policies{suffix}")
    reserved = {"schema_version", "input", "prices"}
    collisions = sorted(reserved & result.keys())
    if collisions:
        raise PlanInputError(f"policy evaluator result uses reserved fields: {', '.join(collisions)}")

    document: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "input": {
            "name": spec.name,
            "base": spec.base,
            "item_level": spec.item_level,
            "quality": spec.quality,
            "flags": spec.flags,
            "sources": list(spec.sources),
            "utility_threshold": spec.threshold,
            "values_note": spec.values_note,
        },
        "prices": {
            "name": loadout.name,
            "unit": loadout.unit,
            "values": loadout.values,
            "note": loadout.note,
            "sources": list(loadout.sources),
            "budget": loadout.budget,
            "base_cost": loadout.base_cost,
        },
        **dict(result),
    }
    return _json_ready(document)


def format_plan(document: Mapping[str, Any]) -> str:
    """Render player-facing policy costs, odds, and decisions from a JSON document."""
    input_data = _required_mapping(document, "input")
    prices = _required_mapping(document, "prices")
    ranked = _required_list(document, "ranked")
    unavailable = _required_list(document, "unavailable")
    assumptions = _required_list(document, "assumptions")
    unit = _required_string(prices, "unit")

    lines = [
        f"Plan: {input_data.get('name', input_data.get('base', 'item'))}",
        "Input: " + ", ".join((
            str(input_data.get("base", "unknown base")),
            f"ilvl {input_data.get('item_level', '?')}",
            f"quality {input_data.get('quality', '?')}",
        )),
        f"Prices: {unit}. {prices.get('note', '')}",
        f"Budget: {_number_text(_number_value(prices, 'budget'))} {unit} (mean-cost criterion)",
        "",
        "Ranked policies",
        "id | name | success probabilities | expected attempts | expected cost | p90 cost | stopping threshold | frontier | method | within budget | p90 over budget",
    ]
    for policy in ranked:
        policy = _mapping(policy, "ranked policy")
        stages = _list_value(policy, "stages")
        probabilities = ", ".join(
            f"{_string_value(stage, 'name')}={_probability_text(_number_value(stage, 'probability'))}"
            for stage in (_mapping(value, "stage") for value in stages)
        )
        attempts = ", ".join(
            f"{_string_value(stage, 'name')}={_number_text(_number_value(stage, 'expected_attempts'))}"
            for stage in (_mapping(value, "stage") for value in stages)
        )
        lines.append(" | ".join((
            _string_value(policy, "id"),
            _string_value(policy, "name"),
            probabilities,
            attempts,
            f"{_number_text(_number_value(policy, 'expected_cost'))} {unit}",
            f"{_number_text(_number_value(policy, 'cost_p90'))} {unit}",
            _stopping_threshold_text(policy, input_data),
            _yes_no(policy.get("frontier")),
            str(policy.get("cost_method", policy.get("method", "unspecified"))),
            _yes_no(policy.get("within_budget")),
            _yes_no(policy.get("p90_over_budget")),
        )))

    for policy in ranked:
        policy = _mapping(policy, "ranked policy")
        lines.extend(("", f"{_string_value(policy, 'id')} - {_string_value(policy, 'name')}", "Steps:"))
        lines.extend(f"  - {step}" for step in _list_value(policy, "steps"))
        lines.append("Decisions:")
        decisions = _list_value(policy, "decision_points")
        lines.extend(f"  - {decision}" for decision in decisions)
        lines.append(f"Expected terminal utility: {_number_text(_number_value(policy, 'expected_utility'))}")
        stopping_threshold = policy.get("stopping_threshold")
        if stopping_threshold is not None:
            lines.append(f"Stopping threshold: {_number_text(_number_value(policy, 'stopping_threshold'))}")
        lines.append(f"Pareto frontier: {_yes_no(policy.get('frontier'))}")
        lines.append(f"Irreversible failure risk: {_probability_text(_number_value(policy, 'irreversible_failure_risk'))}")
        rare_inputs = _list_value(policy, "rare_inputs")
        lines.append("Rare inputs: " + (", ".join(map(str, rare_inputs)) if rare_inputs else "none"))
        estimate = _estimated_cost_detail(policy, unit)
        if estimate:
            lines.append(estimate)
        policy_assumptions = _list_value(policy, "assumptions")
        if policy_assumptions:
            lines.append("Assumptions: " + "; ".join(map(str, policy_assumptions)))
        else:
            lines.append("Assumptions: shared assumptions below")
        for stage in (_mapping(value, "stage") for value in _list_value(policy, "stages")):
            stage_line = (
                "  " + _string_value(stage, "name")
                + f": p={_probability_text(_number_value(stage, 'probability'))}"
                + f", expected attempts={_number_text(_number_value(stage, 'expected_attempts'))}"
            )
            target_after = stage.get("target_probability_after_stage")
            if target_after is not None:
                if isinstance(target_after, bool) or not isinstance(target_after, Real) or not math.isfinite(target_after):
                    raise PlanInputError("target_probability_after_stage must be a finite probability")
                stage_line += f", target after stage={_probability_text(float(target_after))}"
            lines.append(stage_line)
            lines.append("    Actions: " + "; ".join(map(str, _list_value(stage, "actions"))))
            lines.append("    Decisions: " + "; ".join(map(str, _list_value(stage, "decisions"))))

    if unavailable:
        lines.extend(("", "Unavailable candidates:"))
        for candidate in unavailable:
            candidate = _mapping(candidate, "unavailable candidate")
            lines.append(
                f"  - {candidate.get('id', 'unknown')} ({candidate.get('name', 'unnamed')}): "
                + "; ".join(map(str, _list_value(candidate, "reasons")))
            )
    lines.extend(("", "Shared assumptions:"))
    lines.extend(f"  - {assumption}" for assumption in assumptions)
    if input_data.get("values_note"):
        lines.append(f"  - Utility target note: {input_data['values_note']}")
    input_sources = input_data.get("sources", [])
    if input_sources:
        lines.append("  - Item input sources: " + "; ".join(map(str, input_sources)))
    price_sources = prices.get("sources", [])
    if price_sources:
        lines.append("  - Price input sources: " + "; ".join(map(str, price_sources)))
    return "\n".join(lines)


def format_quality(document: Mapping[str, Any]) -> str:
    """Render the bounded ordinary-catalyst policy and its exact laws."""
    input_data = _required_mapping(document, "input")
    lines = [
        "Catalyst quality plan",
        "Input: " + ", ".join((
            str(input_data["base"]),
            f"ilvl {input_data['item_level']}",
            str(input_data["rarity"]),
            f"{input_data['catalyst']} Catalyst",
        )),
        *(_list_value(document, "steps")),
        f"Expected applications: {_number_text(_number_value(document, 'expected_applications'))}",
        f"p90 applications: {_number_text(_number_value(document, 'applications_p90'))}",
        f"Expected cost: {_number_text(_number_value(document, 'expected_cost'))}",
        f"p90 cost: {_number_text(_number_value(document, 'cost_p90'))}",
        "Exact application distribution:",
    ]
    for entry in _list_value(document, "count_distribution"):
        entry = _mapping(entry, "count distribution entry")
        lines.append(
            f"  {_number_text(_number_value(entry, 'applications'))}: "
            f"{_probability_text(_number_value(entry, 'probability'))}"
        )
    lines.append("Final quality states:")
    for entry in _list_value(document, "final_quality_distribution"):
        entry = _mapping(entry, "final quality entry")
        lines.append(
            f"  {_number_text(_number_value(entry, 'quality'))}% {entry['catalyst']}: "
            f"{_probability_text(_number_value(entry, 'probability'))}"
        )
    lines.append(f"Price note: {document['price_disclaimer']}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m craftoracle")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="evaluate reviewed crafting policies")
    plan.add_argument("spec", metavar="SPEC", help="JSON-compatible YAML item specification")
    plan.add_argument("--loadout", required=True, metavar="LOADOUT", help="loadout JSON file")
    plan.add_argument("--json", action="store_true", help="emit machine-readable plan JSON")
    threshold_group = plan.add_mutually_exclusive_group()
    threshold_group.add_argument("--threshold", type=float, metavar="UTILITY", help="override a utility target threshold")
    threshold_group.add_argument(
        "--compare-thresholds",
        metavar="UTILITY,UTILITY",
        help="evaluate distinct utility stopping thresholds from the item specification",
    )
    plan.add_argument(
        "--item-level-range",
        metavar="MIN:MAX",
        help="opt in to an inclusive item-level search over PoB modifier breakpoints",
    )
    report = commands.add_parser("report", help="render an offline Russian route report")
    report.add_argument("spec", metavar="SPEC", help="JSON-compatible YAML item specification")
    report.add_argument("--loadout", required=True, metavar="LOADOUT", help="loadout JSON file")
    report.add_argument("--output-dir", required=True, metavar="DIR", help="repository-local output directory")
    report.add_argument("--evidence-dir", metavar="DIR", help="repository-local evidence directory containing proof.json")
    threshold_group = report.add_mutually_exclusive_group()
    threshold_group.add_argument("--threshold", type=float, metavar="UTILITY", help="override a utility target threshold")
    threshold_group.add_argument("--compare-thresholds", metavar="UTILITY,UTILITY", help="evaluate comparison thresholds")
    quality = commands.add_parser("quality", help="plan an ordinary catalyst quality finish")
    quality.add_argument("--base", default="Vermillion Ring", help="PoB jewellery base name")
    quality.add_argument("--item-level", type=int, default=86, help="positive item level")
    quality.add_argument("--catalyst", required=True, help="regular catalyst name")
    quality.add_argument("--target-quality", type=int, default=20, help="target quality from 1 through 20")
    quality.add_argument("--price", type=float, required=True, help="non-negative caller-supplied unit price")
    quality.add_argument("--json", action="store_true", help="emit machine-readable exact distributions")
    return parser


def _report_output_dir(path: str) -> Path:
    return _repository_path(path, "report output")


def _repository_path(path: str | Path, name: str) -> Path:
    root = Path(__file__).resolve().parents[2].resolve()
    candidate = Path(os.path.normpath(path))
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise PlanInputError(f"{name} path escapes the repository root") from error
    return target


def _load_evidence(directory: str) -> dict[str, Any]:
    target = _repository_path(directory, "evidence")
    try:
        document = json.loads((target / "proof.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"schema_version": 1, "pytest": {"status": "unavailable"}, "coe": {"status": "unavailable"}, "message": f"proof.json unavailable: {error}"}
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise PlanInputError("unsupported evidence proof.json schema")
    return document


def _git_commit() -> str | None:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False, timeout=10)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _copy_evidence_artifacts(source: Path, output: Path, evidence: Mapping[str, Any]) -> None:
    artifacts = evidence.get("artifacts", {})
    paths = ["proof.json", *artifacts.values()] if isinstance(artifacts, Mapping) else ["proof.json"]
    for command in evidence.get("commands", []) if isinstance(evidence.get("commands"), list) else []:
        if isinstance(command, Mapping):
            paths.extend((command.get("stdout_file"), command.get("stderr_file")))
    for raw in paths:
        if not isinstance(raw, str):
            continue
        candidate = (source / raw).resolve()
        try:
            candidate.relative_to(source)
        except ValueError:
            continue
        if candidate.is_file():
            relative = candidate.relative_to(source)
            target = output / "evidence" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if candidate != target:
                shutil.copy2(candidate, target)


def _report_target(spec_path: str | Path, data: Any) -> dict[str, Any]:
    """Expose source-backed target wording without adding it to planner output."""
    spec = load_spec(spec_path, data.mods)
    labels: dict[str, str] = {}
    for group, tiers in spec.tier_ids.items():
        for tier, identifiers in enumerate(tiers, start=1):
            text = " / ".join(str(data.mods[identifier].get("stat_text", identifier)) for identifier in identifiers)
            labels[f"{group}:{tier}"] = text
    return {
        "criteria": [{"group": item.group, "max_tier": item.max_tier, "text": labels.get(f"{item.group}:{item.max_tier}", item.group)} for item in spec.required_mods],
        "any_of": [[{"group": item.group, "max_tier": item.max_tier, "text": labels.get(f"{item.group}:{item.max_tier}", item.group)} for item in alternatives] for alternatives in spec.any_of],
        "value_table": spec.value_table,
        "threshold": spec.threshold,
        "values_note": spec.values_note,
        "labels": labels,
    }


def _fossil_names() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    document = json.loads((root / "data/rules/fossils.json").read_text(encoding="utf-8"))
    return {str(row["id"]): str(row["name"]) for row in document["ordinary"]}


def _load_evaluator():
    try:
        from craftoracle.frontier import evaluate_frontier
    except ModuleNotFoundError as error:
        if error.name != "craftoracle.frontier":
            raise
        raise PlanInputError("frontier evaluator is not available in this checkout") from error
    return evaluate_frontier


def _with_threshold(spec: ItemSpec, threshold: float | None) -> ItemSpec:
    if threshold is None:
        return spec
    if spec.value_table is None:
        raise PlanInputError("--threshold is only valid for a utility item specification")
    if isinstance(threshold, bool) or not isinstance(threshold, Real) or not math.isfinite(threshold):
        raise PlanInputError("--threshold must be a finite number")
    return replace(spec, threshold=float(threshold))


def _parse_comparison_thresholds(spec: ItemSpec, requested: str | Sequence[float] | None) -> tuple[float, ...] | None:
    if requested is None:
        return None
    if spec.value_table is None:
        raise PlanInputError("--compare-thresholds is only valid for a utility item specification")
    if isinstance(requested, str):
        pieces = requested.split(",")
        if not pieces or any(not piece.strip() for piece in pieces):
            raise PlanInputError("--compare-thresholds must be a non-empty comma-separated list")
        try:
            values = tuple(float(piece) for piece in pieces)
        except ValueError as error:
            raise PlanInputError("--compare-thresholds must be a comma-separated list of finite numbers") from error
    else:
        if isinstance(requested, (bytes, bytearray)):
            raise PlanInputError("--compare-thresholds must be a non-empty comma-separated list")
        values = tuple(requested)
    if not values:
        raise PlanInputError("--compare-thresholds must be non-empty")
    if any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) for value in values):
        raise PlanInputError("--compare-thresholds must contain finite numbers")
    parsed = tuple(float(value) for value in values)
    if len(set(parsed)) != len(parsed):
        raise PlanInputError("--compare-thresholds must contain distinct values")
    assert spec.threshold is not None
    if any(value < spec.threshold for value in parsed):
        raise PlanInputError("--compare-thresholds values must be at least the item specification threshold")
    return parsed


def _stopping_threshold_text(policy: Mapping[str, Any], input_data: Mapping[str, Any]) -> str:
    value = policy.get("stopping_threshold")
    if value is None:
        value = input_data.get("utility_threshold")
    if value is None:
        return "-"
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise PlanInputError("stopping_threshold must be a finite number")
    return _number_text(float(value))


def _json_ready(value: Any) -> Any:
    """Recursively preserve all values while making OutcomeClass maps valid JSON."""
    if isinstance(value, OutcomeClass):
        return {
            "labels": list(value.labels),
            "prefixes": value.prefixes,
            "suffixes": value.suffixes,
        }
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PlanInputError("planner result contains a non-finite number")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_ready(entry) for entry in value]
    if isinstance(value, Mapping):
        if value and all(isinstance(key, OutcomeClass) for key in value):
            return [
                {
                    "labels": list(outcome.labels),
                    "prefixes": outcome.prefixes,
                    "suffixes": outcome.suffixes,
                    "probability": _json_ready(probability),
                }
                for outcome, probability in value.items()
            ]
        result: dict[str, Any] = {}
        for key, entry in value.items():
            if not isinstance(key, str):
                raise PlanInputError("planner result has a non-string JSON object key")
            result[key] = _json_ready(entry)
        return result
    raise PlanInputError(f"planner result is not JSON-serializable: {type(value).__name__}")


def _unavailable_reasons(candidates: list[Any]) -> str:
    reasons: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            reasons.extend(str(reason) for reason in candidate.get("reasons", []) if isinstance(reason, str))
    return "; ".join(reasons)


def _estimated_cost_detail(policy: Mapping[str, Any], unit: str) -> str | None:
    """Render MC p90 uncertainty when the evaluator used its documented fallback."""
    interval = policy.get("cost_p90_interval")
    if interval is None:
        return None
    if not isinstance(interval, list) or len(interval) != 2:
        raise PlanInputError("cost_p90_interval must contain lower and upper values")
    lower, upper = interval
    if isinstance(lower, bool) or not isinstance(lower, Real) or not math.isfinite(lower):
        raise PlanInputError("cost_p90_interval lower bound must be finite")
    if isinstance(upper, bool) or not isinstance(upper, Real) or not math.isfinite(upper):
        raise PlanInputError("cost_p90_interval upper bound must be finite")
    samples = policy.get("cost_sample_count")
    seed = policy.get("cost_seed")
    error_bound = policy.get("cost_error_bound")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise PlanInputError("cost_sample_count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise PlanInputError("cost_seed must be an integer")
    if isinstance(error_bound, bool) or not isinstance(error_bound, Real) or not math.isfinite(error_bound):
        raise PlanInputError("cost_error_bound must be finite")
    return (
        "Estimated p90 uncertainty: "
        f"{_number_text(float(lower))}-{_number_text(float(upper))} {unit}; "
        f"samples={samples}, seed={seed}, error bound={_number_text(float(error_bound))}"
    )


def _required_mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping(document.get(key), key)


def _required_list(document: Mapping[str, Any], key: str) -> list[Any]:
    return _list_value(document, key)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PlanInputError(f"{name} must be an object")
    return value


def _list_value(document: Mapping[str, Any], key: str) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list):
        raise PlanInputError(f"{key} must be a list")
    return value


def _required_string(document: Mapping[str, Any], key: str) -> str:
    return _string_value(document, key)


def _string_value(document: Mapping[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise PlanInputError(f"{key} must be a non-empty string")
    return value


def _number_value(document: Mapping[str, Any], key: str) -> float:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise PlanInputError(f"{key} must be a finite number")
    return float(value)


def _probability_text(value: float) -> str:
    if value < 0 or value > 1:
        raise PlanInputError("probability must be in [0, 1]")
    return format(value, ".12g")


def _number_text(value: float) -> str:
    return format(value, ".12g")


def _yes_no(value: Any) -> str:
    if not isinstance(value, bool):
        raise PlanInputError("within_budget must be boolean")
    return "yes" if value else "no"
