"""Measure the variants level of ADR-0023 with the product code (ticket #172): the numbers of its table, re-made on GitHub runners.

`uv run --no-sync python .github/scripts/measure_variants.py <case> [options]`, a case being one of:

    levels     the R14-like Hunter Thicket Bow at each spread: pools, blocks, certified interval, gap, seconds
    endtoend   what `decide` says about the route at the default rates, and the answer `climb` finds
    exact      the exact graph solved with `solve` (long; only with --yes-exact): states, edges, seconds, value
    refusals   what the product says about the R04-like quiver and about the metamods of R14 proper

Options: `--prices default|cheap` and `--goal A|B` pick the prices and the goal of ADR-0023's "Sensitivity"; `--spreads
3000,2000,...` the rungs of `levels`; `--budget` the seconds `decide` may spend; `--out DIR` also writes the JSON lines
into `DIR/<case>.jsonl` (the runner workflow passes `$OUT_DIR`).

One JSON line per fact goes to the console. Nothing is asserted: a number is printed as the product gives it, and a
refusal of the product (`ActionError`, `OutOfScopeError`, `PlanError`) is printed as a line with its text. Anything
else is a bug of the product or of this script and crashes with its traceback. The measurement is heavy: it runs on
a runner (`.github/workflows/run.yml`, docs/ci.md), never on a developer's PC. Needs the game data in `CRAFTING_CACHE_DIR`.
"""

import argparse
import json
import random
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from crafting_system.abstraction import Abstraction, Coarsening, CompressedState, Goal, Wanted
from crafting_system.actions import (
    Action,
    ActionError,
    AlterationOrb,
    AnnulmentOrb,
    ApplyEssence,
    AugmentationOrb,
    BenchCraft,
    ExaltedOrb,
    FracturingOrb,
    RegalOrb,
    RemoveCraftedMods,
    ScouringOrb,
    TransmutationOrb,
    bench_crafts,
)
from crafting_system.cli import PlanError
from crafting_system.cli._approx import Solved, climb, solve_level
from crafting_system.cli._decide import Candidate, Decision, Level, Rates, coarse_refusal, decide
from crafting_system.cli._offers import Offer, PricedOffer, offer_of
from crafting_system.cli._plan import offer_action
from crafting_system.data import GameData, load_game_data
from crafting_system.items import ExplicitMod, Influence, Item, Metamod, Rarity
from crafting_system.solver import solve

try:
    import resource  # POSIX only: the peak memory of the process
except ImportError:
    resource = None

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
BOW_LEVEL = 78
QUIVER_NAME, QUIVER_LEVEL = "Penetrating Arrow Quiver", 81
T1_ATTACK_SPEED = "LocalIncreasedAttackSpeed5"  # (17-19)% increased Attack Speed, tier 1 on the Hunter bow
SPREADS = (3000, 2000, 1500, 1000, 500)  # the rungs of ADR-0023's table
BUDGET = 60.0  # seconds, the CLI's default

ORBS = {
    "transmute": TransmutationOrb(),
    "alter": AlterationOrb(),
    "augment": AugmentationOrb(),
    "regal": RegalOrb(),
    "annul": AnnulmentOrb(),
    "exalt": ExaltedOrb(),
    "scour": ScouringOrb(),
}
PRICES = {  # Chaos Orbs per use, the placeholders of ADR-0023
    "default": {"transmute": 0.1, "alter": 0.2, "augment": 0.2, "regal": 1, "annul": 20, "exalt": 15, "scour": 1},
    "cheap": {"transmute": 0.1, "alter": 0.2, "augment": 0.2, "regal": 0.5, "annul": 2, "exalt": 2, "scour": 0.5},
}
GOALS = {  # the families the goal asks for; the last of each tuple may carry a worst tier
    "A": (("IncreaseSocketedGemLevel", None), ("ChaosDamageHybrid", None), ("IncreasedAttackSpeed", 1)),
    "B": (("PhysicalDamage", None), ("CriticalStrikeMultiplier", None), ("IncreasedAttackSpeed", 1)),
}
REFUSALS = (ActionError, PlanError)  # what the product raises on purpose (`OutOfScopeError` is an `ActionError`)


