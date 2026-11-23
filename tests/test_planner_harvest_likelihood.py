"""The two likelihood Harvest reforges as a method of the planner (#975, OR-37: Harvest is batch B1, a beta method), planned through the entry
and the envelope search on a toy amulet pool whose answer is worked out by hand.

The toy keeps six one-weight families of the small amulet pool, three prefixes (the gem level, Lightning damage, Life) and three suffixes
(Lightning, Cold Resistance, Mana Leech), one mod each. An amulet holds three of each side, so a reforge of a four-mod item draws four of the six
families one after another, each with a chance proportional to its weight among those not drawn yet (`harvest_reforge.likelihood_never_fewer_mods`,
`affix_draw.family_exclusion`), and no side ever fills. Before the draw the weight of a family the item holds is multiplied by 10 (More Likely)
or by 1/10 (Less Likely), `harvest_reforge.likelihood_weight_factor`. Both cost `c` (200 Wild Crystallised Lifeforce), the start is a bought
rare amulet at `S`, and the run's methods setting offers the two reforges alone.

* Less Likely finds the one family missing. The start holds four families but not Life and the goal is Life. A reforge leaves out exactly two
  families. Less Likely weighs the four held ones 1/10 and the two others (Life and Mana Leech) 1: Life is left out when it is one of the
  last two drawn, `q` = 694/69069 (about 1%), summed over the draw orders
  (`_draw`, checked below). Every state after a reforge that missed Life
  holds four families with Life out again and two unheld, so the chance is the same at every such state: `V = c / (1 - q)`. More Likely weighs the held four by 10 and leaves Life out far more often, so the
  plan takes Less Likely.
* More Likely keeps what the item holds. With a seventh family (Fire Resistance: four suffixes, so the suffixes can fill) the start holds the
  gem level, Lightning damage, Lightning and Cold Resistance; the goal is the three prefixes, gem level, Lightning damage and Life. The value of
  the best policy over the four-family states is solved here by value iteration with the chances of each draw order written out (`_draw`), and
  the plan's mean must equal it (about 107.91); at the start that policy takes More Likely, so the two crafts are both used by the plans here.

The lower bound of the method: the reforge reads the families of the junk (`Reads.adding`) and draws mods it does not name, so the offers'
floors class it TERMINAL (`_offer_kinds`): its floor is its price, and Wald's argument is cut at its first use. The search proves each plan
exact: its last standing has its lower figure at the plan's cost.
"""

import dataclasses
import datetime
import itertools
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, DAMAGE_1, FIRE_RESIST, GEM, LIFE_1, MANA_1, RESIST_1
from items_support import AMULET, DATA
from test_cli_offers import with_currency_names

from crafting_system.actions import HarvestReforgeLikelihood, kinds
from crafting_system.data import Weight
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _envelope
from crafting_system.planner._offer_kinds import TERMINAL, _kind_of
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

SIX = (GEM, DAMAGE_1, LIFE_1, RESIST_1, COLD_RESIST, MANA_1)
SEVEN = (*SIX, FIRE_RESIST)  # the test of More Likely adds a fourth suffix: a side of three can then fill
PREFIXES = frozenset({GEM, DAMAGE_1, LIFE_1})
SIDE_ROOM = 3  # an amulet holds three prefixes and three suffixes
FAMILY = {
    GEM: "GlobalDamageTypeGemLevel", DAMAGE_1: "LightningDamage", LIFE_1: "IncreasedLife",
    RESIST_1: "LightningResistance", COLD_RESIST: "ColdResistance", MANA_1: "ManaLeech", FIRE_RESIST: "FireResistance",
}  # fmt: skip
WILD = "Wild Crystallised Lifeforce"
LIFEFORCE = 0.05  # Chaos per Wild Crystallised Lifeforce: one reforge costs 200 of them, c = 10
C = 200 * LIFEFORCE
S = 50.0
Q_LIFE_OUT = Fraction(694, 69069)  # the chance Less Likely leaves Life out of a four-family item without it
METHODS = ("harvest-reforge-likelihood",)  # the run's methods setting (#405: a target names none)


def toy_data(chosen=SIX):
    """The fixture data with the chosen mods at weight 1 on an amulet and every other mod at weight 0 (the bench table still finds its mods)."""
    mods = {
        mod_id: dataclasses.replace(
            mod, spawn_weights=(Weight("amulet", 1), Weight("default", 0)) if mod_id in chosen else (Weight("default", 0),), required_level=1
        )
        for mod_id, mod in DATA.mods.items()
    }
    return with_currency_names(dataclasses.replace(DATA, mods=mods))


