"""R24 and R07 on the real 3.29.3.3 dump, at their committed prices, with nothing solved (ticket #146).

R24 is the fractured-Mana Avoid Shock / Spell Suppression boots with an unveiled Movement Speed + Onslaught, R07 the +2 minion
Convoking Wand read for 3.29 (bench Trigger, unveiled minion speed). These check the targets, the start prices, the offers (the
unveil blocks among them), the given routes and the route conditions on the veil and the offer. The policies (CLI, `--verify`, the
solver's mean against the given route's) are a heavy run: `tests/test_cli_r24_r07_heavy.py`. These skip without the cached dump.
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import load_route, make_plan
from crafting_system.cli._route import RouteError, parse_route
from crafting_system.items import ExplicitMod, Item, Rarity, veiled_placeholder
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "veiled-r24-r07-2026-11-12.json"
ROUTES = {
    "R24": ("examples/targets/r24-avoid-shock-boots.yaml", "examples/routes/r24-avoid-shock-boots.yaml"),
    "R07": ("examples/targets/r07-minion-wand.yaml", "examples/routes/r07-minion-wand.yaml"),
}
START = {
    "R24": "Murder Boots, item level 86-100, fractured +(69-73) to maximum Mana",
    "R07": "Convoking Wand, item level 84",
}
ROUTE_ACTIONS = {
    "R24": {
        "Deafening Essence of Torment", "Orb of Annulment", "Harvest Add Remove Fire", "Bench craft Suffixes Cannot Be Changed",
        "Veiled Chaos Orb", "Unveil", "Pick 1", "Pick 2", "Pick 3",
    },
    "R07": {
        "Fossils Corroded Fossil + Jagged Fossil + Metallic Fossil + Shuddering Fossil", "Orb of Annulment", "Bench craft Prefixes Cannot Be Changed",
        "Bench craft Trigger a Socketed Spell when you Use a Skill, with a 8 second Cooldown / Spells Triggered this way have 150% more Cost",
        "Veiled Chaos Orb", "Unveil", "Pick 1", "Pick 2", "Pick 3",
    },
}
# an unveil block (ADR-0026): offered only with the whole bench-craft kind, which these targets do not name (their bench crafts are named
# by label, the guides' own); the blocks themselves are tested in test_cli_unveil_blocks_real.py
BLOCKS = {
    "R24": "Bench craft +(15-25) to maximum Life",
    "R07": "Bench craft Minions have (14-15)% increased Attack Speed / Minions have (14-15)% increased Cast Speed",
}
BOOTS = "Metadata/Items/Armours/Boots/BootsDexInt9"
MS_ONSLAUGHT = "JunMasterVeiledMovementVelocityAndOnslaughtOnKill"
LIFE_REGEN = "JunMasterVeiledBaseLifeAndManaRegen_"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=["R24", "R07"])
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def unsolved(data, route_id):
    target = load_target(ROOT / ROUTES[route_id][0], data)
    return make_plan(data, target, load_price_file(target.price_file), solve_it=False)


@pytest.fixture(scope="module")
def r24(data):
    target = load_target(ROOT / ROUTES["R24"][0], data)
    return make_plan(data, target, load_price_file(target.price_file), solve_it=False)


def test_the_targets_read_their_committed_price_file(data, route_id):
    target = load_target(ROOT / ROUTES[route_id][0], data)
    assert target.price_file.resolve() == PRICES.resolve()


def test_the_start_item_costs_its_committed_stand_in_price(unsolved, route_id):
    entry = load_price_file(PRICES).prices[START[route_id]]
    assert unsolved.start_price.name == START[route_id]
    assert unsolved.start_price.chaos == pytest.approx(entry.chaos)


def test_the_plan_offers_the_route_actions_all_priced_and_no_unveil_block(unsolved, route_id):
    labels = {priced.label for priced in unsolved.offers}
    assert ROUTE_ACTIONS[route_id] <= labels
    assert BLOCKS[route_id] not in labels
    assert {label for label in labels if label.startswith("Bench craft")} <= ROUTE_ACTIONS[route_id]
    assert not [limit for limit in unsolved.limits if limit.kind == "unpriced"]
    assert {priced.label: priced.cost for priced in unsolved.offers}["Veiled Chaos Orb"] == pytest.approx(146.5)


def test_the_given_route_reads_against_the_offers(unsolved, data, route_id):
    route = load_route(ROOT / ROUTES[route_id][1], unsolved, data)
    assert route.skip_refused
    assert any(rule.when.offer_shows is not None for rule in route.rules)
    assert any(rule.when.veil == "any" for rule in route.rules)


# --- the conditions on the veil and the offer, on R24's boots --------------------------------------------------------------------


def roll(data, mod_id: str, **flags) -> ExplicitMod:
    return ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), **flags)


def boots(data, *mods: ExplicitMod, **fields) -> Item:
    return Item.build(data, base_id=BOOTS, item_level=86, rarity=Rarity.RARE, mods=mods, **fields)


def rule_of(plan, data, when: str):
    return parse_route(f"rules:\n  - when: {when}\n    do: Unveil\n", plan, data).rules[0].when


def test_veil_tells_the_side_of_the_placeholder(r24, data):
    mana = roll(data, "IncreasedMana12", fractured=True)
    prefix = r24.abstraction.compress(boots(data, mana, veiled_placeholder(data, "VeiledPrefix")))
    suffix = r24.abstraction.compress(boots(data, mana, veiled_placeholder(data, "VeiledSuffix")))
    plain = r24.abstraction.compress(boots(data, mana))
    found = {
        value: [rule_of(r24, data, f"{{veil: {value}}}").matches(state, data) for state in (prefix, suffix, plain)]
        for value in ("prefix", "suffix", "any", "none")
    }
    assert found == {
        "prefix": [True, False, False],
        "suffix": [False, True, False],
        "any": [True, True, False],
        "none": [False, False, True],
    }


def test_offer_tells_whether_an_offer_is_drawn_and_where_a_wanted_mod_is_shown(r24, data):
    mana = roll(data, "IncreasedMana12", fractured=True)
    veil = veiled_placeholder(data, "VeiledPrefix")
    drawn = r24.abstraction.compress(boots(data, mana, veil, veil_offer=tuple(sorted((MS_ONSLAUGHT, LIFE_REGEN)))))
    other = r24.abstraction.compress(boots(data, mana, veil, veil_offer=(LIFE_REGEN,)))
    none = r24.abstraction.compress(boots(data, mana, veil))
    at = sorted((MS_ONSLAUGHT, LIFE_REGEN)).index(MS_ONSLAUGHT) + 1  # the offer is kept in mod id order: `Pick k` takes the k-th

    def matches(when: str) -> list[bool]:
        condition = rule_of(r24, data, when)
        return [condition.matches(state, data) for state in (drawn, other, none)]

    assert matches("{offer: drawn}") == [True, True, False]
    assert matches("{offer: none}") == [False, False, True]
    assert matches("{offer: {shows: {family: MovementVelocity}}}") == [True, False, False]
    assert matches(f"{{offer: {{shows: {{family: MovementVelocity}}, at: {at}}}}}") == [True, False, False]
    assert matches(f"{{offer: {{shows: {{family: MovementVelocity}}, at: {3 - at}}}}}") == [False, False, False]


@pytest.mark.parametrize(
    ("when", "problem"),
    [
        ("{veil: left}", "must be one of"),
        ("{offer: maybe}", "must be one of"),
        ("{offer: {shows: {family: MovementVelocity}, at: 4}}", "must be 1, 2 or 3"),
        ("{offer: {shows: {family: MovementVelocity}, at: 1.0}}", "must be 1, 2 or 3"),
        ("{offer: {at: 1}}", "shows: this key is required"),
        ("{offer: {shows: {family: Strength}}}", "Strength"),
    ],
)
def test_a_wrong_veil_or_offer_condition_is_refused_with_its_line(r24, data, when, problem):
    with pytest.raises(RouteError, match=problem):
        rule_of(r24, data, when)


def test_a_plan_without_an_unveil_refuses_the_conditions(data):
    target = load_target(ROOT / "examples/targets/r10-fractured-boots.yaml", data)
    plan = make_plan(data, target, load_price_file(ROOT / "tests/fixtures/prices/routes-allflame-2026-11-10.json"), solve_it=False)
    with pytest.raises(RouteError, match="hold no veil and no offer"):
        parse_route("rules:\n  - when: {veil: none}\n    do: restart\n", plan, data)
