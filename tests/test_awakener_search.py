"""The Awakener's Orb in the one envelope search: its donor searched by the same search and folded into the orb's price (ticket #832, ADR-0022, ADR-0032).

On the small ring pool of `test_abstraction_awakener` (four plain mods, the Crusader and the Shaper mods), a Crusader ring that wants a Crusader
prefix and the Shaper suffix, which only an Awakener's Orb's donor brings:

* the donor's search gives the exact mean of the donor's own graph (every state its offers reach, solved exactly, goal: the want's key);
* the target's search, with the orb priced at its orb and that mean (`_awakener.fold`), gives the exact value of ADR-0022's product (the target
  and its donor's acquisition solved together, `solve_with_donors`), to 1e-9;
* the bound of the whole (`whole_lower`) is at most that value, also when a donor is given a bound below its value;
* the planner offers only the orbs whose donor the target names, and says what it leaves out (OR-13).
"""

import dataclasses

import pytest
from pattern_support import exact_values
from test_abstraction_awakener import CRUS_CURSE, CRUS_P1, CRUS_P2, DATA, LEVEL, PLAIN_P1, RING, SHAP_S1, ring

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.abstraction._pattern import Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import AlchemyOrb, AwakenersOrb, ChaosOrb, Reading, RegalOrb, TransmutationOrb, open_listing
from crafting_system.cli import Offer
from crafting_system.items import Influence, Rarity
from crafting_system.planner._awakener import Donor, donor_abstraction, donor_base_cost, donor_limits, fold, solve_donor, whole_info, whole_lower
from crafting_system.planner._donors import solve_with_donors
from crafting_system.planner._envelope_plan import envelope_limits, envelope_result
from crafting_system.planner._limits import limit_text
from crafting_system.planner._offers import AWAKENER_KIND, RESTART, BuyStartItem, PricedOffer, _with_wanted_donors, donor_wants
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

TOLERANCE = 1e-9
CRUSADER, SHAPER = Influence.CRUSADER, Influence.SHAPER
ORB = AwakenersOrb(RING, LEVEL, SHAPER, SHAP_S1)
RECEIVER = Reading.of({"awakener.group_conflict": "receiver"})  # the reading the plan answers at (`planned`, ADR-0032 as built #832)
GOAL = Goal((Wanted(frozenset({CRUS_P1, CRUS_P2})), Wanted(frozenset({SHAP_S1}))))
START = ring(CRUS_CURSE, PLAIN_P1, influences={CRUSADER})  # no Crusader prefix yet: Chaos Orbs first, and an orb keeps one of two
# the Orb of Alchemy makes a rare donor as a Chaos Orb rerolls one at the same price, so the donor's restart (`donor_base_cost`, which ADR-0022's
# product has not: its acquisition starts from the base once) never pays and the two answers can be compared exactly
PRICES = {"Chaos Orb": (ChaosOrb(), 1.0), "Orb of Alchemy": (AlchemyOrb(), 1.0), "Awakener's Orb": (ORB, 3.0)}
# the planner's kinds (the Orb of Alchemy is not one): a magic donor that missed is cheaper bought again, so the planner's own answer is checked
# against the exact graphs of the donor and of the target with the orb at its folded price
PLANNER_PRICES = {"Chaos Orb": (ChaosOrb(), 1.0), "Orb of Transmutation": (TransmutationOrb(), 0.5), "Regal Orb": (RegalOrb(), 1.0), "Awakener's Orb": (ORB, 3.0)}
RESTART_PRICE = 5.0


def abstraction(prices=PRICES) -> Abstraction:
    return Abstraction(DATA, GOAL, RING, LEVEL, tuple(action for action, _ in prices.values()), reading=RECEIVER, allow_inputs=True)


def priced(prices=PRICES) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in prices.items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(START), {}), RESTART_PRICE, ())]


class _DonorGoal:
    """The donor's graph for `exact_values`: the donor abstraction's kernels, its goal the states with the want's key."""

    def __init__(self, ab: Abstraction, want) -> None:
        self.ab, self.want = ab, want
        self.kernel = ab.kernel

    def is_goal(self, state) -> bool:
        return self.ab.donor_key(state, ORB) == self.want


@pytest.fixture(scope="module")
def solved():
    ab = abstraction()
    offers = priced()
    donor, packed = solve_donor(ab, ORB, offers)
    return ab, offers, donor, packed


