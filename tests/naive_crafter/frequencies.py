"""One orb on one item, applied many times and counted: what the recorded Craft of Exile counts are compared with (ticket #555).

`tests/fixtures/coe_recorded/b1_core.json` (ticket #544) holds, for each case, the item the emulator started from (a base, its item level,
a rarity, mod ids, which of them are fractured), the action, and over `applied` uses the number of finished items that hold each mod and
that have each shape (`1p3s` = one prefix, three suffixes). `count_applications` does the same with this package's orbs, and
`two_sample` is the statistic that puts the two counts side by side.

The statistic. A cell is one event, "the finished item holds mod M" or "the finished item has shape S", with `k1` of `n1` for the
emulator and `k2` of `n2` for the naive crafter. Under the hypothesis that both have the same chance, the pooled chance is
`p = (k1 + k2) / (n1 + n2)` and `z = (k1/n1 - k2/n2) / sqrt(p (1 - p) (1/n1 + 1/n2))` is close to normal. The approximation needs enough
expected counts in both samples, so a cell is tested only when `n1 p` and `n1 (1 - p)` are at least `MIN_EXPECTED` (the smaller sample is
the emulator's); the rest are not tested one by one, and the support check covers them: a mod the emulator gave at least
`SUPPORT_MIN` times in a sample is a mod the naive crafter gives. The cells of the whole module are one family and the limit is
Bonferroni-corrected: a cell fails when `|z|` is above the normal quantile for `ALPHA / m` two-sided, `m` the number of tested cells.
There is no percentage threshold.
"""

import statistics
from collections import Counter
from dataclasses import dataclass
from math import sqrt
from random import Random

from .craft import Crafter, Held, Item, Refused
from .fossils import FossilSet
from .world import FOSSIL_SEPARATOR, FOSSILS, ORBS

ALPHA = 0.01  # the chance of one false alarm anywhere in the module when the two agree
MIN_EXPECTED = 30
SUPPORT_MIN = 5


@dataclass
class Frequencies:
    applied: int
    mods: Counter
    shapes: Counter
    refused: int = 0


def item_of(crafter: Crafter, record: dict, seed: int = 0) -> Item:
    """The recorded start item: its mods with values rolled by the crafter's generator (the values do not matter to an orb)."""
    rng = Random(seed)
    fractured = set(record.get("fractured") or ())
    mods = tuple(Held(mod_id, crafter.book.roll(mod_id, rng), fractured=mod_id in fractured) for mod_id in record.get("mods") or ())
    return Item(record["rarity"], mods)


def use_of(crafter: Crafter, label: str, essences: dict, fossil_records: dict | None = None):
    """A function `(item, rng) -> item` that applies the action named `label` (`fossil_records`: the export's fossils by name, for a `Fossils A + B` label)."""
    if label.startswith(FOSSILS):
        fossils = FossilSet(tuple(label[len(FOSSILS):].split(FOSSIL_SEPARATOR)), fossil_records or {})
        return lambda item, rng: crafter.fossil(item, rng, fossils)
    if label in ORBS:
        return {
            "Orb of Transmutation": crafter.transmute,
            "Orb of Alteration": crafter.alter,
            "Orb of Augmentation": crafter.augment,
            "Regal Orb": crafter.regal,
            "Chaos Orb": crafter.chaos,
            "Exalted Orb": crafter.exalt,
            "Orb of Annulment": crafter.annul,
            "Fracturing Orb": crafter.fracture,
        }[label]
    found = [record for record in essences.values() if record.get("name") == label]
    if len(found) != 1:
        raise KeyError(f"{len(found)} essence records are named {label!r}")
    return lambda item, rng: crafter.essence(item, rng, found[0])


def count_applications(
    crafter: Crafter, item: Item, label: str, essences: dict, applied: int, seed: int, fossil_records: dict | None = None
) -> Frequencies:
    """Apply the action `applied` times to `item` and count the finished items that hold each mod and have each shape."""
    use = use_of(crafter, label, essences, fossil_records)
    rng = Random(seed)
    mods: Counter = Counter()
    shapes: Counter = Counter()
    refused = 0
    for _ in range(applied):
        try:
            finished = use(item, rng)
        except Refused:
            refused += 1
            continue
        mods.update(held.mod_id for held in finished.mods)
        counts = crafter.side_counts(finished.mods)
        shapes[f"{counts['prefix']}p{counts['suffix']}s"] += 1
    return Frequencies(applied - refused, mods, shapes, refused)


@dataclass(frozen=True)
class Cell:
    case: str
    kind: str  # "mod" or "shape"
    name: str
    n1: int
    k1: int
    n2: int
    k2: int

    @property
    def pooled(self) -> float:
        return (self.k1 + self.k2) / (self.n1 + self.n2)

    @property
    def testable(self) -> bool:
        p = self.pooled
        return self.n1 * p >= MIN_EXPECTED and self.n1 * (1 - p) >= MIN_EXPECTED

    @property
    def z(self) -> float:
        p = self.pooled
        spread = sqrt(p * (1 - p) * (1 / self.n1 + 1 / self.n2))
        return (self.k1 / self.n1 - self.k2 / self.n2) / spread if spread > 0 else 0.0

    def describe(self) -> str:
        return (
            f"{self.case} {self.kind} {self.name}: emulator {self.k1}/{self.n1} = {self.k1 / self.n1:.5f}, "
            f"naive crafter {self.k2}/{self.n2} = {self.k2 / self.n2:.5f}, z {self.z:+.2f}"
        )


def cells_of(case: str, recorded: dict, ours: Frequencies) -> list[Cell]:
    """Every mod and every shape either side gave, as cells (the emulator's counts first)."""
    n1, n2 = recorded["applied"], ours.applied
    cells = [Cell(case, "mod", mod_id, n1, recorded["mods"].get(mod_id, 0), n2, ours.mods.get(mod_id, 0)) for mod_id in sorted(set(recorded["mods"]) | set(ours.mods))]
    cells += [Cell(case, "shape", shape, n1, recorded["shapes"].get(shape, 0), n2, ours.shapes.get(shape, 0)) for shape in sorted(set(recorded["shapes"]) | set(ours.shapes))]
    return cells


def critical_z(tested: int, alpha: float = ALPHA) -> float:
    """The two-sided normal quantile for `alpha / tested` (Bonferroni over the tested cells of the module)."""
    return statistics.NormalDist().inv_cdf(1 - alpha / (2 * max(tested, 1)))


def failures(cells: list[Cell], tested: int) -> list[Cell]:
    limit = critical_z(tested)
    return [cell for cell in cells if cell.testable and abs(cell.z) > limit]


def unsupported(cells: list[Cell]) -> list[Cell]:
    """Mod cells where the emulator gave the mod at least `SUPPORT_MIN` times and the naive crafter never."""
    return [cell for cell in cells if cell.kind == "mod" and cell.k1 >= SUPPORT_MIN and cell.k2 == 0]
