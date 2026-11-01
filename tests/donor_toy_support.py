"""The #210 toy graft, set up for the lazy offer loop (ticket #212): the donors it needs can be made, and one is a trap.

`ToyGraft` (tests/inputs_support.py) consumes a donor, a rare amulet with the damage prefix and the mana leech suffix, that
begins as a magic amulet with the damage prefix. Nothing in the catalog turns that magic amulet into that rare one in one
step, so this module adds the forges that do, and a second graft whose donor is harder to make:

* `ToyForge` turns the magic amulet into the donor of `ToyGraft` with chance 1/3 and leaves it as it is otherwise (so an
  attempt is repeated: the donor costs three forges on average).
* `ToyDearGraft` is `ToyGraft` with the same kernel and a donor that also holds a life prefix, which `ToyDearForge` makes
  with chance 1/100. Its donor is made of mods the target does not name, so the seed does not offer it; whether the loop does
  depends on the price of its forge: a forge that costs 1 leaves the determinized distance at 1 (the lower bound cannot see the
  hundred tries), and the loop offers the graft and the solve then finds it dearer; a forge that costs 500 is proved unneeded.

`toy_problem` builds the planner's pieces for the target "damage prefix and mana leech suffix" on the rare amulet that holds a
resistance and a life mod, from `offers_for`, the way `make_plan` does, with the toy kinds named in the target's `actions`.
"""

import contextlib
import dataclasses
from fractions import Fraction

from abstraction_pool import DAMAGE_1, LIFE_1, MANA_1
from contract_support import CONTRACT_DATA, _item, _roll, fixture_items
from inputs_support import TOY_ORB, ToyGraft, donor_start, donor_want

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import Action, Adds, Finite, Kind, Need, NotApplicableError, Reads, registered
from crafting_system.cli._offers import offers_for, price_offers
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry
from cli_support import price_file

TOY_FORGE = "Toy Forge Orb"
TOY_DEAR_FORGE = "Toy Dear Forge Orb"
GOAL_PAIR = Goal((Wanted(frozenset({DAMAGE_1})), Wanted(frozenset({MANA_1}))))


def dear_want() -> Item:
    """The dearer donor: a rare amulet with the damage prefix, the mana leech suffix and a life prefix."""
    return _item(Rarity.RARE, _roll(DAMAGE_1), _roll(MANA_1), _roll(LIFE_1))


@dataclasses.dataclass(frozen=True)
class ToyForge(Action):
    """Makes `becomes` from the magic donor start with chance 1/`den`; otherwise the item is unchanged. Other items are refused."""

    dear: bool = False

    @property
    def den(self) -> int:
        return 100 if self.dear else 3

    def label(self, data: GameData | None = None) -> str:
        return "Toy Dear Forge" if self.dear else "Toy Forge"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_DEAR_FORGE if self.dear else TOY_FORGE: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(draws=False)

    def outcomes(self, data: GameData, item: Item, reading=None) -> Finite:
        if item != donor_start():
            raise NotApplicableError("the toy forge works on the donor's start item only")
        becomes = dear_want() if self.dear else donor_want()
        return Finite(data, item, ((Fraction(1, self.den), becomes), (1 - Fraction(1, self.den), item)))


@dataclasses.dataclass(frozen=True)
class ToyDearGraft(ToyGraft):
    """`ToyGraft` with the dearer donor; the kernel is the same, only what the donor costs differs."""

    with_axis: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Toy Dear Graft"

    def inputs(self, data: GameData, item: Item | None = None) -> tuple[Need, ...]:
        return (Need(donor_start(), dear_want()),)


def _members(*actions: Action):
    def members(data: GameData, item: Item):
        yield from actions  # the donor is made from an item other than the start item, so the kind lists it for every item

    return members


KINDS = (
    Kind("toy-graft", _members(ToyGraft(with_axis=False)), order=901),
    Kind("toy-dear-graft", _members(ToyDearGraft()), order=902),
    Kind("toy-forge", _members(ToyForge()), order=903),
    Kind("toy-dear-forge", _members(ToyForge(dear=True)), order=904),
)
KIND_NAMES = tuple(entry.name for entry in KINDS)


@contextlib.contextmanager
def toy_kinds():
    """The four toy kinds registered in the catalog for the length of a `with` block."""
    with contextlib.ExitStack() as stack:
        for entry in KINDS:
            stack.enter_context(registered(entry))
        yield


def toy_prices(*, dear_forge: float = 1.0, graft: float = 2.0, forge: float = 1.0):
    """A price file for the toy: the prices of the graft orb and the two forges, in Chaos."""
    base = price_file()
    prices = {**base.prices, TOY_ORB: PriceEntry(graft, "test"), TOY_FORGE: PriceEntry(forge, "test"), TOY_DEAR_FORGE: PriceEntry(dear_forge, "test")}
    return dataclasses.replace(base, prices=prices)


def toy_problem(names=KIND_NAMES, **prices):
    """`(abstraction, start, priced offers)` for the target of the pair on the rare amulet with a resistance and a life mod.

    The kinds of `names` must be registered (`toy_kinds()`); the offers are what `offers_for` lists for them.
    """
    start_item = fixture_items()["rare_junk"]
    offers = offers_for(CONTRACT_DATA, GOAL_PAIR, start_item.base_id, start_item, names).offers
    priced, dropped = price_offers(offers, toy_prices(**prices))
    assert not dropped, dropped
    abstraction = Abstraction(
        CONTRACT_DATA, GOAL_PAIR, start_item.base_id, start_item.item_level, [p.offer.action for p in priced], allow_inputs=True
    )
    return abstraction, abstraction.compress(start_item), priced


__all__ = ["GOAL_PAIR", "KINDS", "KIND_NAMES", "ToyDearGraft", "ToyForge", "dear_want", "toy_kinds", "toy_problem", "toy_prices"]
