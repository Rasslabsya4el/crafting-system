"""Corrupted implicits in a target (ADR-0036, ADR-0037, ADR-0038): resolving them and finding the targets that can never be met.

`corrupted: true` on an `implicits:` entry resolves its selector among the corrupted implicit pool of the target's base at its item
level (`actions.corrupted_implicit_pool`) and only there: the same text without the key resolves among ordinary implicits only. A
selector with no mod there is an `Unresolved` that names the cause (no such text for this item class, or a mod that needs a higher
item level) and the nearest mods the pool does hold.

`corruption_problem` is the check of the whole target once it is read: it names the first thing that makes the goal impossible,
the way #141 does for impossible implicits.

* A corrupted start item under a target that neither asks for a corrupted implicit nor sets `allow_corrupted` could never be a goal.
* More corrupted implicits than the corrupting kinds the target may use give (`actions.CORRUPTING_KINDS`: one for the Vaal Orb and the
  Bloodstained resonator, two for the Locus of Corruption). A target that buys its item is not checked (`buys`).
* Two corrupted implicits of one mod group, which the Locus never draws together (its second implicit comes from another group).
* More implicits wanted in all than the item holds after the corrupting action: a corrupting action replaces implicits instead of
  adding to them, so a base implicit asked together with a corrupted one on a base that has only that implicit cannot both stay.

A requirement counts as one wanted implicit only when no other requirement could be met by the same implicit (the entries are taken
smallest first and kept while they share no mod), so two entries a single implicit could meet are never counted as two.
"""

import difflib
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from crafting_system.actions import (
    CORRUPTING_KINDS,
    DEFAULT_CORRUPTING_KINDS,
    ActionError,
    CorruptedImplicitPool,
    corrupted_implicit_pool,
)
from crafting_system.data import BaseItem, GameData, Mod, conflicts
from crafting_system.items import EldritchSide, Item, eldritch_side, spawn_weight
from crafting_system.items.model import MAX_ITEM_LEVEL

from .model import ImplicitRequirement
from .resolve import Resolver, Unresolved, normalise_stat_text, one_line, quoted

NEAREST = 3
START_ITEM_KEY = "start_item.corrupted"
IMPLICITS_KEY = "implicits"


def mod_text(mod: Mod) -> str:
    """The text of `mod` on one line, ranges as `#`; empty for a mod with no text."""
    return one_line(normalise_stat_text(mod.text)) if mod.text else ""


def named(mod: Mod) -> str:
    """A mod for a message: its id and its text."""
    return f'`{mod.id}` ("{mod_text(mod)}")'


def _texts_of(mod: Mod) -> tuple[str, ...]:
    return (normalise_stat_text(mod.text),) if mod.text else ()


def _families_of(mod: Mod) -> tuple[str, ...]:
    return mod.families


