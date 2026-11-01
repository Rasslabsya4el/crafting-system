"""The CLI side of the variants level (ticket #172, ADR-0023): the spread ladder, the refusal, the pilot limit, the block model.

The fixture is the one of `test_abstraction_variants.py`: the small amulet pool with a goal of a Lightning resistance and
life, the three additions and Annulment, and the weights that make its pools unequal (Gem 600 and Lightning damage 1000
among the prefixes, Cold and Fire resistance 1000 each as one family type and Mana Leech 2000 among the suffixes). The
end-to-end queries add a Chaos Orb at 6 Chaos, which makes the additions worth using but not the only way: the exact
plan is the oracle and the rates are injected, so no test reads a clock or asserts a time (ADR-0014).

On this fixture a spread of 1000 pools both sides and its certified gap is about 2%; a spread of 500 pools only the
prefixes and the gap is under 1%. So the shipped ladder climbs from the first rung to the second, and a ladder cut to
the first rung alone gives the narrowest interval with the message of #127. The numbers are of the committed data and
are asserted only as the side of the 1% line that they fall on.
"""

import dataclasses
import datetime
import functools
import json

import pytest
from abstraction_pool import COLD_RESIST, LIFE_1, MANA_1, RESIST_2
from coarse_support import CHAOS, CRAFTS, DATA, REMOVE, abstraction, item, roll
from test_abstraction_variants import ADDITIONS, ANNUL, TYPED, block_of

from crafting_system.abstraction import Abstraction, Coarsening
from crafting_system.actions import AnnulmentOrb, Reads, RegalOrb
from crafting_system.cli import Offer, PlanError, build_report, make_plan, policy_document, render_text
from crafting_system.cli import _decide
from crafting_system.cli._approx import BlockModel, climb, shown_policy, solve_level
from crafting_system.cli._decide import LADDER, SPREAD_LADDER, Candidate, Decision, Level, Rates, coarse_refusal, decide, ladder_for
from crafting_system.cli._offers import PricedOffer
from crafting_system.items import Rarity
from crafting_system.prices import PriceFile
from crafting_system.solver import Action, Outcome, VariantAction
from crafting_system.targets import parse_target

CH = "Chaos Orb"
PRICES = PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {})
RATES = Rates(1.0, 1.0)  # one second a kernel outcome and a solved edge: the forecast is a count
EPSILON = 1e-9


def target_text(rarity: str) -> str:
    return f"""\
base: Paua Amulet
item_level: 84
requirements:
  - family: LightningResistance
  - family: IncreasedLife
start_item:
  rarity: {rarity}
  mods:
    - mod: {MANA_1}
      tier: 1
      values: {[min(stat.min, stat.max) for stat in DATA.mods[MANA_1].stats]}
"""


def additions(*extra: Offer) -> list[Offer]:
    return [
        Offer("Augmentation Orb", ADDITIONS[0], {CH: 1}),
        Offer("Regal Orb", ADDITIONS[1], {CH: 2}),
        Offer("Exalted Orb", ADDITIONS[2], {CH: 3}),
        Offer("Annulment Orb", ANNUL, {CH: 4}),
        *extra,
    ]


WORLDS = {  # name -> (start item rarity, offers)
    "additions_with_chaos": ("rare", additions(Offer("Chaos Orb", CHAOS, {CH: 6}))),
    "additions_only": ("magic", additions()),
}
MAIN = "additions_with_chaos"


@functools.cache
def exact_plan(name: str):
    rarity, offers = WORLDS[name]
    return make_plan(DATA, parse_target(target_text(rarity), DATA, source="t.yaml"), PRICES, offers=offers, start_price=0.0)


def actions_of(name: str):
    return [offer.action for offer in WORLDS[name][1]]


def priced(offers) -> tuple[PricedOffer, ...]:
    return tuple(PricedOffer(offer, float(sum(offer.resources.values())), ()) for offer in offers)


def spread_level(spread) -> Level:
    return Level("spread", spread, f"junk pooled by weight, spread {spread}")


@pytest.fixture(scope="module")
def exact():
    return exact_plan(MAIN)


