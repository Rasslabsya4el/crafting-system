"""Fossils in a Chaotic resonator: a Chaos Orb reroll of a rare item with the pool weights changed by the fossils.

`ApplyFossils(("Dense Fossil", "Shuddering Fossil"))` is one action for a set of one to four
different fossils (named as in the game data or by record id); the number of fossils is the number of
sockets of the Chaotic resonator that holds them (`resonator`). `outcomes(data, item)` returns a
`FossilOutcomes`: the same three ways in as an `Outcomes` (`chance_all`, `distribution`, `sample`).

A resonator with a Tangled Fossil draws one of the 420 tag pairs of the data and a Glyphic Fossil
draws one corrupted-essence mod, so the result is a mixture of plain `Outcomes` (`components`, each
with its probability, components that have the same pool merged). Every other set is one component.
A Fractured Fossil fractures one of the finished mods: `distribution` then also gives `Fractured`
labels (see there).

Refusals, in this order:

* `NotApplicableError`: the item is not rare or is corrupted; a socketed fossil forbids the base (a
  base tag it does not allow, or one it forbids); the item holds a metamod other than the multimod;
  a Fractured Fossil on an item with a fractured mod or an influence; the forced mod of a Hollow or
  Glyphic Fossil shares a family with a fractured mod.
* `OutOfScopeError`: a Bloodstained Fossil (its corrupted implicit is corruption, B4); a jewel, an
  influenced item or an item with the multimod; Hollow and Glyphic in one resonator (no admitted
  rule); a Tangled Fossil when the data holds no outcome records; fractured mods that fill the side
  of the forced mod; a Glyphic Fossil whose candidates are all blocked or missing.
* `ValueError`: raised at construction for no fossil, more than four or the same one twice, and by
  `outcomes` for a name that is no fossil of the data.

The lucky rolls of a Sanctified Fossil change the rolled values only, which belong to the roll
requirements of the Divine Orb ticket; `sample` rolls every value once.
"""

import random
from collections import defaultdict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import combinations

from crafting_system.data import Fossil, GameData, Mod, conflicts
from crafting_system.items import Item, Metamod, Rarity, Side, UnknownBaseError, capacity
from crafting_system.rules import get_rule

from .draw import Outcome, refuse_unmodelled
from .errors import ActionError, NotApplicableError, OutOfScopeError
from .fossil_weights import FossilWeights, fossil_weights
from .outcomes import Outcomes, retained_item
from .pool import Candidate, group_pool, pool_candidates

CHAOTIC_RESONATOR_SOCKETS = get_rule("fossils.chaotic_resonator_sockets")
RESONATOR_REROLLS_LIKE_CHAOS = get_rule("fossils.resonator_rerolls_like_chaos")
RESONATOR_RARE_ONLY = get_rule("fossils.resonator_rare_only")
NO_DUPLICATE_FOSSIL = get_rule("fossils.no_duplicate_fossil")
REFUSED_ON_CORRUPTED = get_rule("fossils.refused_on_corrupted")
REFUSED_BY_METAMOD = get_rule("fossils.refused_by_metamod")
FOSSIL_USE_RESTRICTIONS = get_rule("fossils.use_restrictions")
SPECIAL_FOSSILS = get_rule("fossils.special_fossils")
BLOODSTAINED_IS_CORRUPTION = get_rule("fossils.bloodstained_is_corruption")
GILDED_NO_EXPLICIT_EFFECT = get_rule("fossils.gilded_no_explicit_effect")
FACETED_ADDS_MODS = get_rule("fossils.faceted_adds_mods")
ADDED_MODS_TAKE_FOSSIL_WEIGHTS = get_rule("fossils.added_mods_take_fossil_weights")
HOLLOW_FORCES_MOD = get_rule("fossils.hollow_forces_mod")
GLYPHIC_FORCES_CORRUPTED_ESSENCE_MOD = get_rule("fossils.glyphic_forces_corrupted_essence_mod")
GLYPHIC_BASE_WEIGHT = get_rule("fossils.glyphic_base_weight")
FORCED_MOD_COUNTS_IN_TOTAL = get_rule("fossils.forced_mod_counts_in_total")
FORCED_MOD_IGNORES_ITEM_LEVEL = get_rule("fossils.forced_mod_ignores_item_level")
TANGLED_PAIR_UNIFORM = get_rule("fossils.tangled_pair_uniform")
TANGLED_ADDS_NO_MODS = get_rule("fossils.tangled_adds_no_mods")
FRACTURED_FOSSIL_FRACTURES_ONE = get_rule("fossils.fractured_fossil_fractures_one")
FRACTURED_FOSSIL_REFUSED = get_rule("fossils.fractured_fossil_refused_on_fractured_or_influenced")
FRACTURED_MOD_UNIFORM = get_rule("fossils.fractured_mod_uniform")
FRACTURED_MODS_KEPT = get_rule("fossils.fractured_mods_kept")
DAGGER_STAFF_TAKE_CLASS_MODS = get_rule("essence.dagger_staff_take_class_mods")

