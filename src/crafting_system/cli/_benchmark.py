"""`benchmark`: the solver's route and the guide's route for each benchmark route, with machine info and run times.

ADR-0013's pass rule is that at equal prices the solver's route costs no more than the guide's and that
the guide's published odds match. A guide states no cost, so its cost is its given route (a YAML file)
evaluated at the same prices as the solver's. For every benchmark route that has a target and a given
route this command plans the target, evaluates the given route, recomputes the published odds, and
writes everything to `<output dir>/benchmark.json`. It NEVER fails a route: an odds mismatch, a solver
dearer than the guide or a route that cannot be planned (a missing price, a bad file) is written into
that route's entry, and the exit code stays 0. Only game data that cannot be read, or an output that
cannot be written, is an error.
"""

import argparse
import os
import platform
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path

import yaml

from crafting_system.actions import ActionError
from crafting_system.config import Config, find_project_root, load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import PriceFile, PriceFileNotFound, default_price_file_path, stale_warning
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME
from crafting_system.prices.price_names import canonical_price_name
from crafting_system.risk import Estimate
from crafting_system.solver import ConvergenceError
from crafting_system.targets import KOfN, Requirement, Target, load_target

from ._benchmark_outcomes import ADDS, FRACTURED, REMOVED, PublishedOutcome, published_outcomes
from ._inputs import load_target_prices, write_json
from ._offers import default_offers
from ._plan import Plan, make_plan
from ._report import describe_state, money, number_states, percent
from ._route import RouteResult, evaluate_route, load_route
from ._shares import weight_share

FORMAT = "crafting-system-benchmark/1"
FILE_NAME = "benchmark.json"
START_ITEM = "start item"
NO_MODS = "same item without any mod"
SAME_MEAN = 1e-9  # the solver's mean may exceed the guide's by this much (relative) and still count as not dearer


@dataclass(frozen=True)
class PublishedOdds:
    """A number a guide publishes: the single-draw weight share of `action` for the requirement with stat text `requirement`.

    `on` says which item it was quoted on, `published` is the text as the guide writes it, with as many
    decimals as it gives.
    """

    action: str
    requirement: str
    on: str
    published: str


@dataclass(frozen=True)
class BenchmarkRoute:
    """A benchmark route that has a target and a given route; both paths count from the project root."""

    id: str
    title: str
    target: str
    route: str
    odds: tuple[PublishedOdds, ...]
    outcomes: tuple[PublishedOutcome, ...] = ()
    heavy: str | None = None  # why the planner needs hours here: `benchmark` then checks the published odds only, unless asked with --heavy


GEM = "+1 to Level of all Lightning Skill Gems"
PIERCE, STRENGTH, ARROW, LIFE_TOP = "AdditionalPierceEssence7", "StrengthEssence7_", "AdditionalArrowQuiver1_", "IncreasedLife9"
NO_ATTACK, MULTIMOD = "IntMasterItemGenerationCannotRollAttackAffixes", "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"
SPEED, GEMS, DOT = "LocalIncreasedAttackSpeed5", "LocalIncreaseSocketedGemLevel1", "PoisonDamagePrefixInfluence4"
BOW_TOP = "DamageWithBowSkills5"  # tier 2 of Damage with Bow Skills, the top tier at item level 81
DOT_TIERS = ("PoisonDamagePrefixInfluence1__", "PoisonDamagePrefixInfluence2__", "PoisonDamagePrefixInfluence3", DOT)