@pytest.fixture(scope="module")
def rung_seconds(exact):
    """The forecast seconds of the exact run and of each shipped rung, at the injected rates."""
    forecast = exact.abstraction.estimate([exact.start], actions_of(MAIN))
    rungs = {
        level.size: forecast.coarsened(Coarsening.pooling_by_spread(exact.abstraction, level.size, exact.start)).seconds(1.0, 1.0)
        for level in SPREAD_LADDER
    }
    return forecast.seconds(1.0, 1.0), rungs


@pytest.fixture(scope="module")
def budget(rung_seconds):
    """Over the forecast of both rungs, under that of the exact run."""
    whole, rungs = rung_seconds
    assert max(rungs.values()) < whole
    return (whole + max(rungs.values())) / 2


@pytest.fixture(scope="module")
def approximate(budget):
    rarity, offers = WORLDS[MAIN]
    return make_plan(DATA, parse_target(target_text(rarity), DATA, source="t.yaml"), PRICES, offers=offers, start_price=0.0, budget=budget, rates=RATES)


# --- 1. the ladder follows the declarations ----------------------------------------------------------------------------


def test_the_ladder_of_a_query_with_an_addition_is_by_weight_spread_and_starts_at_1000_then_500():
    assert [level.size for level in SPREAD_LADDER] == [1000, 500]
    assert all(level.kind == "spread" for level in SPREAD_LADDER) and not any(level.kind == "spread" for level in LADDER)
    assert len({level.name for level in (*LADDER, *SPREAD_LADDER)}) == len(LADDER) + len(SPREAD_LADDER)


@pytest.mark.parametrize("addition", ADDITIONS, ids=lambda action: type(action).__name__)
def test_an_offered_addition_that_declares_variants_gives_the_spread_ladder(addition):
    assert addition.reads(DATA).variants
    assert ladder_for(TYPED, [addition]) is SPREAD_LADDER
    assert ladder_for(TYPED, [CHAOS, ANNUL, addition]) is SPREAD_LADDER  # one addition among the others is enough


def test_rerolls_crafts_remove_crafted_mods_and_annulment_alone_give_the_family_group_ladder():
    assert ladder_for(TYPED, [CHAOS]) is LADDER
    assert ladder_for(TYPED, list(CRAFTS)) is LADDER
    assert ladder_for(TYPED, [REMOVE]) is LADDER
    assert ladder_for(TYPED, [ANNUL]) is LADDER
    assert ladder_for(TYPED, [CHAOS, *CRAFTS, REMOVE, ANNUL]) is LADDER
    assert ladder_for(TYPED, []) is LADDER


def test_the_ladder_is_read_when_it_is_asked_so_a_replaced_one_is_the_one_used(monkeypatch):
    mine = (spread_level(123),)
    monkeypatch.setattr(_decide, "SPREAD_LADDER", mine)

    assert ladder_for(TYPED, [ADDITIONS[0]]) is mine
    assert ladder_for(TYPED, [CHAOS]) is LADDER


# --- 2. the refusal ----------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class UndeclaredRegal(RegalOrb):
    """An addition that declares neither block invariance nor variants."""

    def reads(self, data) -> Reads:
        return Reads.adding()


@dataclasses.dataclass(frozen=True)
class UndeclaredAnnulment(AnnulmentOrb):
    """An Annulment that declares nothing."""

    def reads(self, data) -> Reads:
        return Reads()


def test_annulment_and_the_three_additions_have_a_coarse_level_and_an_action_with_no_declaration_still_names_itself():
    assert coarse_refusal(TYPED, [ANNUL, *ADDITIONS]) is None
    assert coarse_refusal(TYPED, [CHAOS, ANNUL, *ADDITIONS]) is None

    regal = coarse_refusal(TYPED, [ANNUL, ADDITIONS[0], UndeclaredRegal()])
    annulment = coarse_refusal(TYPED, [UndeclaredAnnulment(), *ADDITIONS])
    assert regal is not None and regal.startswith("Regal Orb is not declared block-invariant and declares no variants")
    assert annulment is not None and annulment.startswith("Orb of Annulment is not declared block-invariant and declares no variants")


def with_undeclared(exact):
    """The abstraction and the priced offers of the main query with the Regal Orb replaced by one that declares nothing."""
    offers = [Offer("Regal Orb", UndeclaredRegal(), {CH: 2}) if offer.label == "Regal Orb" else offer for offer in WORLDS[MAIN][1]]
    ab = Abstraction(DATA, exact.abstraction.goal, exact.abstraction.base_id, exact.abstraction.item_level, [offer.action for offer in offers])
    return offers, ab, ab.compress(exact.target.start_item)