TOY = toy_data()
TOY7 = toy_data(SEVEN)

TARGET = """\
base: {base}
item_level: 84
requirements:
{requirements}
start_item:
  rarity: rare
  mods:
{mods}
start: bought
"""


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices() -> PriceFile:
    day = "2026-10-30"
    entry = PriceEntry(LIFEFORCE, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {WILD: entry})


def _target(tmp_path, wanted: tuple[str, ...], held: tuple[str, ...], data=TOY):
    requirements = "\n".join(f"  - family: {FAMILY[mod_id]}" for mod_id in wanted)
    mods = "\n".join(
        f"    - mod: {mod_id}\n      values: {[min(stat.min, stat.max) for stat in data.mods[mod_id].stats]}" for mod_id in held
    )
    path = tmp_path / "amulet.yaml"
    path.write_text(TARGET.format(base=data.base_items[AMULET].name, requirements=requirements, mods=mods), encoding="utf-8")
    return dataclasses.replace(load_target(path, data), actions=METHODS)


def _plan(target, seen: list, data=TOY):
    settings = PlanSettings(recipe_starts=False, start_price=S, solver="envelope", watch=seen.append)
    return plan_target(data, target, _prices(), settings)


# ---- the hand-worked numbers ------------------------------------------------------------------------------------


def _draw(held: frozenset, more: bool, families=SIX, count: int = 4) -> dict[frozenset, Fraction]:
    """The chance of each set of `count` families a reforge of an item holding `held` leaves, by the draw orders written out: each draw takes a
    family not drawn yet with a chance proportional to its weight, among the families of a side that still has room."""
    factor = Fraction(10) if more else Fraction(1, 10)
    weight = {family: factor if family in held else Fraction(1) for family in families}
    found: dict[frozenset, Fraction] = {}
    for order in itertools.permutations(families, count):
        chance = Fraction(1)
        for step, family in enumerate(order):
            drawn = order[:step]
            room = {side: SIDE_ROOM - sum((f in PREFIXES) == side for f in drawn) for side in (True, False)}
            open_ = [f for f in families if f not in drawn and room[f in PREFIXES] > 0]
            if family not in open_:
                chance = Fraction(0)
                break
            chance *= weight[family] / sum(weight[f] for f in open_)
        if chance:
            found[frozenset(order)] = found.get(frozenset(order), Fraction(0)) + chance
    return found


def _best_value(start: frozenset, wanted: frozenset, families=SIX) -> tuple[float, bool]:
    """V of the best policy from `start` (reforge with either craft, or buy the start again at S), and whether it reforges More Likely there."""
    states = [frozenset(four) for four in itertools.combinations(families, 4) if sum(f not in PREFIXES for f in four) <= SIDE_ROOM]
    kernels = {(state, more): _draw(state, more, families) for state in states for more in (True, False)}
    value = {state: 0.0 for state in states}
    for _ in range(100_000):
        new = {}
        for state in states:
            if wanted <= state:
                new[state] = 0.0
                continue
            reforge = min(C + sum(float(p) * value[after] for after, p in kernels[(state, more)].items()) for more in (True, False))
            new[state] = min(reforge, S + value[start])
        done = max(abs(new[state] - value[state]) for state in states) < 1e-12
        value = new
        if done:
            break
    q = {more: C + sum(float(p) * value[a] for a, p in kernels[(start, more)].items()) for more in (True, False)}
    return value[start], q[True] < q[False]


def test_the_likelihood_reforges_are_a_planner_kind_offered_by_default():
    (kind,) = [each for each in kinds() if each.name == "harvest-reforge-likelihood"]
    assert kind.planner and not kind.opt_in  # a beta method, offered by default (OR-37, OR-41)
    assert kind in kinds(planner_only=True)


def test_the_hand_worked_draw_left_out_chance():
    # Less Likely on {gem, Lightning damage, Lightning Resistance, Cold Resistance}: Life and Mana Leech weigh 1, the four held 1/10 (total
    # 2.4). Life is left out when the four draws take the other five but one: Mana Leech and three held ones, or the four held ones.
    held = frozenset({GEM, DAMAGE_1, RESIST_1, COLD_RESIST})
    out = sum(p for four, p in _draw(held, more=False).items() if LIFE_1 not in four)
    assert out == Q_LIFE_OUT


