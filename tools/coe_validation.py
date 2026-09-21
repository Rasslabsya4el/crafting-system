"""Run the lead-selected offline Craft of Exile comparison cases once."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from craftoracle.actions import ActionData, action_distribution, load_action_data, prepare_roll
from craftoracle.distributions import probability
from craftoracle.item_model import ItemState, ModRef


NODE_RUNNER = ROOT / "tools" / "coe_offline.cjs"
OUTPUT_DIR = ROOT / "out" / "coe-validation"
PACKAGE_SOURCE = ROOT / "sources" / "raw" / "coe" / "package.js"
DATA_SOURCE = ROOT / "sources" / "raw" / "coe" / "poec_data.json"
ITEM_LEVEL = 86


@dataclass(frozen=True)
class Case:
    id: str
    base: str
    action: str
    rarity: str
    expected_ours: float
    targets: tuple[str, ...]
    existing: tuple[str, ...]
    essence_id: str | None
    coe: dict[str, Any]
    forced_pob_id: str | None = None


def _final(
    *, base_id: str, method: str, req_max_groups: int, prefix: tuple[str, ...] = (),
    suffix: tuple[str, ...] = (), exclude: tuple[str, ...] = (), forced_side: str | None = None,
    forced_essence_name: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command": "real_final",
        "base_id": base_id,
        "item_level": ITEM_LEVEL,
        "method": method,
        "req_max_groups": req_max_groups,
        "targets": {"prefix": list(prefix), "suffix": list(suffix)},
    }
    if exclude:
        payload["exclude_aids"] = list(exclude)
    if forced_side:
        payload["forced_side"] = forced_side
    if forced_essence_name:
        payload["forced_essence_name"] = forced_essence_name
    return payload


def _kernel(
    *, base_id: str, pool_side: str, prefix: tuple[str, ...] = (), suffix: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "command": "real_kernel",
        "base_id": base_id,
        "item_level": ITEM_LEVEL,
        "pool_side": pool_side,
        "draws": 1,
        "exclude_aids": list(exclude),
        "targets": {"prefix": list(prefix), "suffix": list(suffix)},
    }


# IDs 1775/661/684/2007 are supplied by the spec. The batch validates every
# configured mapping against the frozen sources before it writes a report.
CASES: tuple[Case, ...] = (
    Case("C01", "Royal Burgonet", "chaos", "rare", 0.0003673650969794048, ("IncreasedLife9", "ChaosResist6"), (), None,
         _final(base_id="52", method="chaos", req_max_groups=3, prefix=("1775",), suffix=("661",))),
    Case("C02", "Royal Burgonet", "essence", "rare", 0.0008758259906074872, ("IncreasedLife9", "FireResist8"), (),
         "Metadata/Items/Currency/CurrencyEssenceEnvy3",
         _final(base_id="52", method="essence", req_max_groups=3, prefix=("1775",), suffix=("1628",),
                exclude=("661",), forced_side="suffix", forced_essence_name="Envy"), "ChaosResist6"),
    Case("C03", "Royal Burgonet", "exalted", "rare", 0.02546148949713558, ("IncreasedLife9",),
         ("ChaosResist6", "FireResist8", "ColdResist8"), None,
         _kernel(base_id="52", pool_side="prefix", prefix=("1775",), exclude=("661", "1628", "684"))),
    Case("C04", "Simple Robe", "alchemy", "normal", 0.03550816560805275, ("LocalIncreasedEnergyShield11",), (), None,
         _final(base_id="47", method="alchemy", req_max_groups=3, prefix=("2007",))),
    Case("C05", "Simple Robe", "alteration", "magic", 0.0001408371359360036, ("LocalIncreasedEnergyShield11", "LightningResist8"), (), None,
         _final(base_id="47", method="alteration", req_max_groups=1, prefix=("2007",), suffix=("1966",))),
    Case("C06", "Iron Ring", "chaos", "rare", 0.00010876109551498082, ("ColdResist8", "ChaosResist6"), (), None,
         _final(base_id="1", method="chaos", req_max_groups=3, suffix=("684", "661"))),
    Case("C07", "Iron Ring", "alchemy", "normal", 0.024246677570894055, ("ColdResist8",), (), None,
         _final(base_id="1", method="alchemy", req_max_groups=3, suffix=("684",))),
    Case("C08", "Iron Ring", "regal", "magic", 0.0016909029421711193, ("ChaosResist6",),
         ("IncreasedLife7", "FireResist8"), None,
         _kernel(base_id="1", pool_side="both", suffix=("661",), exclude=("1775", "1628"))),
    Case("C09", "Paua Amulet", "chaos", "rare", 0.00010370039891240398, ("IncreasedLife8", "ChaosResist6"), (), None,
         _final(base_id="2", method="chaos", req_max_groups=3, prefix=("1775",), suffix=("661",))),
    Case("C10", "Paua Amulet", "alteration", "magic", 0.006330103412534295, ("ColdResist8",), (), None,
         _final(base_id="2", method="alteration", req_max_groups=1, suffix=("684",))),
    Case("C11", "Iron Greaves", "alchemy", "normal", 0.05122857786828192, ("MovementVelocity6",), (), None,
         _final(base_id="39", method="alchemy", req_max_groups=3, prefix=("2135",))),
    Case("C12", "Iron Greaves", "regal", "magic", 0.0030637254901960784, ("ChaosResist6",),
         ("MovementVelocity6", "FireResist8"), None,
         _kernel(base_id="39", pool_side="both", suffix=("661",), exclude=("2135", "1628"))),
)


def _mod_ref(data: ActionData, mod_id: str) -> ModRef:
    row = data.mods[mod_id]
    return ModRef(mod_id, row["type"], row["group"])


def our_probability(case: Case, data: ActionData) -> tuple[float, dict[str, int]]:
    item = ItemState(
        case.base,
        ITEM_LEVEL,
        case.rarity,
        tuple(_mod_ref(data, mod_id) for mod_id in case.existing),
    )
    labels = {target: target for target in case.targets}
    distribution = action_distribution(case.action, item, data, labels, essence_id=case.essence_id)
    chance = probability(distribution, lambda outcome: all(target in outcome.labels for target in case.targets))
    scenario = prepare_roll(case.action, item, data, labels, essence_id=case.essence_id)
    totals = {"prefix": 0, "suffix": 0}
    for entry in scenario.entries:
        totals[entry.type.lower()] += entry.weight
    return chance, totals


def _pob_values(row: dict[str, Any], pob_id: str) -> tuple[tuple[int, ...], ...]:
    stat_text = row.get("stat_text")
    if not isinstance(stat_text, list) or len(stat_text) != 1 or not isinstance(stat_text[0], str):
        raise ValueError(f"PoB {pob_id} must have exactly one string stat_text for this comparison")
    ranges = tuple((int(low), int(high)) for low, high in re.findall(r"\((\d+)-(\d+)\)", stat_text[0]))
    if ranges:
        return ranges
    scalars = re.findall(r"\b(\d+)\b", stat_text[0])
    if len(scalars) != 1:
        raise ValueError(f"PoB {pob_id} has unsupported stat text for range comparison: {stat_text[0]!r}")
    return ((int(scalars[0]),),)


def _coe_values(value: object, label: str) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, str):
        raise ValueError(f"CoE {label} range is not a JSON string")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"CoE {label} range is invalid JSON") from error
    if not isinstance(decoded, list) or not decoded:
        raise ValueError(f"CoE {label} range must be a non-empty list")
    if all(type(entry) is int for entry in decoded):
        return (tuple(decoded),)
    if all(isinstance(entry, list) and entry and all(type(number) is int for number in entry) for entry in decoded):
        return tuple(tuple(entry) for entry in decoded)
    raise ValueError(f"CoE {label} range has unsupported values")


def validate_correspondence(
    data: ActionData, pob_id: str, coe: dict[str, Any], *, case_id: str, role: str,
) -> dict[str, Any]:
    """Require one configured CoE record to match its PoB side, level, and values."""
    row = data.mods.get(pob_id)
    if row is None:
        raise ValueError(f"{case_id} {role}: missing PoB modifier {pob_id}")
    expected_side = row.get("type")
    actual_side = coe.get("side")
    side = {"prefix": "Prefix", "suffix": "Suffix"}.get(actual_side)
    if side != expected_side:
        raise ValueError(f"{case_id} {role} side mismatch for {pob_id}: PoB={expected_side!r}, CoE={actual_side!r}")
    expected_level = row.get("level")
    actual_level = coe.get("level")
    if actual_level != expected_level:
        raise ValueError(f"{case_id} {role} level mismatch for {pob_id}: PoB={expected_level!r}, CoE={actual_level!r}")
    expected_values = _pob_values(row, pob_id)
    actual_values = _coe_values(coe.get("range"), f"{case_id} {role} {coe.get('aid')}")
    if actual_values != expected_values:
        raise ValueError(f"{case_id} {role} range mismatch for {pob_id}: PoB={expected_values!r}, CoE={actual_values!r}")
    return {
        "role": role,
        "pob_id": pob_id,
        "coe_aid": coe.get("aid"),
        "side": side,
        "level": actual_level,
        "values": [list(value) for value in actual_values],
    }


def _existing_tier_for_pob(
    excluded: dict[str, Any], data: ActionData, pob_id: str, case_id: str,
) -> dict[str, Any]:
    row = data.mods[pob_id]
    tiers = excluded.get("tiers")
    if not isinstance(tiers, list):
        raise ValueError(f"{case_id} existing {pob_id}: excluded CoE modifier has no tier list")
    matches = [tier for tier in tiers if tier.get("level") == row.get("level")]
    if len(matches) != 1:
        raise ValueError(f"{case_id} existing {pob_id}: CoE level match is missing or ambiguous")
    return {"aid": excluded.get("aid"), "side": excluded.get("side"), **matches[0]}


def validate_case_correspondences(case: Case, coe: dict[str, Any], data: ActionData) -> list[dict[str, Any]]:
    """Validate selected target, existing, and forced modifier correspondences."""
    checked: list[dict[str, Any]] = []
    targets = coe.get("targets")
    if not isinstance(targets, dict):
        raise ValueError(f"{case.id}: CoE result lacks targets")
    for side, pob_ids in (("prefix", tuple(target for target in case.targets if data.mods[target]["type"] == "Prefix")),
                          ("suffix", tuple(target for target in case.targets if data.mods[target]["type"] == "Suffix"))):
        coe_targets = targets.get(side)
        if not isinstance(coe_targets, list) or len(coe_targets) != len(pob_ids):
            raise ValueError(f"{case.id}: target count mismatch on {side}")
        checked.extend(
            validate_correspondence(data, pob_id, target, case_id=case.id, role="target")
            for pob_id, target in zip(pob_ids, coe_targets, strict=True)
        )
    if case.existing:
        excluded_aids = case.coe.get("exclude_aids")
        excluded_modifiers = coe.get("excluded_modifiers")
        if not isinstance(excluded_aids, list) or not isinstance(excluded_modifiers, list) or len(excluded_aids) != len(case.existing):
            raise ValueError(f"{case.id}: existing modifier mappings are incomplete")
        by_aid = {entry.get("aid"): entry for entry in excluded_modifiers if isinstance(entry, dict)}
        for pob_id, aid in zip(case.existing, excluded_aids, strict=True):
            excluded = by_aid.get(aid)
            if excluded is None:
                raise ValueError(f"{case.id} existing {pob_id}: CoE excluded modifier {aid} is absent")
            checked.append(validate_correspondence(
                data, pob_id, _existing_tier_for_pob(excluded, data, pob_id, case.id), case_id=case.id, role="existing",
            ))
    if case.forced_pob_id:
        forced = coe.get("forced_essence")
        if not isinstance(forced, dict):
            raise ValueError(f"{case.id}: forced essence modifier is absent")
        checked.append(validate_correspondence(data, case.forced_pob_id, forced, case_id=case.id, role="forced"))
    return checked


def _run_coe(cases: tuple[Case, ...]) -> dict[str, Any]:
    for source in (NODE_RUNNER, PACKAGE_SOURCE, DATA_SOURCE):
        if not source.exists():
            raise FileNotFoundError(f"required offline CoE source is missing: {source}")
    completed = subprocess.run(
        ["node", str(NODE_RUNNER)],
        cwd=ROOT,
        input=json.dumps({"command": "batch", "cases": [case.coe for case in cases]}),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(f"offline CoE runner failed: {completed.stderr.strip()}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("offline CoE runner returned invalid JSON") from error
    if not isinstance(result.get("cases"), list) or len(result["cases"]) != len(cases):
        raise RuntimeError("offline CoE runner returned an unexpected case count")
    return result


def run() -> dict[str, Any]:
    started = time.monotonic()
    data = load_action_data(ROOT)
    ours = [our_probability(case, data) for case in CASES]
    for case, (measured, _) in zip(CASES, ours, strict=True):
        if not math.isclose(measured, case.expected_ours, rel_tol=1e-14, abs_tol=1e-18):
            raise RuntimeError(
                f"our probability changed for {case.id}: expected {case.expected_ours:.17g}, got {measured:.17g}"
            )
    coe = _run_coe(CASES)
    results = []
    for case, (our_value, our_totals), coe_value in zip(CASES, ours, coe["cases"], strict=True):
        external = float(coe_value["probability"])
        results.append({
            "id": case.id,
            "base": case.base,
            "action": case.action,
            "rarity": case.rarity,
            "item_level": ITEM_LEVEL,
            "targets": list(case.targets),
            "expected_ours": case.expected_ours,
            "existing_ids": list(case.existing),
            "essence_id": case.essence_id,
            "correspondences": validate_case_correspondences(case, coe_value, data),
            "ours": our_value,
            "coe": external,
            "relative_difference": (our_value - external) / external,
            "ours_pool_totals": our_totals,
            "coe_result": coe_value,
        })
    return {
        "case_count": len(results),
        "node_version": coe["node_version"],
        "source_hashes": coe["source_hashes"],
        "runtime_minutes": (time.monotonic() - started) / 60,
        "cases": results,
    }


def _format_table(report: dict[str, Any]) -> str:
    lines = ["id\taction\trarity\tilvl\tours\tcoe\trelative_difference\tours_prefix\tours_suffix\tcoe_prefix\tcoe_suffix\tcoe_combined\tmethod"]
    for row in report["cases"]:
        coe = row["coe_result"]
        coe_totals = coe.get("pool_totals") or coe.get("side_pool_totals") or {"prefix": "", "suffix": ""}
        lines.append("\t".join((
            row["id"], row["action"], row["rarity"], str(row["item_level"]), f"{row['ours']:.16g}", f"{row['coe']:.16g}",
            f"{row['relative_difference']:.16g}", str(row["ours_pool_totals"]["prefix"]),
            str(row["ours_pool_totals"]["suffix"]), str(coe_totals.get("prefix", "")),
            str(coe_totals.get("suffix", "")), str(coe.get("combined_pool_total", "")), coe["method"],
        )))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    report = run()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "comparison.tsv").write_text(_format_table(report), encoding="utf-8")
    print(_format_table(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