def test_the_donor_search_gives_the_exact_mean_of_the_donors_graph(solved):
    ab, offers, donor, packed = solved
    dab = donor_abstraction(ab, ORB)
    (need,) = ORB.inputs(DATA)
    start = dab.compress(need.start)
    want = dab.donor_key(dab.compress(need.want), ORB)
    graph = [PatternOffer(label, action, cost) for label, (action, cost) in PRICES.items() if action is not ORB]
    graph.append(PatternOffer(RESTART, None, donor_base_cost(offers)))  # the donor's restart buys its normal base again
    exact = exact_values(_DonorGoal(dab, want), start, graph)[start]
    assert donor.exact and donor.stopped is None
    assert donor.upper == pytest.approx(exact, rel=TOLERANCE)
    assert donor.lower == donor.upper
    assert packed.info["envelope"].lower <= exact * (1 + TOLERANCE)


def test_the_target_with_the_folded_orb_gives_the_exact_value_of_the_product(solved):
    ab, offers, donor, _ = solved
    start = ab.compress(START)
    product = solve_with_donors(ab, start, offers, reaches=ab.reaches_donor(ORB))
    assert product.solution.error_bound < TOLERANCE
    result = envelope_result(ab, start, fold(offers, [donor]))
    info = result.info["envelope"]
    assert info.exact
    assert result.solution.values[start] == pytest.approx(product.value, rel=TOLERANCE)
    assert whole_lower(info.lower, offers, [donor]) <= product.value * (1 + TOLERANCE)


def test_the_bound_of_the_whole_holds_when_a_donor_is_not_proved(solved):
    """A donor stopped at a gap: the target's bound at the upper donor price, divided by 1 + r, is still below the product's value."""
    ab, offers, donor, _ = solved
    start = ab.compress(START)
    product = solve_with_donors(ab, start, offers, reaches=ab.reaches_donor(ORB)).value
    for share in (0.5, 0.1):  # the donor's bound at a share of its value, its plan at 1.5 times
        loose = dataclasses.replace(donor, lower=donor.upper * share, upper=donor.upper * 1.5, exact=False, stopped="a test's net")
        result = envelope_result(ab, start, fold(offers, [loose]))
        bound = whole_lower(result.info["envelope"].lower, offers, [loose])
        assert bound <= product * (1 + TOLERANCE)
        assert result.solution.values[start] >= product * (1 - TOLERANCE)  # the plan with the dearer donor costs at least the optimum


def test_the_folded_orb_carries_its_donor_as_a_part_and_the_page_says_the_base_is_a_stand_in(solved):
    _, offers, donor, _ = solved
    (orb,) = [p for p in fold(offers, [donor]) if p.offer.action == ORB]
    assert orb.cost == pytest.approx(3.0 + donor.upper)
    assert orb.parts[-1][0] == "second item" and orb.parts[-1][2] == donor.upper
    stand_in = donor_base_cost(offers)
    assert stand_in == pytest.approx(0.1)  # a tenth of the cheapest paid action, the Chaos Orb and the Orb of Alchemy at 1
    (base,) = [limit for limit in donor_limits([donor], stand_in) if limit.what == "A second item's base is a stand-in price"]
    assert "stand-in of 0.10 Chaos" in limit_text(base)  # the page's "leaves out" lines are `limit_text` (`cli._route_view`): it says the figure (OR-13)
    stopped = dataclasses.replace(donor, exact=False, stopped="a test's net", lower=donor.upper / 2)
    assert "A second item's plan is not proved the cheapest" in [limit.what for limit in donor_limits([stopped], stand_in)]


def test_whole_lower_is_the_targets_bound_when_every_donor_is_exact():
    donor = Donor(ORB, 4.0, 4.0, True, None, 3, 0.0)
    assert whole_lower(10.0, priced(), [donor]) == 10.0
    loose = Donor(ORB, 2.0, 4.0, False, "net", 3, 0.0)  # r = (4 - 2) / (3 + 2) = 0.4
    assert whole_lower(10.0, priced(), [loose]) == pytest.approx(10.0 / 1.4)


def test_the_bound_is_a_lower_bound_at_every_state_of_the_targets_exact_graph(solved):
    """The crafted-pattern bound with the orb at its folded price, at every state the target's offers reach (`Reads.influenced`, `input_mods`)."""
    ab, offers, donor, _ = solved
    start = ab.compress(START)
    folded = fold(offers, [donor])
    graph = [PatternOffer(p.label, None if isinstance(p.offer.action, BuyStartItem) else p.offer.action, p.cost) for p in folded]
    exact = exact_values(ab, start, graph)
    model = build_pattern_model(ab, start, graph)
    assert model.stopped is None
    solved_model = solve_packed(pack_pattern_model(model, graph))
    pattern = Pattern(ab, None, [offer.action for offer in graph if offer.action is not None])
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        assert float(solved_model.value[model.index[key]]) <= value * (1 + TOLERANCE) + TOLERANCE, (state, value)


