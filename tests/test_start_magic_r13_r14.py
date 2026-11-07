"""R13 and R14 start from a Magic base: their guides open with Alteration and name no Transmutation Orb (#576, OR-4, OR-16, OR-17).

The guides: R13 "Alt spam for T1 Life and a resist" (Reddit thread pq4owv), R14 "Alteration roll a Hunter Thicket Bow(ilvl 78+)"
(Reddit comments/1f6a963). An Orb of Alteration works on a Magic item only, so a Normal start would need a Transmutation Orb the
guide never names, a hidden step. The start item is a Magic base with any mods or none, bought at its market price (OR-4, OR-17), so
the price key is the Magic base's. These tests need the cached dump (`CRAFTING_CACHE_DIR`) and skip cleanly without it. The first step
of each solved plan is checked where the plan is solved: R13 in `test_cli_r13_real.py`, R14 in `test_cli_r04_r14_heavy.py` (a heavy run).
"""

import json
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import load_route, make_plan
from crafting_system.items import Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import StartKind, buy_spec_of, load_target, start_price_key

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices"
CASES = {
    "r13-life-resist-belt": ("Alt spam for T1 Life and a resist", "Leather Belt, magic, item level 86-100"),
    "r14-hunter-bow": ("Alteration roll a Hunter Thicket Bow", "Thicket Bow, magic, item level 78-79, Hunter influence"),
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(params=sorted(CASES))
def stem(request):
    return request.param


def test_the_target_parses_with_a_magic_bought_start_item_and_quotes_the_guide(data, stem):
    path = ROOT / "examples" / "targets" / f"{stem}.yaml"
    target = load_target(path, data)

    assert target.start is StartKind.BOUGHT
    assert target.start_item.rarity is Rarity.MAGIC and target.start_item.mods == ()  # any mod or none (OR-17)
    assert CASES[stem][0] in path.read_text(encoding="utf-8")
    assert "transmutation-orb" not in target.actions  # the guide names none


def test_the_price_key_and_the_buy_spec_are_the_magic_base(data, stem):
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    spec = buy_spec_of(data, target)

    assert start_price_key(data, target) == spec.name == CASES[stem][1]
    assert spec.rarity == "magic"


@pytest.mark.parametrize("fixture", ["routes-allflame-2026-10-31.json", "vendor-v01-2026-11-01.json"])
def test_both_committed_price_files_hold_the_magic_key_and_no_normal_one(stem, fixture):
    prices = json.loads((PRICES / fixture).read_text(encoding="utf-8"))["prices"]
    key = CASES[stem][1]

    assert key in prices and prices[key]["chaos"] > 0
    assert key.replace(", magic,", ", normal,") not in prices


def test_the_plan_offers_no_transmutation_orb_and_the_given_route_has_no_rule_for_one(data, stem):
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    plan = make_plan(data, target, load_price_file(PRICES / "routes-allflame-2026-10-31.json"), solve_it=False)

    assert plan.start_price.name == CASES[stem][1]
    assert "Orb of Transmutation" not in {priced.label for priced in plan.offers}
    assert "Orb of Alteration" in {priced.label for priced in plan.offers}
    route = load_route(ROOT / "examples" / "routes" / f"{stem}.yaml", plan, data)
    assert all(rule.do != "Orb of Transmutation" for rule in route.rules)


def test_the_start_price_of_r13_is_a_trade_price_and_r14s_a_marked_stand_in(data):
    committed = json.loads((PRICES / "routes-allflame-2026-10-31.json").read_text(encoding="utf-8"))["prices"]

    belt = committed[CASES["r13-life-resist-belt"][1]]
    assert belt["source"] == "trade-api" and belt["detail"]["query"]["query"]["filters"]["type_filters"]["filters"]["rarity"] == {"option": "magic"}
    bow = committed[CASES["r14-hunter-bow"][1]]  # the exact item has 0 listings (#601): the wider item's price, said so in its note
    assert bow["source"] == "trade-api" and "STAND-IN" in bow["note"] and "#601" in bow["note"]