MIN_FOSSILS = 1
MAX_FOSSILS = max(CHAOTIC_RESONATOR_SOCKETS.value.values())
TANGLED_RECORD_MARKER = "RandomFossilOutcome"


@dataclass(frozen=True, slots=True)
class Fractured:
    """The label of a mod that a Fractured Fossil fractured: `Fractured(label(mod))` in an outcome with count 1.

    The fractured mod is also counted under its own label like every new mod, so a caller that
    does not care about fracturing reads the same counts as for any reroll.
    """

    label: Hashable


@dataclass(frozen=True, eq=False)
class FossilOutcomes:
    """What a resonator with `fossils` can leave behind: a mixture of `Outcomes` (`components`).

    `components` holds `(probability, Outcomes)` pairs that sum to 1. `fractures` is True when a
    Fractured Fossil is socketed: one finished mod is then fractured, uniformly among all of them.
    """

    data: GameData
    components: tuple[tuple[Fraction, Outcomes], ...]
    fractures: bool

    def chance_all(self, mod_ids) -> Fraction:
        """The exact chance that the finished item holds all of `mod_ids`, kept, forced or newly drawn."""
        wanted = list(mod_ids)
        return sum((p * part.chance_all(wanted) for p, part in self.components), Fraction(0))

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The exact distribution of the new mods seen through `label`, as for `Outcomes.distribution`.

        With a Fractured Fossil every outcome also holds one `(Fractured(l), 1)` pair, `l` being the
        label of the mod that was fractured; the mods that are kept or forced take part in the choice.
        """
        mixed: dict[Outcome, Fraction] = defaultdict(Fraction)
        for p, part in self.components:
            forced = None if part.forced is None else label(self.data.mods[part.forced])
            for outcome, chance in part.distribution(label).items():
                if not self.fractures:
                    mixed[outcome] += p * chance
                    continue
                counts = dict(outcome)
                if forced is not None:
                    counts[forced] = counts.get(forced, 0) + 1
                whole = sum(counts.values())
                if whole == 0:
                    mixed[outcome] += p * chance
                    continue
                for lab, count in counts.items():
                    mixed[outcome | {(Fractured(lab), 1)}] += p * chance * Fraction(count, whole)
        return dict(mixed)

    def sample(self, rng: random.Random) -> Item:
        """One finished item drawn with `rng`; a Fractured Fossil fractures one of its mods at random."""
        part = rng.choices([c for _, c in self.components], weights=[float(p) for p, _ in self.components])[0]
        finished = part.sample(rng)
        if not self.fractures or not finished.mods:
            return finished
        chosen = rng.randrange(len(finished.mods))
        mods = tuple(
            replace(entry, fractured=True) if index == chosen else entry
            for index, entry in enumerate(finished.mods)
        )
        return finished.changed(self.data, mods=mods)


@dataclass(frozen=True)
class ApplyFossils:
    """One Chaotic resonator with 1 to 4 different fossils, each named as in the game data or by record id."""

    fossils: tuple[str, ...]

    def __post_init__(self) -> None:
        names = self.fossils
        if isinstance(names, str) or not all(isinstance(name, str) and name.strip() for name in names):
            raise ValueError("a resonator is given the names of its fossils, as a tuple of strings")
        if not MIN_FOSSILS <= len(names) <= MAX_FOSSILS:
            raise ValueError(f"a Chaotic resonator holds {MIN_FOSSILS} to {MAX_FOSSILS} fossils, not {len(names)}")
        if len(set(names)) != len(names):
            raise ValueError("a resonator takes one fossil of each type, and this set repeats one")
        object.__setattr__(self, "fossils", tuple(sorted(names)))

    @classmethod
    def of(cls, *names: str) -> "ApplyFossils":
        return cls(tuple(names))

    @property
    def resonator(self) -> str:
        """The Chaotic resonator with as many sockets as there are fossils ("Potent Chaotic Resonator")."""
        sockets = {count: name for name, count in CHAOTIC_RESONATOR_SOCKETS.value.items()}
        return f"{sockets[len(self.fossils)]} Chaotic Resonator"

    def outcomes(self, data: GameData, item: Item) -> FossilOutcomes:
        """The outcomes of using the resonator on `item`; see the module text for the refusals."""
        records = [_record(data, name) for name in self.fossils]
        if len({record.id for record in records}) != len(records):
            raise ValueError("a resonator takes one fossil of each type, and this set names one twice")
        _check_item(data, item)
        base = data.base_items.get(item.base_id)
        if base is None:
            raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
        for record in records:
            _check_fossil(record, base.tags, item)
        _check_set(records)
        refuse_unmodelled(data, item)
        return _build(data, item, records)


def _record(data: GameData, name: str) -> Fossil:
    """The fossil named `name` (or with that record id); the Tangled outcome records are no fossils to socket."""
    for record in data.fossils.values():
        if name in (record.name, record.id) and record.name:
            return record
    raise ValueError(f"there is no fossil {name!r} in the game data")


def _special(record: Fossil, key: str) -> bool:
    return record.name == SPECIAL_FOSSILS.value[key]


def _check_item(data: GameData, item: Item) -> None:
    if item.rarity is not Rarity.RARE:
        raise NotApplicableError(f"a Chaotic resonator works on a rare item only, and this item is {item.rarity}")
    if item.corrupted:
        raise NotApplicableError("the item is corrupted, and a corrupted item takes no resonator")
    blocking = item.metamods(data) - {Metamod.MULTIPLE_CRAFTED_MODS}
    if blocking:
        names = ", ".join(sorted(metamod.value for metamod in blocking))
        raise NotApplicableError(f"a resonator cannot be used on an item with a metamod ({names})")


def _check_fossil(record: Fossil, base_tags: tuple[str, ...], item: Item) -> None:
    """The refusals that one fossil makes on its own: the base it allows and the state of the item it takes."""
    if record.allowed_tags and not set(record.allowed_tags) & set(base_tags):
        raise NotApplicableError(
            f"the {record.name} works on an item with one of the tags {', '.join(record.allowed_tags)} only"
        )
    forbidden = sorted(set(record.forbidden_tags) & set(base_tags))
    if forbidden:
        raise NotApplicableError(f"the {record.name} does not work on an item with the tag {forbidden[0]}")
    if _special(record, "fractured") and (item.fractured_mods or item.influences):
        raise NotApplicableError(
            f"the {record.name} cannot be used on a fractured or an influenced item"
        )
    if _special(record, "bloodstained"):
        raise OutOfScopeError(
            f"the {record.name} makes the item corrupted and adds a corrupted implicit, "
            "which belongs to corruption (B4) and is not modelled"
        )


def _check_set(records: list[Fossil]) -> None:
    forcing = [
        record
        for record in records
        if record.forced_mods or record.corrupted_essence_chance >= 100 and not _special(record, "tangled")
    ]
    if len(forcing) > 1:
        raise OutOfScopeError(
            "two fossils that each force a mod (Hollow and Glyphic) are in one resonator; "
            "no admitted rule says how the game counts them"
        )


def usable_fossils(data: GameData, item: Item) -> list[str]:
    """The names of the fossils that a resonator could hold on `item`: none when the item takes no resonator.

    A fossil the item refuses on its own, or that is out of scope (Bloodstained), is left out.
    """
    try:
        _check_item(data, item)
        refuse_unmodelled(data, item)
    except ActionError:
        return []
    base = data.base_items.get(item.base_id)
    if base is None:
        raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
    usable = []
    for record in data.fossils.values():
        if not record.name:
            continue
        try:
            _check_fossil(record, base.tags, item)
        except ActionError:
            continue
        usable.append(record.name)
    return usable


def fossil_actions(data: GameData, item: Item) -> list[ApplyFossils]:
    """Every `ApplyFossils` set of 1 to 4 fossils that `item` could take: the actions of the fossil family.

    A set is listed when each fossil is usable on the item and the set is not out of scope as a
    whole (Hollow with Glyphic). A set can still be refused later by `outcomes` for a reason that
    needs the pool (a forced mod that has no room).
    """
    names = usable_fossils(data, item)
    by_name = {record.name: record for record in data.fossils.values() if record.name}
    actions = []
    for size in range(MIN_FOSSILS, MAX_FOSSILS + 1):
        for chosen in combinations(names, size):
            try:
                _check_set([by_name[name] for name in chosen])
            except ActionError:
                continue
            actions.append(ApplyFossils(chosen))
    return actions


def _build(data: GameData, item: Item, records: list[Fossil]) -> FossilOutcomes:
    opulent = any(_special(record, "opulent") for record in records)
    sanctified = any(record.rolls_lucky for record in records)
    tangled = any(_special(record, "tangled") for record in records)
    extra = _added_mods(data, records)
    pairs = _tangled_pairs(data) if tangled else [(Fraction(1), None)]
    fractures = any(_special(record, "fractured") for record in records)
    candidates_for: dict[str | None, tuple[Candidate, ...]] = {}
    retained_for: dict[str | None, Item] = {}
    merged: dict[tuple, list] = {}
    for pair_chance, pair in pairs:
        weights = fossil_weights(records, pair, opulent=opulent, sanctified=sanctified)
        for forced_chance, forced in _forced_choices(data, item, records, weights):
            key = None if forced is None else forced.id
            if key not in retained_for:
                retained_for[key] = retained_item(data, item, forced)
                candidates_for[key] = pool_candidates(data, retained_for[key], None, extra)
            pool = group_pool(candidates_for[key], weights.factor)
            signature = (key, tuple((family.family, tuple((e.mod.id, e.weight) for e in family.mods)) for family in pool))
            part = Outcomes.over(data, retained_for[key], pool, None, forced)
            entry = merged.setdefault(signature, [Fraction(0), part])
            entry[0] += pair_chance * forced_chance
    components = tuple((chance, part) for chance, part in merged.values())
    return FossilOutcomes(data, components, fractures)


def _added_mods(data: GameData, records: list[Fossil]) -> list[Mod]:
    """The mods that join the pool: those a fossil adds, a Tangled Fossil's legacy list not counted."""
    ids = dict.fromkeys(
        mod_id for record in records if not _special(record, "tangled") for mod_id in record.added_mods
    )
    return [data.mods[mod_id] for mod_id in ids]


