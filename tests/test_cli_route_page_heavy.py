"""The real pages of R04 and R14 say what the item states do (ticket #466, issue #492; OR-18, OR-20, OR-31).

The plans are R04's 177,242 walked states and R14's 816,153 (minutes to half an hour, 6 to 10 GB), so these tests run in a heavy run, not in
a CI shard or on a PC:

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 1 --long --timeout-minutes 120 \
        --command 'CRAFTING_ROUTES=R14 CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider -s tests/test_cli_route_page_heavy.py'

(`CRAFTING_ROUTES` is `R04`, `R14` or both.) Without `CRAFTING_HEAVY` they skip, and without the cached dump they skip too.

Both pages are shown from the lumped chain of the optimal policy, one shown member per block. The steps are made from the item states of
the policy (`_route_chain`), so what a page says of an item is a fact about items: an orb that only adds a mod loses none (the lines the
lumped view printed after R04's Remove Crafted Mods and R14's Augmentation), and the tier chances of R04's Exalted Orb are those of the
published odds (13% and 20%, `tests/test_cli_r04_r14_real.py`) on the guide's two states.
"""

import os
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from route_view_support import alike_key

from crafting_system.cli import make_plan
from crafting_system.cli._benchmark import BENCHMARKS
from crafting_system.cli._benchmark_outcomes import item_of, published_outcomes
from crafting_system.cli._route_chain import chain_of_packed_policy
from crafting_system.cli._route_flow import flow_of
from crafting_system.cli._route_tiers import tier_lines
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGETS = {"R04": "r04-penetrating-quiver", "R14": "r14-hunter-bow"}
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")
ADDING = {"Orb of Transmutation", "Orb of Augmentation", "Regal Orb", "Exalted Orb", "Orb of Alchemy"}  # orbs that put a mod on an item and take none off


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=os.environ.get("CRAFTING_ROUTES", "R04,R14").split(","))
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def plan(data, route_id):
    return make_plan(data, load_target(ROOT / "examples" / "targets" / f"{TARGETS[route_id]}.yaml", data), load_price_file(PRICES))


@pytest.fixture(scope="module")
def section(plan, data):
    return build_section(route_input(plan), data)  # how long it takes is measured by `.github/scripts/page_size.py`, not by a test


@HEAVY
def test_the_plan_is_shown_by_its_lumped_chain_and_the_page_is_made_from_item_states(plan, section):
    assert plan.lumped and len(plan.policy) > len(plan.view_policy)
    chain = chain_of_packed_policy(plan.policy)
    assert chain.m == len(plan.policy)  # every item state of the policy is a row of the chain
    assert sum(len(step.states) for step in flow_of(chain).steps) == chain.m


@HEAVY
def test_the_page_of_a_big_plan_says_in_a_limit_that_the_share_of_runs_entering_a_step_is_left_out(plan, data):
    from crafting_system.cli._limits import STEPS
    from crafting_system.cli._route_flow import ENTRY_STATES, flow_limits

    chain = chain_of_packed_policy(plan.policy)

    steps = [limit for limit in plan.limits if limit.kind == STEPS]

    assert chain.m > ENTRY_STATES  # R04's policy has 18,696 item states, R14's 87,251
    assert [limit.what for limit in steps] == ["How often a run enters a step is not shown"]  # solved, so only this one
    assert steps == list(flow_limits(chain))
    assert "What the steps show" in [field.label for field in build_section(route_input(plan), data).goal.leaves_out]


@HEAVY
def test_an_orb_that_only_adds_a_mod_never_loses_a_wanted_mod_on_the_page(section):
    rows = [row for row in section.rows if row.title in ADDING]
    assert rows
    for row in rows:
        for field in row.fields:
            if field.label == "On failure":
                assert not any(" lost" in line.text for line in field.lines), (row.title, [line.text for line in field.lines])


@HEAVY
def test_no_step_prints_two_lines_that_read_alike(section):
    for row in section.rows:
        for field in row.fields:
            if field.label in ("Chance per use", "On failure"):
                texts = [alike_key(line.text) for line in field.lines]
                assert len(texts) == len(set(texts)), (row.title, texts)


@HEAVY
def test_the_visits_of_the_item_states_are_solved_and_add_up_to_the_mean_cost_of_the_plan(plan):
    flow = flow_of(chain_of_packed_policy(plan.policy))

    assert flow.measured  # solved to a residual of 1e-9; otherwise a `Limit` says so (`flow_limits`) and each step it applies to
    total = sum(step.uses * step.cost for step in flow.steps if step.uses is not None)
    assert total == pytest.approx(plan.mean_remaining, rel=1e-6)  # the same mean the solver certified, from the sparse solve of the visits


@HEAVY
def test_the_tier_chances_of_the_exalted_orb_are_the_published_odds_on_the_guides_two_states(plan, data, route_id):
    if route_id != "R04":
        pytest.skip("the published Exalted Orb odds with a top tier of each family are R04's")
    bench = next(each for each in BENCHMARKS if each.id == "R04")
    target = load_target(ROOT / bench.target, data)
    found = published_outcomes(data, target, bench.outcomes)
    exalted = next(priced for priced in plan.offers if priced.label == "Exalted Orb").offer.action
    first = plan.abstraction.compress(item_of(data, target, bench.outcomes[1]))
    second = plan.abstraction.compress(item_of(data, target, bench.outcomes[3]))

    a = {line.text: line for line in tier_lines(plan.abstraction, exalted, [first], [1.0])}
    b = {line.text: line for line in tier_lines(plan.abstraction, exalted, [second], [1.0])}

    def top(line) -> float:
        return next(share.chance for share in line.tiers if share.wanted)

    life, bow = "+# to maximum Life", "#% increased Damage with Bow Skills"
    assert top(a[life]) + top(a[bow]) == pytest.approx(found[2]["share"])  # 13%: 2 in 15
    assert top(b[bow]) == pytest.approx(found[4]["share"])  # 20%: 1 in 5


@HEAVY
def test_the_exalted_step_of_the_page_is_the_visit_weighted_mixture_of_its_item_states(plan, data, route_id):
    chain = chain_of_packed_policy(plan.policy)
    flow = flow_of(chain)
    steps = [step for step in flow.steps if step.action is not None and step.action.label == "Exalted Orb"]
    if not steps:
        pytest.skip("the optimal policy of this route takes no Exalted Orb")
    (step,) = steps
    exalted = plan.offer_of(step.action).offer.action
    ab = plan.abstraction

    mixed = {line.text: line for line in tier_lines(ab, exalted, step.states, step.weights)}

    total = sum(step.weights)
    apart = []  # each state alone, apart from the mixture: {family text: {tier: chance}}
    for state in step.states:
        apart.append({each.text: {s.tier: s.chance for s in each.tiers} for each in tier_lines(ab, exalted, [state], [1.0])})
    for text, line in mixed.items():
        for share in line.tiers:
            weighted = sum(weight * single.get(text, {}).get(share.tier, 0.0) for weight, single in zip(step.weights, apart))
            assert share.chance == pytest.approx(weighted / total, rel=1e-9, abs=1e-12), (text, share.tier)
