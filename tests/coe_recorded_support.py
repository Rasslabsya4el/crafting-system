"""Support for the recorded Craft of Exile frequencies of the B1 core (ticket #544, audit TESTS-23).

`tests/fixtures/coe_recorded/b1_core.json` holds counts of finished items from the Craft of Exile emulator,
recorded by `tools/coe_emulator/record.py` on the real bases of the benchmark routes (provenance in the file:
sample sizes, seeds, date, the hashes of the Craft of Exile copy). It holds counts only, no Craft of Exile code.
Here is the other side: our exact distribution of the same action on the same item, and the statistics that put
the two side by side.

The test (stated in one place, `ALPHA` and `MIN_EXPECTED`):

* Each cell is one event with an exact chance `p` of ours (a Fraction turned to a float) and a count `k` out of the
  `n` applications the emulator recorded: "the finished item holds mod M", "the new mods are 2 prefixes and 1
  suffix", "the item holds a mod that the goal's tier line accepts".
* A goal line that asks a roll (`min_roll`) is a "roll" cell: "the finished item holds a mod of the line's with a rolled
  value that reaches the roll". The emulator side is the count of the rolled values it recorded for the line's stat text
  (`record["rolls"]`, a histogram per mod of ours); our side is the chance of each mod (`marginals`) times the chance that its
  roll, uniform over the integers of each stat's range, reaches the roll (`roll_law`, the planner's own law).
* A cell is tested by the exact two-sided binomial test, `p_value = min(1, 2 * min(P(X <= k), P(X >= k)))` with
  `X ~ Binomial(n, p)`. No normal approximation, so a small cell is as honest as a large one.
* The cells are many, so the test is Bonferroni-corrected: a cell is a failure when `p_value < ALPHA / m`, where
  `m` is the number of cells of the whole module and `ALPHA` is the chance of ONE false alarm anywhere in the module
  when our model is exactly right. There is no fixed percentage threshold (the old one was 5% of the chance).
* A cell is tested only when the emulator sample is large enough to say something: `n * p >= MIN_EXPECTED` and
  `n * (1 - p) >= MIN_EXPECTED`. The rest is not tested one by one; the support test covers them: every mod the
  emulator gave is a mod our model can give.
"""

import json
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from crafting_system.abstraction import Status, status_of
from crafting_system.abstraction._rolls import roll_law
from crafting_system.actions.catalog import catalog
from crafting_system.data import GameData, StatRange
from crafting_system.items import ExplicitMod, Item, Rarity

RECORDED = Path(__file__).resolve().parent / "fixtures" / "coe_recorded" / "b1_core.json"
ALPHA = 0.01  # the chance of one false alarm anywhere in the module when our model is right
MIN_EXPECTED = 5  # a cell is tested when both n*p and n*(1-p) reach this


def load_recorded() -> dict:
    return json.loads(RECORDED.read_text(encoding="utf-8"))


# --- the statistic -------------------------------------------------------------------------------


def _log_pmf(n: int, k: int, p: float) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p)


def _tail(n: int, k: int, p: float, *, below: bool) -> float:
    """P(X <= k) when `below`, else P(X >= k), summed outward from k with the pmf recurrence (terms fall away from the mean)."""
    term = math.exp(_log_pmf(n, k, p))
    total = term
    odds = p / (1 - p)
    index = k
    while True:
        if below:
            if index == 0:
                break
            term *= index / (n - index + 1) / odds
            index -= 1
        else:
            if index == n:
                break
            term *= (n - index) / (index + 1) * odds
            index += 1
        total += term
        if term < 1e-18 * total:
            break
    return min(total, 1.0)