def test_less_likely_finds_the_missing_family_at_c_over_one_minus_q(tmp_path):
    held = (GEM, DAMAGE_1, RESIST_1, COLD_RESIST)
    target = _target(tmp_path, (LIFE_1,), held)
    q = Q_LIFE_OUT
    # every state after a miss holds four families with Life out: by symmetry of the one weights the chance is q there too
    for four in (frozenset(f) for f in itertools.combinations(SIX, 4)):
        if LIFE_1 not in four:
            assert sum(p for after, p in _draw(four, more=False).items() if LIFE_1 not in after) == q
    expected = C / (1 - float(q))
    seen: list = []
    plan = _plan(target, seen)
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved: the bound met the plan


def test_more_likely_keeps_what_the_item_holds_at_the_value_of_the_best_policy(tmp_path):
    # seven families (Fire Resistance added: four suffixes, so a side of three can fill); the start holds two of the three prefixes wanted
    held = (GEM, DAMAGE_1, RESIST_1, COLD_RESIST)
    wanted = (GEM, DAMAGE_1, LIFE_1)
    expected, more_first = _best_value(frozenset(held), frozenset(wanted), SEVEN)
    assert more_first  # the hand-worked policy reforges More Likely at the start
    assert expected == pytest.approx(107.91, abs=0.01)
    target = _target(tmp_path, wanted, held, TOY7)
    seen: list = []
    plan = _plan(target, seen, TOY7)
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)


def test_the_floor_of_the_reforge_is_its_price_terminal():
    from crafting_system.items import ExplicitMod, Item, Rarity

    start = Item.build(
        TOY, base_id=AMULET, item_level=84, rarity=Rarity.RARE,
        mods=tuple(ExplicitMod(m, tuple(min(s.min, s.max) for s in TOY.mods[m].stats)) for m in (GEM, DAMAGE_1, RESIST_1, COLD_RESIST)),
    )  # fmt: skip
    for more in (True, False):
        action = HarvestReforgeLikelihood(more)
        assert _kind_of(TOY, start, PricedOffer(Offer(action.label(), action, {}), C, ()))[0] == TERMINAL


def test_a_six_mod_reforge_bound_is_certified_not_lowered_to_zero(tmp_path, monkeypatch):
    # #1448. Seven families; the start holds six of them, all but Mana Leech, which is the goal. A reforge of a six-mod item draws six: three
    # prefixes of three and three suffixes of four, so it leaves out exactly one suffix; Less Likely weighs the five held families other than
    # the prefixes 1/10 and Mana Leech 1, and every miss gives the start again: V = c / (1 - q), q the chance Mana Leech is the one left out.
    # The bound walks a draw of six as six choice nodes at `FLOOR_COST` before the next paid reforge, so its certificate needs the window 8.
    # Before #1448 the doubling stopped at 4 as at a free cycle, the bound certified nothing and was lowered to 0 at every key: the search began
    # at a lower figure of 0 (R12's likelihood group, 823 keys, the same way). The exact solve in rational numbers (#1380) would rescue a bound
    # this small, not R12's; it is turned off so the bound stands on its float64 certificate as a large one does.
    from crafting_system.planner import _envelope_plan
    from crafting_system.solver import _packed_exact

    monkeypatch.setattr(_packed_exact, "EXACT_CLASSES", 0)
    held = (GEM, DAMAGE_1, LIFE_1, RESIST_1, COLD_RESIST, FIRE_RESIST)
    q = sum(p for six, p in _draw(frozenset(held), more=False, families=SEVEN, count=6).items() if MANA_1 not in six)
    assert q == sum(p for six, p in _draw(frozenset(held), more=False, families=SEVEN, count=6).items() if six == frozenset(held))
    expected = C / (1 - float(q))
    bounds = []
    real = _envelope_plan.pattern_lower_bound
    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", lambda *a, **k: bounds.append(real(*a, **k)) or bounds[-1])
    seen: list = []
    plan = _plan(_target(tmp_path, (MANA_1,), held, TOY7), seen, TOY7)

    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert bounds and all(bound.error_bound < 1e-6 for bound in bounds)  # certified (before: inf)
    assert seen[0].lower >= C * (1 - 1e-9)  # the search starts at the bound: at least one reforge's price (before: 0)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved
