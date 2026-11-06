"""The chance of each tier of a wanted mod at a step, on R04's two Exalted Orbs (OR-31, ticket #466).

A guide's "guarantee" is of a family: its two Exalted Orbs force the Maximum Life and the Increased Damage with Bow Skills prefixes
(`cannot roll attack modifiers` leaves only those two). The published odds of the benchmark (`tests/test_cli_r04_r14_real.py`) say
how likely the top tier of each is: 2 in 15 for the first Exalted Orb (Life or Bow damage), 1 in 5 for the second (Bow damage, Life
being on). The tier lines must give the same numbers from the same game data, and each line must sum to 100%.
These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; CI fetches it) and skip cleanly without it.
"""

import dataclasses
import math
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan
from crafting_system.cli._benchmark import BENCHMARKS
from crafting_system.cli._benchmark_outcomes import item_of, published_outcomes
from crafting_system.cli._plan import offer_action
from crafting_system.cli._route_tiers import tier_lines
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.prices import load_price_file
from crafting_system.risk import evaluate
from crafting_system.solver import Solution
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
LIFE = "+# to maximum Life"
BOW = "#% increased Damage with Bow Skills"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def plan(data):
    return make_plan(data, load_target(ROOT / "examples/targets/r04-penetrating-quiver.yaml", data), load_price_file(PRICES), solve_it=False)


@pytest.fixture(scope="module")
def published(data):
    bench = next(each for each in BENCHMARKS if each.id == "R04")
    target = load_target(ROOT / bench.target, data)
    return bench, target, published_outcomes(data, target, bench.outcomes)


@pytest.fixture(scope="module")
def exalted(plan):
    return next(priced for priced in plan.offers if priced.label == "Exalted Orb")


@pytest.fixture(scope="module")
def first(plan, data, published):
    """The quiver with the Pierce fractured, the Strength, the arrow and the metamod: the first forced Exalted Orb."""
    bench, target, _ = published
    return plan.abstraction.compress(item_of(data, target, bench.outcomes[1]))


@pytest.fixture(scope="module")
def second(plan, data, published):
    """The same quiver with Maximum Life added: the second forced Exalted Orb."""
    bench, target, _ = published
    return plan.abstraction.compress(item_of(data, target, bench.outcomes[3]))


def by_text(lines):
    return {line.text: line for line in lines}


def target_share(line) -> float:
    """The chance of the best tier the target accepts and the item level lets spawn: the guide's 'top tier of the target'."""
    return next(share.chance for share in line.tiers if share.wanted)


def test_every_tier_line_sums_to_a_hundred_percent(plan, exalted, first, second):
    for state in (first, second):
        for line in tier_lines(plan.abstraction, exalted.offer.action, [state], [1.0]):
            assert math.fsum(share.chance for share in line.tiers) + line.none == pytest.approx(1.0)
            assert line.none >= 0.0 and all(share.chance >= 0.0 for share in line.tiers)


def test_the_first_exalted_orb_gives_life_and_bow_damage_a_tier_each_and_their_top_tiers_make_the_published_two_in_fifteen(
    plan, exalted, first, published
):
    _, _, found = published
    row = found[2]  # "adds the TOP tier of Life or of Bow damage": 13% of one use
    assert row["published"] == "100%" and row["computed"] == "13%"

    lines = by_text(tier_lines(plan.abstraction, exalted.offer.action, [first], [1.0]))

    assert set(lines) == {LIFE, BOW}
    life, bow = lines[LIFE], lines[BOW]
    assert life.tiers[0].tier == 1 and life.tiers[0].wanted and not any(share.wanted for share in life.tiers[1:])  # the target asks Life tier 1
    assert target_share(life) + target_share(bow) == pytest.approx(row["share"])  # the two top tiers, each a share of the same draw
    assert target_share(life) == pytest.approx(1 / 15) and target_share(bow) == pytest.approx(1 / 15)
    assert life.none == pytest.approx(1 / 3) and bow.none == pytest.approx(2 / 3)  # Life has 10 of the 15 draws, Bow damage 5


def test_the_second_exalted_orb_has_life_on_so_only_bow_damage_is_left_and_its_top_tier_is_the_published_one_in_five(
    plan, exalted, second, published
):
    _, _, found = published
    row = found[4]
    assert row["computed"] == "20%"

    lines = by_text(tier_lines(plan.abstraction, exalted.offer.action, [second], [1.0]))

    assert set(lines) == {BOW}
    assert target_share(lines[BOW]) == pytest.approx(row["share"]) == pytest.approx(0.2)
    assert lines[BOW].none == pytest.approx(0.0, abs=1e-12)  # the only prefix left: Bow damage is added for sure


def test_the_tiers_of_a_step_are_the_visit_weighted_mixture_of_its_states(plan, exalted, first, second):
    a = by_text(tier_lines(plan.abstraction, exalted.offer.action, [first], [1.0]))
    b = by_text(tier_lines(plan.abstraction, exalted.offer.action, [second], [1.0]))

    mixed = by_text(tier_lines(plan.abstraction, exalted.offer.action, [first, second], [3.0, 1.0]))

    assert mixed[LIFE].tiers[0].chance == pytest.approx(3 / 4 * a[LIFE].tiers[0].chance)  # the second state holds Life: 0 there
    assert target_share(mixed[BOW]) == pytest.approx(3 / 4 * target_share(a[BOW]) + 1 / 4 * target_share(b[BOW]))
    assert mixed[BOW].none == pytest.approx(3 / 4 * a[BOW].none + 1 / 4 * b[BOW].none)


def test_an_action_that_adds_no_wanted_family_has_no_tier_line(plan, first):
    annul = next(priced for priced in plan.offers if priced.label == "Orb of Annulment")

    assert tier_lines(plan.abstraction, annul.offer.action, [first], [1.0]) == []


def hand_policy(plan, exalted, first):
    """The Exalted Orb at the first state and at every state it leads to that still lacks a prefix; the rest are dead ends."""
    ab = plan.abstraction
    policy, order = {}, [first]
    for state in order:
        if ab.is_goal(state) or len(order) > 40 or len(state.slots) >= 5:
            continue
        policy[state] = offer_action(ab, exalted, state)
        order += [s for s, w in policy[state].outcomes if w > 0 and s not in order]
    return policy


def test_the_page_shows_the_tier_line_of_the_exalted_step(plan, exalted, first, data):
    policy = hand_policy(plan, exalted, first)
    start = dataclasses.replace(plan, start=first, solution=Solution({}, policy, 0.0), risk=evaluate(policy, first, plan.abstraction.is_goal))

    section = build_section(route_input(start), data)

    step = next(row for row in section.rows if row.title == "Exalted Orb")
    (field,) = [field for field in step.fields if field.label == "Tier chances"]
    lines = [line.text for line in field.lines]
    assert [line.split(":")[0] for line in lines] == [LIFE, BOW]
    assert lines[0].startswith(f"{LIFE}: T1 ") and "(target)" in lines[0] and lines[0].rstrip().split(" · ")[-1].startswith("none ")
