"""The contract suite of the actions (ticket #108): every check that any action must pass, with no edit per action.

`check_action(action, item)` runs the checks on one action and one item; `contract_pairs()` lists the
`(kind, action, item)` triples of the catalog on the fixture items, a few members of each kind. A new
method needs no line here: it registers its kind in the catalog and the suite finds it. The toy action
of `test_actions_toy.py` runs the same `check_action`.

The checks, each against something written without the code under test:

* the outcomes sum to one, seen through a label that tells every mod apart and through a coarse one;
* the finished items listed by brute force from `components` give each mod the chance `chance_all` says;
* the sampler holds each mod as often as that chance, within five standard errors (fixed seed);
* the kernel of `abstraction` equals the brute force on the compressed finished items (layer 1,
  ADR-0019), unless the action fractures a mod (the fossil tests cover that one);
* what the action declares agrees with what it does: an action that reads no junk keeps none, and an
  action that adds nothing unnamed only adds the mods it names; one that does not declare `adds.implicits`,
  `adds.quality` or `adds.offer` leaves the implicits, the quality and the offer as they were, and one that does
  not declare `reads.implicits`, `reads.quality` or `reads.offer` gives the same result on the item without them
  (ticket #142);
* an action that reads rule axes (ticket #210) passes every check above at every reading of its axes
  (`model_readings`), with the kernel of an abstraction made for that reading; its plain `outcomes(data, item)`
  is the plan's reading; and an action with inputs lists `Need`s of valid items, the same on every call;
* a corrupting action (ticket #258, ADR-0036) turns every outcome into a corrupted item, puts an implicit on it, and that item is
  final: no action of the catalog applies to it. An action that does not declare `adds.corrupts` leaves the corruption as it was. One
  that also declares `adds.keeps_mods` cannot reach the goal of a target that asks for a corrupted implicit from a state that misses
  another requirement, which is what lets a planner offer it from the other states only;
* Memory Strands (ticket #276, ADR-0041), on the fixture items that hold strands: an action that has not declared `strand_use` is
  refused on them (`OutOfScopeError`); a declared one is refused only for the reasons it refuses the same item with no strands, its
  result is a `Spent` exactly when it declares a spend, and the distribution of the count after the craft sums to one, follows the
  law and is the one the sampler draws; a draw that does not declare `cuts` gives the mods it gives at 0 strands, and a cutting
  action's draw differs from it on some stranded item (`check_cutting_kinds_differ_from_the_uncut_draw`). The kernel is not compared
  on them: the compressed state does not carry the count until B5-4 (#277);
* the fracturing actions (a Fractured Fossil) are not compared with the brute force here: their kernel
  has its own tests in `test_abstraction_fossil.py`;
* the resources are whole counts of named things and price the offer from a fixture price file.

The data is the fixture pool of `abstraction_pool.SMALL` plus the mods the fixture essences, fossils
and bench options name, so that every kind has something to do and the brute force stays small.
"""

import dataclasses
import datetime
import math
import random
from collections import defaultdict
from fractions import Fraction

from abstraction_pool import (
    FIRE_GEM,
    COLD_RESIST,
    DAMAGE_1,
    FIRE_RESIST,
    GEM,
    LEVEL,
    LIFE_1,
    LIFE_2,
    MANA_1,
    POOL_IDS,
    RESIST_1,
    RESIST_2,
    RESISTS,
)
from coarse_support import blocks_of, compare_members, compare_variants, concrete_items
from contract_registry import (
    ExtraFixture,
    extra_items,
    fixture_amulets,
    fixture_mods,
    is_free_action,
    load_family_fixtures,
    puts_back_forced_mod,
)
from items_support import AMULET, DATA

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted
from crafting_system.actions import (
    BLOCKING,
    Action,
    ActionError,
    Adds,
    Fixed,
    Need,
    OutOfScopeError,
    Reading,
    Reads,
    Rerolled,
    Spent,
    catalog,
    kinds,
    model_readings,
    strands_after,
)
from crafting_system.data import BaseItem, Weight
from crafting_system.cli._offers import FREE_ACTION_SHARE, offer_of, price_offers
from crafting_system.items import ExplicitMod, Influence, Item, Metamod, Rarity, is_corrupted_implicit, tier_table
from crafting_system.prices import CHAOS_ORB, PriceEntry, PriceFile
from crafting_system.rules import rule_by_id


load_family_fixtures()  # the families' own fixture modules (`contract_fixtures_*.py`) register what they add; none is named here

ORDINARY_CRAFT = "EinharMasterWeaponElementalDamage1_"  # an ordinary crafted mod of the fixture, copied for the extra crafts
COLD_CRAFT, FIRE_CRAFT, DAMAGE_CRAFT = "ContractCraftCold", "ContractCraftFire", "ContractCraftLightningDamage"
HYBRID_JUNK = "ContractJunkColdAndMana"  # a suffix mod of two families that no pool draws


