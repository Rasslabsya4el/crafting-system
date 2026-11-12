"""The Vaal Orb as an exact action: four equal outcomes, a weighted implicit pool and a brick that is a dead end (ticket #259, ADR-0037).

A Vaal Orb corrupts the item and applies one of four outcomes with chance 1/4 each (`corruption.vaal_equipment_four_outcomes`):

1. **A corrupted implicit.** One mod is drawn by weight from the corrupted pool of the item's base at its item level
   (`corrupted_implicit_pool`, `corruption.implicit_pool_by_item_class`) and replaces one implicit of the item, chosen uniformly among its
   implicits, base and Eldritch ones alike (`corruption.implicit_replaces_existing`, `eldritch.vaal_replaces_one_implicit`); an item with
   none gains it. The draw is the one of a Bloodstained resonator (`ImplicitDraw`, `actions/bloodstained.py`); a result shows the drawn
   implicit at its lowest values and `sample` rolls each stat uniformly over its integer range, independently (`affix_pool.values_uniform_integers`).
   The explicit mods are not touched.
2. **A socket.** Since 3.29.0 one white socket turns non-white (`corruption.vaal_socket_outcome_3_29`). No target can mind that (ADR-0036,
   "Sockets"), so the result is the item corrupted and nothing else; jewels have no sockets and so no such outcome.
3. **The brick.** The item becomes a rare of the same base with random affixes, sockets and links.
4. **Nothing**: the item is only corrupted.

**A jewel** (an ordinary or abyss jewel; the pool is that of its domain) has four outcomes too: the implicit, the brick (a rare jewel of the same
base), a corruption-exclusive unique jewel and nothing (`corruption.jewel_vaal_outcomes`). Only a Cobalt, a Crimson and a Viridian Jewel have such
a unique; on every other base that outcome has no effect and counts as nothing, so nothing has chance 1/2 there. A unique result is a dead end
(unique items are never a target, #81).

**The brick and the unique are one dead end** (ADR-0036, ADR-0037): a corrupted item that is final and that a target which asks for a corrupted
implicit can never accept, whatever the item held. They are listed as one result, the item corrupted, a rare, with its fractured mods and nothing
else (every other mod the reroll erases, the contract suite requires the fractured ones to stay) and its implicits, quality, enchantment, sockets
and strands as they were (the brick adds no corrupted implicit and touches none of these; `memory_strands`: "the corrupted item keeps its count",
ADR-0041). The compressed state has no field that tells a brick apart, so every brick lands in one state: the same state for any roll of the reroll.
That is the Orb the catalog lists, the one a target that asks for a corrupted implicit gets.

**For a target that only allows a corrupted item** (ticket #260, ADR-0037) the brick can be the goal, so that target gets
`VaalOrb(brick_fills=True)` (`Action.for_allowed_corruption`, asked by the offer filter): its brick is a draw. The item becomes a rare of the
same base, corrupted, with its implicits, influences, quality, enchantment, sockets and strands as they were, and is filled with ordinary
draws (`Outcomes.fill`: item level, family exclusion, weights, influence, the Attack and Caster blocks) to a full item: three prefixes and three
suffixes, two and two on a jewel (`corruption.vaal_brick_rare_six_mods`, `corruption.jewel_brick_fills_to_limit`, both `approximate`); a
pool that runs out ends the fill early. What it keeps is the rule axis `corruption.vaal_brick` (`BRICK_AXIS`):

* `wiki`, the plan's reading: the brick "respects metamods" (wiki), so the mods of a side locked by `Prefixes/Suffixes Cannot Be Changed` stay,
  as a Chaos Orb keeps them (`retained_item`, `metamods.kept_by_reroll`), and the fractured mods stay (this project's inference: the wiki says
  nothing of them). The open slots of a locked side are filled too, as a Chaos Orb fills them (`metamods.locks_protect_existing_mods`).
* `coe`, Craft of Exile's code (`metaprot = false`, `remfrac = true`): every explicit mod goes, the fractured ones included, and no lock holds.

The brick draws no tier cut from the strands (the Orb spends none, ADR-0041). The sockets are not rerolled in the model: a target that names
sockets and only allows corruption would need the brick's random sockets, which ADR-0036 leaves out (an `approximate` simplification there).

**Refusals.** `NotApplicableError` for a corrupted item and for a base whose item class has no corrupted pool (a flask, a map, a gem, currency);
`OutOfScopeError` for a Cluster or a Timeless Jewel (their pools are not checked, ADR-0004) and for an item level at which the pool is empty (no
admitted rule says what the Orb does then). A mirrored or a unique item is refused by the game too, but the item model holds neither: `Item` has
no such flag and no unique rarity. The Orb is accepted on normal, magic and rare items alike. Allflame crafting is not in v1 and refuses the Vaal Orb
anyway (`corruption.vaal_incompatible_with_allflame`).

**What it declares.** `Reads` names the implicits (the number of candidates for the replacement depends on how many the item holds) and the junk (a
result keeps it); `Adds.corrupting(keeps_mods=True)` says that it corrupts, that it puts an implicit on the item and that every outcome that can
still be the goal holds the explicit mods the item held, so a target that asks gets the Orb only from a state in which every other requirement passes
(`cli._prune`, ADR-0036). A Vaal Orb neither cuts tiers nor spends Memory Strands (`memory_strands.cut_follows_spend_table`, `memory_strands.not_spent_by`).
Its `chance_all` counts the corrupted implicit it adds as the Bloodstained resonator's does; `implicit_chances` counts every implicit the finished item holds,
the ones that stay included.
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity, Side, is_corrupted_implicit
from crafting_system.items.implicits import corrupted_pool_domain
from crafting_system.items.words import base_words
from crafting_system.rules import get_rule

from .bloodstained import ImplicitDraw
from .catalog import kind
from .contract import Action, Adds, Axis, Previewable, Reading, Reads
from .corrupted_pool import corrupted_implicit_pool
from .draw import Outcome, refuse_unmodelled
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .outcomes import Outcomes, retained_item
from .rolls import roll_values
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY, StrandUse

__all__ = [
    "BRICK_AXIS",
    "BrickOutcomes",
    "VaalOrb",
    "VaalOutcomes",
]

FOUR_OUTCOMES = get_rule("corruption.vaal_equipment_four_outcomes")
UNIFORM_IN_COE_CODE = get_rule("corruption.vaal_uniform_in_coe_code")
SOCKET_OUTCOME = get_rule("corruption.vaal_socket_outcome_3_29")
BRICK = get_rule("corruption.vaal_brick_rare_six_mods")
REPLACES_EXISTING = get_rule("corruption.implicit_replaces_existing")
REPLACES_ONE_ELDRITCH = get_rule("eldritch.vaal_replaces_one_implicit")
POOL_BY_ITEM_CLASS = get_rule("corruption.implicit_pool_by_item_class")
JEWEL_OUTCOMES = get_rule("corruption.jewel_vaal_outcomes")
JEWEL_POOL = get_rule("corruption.jewel_implicit_pool")
JEWEL_BRICK = get_rule("corruption.jewel_brick_fills_to_limit")
VALUES_UNIFORM = get_rule("affix_pool.values_uniform_integers")
CORRUPTED_IS_FINAL = get_rule("corruption.corrupted_modifiable_exceptions")
COST = get_rule("vaal_orb.cost")

# the three jewel bases that have a corruption-exclusive unique; any other base gives no effect for that outcome (`corruption.jewel_vaal_outcomes`)
UNIQUE_JEWEL_BASES = frozenset({"Cobalt Jewel", "Crimson Jewel", "Viridian Jewel"})
QUARTER = Fraction(1, 4)
# what the brick keeps (ticket #260): the wiki's reading (fractured mods and locked sides stay) is the plan's, Craft of Exile's removes them all
BRICK_AXIS = Axis("corruption.vaal_brick", ("wiki", "coe"), "wiki", planned=True)  # the plan answers at the wiki, the claim marked approximate (OR-11)
EQUIPMENT_DOMAIN = "item"  # the domain of the corrupted mods of equipment, jewellery and quivers; a jewel draws from `misc` and an abyss jewel from `abyss_jewel`


@dataclass(frozen=True, eq=False)
class VaalOutcomes(Finite):
    """The result of one Vaal Orb: `Finite` over the corrupted items it can leave, with a sampler that rolls the values of the drawn implicit.

    `Finite` shows the drawn implicit at its lowest values (a result is exact); `sample` rolls each stat of it uniformly over its integer
    range, independently, as the game does.
    """

    def sample(self, rng: random.Random) -> Item:
        return _rolled_implicit(self.data, super().sample(rng), rng)

    def implicit_chances(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these implicits, the drawn one and the ones that stay alike.

        `chance_all` counts the corrupted implicit only, as the contract suite expects of an action whose items hold Eldritch implicits;
        this counts every implicit of the finished item. Raises `ValueError` for an id that is not in the game data.
        """
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        return sum(
            (chance for chance, item in self.results if wanted <= {entry.mod_id for entry in item.implicits}),
            Fraction(0),
        )


