"""The bound's build makes an erasing action's kernel from the alike twin (ticket #1146, ADR-0065; OR-12, OR-14).

An action that erases the ordinary slots (`Abstraction._erases`: it reads no junk and no lock keeps a side) has, in the pattern build, the
kernel of `Abstraction.alike_twin`: the same abstraction with its ordinary slots told apart by side and protected tags alone. The key of a state
(`Pattern.key`) reads of the ordinary slots their count per side and those tags, so the twin's outcomes fall on the keys the fine ones fall on,
with the same chances, from far fewer outcomes; and members are made from the key and the slot universe, never from the outcomes that reached
a key, so nothing else of the build changes. What is checked here:

* the twin's pushed kernel is the fine one, at every member the build asks an erasing action of (the bow world of `test_abstraction_pattern`,
  with the metamods, the tags on and off, a lock, essences and Harvest reforges);
* the build with the twin is the build without it: the same keys, rows and values, from fewer outcomes (counted);
* the bound stays at or below the exact value at every state of the exact graph (OR-12), as `test_free_action_floors` checks its floors;
* through the planner's entry, counted in states (`Budget.in_states`), the plan and its lower figure are the same with the twin and without.
"""

from collections import defaultdict
from fractions import Fraction

import pytest
from pattern_support import exact_values
from test_abstraction_pattern import ACTIONS, BOW, STARTS, build, offers_of, pattern_of, world  # noqa: F401 (world: the fixture)
from test_cli_envelope_plan import coarse  # noqa: F401 (the fixture: the coarse world, a Chaos Orb and bench crafts)
from coarse_support import DATA as COARSE

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import Pattern, PatternBuilder, PatternOffer, build_pattern_model
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.actions import ActionError
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.solver import solve_packed

ERASING = ("chaos", "essence-outside-pool", "essence-in-pool", "reforge-fire", "reforge-caster", "alter", "transmute")
BROAD = ("chaos", "essence-in-pool", "reforge-fire", "reforge-caster", "exalted", "annul", "bench-craft", "bench-lock", "remove")


def broad_offers() -> list[PatternOffer]:
    """Erasing draws beside readers of the junk (bench crafts, a lock, the Exalted Orb, the Annulment): a build of a few hundred keys."""
    return [PatternOffer(name, ACTIONS[name], 1.0 + i / 4) for i, name in enumerate(BROAD)] + [PatternOffer("restart", None, 3.0)]


def pushed(pattern, ab, state, action) -> dict:
    out = defaultdict(Fraction)
    for successor, chance in ab.kernel(state, action).items():
        out[pattern.key(successor)] += chance
    return dict(out)


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_twins_kernel_of_an_erasing_action_falls_on_the_fine_keys_with_the_fine_chances(world, tags):
    data, ab, states = world
    pattern, twin = pattern_of(ab, tags), ab.alike_twin()
    checked = fine_outcomes = twin_outcomes = 0
    for state in states:
        for name in ERASING:
            action = ACTIONS[name]
            if not ab._erases(state, action):
                continue
            try:
                fine = ab.kernel(state, action)
            except ActionError:
                with pytest.raises(ActionError):
                    twin.kernel(state, action)
                continue
            lumped = twin.kernel(state, action)
            assert pushed(pattern, twin, state, action) == pushed(pattern, ab, state, action), (name, state)
            checked += 1
            fine_outcomes += len(fine)
            twin_outcomes += len(lumped)
    assert checked > 100
    assert twin_outcomes < fine_outcomes


def test_a_lumped_outcome_holds_no_kind_of_the_fine_abstraction_but_the_veiled_and_the_crafted(world):
    """The twin's states are not states of the abstraction: their ordinary slots are `ALIKE` with the tags (never noted in the universe)."""
    data, ab, _ = world
    start = ab.compress(build(data, BOW, STARTS[0]))
    for successor in ab.alike_twin().kernel(start, ACTIONS["chaos"]):
        assert all(slot.crafted or slot.kind.split("@")[0] == "" for slot in successor.slots), successor


def build_counted(ab, start, offers, tags, lump, monkeypatch):
    """The model with or without the twin, and the outcomes its kernels pushed onto keys."""
    monkeypatch.setattr(_pattern, "LUMP_ERASING", lump)
    count = [0]
    real = PatternBuilder._intern

    def counting(self, state):
        count[0] += 1
        return real(self, state)

    monkeypatch.setattr(PatternBuilder, "_intern", counting)
    model = build_pattern_model(ab, start, offers, tags=tags)
    monkeypatch.setattr(PatternBuilder, "_intern", real)
    return model, count[0]


