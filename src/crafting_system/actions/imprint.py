"""Imprint and restore as exact actions on an item that holds its imprints (ADR-0034, ADR-0060, ticket #219).

An imprint stores the state of one item and restores it later; the Eternal Orb that made it has not dropped since 2.0.0, so the planner
offers the two beast recipes of 3.29 only (`imprint.beast_recipes`): the **Craicic Croaker** makes an imprint of a **magic** item, the
**Fenumal Plagued Arachnid** one of a **rare Talisman**; a rare item that is not a Talisman cannot be imprinted. The beast is priced from
the price file, once per imprint made. The item holds its imprints (`Item.imprints`): each is the whole item as it was, with no imprint of
its own, and they are kept in the order they were made.

* **`Imprint(beast, limit, replaces)`.** Adds the item as it stands to the imprints it holds, and changes nothing else. At most `limit`
  imprints are held (`imprint.several_per_item`; the setting `max_imprints` of the planner, default `DEFAULT_MAX_IMPRINTS` = 1, because the
  first imprint multiplies the real state space by 200 and the second gains 0.08% at best, ADR-0060 point 5); a full item takes a new one
  only by replacing one (`replaces=k`, the k-th in the order the item keeps them): holding an old imprint costs nothing in the game, so the
  cap bounds the state and not the game. In the compressed state an imprint of a state already held is refused, because a second imprint of
  a state held never helps (ADR-0060 point 4); on a concrete item it is allowed (two items of one state can differ).
* **`Restore(index)`.** Returns the item to its `index`-th imprint, in every part the imprint holds (`imprint.restores_state`: implicit
  and explicit mods, enchantment, quality, base defences, Memory Strands), and the imprint is used up (`imprint.consumed_on_restore`); the
  other imprints stay. In the compressed state it is refused when the item already is in the state of its imprint (it would burn the imprint
  for nothing). It consumes nothing, so
  the planner prices it at its free-action epsilon (ADR-0026), and it takes no `Need`: the imprint is the item itself in an earlier state,
  so what it cost is the beast that made it, paid when it was made (ADR-0060 point 3).

Refusals (`NotApplicableError`): a corrupted item and an item with a fractured mod (`imprint.refused_on_fractured`,
`imprint.refused_on_corrupted_mirrored`; an imprint made before a Fracturing Orb cannot undo it), a jewel (owner, ticket #201), a normal
item, and the wrong beast for the rarity; a Restore with no such imprint. A mirrored item is not modelled: an `Item` has no such flag.

What the other actions do to the imprints. Every action that returns the item it was given with some part changed (`Item.changed`) keeps
the imprints, so a Restore undoes an Awakener's Orb on the receiver (`awakener.imprint_restores_receiver_only`: the donor is consumed
with its own imprints and is never brought back) and a Chaos Orb or an Annulment can be undone the same way. An action that builds a new
item (a recombinator output, an Allflame copy, a split item: `imprint.not_for_derived_items`) gives it none. The compressed state forgets
the imprints of an item that is corrupted or holds a fractured mod, because none can be used on it (`abstraction`, ADR-0060).

Exactness of the declarations. A Restore also restores the implicits, the quality and the unveil offer, but it declares none of them: a
snapshot differs from the item in such a part only if some other action of the model changed it, and that action declares it, which makes
the state keep it. The model of a route in which nothing changes the quality keeps no quality, and none is needed. The kind is not a
planner kind until the end-to-end ticket (#223) wires R15 and R17 and measures the state growth; the kernel and the state are here.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, ImprintMove, Reads
from .draw import jewel_class
from .errors import NotApplicableError
from .finite import Finite

__all__ = ["DEFAULT_MAX_IMPRINTS", "Imprint", "Restore", "imprint_actions"]

BEAST_RECIPES = get_rule("imprint.beast_recipes")
RESTORES_STATE = get_rule("imprint.restores_state")
REFUSED_ON_FRACTURED = get_rule("imprint.refused_on_fractured")
REFUSED_ON_CORRUPTED = get_rule("imprint.refused_on_corrupted_mirrored")
NOT_FOR_DERIVED_ITEMS = get_rule("imprint.not_for_derived_items")
CONSUMED_ON_RESTORE = get_rule("imprint.consumed_on_restore")
SEVERAL_PER_ITEM = get_rule("imprint.several_per_item")
RESTORES_THE_RECEIVER_ONLY = get_rule("awakener.imprint_restores_receiver_only")

DEFAULT_MAX_IMPRINTS = 1
"""How many imprints an item holds at most unless the planner is told otherwise (ADR-0060 point 5)."""

CROAKER, ARACHNID = "magic", "rare_talisman"  # the keys of `imprint.beast_recipes`: the recipe for a magic item, the one for a rare Talisman
TALISMAN_TAG = "talisman"  # the tag of the Talisman bases (bases of the amulet class)


def _is_talisman(data: GameData, item: Item) -> bool:
    base = data.base_items.get(item.base_id)
    return base is not None and TALISMAN_TAG in base.tags


def _refuse_unrestorable(data: GameData, item: Item, what: str) -> None:
    """The refusals every imprint and restore share: an item an imprint can be neither made of nor used on."""
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and an imprint cannot be made of or used on a corrupted item: {what}")
    if item.fractured_mods:
        raise NotApplicableError(f"the item holds a fractured mod, and an imprint cannot be made of or used on a fractured item: {what}")
    if jewel_class(data, item) is not None:
        raise NotApplicableError(f"the item is a jewel, and an imprint is refused on a jewel: {what}")


def _of(item: Item) -> Item:
    """The item as an imprint keeps it: itself, with no imprint of its own."""
    return replace(item, imprints=())


@dataclass(frozen=True)
class Imprint(Action):
    """One imprint of the item in hand, made by a beast: `beast` is `"magic"` (Craicic Croaker) or `"rare_talisman"` (Fenumal Plagued Arachnid).

    `limit` is the most imprints an item holds; `replaces` is None to add an imprint to an item with room, or the index of the imprint a
    full item gives up for the new one.
    """

    beast: str
    limit: int = DEFAULT_MAX_IMPRINTS
    replaces: int | None = None

    def __post_init__(self) -> None:
        if self.beast not in BEAST_RECIPES.value:
            raise ValueError(f"an imprint is made by one of {sorted(BEAST_RECIPES.value)}, not {self.beast!r}")
        if self.limit < 1:
            raise ValueError(f"an item holds at least one imprint, not {self.limit}")
        if self.replaces is not None and not 0 <= self.replaces < self.limit:
            raise ValueError(f"the imprint to replace is one of {self.limit}, not number {self.replaces}")

    @property
    def beast_name(self) -> str:
        """The beast as the price file names it."""
        return BEAST_RECIPES.value[self.beast]

    def label(self, data: GameData | None = None) -> str:
        text = f"Imprint with the {self.beast_name}"
        return text if self.replaces is None else f"{text}, replacing imprint {self.replaces + 1}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.beast_name: 1}

    def reads(self, data: GameData) -> Reads:
        # The result keeps every mod and depends on none of their families; it does depend on the imprints held (the cap).
        return Reads(junk=True, families=frozenset(), imprints=True)

    def imprint_move(self) -> ImprintMove:
        return ImprintMove(restore=False, index=self.replaces)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, imprints=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset({BEAST_RECIPES.id, RESTORES_STATE.id, REFUSED_ON_FRACTURED.id, REFUSED_ON_CORRUPTED.id, SEVERAL_PER_ITEM.id})

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The item as it is, with a new imprint of it; `NotApplicableError` where the game or the cap refuses (see the module)."""
        _refuse_unrestorable(data, item, "imprint")
        if self.beast == CROAKER:
            if item.rarity is not Rarity.MAGIC:
                raise NotApplicableError(f"the Craicic Croaker makes an imprint of a magic item, and this item is {item.rarity.value}")
        elif item.rarity is not Rarity.RARE or not _is_talisman(data, item):
            raise NotApplicableError(
                "the Fenumal Plagued Arachnid makes an imprint of a rare Talisman, and this item is not one: "
                "a rare item that is not a Talisman cannot be imprinted"
            )
        if len(item.imprints) > self.limit:
            raise NotApplicableError(f"the item holds {len(item.imprints)} imprints, more than the {self.limit} this setting allows")
        snapshot = _of(item)
        held = item.imprints
        if self.replaces is None:
            if len(held) >= self.limit:
                raise NotApplicableError(f"the item holds {len(held)} imprints, the most it may: a new one replaces an old one")
        else:
            if len(held) < self.limit:
                raise NotApplicableError("the item has room for another imprint, so none is given up")
            held = tuple(entry for index, entry in enumerate(held) if index != self.replaces)
        return Finite(data, item, ((Fraction(1), item.changed(data, imprints=(*held, snapshot))),))