class CorruptedResolver:
    """Resolves corrupted implicit selectors for one `Resolver` (one game data)."""

    def __init__(self, resolver: Resolver) -> None:
        self.resolver = resolver
        self.data = resolver.data

    def _pools(self, base_id: str, item_level: int) -> tuple[CorruptedImplicitPool, CorruptedImplicitPool, BaseItem]:
        """The pool at `item_level` and at every level; `Unresolved` for a base with no pool or a level below every mod."""
        base = self.data.base_items[base_id]
        try:
            here = corrupted_implicit_pool(self.data, base_id, item_level)
            anywhere = corrupted_implicit_pool(self.data, base_id, MAX_ITEM_LEVEL)
        except ActionError as problem:
            raise Unresolved(f"`corrupted: true` cannot be asked for here: {problem}") from None
        if not here.mods:
            lowest = min(entry.mod.required_level for entry in anywhere.mods)
            raise Unresolved(
                f"no corrupted implicit of a {base.item_class} ({base.name}) can occur at item level {item_level};"
                f" the lowest needs item level {lowest}"
            )
        return here, anywhere, base

    def for_stat(self, base_id: str, item_level: int, text: str) -> frozenset[str]:
        """Every mod of the corrupted pool whose normalised text equals the normalised `text`; `Unresolved` if there is none."""
        wanted = normalise_stat_text(text)
        if not wanted:
            raise Unresolved("the stat text is empty once markup such as [..] and blank lines are removed")
        here, anywhere, base = self._pools(base_id, item_level)
        label = f'the text "{one_line(wanted)}"'
        found = self._select(here, anywhere, wanted, _texts_of, label, base, item_level)
        if found is not None:
            return found
        ordinary = self.resolver.kind_of_text(wanted)
        raise Unresolved(
            f"no corrupted implicit of a {base.item_class} ({base.name}) has {label}; "
            + self._elsewhere(wanted, ordinary, _texts_of)
            + self._closest(here, wanted, _texts_of)
        )

    def for_family(self, base_id: str, item_level: int, family: str) -> frozenset[str]:
        """Every mod of the corrupted pool that belongs to `family`; `Unresolved` if there is none."""
        here, anywhere, base = self._pools(base_id, item_level)
        label = f"the family `{family}`"
        found = self._select(here, anywhere, family, _families_of, label, base, item_level)
        if found is not None:
            return found
        ordinary = self.resolver.kind_of_family(family)
        raise Unresolved(
            f"no corrupted implicit of a {base.item_class} ({base.name}) belongs to {label}; "
            + self._elsewhere(family, ordinary, _families_of)
            + self._closest(here, family, _families_of)
        )

    def _select(
        self,
        here: CorruptedImplicitPool,
        anywhere: CorruptedImplicitPool,
        wanted: str,
        keys: Callable[[Mod], tuple[str, ...]],
        label: str,
        base: BaseItem,
        item_level: int,
    ) -> frozenset[str] | None:
        """The pool mods at `item_level` that have the key `wanted`; None when none; `Unresolved` when only a higher level has one."""
        found = frozenset(entry.mod.id for entry in here.mods if wanted in keys(entry.mod))
        if found:
            return found
        later = [entry.mod for entry in anywhere.mods if wanted in keys(entry.mod)]
        if later:
            need = min(mod.required_level for mod in later)
            raise Unresolved(
                f"the corrupted implicit with {label} ({quoted(mod.id for mod in later)}) needs an item level of {need},"
                f" but the target is item level {item_level}; raise `item_level` or ask for one a {base.item_class}"
                f" can get at that level: {self._nearest(here, wanted, keys)}"
            )
        return None

    def _elsewhere(self, wanted: str, ordinary: str | None, keys: Callable[[Mod], tuple[str, ...]]) -> str:
        """Where else the key is found, when it is not a corrupted implicit of this class: a sentence ending in a space, or ''."""
        if ordinary == "implicit":
            return "it names an ordinary implicit, so write the entry without `corrupted: true`; "
        if ordinary == "explicit":
            return "it names a prefix or suffix, so write it under `requirements:`; "
        if any(mod.generation_type == "corrupted" and wanted in keys(mod) for mod in self.data.mods.values()):
            return "it is a corrupted implicit of other item classes only; "
        return ""

    def _closest(self, here: CorruptedImplicitPool, wanted: str, keys: Callable[[Mod], tuple[str, ...]]) -> str:
        return f"the nearest corrupted implicits it can get at this item level: {self._nearest(here, wanted, keys)}"

    @staticmethod
    def _nearest(here: CorruptedImplicitPool, wanted: str, keys: Callable[[Mod], tuple[str, ...]]) -> str:
        first: dict[str, Mod] = {}
        for entry in here.mods:
            for key in keys(entry.mod):
                first.setdefault(key.lower(), entry.mod)
        near = difflib.get_close_matches(wanted.lower(), first, n=NEAREST, cutoff=0.0)
        return ", ".join(named(first[key]) for key in near) or "none"

    def explain_mod(self, base_id: str, item_level: int, mod_id: str, selector: str, written: str) -> str:
        """Why the `mod` key `mod_id` is not one of the corrupted mods the `selector` (`family` or `stat`) `written` selects."""
        here, anywhere, base = self._pools(base_id, item_level)
        at_level = {entry.mod.id: entry.mod for entry in here.mods}
        if mod_id in at_level:
            return f"`{mod_id}` is a corrupted implicit of a {base.item_class}, but not of the {selector} `{written}`"
        later = {entry.mod.id: entry.mod for entry in anywhere.mods}
        if mod_id in later:
            return (
                f"`{mod_id}` needs an item level of {later[mod_id].required_level}, but the target is item level {item_level};"
                f" the nearest corrupted implicit a {base.item_class} can get at that level:"
                f" {self._nearest(here, mod_id, lambda mod: (mod.id,))}"
            )
        mod = self.data.mods.get(mod_id)
        what = "is not a mod id in the game data" if mod is None else "is not a corrupted implicit of this item class"
        return (
            f"`{mod_id}` {what}; the nearest corrupted implicits a {base.item_class} can get at this item level:"
            f" {self._nearest(here, mod_id, lambda mod: (mod.id,))}"
        )


