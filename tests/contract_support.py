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
  action that adds nothing unnamed only adds the mods it names;
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
from coarse_support import blocks_of, compare_members, concrete_items
from items_support import AMULET, DATA

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted
from crafting_system.actions import (
    Action,
    ActionError,
    Adds,
    Fixed,
    OutOfScopeError,
    Reads,
    kinds,
)
from crafting_system.data import BaseItem, Weight
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import ExplicitMod, Influence, Item, Metamod, Rarity, tier_table
from crafting_system.prices import CHAOS_ORB, PriceEntry, PriceFile


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
    mods[HYBRID_JUNK] = dataclasses.replace(
        mods[COLD_RESIST], id=HYBRID_JUNK, families=(*mods[COLD_RESIST].families, *mods[MANA_1].families), spawn_weights=(), generation_weights=()
    )
    for option in options:
        for entry in option.cost:
            bases.setdefault(
                entry.item_id,
                BaseItem(entry.item_id, entry.item_id.rsplit("/", 1)[-1], "StackableCurrency", "currency", 1, (), (), "released"),
            )
    return dataclasses.replace(DATA, mods=mods, base_items=bases, bench_options=tuple(options))


SHAPER_PREFIX = "ContractShaperPrefix1"
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
    }
    crafted = _ordinary_crafted_mod()
    if crafted is not None:
        items["rare_crafted"] = _item(Rarity.RARE, _roll(RESIST_2), _roll(crafted, crafted=True))
    return items