def test_a_query_over_the_budget_with_an_undeclared_action_is_exact_when_small_and_says_why(exact):
    offers, ab, start = with_undeclared(exact)

    decision = decide(ab, start, priced(offers), 0.0, RATES)

    assert decision.action == "exact" and decision.levels == ()
    assert decision.message.startswith("no approximate level available (Regal Orb is not declared block-invariant")


def test_a_query_over_the_budget_with_an_undeclared_action_is_refused_when_the_exact_run_is_beyond_what_was_run(exact, monkeypatch):
    offers, ab, start = with_undeclared(exact)
    monkeypatch.setattr(_decide, "EXACT_TRANSITIONS", 100)

    decision = decide(ab, start, priced(offers), 0.0, RATES)
    assert decision.action == "refused" and "no approximate level available (Regal Orb is not declared block-invariant" in decision.message

    with pytest.raises(PlanError, match=r"no approximate level available \(Regal Orb is not declared block-invariant"):
        make_plan(DATA, exact.target, PRICES, offers=offers, start_price=0.0, budget=0.0, rates=RATES)


# --- 3. decide on a query with additions -------------------------------------------------------------------------------


def test_over_the_budget_the_decision_is_approximate_and_its_levels_are_the_spread_rungs(exact, budget):
    decision = decide(exact.abstraction, exact.start, exact.offers, budget, RATES)

    assert decision.action == "approximate" and decision.message == ""
    assert [found.level for found in decision.levels] == list(SPREAD_LADDER)  # the two rungs pool different families
    for found in decision.levels:
        assert found.coarsening is not None and found.coarsening.groups  # a rung that pools something
        assert found.estimate is not None and found.estimate.states < decision.estimate.states
    assert decision.estimate.walked and decision.estimate.complete


def test_a_rung_whose_own_forecast_does_not_fit_the_budget_is_left_out(exact, rung_seconds):
    _, rungs = rung_seconds
    between = (rungs[1000] + rungs[500]) / 2
    assert rungs[1000] < between < rungs[500]

    decision = decide(exact.abstraction, exact.start, exact.offers, between, RATES)

    assert decision.action == "approximate" and [found.level for found in decision.levels] == [SPREAD_LADDER[0]]


def test_the_rungs_are_the_ones_of_the_ladder_as_it_is_when_decide_runs_and_a_rung_that_cuts_nothing_new_is_dropped(exact, budget, monkeypatch):
    first, same, wide = spread_level(400), spread_level(500), spread_level(1500)  # 400 and 500 pool the prefixes only, 1500 both sides
    monkeypatch.setattr(_decide, "SPREAD_LADDER", (first, same, wide))

    decision = decide(exact.abstraction, exact.start, exact.offers, budget, RATES)

    assert decision.action == "approximate" and [found.level for found in decision.levels] == [first, wide]
    assert len({found.coarsening.groups for found in decision.levels}) == 2


def test_a_budget_above_the_forecast_is_exact(exact, rung_seconds):
    whole, _ = rung_seconds

    for budget in (whole, 1e12):
        decision = decide(exact.abstraction, exact.start, exact.offers, budget, RATES)
        assert decision.action == "exact" and decision.levels == () and decision.message == ""
        assert decision.transitions == exact.abstraction.estimate([exact.start], actions_of(MAIN)).transitions


def test_with_the_pilot_walk_cut_short_the_levels_have_no_forecast_and_are_still_offered(exact, monkeypatch):
    monkeypatch.setattr(_decide, "ADDING_LIMIT", 10)

    decision = decide(exact.abstraction, exact.start, exact.offers, 10.0, RATES)

    assert decision.estimate is not None and not decision.estimate.complete
    assert decision.action == "approximate" and [found.level for found in decision.levels] == list(SPREAD_LADDER)
    assert all(found.estimate is None and found.coarsening is not None for found in decision.levels)


def test_a_count_cut_short_is_never_taken_for_a_small_exact_graph_even_when_it_fits_the_budget(exact, monkeypatch):
    monkeypatch.setattr(_decide, "ADDING_LIMIT", 10)

    decision = decide(exact.abstraction, exact.start, exact.offers, 1e12, RATES)

    # the count is a lower bound: the exact run is not taken for small, the levels are tried without a forecast
    assert decision.action == "approximate" and all(found.estimate is None for found in decision.levels)