@dataclass(frozen=True)
class Restore(Action):
    """Restore the item to its `index`-th imprint (in the order the item keeps them), which is used up."""

    index: int = 0

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"the imprints are numbered from 0, not {self.index}")

    def label(self, data: GameData | None = None) -> str:
        return f"Restore imprint {self.index + 1}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}  # the imprint was paid for when it was made; the planner prices a free action at its epsilon (ADR-0026)

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), imprints=True)

    def imprint_move(self) -> ImprintMove:
        return ImprintMove(restore=True, index=self.index)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It returns the mods of the item to those of the imprint, none drawn or named in advance.
        return Adds(named=None, draws=False, imprints=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            {
                RESTORES_STATE.id,
                REFUSED_ON_FRACTURED.id,
                REFUSED_ON_CORRUPTED.id,
                NOT_FOR_DERIVED_ITEMS.id,
                CONSUMED_ON_RESTORE.id,
                RESTORES_THE_RECEIVER_ONLY.id,
            }
        )

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The imprint as it was, holding the other imprints; `NotApplicableError` where the game refuses or there is no such imprint."""
        _refuse_unrestorable(data, item, "restore")
        if self.index >= len(item.imprints):
            raise NotApplicableError(f"the item holds {len(item.imprints)} imprints and none is number {self.index + 1}")
        target = item.imprints[self.index]
        rest = tuple(entry for index, entry in enumerate(item.imprints) if index != self.index)
        return Finite(data, item, ((Fraction(1), target.changed(data, imprints=rest)),))


def imprint_actions(data: GameData, item: Item, max_imprints: int = DEFAULT_MAX_IMPRINTS) -> tuple[Action, ...]:
    """Every imprint and restore an item whose imprints are held at most `max_imprints` may need: the planner's way to set the cap.

    The Croaker for any item that is or may become magic; the Arachnid when the base is a Talisman. With the cap reached, a new
    imprint replaces one, so there is one Imprint for each held imprint; one Restore for each. The catalog lists this for the default cap.
    """
    if max_imprints < 1:
        raise ValueError(f"an item holds at least one imprint, not {max_imprints}")
    if jewel_class(data, item) is not None or item.corrupted:
        return ()
    beasts = [CROAKER] + ([ARACHNID] if _is_talisman(data, item) else [])
    made = [Imprint(beast, max_imprints, replaces) for beast in beasts for replaces in (None, *range(max_imprints))]
    return (*made, *(Restore(index) for index in range(max_imprints)))


@kind("imprint", order=97, planner=False, why_not="the end-to-end ticket #223 wires R15 and R17 and measures the state growth of imprints", reads_item_state_while_not_planner="any")
def _imprint(data: GameData, item: Item):
    yield from (action for action in imprint_actions(data, item) if isinstance(action, Imprint))


@kind("restore", order=98, planner=False, why_not="the end-to-end ticket #223 wires R15 and R17 and measures the state growth of imprints", reads_item_state_while_not_planner="any")
def _restore(data: GameData, item: Item):
    yield from (action for action in imprint_actions(data, item) if isinstance(action, Restore))