@dataclass(frozen=True)
class Case:
    """One query: a route and what each of its actions costs in Chaos Orbs.

    `offers` pairs every action with its cost; the first `levels` and `endtoend` use are those of the route as the
    planner would build them (`abstraction` enables the actions that read the junk, as `make_plan` does).
    """

    name: str
    data: GameData
    goal: Goal
    base_id: str
    item_level: int
    start_item: Item
    offers: tuple[tuple[Action, float], ...]

    @property
    def actions(self) -> tuple[Action, ...]:
        return tuple(action for action, _ in self.offers)

    def abstraction(self, factory: Callable[..., Abstraction] = Abstraction) -> Abstraction:
        enabled = [action for action in self.actions if action.reads(self.data).junk]
        return factory(self.data, self.goal, self.base_id, self.item_level, enabled)

    def priced(self) -> tuple[PricedOffer, ...]:
        """The offers with their costs; a priced offer carries no resources here, only the cost."""
        found = []
        for action, cost in self.offers:
            offer = offer_of(action, action.label(self.data), self.data, self.start_item)
            found.append(PricedOffer(offer, float(cost), ()))
        return tuple(found)


# --- the routes ---------------------------------------------------------------------------------------------------


def family_ids(data: GameData, family: str) -> frozenset[str]:
    """The ids of the mods of one family (and of that family alone)."""
    return frozenset(mod.id for mod in data.mods.values() if mod.families == (family,))


def wanted(data: GameData, family: str, min_tier: int | None = None) -> Wanted:
    return Wanted(family_ids(data, family), min_tier=min_tier)


def bow_case(data: GameData, prices: str, goal: str) -> Case:
    """The R14-like Hunter Thicket Bow of ADR-0023: Transmutation to Scouring, from a normal item."""
    leaves = tuple(wanted(data, family, tier) for family, tier in GOALS[goal])
    start = Item.build(data, base_id=BOW, item_level=BOW_LEVEL, rarity=Rarity.NORMAL, influences=frozenset({Influence.HUNTER}))
    offers = tuple((ORBS[name], PRICES[prices][name]) for name in ORBS)
    return Case(f"bow-{prices}-{goal}", data, Goal(leaves), BOW, BOW_LEVEL, start, offers)


def goal_families(data: GameData, goal: Goal) -> frozenset[str]:
    return frozenset(family for leaf in goal.leaves for mod_id in leaf.mod_ids for family in data.mods[mod_id].families)


def crafts_of_class(data: GameData, base_id: str, families: Iterable[str]) -> list[BenchCraft]:
    """The bench crafts offered for the class of `base_id` whose mod is of one of `families`."""
    item_class = data.base_items[base_id].item_class
    wanted_families = set(families)
    return [
        craft
        for craft in bench_crafts(data)
        if item_class in craft.option(data).item_classes and wanted_families & set(data.mods[craft.mod_id].families)
    ]


def with_crafts(case: Case, extra: Iterable[tuple[Action, float]], name: str) -> Case:
    return Case(name, case.data, case.goal, case.base_id, case.item_level, case.start_item, (*case.offers, *extra))


def metamod_case(data: GameData) -> Case:
    """R14 proper: the bow of `bow_case` with the bench crafts of the metamods (and the goal's own crafts) and Remove Crafted Mods."""
    case = bow_case(data, "default", "A")
    metamods = {metamod.value for metamod in Metamod}
    crafts = crafts_of_class(data, BOW, goal_families(data, case.goal) | metamods)
    extra = [(craft, 2.0) for craft in crafts] + [(RemoveCraftedMods(), 1.0)]
    return with_crafts(case, extra, "bow-metamods")


def quiver_case(data: GameData) -> Case:
    """R04-like: a Penetrating Arrow Quiver, item level 81; Essence of Insanity, Annulment, Fracturing Orb, Deafening Essence of Rage, Exalted.

    The goal is Maximum Life, Increased Damage with Bow Skills, tier 1 Strength, an additional arrow and the pierce of the
    essence. The costs are placeholders: only the refusal of the product is asked for. The bench crafts are the quiver's
    that touch the goal, the metamods and Remove Crafted Mods.
    """
    base = min(found.id for found in data.base_items.values() if found.name == QUIVER_NAME and "trade_market_legacy_item" not in found.tags)
    insanity = next(essence for essence in data.essences.values() if essence.name == "Essence of Insanity")
    pierce = insanity.mod_for("Quiver")
    bow_damage = frozenset(mod_id for mod_id in family_ids(data, "DamageWithWeaponTypeSkill") if "BowSkills" in mod_id)
    goal = Goal(
        (
            wanted(data, "IncreasedLife"),
            Wanted(bow_damage),
            wanted(data, "Strength", 1),
            wanted(data, "AdditionalArrows"),
            Wanted(frozenset({pierce})),
        )
    )
    start = Item.build(data, base_id=base, item_level=QUIVER_LEVEL, rarity=Rarity.NORMAL)
    metamods = {metamod.value for metamod in Metamod}
    crafts = crafts_of_class(data, base, goal_families(data, goal) | metamods)
    offers: list[tuple[Action, float]] = [
        (ApplyEssence("Essence of Insanity"), 5.0),
        (AnnulmentOrb(), 20.0),
        (FracturingOrb(), 20.0),
        (ApplyEssence("Deafening Essence of Rage"), 3.0),
        (ExaltedOrb(), 15.0),
        *((craft, 2.0) for craft in crafts),
        (RemoveCraftedMods(), 1.0),
    ]
    return Case("quiver-r04", data, goal, base, QUIVER_LEVEL, start, tuple(offers))