def _rolled_implicit(data: GameData, finished: Item, rng: random.Random) -> Item:
    """`finished` with the values of its corrupted implicit, if it holds one, rolled uniformly over each stat's integer range."""
    drawn = [entry for entry in finished.implicits if is_corrupted_implicit(data.mods[entry.mod_id])]
    if not drawn:
        return finished
    rolled = replace(drawn[0], values=roll_values(rng, data.mods[drawn[0].mod_id]))
    return finished.changed(data, implicits=tuple(rolled if entry is drawn[0] else entry for entry in finished.implicits))


@dataclass(frozen=True, eq=False)
class BrickOutcomes:
    """The result of one Vaal Orb whose brick is a full fill (ticket #260): the `fixed` items of the other outcomes and the `brick` draw.

    `fixed` are `(probability, item)` pairs of the implicit, nothing and unique-jewel outcomes, as `VaalOutcomes` lists them, and `brick` the
    `Outcomes` of the fill, with probability `brick_chance` (1/4); the two sum to 1. `given` is the item the Orb was used on. It has the four
    ways in of an `ActionOutcomes`: the kernel reads `components`, a fixed part per item and the fill as one pool draw.
    """

    data: GameData
    given: Item
    fixed: tuple[tuple[Fraction, Item], ...]
    brick: Outcomes
    brick_chance: Fraction

    def __post_init__(self) -> None:
        if any(chance <= 0 for chance, _ in self.fixed) or self.brick_chance <= 0 or sum(c for c, _ in self.fixed) + self.brick_chance != 1:
            raise ValueError("the outcomes of a Vaal Orb have positive probabilities that sum to 1")

    @cached_property
    def _fixed(self) -> "VaalOutcomes":
        """The fixed outcomes as a `Finite` of their own, scaled up to sum to 1 (its ways in are scaled back down)."""
        whole = 1 - self.brick_chance
        return VaalOutcomes(self.data, self.given, tuple((chance / whole, item) for chance, item in self.fixed))

    @property
    def components(self) -> tuple[tuple[Fraction, object], ...]:
        whole = 1 - self.brick_chance
        return (*((whole * share, part) for share, part in self._fixed.components), (self.brick_chance, self.brick))

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these mods, explicit mods and corrupted implicits (a brick holds no corrupted implicit)."""
        wanted = list(mod_ids)
        whole = 1 - self.brick_chance
        return whole * self._fixed.chance_all(wanted) + self.brick_chance * self.brick.chance_all(wanted)

    def implicit_chances(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these implicits; a brick holds the implicits the item held."""
        wanted = list(mod_ids)
        whole = 1 - self.brick_chance
        held = {entry.mod_id for entry in self.brick.retained.implicits}
        return whole * self._fixed.implicit_chances(wanted) + (self.brick_chance if set(wanted) <= held else Fraction(0))

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The new explicit mods seen through `label`: those of each fixed item against `given`, and those the brick draws."""
        whole = 1 - self.brick_chance
        shown: dict[Outcome, Fraction] = {}
        for outcome, chance in self._fixed.distribution(label).items():
            shown[outcome] = shown.get(outcome, Fraction(0)) + whole * chance
        for outcome, chance in self.brick.distribution(label).items():
            shown[outcome] = shown.get(outcome, Fraction(0)) + self.brick_chance * chance
        return shown

    def sample(self, rng: random.Random) -> Item:
        """One finished item: a brick with probability `brick_chance` (its drawn mods rolled), else a fixed outcome with its implicit rolled."""
        if rng.random() < float(self.brick_chance):
            return self.brick.sample(rng)
        return self._fixed.sample(rng)


def dead_end(data: GameData, item: Item) -> Item:
    """What a brick, or the unique jewel of a Vaal Orb, leaves for the plan: the item corrupted, a rare, with its fractured mods and nothing else of the explicit mods."""
    return item.changed(data, rarity=Rarity.RARE, corrupted=True, mods=item.fractured_mods)


@dataclass(frozen=True)
class VaalOrb(Action):
    """One Vaal Orb; with `brick_fills` the one a target that only allows corruption gets, whose brick is a full fill (ticket #260)."""

    brick_fills: bool = False

    def for_allowed_corruption(self, data: GameData | None = None) -> "VaalOrb":
        return VaalOrb(brick_fills=True)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        """What the brick keeps is open between the wiki and Craft of Exile; a dead brick reads nothing of it."""
        return (BRICK_AXIS,) if self.brick_fills else ()

    def label(self, data: GameData | None = None) -> str:
        return "Vaal Orb"

    def previewable(self, data: GameData | None = None) -> Previewable:
        return Previewable.BY_ITEM_TEXT  # ADR-0055: only the Lock's item text covers it; the claim is approximate

    def currency_item(self, data: GameData | None = None) -> str:
        return "Vaal Orb"

    def preview_claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset({"hinekora_lock.vaal_orb_previewed"})

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY)  # ADR-0041: neither cuts nor spends; the brick keeps the count

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                FOUR_OUTCOMES,
                UNIFORM_IN_COE_CODE,
                SOCKET_OUTCOME,
                BRICK,
                REPLACES_EXISTING,
                REPLACES_ONE_ELDRITCH,
                POOL_BY_ITEM_CLASS,
                JEWEL_OUTCOMES,
                JEWEL_POOL,
                JEWEL_BRICK,
                VALUES_UNIFORM,
                CORRUPTED_IS_FINAL,
                COST,
            )
        )

    def reads(self, data: GameData) -> Reads:
        # How many implicits the item holds decides which one goes; the junk is kept by every outcome but the brick, which erases it all.
        # Nothing here depends on a family or on a weight of the explicit pool, so a pooled block of junk families gives the same kernel.
        return Reads(junk=True, families=frozenset(), implicits=True, block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        if self.brick_fills:  # the brick draws explicit mods and can meet a requirement the item missed; Craft of Exile's brick takes the fractured mods off
            return Adds.corrupting(erases_fractured=True)
        # the implicit is drawn from the corrupted pool, no explicit mod is; every outcome that can still be a goal keeps the explicit mods
        return Adds.corrupting(keeps_mods=True, draws=False)

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> VaalOutcomes | BrickOutcomes:
        """The four outcomes on `item`, as the corrupted items they leave with their exact chances; with `brick_fills` the brick is a draw.

        `reading` is the value of `BRICK_AXIS` for a filling brick (the plan's, the wiki, when None or without it); a dead brick reads none.
        Raises `NotApplicableError` for a corrupted item and for a base whose class has no corrupted pool, `OutOfScopeError` for a Cluster
        or a Timeless Jewel, for an item level at which the pool is empty and, for a filling brick, for an item the draws do not model (an
        influenced item of a class with no influence key), `UnknownBaseError` for a base not in the game data.
        """
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Vaal Orb")
        pool = corrupted_implicit_pool(data, item.base_id, item.item_level)
        if not pool.mods:
            raise OutOfScopeError(
                f"the corrupted implicit pool of {base_words(data, item.base_id)} is empty at item level {item.item_level}, and the model has no rule for what a Vaal Orb does when it has no implicit to add",
                detail=(
                    f"the corrupted implicit pool of {item.base_id} is empty at item level {item.item_level}, and no admitted rule says "
                    "what a Vaal Orb does when it has no implicit to add"
                ),
            )
        base = data.base_items[item.base_id]
        jewel = corrupted_pool_domain(base) != EQUIPMENT_DOMAIN
        nothing = item.changed(data, corrupted=True)
        dead = dead_end(data, item)
        landed: dict[Item, Fraction] = {}

        def land(result: Item, chance: Fraction) -> None:
            landed[result] = landed.get(result, Fraction(0)) + chance

        for case in ImplicitDraw.for_item(data, item, replaces_all=False).cases:
            land(item.changed(data, corrupted=True, implicits=case.implicits), QUARTER * case.chance)
        brick = self._brick(data, item, reading) if self.brick_fills else None
        if brick is None:
            land(dead, QUARTER)  # the brick, a dead end
        if jewel:  # a unique jewel is a dead end on the three bases that have one, nothing on every other; a jewel has no socket outcome
            land(dead if base.name in UNIQUE_JEWEL_BASES else nothing, QUARTER)
            land(nothing, QUARTER)
        else:  # the socket outcome changes nothing a target can mind
            land(nothing, 2 * QUARTER)
        results = tuple((chance, result) for result, chance in landed.items())
        if brick is None:
            return VaalOutcomes(data, item, results)
        return BrickOutcomes(data, item, results, brick, QUARTER)

    def _brick(self, data: GameData, item: Item, reading: Reading | None) -> Outcomes:
        """The brick as a draw: the item a rare, corrupted, holding what the reading keeps, filled with ordinary draws to a full item."""
        refuse_unmodelled(data, item, jewels=True)
        keeps = (reading or Reading()).get(BRICK_AXIS.name, BRICK_AXIS.plan)
        if keeps not in BRICK_AXIS.readings:
            raise ValueError(f"the axis {BRICK_AXIS.name} has the readings {BRICK_AXIS.readings}, got {keeps!r}")
        if keeps == "wiki":  # the fractured mods and the locked sides stay, as a Chaos Orb keeps them
            retained = retained_item(data, item).changed(data, corrupted=True)
        else:  # Craft of Exile: every explicit mod goes
            retained = item.changed(data, rarity=Rarity.RARE, corrupted=True, mods=())
        full = len(retained.mods) + sum(retained.free_slots(data, side) for side in Side)
        return Outcomes.fill(data, retained, {full: Fraction(1)}, cut=self.cut_of(data, item))


@kind(
    "vaal",
    order=104,
    corrupting=True,
    # it works on an item whose class has a corrupted pool; the amulet of the contract suite's fixture has none (the family's own fixture
    # items, `tests/contract_fixtures_corruption.py`, carry it)
    applies_only_to="an item whose class has a corrupted implicit pool",
)
def _vaal_orb(data: GameData, item: Item):
    if item.corrupted:
        return
    try:
        corrupted_implicit_pool(data, item.base_id, item.item_level)
    except ValueError:
        return  # a class with no pool (NotApplicableError), a Cluster or Timeless Jewel (OutOfScopeError) or a base the data lacks: the Orb is not listed
    yield VaalOrb()
