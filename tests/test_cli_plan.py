"""R12 through the whole chain on the fixture amulet pool: targets -> prices -> abstraction -> solver -> risk.

The expected numbers are written from the definition: one click of the Harvest reforge leaves the
wanted mod with the exact chance `chance_all` gives, the policy repeats the click until it does, so
the clicks are geometric. Mean cost = start price + click cost / q, and the p90 is the cost of the
least number of clicks that is done with chance 0.9 (the costs share one unit, so the budget DP is exact).
"""

import pytest
from cli_support import LIFEFORCE, R12, START, geometric_p90_clicks, price_file, read_json
from cli_support import run as run_command
from targets_support import DATA

from crafting_system.actions import ChaosOrb, HarvestReforge
from crafting_system.cli import Offer, PlanError, default_offers, make_plan
from crafting_system.prices import write_price_file
from crafting_system.rules import get_rule
from crafting_system.targets import load_target

GEM = "GlobalLightningGemLevel1"
LIFEFORCE_PRICE = 0.01
CLICK = 50 * LIFEFORCE_PRICE


def run(tmp_path, *arguments, prices="default", **fields):
    """The command on the fixture data with a price file that has the lifeforce and the start amulet."""
    return run_command(tmp_path, *arguments, prices=price_file() if prices == "default" else prices, **fields)


@pytest.fixture(scope="module")
def target():
    return load_target(R12, DATA)


@pytest.fixture(scope="module")
def q(target):
    """The exact chance that one Harvest reforge click leaves the gem-level mod on the start item."""
    return float(HarvestReforge("lightning").outcomes(DATA, target.start_item).chance_all([GEM]))


def test_the_click_cost_is_fifty_primal_lifeforce_from_the_registry():
    rule = get_rule("harvest_reforge.lifeforce_cost")

    assert dict(rule.value["lightning"]) == {LIFEFORCE: 50}
    harvest = next(offer for offer in default_offers() if offer.label == "Harvest Reforge Lightning")
    assert dict(harvest.resources) == {LIFEFORCE: 50}


def test_the_default_offers_are_the_chaos_orb_and_the_reforge():
    assert [offer.label for offer in default_offers()] == ["Chaos Orb", "Harvest Reforge Lightning"]


def test_the_cli_returns_the_policy_with_odds_mean_cost_and_p90(tmp_path, q):
    code, out = run(tmp_path)

    assert code == 0
    document = read_json(out)
    (state,) = document["states"]
    assert state["id"] == "S1" and state["action"] == "Harvest Reforge Lightning"
    assert state["cost_per_use"] == pytest.approx(CLICK)
    assert state["goal_chance_per_use"] == pytest.approx(q, rel=1e-12)
    assert state["reach_probability"] == pytest.approx(1.0)
    odds = {step["to"]: step["probability"] for step in state["transitions"]}
    assert odds == {"goal": pytest.approx(q, rel=1e-12), "S1": pytest.approx(1 - q, rel=1e-12)}

    totals = document["totals"]
    start = 4.0
    assert totals["success_probability"]["value"] == 1.0
    assert totals["mean_cost"]["value"] == pytest.approx(start + CLICK / q, rel=1e-9)
    assert totals["mean_cost_without_start"] == pytest.approx(CLICK / q, rel=1e-9)
    assert totals["p90"]["value"] == pytest.approx(start + CLICK * geometric_p90_clicks(q), rel=1e-9)
    assert totals["p90"]["low"] <= totals["p90"]["value"] <= totals["p90"]["high"]
    assert totals["mean_cost_divine"] == pytest.approx(totals["mean_cost"]["value"] / 300.0)
    assert document["start"] == {
        "state": "S1", "price_name": START, "price_chaos": 4.0, "price_source": "trade-api"
    }  # fmt: skip


def test_the_text_tree_shows_the_main_line_the_miss_the_odds_the_mean_and_p90(tmp_path, q, capsys):
    run(tmp_path)

    text = capsys.readouterr().out
    assert "S1: rare; fractured +#% to Lightning Resistance; lacks +1 to Level of all Lightning Skill Gems" in text
    assert "do: Harvest Reforge Lightning (50 Primal Crystallised Lifeforce = 0.50 Chaos each)" in text
    assert f"{q * 100:.2f}%  goal reached" in text
    assert "nothing gained, back to S1" in text
    assert "mean cost" in text and "p90" in text and "Divine" in text
    assert "risk.evaluate" in text and "JSON policy written to" in text
    assert text.isascii()


def test_the_cheaper_action_wins_when_the_lifeforce_is_dear(tmp_path):
    # A click of the reforge costs 10 Chaos here, far more than a Chaos Orb draw is worth.
    code, out = run(tmp_path, prices=price_file(lifeforce=0.2))

    assert code == 0
    assert read_json(out)["states"][0]["action"] == "Chaos Orb"


def test_a_start_price_given_on_the_command_line_wins(tmp_path, q):
    code, out = run(tmp_path, "--start-price", "10")

    document = read_json(out)
    assert code == 0 and document["start"]["price_chaos"] == 10.0
    assert document["start"]["price_source"] == "given on the command line"
    assert document["totals"]["mean_cost"]["value"] == pytest.approx(10.0 + CLICK / q, rel=1e-9)


def test_a_hand_override_of_the_start_price_wins_over_the_trade_price(tmp_path):
    write_price_file(tmp_path / "prices.json", price_file())
    (tmp_path / "price_overrides.toml").write_text(f'[prices]\n"{START}" = 6.5\n', encoding="utf-8")
    target_file = tmp_path / "r12.yaml"
    target_file.write_text(R12.read_text(encoding="utf-8") + "price_file: prices.json\n", encoding="utf-8")

    code, out = run(tmp_path, target=target_file, prices=None)  # prices=None: read the file the target names

    assert code == 0
    start = read_json(out)["start"]
    assert start["price_chaos"] == 6.5 and start["price_source"] == "override"


def test_a_start_item_without_a_price_stops_with_a_message(tmp_path, capsys):
    code, _ = run(tmp_path, prices=price_file(start=None))

    assert code == 1
    assert "no price for the start item 'R12 start amulet'" in capsys.readouterr().err


def test_an_action_without_a_price_is_dropped_and_listed(tmp_path, capsys):
    code, out = run(tmp_path, prices=price_file(lifeforce=None))

    assert code == 0
    document = read_json(out)
    assert document["dropped_actions"] == [{"action": "Harvest Reforge Lightning", "missing_prices": [LIFEFORCE]}]
    assert document["states"][0]["action"] == "Chaos Orb"
    assert "Dropped for lack of a price: Harvest Reforge Lightning" in capsys.readouterr().out


def test_a_plan_with_no_priced_action_is_refused(target):
    offers = [Offer("Chaos Orb", ChaosOrb(), {"Unobtainium": 1})]

    with pytest.raises(PlanError, match="no action has a price; missing: Unobtainium"):
        make_plan(DATA, target, price_file(), offers=offers)


def test_a_start_item_that_already_meets_the_target_costs_only_its_price(tmp_path):
    text = R12.read_text(encoding="utf-8").replace(
        '- stat: "+1 to Level of all Lightning Skill Gems"', "- family: LightningResistance"
    )
    target_file = tmp_path / "done.yaml"
    target_file.write_text(text, encoding="utf-8")

    code, out = run(tmp_path, target=target_file)

    document = read_json(out)
    assert code == 0 and document["states"] == []
    assert document["totals"]["mean_cost"]["value"] == 4.0