# --- what is written ----------------------------------------------------------------------------------------------


class Report:
    """The JSON lines of a run: each goes to the console and, with an output folder, to `<folder>/<name>.jsonl`."""

    def __init__(self, name: str, out: Path | None = None) -> None:
        self.rows: list[dict] = []
        self.path = None
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            self.path = out / f"{name}.jsonl"
            self.path.write_text("", encoding="utf-8")

    def emit(self, **row) -> dict:
        self.rows.append(row)
        line = json.dumps(row, default=str)
        print(line, flush=True)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return row

    def attempt[T](self, call: Callable[[], T], **fields) -> T | None:
        """`call()`, or None after a line that carries `fields` and the text of the refusal (the product's, not a bug)."""
        try:
            return call()
        except REFUSALS as refusal:
            self.emit(**fields, refused=type(refusal).__name__, message=str(refusal))
            return None


def peak_memory_mb() -> float | None:
    """The peak resident memory of the process in megabytes (Linux), None where the platform does not say."""
    if resource is None:
        return None
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


# --- levels -------------------------------------------------------------------------------------------------------


class CountingCoarsening:
    """A `Coarsening` that counts what the block model asks of it, for the size of the model; every other member is the wrapped one's.

    `counts[bound]` holds, per model: `offered` (block, action) pairs the model has an action for, `refused`, `edges` (the
    outcomes of every kernel returned), `variant_actions` (pairs with more than one variant kernel), `variant_kernels` and
    `variant_edges` (of those pairs only). The product is not altered; this is a view in front of it.
    """

    def __init__(self, coarsening: Coarsening) -> None:
        self._coarsening = coarsening
        self.counts = {bound: Counter() for bound in ("lower", "upper")}

    def __getattr__(self, name: str):
        return getattr(self._coarsening, name)

    def variants(self, block, action, bound):
        count = self.counts[bound]
        try:
            kernels = self._coarsening.variants(block, action, bound)
        except ActionError:
            count["refused"] += 1
            raise
        count["offered"] += 1
        count["edges"] += sum(len(kernel) for kernel in kernels)
        if len(kernels) > 1:
            count["variant_actions"] += 1
            count["variant_kernels"] += len(kernels)
            count["variant_edges"] += sum(len(kernel) for kernel in kernels)
        return kernels


def level_row(case: Case, spread: float, ab: Abstraction, start: CompressedState, offers: tuple[PricedOffer, ...]) -> dict:
    """Build the coarsening of one spread, solve both models with `solve_level`, and the facts of it."""
    began = time.perf_counter()
    coarsening = Coarsening.pooling_by_spread(ab, spread, start)
    pooled = time.perf_counter()
    counting = CountingCoarsening(coarsening)
    level = Level("spread", spread, f"junk pooled by weight, spread {spread}")
    solved = solve_level(Candidate(level, None, counting), start, offers)
    found = solved.approximation
    return dict(
        case="levels", route=case.name, spread=spread, pools=len(coarsening.groups),
        pooled_families=sum(len(group) for group in coarsening.groups), blocks=found.blocks,
        lower=found.lower, upper=found.upper, gap=found.gap, within_tolerance=found.within_tolerance,
        seconds=solved.seconds, pooling_seconds=pooled - began, wall_seconds=time.perf_counter() - began,
        models={bound: dict(count) for bound, count in counting.counts.items()},
    )  # fmt: skip


def run_levels(case: Case, spreads: Iterable[float], report: Report) -> list[dict]:
    """One line per spread: the certified interval of the start item at that spread (ADR-0023's table).

    `seconds` is `solve_level`'s own (the two block models built and solved); `wall_seconds` adds the pooling.
    A spread the product refuses gives a line with the refusal, and the next spread is tried.
    """
    ab = case.abstraction()
    start = ab.compress(case.start_item)
    offers = case.priced()
    rows = []
    for spread in spreads:
        row = report.attempt(lambda spread=spread: level_row(case, spread, ab, start, offers), case="levels", route=case.name, spread=spread)
        if row is not None:
            rows.append(report.emit(**row))
    return rows


