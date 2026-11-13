"""Burns: the cheap currency that gives a Hinekora's Lock up, and the re-anoint that is only a burn (ticket #295, B8-3, ADR-0056).

After looking at the previews a player may take none of them and change the item with a currency that changes no mod, which ends the foresight, and lock
again (the wiki: the way to get fresh previews). That currency is the **burn**. An action declares it with `Action.burn` (a Chromatic Orb, a Whetstone or a
Scrap, a Blessed Orb, the re-anoint below); the kinds that hold such actions carry `burns=True` (`catalog.py`).

**Legality at a state.** `Action.burn_refusal(data, item, keeps)` says why an action is no burn of `item` at a state that keeps `keeps` (`BurnKeeps`: what the
compressed state holds that a burn could touch), and `burns_at` lists the burns that are legal:

* a quality currency only where the state keeps the quality and not at the maximum quality (`quality_currency.py`);
* a Blessed Orb only on an item with a ranged implicit, not with an Eldritch implicit, and not where a requirement reads the implicits (`blessed.py`);
* a Chromatic Orb on an item of a socketed class, an item that states no sockets counting as having one (`socket_colours.py`, `burn.chromatic_socket_assumption`);
* a re-anoint on a ring or an amulet, not where the target requires the enchantment (`ReAnoint`);
* **a jewel has no burn**: no cheap currency is known to end its foresight, and a jewel has no quality, sockets or anoint (`burns_at` answers nothing for one).

**A burn is a `Burn`, never a plain action.** `Burn(action)` wraps the action as an ordinary unpreviewed action whose result is `Action.burn_outcomes` and whose
claims include the claims behind the burn (`Action.burn_claims`, the socket assumption of the Chromatic Orb), so a plan that burns lists them among its
approximate inputs and a plan that does not never does. No kind lists a `Burn`: it is made by `burns_at`, so it is absent from the catalog and from every plain
offer, and the Peek of a Lock (B8-4) is the only place that takes it, as the fallback `F(s)`. The cheapest legal burn at the prices of the price file is
`prices.cheapest_burn`.

**The re-anoint** (`ReAnoint`, kind `re-anoint`) is the one burn that exists only as a burn: neither B6 nor B7 adds an anoint action (ADR-0056). It anoints a ring or an
amulet again with the cheapest oils (`burn.reanoint_cost`, approximate: three Clear Oil), which ends the foresight and leaves every mod as it is
(`burn.reanoint_is_the_least_destructive_burn`). The compressed state keeps no enchantment (ADR-0050), so it never changes the state; the exact result is the item.
It is refused where the target requires the enchantment it would replace (`BurnKeeps.enchantment`, ADR-0050), on a corrupted item, and on any class but rings and
amulets. It is no planner kind: as a plain action it would give a target nothing.

**Memory Strands** (ADR-0041): it neither cuts nor spends, as the Blessed Orb (`memory_strands.cut_follows_spend_table`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.rules import get_rule

from .catalog import kind, kinds
from .contract import Action, ActionOutcomes, Adds, BurnKeeps, Reading, Reads
from .errors import NotApplicableError
from .finite import Finite
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, StrandUse

__all__ = [
    "Burn",
    "ReAnoint",
    "burns_at",
]

REANOINT_LEAST_DESTRUCTIVE = get_rule("burn.reanoint_is_the_least_destructive_burn")
REANOINT_COST = get_rule("burn.reanoint_cost")
ENDS_THE_FORESIGHT = get_rule("hinekora_lock.neutral_currency_removes_foresight")
JEWEL_CLASSES = frozenset(get_rule("affix_count.rare_jewel_max_per_side").value["item_classes"])
REANOINT_CLASSES = frozenset({"Ring", "Amulet"})
ONE = Fraction(1)


@dataclass(frozen=True)
class ReAnoint(Action):
    """One re-anoint of a ring or an amulet with the cheapest oils: a burn and nothing else."""

    def label(self, data: GameData | None = None) -> str:
        return "Re-anoint"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(REANOINT_COST.value)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: it draws no mod and the wiki's strand table has no row for it

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(rule.id for rule in (REANOINT_LEAST_DESTRUCTIVE, REANOINT_COST, ENDS_THE_FORESIGHT))

    def reads(self, data: GameData) -> Reads:
        """Nothing of the item: it is refused on a corrupted one, which is a flag of the item and no part of the state, and changes nothing of the mods."""
        return Reads(junk=True, families=frozenset())

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        """No mod; it replaces the enchantment, which is no part of the compressed state (ADR-0050)."""
        return Adds(named=frozenset(), draws=False, enchantment=True)

    def burn(self, data: GameData | None = None) -> bool:
        return True

    def burn_refusal(self, data: GameData, item: Item, keeps: BurnKeeps) -> str | None:
        """Refused where the target requires the enchantment (the re-anoint replaces it, ADR-0050), and where the use itself is refused."""
        if keeps.enchantment:
            return "the target requires the enchantment of the item, and a re-anoint replaces it (ADR-0050)"
        return super().burn_refusal(data, item, keeps)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The item as it was: a re-anoint changes no mod, and the enchantment it replaces is no part of the state the model keeps.

        Raises `NotApplicableError` for a corrupted item and for an item that is not a ring or an amulet.
        """
        item_class = data.base_items[item.base_id].item_class
        if item_class not in REANOINT_CLASSES:
            raise NotApplicableError(f"a re-anoint is a burn of a ring or an amulet, and this item is a {item_class}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Hinekora's Lock, so it has nothing to burn")
        return Finite(data, item, ((ONE, item),))