def _fixture_data():
    keep = set(POOL_IDS)
    for essence in DATA.essences.values():
        keep.update(entry.mod_id for entry in essence.mods if entry.mod_id)
    for fossil in DATA.fossils.values():
        keep.update(fossil.forced_mods)
        keep.update(fossil.added_mods)
    for option in DATA.bench_options:
        if option.actions.add_explicit_mod:
            keep.add(option.actions.add_explicit_mod)
    keep &= set(DATA.mods)
    # the fixture names currencies in bench costs that it holds no base item for: add one, named by its id
    bases = dict(DATA.base_items)
    for option in DATA.bench_options:
        for entry in option.cost:
            bases.setdefault(
                entry.item_id,
                BaseItem(entry.item_id, entry.item_id.rsplit("/", 1)[-1], "StackableCurrency", "currency", 1, (), (), "released"),
            )
    mods = {mod_id: mod for mod_id, mod in DATA.mods.items() if mod_id in keep}
    # a Shaper prefix on amulets, which the fixture excerpt lacks: the lightning damage prefix with the spawn weight of an influence mod
    shaper = mods[DAMAGE_1]
    mods[SHAPER_PREFIX] = dataclasses.replace(
        shaper,
        id=SHAPER_PREFIX,
        type=SHAPER_PREFIX,
        families=(SHAPER_PREFIX,),
        spawn_weights=(Weight("amulet_shaper", 700), Weight("default", 0)),
    )
    # a cold added-damage prefix, the lightning one with its stat ids and tag renamed, so that the Harvest damage swaps have a target
    # (ticket #148): one tier of its own type, so it is tier 1, and the swaps find it from the tier-1 lightning damage mod
    lightning = mods[DAMAGE_1]
    mods[COLD_DAMAGE] = dataclasses.replace(
        lightning,
        id=COLD_DAMAGE,
        type=COLD_DAMAGE,
        families=(COLD_DAMAGE,),
        implicit_tags=tuple("cold" if tag == "lightning" else tag for tag in lightning.implicit_tags),
        stats=tuple(dataclasses.replace(stat, id=stat.id.replace("lightning", "cold")) for stat in lightning.stats),
    )
    # crafts that clash with a mod of the pool: every ordinary crafted mod takes the family of a mana mod,
    # so the items that hold that life mod refuse the craft and a kernel that forgets the family is caught
    metamods = {metamod.value for metamod in Metamod}
    for option in DATA.bench_options:
        crafted = mods.get(option.actions.add_explicit_mod or "")
        if crafted is not None and crafted.generation_type in ("prefix", "suffix") and crafted.stats and not metamods & set(crafted.families):
            mods[crafted.id] = dataclasses.replace(crafted, families=mods[MANA_1].families)
    # crafts that clash with more of the pool, so that several families are told apart and can be pooled
    # (ticket #125): a cold and a fire resistance craft (suffixes), a lightning damage craft (a prefix); and a
    # hybrid junk mod of two families that nothing draws, which the pooling must keep apart
    options = list(DATA.bench_options)
    template = next(option for option in options if option.actions.add_explicit_mod == ORDINARY_CRAFT)
    for mod_id, side, source in ((COLD_CRAFT, "suffix", COLD_RESIST), (FIRE_CRAFT, "suffix", FIRE_RESIST), (DAMAGE_CRAFT, "prefix", DAMAGE_1)):
        mods[mod_id] = dataclasses.replace(
            mods[ORDINARY_CRAFT], id=mod_id, type=mod_id, text=f"Test {mod_id}", families=mods[source].families, generation_type=side
        )
        options.append(dataclasses.replace(template, actions=dataclasses.replace(template.actions, add_explicit_mod=mod_id)))
    mods.update(fixture_mods())  # the mods the families register (the beast crafts' aspect suffixes, ticket #147)
    mods[HYBRID_JUNK] = dataclasses.replace(
        mods[COLD_RESIST], id=HYBRID_JUNK, families=(*mods[COLD_RESIST].families, *mods[MANA_1].families), spawn_weights=(), generation_weights=()
    )
    for option in options:
        for entry in option.cost:
            bases.setdefault(
                entry.item_id,
                BaseItem(entry.item_id, entry.item_id.rsplit("/", 1)[-1], "StackableCurrency", "currency", 1, (), (), "released"),
            )
    # the fixture amulet is a Talisman as far as the beast crafts go: the tag is all they read, and no mod spawns on it
    amulet = bases[AMULET]
    bases[AMULET] = dataclasses.replace(amulet, tags=(*amulet.tags, "talisman"))
    return dataclasses.replace(DATA, mods=mods, base_items=bases, bench_options=tuple(options))


