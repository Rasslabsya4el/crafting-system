"""The crafted-pattern bound built without the walk (ticket #497): the members of a key by action class, and the model.

On a fixture Thicket Bow whose pool has five attack-tagged prefix families of four different weights and three suffix families, with the lock,
the Attack and the Caster metamods, the Exalted Orb, the Annulment, the Fracturing Orb, a Chaos Orb and Remove Crafted Mods are enabled. For keys
of states a seeded random walk met (both with the protected tags in the key and without them), the tests compare, by brute force, every member of
the key (`Pattern.members(key, Mode.ALL)`, each a state an item stands for) with the members the policy of each action class offers:

* every concrete state that the walk met is a member of its key (the brute force is complete);
* for random values of the successor keys, the least backup over the offered members is at most the backup of every member, and the action is
  offered whenever some member can take it (the optimistic model offers an action at least as good as every member's);
* a negative control: the lightest member alone does not do this for the Exalted Orb, and one member does not do it for a Chaos Orb under a lock,
  which is why those use the extremes and every member;
* the model built from the start key (`build_pattern_model`) gives, at every concrete state of the exact graph, a value at most the exact one
  (`tests/pattern_support.py`), and the exact one at the start for a key that tells every state apart.

Nothing here asserts a time (ADR-0014).
"""

import dataclasses
import random
from collections import Counter

import pytest
from abstraction_removals_support import (
    AS_5,
    BOW,
    BOW_DATA,
    CASTER,
    CRAFT,
    FIRE,
    FIRE_RES,
    METAMODS,
    NA,
    NC,
    PL,
    SL,
    SOCKET,
    SOCKET_LEAF,
    SPEED_TIER_1,
    build,
)
from pattern_support import all_members, check_dominates, exact_values, pushed

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import (
    ActionError,
    AlterationOrb,
    AnnulmentOrb,
    ApplyEssence,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    RegalOrb,
    RemoveCraftedMods,
    TransmutationOrb,
)
from crafting_system.cli._pattern_bound import pack_pattern_model
from crafting_system.data import EssenceMod, Weight
from crafting_system.items import Rarity, Side
from crafting_system.solver import solve_packed

LEVEL = 84
EXTRA_PREFIXES = (("PatternPrefixA", 500), ("PatternPrefixB", 2000), ("PatternPrefixC", 3000))  # attack-tagged, as FIRE is
EXTRA_SUFFIXES = (("PatternSuffixA", 400), ("PatternSuffixB", 2500))  # no tag, as FIRE_RES is
ESSENCE_ONLY = "PatternEssenceOnly"  # an attack-tagged prefix of its own family that only an essence forces: the pool does not list it
ESSENCES = ("Whispering Essence of Hatred", "Essence of Hysteria")  # both reforge a rare item (level 6 and 8): they remove every mod, the forced one stays
# the five of the first version, then the rest of the classes the ticket names
ACTIONS = {
    "chaos": ChaosOrb(), "exalted": ExaltedOrb(), "annul": AnnulmentOrb(), "fracture": FracturingOrb(), "remove": RemoveCraftedMods(),
    "essence-outside-pool": ApplyEssence(ESSENCES[0]), "essence-in-pool": ApplyEssence(ESSENCES[1]),
    "reforge-fire": HarvestReforge("fire"), "reforge-caster": HarvestReforge("caster"),
    "bench-lock": BenchCraft(PL), "bench-craft": BenchCraft(CRAFT),
    "augment": AugmentationOrb(), "regal": RegalOrb(), "transmute": TransmutationOrb(), "alter": AlterationOrb(),
}
EXPECTED_MODE = {
    "chaos": Mode.ANY, "exalted": Mode.EXTREMES, "annul": Mode.ONE, "fracture": Mode.ALL, "remove": Mode.ONE,
    "essence-outside-pool": Mode.ANY, "essence-in-pool": Mode.ANY, "reforge-fire": Mode.ANY, "reforge-caster": Mode.ANY,
    "bench-lock": Mode.ONE, "bench-craft": Mode.ONE, "augment": Mode.EXTREMES, "regal": Mode.EXTREMES, "transmute": Mode.ANY, "alter": Mode.ANY,
}
MODEL_ACTIONS = ("chaos", "exalted", "annul", "fracture", "remove")  # the route the exact graph is walked on (the others make it too big for a test)
GOAL = Goal((SOCKET_LEAF, SPEED_TIER_1))
STARTS = (
    (FIRE, AS_5, FIRE_RES),
    (FIRE, CASTER, AS_5, FIRE_RES, NA),
    (FIRE, SOCKET, AS_5, SL),  # the suffix lock keeps the suffixes through a reroll
    (FIRE, CASTER, AS_5, NC),
    (FIRE, SOCKET, FIRE_RES, EXTRA_SUFFIXES[1][0], SL),  # two junk suffixes kept by the lock, one open suffix slot that a reroll fills
    (FIRE, CASTER, EXTRA_SUFFIXES[0][0], EXTRA_SUFFIXES[1][0], SL),
)
OTHER_STARTS = (  # a normal bow, and magic bows: for Transmutation, the essences, Augmentation, Regal and Alteration
    ((), Rarity.NORMAL), ((), Rarity.NORMAL),
    ((FIRE,), Rarity.MAGIC), ((AS_5,), Rarity.MAGIC), ((CASTER, FIRE_RES), Rarity.MAGIC), ((SOCKET, AS_5), Rarity.MAGIC),
)