def _tangled_pairs(data: GameData) -> list[tuple[Fraction, Fossil]]:
    """The 420 outcome records of a Tangled Fossil, each with the same probability."""
    pairs = [record for record in data.fossils.values() if not record.name and TANGLED_RECORD_MARKER in record.id]
    if not pairs:
        raise OutOfScopeError("the game data holds no outcome records for the Tangled Fossil")
    return [(Fraction(1, len(pairs)), record) for record in pairs]


def _forced_choices(
    data: GameData, item: Item, records: list[Fossil], weights: FossilWeights
) -> list[tuple[Fraction, Mod | None]]:
    """The forced mods of the resonator with their probabilities: `[(1, None)]` when no fossil forces one."""
    base = data.base_items[item.base_id]
    for record in records:
        if record.forced_mods:
            mods = [data.mods[mod_id] for mod_id in record.forced_mods]
            if len(mods) != 1:
                raise OutOfScopeError(f"the {record.name} forces {len(mods)} mods; only one is modelled")
            _check_forced(data, item, mods[0], record.name)
            return [(Fraction(1), mods[0])]
        if record.corrupted_essence_chance >= 100 and not _special(record, "tangled"):
            return _glyphic_choices(data, item, base.item_class, weights, record.name)
    return [(Fraction(1), None)]