# --- end to end ---------------------------------------------------------------------------------------------------


class TimedAbstraction(Abstraction):
    """An `Abstraction` that adds up the seconds its pilot count (`estimate`) takes, to tell the pilot from the rest of `decide`."""

    pilot_seconds = 0.0

    def estimate(self, starts, actions, **options):
        began = time.perf_counter()
        try:
            return super().estimate(starts, actions, **options)
        finally:
            self.pilot_seconds += time.perf_counter() - began


def decision_row(case: Case, decision: Decision, ab: TimedAbstraction, decide_seconds: float, budget: float) -> dict:
    found = decision.estimate
    return dict(
        case="decision", route=case.name, action=decision.action, message=decision.message, budget=budget,
        levels=len(decision.levels), level_names=[candidate.level.name for candidate in decision.levels],
        level_forecasts=[None if c.estimate is None else c.estimate.transitions for c in decision.levels],
        pilot_complete=None if found is None else found.complete, pilot_walked=None if found is None else found.walked,
        pilot_states=None if found is None else found.states, pilot_transitions=decision.transitions,
        predicted_seconds=decision.predicted, pilot_seconds=ab.pilot_seconds, decide_seconds=decide_seconds,
    )  # fmt: skip


def answer_row(case: Case, solved: Solved, wall_seconds: float) -> dict:
    found = solved.approximation
    return dict(
        case="answer", route=case.name, level=found.level, blocks=found.blocks, lower=found.lower, upper=found.upper,
        gap=found.gap, within_tolerance=found.within_tolerance, message=found.message,
        seconds=solved.seconds, wall_seconds=wall_seconds,
    )  # fmt: skip


def climb_or_refuse(decision: Decision, start: CompressedState, offers: tuple[PricedOffer, ...]) -> Solved:
    try:
        return climb(decision, start, offers)
    except ActionError:
        raise
    except ValueError as error:
        raise PlanError(str(error)) from error  # as `make_plan` turns a ladder with no policy into a refusal


def run_decision(case: Case, report: Report, budget: float, rates: Rates | None = None) -> Decision | None:
    """`decide` on the route (at the rates it measures, unless `rates` injects them), then `climb` when it says approximate; the lines of both."""
    ab = case.abstraction(TimedAbstraction)
    start = ab.compress(case.start_item)
    offers = case.priced()
    began = time.perf_counter()
    decision = report.attempt(lambda: decide(ab, start, offers, budget, rates), case="decision", route=case.name)
    if decision is None:
        return None
    report.emit(**decision_row(case, decision, ab, time.perf_counter() - began, budget))
    if decision.action == "approximate":
        began = time.perf_counter()
        solved = report.attempt(lambda: climb_or_refuse(decision, start, offers), case="answer", route=case.name)
        if solved is not None:
            report.emit(**answer_row(case, solved, time.perf_counter() - began))
    return decision


# --- exact --------------------------------------------------------------------------------------------------------


class CountingModel:
    """The exact graph of a case for `solve`, counting the states expanded, the edges and the seconds spent in the kernels."""

    def __init__(self, ab: Abstraction, offers: tuple[PricedOffer, ...]) -> None:
        self.ab, self.offers = ab, offers
        self.expanded = self.edges = 0
        self.kernel_seconds = 0.0

    def is_goal(self, state: CompressedState) -> bool:
        return self.ab.is_goal(state)

    def actions(self, state: CompressedState):
        began = time.perf_counter()
        found = []
        for priced in self.offers:
            try:
                found.append(offer_action(self.ab, priced, state))
            except ActionError:  # the game refuses it here, or no admitted rule covers it
                continue
        self.expanded += 1
        self.edges += sum(len(action.outcomes) for action in found)
        self.kernel_seconds += time.perf_counter() - began
        return found


def run_exact(case: Case, report: Report) -> dict:
    """Solve the exact graph with `solve`: states, edges, seconds and the value of the start item, to check the intervals of `levels`."""
    ab = case.abstraction()
    start = ab.compress(case.start_item)
    model = CountingModel(ab, case.priced())
    began = time.perf_counter()
    solution = solve(model, [start])
    seconds = time.perf_counter() - began
    return report.emit(
        case="exact", route=case.name, states=len(solution.values), expanded=model.expanded, edges=model.edges,
        seconds=seconds, kernel_seconds=model.kernel_seconds, solve_seconds=seconds - model.kernel_seconds,
        value=solution.values[start], error_bound=solution.error_bound, peak_memory_mb=peak_memory_mb(),
    )  # fmt: skip