# -- the target as a whole ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorruptionProblem:
    """The first reason a target's corruption keys can never be met: where it is blamed and what to tell the owner.

    `key` is `implicits` (then `index` is the position of the blamed entry in the target's `implicits`) or `start_item.corrupted`.
    """

    key: str
    index: int | None
    message: str


def corruption_problem(
    data: GameData,
    base_id: str,
    item_level: int,
    implicits: tuple[ImplicitRequirement, ...],
    allow_corrupted: bool,
    start_item: Item,
    buys: bool,
    actions: tuple[str, ...] | None,
) -> CorruptionProblem | None:
    """The first impossibility among the corrupted implicits, the corrupted start item and `actions:`, or None.

    `buys` is true when the target buys its item (it names a price for the start item, or the start item is itself corrupted):
    a bought item brings its corrupted implicits with it, so the counts of what the planner can draw are not checked and every
    corrupting kind is taken as available.
    """
    asked = [(index, wish) for index, wish in enumerate(implicits) if wish.corrupted]
    if start_item.corrupted and not asked and not allow_corrupted:
        return CorruptionProblem(
            START_ITEM_KEY,
            None,
            "the start item is corrupted, and nothing changes a corrupted item, so it could never become the goal; this target"
            " neither asks for a corrupted implicit (`corrupted: true` under `implicits:`) nor sets `allow_corrupted: true`,"
            " and a corrupted item is then never a goal. Leave `corrupted` out of the start item or allow a corrupted goal",
        )
    if not asked:
        return None
    base = data.base_items[base_id]
    wanted = _distinct(asked)
    kinds = dict(CORRUPTING_KINDS) if buys else _usable_kinds(actions)
    best = max(kinds.values(), default=0)
    if not buys and len(wanted) > best:
        return _too_many(implicits, wanted, kinds, best, actions)
    if not buys and len(wanted) == 2:
        problem = _same_group(data, base_id, item_level, implicits, wanted)
        if problem is not None:
            return problem
    ordinary = _distinct([(index, wish) for index, wish in enumerate(implicits) if not wish.corrupted])
    if ordinary:
        return _no_room(data, base, implicits, ordinary, wanted, kinds)
    return None


def _distinct(entries: list[tuple[int, ImplicitRequirement]]) -> list[tuple[int, ImplicitRequirement]]:
    """Entries no one implicit could meet two of, in file order: the smallest are kept first while they share no mod."""
    taken: set[str] = set()
    kept = []
    for index, wish in sorted(entries, key=lambda entry: (len(entry[1].mod_ids), entry[0])):
        if taken.isdisjoint(wish.mod_ids):
            kept.append((index, wish))
            taken |= wish.mod_ids
    return sorted(kept)


def _usable_kinds(actions: tuple[str, ...] | None) -> dict[str, int]:
    """The corrupting kinds the target may use and how many corrupted implicits one use gives."""
    if actions is None:
        return dict(DEFAULT_CORRUPTING_KINDS)
    return {name: CORRUPTING_KINDS[name] for name in actions if name in CORRUPTING_KINDS}


def _asked_text(wish: ImplicitRequirement) -> str:
    return f"`{wish.family}`" if wish.stat is None else f'"{one_line(normalise_stat_text(wish.stat))}"'