@pytest.mark.parametrize("error", ["OutOfScopeError", "NotApplicableError", "NoPolicy"])
def test_an_orb_whose_donor_cannot_be_planned_is_left_out_and_the_plan_says_why(monkeypatch, error):
    """`solve_donors`' clause (`test_cli_model_gaps.CLAUSES`): a model gap, a game refusal or no policy leaves the orb out with a limit."""
    import crafting_system.actions as actions
    from crafting_system.planner import _awakener, _envelope

    raised = {"OutOfScopeError": actions.OutOfScopeError, "NotApplicableError": actions.NotApplicableError, "NoPolicy": _envelope.NoPolicy}[error]

    def refuse(*_args, **_options):
        raise raised("planted")

    monkeypatch.setattr(_awakener, "solve_donor", refuse)
    offers = priced()
    orbs = [p for p in offers if p.offer.action == ORB]
    donors, left_out = _awakener.solve_donors(abstraction(), orbs, offers)
    assert donors == ()
    (limit,) = left_out
    assert limit.what == "An Awakener's Orb is not offered" and "planted" in limit.why and "Awakener's Orb" in limit.why


def _exact_donor(offers, prices=PRICES) -> float:
    dab = donor_abstraction(abstraction(prices), ORB)
    (need,) = ORB.inputs(DATA)
    start = dab.compress(need.start)
    want = dab.donor_key(dab.compress(need.want), ORB)
    graph = [PatternOffer(label, action, cost) for label, (action, cost) in prices.items() if action is not ORB]
    graph.append(PatternOffer(RESTART, None, donor_base_cost(offers)))
    return exact_values(_DonorGoal(dab, want), start, graph)[start]


def test_a_donor_search_stopped_at_a_gap_keeps_a_bound_below_and_a_plan_above_the_exact_mean():
    offers = priced()
    exact = _exact_donor(offers)
    donor, _ = solve_donor(abstraction(), ORB, offers, gap=0.5, gap_after=0.0)  # stop at the first plan proved within 50%
    assert donor.lower <= exact * (1 + TOLERANCE)
    assert donor.upper >= exact * (1 - TOLERANCE)
    assert donor.upper <= donor.lower * 1.5 * (1 + TOLERANCE) or donor.exact


def test_an_exact_target_beside_a_stopped_donor_is_not_exact_and_says_the_donors_stop(solved):
    ab, offers, donor, _ = solved
    start = ab.compress(START)
    info = envelope_result(ab, start, fold(offers, [donor])).info["envelope"]
    loose = dataclasses.replace(donor, lower=donor.upper / 2, exact=False, stopped="the time limit of 3 seconds was reached")
    found = whole_info(info, offers, [loose])
    assert info.exact and not found.exact
    assert found.lower == pytest.approx(whole_lower(info.lower, offers, [loose])) and found.lower < info.lower
    assert "second item" in found.stopped and "3 seconds" in found.stopped and "None" not in limit_text(envelope_limits(found)[0])
    assert whole_info(info, offers, [donor]) == dataclasses.replace(info, lower=whole_lower(info.lower, offers, [donor]))
    free = dataclasses.replace(loose, lower=0.0)
    assert whole_lower(10.0, [dataclasses.replace(p, cost=0.0) for p in offers], [free]) == 0.0  # a use proved to cost nothing proves nothing


def _ring_target(data) -> str:
    def entry(mod_id):
        return f"    - mod: {mod_id}\n      values: {[min(stat.min, stat.max) for stat in data.mods[mod_id].stats]}\n"

    return (
        f"base: {RING}\nitem_level: {LEVEL}\ninfluence: [crusader]\nactions: [awakeners-orb, chaos-orb, transmutation-orb, regal-orb]\n"
        "requirements:\n- family: ContractRingCrusP\n  min_tier: any\n- family: ContractRingShapS\n  mod: ContractRingShapS1\n"
        f"start_item:\n  rarity: rare\n  mods:\n{entry(CRUS_CURSE)}{entry(PLAIN_P1)}start: bought\n"
    )