@kind(
    "re-anoint",
    order=107,
    planner=False,
    why_not="a burn only (ticket #295, ADR-0056): as a plain action it changes nothing the state keeps and gives a target nothing; the Peek of a Lock takes it as a fallback",
    burns=True,
)
def _re_anoint(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in REANOINT_CLASSES and not item.corrupted:
        yield ReAnoint()


@dataclass(frozen=True)
class Burn(Action):
    """`action` used as a burn of a Hinekora's Lock: an ordinary unpreviewed action, never a plain offer.

    Its result is `action.burn_outcomes`, its price is the action's, and its claims are the action's together with the claims behind the burn
    (`Action.burn_claims`) and the claim that it ends the foresight. It is made by `burns_at` for a state where `action` is a legal burn.
    """

    action: Action

    def __post_init__(self) -> None:
        if not self.action.burn():
            raise ValueError(f"{self.action.label()} does not declare `burn`, so it is no burn of a Lock (ADR-0056)")

    @property
    def variant(self) -> str:
        return self.action.variant

    def label(self, data: GameData | None = None) -> str:
        return f"Burn with {self.action.label(data)}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return self.action.resources(data)

    def reads(self, data: GameData) -> Reads:
        return self.action.reads(data)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return self.action.adds(data, item)

    def rule_axes(self, data: GameData):
        return self.action.rule_axes(data)

    def strand_use(self, data: GameData | None = None) -> StrandUse | None:
        return self.action.strand_use(data)

    def strand_claims(self, data: GameData | None = None) -> frozenset[str]:
        return self.action.strand_claims(data)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return self.action.claims(data) | self.action.burn_claims(data) | {ENDS_THE_FORESIGHT.id}

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> ActionOutcomes:
        """The result of the wrapped action as a burn on `item` (`Action.burn_outcomes`); its refusals are the action's."""
        return self.action.burn_outcomes(data, item, reading)


def burns_at(data: GameData, item: Item, keeps: BurnKeeps = BurnKeeps()) -> tuple[Burn, ...]:
    """The burns that are legal on `item` at a state that keeps `keeps`, in catalog order; none for a jewel.

    Only the kinds that declare `burns` are asked, so no opt-in kind (the fossil sets) is searched. Each burn is a `Burn`: it is not an action
    of the catalog, so it is never offered as a plain action (ADR-0056). With `keeps.sockets` (the target names sockets) an action that changes
    the sockets (`Adds.sockets`) is no burn: the socket finish starts from the start item's sockets (ticket #231).
    """
    base = data.base_items.get(item.base_id)
    if base is None or base.item_class in JEWEL_CLASSES:
        return ()
    found: dict[Burn, None] = {}
    for entry in kinds():
        if not entry.burns:
            continue
        for action in entry.members(data, item):
            if keeps.sockets and action.adds(data, item).sockets:
                continue
            if action.burn(data) and action.burn_refusal(data, item, keeps) is None:
                found.setdefault(Burn(action))
    return tuple(found)
