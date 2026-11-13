"""`benchmark`: the solver's route and the guide's route for each benchmark route, with machine info and run times.

ADR-0013's pass rule is that at equal prices the solver's route costs no more than the guide's and that
the guide's published odds match. A guide states no cost, so its cost is its given route (a YAML file)
evaluated at the same prices as the solver's. For every benchmark route that has a target and a given
route this command plans the target, evaluates the given route, recomputes the published odds, and
writes everything to `<output dir>/benchmark.json`. It NEVER fails a route: an odds mismatch, a solver
dearer than the guide or a route that cannot be planned (a missing price, a bad file) is written into
that route's entry, and the exit code stays 0. Only game data that cannot be read, or an output that
cannot be written, is an error.

The check is on both sides (ticket #554): beside "the planner is not dearer than the guide" each route with a given route carries every
state where the two part, with the chance of visiting it under each policy, the ratio planner mean / guide mean, and a "needs a human"
row when that ratio is below the review line of the config (`_benchmark_divergence`). The row is a prompt, never a verdict or a cut. A route that a person
has taken apart carries a reviewed verdict (`_benchmark_verdicts`, ticket #634) and prints it until its ratio, its files or the planner's first divergent
action have moved; the first divergence tells the chance and the cost of one use of both actions (ticket #617).
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

from crafting_system.actions import imprints_held_at_most
from crafting_system.config import Config, find_project_root, load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import PriceFile, PriceFileNotFound, default_price_file_path, planned_price, stale_warning
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME
from crafting_system.risk import Estimate
from crafting_system.solver import ConvergenceError
from crafting_system.targets import KOfN, Requirement, StartKind, Target, load_target, start_price_key

from ._benchmark_divergence import divergence_lines, divergences_of, first_divergence_of, mean_ratio, review_lines, review_of
from ._benchmark_verdicts import COMPLETED, GUIDE, Reviewing, text_hash, verdict_of
from ._benchmark_outcomes import ADDS, FRACTURED, REMOVED, PublishedOutcome, published_outcomes
from ._inputs import load_target_prices, write_json
from ._offers import default_offers
from ._plan import Plan, make_plan
from ._report import interval_answer_of, money, name_states, number_states, percent
from ._route import RouteResult, evaluate_route, load_route
from ._shares import weight_share
from ._start_report import first_step_document
from ._start_step import first_step
from ._starts import plan_with_starts

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
class ExpectedStart:
    """The start item a benchmark route is meant to begin from, and why that start wins (ADR-0059, ticket #331).

    `key` is the key of the start candidate the plan should choose (`vendor:minion_helmet:1`; `plain` for the target's own start
    item) and `why` is the explanation printed with the answer. A route with one is planned with the start options, not from the
    target's own start item alone, and the entry records the choice and whether it is the expected one. It never fails the run.
    """

    key: str
    why: str


@dataclass(frozen=True)
class BenchmarkRoute:
    """A benchmark route that has a target, usually a given route, and sometimes an expected start; paths count from the project root.

    `route` is None for a route that has no guide to compare with (V01: no guide writes a route for a recipe-made start item); the
    entry then has no given-route half. `start` is the expected start of a route that begins from a vendor recipe.
    """

    id: str
    title: str
    target: str
    route: str | None
    odds: tuple[PublishedOdds, ...]
    outcomes: tuple[PublishedOutcome, ...] = ()
    heavy: str | None = None  # why the planner needs minutes of a big machine here: `benchmark` then checks the published odds only, unless asked with --heavy
    start: ExpectedStart | None = None
    completed: str | None = None  # the given route with a last rule that restarts, so that its mean is finite (the guide's own route has gaps): evaluated beside it


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
            PublishedOutcome(  # the same Exalted Orb read at the target's tiers (OR-1): the guide's 100% is of the family, so no number is published (#599)
                "Exalted Orb", "adds the TOP tier of Maximum Life or of Increased Damage with Bow Skills (the target's tiers)",
                "the quiver with the Pierce fractured, the Strength, the arrow and \"Cannot roll Attack Modifiers\"",
                (PIERCE, STRENGTH, ARROW, NO_ATTACK), ADDS, (LIFE_TOP, BOW_TOP), None,
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
                (PIERCE, STRENGTH, ARROW, NO_ATTACK, LIFE_TOP), ADDS, (BOW_TOP,), None,
                fractured=(PIERCE,), crafted=(NO_ATTACK,),
            ),
        ),
        heavy="the exact graph has 177,242 states and 536 million transitions: the packed solver takes about 10 minutes and 6 GB (ticket #70)",
        completed="examples/routes/r04-penetrating-quiver-restart.yaml",
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
            PublishedOutcome(  # the same Exalted Orb read at the target's tiers (OR-1): the guide's 100% is of the family, so no number is published (#599)
                "Exalted Orb", "adds +1 to Level of Socketed Gems or the TOP tier of Chaos Damage over Time (the target's tiers)",
                "the bow with the Attack Speed, \"Can have up to 3 Crafted Modifiers\" and \"Cannot roll Attack Modifiers\"",
                (SPEED, MULTIMOD, NO_ATTACK), ADDS, (GEMS, DOT), None, crafted=(MULTIMOD, NO_ATTACK),
            ),
            PublishedOutcome(  # the second forced Exalted Orb: +1 gems is already on the bow
                "Exalted Orb", "adds Chaos Damage over Time (the second forced Exalted Orb), any tier",
                "the bow of the rows above with +1 to Level of Socketed Gems added",
                (SPEED, MULTIMOD, NO_ATTACK, GEMS), ADDS, DOT_TIERS, "100%", crafted=(MULTIMOD, NO_ATTACK),
            ),
            PublishedOutcome(
                "Exalted Orb", "adds the TOP tier of Chaos Damage over Time (the second Exalted Orb, the target's tier)",
                "the bow of the rows above with +1 to Level of Socketed Gems added",
                (SPEED, MULTIMOD, NO_ATTACK, GEMS), ADDS, (DOT,), None, crafted=(MULTIMOD, NO_ATTACK),
            ),
        ),
        heavy="the exact graph has 816,153 states: the packed solver takes about 32 minutes and 9 GB, and no approximate level exists for a route with metamods (ticket #70)",
        completed="examples/routes/r14-hunter-bow-restart.yaml",
    ),
    # The guide publishes no odds (#223); the beasts of its imprint and the start Talisman are priced from its own price file.
    BenchmarkRoute(
        "R17",
        "+2 Lightning rare Talisman with the rare-Talisman imprint (Reddit guide)",
        "examples/targets/r17-lightning-talisman.yaml",
        "examples/routes/r17-lightning-talisman.yaml",
        (),
        heavy="the exact walk of the imprint loop passed 2.76 million states and 28 million transitions in an hour and did not end (heavy run 43308613718, #223): it waits for a bound or a value-carrying form of the held imprint (ADR-0060, #817)",
    ),
    # No guide writes a route for a recipe-made start item, so V01 has no given route: its answer is the start the plan chooses (ticket #331).
    BenchmarkRoute(
        "V01",
        "Minion helmet with +1 to Level of all Minion Skill Gems and top Life, started from the vendor recipe (research note on vendor recipes)",
        "examples/targets/v01-minion-helmet.yaml",
        None,
        (),
        start=ExpectedStart(
            "vendor:minion_helmet:1",
            "The +1 Minion gems mod is 250 of 114,675 weight of a Lion Pelt's pool, about one draw in 459, so Transmutation and Alteration "
            "find it rarely. The Minion helmet recipe makes a Magic helmet that holds exactly that mod for the base and two Minion gems "
            "with 40% quality in all; the rest of the craft only has to add the top Life. At the prices of tests/fixtures/prices/vendor-v01-2026-11-01.json the recipe start costs "
            "8 Chaos and the plan from it about 866 Chaos in all, against about 1,349 Chaos from the plain Normal helmet.",
        ),
    ),
)

def reads_own_prices(bench: BenchmarkRoute, root: Path) -> bool:
    """Whether a heavy script must let the route read the price file its target names instead of the committed snapshot of the routes.

    True for a route that starts from a vendor recipe (V01) and for a target that names its own price file (a top-level `price_file:`;
    R17, whose beasts and start Talisman are not in the snapshot, #223).
    """
    if bench.start is not None:
        return True
    return any(line.startswith("price_file:") for line in (root / bench.target).read_text(encoding="utf-8").splitlines())


class _Skipped(Exception):
    """A heavy route that `benchmark` leaves unsolved; its entry already says why."""


# What a route can fail with; each is written into the route's entry, none ends the command. `ValueError` stays the parent of both refusal families
# (a game refusal, a model gap) and of every other error of a route (a bad target, a bad price): the entry carries the text of whichever it was.
ROUTE_ERRORS = (ValueError, OSError, DataError, PriceFileNotFound, ConvergenceError)


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
        with imprints_held_at_most(config.max_imprints):  # the setting `max_imprints` for every plan of the run (#223)
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
        "start": None,
        "solver_not_dearer": None,
        "completed_route": None,
        "solver_not_dearer_than_completed": None,
        "interval": None,
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
        missing = _missing_start_price(data, target, loaded, root, config, bench.target)
        entry["missing_price"] = missing
        if missing is not None:
            raise ValueError(_missing_message(missing))
        judged = bench.route is not None  # the guide's route is judged against the plan: `auto` walks (#535, #732)
        plan = make_plan(data, target, loaded, judges_route=judged) if bench.start is None else plan_with_starts(data, target, loaded, judges_route=judged)
        entry["start"] = _start_entry(plan, data, bench.start)
        shift = plan.start_price.chaos
        risk = plan.risk
        entry["solver"] = _totals(risk.success_probability, risk.mean, risk.p50, risk.p90, shift)
        entry["solver"]["seconds"] = plan.solve_seconds
        timings["solver"], timings["risk_evaluate"] = plan.solve_seconds, plan.risk_seconds
        entry["published_odds"] += published_odds(data, plan, bench)
        answer = interval_answer_of(plan, data)
        if answer is not None:  # a plan that reads a rule axis (a recombinator, #225): approximate, with its cost at every reading and the route without it
            entry["interval"] = {"approximate": True, **answer.document()}

        if bench.route is not None:
            route = load_route(root / bench.route, plan, data)
            result = evaluate_route(plan, route, data)
            entry["given_route"] = _given_route(
                plan, result, data, shift, entry["solver"]["mean"], config.benchmark_review_ratio, _reviewing(bench, bench.route, GUIDE, root, config)
            )
            timings["route_evaluate"] = result.seconds
            entry["solver_not_dearer"] = _not_dearer(entry["solver"]["mean"], entry["given_route"]["mean"])
            if bench.completed is not None:
                again = evaluate_route(plan, load_route(root / bench.completed, plan, data), data)
                entry["completed_route"] = _given_route(
                    plan, again, data, shift, entry["solver"]["mean"], config.benchmark_review_ratio,
                    _reviewing(bench, bench.completed, COMPLETED, root, config),
                )
                timings["completed_route_evaluate"] = again.seconds
                entry["solver_not_dearer_than_completed"] = _not_dearer(entry["solver"]["mean"], entry["completed_route"]["mean"])
    except _Skipped:
        pass
    except ROUTE_ERRORS as error:
        entry["error"] = _without_root(str(error), root)
    timings["total"] = time.perf_counter() - began
    entry["timings_seconds"] = timings
    return entry, loaded


def _reviewing(bench: BenchmarkRoute, route_file: str, side: str, root: Path, config: Config) -> Reviewing | None:
    """What the verdict of one half of a route is judged on now: its tolerance and the hashes of the target and of the route file evaluated; None without a verdict."""
    verdict = verdict_of(bench.id, side)
    if verdict is None:
        return None
    return Reviewing(verdict, config.benchmark_review_tolerance, text_hash(root / bench.target), text_hash(root / route_file))


def _start_entry(plan: Plan, data: GameData, expected: ExpectedStart | None) -> dict | None:
    """What the plan started from and what it was compared with: the expected start, the chosen one, every option's totals, the refusals.

    None for a route that is planned from its own start item alone. Whether the chosen start is the expected one is recorded, never
    enforced here (a test pins it).
    """
    if expected is None:
        return None
    choice = plan.starts
    chosen = "plain" if choice is None else choice.chosen.key
    options = []
    refused = []
    step = None
    if choice is not None:
        options = [
            {
                "key": row.candidate.key,
                "label": row.candidate.label,
                "outcome": row.outcome,
                "start_price": None if row.candidate.price is None else _number(row.candidate.price),
                "given": row.candidate.given,
                "total": None if row.total is None else _number(row.total),
            }
            for row in choice.considered
        ]
        refused = [{"recipe": each.recipe, "reason": each.reason, "detail": each.detail} for each in choice.refused]
        step = first_step(choice.chosen, data, plan.target)
    return {
        "expected": expected.key,
        "why": expected.why,
        "chosen": chosen,
        "matches": chosen == expected.key,
        "start_price": None if plan.start_price.given else _number(plan.start_price.chaos),
        "given": plan.start_price.given,
        "options": options,
        "refused": refused,
        "first_step": None if step is None else first_step_document(step),
    }


def _missing_start_price(data: GameData, target: Target, prices: PriceFile, root: Path, config: Config, target_file: str) -> dict | None:
    """What a route misses when its start item has no price in `prices`, else None.

    The name is the price key computed from the target (`start_price_key`). The overrides file is the one `load_target_prices` reads
    beside the price file. The trade command is only named, never run: the benchmark does not call the trade API, so a run stays
    reproducible and offline.
    """
    if target.start is not StartKind.BOUGHT:  # a given start item (OR-6) has no price to miss
        return None
    name = start_price_key(data, target)
    if planned_price(prices, name) is not None:
        return None
    price_file = target.price_file if target.price_file is not None else default_price_file_path(config)
    return {
        "name": name,
        "override_line": f'"{name}" = <the price in Chaos Orbs>',
        "overrides_file": _without_root(str(price_file.parent / OVERRIDES_FILE_NAME), root),
        "trade_target": target_file,
    }


def _missing_message(missing: dict) -> str:
    """The error of a route whose start item has no price: the line to write, and the trade command for the target."""
    text = (
        f"no price for the start item {missing['name']!r}. Add this line under [prices] in "
        f"{missing['overrides_file']}: {missing['override_line']} (a bought start item must have a price above 0)"
    )
    text += f", or price it on the trade API with: python -m crafting_system.cli trade {missing['trade_target']}"
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


def _given_route(
    plan: Plan,
    result: RouteResult,
    data: GameData,
    shift: float,
    solver_mean: float | None = None,
    review_line: float | None = None,
    reviewing: Reviewing | None = None,
) -> dict:
    """The guide's route at the planner's prices: its totals, its gaps and its first divergence from the planner.

    With a `review_line` (the config's `[benchmark] review_ratio`) it also carries every divergence with the chance of each and the
    ratio of the planner's mean `solver_mean` (start price included) to the guide's (ticket #554). A caller that wants the totals only
    (`.github/scripts/measure_sim.py`) leaves it out and no visit chance is solved. `reviewing` is what the verdict of the route (if a person gave
    one) is judged on (`_benchmark_verdicts`, ticket #634); the first divergence then also carries the numbers of one use of each action (ticket #617).
    """
    risk = result.risk
    found = _totals(risk.success_probability, risk.mean, risk.p50, risk.p90, shift)
    divergence = result.divergence
    found["gaps"] = len(result.gaps)
    found["first_divergence"] = None
    if divergence is not None:
        first = first_divergence_of(plan, data, divergence, name_states(number_states(plan), [divergence.state]))
        found["first_divergence"] = first if review_line is not None else {key: value for key, value in first.items() if key != "per_use"}
    found["seconds"] = result.seconds
    if review_line is not None:
        found["divergences"] = divergences_of(plan, result, data)
        ratio = mean_ratio(solver_mean, found["mean"])
        first_action = None if divergence is None else divergence.solver_action
        found["mean_ratio"] = review_of(ratio, review_line, None if reviewing is None else reviewing.judge(ratio, first_action))
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
        if entry["start"] is not None:
            lines.extend(_start_summary(entry["start"]))
        if entry["given_route"] is not None:
            given = entry["given_route"]
            lines.append("  given route  " + _summary_line(given) + f", {given['gaps']} gap(s)")
            lines.extend(_review_summary("guide", given))
        if entry["completed_route"] is not None:
            completed = entry["completed_route"]
            lines.append("  given route, completed (see cli/_route.py)  " + _summary_line(completed) + f", {completed['gaps']} gap(s)")
            lines.extend(_review_summary("completed route", completed))
        for odds in entry["published_odds"]:
            if odds["published"] is None:  # no number to check: our chance at the target's tiers, beside the guide's family-level row above it
                lines.append(f"  our odds {odds['computed']} ({odds['on']}): {odds['requirement']}; the guide publishes no number for this reading")
                continue
            verdict = "matches" if odds["matches"] else "DIFFERS"
            lines.append(f"  published odds {odds['published']} ({odds['on']}): computed {odds['computed']}, {verdict}")
        if entry.get("interval") is not None:
            lines.extend(_interval_summary(entry["interval"]))
        if entry["solver_not_dearer"] is not None:
            lines.append("  solver not dearer than the guide: " + ("yes" if entry["solver_not_dearer"] else "NO"))
        if entry["solver_not_dearer_than_completed"] is not None:
            lines.append("  solver not dearer than the completed route: " + ("yes" if entry["solver_not_dearer_than_completed"] else "NO"))
        if entry["error"] is not None:
            lines.append(f"  error: {entry['error']}")
        if entry["missing_price"] is not None:
            lines.append(f"  add to {entry['missing_price']['overrides_file']} under [prices]:")
            lines.append(f"    {entry['missing_price']['override_line']}")
    return "\n".join(lines)


def _interval_summary(interval: dict) -> list[str]:
    """The interval of an approximate answer (#225): the plan's cost over the grid of the rule axis and the route without recombinators."""
    spread = interval["plan_interval"]
    lines = [
        f"  approximate  the plan reads {', '.join(axis['words'] for axis in interval['rule_axes'])}; made at {interval['plan_reading']}",
        f"  interval     {money(_finite_or_inf(spread['best']['value']))} to {money(_finite_or_inf(spread['worst']['value']))} Chaos over the grid "
        f"(cheapest at {spread['best_reading']}, dearest at {spread['worst_reading']})",
    ]
    without = interval["without_recombinators"]
    if without is not None:
        lines.append(f"  without recombinators  {money(_finite_or_inf(without['value']))} Chaos")
    return lines


def _finite_or_inf(value: float | None) -> float:
    return float("inf") if value is None else value


def _review_summary(label: str, totals: dict) -> list[str]:
    """The ratio, the "needs a human" row and the divergences of a route's totals (none for totals made without them)."""
    if "mean_ratio" not in totals:
        return []
    return [*review_lines(label, totals["mean_ratio"], totals["divergences"], totals["first_divergence"]), *divergence_lines(totals["divergences"])]


def _start_summary(start: dict) -> list[str]:
    verdict = "as expected" if start["matches"] else "NOT the expected one"
    price = "given, not counted" if start["given"] else "no price" if start["start_price"] is None else f"{money(start['start_price'])} Chaos"
    lines = [f"  start        {start['chosen']} ({verdict}; expected {start['expected']}), start price {price}"]
    for option in start["options"]:
        total = "not planned" if option["total"] is None else f"{money(option['total'])} Chaos in all"
        lines.append(f"    {option['outcome']}: {option['label']}: {total}")
    for refusal in start["refused"]:
        lines.append(f"    refused: {refusal['recipe']}: {refusal['reason']}: {refusal['detail']}")
    lines.append(f"  why          {start['why']}")
    return lines


def _summary_line(totals: dict) -> str:
    mean = money(float("inf") if totals["mean"] is None else totals["mean"])
    success = percent(totals["success"] if totals["success"] is not None else 0.0)
    return f"success {success}, mean {mean} Chaos, {totals['seconds'] * 1000:.0f} ms"
