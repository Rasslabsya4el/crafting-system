"""The route page of a lumped plan is made from item states, not from the shown member of a block (ticket #466, issue #492, OR-20, OR-31).

A packed plan above `VIEW_FROM_STATES` item states is shown by its lumped chain. The chances, uses and costs of the lumped chain are exact,
but a statement about an item (a mod lost, the tiers a draw can add) was read off one member of a block, so R04 printed "Bow Attacks fire an
additional Arrow lost (100%)" after a Remove Crafted Mods and R14 a loss after an Augmentation. `_route_chain.chain_of_packed_policy` holds the
policy on item states as arrays straight from the walked graph and `_route_flow.flow_of` makes the steps of it. Here the packed V01 (a few
hundred item states, a few seconds) has its view forced to the lumped chain and the two ways to the same steps are compared with the plain
mapping of the same policy, which `build_flow` reads state by state.
These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`) and skip cleanly without it.
"""

import math
from pathlib import Path

import numpy as np
import pytest
from abstraction_support import real_game_data

from crafting_system.cli import _plan, make_plan
from crafting_system.cli._route_chain import chain_of_packed_policy
from crafting_system.cli._route_flow import build_flow, flow_of
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "v01-minion-helmet.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "vendor-v01-2026-11-01.json"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def plan(data):
    return make_plan(data, load_target(TARGET, data), load_price_file(PRICES), solver="packed")


@pytest.fixture
def lumped_plan(plan, monkeypatch):
    monkeypatch.setattr(_plan, "VIEW_FROM_STATES", 10)  # the view is the lumped chain, as for R04 and R14
    assert plan.lumped
    return plan


def by_label(flow):
    return {step.action.label: step for step in flow.steps if step.action is not None}


def test_the_flow_of_the_packed_chain_is_the_flow_of_the_policy_state_by_state(plan):
    mapping = build_flow(plan.start, plan.policy, plan.is_goal, is_restart=lambda action: action.label == "restart")
    packed = flow_of(chain_of_packed_policy(plan.policy), is_restart=lambda action: action.label == "restart")

    assert packed.measured and mapping.measured and set(by_label(packed)) == set(by_label(mapping))
    for label, step in by_label(mapping).items():
        other = by_label(packed)[label]
        assert set(step.states) == set(other.states)
        assert other.uses == pytest.approx(step.uses, rel=1e-9) and other.cost == pytest.approx(step.cost)
        wanted = {(edge.kind, edge.to and mapping.steps[edge.to - 1].action and mapping.steps[edge.to - 1].action.label): edge.chance for edge in step.edges}
        got = {(edge.kind, edge.to and packed.steps[edge.to - 1].action and packed.steps[edge.to - 1].action.label): edge.chance for edge in other.edges}
        assert got == pytest.approx(wanted, rel=1e-9)


def test_a_sparse_solve_of_the_visits_agrees_with_the_dense_inverse(plan, monkeypatch):
    from crafting_system.cli import _route_flow

    chain = chain_of_packed_policy(plan.policy)
    dense = flow_of(chain)
    monkeypatch.setattr(_route_flow, "ENTRY_STATES", 5)  # every chain with more than 5 states that can finish goes to BiCGSTAB

    sparse = flow_of(chain)

    assert sparse.measured and not sparse.entered and dense.entered
    for a, b in zip(dense.steps, sparse.steps):
        assert b.uses == pytest.approx(a.uses, rel=1e-8)
        assert b.weights == pytest.approx(a.weights, rel=1e-7)
        assert [edge.chance for edge in b.edges] == pytest.approx([edge.chance for edge in a.edges], rel=1e-8)


def test_the_page_of_a_lumped_plan_says_what_the_item_states_do(lumped_plan, data):
    section = build_section(route_input(lumped_plan), data)

    adding = [row for row in section.rows if row.title in ("Orb of Augmentation", "Regal Orb")]
    assert adding
    for row in adding:  # an orb that only adds a mod never takes one away
        assert not any(" lost" in line.text for field in row.fields if field.label == "On failure" for line in field.lines)


def test_the_tier_lines_and_uses_of_a_lumped_plan_are_those_of_the_plain_policy(plan, data, monkeypatch):
    plain = {row.title: row for row in build_section(route_input(plan), data).rows}
    monkeypatch.setattr(_plan, "VIEW_FROM_STATES", 10)
    shown = {row.title: row for row in build_section(route_input(plan), data).rows}

    assert set(plain) == set(shown)
    for title, row in plain.items():
        for label in ("Tier chances", "Uses on average", "Step cost"):
            assert [f.lines for f in shown[title].fields if f.label == label] == [f.lines for f in row.fields if f.label == label], title


ROUTE = """\
name: Transmute, alter until the gem, regal, restart
rules:
  - when: {rarity: normal}
    do: Orb of Transmutation
  - when:
      rarity: magic
      requirements:
        - stat: "+1 to Level of all Minion Skill Gems"
          status: passing
    do: Regal Orb
  - when: {rarity: magic}
    do: Orb of Alteration
  - do: restart
"""


def test_a_given_route_read_on_a_packed_plan_is_a_chain_of_item_states_whose_steps_add_up_to_the_risk_mean_and_one_finish(plan, data):
    from crafting_system.cli import evaluate_route, parse_route

    route = parse_route(ROUTE, plan, data, "route.yaml")
    result = evaluate_route(plan, route, data)
    assert result.chain is not None

    flow = flow_of(result.chain, is_restart=lambda action: action.label == "restart")

    assert flow.measured and [step.action.label for step in flow.steps if step.action] == ["Orb of Transmutation", "Orb of Alteration", "Regal Orb", "restart"]
    # the risk run measured the mean on the lumped chain; the steps of the item chain add up to it, and a run finishes once
    assert sum(step.uses * step.cost for step in flow.steps) == pytest.approx(result.risk.mean.value, rel=1e-6)
    assert sum(edge.chance * step.uses for step in flow.steps for edge in step.edges if edge.kind == "goal") == pytest.approx(1.0)


def test_every_item_state_of_the_policy_is_a_row_of_the_chain_and_each_row_is_a_distribution(plan):
    chain = chain_of_packed_policy(plan.policy)

    assert chain.m == len(plan.policy)
    assert np.all(np.diff(chain.ptr) >= 0) and chain.ptr[-1] == len(chain.dst) == len(chain.prob)
    sums = np.add.reduceat(chain.prob, chain.ptr[:-1][np.diff(chain.ptr) > 0])
    assert np.allclose(sums, 1.0, rtol=0, atol=1e-12)
    assert math.isfinite(chain.prob.sum())