# --- refusals -----------------------------------------------------------------------------------------------------


def run_refusals(data: GameData, report: Report, budget: float) -> None:
    """What the product says for the R04-like quiver and for the metamods of R14 proper. Nothing is asserted."""
    quiver = quiver_case(data)
    report.emit(case="query", route=quiver.name, base=quiver.base_id, item_level=quiver.item_level, actions=[a.label(data) for a in quiver.actions])
    ab = quiver.abstraction()
    report.emit(case="coarse_refusal", route=quiver.name, message=coarse_refusal(ab, quiver.actions))
    run_decision(quiver, report, budget)

    bow = metamod_case(data)
    report.emit(case="query", route=bow.name, base=bow.base_id, item_level=bow.item_level, actions=[a.label(data) for a in bow.actions])
    report.emit(case="coarse_refusal", route=bow.name, message=coarse_refusal(bow.abstraction(), bow.actions))
    run_decision(bow, report, budget)
    run_metamod_kernels(bow, report)


def metamod_item(case: Case, metamod: Metamod, report: Report) -> Item | None:
    """A rare Hunter bow with its tier 1 attack speed and the craft of `metamod` on it, made by the craft itself (None: no such craft, or refused)."""
    data = case.data
    mod = data.mods[T1_ATTACK_SPEED]
    held = ExplicitMod(mod.id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats))
    rare = Item.build(
        data, base_id=case.base_id, item_level=case.item_level, rarity=Rarity.RARE, influences=frozenset({Influence.HUNTER}), mods=(held,)
    )
    craft = next(
        (action for action in case.actions if isinstance(action, BenchCraft) and metamod.value in data.mods[action.mod_id].families), None
    )
    if craft is None:
        report.emit(case="metamod_item", route=case.name, metamod=metamod.name, message="the route has no bench craft of this metamod")
        return None
    made = report.attempt(
        lambda: craft.outcomes(data, rare).sample(random.Random(172)), case="metamod_item", route=case.name, metamod=metamod.name, craft=craft.mod_id
    )  # fmt: skip
    if made is not None:
        report.emit(case="metamod_item", route=case.name, metamod=metamod.name, craft=craft.mod_id, mods=[entry.mod_id for entry in made.mods])
    return made


def run_metamod_kernels(case: Case, report: Report) -> None:
    """The exact kernel of every action of the route on a bow that holds a metamod: its answer, or the text of its refusal."""
    ab = case.abstraction()
    for metamod in (Metamod.NO_ATTACK_MODS, Metamod.MULTIPLE_CRAFTED_MODS):
        item = metamod_item(case, metamod, report)
        if item is None:
            continue
        fields = dict(case="metamod_kernel", route=case.name, metamod=metamod.name)
        state = report.attempt(lambda: ab.compress(item), action="compress", **fields)
        if state is None:
            continue
        for action in case.actions:
            label = action.label(case.data)
            kernel = report.attempt(lambda action=action: ab.kernel(state, action), action=label, **fields)
            if kernel is not None:
                report.emit(action=label, outcomes=len(kernel), **fields)


# --- the command line ---------------------------------------------------------------------------------------------


def parse_spreads(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split(",") if part.strip())


def parser() -> argparse.ArgumentParser:
    found = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    found.add_argument("case", choices=("levels", "endtoend", "exact", "refusals"))
    found.add_argument("--prices", choices=sorted(PRICES), default="default")
    found.add_argument("--goal", choices=sorted(GOALS), default="A")
    found.add_argument("--spreads", type=parse_spreads, default=SPREADS, help="levels: comma-separated, e.g. 3000,2000,1500,1000,500")
    found.add_argument("--budget", type=float, default=BUDGET, help="endtoend, refusals: seconds the exact run may take")
    found.add_argument("--yes-exact", action="store_true", help="exact: really solve the exact graph (minutes to hours)")
    found.add_argument("--out", type=Path, default=None, help="also write the JSON lines into DIR/<case>.jsonl")
    return found


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.case == "exact" and not args.yes_exact:
        Report(args.case).emit(case="exact", skipped="the exact graph is large and slow: pass --yes-exact to solve it")
        return 0
    data = load_game_data()
    if args.case == "refusals":
        run_refusals(data, Report("refusals", args.out), args.budget)
        return 0
    case = bow_case(data, args.prices, args.goal)
    report = Report(f"{args.case}-{args.prices}-{args.goal}", args.out)
    if args.case == "levels":
        run_levels(case, args.spreads, report)
    elif args.case == "endtoend":
        run_decision(case, report, args.budget)
    else:
        run_exact(case, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