def pattern_data():
    """The fixture bow's pool with synthetic junk families, so that a class of pure junk has several types of different weights."""
    mods = {mod_id: BOW_DATA.mods[mod_id] for mod_id in (FIRE, SOCKET, CASTER, AS_5, FIRE_RES, CRAFT, *METAMODS.values())}
    mods[ESSENCE_ONLY] = dataclasses.replace(
        BOW_DATA.mods[FIRE], id=ESSENCE_ONLY, type=ESSENCE_ONLY, families=(ESSENCE_ONLY,), spawn_weights=(), is_essence_only=True
    )
    for template, extra in ((FIRE, EXTRA_PREFIXES), (FIRE_RES, EXTRA_SUFFIXES)):
        for name, weight in extra:
            mods[name] = dataclasses.replace(
                BOW_DATA.mods[template], id=name, type=name, families=(name,), spawn_weights=(Weight("bow", weight), Weight("default", 0))
            )
    forced = {ESSENCES[0]: ESSENCE_ONLY, ESSENCES[1]: SOCKET}
    essences = {
        key: dataclasses.replace(essence, mods=(EssenceMod("Bow", forced[essence.name]),), level=6 if essence.name == ESSENCES[0] else 8)
        if essence.name in forced
        else essence
        for key, essence in BOW_DATA.essences.items()
    }
    return dataclasses.replace(BOW_DATA, mods=mods, essences=essences)


@pytest.fixture(scope="module")
def world():
    data = pattern_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    states = set()
    rng = random.Random(497)
    starts = [ab.compress(build(data, BOW, ids)) for ids in STARTS]
    starts += [ab.compress(build(data, BOW, ids, rarity=rarity)) for ids, rarity in OTHER_STARTS]
    for start in starts:
        for _ in range(60):
            state = start
            for _ in range(8):
                states.add(state)
                if ab.is_goal(state):
                    break
                action = rng.choice(list(ACTIONS.values()))
                try:
                    kernel = ab.kernel(state, action)
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(c) for c in kernel.values()])[0]
    return data, ab, sorted(states, key=repr)


def pattern_of(ab, tags):
    """The `Pattern` with the offered actions, as `build_pattern_model` makes it: what they add by name joins the universe."""
    return Pattern(ab, tags, list(ACTIONS.values()))


def keys_of(pattern, states):
    return list(dict.fromkeys(pattern.key(state) for state in states))


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_every_state_the_walk_met_is_a_member_of_its_key(world, tags):
    _, ab, states = world
    pattern = pattern_of(ab, tags)
    for state in states:
        assert state in all_members(pattern, pattern.key(state)), state


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_mode_of_each_action_class(world, tags):
    _, ab, states = world
    pattern = pattern_of(ab, tags)
    for key in keys_of(pattern, states):
        for name, action in ACTIONS.items():
            expected = Mode.ALL if pattern.holds_lock(key) and EXPECTED_MODE[name] in (Mode.ANY, Mode.ONE) else EXPECTED_MODE[name]
            assert pattern.mode_of(action, key) is expected, (name, key)