def _too_many(
    implicits: tuple[ImplicitRequirement, ...],
    wanted: list[tuple[int, ImplicitRequirement]],
    kinds: Mapping[str, int],
    best: int,
    actions: tuple[str, ...] | None,
) -> CorruptionProblem:
    index, wish = wanted[best]  # the first entry beyond what one corrupting action can give
    if actions is None:
        gives = "the Vaal Orb gives one corrupted implicit and the Locus of Corruption two, and no action gives more"
        fix = "ask for at most two, or buy the item and name its corrupted implicits in the buy spec"
    elif not kinds:
        gives = (
            f"`actions:` names no corrupting kind ({quoted(CORRUPTING_KINDS)}), so no action gives the item a corrupted implicit"
        )
        fix = "name a corrupting kind in `actions:`, or buy the item and name its corrupted implicits in the buy spec"
    else:
        gives = f"the corrupting kinds in `actions:` ({quoted(kinds)}) give at most {best} at a time"
        fix = (
            "add `locus` to `actions:`, " if best < 2 and len(wanted) == 2 and "locus" not in kinds else "ask for fewer, "
        ) + "or buy the item and name its corrupted implicits in the buy spec"
    return CorruptionProblem(
        IMPLICITS_KEY,
        index,
        f"the target asks for {len(wanted)} corrupted implicit{'' if len(wanted) == 1 else 's'}, but {gives};"
        f" {_asked_text(wish)} is the one too many ({fix})",
    )


def _same_group(
    data: GameData,
    base_id: str,
    item_level: int,
    implicits: tuple[ImplicitRequirement, ...],
    wanted: list[tuple[int, ImplicitRequirement]],
) -> CorruptionProblem | None:
    """Two corrupted implicits can come only from the Locus, which draws the second from another mod group than the first."""
    (first_index, first), (second_index, second) = wanted
    pairs = [(a, b) for a in sorted(first.mod_ids) for b in sorted(second.mod_ids)]
    if any(not conflicts(data.mods[a], data.mods[b]) for a, b in pairs):
        return None
    a, b = data.mods[pairs[0][0]], data.mods[pairs[0][1]]
    group = next(family for family in a.families if family in b.families)
    pool = corrupted_implicit_pool(data, base_id, item_level)
    others = CorruptedImplicitPool(
        pool.base_id,
        pool.item_class,
        pool.item_level,
        tuple(entry for entry in pool.mods if not any(conflicts(data.mods[x], entry.mod) for x in first.mod_ids)),
    )
    nearest = CorruptedResolver._nearest(others, mod_text(b), lambda mod: (mod_text(mod).lower(),))
    return CorruptionProblem(
        IMPLICITS_KEY,
        second_index,
        f"implicits[{first_index}] and implicits[{second_index}] are both of the mod group `{group}` ({named(a)} and {named(b)}):"
        " two corrupted implicits can come only from the Locus of Corruption, which draws the second from another mod group than"
        f" the first, so no item holds both; the nearest corrupted implicits of another group: {nearest}",
    )


def _eldritch_sides(data: GameData, base: BaseItem) -> set[EldritchSide]:
    """The Eldritch sides some implicit of which has a spawn weight above 0 on `base`."""
    sides: set[EldritchSide] = set()
    for mod in data.mods.values():
        side = eldritch_side(mod)
        if side is not None and side not in sides and spawn_weight(mod, base.tags) > 0:
            sides.add(side)
    return sides


def _no_room(
    data: GameData,
    base: BaseItem,
    implicits: tuple[ImplicitRequirement, ...],
    ordinary: list[tuple[int, ImplicitRequirement]],
    wanted: list[tuple[int, ImplicitRequirement]],
    kinds: Mapping[str, int],
) -> CorruptionProblem | None:
    """A corrupting action that adds `k` corrupted implicits replaces `k` of the item's `n`: `max(n - k, 0)` ordinary ones stay."""
    held = len(base.implicits) + len(_eldritch_sides(data, base))
    able = {name: gives for name, gives in kinds.items() if gives >= len(wanted)}
    if not able or any(held - gives >= len(ordinary) for gives in able.values()):
        return None
    name, gives = max(able.items(), key=lambda kind: (-kind[1], kind[0]))  # the kind that replaces the fewest
    keeps = max(held - gives, 0)
    own = f" ({quoted(base.implicits)})" if base.implicits else ""
    ordinary_text = ", ".join(_asked_text(wish) for _, wish in ordinary)
    corrupted_text = ", ".join(_asked_text(wish) for _, wish in wanted)
    return CorruptionProblem(
        IMPLICITS_KEY,
        wanted[0][0],
        f"the target asks for {len(ordinary) + len(wanted)} implicits in all ({ordinary_text} and the corrupted {corrupted_text}),"
        f" but a corrupting action replaces implicits instead of adding to them: a {base.name} can hold {held} implicit"
        f"{'' if held == 1 else 's'}{own}, so after `{name}` (which adds {gives}) at most {keeps} of them stay;"
        " ask for fewer implicits",
    )

