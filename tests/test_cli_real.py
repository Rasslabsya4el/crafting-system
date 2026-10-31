"""R12 on the real 3.29.3.3 dump: the guide's numbers as weight shares, and the whole command (ticket #26).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at
it) and skip cleanly without it; CI fetches it (ticket #165). The guide (PoE Vault, "Fractured-lightning-resistance +1
Lightning amulet") quotes single-draw weight shares; the pool builder reproduces them on the 3.29
weights, ADR-0020. The solver's chance that the finished item holds the mod is reported next to them
and is NOT compared with the guide: later draws of the same click feed it too.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from cli_support import R12, geometric_p90_clicks, price_file, read_json
from cli_support import run as run_command

from crafting_system.actions import HarvestReforge
from crafting_system.cli import make_plan, verify, weight_share
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table
from crafting_system.targets import load_target

AMULET = "Metadata/Items/Amulets/Amulet1"
RESIST = "LightningResist1"
GEM = "GlobalLightningGemLevel1"
LIGHTNING = "lightning"
LIFEFORCE_PRICE = 0.03458  # Primal Crystallised Lifeforce on poe.ninja, Allflame, 2026-10-31
GUIDE_CHAOS_TOTAL = 213_850  # the guide's total for the natural odds: 200 / 213,850 = 0.0935%
RUNS = 2_000


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def amulet(data, *, level: int, fractured_resist: bool) -> Item:
    mods = ()
    if fractured_resist:
        mod = data.mods[RESIST]
        low = tuple(min(stat.min, stat.max) for stat in mod.stats)
        mods = (ExplicitMod(RESIST, tier_table(data, AMULET)[RESIST], low, fractured=True),)
    return Item.build(data, base_id=AMULET, rarity=Rarity.RARE, item_level=level, mods=mods)


def test_reforge_lightning_is_200_in_14950(data):
    wanted, total = weight_share(data, amulet(data, level=86, fractured_resist=False), [GEM], LIGHTNING)

    assert (wanted, total) == (200, 14_950)
    assert f"{float(Fraction(wanted, total)) * 100:.3f}%" == "1.338%"


def test_reforge_lightning_with_the_fractured_lightning_resistance_is_200_in_6950(data):
    wanted, total = weight_share(data, amulet(data, level=86, fractured_resist=True), [GEM], LIGHTNING)

    assert (wanted, total) == (200, 6_950)
    assert f"{float(Fraction(wanted, total)) * 100:.2f}%" == "2.88%"


def test_the_chaos_share_at_item_level_86_is_200_in_214650_and_the_guide_is_800_lower(data):
    wanted, total = weight_share(data, amulet(data, level=86, fractured_resist=False), [GEM], None)

    assert (wanted, total) == (200, 214_650)
    assert f"{float(Fraction(wanted, total)) * 100:.4f}%" == "0.0932%"
    assert total - GUIDE_CHAOS_TOTAL == 800  # the guide's 200 / 213,850 = 0.0935%, cause not identified


def test_the_solver_chance_of_one_click_sits_next_to_the_shares_and_is_not_the_guides_number(data):
    target = load_target(R12, data)

    q = float(HarvestReforge(LIGHTNING).outcomes(data, target.start_item).chance_all([GEM]))

    assert q == pytest.approx(0.031712, abs=1e-6)  # 3.17% for a click, against the share 2.88%: not compared


def test_the_command_on_the_real_r12_amulet(tmp_path, data, capsys):
    q = float(HarvestReforge(LIGHTNING).outcomes(data, load_target(R12, data).start_item).chance_all([GEM]))
    click = 50 * LIFEFORCE_PRICE

    code, out = run_command(tmp_path, data=data, prices=price_file(lifeforce=LIFEFORCE_PRICE))

    document = read_json(out)
    assert code == 0
    (state,) = document["states"]
    assert state["action"] == "Harvest Reforge Lightning"
    assert state["goal_chance_per_use"] == pytest.approx(q, rel=1e-12)
    totals = document["totals"]
    assert totals["mean_cost"]["value"] == pytest.approx(4.0 + click / q, rel=1e-9)
    assert totals["p90"]["value"] == pytest.approx(4.0 + click * geometric_p90_clicks(q), rel=1e-9)
    shares = {(s["action"], s["wanted_weight"], s["candidate_weight"]): s for s in document["single_draw_shares"]}
    harvest = shares[("Harvest Reforge Lightning", 200, 6_950)]
    assert harvest["share"] == pytest.approx(0.02878, abs=1e-5)
    assert harvest["chance_of_one_use"] == pytest.approx(q, rel=1e-12)
    assert "200/6,950 = 2.88%" in capsys.readouterr().out
    assert document["timings_seconds"]["risk_evaluate"] >= 0.0


def test_verify_agrees_with_the_computed_mean_on_the_real_amulet(data):
    plan = make_plan(data, load_target(R12, data), price_file(lifeforce=LIFEFORCE_PRICE))

    check = verify(data, plan, runs=RUNS, seed=11)

    assert check.agrees, check.reason
    assert check.report.successes == RUNS
    assert check.computed_mean == pytest.approx(4.0 + plan.mean_remaining)



def test_without_a_lifeforce_price_the_reforge_is_dropped_and_the_chaos_orb_policy_is_returned(tmp_path, data, capsys):
    code, out = run_command(tmp_path, data=data, prices=price_file(lifeforce=None))

    document = read_json(out)
    assert code == 0
    dropped = {drop["action"]: drop["missing_prices"] for drop in document["dropped_actions"]}
    assert dropped.pop("Harvest Reforge Lightning") == ["Primal Crystallised Lifeforce"]
    assert dropped and all(name.startswith(("Bench craft", "Remove")) or "Essence of" in name for name in dropped)
    # the price file of this test holds no essence and no bench currency
    (state,) = document["states"]
    assert state["action"] == "Chaos Orb"
    assert 0.0 < state["goal_chance_per_use"] < 0.01  # about 0.42% a Chaos Orb, the weights are huge integers
    assert state["reach_probability"] == pytest.approx(1.0)
    assert document["totals"]["mean_cost"]["value"] == pytest.approx(4.0 + 1.0 / state["goal_chance_per_use"], rel=1e-9)
    assert "Dropped for lack of a price: Harvest Reforge Lightning" in capsys.readouterr().out