def binomial_two_sided(n: int, k: int, p: float) -> float:
    """The exact two-sided binomial p-value of `k` hits in `n` trials of chance `p`: twice the tail on k's side, at most 1."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"{k} hits in {n} trials")
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return min(1.0, 2 * _tail(n, k, p, below=k <= n * p))


@dataclass(frozen=True)
class Cell:
    """One tested event: its chance in our model and the count the emulator gave."""

    case: str
    kind: str  # "mod", "shape", "tier", "joint" or "roll"
    name: str
    n: int
    seen: int
    ours: float

    @property
    def expected(self) -> float:
        return self.n * self.ours

    @property
    def testable(self) -> bool:
        return self.n * self.ours >= MIN_EXPECTED and self.n * (1 - self.ours) >= MIN_EXPECTED

    @property
    def p_value(self) -> float:
        return binomial_two_sided(self.n, self.seen, self.ours)

    def describe(self) -> str:
        return f"{self.case} {self.kind} {self.name}: ours {self.ours:.5f} (expect {self.expected:.1f}), emulator {self.seen}/{self.n}, p {self.p_value:.2e}"


def failures(cells: list[Cell], alpha: float = ALPHA) -> list[Cell]:
    """The testable cells with p below `alpha / m`, `m` the number of testable cells (Bonferroni)."""
    testable = [cell for cell in cells if cell.testable]
    bound = alpha / max(len(testable), 1)
    return [cell for cell in testable if cell.p_value < bound]


# --- our side ------------------------------------------------------------------------------------


def build_item(data: GameData, spec: dict) -> Item:
    mods = []
    for mod_id in spec.get("mods", []):
        mod = data.mods[mod_id]
        low = tuple(min(stat.min, stat.max) for stat in mod.stats)
        mods.append(ExplicitMod(mod_id, low, fractured=mod_id in spec.get("fractured", []), crafted=mod.domain == "crafted"))
    return Item.build(
        data, base_id=spec["base"], item_level=spec["item_level"], rarity=Rarity(spec["rarity"]), mods=tuple(mods)
    )


class OurCase:
    """Our exact distribution of one recorded action on its item.

    `marginals` is the chance that the finished item holds each mod that the action can add; `shapes` the chance of
    each (prefixes, suffixes) of the finished item. A family leaves the pool whole when one of its mods is drawn and
    the mod is then picked by weight inside the family, so the chance of a mod is the chance of its family times its
    weight over the family's; `test_the_marginals_by_family_are_the_exact_ones` checks that against the exact
    distribution of single mods.
    """

    def __init__(self, data: GameData, record: dict) -> None:
        self.data = data
        self.item = build_item(data, record["item"])
        actions = {action.label(data): action for action in catalog(data, self.item)}
        self.action = actions[record["action"]]
        self.outcomes = self.action.outcomes(data, self.item)
        self.parts = tuple(self.outcomes.components)
        self.kept = frozenset(set.intersection(*({m.mod_id for m in part.retained.mods} for _, part in self.parts)))
        self._marginals: dict[str, Fraction] | None = None

    def side(self, mod_id: str) -> str:
        return self.data.mods[mod_id].generation_type

    def marginals(self) -> dict[str, Fraction]:
        if self._marginals is None:
            found: dict[str, Fraction] = {}
            for chance, part in self.parts:
                kept = {m.mod_id for m in part.retained.mods}
                # Two families of one side and one total weight are interchangeable in the draw, so each is drawn with
                # the same chance: the expected number drawn of its class over the class's size. One exact
                # distribution, labelled by class, gives all of them.
                class_of = {entry.mod.id: (str(family.side), family.weight) for family in part.pool for entry in family.mods}
                size_of: dict[tuple, int] = {}
                for family in part.pool:
                    size_of[(str(family.side), family.weight)] = size_of.get((str(family.side), family.weight), 0) + 1
                expected: dict[tuple, Fraction] = dict.fromkeys(size_of, Fraction(0))
                for outcome, c in part.distribution(lambda mod: class_of.get(mod.id)).items():
                    for label, count in outcome:
                        if label is not None:
                            expected[label] += c * count
                for family in part.pool:
                    drawn = expected[(str(family.side), family.weight)] / size_of[(str(family.side), family.weight)]
                    total = family.weight
                    for entry in family.mods:
                        if entry.mod.id not in kept:
                            found[entry.mod.id] = found.get(entry.mod.id, Fraction(0)) + chance * drawn * entry.weight / total
            self._marginals = found
        return self._marginals

    def exact_marginal(self, mod_id: str) -> Fraction:
        """The chance of `mod_id` straight from the exact distribution of the new mods, with the mod as the only label."""
        total = Fraction(0)
        for chance, part in self.parts:
            shown = part.distribution(lambda mod: mod.id if mod.id == mod_id else None)
            total += chance * sum((c for outcome, c in shown.items() if any(label == mod_id for label, _ in outcome)), Fraction(0))
        return total

    def joint(self, names: tuple[str, ...]) -> Fraction:
        """The exact chance that the finished item holds a mod of every family in `names` (the kept mods count)."""
        wanted = set(names)
        total = Fraction(0)
        for chance, part in self.parts:
            kept = {family for entry in part.retained.mods for family in self.data.mods[entry.mod_id].families} & wanted
            shown = part.distribution(lambda mod: next((name for name in names if name in mod.families), None))
            for outcome, c in shown.items():
                if (kept | {label for label, _ in outcome if label is not None}) >= wanted:
                    total += chance * c
        return total

    def shapes(self) -> dict[str, Fraction]:
        """The chance of each (prefixes, suffixes) of the finished item, as "2p3s"."""
        found: dict[str, Fraction] = {}
        for chance, part in self.parts:
            kept = [m.mod_id for m in part.retained.mods]
            base_p = sum(self.side(m) == "prefix" for m in kept)
            base_s = len(kept) - base_p
            for outcome, c in part.distribution(lambda mod: mod.generation_type).items():
                counts = dict(outcome)
                key = f"{base_p + counts.get('prefix', 0)}p{base_s + counts.get('suffix', 0)}s"
                found[key] = found.get(key, Fraction(0)) + chance * c
        return found


# --- the cells -----------------------------------------------------------------------------------


def lump(cells_by_name: dict[str, tuple[int, float]], case: str, n: int) -> list[Cell]:
    """Disjoint cells (shapes): those too small to test alone are pooled into one cell ("the rest")."""
    cells: list[Cell] = []
    rest_seen, rest_ours = 0, 0.0
    for name, (seen, ours) in sorted(cells_by_name.items()):
        cell = Cell(case, "shape", name, n, seen, ours)
        if cell.testable:
            cells.append(cell)
        else:
            rest_seen += seen
            rest_ours += ours
    if rest_ours > 0 or rest_seen:
        cells.append(Cell(case, "shape", "the rest", n, rest_seen, min(rest_ours, 1.0)))
    return cells


def mod_cells(case: str, record: dict, ours: OurCase) -> list[Cell]:
    n = record["applied"]
    return [
        Cell(case, "mod", mod_id, n, record["mods"].get(mod_id, 0), float(chance))
        for mod_id, chance in sorted(ours.marginals().items())
    ]


def joint_cells(case: str, record: dict, ours: OurCase) -> list[Cell]:
    """Cells for the pairs of families recorded together ("IncreasedLife+FireResistance"): both on the finished item."""
    return [
        Cell(case, "joint", name, record["applied"], seen, float(ours.joint(tuple(name.split("+")))))
        for name, seen in record.get("joints", {}).items()
    ]


def shape_cells(case: str, record: dict, ours: OurCase) -> list[Cell]:
    n = record["applied"]
    theirs = record["shapes"]
    mine = ours.shapes()
    return lump({key: (theirs.get(key, 0), float(mine.get(key, 0))) for key in set(theirs) | set(mine)}, case, n)


def shifted(mod, by: int):
    """The mod with every stat range moved by `by`: the wrong roll range of the control (a model whose ranges are off by one)."""
    return replace(mod, stats=tuple(StatRange(stat.id, stat.min + by, stat.max + by) for stat in mod.stats))


def roll_chance(data: GameData, ours: OurCase, line, by: int = 0) -> float:
    """Our chance that the finished item holds a mod of `line` whose roll reaches the line's `min_roll`.

    A mod of the line is held at most once (they are one family), so the chances add: for each mod our model can add, its
    marginal chance times the share of its rolls that the line passes. `by` moves every stat range (the control).
    """
    marginals = ours.marginals()
    total = 0.0
    for mod_id in sorted(line.mod_ids & marginals.keys()):
        law = roll_law([line], shifted(data.mods[mod_id], by), crafted=False)
        passing = sum((chance for statuses, chance in law if statuses[0] == Status.PASSING), Fraction(0))
        total += float(marginals[mod_id] * passing)
    return total


def roll_seen(record: dict, line) -> int:
    """The finished items of the emulator that hold a mod of `line` rolled to reach its `min_roll` (the goal's own judge, `status_of`)."""
    seen = 0
    for mod_id, histogram in record["rolls"][line.stat].items():
        for value, count in histogram.items():
            if mod_id in line.mod_ids and status_of(line, mod_id, (json.loads(value),), False) is Status.PASSING:
                seen += count
    return seen


def roll_cell(data: GameData, case: str, name: str, record: dict, ours: OurCase, line, by: int = 0) -> Cell:
    return Cell(case, "roll", name, record["applied"], roll_seen(record, line), roll_chance(data, ours, line, by))