SHAPER_PREFIX = "ContractShaperPrefix1"
COLD_DAMAGE = "ContractColdDamage1"
CONTRACT_DATA = _fixture_data()
TIERS = tier_table(CONTRACT_DATA, AMULET)
GOAL = Goal((Wanted(frozenset({GEM})), Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))))
SAMPLES = 1_000
SIGMAS = 5.0


def _roll(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    mod = CONTRACT_DATA.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def _item(rarity: Rarity, *mods: ExplicitMod, **fields) -> Item:
    return Item.build(CONTRACT_DATA, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods, **fields)


def _ordinary_crafted_mod() -> str | None:
    """A bench-crafted mod that is no metamod, for the item that holds a crafted mod."""
    metamods = {metamod.value for metamod in Metamod}
    for option in CONTRACT_DATA.bench_options:
        mod_id = option.actions.add_explicit_mod
        mod = CONTRACT_DATA.mods.get(mod_id) if mod_id else None
        if mod is not None and mod.generation_type in ("prefix", "suffix") and mod.stats and not metamods & set(mod.families):
            return mod_id
    return None


def fixture_items() -> dict[str, Item]:
    """The items the catalog is asked about: one of each rarity, and a rare item with fractured, junk and crafted mods."""
    items = {
        "normal": _item(Rarity.NORMAL),
        "magic": _item(Rarity.MAGIC, _roll(LIFE_1)),
        "rare_junk": _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1)),
        "rare_fractured": _item(Rarity.RARE, _roll(RESIST_1, fractured=True), _roll(MANA_1)),
        "rare_four": _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1), _roll(DAMAGE_1), _roll(FIRE_GEM)),
        "rare_shaper": _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1), influences=frozenset({Influence.SHAPER})),
        # a fire resistance and a cold damage, what the Harvest swaps change (fire to cold, cold to lightning); both are the only mod of
        # their family in the fixture, because the compressed state forgets which tier of a family a junk mod was (#149)
        "rare_resists": _item(Rarity.RARE, _roll(FIRE_RESIST), _roll(COLD_DAMAGE)),
    }
    items.update(fixture_amulets())  # the items the families register (the veiled orbs' placeholder and offer, ticket #144)
    crafted = _ordinary_crafted_mod()
    if crafted is not None:
        items["rare_crafted"] = _item(Rarity.RARE, _roll(RESIST_2), _roll(crafted, crafted=True))
    return items


def extra_fixture_items() -> dict[str, ExtraFixture]:
    """The items on a base of their own that the families register (`contract_registry.register_extra_item`).

    Each is asked about the kinds named with it and no other kind, in the data it lives in (`.data`).
    """
    return extra_items()


