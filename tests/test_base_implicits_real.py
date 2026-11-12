"""An item carries every implicit of its base, on the real data (ticket #484, decided on #449).

R06's Heavy Belt has `+(25-35) to Strength` (mod `StrengthImplicitBelt1`) from the start, so R06's `min_roll: 35` is a question about the roll,
not about presence. Checked here, on the real 3.29.3.3 data:

* a fresh Heavy Belt, and R06's start item, carry the Strength implicit at the low end of its range, 25;
* R06's `implicits` requirement is judged on that roll by the planner's goal check and by the goal oracle (which imports nothing of the
  planner and holds the rule written from #449), both ways: 25 does not meet 35, 35 does, and a belt whose implicit was replaced does not;
* a Vaal Orb's implicit outcome replaces the base implicit and its other outcomes keep it; a Scouring Orb keeps it; a Bloodstained draw
  chooses among the implicits the item lists, the base's included;
* the item a state stands for carries the base implicit no requirement names, and loses it to an Eldritch implicit or to a corrupted implicit,
  not to the corruption alone (#528).
"""

from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from goal_oracle_support import load_export, oracle_item
from independent.export import ExportMissing
from oracle import goal_oracle as g

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted
from crafting_system.actions import ScouringOrb, VaalOrb
from crafting_system.actions.bloodstained import ImplicitDraw
from crafting_system.items import ExplicitMod, ImplicitMod, Item, Rarity, is_corrupted_implicit
from crafting_system.targets import load_target

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "targets"
R06 = EXAMPLES / "r06-strength-heavy-belt.yaml"
STRENGTH = "StrengthImplicitBelt1"
LIFE = "IncreasedLife8"


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def target(real):
    return load_target(R06, real)


@pytest.fixture(scope="module")
def rare_belt(real, target):
    """A rare Heavy Belt with one mod, built with no `implicits`, so it carries its base's."""
    mod = real.mods[LIFE]
    return Item.build(
        real,
        base_id=target.base_id,
        item_level=75,
        rarity=Rarity.RARE,
        mods=(ExplicitMod(LIFE, tuple(min(stat.min, stat.max) for stat in mod.stats)),),
    )


def test_a_fresh_heavy_belt_carries_its_strength_implicit_at_the_low_end_of_its_range(real, target):
    stat = real.mods[STRENGTH].stats[0]
    fresh = Item.build(real, base_id=target.base_id, item_level=75, rarity=Rarity.NORMAL)

    assert (stat.min, stat.max) == (25, 35)
    assert fresh.implicits == (ImplicitMod(STRENGTH, 0, (25,)),)
    assert target.start_item.implicits == (ImplicitMod(STRENGTH, 0, (25,)),)  # R06 lists none: the parser adds the base's own


def test_r06_asks_the_roll_of_that_implicit_and_the_planner_judges_it_on_the_roll_held(real, target):
    (wanted,) = target.implicits
    start = target.start_item

    assert wanted.min_roll == (35,) and wanted.mod_ids == {STRENGTH}
    assert wanted in target.unmet(start)  # present at 25, and 25 is below 35
    assert wanted not in target.unmet(start.changed(real, implicits=(ImplicitMod(STRENGTH, 0, (35,)),)))
    assert wanted in target.unmet(start.changed(real, implicits=(ImplicitMod(STRENGTH, 0, (34,)),)))
    assert wanted in target.unmet(start.changed(real, implicits=()))  # replaced: absent


def test_the_oracle_judges_r06_on_the_same_roll_with_the_rule_written_from_the_text_of_449(target):
    try:
        export = load_export()
    except ExportMissing as problem:
        pytest.skip(str(problem))
    spec = g.OracleTarget.from_text(R06.read_text(encoding="utf-8"))
    oracle = g.Oracle(export, spec)
    (wanted,) = spec.implicits
    at = lambda value: g.OItem((), (g.OImplicit(STRENGTH, (value,)),))  # noqa: E731

    assert not oracle.implicit_met(wanted, g.OItem(()))  # nothing listed: held at the low end, 25, below 35
    assert not oracle.implicit_met(wanted, oracle_item(target.start_item))
    assert [(entry.mod_id, entry.values) for entry in oracle.held_implicits(g.OItem(()))] == [(STRENGTH, (25,))]
    assert not oracle.implicit_met(wanted, at(34)) and oracle.implicit_met(wanted, at(35))
    replaced = g.OItem((), (g.OImplicit("AvoidShockEldritchImplicit1", (34,)),))  # an implicit not the base's takes its place
    assert [entry.mod_id for entry in oracle.held_implicits(replaced)] == ["AvoidShockEldritchImplicit1"]
    assert not oracle.implicit_met(wanted, replaced)