def test_only_a_query_with_a_walked_action_takes_the_smaller_pilot_limit(monkeypatch):
    ab = abstraction()
    start = ab.compress(item(roll(MANA_1)))
    offers = priced([Offer("Chaos Orb", CHAOS, {CH: 1}), *(Offer(f"Craft {c.mod_id}", c, {CH: 2}) for c in CRAFTS), Offer("Remove Crafted Mods", REMOVE, {CH: 1})])
    monkeypatch.setattr(_decide, "ADDING_LIMIT", 10)

    decision = decide(ab, start, offers, 1e12, RATES)

    assert decision.action == "exact" and decision.estimate.complete and decision.estimate.states > 10  # the limit of 10 did not apply


# --- 4. end to end -----------------------------------------------------------------------------------------------------


def test_over_the_budget_the_shipped_ladder_climbs_to_the_rung_that_reaches_one_percent_and_brackets_the_exact_mean(exact, approximate):
    found = approximate.approximation

    assert found is not None and found.level == SPREAD_LADDER[1].name  # the first rung is wider than 1% on this query
    assert found.lower <= exact.mean_remaining <= found.upper
    assert found.gap <= found.tolerance == 0.01 and found.within_tolerance and found.message == ""
    assert approximate.mean_remaining == found.upper  # the policy shown costs the upper bound
    assert approximate.risk is None and approximate.risk_seconds == 0.0
    assert found.blocks < len(exact.solution.values)
    assert approximate.start in approximate.policy and not approximate.is_goal(approximate.start)


def test_the_first_rung_alone_is_wider_than_one_percent_on_this_query(approximate, exact):
    decision = Decision("approximate", (Candidate(SPREAD_LADDER[0], None, Coarsening.pooling_by_spread(exact.abstraction, 1000, exact.start)),), transitions=3136)

    found = climb(decision, exact.start, exact.offers).approximation

    assert found.gap > 0.01 and not found.within_tolerance
    assert found.lower <= exact.mean_remaining <= found.upper  # still certified


def test_the_text_marks_the_answer_with_the_level_and_gives_no_risk_numbers(approximate):
    text = render_text(build_report(approximate, DATA))
    head = text.partition("\nRequirements:")[0]

    assert head.startswith("Answer: approximate (certified within ") and " of the exact mean)" in head
    assert f"Level: {SPREAD_LADDER[1].name};" in head
    assert "Blocks solved: " in text
    assert "  success, p50, p90, CVaR  not given for an approximate answer" in text
    assert "p90   " not in text and "success chance" not in text


def test_the_json_holds_the_interval_the_gap_the_level_and_the_blocks_and_no_risk_numbers(approximate, exact):
    document = policy_document(build_report(approximate, DATA))

    answer = document["answer"]
    assert {"approximate", "lower", "upper", "gap", "level", "blocks"} <= set(answer)
    assert answer["approximate"] is True and answer["level"] == SPREAD_LADDER[1].name
    assert answer["lower"] <= exact.mean_remaining <= answer["upper"]
    assert answer["gap"] == approximate.approximation.gap <= 0.01 and answer["within_tolerance"] is True
    assert answer["blocks"] == approximate.approximation.blocks > 0
    assert set(document["totals"]) == {"mean_cost", "mean_cost_divine", "mean_cost_without_start", "solver_error_bound"}  # no p90, no CVaR
    json.dumps(document, allow_nan=False)


@pytest.mark.parametrize("spread, reaches", [(400, True), (500, True), (1000, False)])
def test_a_ladder_of_one_rung_gives_a_gap_within_one_percent_or_the_narrowest_interval_with_the_message(exact, budget, monkeypatch, spread, reaches):
    level = spread_level(spread)
    monkeypatch.setattr(_decide, "SPREAD_LADDER", (level,))
    rarity, offers = WORLDS[MAIN]

    plan = make_plan(DATA, exact.target, PRICES, offers=offers, start_price=0.0, budget=budget, rates=RATES)

    found = plan.approximation
    assert found is not None and found.level == level.name
    assert found.lower <= exact.mean_remaining <= found.upper
    assert plan.mean_remaining == found.upper and plan.risk is None
    assert found.within_tolerance is reaches
    text = render_text(build_report(plan, DATA))
    answer = policy_document(build_report(plan, DATA))["answer"]
    assert answer["approximate"] is True and answer["level"] == level.name and answer["within_tolerance"] is reaches
    if reaches:
        assert found.gap <= 0.01 and found.message == "" and answer["message"] == ""
        assert "Answer: approximate (certified within " in text
    else:
        assert found.gap > 0.01
        assert found.message.startswith(f"No level reaches 1%: the narrowest certified interval has a gap of {found.gap:.2%} ")
        assert "run again with --exact (3,136 transitions" in found.message
        assert answer["message"] == found.message
        assert "Answer: approximate (the certified gap is " in text and "above the 1% tolerance" in text