def keys_where_legal(pattern, ab, keys, action, wanted, rng):
    """Up to `wanted` keys at which some member can take the action (a key with no legal member compares nothing)."""
    found = []
    for key in rng.sample(keys, len(keys)):
        if any(pushed(pattern, ab, member, action) is not None for member in all_members(pattern, key)):
            found.append(key)
            if len(found) == wanted:
                break
    return found


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
@pytest.mark.parametrize("name", list(ACTIONS))
def test_the_offered_members_are_at_least_as_good_as_every_member(world, name, tags):
    """The soundness argument of each action class, against brute force: every member of the key, random values of the successor keys."""
    _, ab, states = world
    pattern = pattern_of(ab, tags)
    rng = random.Random(1)
    sample = keys_where_legal(pattern, ab, keys_of(pattern, states), ACTIONS[name], 25, rng)
    assert sample, f"no key of the walk has a member that can take {name}"
    compared = offered = 0
    for key in sample:
        members, legal = check_dominates(pattern, ab, key, ACTIONS[name], pattern.mode_of(ACTIONS[name], key), rng, trials=12)
        compared += members
        offered += legal
    assert compared and offered


def keys_with_junk_choices(pattern, states):
    return [key for key in keys_of(pattern, states) if len(pattern.members(key, Mode.ALL)) > len(pattern.members(key, Mode.EXTREMES))]


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_extremes_are_fewer_than_every_member_and_the_lightest_alone_is_not_enough(world, tags):
    """The extremes save members (the point of the build), and one member does not do for an addition (so the check above can fail)."""
    _, ab, states = world
    pattern = pattern_of(ab, tags)
    choosy = keys_with_junk_choices(pattern, states)
    assert choosy, "the fixture has no key with a choice of junk"
    rng = random.Random(2)
    with pytest.raises(AssertionError):
        for key in choosy:
            check_dominates(pattern, ab, key, ACTIONS["exalted"], Mode.ONE, rng, trials=40)


def test_one_member_is_not_enough_for_a_reroll_under_a_lock(world):
    """A lock keeps the junk of its side through a reroll, so the draw depends on which families it holds: such a key uses every member."""
    _, ab, states = world
    pattern = pattern_of(ab, True)
    locked = [key for key in keys_of(pattern, states) if pattern.holds_lock(key)]
    assert locked
    rng = random.Random(3)
    with pytest.raises(AssertionError):
        for key in locked:
            check_dominates(pattern, ab, key, ACTIONS["chaos"], Mode.ANY, rng, trials=40)
    for key in locked:  # and every member is enough
        check_dominates(pattern, ab, key, ACTIONS["chaos"], Mode.ALL, rng, trials=5)


def offers_of():
    """The offers of the route the exact graph is walked on: five actions at made-up prices, and the restart."""
    costs = {"chaos": 1.0, "exalted": 2.0, "annul": 5.0, "fracture": 20.0, "remove": 0.5}
    return [PatternOffer(name, ACTIONS[name], costs[name]) for name in MODEL_ACTIONS] + [PatternOffer("restart", None, 3.0)]


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_model_is_a_lower_bound_at_every_concrete_state(world, tags):
    """`build_pattern_model` from the start key alone: its value at the key of every state of the exact graph is at most the exact value."""
    data, ab, _ = world
    start = ab.compress(build(data, BOW, STARTS[0]))
    offers = offers_of()
    exact = exact_values(ab, start, offers)
    model = build_pattern_model(ab, start, offers, tags=tags)
    solved = solve_packed(pack_pattern_model(model, offers))
    pattern = pattern_of(ab, tags)
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        bound = float(solved.value[model.index[key]])
        assert bound <= value * (1 + 1e-9) + 1e-9, (state, bound, value)
    assert 0 < solved.value[0] <= exact[start] * (1 + 1e-9)
    assert model.stats.kernels > 0 and model.stats.universe_growth == 0