def contract_pairs(per_kind: int = 3) -> list[tuple[str, Action, str]]:
    """`(kind name, action, item name)` for up to `per_kind` members of each registered kind on each fixture item."""
    found = []
    for name, item in fixture_items().items():
        for entry in kinds():
            members = list(entry.members(CONTRACT_DATA, item))
            picked = members if len(members) <= per_kind else [members[0], members[len(members) // 2], members[-1]]
            found.extend((entry.name, action, name) for action in picked)
    return found


# --- the brute force ----------------------------------------------------------------------------


def finished(outcomes, data=CONTRACT_DATA) -> list[tuple[Fraction, Item]]:
    """Every finished item with its probability, listed from the mixture: a fixed result, or one item per outcome of a pool draw."""
    items = []
    for share, part in outcomes.components:
        if isinstance(part, Fixed):
            items.append((share, part.result))
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
    return ExplicitMod(mod_id, tier_table(data, AMULET).get(mod_id, 1), values)


# --- the checks ----------------------------------------------------------------------------------


def check_action(action: Action, item: Item, data=CONTRACT_DATA, goal: Goal = GOAL) -> bool:
    """Run every check of the contract on `action` used on `item`; False when the game or the rules refuse it here (nothing to check).

    Raises `AssertionError` naming the check that failed.
    """
    try:
        outcomes = action.outcomes(data, item)
    except ActionError as refusal:
        check_kernel_refuses_too(action, item, data, goal, type(refusal))
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
    if not outcomes.fractures:
        check_kernel_equals_brute_force(action, reads, item, items, data, goal)
    check_resources_are_priced(action, item, data)
    check_block_invariance(action, data, goal)
    return True


def check_kernel_refuses_too(action, item: Item, data, goal: Goal, refusal: type[ActionError]) -> None:
    """Where the action refuses the item, the kernel of the item's state refuses it the same way (the families the action reads are told apart)."""
    reads = action.reads(data)
    ab = Abstraction(data, goal, AMULET, LEVEL, [action] if reads.junk else [])
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


def _held(items, mod_id: str) -> Fraction:
    return sum((chance for chance, item in items if any(e.mod_id == mod_id for e in item.mods)), Fraction(0))


def check_chances_agree(outcomes, items, data) -> None:
    assert sum(chance for chance, _ in items) == 1, "the listed finished items sum to one"
    for mod_id in data.mods:
        assert _held(items, mod_id) == outcomes.chance_all([mod_id]), f"chance_all of {mod_id} is the listed items'"


def check_sampler_follows_the_chances(outcomes, items, data) -> None:
    rng = random.Random(20261031)
    seen: dict[str, int] = defaultdict(int)
    for _ in range(SAMPLES):
        drawn = outcomes.sample(rng)
        drawn.validate(data)
        for mod_id in {entry.mod_id for entry in drawn.mods}:
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
            kept = {entry.mod_id for entry in part.retained.mods if not entry.fractured and not entry.crafted}
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


def check_kernel_equals_brute_force(action, reads: Reads, item: Item, items, data, goal: Goal) -> None:
    enabled = [action] if reads.junk else []
    ab = Abstraction(data, goal, AMULET, LEVEL, enabled)
    expected: dict = defaultdict(Fraction)
    for chance, result in items:
        expected[ab.compress(result)] += chance
    kernel = ab.kernel(ab.compress(item), action)
    assert dict(kernel) == dict(expected), "the kernel equals the brute force on the compressed finished items"
    assert sum(kernel.values()) == 1


def check_resources_are_priced(action, item: Item, data) -> None:
    resources = action.resources(data)
    assert resources, "one use consumes something"
    assert all(isinstance(name, str) and name and isinstance(count, int) and count > 0 for name, count in resources.items())
    prices = {name: PriceEntry(2.0, "test") for name in resources if name != CHAOS_ORB}
    file = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)
    offer = offer_of(action, action.label(data), data, item)
    priced, dropped = price_offers([offer], file)
    assert not dropped and len(priced) == 1, "every resource is found in a price file that names it"
    expected = sum(float(count) if name == CHAOS_ORB else 2.0 * count for name, count in resources.items())
    assert priced[0].cost == expected


# --- block invariance ----------------------------------------------------------------------------


_WORLDS: dict = {}
_COMPARED: dict = {}  # a kind is compared once however many fixture items list it


def _coarse_world(data, goal: Goal, extra: Action | None):
    """The exact abstraction (the catalog's crafts and Remove Crafted Mods enabled, and `extra` when it reads the junk),
    the coarsenings under test, and the blocks of the fixture items with their exact states (the brute force)."""
    crafts = [action for entry in kinds() if entry.name in ("bench-craft", "remove-crafted-mods") for action in entry.members(data, _item(Rarity.RARE, _roll(LIFE_1)))]
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
    """Where the action declares `block_invariant`, the members of a block where it is legal give the same kernel pushed through the blocks.

    The blocks and their members come from the brute force over concrete items (`fixture_blocks`), the
    kernels are the exact kernels of the members, and the legality of each is the action's own. The two
    models of the coarse state must offer the action exactly where some member (the lower) or every member
    (the upper) can take it, and give that kernel. An action that does not declare it must be refused by the
    coarse state (`OutOfScopeError`). Returns how many members were compared with another member of their block.
    """
    key = (action, id(data), goal)
    if key not in _COMPARED:
        _COMPARED[key] = _compare_members(action, data, goal)
    return _COMPARED[key]


def _compare_members(action: Action, data, goal: Goal) -> int:
    reads = action.reads(data)
    if not reads.block_invariant:
        ab, [(coarsening, blocks), *_] = _coarse_world(data, goal, None)
        block = next(iter(blocks))
        for bound in ("lower", "upper"):
            try:
                coarsening.kernel(block, action, bound)
            except OutOfScopeError:
                continue
            raise AssertionError("an action that does not declare block_invariant is refused by the coarse state")
        return 0
    try:
        ab, worlds = _coarse_world(data, goal, action if reads.junk else None)
    except OutOfScopeError as refusal:
        raise AssertionError(f"the action declares block_invariant but the coarse state refuses it: {refusal}") from refusal
    return sum(compare_members(action, ab, coarsening, blocks) for coarsening, blocks in worlds)