def extra_pairs(per_kind: int = 3) -> list[tuple[str, Action, str]]:
    """`(kind name, action, item name)` as `contract_pairs`, for `extra_fixture_items`."""
    found = []
    for name, extra in extra_fixture_items().items():
        for entry in kinds():
            if entry.name not in extra.kinds:
                continue
            members = list(entry.members(extra.data, extra.item))
            picked = members if len(members) <= per_kind else [members[0], members[len(members) // 2], members[-1]]
            found.extend((entry.name, action, name) for action in picked)
    return found


def contract_pairs(per_kind: int = 3) -> list[tuple[str, Action, str]]:
    """`(kind name, action, item name)` for up to `per_kind` members of each registered kind on each fixture item."""
    found = []
    for name, item in fixture_items().items():
        for entry in kinds():
            members = list(entry.members(CONTRACT_DATA, item))
            picked = members if len(members) <= per_kind else [members[0], members[len(members) // 2], members[-1]]
            found.extend((entry.name, action, name) for action in picked)
    return found


def check_every_kind_applies_on_some_fixture_item() -> set[str]:
    """Every registered kind applies on some fixture item, except the kinds that declare `applies_only_to`; the names that applied.

    A kind with `applies_only_to` (an armour-only kind, ticket #151) is not asked on the amulets of the fixture: it must not apply to
    one, or it is not that class only; it may use the extra items of its own class, which are armour. No kind is named here.
    """
    items, extra = fixture_items(), extra_fixture_items()
    limited = {entry.name for entry in kinds() if entry.applies_only_to}
    applied: set[str] = set()
    for kind, action, item in contract_pairs():
        try:
            action.outcomes(CONTRACT_DATA, items[item])
        except ActionError:
            continue
        applied.add(kind)
    assert not limited & applied, "a kind that applies to an amulet is not limited to one class: drop `applies_only_to` from its declaration"
    for kind, action, item in extra_pairs():  # the extra items are of the class a limited kind works on
        try:
            action.outcomes(extra[item].data, extra[item].item)
        except ActionError:
            continue
        applied.add(kind)
    assert {entry.name for entry in kinds()} - limited <= applied
    return applied


# --- the brute force ----------------------------------------------------------------------------


def finished(outcomes, data=CONTRACT_DATA) -> list[tuple[Fraction, Item]]:
    """Every finished item with its probability, listed from the mixture: a fixed result, or one item per outcome of a pool draw."""
    items = []
    for share, part in outcomes.components:
        if isinstance(part, Fixed):
            items.append((share, part.result))
            continue
        if isinstance(part, Rerolled):  # the same mods with other values: the checks that follow read mods, not values
            items.append((share, part.given))
            continue
        for outcome, chance in part.distribution(lambda mod: mod.id).items():
            added = tuple(
                _roll_in(data, mod_id) for mod_id, count in sorted(outcome) for _ in range(count)
            )
            items.append((share * chance, part.retained.changed(data, mods=(*part.retained.mods, *added))))
    return items


def _roll_in(data, mod_id: str) -> ExplicitMod:
    mod = data.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, tier_table(data, AMULET).get(mod_id, 1), values)  # only amulets are drawn onto in the brute force below


# --- the checks ----------------------------------------------------------------------------------


def check_action(action: Action, item: Item, data=CONTRACT_DATA, goal: Goal = GOAL) -> bool:
    """Run every check of the contract on `action` used on `item`; False when the game or the rules refuse it here (nothing to check).

    Raises `AssertionError` naming the check that failed.
    """
    readings = model_readings(data, [action])
    applied = False
    for reading in readings:
        applied |= _check_at(action, item, data, goal, reading)
    if applied:
        check_axes_and_inputs(action, item, data, readings)
        check_resources_are_priced(action, item, data)
        check_block_invariance(action, data, goal)
    return applied


def _check_at(action: Action, item: Item, data, goal: Goal, reading: Reading) -> bool:
    """Every check that depends on the result of the action, at one reading of its rule axes (the empty one for an action with none)."""
    try:
        outcomes = action.outcomes_under(data, item, reading)
    except ActionError as refusal:
        if item.memory_strands:
            check_stranded_refusal(action, item, data, type(refusal), reading)
        else:
            check_kernel_refuses_too(action, item, data, goal, type(refusal), reading)
        return False
    name = action.label(data)
    assert isinstance(name, str) and name, "the label is a name"
    reads, adds = action.reads(data), action.adds(data, item)
    assert isinstance(reads, Reads) and isinstance(adds, Adds)

    check_sums_to_one(outcomes, data)
    items = finished(outcomes, data)
    check_chances_agree(outcomes, items, data)
    check_sampler_follows_the_chances(outcomes, items, data)
    check_declarations_agree(action, reads, adds, outcomes, items, item)
    check_item_state_declarations(action, reads, adds, items, item, data, reading)
    check_corruption_declarations(action, reads, adds, items, item, data, goal)
    if item.memory_strands:
        check_strand_declarations(action, item, outcomes, items, data, reading)
    elif not outcomes.fractures and not _rerolls_values(outcomes):
        check_kernel_equals_brute_force(action, reads, item, items, data, goal, reading)
    return True


def _rerolls_values(outcomes) -> bool:
    """Whether a part of the result is a `Rerolled` one (a Divine Orb).

    Ticket #71: its kernel is not compared with the brute force here. `finished` lists the item once, with the values
    it had, while the kernel of a `Rerolled` part also depends on the roll limits of the goal, which the fixture GOAL
    does not have; the exact comparison over every value combination (small ranges) is layer 1 of #71 in the
    abstraction tests. Drop this skip once the kernel of a `Rerolled` part exists and `finished` lists the rolled items.
    """
    return any(isinstance(part, Rerolled) for _, part in outcomes.components)


def check_stranded_refusal(action: Action, item: Item, data, refusal: type[ActionError], reading: Reading | None = None) -> None:
    """The action refuses an item that holds strands (the kernel is not asked: the compressed state carries no count until #277).

    An action that has not declared `strand_use` is refused with `OutOfScopeError`, whatever the item. A declared one is refused for the
    reasons of the game only: it refuses the same item with no strands, for the same reason.
    """
    if action.strand_use(data) is None:
        assert refusal is OutOfScopeError, "an action that has not declared strand_use is refused on an item with strands as out of scope"
        return
    bare = item.changed(data, memory_strands=0)
    try:
        action.outcomes_under(data, bare, reading)
    except ActionError as raised:
        assert type(raised) is refusal, "a declared action refuses a stranded item for the reason it refuses the item with no strands"
    else:
        raise AssertionError(f"{action.label(data)} declares its strand use yet refuses the stranded item ({refusal.__name__}) and not the same item with none")


def check_strand_declarations(action: Action, item: Item, outcomes, items, data, reading: Reading | None = None) -> None:
    """What a declared action does on an item with strands (ADR-0041): see the module docstring."""
    use = action.strand_use(data)
    assert use is not None, "an action that has not declared strand_use is refused on an item with strands, not run"
    assert isinstance(use.claims, frozenset) and all(rule_by_id(claim).id == claim for claim in use.claims), "every claim behind a declaration is in the registry"
    assert action.strand_claims(data) == use.claims
    assert use.claims, "a declaration cites the claim it rests on"
    assert ("memory_strands.rollable_tiers" in use.claims) == use.cuts, "an action cites the cut formula exactly when it cuts"
    assert (use.spend is not None) == isinstance(outcomes, Spent), "the result is a Spent exactly when the action declares a spend"
    after = strands_after(outcomes, item.memory_strands)
    assert sum(after.values()) == 1, "the count after the craft is a distribution"
    assert after == use.after(item), "the count after the craft is the declared law's, from the count before"
    low = item.memory_strands - (use.spend.ceiling(len(item.mods)) if use.spend is not None else 0)
    assert all(max(0, low) <= left <= item.memory_strands for left in after), "a craft never raises the count and never spends more than its ceiling"
    rng = random.Random(20261101)
    seen: dict[int, int] = defaultdict(int)
    for _ in range(SAMPLES):
        drawn = outcomes.sample(rng)
        drawn.validate(data)
        assert drawn.memory_strands in after, "the sampler draws a count the distribution allows"
        seen[drawn.memory_strands] += 1
    for left, chance in after.items():
        error = SIGMAS * math.sqrt(float(chance) * (1 - float(chance)) / SAMPLES) + 1e-9
        assert abs(seen[left] / SAMPLES - float(chance)) <= error, f"the sampler leaves {left} strands as often as the distribution says"
    if not use.cuts:
        bare = item.changed(data, memory_strands=0)
        assert _by_mods(items) == _by_mods(finished(action.outcomes_under(data, bare, reading), data)), (
            "an action that does not declare `cuts` draws the mods it draws at 0 strands"
        )


def _by_mods(listed) -> dict:
    """The finished items with the chance of each, the strand count left out."""
    return _stripped(listed, {"memory_strands": 0})


def check_cutting_kinds_differ_from_the_uncut_draw(data=CONTRACT_DATA) -> set[str]:
    """Every kind that declares `cuts` gives, on some stranded fixture item, other mods than it gives at 0 strands; the names that did.

    A cut can leave a draw as it was (a pool whose tables are one tier), so this is asked of the kind on all the items, not of each.
    """
    differing: set[str] = set()
    declared: set[str] = set()
    for kind, action, name in contract_pairs():
        item = fixture_items()[name]
        use = action.strand_use(data)
        if not item.memory_strands or use is None or not use.cuts:
            continue
        declared.add(kind)
        try:
            cut = finished(action.outcomes_under(data, item), data)
            plain = finished(action.outcomes_under(data, item.changed(data, memory_strands=0)), data)
        except ActionError:
            continue
        if _by_mods(cut) != _by_mods(plain):
            differing.add(kind)
    assert declared <= differing, f"a kind declares `cuts` yet never draws other mods than at 0 strands: {sorted(declared - differing)}"
    return declared


def check_kernel_refuses_too(action, item: Item, data, goal: Goal, refusal: type[ActionError], reading: Reading | None = None) -> None:
    """Where the action refuses the item, the kernel of the item's state refuses it the same way (the families the action reads are told apart)."""
    reads = action.reads(data)
    ab = Abstraction(data, goal, item.base_id, item.item_level, [action] if reads.junk or reads.item_state else [], reading=reading)
    try:
        kernel = ab.kernel(ab.compress(item), action)
    except ActionError as raised:
        assert type(raised) is refusal, "the kernel refuses for the same reason the action does"
    else:
        raise AssertionError(f"the action refuses the item ({refusal.__name__}) but the kernel of its state does not: {dict(kernel)!r}")


def check_sums_to_one(outcomes, data) -> None:
    for label in (lambda mod: mod.id, lambda mod: mod.generation_type):
        assert sum(outcomes.distribution(label).values()) == 1, "the outcomes sum to exactly one"
    assert sum(share for share, _ in outcomes.components) == 1, "the components sum to exactly one"


def _held(items, mod_id: str, data=None) -> Fraction:
    """The chance that a finished item holds `mod_id`: as a mod, or, for a corrupted implicit, as an implicit.

    A corrupting action's `chance_all` counts the corrupted implicit it adds (ticket #261); the other implicits (Eldritch, base) are
    not asked of `chance_all` by any action yet, so they are not counted here.
    """
    corrupted = data is not None and is_corrupted_implicit(data.mods[mod_id])
    return sum(
        (chance for chance, item in items if any(e.mod_id == mod_id for e in (*item.mods, *(item.implicits if corrupted else ())))),
        Fraction(0),
    )


def check_chances_agree(outcomes, items, data) -> None:
    assert sum(chance for chance, _ in items) == 1, "the listed finished items sum to one"
    for mod_id in data.mods:
        assert _held(items, mod_id, data) == outcomes.chance_all([mod_id]), f"chance_all of {mod_id} is the listed items'"


def check_sampler_follows_the_chances(outcomes, items, data) -> None:
    rng = random.Random(20261031)
    seen: dict[str, int] = defaultdict(int)
    for _ in range(SAMPLES):
        drawn = outcomes.sample(rng)
        drawn.validate(data)
        for mod_id in {entry.mod_id for entry in (*drawn.mods, *(e for e in drawn.implicits if is_corrupted_implicit(data.mods[e.mod_id])))}:
            seen[mod_id] += 1
    for mod_id in data.mods:
        chance = float(outcomes.chance_all([mod_id]))
        error = SIGMAS * math.sqrt(chance * (1 - chance) / SAMPLES) + 1e-9
        assert abs(seen[mod_id] / SAMPLES - chance) <= error, f"the sampler holds {mod_id} as often as chance_all says"


def check_declarations_agree(action, reads: Reads, adds: Adds, outcomes, items, given: Item) -> None:
    if reads.needs_crafted:
        assert given.crafted_mods, "an action that needs a crafted mod refuses an item without one"
    if adds.named is not None:
        for _, result in items:
            assert adds.named <= {entry.mod_id for entry in result.mods}, "every result holds the mods the action names"
    if adds.tag is not None:
        assert adds.draws, "a guaranteed tag belongs to a draw"
        for _, result in items:
            drawn = [CONTRACT_DATA.mods[e.mod_id] for e in result.mods if not e.fractured and not e.crafted]
            assert any(adds.tag in mod.implicit_tags for mod in drawn), "every result holds a drawn mod with the guaranteed tag"
    if not adds.keeps_crafted:
        crafted = {entry.mod_id for entry in given.mods if entry.crafted}
        for _, result in items:
            assert not crafted & {entry.mod_id for entry in result.mods if entry.crafted}, "an action that erases the crafted mods leaves none"
    if adds.single_draw:
        assert adds.draws and not reads.junk and not adds.named, "a single draw reads no junk and forces no mod"
    assert adds.fractures or not outcomes.fractures, "an action that fractures a mod says so in `adds`"
    if not adds.fractures:
        fractured = {entry.mod_id for entry in given.mods if entry.fractured}
        for _, result in items:
            assert fractured == {entry.mod_id for entry in result.mods if entry.fractured}, "an action that does not fracture leaves the fractured mods as they were"
    junk = {entry.mod_id for entry in given.mods if not entry.fractured and not entry.crafted}
    if not reads.junk:
        for _, part in outcomes.components:
            forced = getattr(part, "forced", None) if puts_back_forced_mod(action) else None  # a mod it erased may be put back: forced, not kept
            kept = {entry.mod_id for entry in part.retained.mods if not entry.fractured and not entry.crafted and entry.mod_id != forced}
            assert not kept & junk, "an action that reads no junk erases it"
    if adds.named is not None and not adds.draws:
        held = {(entry.mod_id, entry.fractured, entry.crafted) for entry in given.mods}
        for _, result in items:
            new = {entry.mod_id for entry in result.mods if (entry.mod_id, entry.fractured, entry.crafted) not in held}
            assert new <= adds.named, "an action that draws nothing adds only the mods it names"
    if adds.named is not None and adds.crafted:
        for _, result in items:
            crafted = {entry.mod_id for entry in result.mods if entry.crafted}
            assert adds.named & crafted or not adds.named, "the named mods are added as crafted mods"


def check_item_state_declarations(action, reads: Reads, adds: Adds, items, given: Item, data, reading: Reading | None = None) -> None:
    """The implicits, the quality and the offer: an action changes only what `adds` says, and reads only what `reads` says (ticket #142)."""
    for _, result in items:
        if not adds.implicits:
            assert result.implicits == given.implicits, "an action that does not declare adds.implicits leaves the implicits as they were"
        if not adds.quality:
            assert result.quality == given.quality, "an action that does not declare adds.quality leaves the quality as it was"
        if not adds.offer:
            placeholder = any(data.mods[entry.mod_id].domain == "veiled" for entry in result.mods)
            assert result.veil_offer == (given.veil_offer if placeholder else ()), (
                "an action that does not declare adds.offer leaves the offer as it was (it goes with its placeholder)"
            )
    without = {
        "implicits": (reads.implicits, bool(given.implicits), {"implicits": ()}),
        "quality": (reads.quality, given.quality is not None, {"quality": None}),
        "offer": (reads.offer, bool(given.veil_offer), {"veil_offer": ()}),
    }
    for name, (declared, held, strip) in without.items():
        if declared or not held:
            continue
        bare = given.changed(data, **strip)
        try:
            other = action.outcomes_under(data, bare, reading)
        except ActionError:
            raise AssertionError(f"an action that does not declare reads.{name} refuses the item once its {name} are taken off, but not with them") from None
        assert _stripped(finished(other, data), strip) == _stripped(items, strip), (
            f"an action that does not declare reads.{name} gives the same result on the item without its {name}"
        )


def check_corruption_declarations(action, reads: Reads, adds: Adds, items, given: Item, data, goal: Goal) -> None:
    """Corruption (ticket #258, ADR-0036): only an action that declares `adds.corrupts` corrupts, and what it corrupts is final.

    * without `adds.corrupts` every result is corrupted exactly when the item was;
    * with it every result is corrupted, and no action of the catalog applies to a result (it is the goal or a dead end);
    * with `adds.keeps_mods` as well, from an item whose state misses a requirement no result is a goal of the same goal made to
      ask for a corrupted implicit (the exactness of the pruning of `cli._prune`).
    """
    if not adds.corrupts:
        for _, result in items:
            assert result.corrupted == given.corrupted, "an action that does not declare adds.corrupts leaves the corruption as it was"
        return
    assert adds.implicits, "an action that corrupts adds an implicit"
    for _, result in items:
        assert result.corrupted, "every result of a corrupting action is a corrupted item"
        for other in catalog(data, result):
            try:
                other.outcomes(data, result)
            except ActionError:
                continue
            raise AssertionError(f"a corrupted item is final, but {other.label(data)} applies to a result of {action.label(data)}")
    if adds.keeps_mods:
        asking = dataclasses.replace(goal, asks_corrupted=True)
        ab = Abstraction(data, asking, given.base_id, given.item_level, [action] if reads.junk or reads.item_state else [])
        if not ab.meets_requirements(ab.compress(given)):
            for _, result in items:
                assert not ab.is_goal(ab.compress(result)), (
                    "an action that keeps the mods cannot reach the goal from a state that misses a requirement"
                )


def _stripped(listed, strip: dict) -> dict:
    """The finished items with the chance of each, with the fields of `strip` taken off, added up by item."""
    found: dict = defaultdict(Fraction)
    for chance, result in listed:
        found[dataclasses.replace(result, **strip)] += chance
    return dict(found)


def check_kernel_equals_brute_force(action, reads: Reads, item: Item, items, data, goal: Goal, reading: Reading | None = None) -> None:
    enabled = [action] if reads.junk or reads.item_state else []
    ab = Abstraction(data, goal, item.base_id, item.item_level, enabled, reading=reading)
    expected: dict = defaultdict(Fraction)
    for chance, result in items:
        expected[ab.compress(result)] += chance
    kernel = ab.kernel(ab.compress(item), action)
    assert dict(kernel) == dict(expected), "the kernel equals the brute force on the compressed finished items"
    assert sum(kernel.values()) == 1


def check_axes_and_inputs(action: Action, item: Item, data, readings: tuple[Reading, ...]) -> None:
    """The two-item declarations (ticket #210): an action's `inputs` are `Need`s of valid items, the same on every call; and one that
    reads rule axes takes the plan's reading when it is given none, or one that lacks its axes, and has one model per combination of values.
    """
    needs = action.inputs(data, item)
    assert isinstance(needs, tuple) and all(isinstance(need, Need) for need in needs), "inputs are a tuple of Needs"
    assert needs == action.inputs(data, item), "an action gives the same inputs on every call"
    for need in needs:
        need.start.validate(data)
        need.want.validate(data)
    axes = action.rule_axes(data)
    assert isinstance(axes, tuple) and len({axis.name for axis in axes}) == len(axes), "an action lists each axis once"
    assert len(readings) == math.prod(len(axis.readings) for axis in axes), "one reading for each combination of values of the axes"
    assert readings[0] == Reading.of({axis.name: axis.plan for axis in axes}), "the plan's reading comes first"
    if not axes:
        return
    plan = _stripped(finished(action.outcomes_under(data, item, readings[0]), data), {})
    for given in (None, Reading()):
        plain = action.outcomes(data, item, given)
        assert _stripped(finished(plain, data), {}) == plan, "an action with axes uses the plan's reading when it is given none"
    assert _stripped(finished(action.outcomes(data, item), data), {}) == plan, "outcomes(data, item) is the plan's reading"


def check_resources_are_priced(action, item: Item, data) -> None:
    resources = action.resources(data)
    assert resources or is_free_action(action), "one use consumes something, unless the action's family registers it as free"
    assert all(isinstance(name, str) and name and isinstance(count, int) and count > 0 for name, count in resources.items())
    prices = {name: PriceEntry(2.0, "test") for name in resources if name != CHAOS_ORB}
    file = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)
    offer = offer_of(action, action.label(data), data, item)
    priced, dropped = price_offers([offer], file)
    assert not dropped and len(priced) == 1, "every resource is found in a price file that names it"
    expected = sum(float(count) if name == CHAOS_ORB else 2.0 * count for name, count in resources.items())
    if not resources:  # a free action costs the planner's epsilon, a share of the cheapest offer that costs something (here there is none)
        expected = FREE_ACTION_SHARE
    assert priced[0].cost == expected


# --- block invariance ----------------------------------------------------------------------------


_WORLDS: dict = {}
_COMPARED: dict = {}  # a kind is compared once however many fixture items list it


def _adds_blocking_metamod(data, action: Action) -> bool:
    """Whether the action adds a lock or an Attack/Caster metamod: it makes the state model metamods, which has no coarse level yet (#69)."""
    blocking = {metamod.value for metamod in BLOCKING}
    return any(blocking & set(data.mods[mod_id].families) for mod_id in action.adds(data).named or ())


def _coarse_world(data, goal: Goal, extra: Action | None):
    """The exact abstraction (the catalog's crafts and Remove Crafted Mods enabled, and `extra` when it reads the junk),
    the coarsenings under test, and the blocks of the fixture items with their exact states (the brute force)."""
    crafts = [
        action
        for entry in kinds()
        if entry.name in ("bench-craft", "remove-crafted-mods")
        for action in entry.members(data, _item(Rarity.RARE, _roll(LIFE_1)))
        if not _adds_blocking_metamod(data, action)
    ]
    enabled = tuple(dict.fromkeys([*crafts, *([extra] if extra is not None else [])]))
    key = (id(data), goal, enabled)
    if key not in _WORLDS:
        ab = Abstraction(data, goal, AMULET, LEVEL, enabled)
        coarsenings = [Coarsening.pooling_irrelevant(ab), Coarsening.pooling_irrelevant(ab, 2)]
        ordinary = [MANA_1, COLD_RESIST, FIRE_RESIST, HYBRID_JUNK, DAMAGE_1, RESIST_2, LIFE_1]
        items = list(concrete_items(data, ordinary, crafted=[COLD_CRAFT, _ordinary_crafted_mod()], largest=4, rarities=(Rarity.RARE, Rarity.MAGIC)))
        _WORLDS[key] = (ab, [(c, blocks_of(ab, c, items)) for c in coarsenings])
    return _WORLDS[key]


def fixture_blocks(data=CONTRACT_DATA, goal: Goal = GOAL) -> list[dict]:
    """The blocks of the fixture items under each coarsening of the contract suite: `{block: exact states}`, found by brute force.

    The items hold up to four mods drawn from the pooled families, a goal-relevant family and a hybrid junk
    mod, with at most one fractured and one crafted mod, so a full prefix side and a full suffix side are
    among them.
    """
    return [blocks for _, blocks in _coarse_world(data, goal, None)[1]]


def check_block_invariance(action: Action, data=CONTRACT_DATA, goal: Goal = GOAL) -> int:
    """Where the action declares `block_invariant`, the members of a block where it is legal give the same kernel pushed through the blocks;
    where it declares `variants`, the backups of the members lie between the smallest and the largest backup of the variant kernels (`compare_variants`).

    The blocks and their members come from the brute force over concrete items (`fixture_blocks`), the
    kernels are the exact kernels of the members, and the legality of each is the action's own. The two
    models of the coarse state must offer the action exactly where some member (the lower) or every member
    (the upper) can take it, and give that kernel. An action that declares neither must be refused by the
    coarse state (`OutOfScopeError`). Returns how many members were compared with another member of their block.
    """
    key = (action, id(data), goal)
    if key not in _COMPARED:
        _COMPARED[key] = _compare_members(action, data, goal)
    return _COMPARED[key]


def _compare_members(action: Action, data, goal: Goal) -> int:
    reads = action.reads(data)
    if not reads.block_invariant and not reads.variants:
        ab, [(coarsening, blocks), *_] = _coarse_world(data, goal, None)
        block = next(iter(blocks))
        for bound in ("lower", "upper"):
            try:
                coarsening.kernel(block, action, bound)
            except OutOfScopeError:
                continue
            raise AssertionError("an action that declares neither block_invariant nor variants is refused by the coarse state")
        return 0
    try:
        ab, worlds = _coarse_world(data, goal, action if reads.junk else None)
    except OutOfScopeError as refusal:
        raise AssertionError(f"the action declares block_invariant or variants but the coarse state refuses it: {refusal}") from refusal
    check = compare_variants if reads.variants else compare_members
    return sum(check(action, ab, coarsening, blocks) for coarsening, blocks in worlds)