def test_a_key_without_tags_is_not_stronger_than_one_with_them(world):
    data, ab, _ = world
    start = ab.compress(build(data, BOW, STARTS[1]))
    offers = offers_of()
    values = {}
    for tags in (True, False):
        model = build_pattern_model(ab, start, offers, tags=tags)
        values[tags] = float(solve_packed(pack_pattern_model(model, offers)).value[0])
    assert values[False] <= values[True] * (1 + 1e-9)


def test_the_statistics_count_what_was_evaluated(world):
    data, ab, _ = world
    start = ab.compress(build(data, BOW, STARTS[0]))
    model = build_pattern_model(ab, start, offers_of())
    stats = model.stats
    assert stats.keys == len(model.keys) == len(model.actions) and stats.goal_keys == sum(model.goal)
    assert stats.kernels <= stats.pairs and stats.abstract_actions == sum(len(row) for row in model.actions)
    assert Counter(model.goal)[True] == stats.goal_keys
    assert {mode for mode, _ in stats.modes} >= {"any", "extremes", "one", "all"}


# --- refusals: a game refusal may drop an action, a model gap may not (OR-12, OR-13) ----------------------------------


def lightest_prefix_attack_kind(pattern):
    classes = pattern.universe(frozenset()).classes[Side.PREFIX][("attack",)]
    return min(classes, key=lambda item: (item.type.weight(frozenset()), item.kind)).kind


def plant(monkeypatch, ab, error, when):
    """`kernel_key` of the Annulment raises `error` at the states `when` picks: a refusal planted at some members of some keys."""
    real = ab.kernel_key

    def planted(state, action):
        if action is ACTIONS["annul"] and when(state):
            raise error("planted")
        return real(state, action)

    monkeypatch.setattr(ab, "kernel_key", planted)


def planted_world(world):
    data, ab, _ = world
    start = ab.compress(build(data, BOW, STARTS[0]))
    kind = lightest_prefix_attack_kind(pattern_of(ab, True))
    return ab, start, lambda state: any(slot.kind == kind and not slot.crafted for slot in state.slots)


def test_a_model_gap_at_one_member_makes_the_build_refuse(world, monkeypatch):
    """The Annulment is offered at the lightest member of a key; a gap there, with other members that can take it, must not drop it."""
    ab, start, holds = planted_world(world)
    plant(monkeypatch, ab, OutOfScopeError, holds)
    with pytest.raises(OutOfScopeError, match="model gap"):
        build_pattern_model(ab, start, offers_of())


def test_a_game_refusal_at_the_same_members_only_drops_the_action_there(world, monkeypatch):
    ab, start, holds = planted_world(world)
    plant(monkeypatch, ab, NotApplicableError, holds)
    model = build_pattern_model(ab, start, offers_of())
    assert model.stats.refused_pairs > 0 and model.stats.gap_pairs == 0


def test_a_model_gap_at_every_member_of_a_key_drops_the_action_as_the_exact_model_does(world, monkeypatch):
    ab, start, _ = planted_world(world)
    plant(monkeypatch, ab, OutOfScopeError, lambda state: True)
    model = build_pattern_model(ab, start, offers_of())
    assert model.stats.gap_pairs > 0
    assert all(offers_of()[offer].label != "annul" for row in model.actions for offer, _ in row)


def test_what_an_offered_action_adds_by_name_is_in_the_universe_before_any_kernel_is_run(world):
    """The essence forces a mod the pool does not list: the universe has it from the offers, and the walk's states that hold it are members."""
    _, ab, states = world
    held = [state for state in states if any(slot.kind == ESSENCE_ONLY or ESSENCE_ONLY in slot.kind for slot in state.slots)]
    assert held, "the walk never met a state holding the essence-only mod"
    seeded, bare = pattern_of(ab, True), Pattern(ab, True)
    for state in held[:20]:
        assert state in all_members(seeded, seeded.key(state))
    assert any(state not in all_members(bare, bare.key(state)) for state in held)