def test_a_vaal_implicit_outcome_replaces_the_base_implicit_and_the_other_outcomes_keep_it(real, rare_belt):
    base = ImplicitMod(STRENGTH, 0, (25,))
    assert rare_belt.implicits == (base,)

    results = VaalOrb().outcomes(real, rare_belt).results
    replaced = sum((chance for chance, item in results if base not in item.implicits), Fraction(0))
    kept = sum((chance for chance, item in results if base in item.implicits), Fraction(0))

    assert replaced == Fraction(1, 4)  # the implicit outcome; the socket and nothing outcomes keep it, the brick keeps its implicits
    assert kept == Fraction(3, 4)
    for _, item in results:
        assert item.corrupted
        drawn = [entry for entry in item.implicits if is_corrupted_implicit(real.mods[entry.mod_id])]
        assert len(drawn) <= 1 and (len(item.implicits) == 1 if drawn else item.implicits == (base,))


def test_a_scouring_orb_keeps_the_base_implicit(real, rare_belt):
    scoured = ScouringOrb().outcomes(real, rare_belt).retained

    assert scoured.mods == () and scoured.implicits == rare_belt.implicits == (ImplicitMod(STRENGTH, 0, (25,)),)


def test_a_bloodstained_draw_chooses_among_the_implicits_the_item_lists_the_base_included(real, rare_belt):
    draw = ImplicitDraw.for_item(real, rare_belt, replaces_all=False)

    assert draw.kept == ((Fraction(1), ()),)  # the one implicit it lists is the one replaced
    assert all(case.kept == () for case in draw.cases)
    assert ImplicitDraw.for_item(real, rare_belt.changed(real, implicits=()), replaces_all=False).kept == ((Fraction(1), ()),)  # none: it just gains one


def test_the_item_a_state_stands_for_carries_the_base_implicit_no_requirement_names(real, rare_belt):
    # a goal that names an Eldritch implicit only: the Strength implicit decides nothing, so the state does not keep it
    ability = Abstraction(real, Goal((), (ImplicitWanted(frozenset({"AvoidShockEldritchImplicit1"})),)), rare_belt.base_id, 75, [])
    state = ability.compress(rare_belt)
    rebuilt, _ = ability._item_of(state, False)

    assert rebuilt.implicits == rare_belt.implicits  # present again, at the low end
    assert ability.compress(rebuilt) == state
    corrupted = ability.compress(rare_belt.changed(real, corrupted=True, implicits=()))
    assert ability._item_of(corrupted, False)[0].implicits == ()  # the corruption took its place; a corrupted item is final


def test_a_vaal_outcome_that_keeps_the_base_implicit_survives_compress_then_item_of_and_the_implicit_outcome_replaces_it(real, rare_belt):
    """Ticket #528 (#531): the state says which base implicits a corrupted item no longer holds, so it does not read "corrupted" as "replaced"."""
    ability = Abstraction(real, Goal((), (ImplicitWanted(frozenset({"AvoidShockEldritchImplicit1"})),)), rare_belt.base_id, 75, [VaalOrb()])
    strength = ImplicitMod(STRENGTH, 0, (25,))
    kept = replaced = Fraction(0)
    for chance, item in VaalOrb().outcomes(real, rare_belt).results:
        rebuilt = ability._item_of(ability.compress(item), False)[0]
        if strength in item.implicits:
            assert rebuilt.implicits == (strength,)
            kept += chance
        else:
            assert rebuilt.implicits == ()  # the corrupted implicit took its place; the state keeps no corrupted implicit (ADR-0036)
            replaced += chance
        assert ability.compress(rebuilt) == ability.compress(item)
    assert (kept, replaced) == (Fraction(3, 4), Fraction(1, 4))


def test_a_state_keeps_the_named_base_implicit_and_its_roll(real, rare_belt):
    ability = Abstraction(real, Goal((), (ImplicitWanted(frozenset({STRENGTH}), min_roll=(35,)),)), rare_belt.base_id, 75, [])
    low = ability.compress(rare_belt)
    high = ability.compress(rare_belt.changed(real, implicits=(ImplicitMod(STRENGTH, 0, (35,)),)))
    gone = ability.compress(rare_belt.changed(real, implicits=()))

    assert not ability.is_goal(low) and ability.is_goal(high) and not ability.is_goal(gone)
    assert len({low, high, gone}) == 3
    assert ability._item_of(low, False)[0].implicits == (ImplicitMod(STRENGTH, 0, (25,)),)
    assert ability._item_of(high, False)[0].implicits == (ImplicitMod(STRENGTH, 0, (35,)),)
    assert ability._item_of(gone, False)[0].implicits == ()