# --- 5. the block model ------------------------------------------------------------------------------------------------


def pair(coarsening, block, offers, shared=None):
    shared = {} if shared is None else shared
    return BlockModel(coarsening, block, offers, "lower", shared), BlockModel(coarsening, block, offers, "upper", shared), shared


def offers_of(*actions) -> tuple[PricedOffer, ...]:
    return priced([Offer(action.label(DATA), action, {CH: 1}) for action in actions])


def by_label(actions) -> dict:
    return {action.label: action for action in actions}


POOLING = Coarsening.pooling_by_spread(TYPED, 1000)
EVERY = (*ADDITIONS, ANNUL)


def test_a_block_with_several_variants_offers_a_variant_action_and_an_invariant_action_a_plain_one():
    block = block_of(TYPED, POOLING, roll(COLD_RESIST), roll(LIFE_1))  # one pooled suffix slot: a light and a heavy variant of the Exalted Orb
    lower, upper, _ = pair(POOLING, block, offers_of(*EVERY))

    for model in (lower, upper):
        found = by_label(model.actions(block))
        assert set(found) == {"Exalted Orb", "Orb of Annulment"}  # a rare item takes neither a Regal nor an Augmentation
        assert isinstance(found["Exalted Orb"], VariantAction) and len(found["Exalted Orb"].variants) == 2
        assert type(found["Orb of Annulment"]) is Action and found["Orb of Annulment"].outcomes
        assert found["Exalted Orb"].cost == 1.0


def test_a_block_with_one_variant_gives_a_plain_action_even_for_an_addition():
    block = block_of(TYPED, POOLING, roll(LIFE_1), roll(RESIST_2))  # no pooled slot held: one kernel
    lower, _, _ = pair(POOLING, block, offers_of(*EVERY))

    found = by_label(lower.actions(block))

    assert type(found["Exalted Orb"]) is Action


def test_the_variants_of_the_lower_and_the_upper_model_are_the_same_set_where_every_member_can_take_the_action():
    block = block_of(TYPED, POOLING, roll(COLD_RESIST), roll(LIFE_1))
    lower, upper, _ = pair(POOLING, block, offers_of(*EVERY))

    low, high = by_label(lower.actions(block)), by_label(upper.actions(block))

    assert set(low["Exalted Orb"].variants) == set(high["Exalted Orb"].variants)
    assert low["Orb of Annulment"] == high["Orb of Annulment"]


def test_on_every_reached_block_the_upper_model_offers_a_subset_of_the_actions_of_the_lower_one_with_the_same_variants():
    start = POOLING.coarsen(TYPED.compress(item(roll(MANA_1), rarity=Rarity.MAGIC)))
    reached = POOLING.reachable([start], EVERY, "lower", stop_at_goal=True)
    offers = offers_of(*EVERY)
    several = 0

    for block in reached:
        lower, upper, _ = pair(POOLING, block, offers)
        low, high = by_label(lower.actions(block)), by_label(upper.actions(block))
        assert set(high) <= set(low)
        for label, action in high.items():
            if isinstance(action, VariantAction):
                assert set(action.variants) == set(low[label].variants)
                several += 1
            else:
                assert action == low[label]
    assert len(reached) > 20 and several > 0