def _glyphic_choices(
    data: GameData, item: Item, item_class: str, weights: FossilWeights, name: str
) -> list[tuple[Fraction, Mod | None]]:
    """The corrupted-essence mod of a Glyphic Fossil: base weight 1000, times the tag factor, per candidate."""
    candidates: dict[str, Fraction] = {}
    for essence in data.essences.values():
        if not essence.is_corruption_only:
            continue
        mod_id = essence.mod_for(item_class)
        if mod_id is None:
            mod_id = essence.mod_for(DAGGER_STAFF_TAKE_CLASS_MODS.value.get(item_class, item_class))
        if mod_id is None:
            continue
        mod = data.mods[mod_id]
        if any(conflicts(mod, data.mods[entry.mod_id]) for entry in item.fractured_mods):
            continue
        weight = GLYPHIC_BASE_WEIGHT.value * weights.factor(mod, tags_only=True)
        if weight > 0:
            candidates[mod_id] = candidates.get(mod_id, Fraction(0)) + weight
    if not candidates:
        raise OutOfScopeError(f"the {name} has no corrupted-essence mod to force on this item")
    whole = sum(candidates.values(), Fraction(0))
    choices = []
    for mod_id, weight in candidates.items():
        _check_forced(data, item, data.mods[mod_id], name)
        choices.append((weight / whole, data.mods[mod_id]))
    return choices


def _check_forced(data: GameData, item: Item, forced: Mod, name: str) -> None:
    """The forced mod must fit beside the fractured mods: its family free, a slot on its side."""
    side = Side(forced.generation_type)
    for entry in item.fractured_mods:
        if conflicts(forced, data.mods[entry.mod_id]):
            raise NotApplicableError(
                f"the item already has a mod of this type: the forced mod {forced.id} of the {name} "
                f"shares a family with the fractured mod {entry.mod_id}"
            )
    used = sum(1 for entry in item.fractured_mods if data.mods[entry.mod_id].generation_type == side.value)
    if used >= capacity(data, item.base_id, Rarity.RARE).of(side):
        raise OutOfScopeError(
            f"the fractured mods fill every {side.value} slot, so the forced mod {forced.id} "
            "has no slot; no admitted rule says what the game does then"
        )