def rows_of(model) -> list[list]:
    """Each key's row as (offer, its pushed kernel as sorted (successor key, chance)): kernel ids depend on the order kernels were made."""
    return [sorted((oi, tuple(sorted(zip(*model.kernels[k])))) for oi, k in row) for row in model.actions]


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
@pytest.mark.parametrize("start", [0, 4], ids=["plain", "lock"])
def test_the_build_with_the_twin_is_the_build_without_it_from_fewer_outcomes(world, tags, start, monkeypatch):
    data, ab, _ = world
    first = ab.compress(build(data, BOW, STARTS[start]))
    offers = broad_offers()
    fine, fine_count = build_counted(ab, first, offers, tags, False, monkeypatch)
    lumped, lumped_count = build_counted(ab, first, offers, tags, True, monkeypatch)
    assert lumped.keys == fine.keys and lumped.goal == fine.goal
    assert rows_of(lumped) == rows_of(fine)
    by_fine = solve_packed(pack_pattern_model(fine, offers)).value
    by_lumped = solve_packed(pack_pattern_model(lumped, offers)).value
    assert list(by_lumped) == pytest.approx(list(by_fine), rel=1e-12)
    assert lumped.stats.universe_growth == fine.stats.universe_growth
    assert lumped_count < fine_count


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_with_the_twin_the_bound_is_at_most_the_exact_value_at_every_state_of_the_exact_graph(world, tags):
    """OR-12: the chaos of the exact graph's route (`offers_of`) is erasing, so its kernels are the twin's; every key's value <= V* there."""
    assert _pattern.LUMP_ERASING
    data, ab, _ = world
    for ids in (STARTS[0], STARTS[4]):  # a plain start and one with a suffix lock (a reroll under a lock is not erasing: the fine kernel)
        start = ab.compress(build(data, BOW, ids))
        offers = offers_of()
        exact = exact_values(ab, start, offers)
        model = build_pattern_model(ab, start, offers, tags=tags)
        solved = solve_packed(pack_pattern_model(model, offers))
        pattern = pattern_of(ab, tags)
        for state, value in exact.items():
            bound = float(solved.value[model.index[pattern.key(state)]])
            assert bound <= value * (1 + 1e-9) + 1e-9, (state, bound, value)


def test_through_the_planners_entry_counted_in_states_the_plan_and_its_lower_figure_are_the_same(coarse, monkeypatch):  # noqa: F811
    """The coarse world (a Chaos Orb, bench crafts that read the junk, Remove Crafted Mods), planned to the end on a count of states."""
    target, prices, _ = coarse
    found, lumped = {}, []
    real = Abstraction.alike_twin
    monkeypatch.setattr(Abstraction, "alike_twin", lambda self: (lumped.append(1), real(self))[1])
    for lump in (False, True):
        monkeypatch.setattr(_pattern, "LUMP_ERASING", lump)
        plan = plan_target(COARSE, target, prices, PlanSettings(recipe_starts=False, start_price=5.0, solver="envelope", budget=Budget.in_states(10**5)))
        info = plan.packed.info["envelope"]
        found[lump] = (plan.mean_remaining, info.lower, info.exact)
    assert lumped, "the bound's build never asked the twin"
    assert found[True][2] and found[False][2]
    assert found[True][0] == pytest.approx(found[False][0], rel=1e-12)
    assert found[True][1] == pytest.approx(found[False][1], rel=1e-12)


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
@pytest.mark.parametrize("start", [0, 4], ids=["plain", "lock"])
def test_a_fine_erasing_kernel_teaches_the_seeded_universe_no_slot(world, tags, start, monkeypatch):
    """Without the twin, the build notes every outcome: those of the erasing kernels never grow the universe (pool and names seeded it)."""
    data, ab, _ = world
    monkeypatch.setattr(_pattern, "LUMP_ERASING", False)
    grown = []
    real = Pattern.note
    erasing = [False]
    kernel = ab.kernel

    def note(self, state):
        before = self.grew
        real(self, state)
        if erasing[0] and self.grew > before:
            grown.append(state)

    def marked(state, action):
        erasing[0] = ab._erases(state, action)
        return kernel(state, action)

    monkeypatch.setattr(Pattern, "note", note)
    monkeypatch.setattr(ab, "kernel", marked)
    model = build_pattern_model(ab, ab.compress(build(data, BOW, STARTS[start])), broad_offers(), tags=tags)
    assert model.stats.kernels > 0
    assert not grown, grown[:3]