@pytest.mark.parametrize("first", ["lower", "upper"])
def test_both_sides_of_a_pair_share_their_computation_of_the_kernels_of_a_block(monkeypatch, first):
    block = block_of(TYPED, POOLING, roll(COLD_RESIST), roll(LIFE_1))
    variants_calls, kernel_calls = [], []
    real_variants, real_kernel = POOLING.variants, TYPED.kernel

    def counted_variants(found_block, action, bound):
        variants_calls.append((found_block, action, bound))
        return real_variants(found_block, action, bound)

    def counted_kernel(state, action):
        kernel_calls.append((state, action))
        return real_kernel(state, action)

    monkeypatch.setattr(POOLING, "variants", counted_variants)
    monkeypatch.setattr(TYPED, "kernel", counted_kernel)
    models = dict(zip(("lower", "upper"), pair(POOLING, block, offers_of(*EVERY))[:2]))
    shared = models["lower"].shared
    assert variants_calls == [] and kernel_calls == []  # building the models computes nothing

    models[first].actions(block)
    once = (len(variants_calls), len(kernel_calls))
    models["upper" if first == "lower" else "lower"].actions(block)

    assert once[0] == 2 * len(EVERY) and once[1] > 0  # each action once for each side, in the pass of the first side
    assert (len(variants_calls), len(kernel_calls)) == once  # the second side computes nothing
    assert {bound for _, _, bound in variants_calls} == {"lower", "upper"} and shared == {}
    assert len({(found_block, action, bound) for found_block, action, bound in variants_calls}) == len(variants_calls)


# --- 6. the policy shown ------------------------------------------------------------------------------------------------


def test_shown_policy_replaces_a_variant_action_by_the_plain_action_of_its_dearest_variant_and_leaves_plain_actions_alone():
    light = (Outcome("a", 1), Outcome("b", 1))  # (1 + 5) / 2 = 3
    heavy = (Outcome("b", 3), Outcome("a", 1))  # (15 + 1) / 4 = 4
    lightest = (Outcome("a", 1),)  # 1
    variant = VariantAction("add", 2.5, (light, heavy, lightest))
    plain = Action("reroll", 1.0, (Outcome("a", 1), Outcome("b", 2)))
    values = {"a": 1.0, "b": 5.0, "c": 0.0}

    shown = shown_policy({"s": variant, "t": plain}, values)

    assert shown["s"] == Action("add", 2.5, heavy) and type(shown["s"]) is Action
    assert shown["t"] is plain
    assert all(hasattr(action, "outcomes") for action in shown.values())


def test_the_variant_shown_changes_with_the_values_it_is_judged_by():
    variant = VariantAction("add", 1.0, ((Outcome("a", 1),), (Outcome("b", 1),)))

    assert shown_policy({"s": variant}, {"a": 1.0, "b": 2.0})["s"].outcomes == (Outcome("b", 1),)
    assert shown_policy({"s": variant}, {"a": 2.0, "b": 1.0})["s"].outcomes == (Outcome("a", 1),)


def test_a_solved_level_shows_for_each_addition_of_its_policy_the_variant_that_is_dearest_under_its_values(exact):
    pooling = Coarsening.pooling_by_spread(exact.abstraction, 500, exact.start)
    solved = solve_level(Candidate(spread_level(500), None, pooling), exact.start, exact.offers)
    policy, values = solved.solution.policy, solved.solution.values
    checked = 0

    assert policy and all(not isinstance(action, VariantAction) and hasattr(action, "outcomes") for action in policy.values())
    for block, shown in policy.items():
        for offered in BlockModel(pooling, solved.start, exact.offers, "upper").actions(block):
            if offered.label == shown.label and isinstance(offered, VariantAction):
                dearest = max(sum(o.weight * values[o.state] for o in variant) / sum(o.weight for o in variant) for variant in offered.variants)
                assert sum(o.weight * values[o.state] for o in shown.outcomes) / sum(o.weight for o in shown.outcomes) == pytest.approx(dearest)
                assert shown.outcomes in offered.variants
                checked += 1
    assert checked > 0  # the policy uses an addition on a block with several variants


# --- 7. the bounds are certified ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", WORLDS)
@pytest.mark.parametrize("spread", [400, 500, 1000, 1500, 100_000])
def test_for_every_spread_the_lower_bound_is_under_the_exact_mean_and_the_upper_one_over_it(name, spread):
    plan = exact_plan(name)
    pooling = Coarsening.pooling_by_spread(plan.abstraction, spread, plan.start)
    assert pooling.groups  # the spread pools something on this fixture

    found = solve_level(Candidate(spread_level(spread), None, pooling), plan.start, plan.offers).approximation

    assert found.lower - EPSILON <= plan.mean_remaining <= found.upper + EPSILON
    assert found.gap >= 0 and found.blocks <= len(plan.solution.values)