BENCHMARKS = (
    BenchmarkRoute(
        "R12",
        "Fractured Lightning Resistance +1 Lightning amulet (PoE Vault guide)",
        "examples/targets/r12-lightning-amulet.yaml",
        "examples/routes/r12-lightning-amulet.yaml",
        (
            PublishedOdds("Harvest Reforge Lightning", GEM, START_ITEM, "2.88%"),
            PublishedOdds("Harvest Reforge Lightning", GEM, NO_MODS, "1.338%"),
        ),
    ),
    # The guides of these six publish no odds, so there is nothing to recompute (tickets #60, #63 and #66).
    BenchmarkRoute(
        "R10",
        "Fractured Movement Speed Intelligence boots (PoE Vault guide)",
        "examples/targets/r10-fractured-boots.yaml",
        "examples/routes/r10-fractured-boots.yaml",
        (),
    ),
    BenchmarkRoute(
        "R11",
        "Fractured Chaos Resistance reservation helmet (TbXie guide)",
        "examples/targets/r11-reservation-helmet.yaml",
        "examples/routes/r11-reservation-helmet.yaml",
        (),
    ),
    BenchmarkRoute(
        "R05",
        "Budget fractured All Attributes Strength ring (PoE Vault guide)",
        "examples/targets/r05-strength-ring.yaml",
        "examples/routes/r05-strength-ring.yaml",
        (),
    ),
    BenchmarkRoute(
        "R13",
        "Alt-regal tier-1 life double-resistance belt (Reddit guide)",
        "examples/targets/r13-life-resist-belt.yaml",
        "examples/routes/r13-life-resist-belt.yaml",
        (),
    ),
    BenchmarkRoute(
        "R08",
        "Dense + Shuddering Energy Shield boots (PoE Vault guide)",
        "examples/targets/r08-energy-shield-boots.yaml",
        "examples/routes/r08-energy-shield-boots.yaml",
        (),
    ),
    BenchmarkRoute(
        "R09",
        "Pristine + Shuddering Life boots (PoE Vault guide)",
        "examples/targets/r09-life-boots.yaml",
        "examples/routes/r09-life-boots.yaml",
        (),
    ),
    BenchmarkRoute(
        "R04",
        "Insanity-fractured additional-arrow Penetrating Arrow Quiver (PoE Vault guide)",
        "examples/targets/r04-penetrating-quiver.yaml",
        "examples/routes/r04-penetrating-quiver.yaml",
        (),
        (
            PublishedOutcome(
                "Fracturing Orb", "fractures the Pierce", "a rare quiver with exactly 4 mods, the Pierce among them",
                (PIERCE, LIFE_TOP, STRENGTH, ARROW), FRACTURED, (PIERCE,), "25%",
            ),
            PublishedOutcome(
                "Exalted Orb", "adds Maximum Life or Increased Damage with Bow Skills (each of the two forced Exalted Orbs)",
                "the quiver with the Pierce fractured, the Strength, the arrow and \"Cannot roll Attack Modifiers\"",
                (PIERCE, STRENGTH, ARROW, NO_ATTACK), ADDS, (), "100%",
                fractured=(PIERCE,), crafted=(NO_ATTACK,), families=("IncreasedLife", "DamageWithWeaponTypeSkill"),
            ),
            PublishedOutcome(  # the same Exalted Orb read at the target's tiers (owner rule: an unstated tier is the top tier)
                "Exalted Orb", "adds the TOP tier of Maximum Life or of Increased Damage with Bow Skills (the target's tiers)",
                "the quiver with the Pierce fractured, the Strength, the arrow and \"Cannot roll Attack Modifiers\"",
                (PIERCE, STRENGTH, ARROW, NO_ATTACK), ADDS, (LIFE_TOP, BOW_TOP), "100%",
                fractured=(PIERCE,), crafted=(NO_ATTACK,),
            ),
            PublishedOutcome(  # the second forced Exalted Orb: Maximum Life is already on the quiver
                "Exalted Orb", "adds Increased Damage with Bow Skills (the second forced Exalted Orb), any tier",
                "the quiver of the row above with Maximum Life added",
                (PIERCE, STRENGTH, ARROW, NO_ATTACK, LIFE_TOP), ADDS, (), "100%",
                fractured=(PIERCE,), crafted=(NO_ATTACK,), families=("DamageWithWeaponTypeSkill",),
            ),
            PublishedOutcome(
                "Exalted Orb", "adds the TOP tier of Increased Damage with Bow Skills (the second Exalted Orb, the target's tier)",
                "the quiver of the row above with Maximum Life added",
                (PIERCE, STRENGTH, ARROW, NO_ATTACK, LIFE_TOP), ADDS, (BOW_TOP,), "100%",
                fractured=(PIERCE,), crafted=(NO_ATTACK,),
            ),
        ),
        heavy="the exact graph needs more memory than a 16 GB runner has (ticket #70)",
    ),
    BenchmarkRoute(
        "R14",
        "Toxic Rain Hunter bow with +1 socketed gems and chaos damage over time (Reddit guide)",
        "examples/targets/r14-hunter-bow.yaml",
        "examples/routes/r14-hunter-bow.yaml",
        (),
        (
            PublishedOutcome(
                "Orb of Annulment", "removes the Attack Speed", "a rare bow with 3 mods, the Attack Speed among them",
                (SPEED, GEMS, DOT), REMOVED, (SPEED,), "33%",
            ),
            PublishedOutcome(
                "Orb of Annulment", "removes the Attack Speed", "a rare bow with 2 mods, the Attack Speed among them",
                (SPEED, GEMS), REMOVED, (SPEED,), "50%",
            ),
            PublishedOutcome(
                "Exalted Orb", "adds +1 to Level of Socketed Gems or Chaos Damage over Time (the first forced Exalted Orb)",
                "the bow with the Attack Speed, \"Can have up to 3 Crafted Modifiers\" and \"Cannot roll Attack Modifiers\"",
                (SPEED, MULTIMOD, NO_ATTACK), ADDS, (GEMS, *DOT_TIERS), "100%", crafted=(MULTIMOD, NO_ATTACK),
            ),
            PublishedOutcome(  # the same Exalted Orb read at the target's tiers (owner rule: an unstated tier is the top tier)
                "Exalted Orb", "adds +1 to Level of Socketed Gems or the TOP tier of Chaos Damage over Time (the target's tiers)",
                "the bow with the Attack Speed, \"Can have up to 3 Crafted Modifiers\" and \"Cannot roll Attack Modifiers\"",
                (SPEED, MULTIMOD, NO_ATTACK), ADDS, (GEMS, DOT), "100%", crafted=(MULTIMOD, NO_ATTACK),
            ),
            PublishedOutcome(  # the second forced Exalted Orb: +1 gems is already on the bow
                "Exalted Orb", "adds Chaos Damage over Time (the second forced Exalted Orb), any tier",
                "the bow of the rows above with +1 to Level of Socketed Gems added",
                (SPEED, MULTIMOD, NO_ATTACK, GEMS), ADDS, DOT_TIERS, "100%", crafted=(MULTIMOD, NO_ATTACK),
            ),
            PublishedOutcome(
                "Exalted Orb", "adds the TOP tier of Chaos Damage over Time (the second Exalted Orb, the target's tier)",
                "the bow of the rows above with +1 to Level of Socketed Gems added",
                (SPEED, MULTIMOD, NO_ATTACK, GEMS), ADDS, (DOT,), "100%", crafted=(MULTIMOD, NO_ATTACK),
            ),
        ),
        heavy="the exact graph has more than 570,000 states and no approximate level exists for a route with metamods (ticket #70)",
    ),
)

