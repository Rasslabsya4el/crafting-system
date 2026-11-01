"""Golden route pages of B2 (ticket #143): an approximate input (a Conflict stand-in) and an unveil offer.

No shipped claim is marked yet and the Orb of Conflict is not built (tickets of batch B2), so the first page
uses a stand-in Chaos Orb named after the Orb of Conflict whose claim carries the mark; `toy_plan` of
`test_cli_approximate_inputs` makes the plan. The second page is the start item of a route: a belt with a veiled
placeholder, the offer drawn for it, a catalyst quality and an Eldritch implicit, on the hand-made extended data.
"""

import dataclasses

import pytest
from implicits_support import BELT, implicit, placeholder
from items_support import DATA
from targets_implicits_support import TEXTED
from route_view_support import assert_golden
from test_cli_approximate_inputs import RULES, make_rule, toy_plan

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.actions import ChaosOrb
from crafting_system.cli import Offer, _marking, price_offers
from crafting_system.cli._plan import Plan, StartPrice, leaf_labels, offer_action
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.items import CatalystType, Item, Quality, Rarity
from crafting_system.prices import CHAOS_ORB
from crafting_system.risk import evaluate
from crafting_system.solver import Solution
from crafting_system.targets import ImplicitRequirement, QualityRequirement, Requirement, Target

CONFLICT_ODDS = make_rule(
    "conflict.odds",
    approximate=True,
    approximate_reason="the odds are a fit to a sample of 525 uses; no other source gives them",
)


@dataclasses.dataclass(frozen=True)
class ConflictStandIn(ChaosOrb):
    """A Chaos Orb that stands in for the Orb of Conflict: it reads the one marked claim."""

    def label(self, data=None) -> str:  # noqa: ANN001
        return "Orb of Conflict (stand-in)"

    def claims(self, data=None) -> frozenset[str]:  # noqa: ANN001
        return frozenset({CONFLICT_ODDS.id})


@pytest.fixture
def conflict_registry(monkeypatch):
    monkeypatch.setattr(_marking, "rule_by_id", {**RULES, CONFLICT_ODDS.id: CONFLICT_ODDS}.__getitem__)


def test_golden_a_route_whose_action_reads_an_approximate_claim_names_it_on_the_goal_card(conflict_registry):
    offers = (Offer("Orb of Conflict (stand-in)", ConflictStandIn(), {CHAOS_ORB: 1}),)
    plan = toy_plan("Orb of Conflict (stand-in)", offers)
    html = render_page(Page("Test page", (build_section(route_input(plan), DATA, anchor="policy"),)))

    assert "Approximate inputs" in html
    assert "conflict.odds: the odds are a fit to a sample of 525 uses" in html
    assert_golden("approximate_conflict", html)


UNVEIL_TEXTS = {
    "UnveiledPrefixLife1": "+(30-40) to maximum Life",
    "UnveiledPrefixMana1": "+(30-40) to maximum Mana",
    "UnveiledPrefixAilments1": "(20-25)% chance to Avoid Elemental Ailments",
}
UNVEIL_DATA = dataclasses.replace(
    TEXTED, mods={**TEXTED.mods, **{k: dataclasses.replace(TEXTED.mods[k], text=t) for k, t in UNVEIL_TEXTS.items()}}
)  # the hand-made unveiled mods have the placeholder text `x`
UNVEIL_START = Item.build(
    UNVEIL_DATA,
    base_id=BELT,
    item_level=84,
    rarity=Rarity.RARE,
    mods=(placeholder(),),
    veil_offer=tuple(UNVEIL_TEXTS),
    quality=Quality(CatalystType.PRISMATIC, 12),
    implicits=(implicit("StrengthImplicitBelt1"), implicit("AvoidShockEldritchImplicit2", 2)),
)
SHOCK_IMPLICIT = ImplicitRequirement(
    "AvoidShock", None, frozenset({"AvoidShockEldritchImplicit2", "AvoidShockEldritchImplicit3"}), min_grade=2
)


def unveil_plan() -> Plan:
    from route_view_support import PRICES, START_NAME

    target = Target(
        BELT, 84, frozenset(), (Requirement("IncreasedLife", None, frozenset({"IncreasedLife1"})),), UNVEIL_START,
        implicits=(SHOCK_IMPLICIT,), quality=QualityRequirement(CatalystType.PRISMATIC, 15), start_price=START_NAME,
    )  # fmt: skip
    ab = Abstraction(UNVEIL_DATA, Goal.from_target(target), BELT, 84, (ChaosOrb(),))
    first = ab.compress(UNVEIL_START)
    priced, _ = price_offers((Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1}),), PRICES)
    policy = {first: offer_action(ab, priced[0], first)}
    return Plan(
        target=target, abstraction=ab, leaf_labels=leaf_labels(target), prices=PRICES, start=first,
        start_price=StartPrice(START_NAME, 6.0, "trade-api"), offers=priced, dropped=(), left_out=(),
        solution=Solution({first: 1.0}, policy, 0.0), risk=evaluate(policy, first, ab.is_goal),
        solve_seconds=0.0, risk_seconds=0.0,
    )  # fmt: skip


def test_golden_the_start_item_card_shows_the_veiled_placeholder_its_offer_quality_and_implicit():
    html = render_page(Page("Test page", (build_section(route_input(unveil_plan()), UNVEIL_DATA, anchor="policy"),)))

    assert "Unveil offer" in html
    assert "Prismatic catalyst quality 12%" in html
    assert "veiled" in html
    assert_golden("unveil_offer", html)