def test_the_planners_entry_plans_the_orb_through_the_one_search_at_the_exact_value():
    """`make_plan` on the ring target: the orb is offered (its donor mod is named), the plan is the envelope search's (no reading solve, no
    product), its mean is the exact value of the target's graph with the orb at its cost and the exact mean of the donor's graph, and the page's
    limits say the donor's base and steps."""
    import datetime

    from crafting_system.cli import make_plan
    from crafting_system.prices.price_file import PriceEntry, PriceFile, Provenance
    from crafting_system.targets import parse_target

    from influence_support import INFLUENCE_DATA

    # the bench's crafts that `offers_for` names by their mods (the metamods), which none of the orbs draws
    data = dataclasses.replace(DATA, mods={**DATA.mods, **{k: m for k, m in INFLUENCE_DATA.mods.items() if m.domain == "crafted"}})
    target = parse_target(_ring_target(data), data, source="<ring>")
    entries = {
        name: PriceEntry(cost, "poe.ninja", None, None, Provenance("ninja-exchange", "Test", "2026-11-16", 1.0)) for name, (_, cost) in PLANNER_PRICES.items()
    }
    prices = PriceFile("Test", datetime.datetime(2026, 11, 16, tzinfo=datetime.UTC), 300.0, entries)
    plan = make_plan(data, target, prices, start_price=RESTART_PRICE, with_risk=False)
    ab, offers = abstraction(PLANNER_PRICES), priced(PLANNER_PRICES)
    donor = _exact_donor(offers, PLANNER_PRICES)
    graph = [PatternOffer(label, action, cost + (donor if action is ORB else 0.0)) for label, (action, cost) in PLANNER_PRICES.items()]
    exact = exact_values(ab, ab.compress(START), [*graph, PatternOffer(RESTART, None, RESTART_PRICE)])[ab.compress(START)]
    assert plan.readings is None and plan.donors is None and plan.packed is not None
    assert plan.packed.info["envelope"].exact
    assert plan.solution.values[plan.start] == pytest.approx(exact, rel=TOLERANCE)
    assert any(action.label.startswith("Awakener's Orb with a shaper donor") for action in plan.solution.policy.values())
    said = {limit.what for limit in plan.limits}
    assert {"A second item's base is a stand-in price", "How each second item is made is not shown"} <= said


def test_an_orb_whose_donor_cannot_be_read_is_kept_and_its_search_leaves_it_out_and_says_why():
    """`donor_wants`' clause (`test_cli_model_gaps.CLAUSES`): an orb whose donor mod is no influence mod of its influence names no donor; the
    offers keep it, and its donor's search leaves it out with the limit that says why (OR-13), never an error of the whole plan."""
    from crafting_system.planner import _awakener

    bad = AwakenersOrb(RING, LEVEL, SHAPER, PLAIN_P1)  # a plain mod: no Shaper donor holds it as its influence mod
    assert donor_wants(DATA, bad) is None
    assert donor_wants(DATA, ORB)[1] == frozenset({SHAP_S1})
    kept = _with_wanted_donors(DATA, START, None, frozenset(), {CRUS_P1, CRUS_P2, SHAP_S1}, {bad: AWAKENER_KIND, ORB: AWAKENER_KIND})
    assert bad in kept and ORB in kept
    offers = [*priced(), PricedOffer(Offer("Awakener's Orb [plain]", bad, {"Awakener's Orb": 1}, kind=AWAKENER_KIND), 3.0, ())]
    donors, left_out = _awakener.solve_donors(abstraction(), offers[-1:], offers)
    assert donors == ()
    (limit,) = left_out
    assert limit.what == "An Awakener's Orb is not offered"


def test_a_donor_is_offered_the_target_s_actions_but_not_its_restart_its_listing_draw_or_an_orb():
    """`_applies_to_donors`: the donor buys its own base, a bought listing is the target's alone (ADR-0064), and a donor never takes an orb."""
    from crafting_system.planner._awakener import _applies_to_donors

    listing = open_listing(Rarity.RARE)
    offers = {
        "Orb of Transmutation": (TransmutationOrb(), True),
        "Chaos Orb": (ChaosOrb(), True),
        "Awakener's Orb": (ORB, False),
        RESTART: (BuyStartItem(START), False),
        "the listing": (listing, False),
    }
    for label, (action, applies) in offers.items():
        assert _applies_to_donors(PricedOffer(Offer(label, action, {}), 1.0, ())) is applies, label