class _Skipped(Exception):
    """A heavy route that `benchmark` leaves unsolved; its entry already says why."""


# What a route can fail with; each is written into the route's entry, none ends the command.
ROUTE_ERRORS = (ValueError, OSError, DataError, PriceFileNotFound, ActionError, ConvergenceError)


def benchmark_main(
    argv: Sequence[str],
    *,
    command: str,
    env: Mapping[str, str] | None = None,
    today: date | None = None,
    data: GameData | None = None,
    prices: PriceFile | None = None,
) -> int:
    """Run the benchmark and return 0 (1 only when the game data cannot be read or the output cannot be written)."""
    parser = argparse.ArgumentParser(
        prog=f"{command} benchmark",
        description="Run the solver and the given route of every benchmark route and write benchmark.json.",
    )
    parser.add_argument("--out", metavar="DIR", help="where to write benchmark.json (default: the output dir)")
    parser.add_argument("--heavy", action="store_true", help="also solve the routes that take the planner hours (R04, R14); without it only their published odds are checked")
    args = parser.parse_args(list(argv))

    try:
        config = load_config(env)
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
        root = find_project_root()
        out_dir = Path(args.out) if args.out else config.output_dir
        entries = []
        used_prices: PriceFile | None = None
        for bench in BENCHMARKS:
            entry, loaded = run_route(bench, game, root, config, prices, today, heavy=args.heavy)
            entries.append(entry)
            used_prices = used_prices or loaded
        document = {
            "format": FORMAT,
            "machine": machine_info(root),
            "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "prices": None
            if used_prices is None
            else {"league": used_prices.league, "fetched_at": used_prices.fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ")},
            "routes": entries,
        }
        write_json(out_dir / FILE_NAME, document)
        print(render_summary(document))
        print(f"Benchmark written to {out_dir / FILE_NAME}")
    except (DataError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def machine_info(root: Path) -> dict:
    """The machine the numbers came from: OS, CPU, Python and the commit of the checkout."""
    return {
        "os": f"{platform.system()} {platform.release()}".strip(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine() or "unknown",
        "cpu_count": os.cpu_count() or 1,
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "commit": _commit(root),
    }


def _commit(root: Path) -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    text = done.stdout.strip()
    return text if done.returncode == 0 and text else "unknown"


# --- one route -----------------------------------------------------------------------------------


def run_route(
    bench: BenchmarkRoute,
    data: GameData,
    root: Path,
    config: Config,
    prices: PriceFile | None,
    today: date | None,
    *,
    heavy: bool = False,
) -> tuple[dict, PriceFile | None]:
    """The entry of one benchmark route, and the price file it was run on (None when none was loaded).

    A failure is written to `entry["error"]`; what was done before it stays in the entry.
    """
    entry: dict = {
        "id": bench.id,
        "title": bench.title,
        "target": bench.target,
        "route": bench.route,
        "error": None,
        "missing_price": None,
        "solver": None,
        "given_route": None,
        "published_odds": [],
        "solver_not_dearer": None,
        "timings_seconds": None,
    }
    timings: dict[str, float | None] = {"solver": None, "risk_evaluate": None, "route_evaluate": None}
    loaded: PriceFile | None = None
    began = time.perf_counter()
    try:
        target = load_target(root / bench.target, data)
        entry["published_odds"] = published_outcomes(data, target, bench.outcomes)  # needs no plan, so a refused route still has them
        if bench.heavy is not None and not heavy:
            entry["error"] = f"not solved: {bench.heavy} (run `benchmark --heavy` to solve it)"
            raise _Skipped
        loaded = prices if prices is not None else load_target_prices(target.price_file, config)
        stale = stale_warning(loaded, today if today is not None else datetime.now(UTC).date())
        if stale:
            print(f"Warning: {stale}", file=sys.stderr)
        missing = _missing_start_price(target, loaded, root, config)
        entry["missing_price"] = missing
        if missing is not None:
            raise ValueError(_missing_message(missing))
        plan = make_plan(data, target, loaded)
        shift = plan.start_price.chaos
        risk = plan.risk
        entry["solver"] = _totals(risk.success_probability, risk.mean, risk.p50, risk.p90, shift)
        entry["solver"]["seconds"] = plan.solve_seconds
        timings["solver"], timings["risk_evaluate"] = plan.solve_seconds, plan.risk_seconds
        entry["published_odds"] += published_odds(data, plan, bench)

        route = load_route(root / bench.route, plan, data)
        result = evaluate_route(plan, route, data)
        entry["given_route"] = _given_route(plan, result, data, shift)
        timings["route_evaluate"] = result.seconds
        entry["solver_not_dearer"] = _not_dearer(entry["solver"]["mean"], entry["given_route"]["mean"])
    except _Skipped:
        pass
    except ROUTE_ERRORS as error:
        entry["error"] = _without_root(str(error), root)
    timings["total"] = time.perf_counter() - began
    entry["timings_seconds"] = timings
    return entry, loaded


def _missing_start_price(target: Target, prices: PriceFile, root: Path, config: Config) -> dict | None:
    """What a route misses when its start item has no price in `prices`, else None.

    The overrides file is the one `load_target_prices` reads beside the price file. The buy spec is only
    named, never run: the benchmark does not call the trade API, so a run stays reproducible and offline.
    """
    if target.start_price is None:
        return None
    name = canonical_price_name(target.start_price)
    if name in prices.prices:
        return None
    price_file = target.price_file if target.price_file is not None else default_price_file_path(config)
    return {
        "name": name,
        "override_line": f'"{name}" = 0',
        "overrides_file": _without_root(str(price_file.parent / OVERRIDES_FILE_NAME), root),
        "buy_spec": _buy_spec_named(name, root),
    }


def _buy_spec_named(name: str, root: Path) -> str | None:
    """The path, from the project root, of the buy spec in examples/buy/ whose top-level `name:` is `name`, else None."""
    for spec in sorted((root / "examples" / "buy").glob("*.yaml")):
        try:
            record = yaml.safe_load(spec.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        if isinstance(record, dict) and record.get("name") == name:
            return spec.relative_to(root).as_posix()
    return None


def _missing_message(missing: dict) -> str:
    """The error of a route whose start item has no price: the line to write, and the trade command if a buy spec exists."""
    text = (
        f"no price for the start item {missing['name']!r}. Add this line under [prices] in "
        f"{missing['overrides_file']}: {missing['override_line']}, then replace the 0 with the item's price in Chaos Orbs "
        "(a 0 left in place is refused by the overrides loader, which names the item)"
    )
    if missing["buy_spec"] is not None:
        text += f", or price it on the trade API with: python -m crafting_system.prices trade --spec {missing['buy_spec']}"
    return text + "."


def _without_root(text: str, root: Path) -> str:
    """`text` with the project root cut off the paths in it, so that no written file holds an absolute path."""
    for prefix in (f"{root}{os.sep}", f"{root.as_posix()}/"):
        text = text.replace(prefix, "")
    return text


def _number(value: float) -> float | None:
    return None if value != value or value in (float("inf"), float("-inf")) else value


def _totals(success: Estimate, mean: Estimate, p50: Estimate, p90: Estimate, shift: float) -> dict:
    return {
        "success": _number(success.value),
        "mean": _number(mean.value + shift),
        "p50": _number(p50.value + shift),
        "p90": _number(p90.value + shift),
    }


def _given_route(plan: Plan, result: RouteResult, data: GameData, shift: float) -> dict:
    risk = result.risk
    found = _totals(risk.success_probability, risk.mean, risk.p50, risk.p90, shift)
    divergence = result.divergence
    found["gaps"] = len(result.gaps)
    found["first_divergence"] = (
        None
        if divergence is None
        else {
            "state": number_states(plan)[divergence.state],
            "description": describe_state(plan, data, divergence.state),
            "solver_action": divergence.solver_action,
            "route_action": divergence.route_action,
        }
    )
    found["seconds"] = result.seconds
    return found


def _not_dearer(solver_mean: float | None, given_mean: float | None) -> bool:
    """Whether the solver's mean is at most the guide's (a guide that never finishes is dearer than anything)."""
    if solver_mean is None:
        return False
    if given_mean is None:
        return True
    return solver_mean <= given_mean * (1.0 + SAME_MEAN)


# --- published odds ------------------------------------------------------------------------------


def _mods_of(target: Target, stat: str) -> frozenset[str]:
    """The mod ids of the target's requirement with stat text `stat`."""
    found: list[frozenset[str]] = []

    def walk(node: Requirement | KOfN) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        elif node.stat == stat:
            found.append(node.mod_ids)

    for node in target.requirements:
        walk(node)
    if not found:
        raise ValueError(f"the target has no requirement with the stat text {stat!r}")
    return found[0]


def published_odds(data: GameData, plan: Plan, bench: BenchmarkRoute) -> list[dict]:
    """Each published single-draw share recomputed from the pool, formatted to the guide's decimals, and compared."""
    offers = {offer.label: offer for offer in default_offers()}
    start = plan.target.start_item
    found = []
    for odds in bench.odds:
        item = start if odds.on == START_ITEM else start.changed(data, mods=())
        wanted, total = weight_share(data, item, _mods_of(plan.target, odds.requirement), offers[odds.action].tag)
        share = Fraction(wanted) / Fraction(total) if total else Fraction(0)
        decimals = len(odds.published.rstrip("%").partition(".")[2])
        computed = f"{float(share) * 100:.{decimals}f}%"
        found.append(
            {
                "action": odds.action,
                "requirement": odds.requirement,
                "on": odds.on,
                "published": odds.published,
                "computed": computed,
                "matches": computed == odds.published,
                "wanted_weight": _weight(wanted),
                "candidate_weight": _weight(total),
                "share": float(share),
            }
        )
    return found


def _weight(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


# --- the summary ---------------------------------------------------------------------------------


def render_summary(document: dict) -> str:
    """A short ASCII summary of `document` for the terminal."""
    machine = document["machine"]
    lines = [
        f"Benchmark on {machine['os']}, {machine['cpu_count']} CPUs, {machine['python']}, commit {machine['commit'][:12]}"
    ]
    for entry in document["routes"]:
        lines.append(f"{entry['id']}: {entry['title']}")
        if entry["solver"] is not None:
            lines.append("  solver       " + _summary_line(entry["solver"]))
        if entry["given_route"] is not None:
            given = entry["given_route"]
            lines.append("  given route  " + _summary_line(given) + f", {given['gaps']} gap(s)")
            divergence = given["first_divergence"]
            if divergence is not None:
                lines.append(
                    f"  first divergence {divergence['state']}: policy does {divergence['solver_action']}, "
                    f"route does {divergence['route_action']}"
                )
        for odds in entry["published_odds"]:
            verdict = "matches" if odds["matches"] else "DIFFERS"
            lines.append(f"  published odds {odds['published']} ({odds['on']}): computed {odds['computed']}, {verdict}")
        if entry["solver_not_dearer"] is not None:
            lines.append("  solver not dearer than the guide: " + ("yes" if entry["solver_not_dearer"] else "NO"))
        if entry["error"] is not None:
            lines.append(f"  error: {entry['error']}")
        if entry["missing_price"] is not None:
            lines.append(f"  add to {entry['missing_price']['overrides_file']} under [prices]:")
            lines.append(f"    {entry['missing_price']['override_line']}")
    return "\n".join(lines)


def _summary_line(totals: dict) -> str:
    mean = money(float("inf") if totals["mean"] is None else totals["mean"])
    success = percent(totals["success"] if totals["success"] is not None else 0.0)
    return f"success {success}, mean {mean} Chaos, {totals['seconds'] * 1000:.0f} ms"
