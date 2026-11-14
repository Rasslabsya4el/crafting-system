"""Our exact outcome distribution against recorded Craft of Exile emulator frequencies, for the B1 core (ticket #544).

The counts are in `tests/fixtures/coe_recorded/b1_core.json` (our measurement, with its sample sizes, seeds, date and the
hashes of the Craft of Exile copy; no Craft of Exile code). They were recorded on the real bases of the benchmark routes:

* the Chaos Orb (R12's amulet with a fractured mod, R13's belt with four ordinary mods);
* the essences of R05 (Deafening Rage), R10 (Shrieking Spite) and R11 (Shrieking Loathing) on the routes' start items;
* Alteration, Augmentation and Regal on R13's belt, tested at the goal's tier (Life, Fire/Cold/Lightning Resistance T1);
* the fossil pairs of R08 (Dense + Shuddering) and R09 (Pristine + Shuddering) on their boots;
* the start boots of R08 and R09 with one Prismatic Fossil and with the guide's pair again (#617, `tools/coe_emulator/checks/617-start-boots.json`), each
  with the joint "the target is met" count: the share of finished items that are the target, or one sure bench craft short of it, read by the planner's
  own judge, against the planner's exact chance of one use (`_benchmark_use.per_use_of`), the number the review row of `benchmark` tells;
* the essences the `actions:` key of R08, R09 and R13 hides (#627, `tools/coe_emulator/checks/627-key-essences.json`): Shrieking Essence of Fear
  and Screaming Essence of Spite on the start boots of R08 and R09, with the target-met count against the planner's chance of one use on the target
  with its key removed (what the plans of run 42369553590 repeat), and Deafening Essence of Hatred on R13's rare belt.
* the Exalted Orb the `actions:` key of J01 and V01 hides (#637, `tools/coe_emulator/checks/637-exalt-key.json`): on the later items of the craft
  where the plans with the orb added take it (3-mod jewels missing one goal mod; helmets with the +1 Minion mod or tier 1 Life and 3 to 5 mods), with
  the target-met count against the planner's chance of one use on the target with the orb added, which is also pinned to a fraction worked by hand.

The statistic is stated in `coe_recorded_support.py`: an exact two-sided binomial test per cell, a Bonferroni correction
over every cell of this module, `ALPHA` = 0.01 for the module. There is no percentage threshold. A cell that fails is a
disagreement between our model and the emulator: it is filed as an issue (OR-29), never hidden by a wider test.

The roll cells (OR-4) are the goal lines that ask a roll, not a tier: R10's "+# to maximum Life" of at least 70, as
`r10-fractured-boots-70-life.yaml` writes it (`ROLL_TARGET_OF`). Since #895 the benchmark targets of R10 and R11 ask the Life by
tier (the owner's reading of 2026-11-13), so their Life lines are tier cells, and R11's roll of 96 is asked by no file any more. The
record holds, for the two essence cases, how many finished items carry each rolled value of each Life mod of ours;
the cell is the share of items that hold a Life mod whose roll the line's own judge passes, against our chance (the mod's
chance times the share of its uniform rolls that reach the roll). The histogram cells (one per Life mod, the whole law of its rolled values) are the control: a model whose roll ranges are shifted by one must fail them.

The tier-aware cells (OR-1, OR-2) put the emulator's chance that the finished item holds a mod "at tier T1" beside
what OUR GOAL says is that mod: the target file of the route is loaded, and each of its mod lines is judged by the
requirement's own `tier_ok` set (`accepted_by_tier`), not by a tier number written here.

Needs the cached dump (`CRAFTING_CACHE_DIR`); CI fetches it, so these run there.
"""

import json
import math
import re
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from coe_recorded_support import (
    ALPHA,
    MIN_EXPECTED,
    Cell,
    OurCase,
    binomial_two_sided,
    build_item,
    chi_square_sf,
    failures,
    histogram_cells,
    histogram_failures,
    joint_cells,
    load_recorded,
    mod_cells,
    roll_cell,
    shape_cells,
    target_cells,
)

from crafting_system.targets import load_target
from crafting_system.targets.model import KOfN

TARGETS = Path(__file__).resolve().parents[1] / "examples" / "targets"
RECORDED = load_recorded()
CASES = RECORDED["cases"]
# the route's target file whose mod lines the case is judged by
TARGET_OF = {
    "chaos-r12-amulet": "r12-lightning-amulet",
    "chaos-r13-belt": "r13-life-resist-belt",
    "essence-r05-ring": "r05-strength-ring",
    "essence-r10-boots": "r10-fractured-boots",
    "essence-r11-helmet": "r11-reservation-helmet",
    "alteration-r13-belt": "r13-life-resist-belt",
    "augmentation-r13-belt": "r13-life-resist-belt",
    "regal-r13-belt": "r13-life-resist-belt",
    "fossil-r08-boots": "r08-energy-shield-boots",
    "fossil-r09-boots": "r09-life-boots",
    "essence-c02-helmet": None,  # the prototype's case C02 has no route: its two targets are the joint cells
    "start-r08-prismatic": "r08-energy-shield-boots",  # #617: the first action of the planner and of the guide on the start boots, with the target-met count
    "start-r08-pair": "r08-energy-shield-boots",
    "start-r09-prismatic": "r09-life-boots",
    "start-r09-pair": "r09-life-boots",
    "essence-r08-fear": "r08-energy-shield-boots",  # #627: the essences the actions: key hides
    "essence-r09-spite": "r09-life-boots",
    "essence-r13-hatred": "r13-life-resist-belt",
    "exalt-j01-wants-attack-speed": "j01-cobalt-life-attack-speed",  # #637: the Exalted Orb the keys hide, on later items of the craft
    "exalt-j01-wants-wand-speed": "j01-cobalt-life-attack-speed",
    "exalt-j01-wants-life": "j01-cobalt-life-attack-speed",
    "exalt-v01-minion-three-mods": "v01-minion-helmet",
    "exalt-v01-minion-four-mods": "v01-minion-helmet",
    "exalt-v01-minion-five-mods": "v01-minion-helmet",
    "exalt-v01-life-three-mods": "v01-minion-helmet",
}
# the target file whose roll line (`min_roll`, OR-4) a case is also judged by: the benchmark target of R10 asks the Life by tier since
# #895, and this file keeps the guide's "at least 70" as a roll
ROLL_TARGET_OF = {"essence-r10-boots": "r10-fractured-boots-70-life"}
# the cases whose record holds the rolled values of each Life mod (the histogram cells, the control of the roll law)
HISTOGRAM_CASES = ("essence-r10-boots", "essence-r11-helmet")
# #627: the cases whose action the target's `actions:` key leaves out; their one use is the planner's on the target with the key removed (`actions`
# None, every kind not opt-in), as `.github/scripts/actions_key.py` plans the `removed` variant
KEY_HIDES = {"essence-r08-fear", "essence-r09-spite", "essence-r13-hatred"}
# the label of the case's action, for the cases recorded with a `target`: the planner's own numbers of one use of it on the start item
PRICES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
# the essence cases: the target's `mod:` line that the essence's forced mod must be (OR-2)
FORCED_BY_GOAL = {
    "essence-r05-ring": "StrengthEssence7_",
    "essence-r10-boots": "Intelligence8",
    "essence-r11-helmet": "ManaReservationEfficiencyEssence6_",
}
# #627: the forced mod of each essence the key hides, as `essences.json` gives it for the item class (claim `essence.forced_mod_by_item_class`);
# R08's and R09's are filler suffixes no goal line asks, R13's is the tier 1 of the Cold Resistance line
FORCED_BY_DATA = {
    "essence-r08-fear": "MinionLifeEssence6",
    "essence-r09-spite": "Intelligence6",
    "essence-r13-hatred": "ColdResist8",
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def ours(data):
    return {case: OurCase(data, record) for case, record in CASES.items()}


@pytest.fixture(scope="module")
def uses(data, targets):
    """The planner's numbers of one use of each recorded action that has a target-met count, on the start item (the plan is not solved)."""
    from crafting_system.cli._benchmark_use import per_use_of
    from crafting_system.planner._plan import make_plan
    from crafting_system.prices import load_price_file

    found = {}
    for case, record in CASES.items():
        if "target" in record and case in EXALT_BY_HAND:  # #637: a later item of the craft, the orb added to the key
            found[case] = exalt_use(data, {**record["item"], "target": record["target"]["file"]})
        elif "target" in record:
            target = targets[TARGET_OF[case]]
            if case in KEY_HIDES:
                target = replace(target, actions=None)
            plan = make_plan(data, target, load_price_file(PRICES), solve_it=False)
            item = target.start_item
            assert (record["item"]["base"], record["item"]["item_level"], record["item"]["rarity"], record["item"]["mods"]) == (
                item.base_id, item.item_level, item.rarity.value, []
            ), f"{case}: the recorded item is not the target's start item"
            opened = plan.abstraction.compress(item) if plan.start.flags.unopened else plan.start  # a bought listing is drawn first (#640): the recorded item is the one it opens to
            found[case] = per_use_of(plan, opened, record["action"])
            assert found[case]["short"] is not None, f"{case}: R08 and R09 have a sure bench step; its second target cell must not drop out"
    return found


@pytest.fixture(scope="module")
def targets(data):
    return {name: load_target(TARGETS / f"{name}.yaml", data) for name in {*TARGET_OF.values(), *ROLL_TARGET_OF.values()} if name}


def leaves(node):
    if isinstance(node, KOfN):
        for member in node.of:
            yield from leaves(member)
    else:
        yield node


def line_name(line) -> str:
    """The name of a goal line's cell: the line as the target file writes it (a roll, a tier, or the mods it names / accepts)."""
    if line.min_roll is not None:
        return f"{line.family or line.stat} roll {list(line.min_roll)}"
    return f"{line.family or line.stat} {'tier ' + str(line.min_tier) if line.min_tier is not None else 'by its mod'}"


def tier_cells(data, case, record, our, target) -> list[Cell]:
    """For each mod line of the goal that a draw can satisfy: the chance that the finished item holds a mod that line accepts.

    The mods a line accepts are the requirement's `tier_ok` (the natural tier it asks, OR-1) or, for a line that names a
    mod (`mod:`, OR-2) or a stat text, its `mod_ids`. They are in one family, so an item holds at most one of them and
    the chance is the sum of the mods' chances; a line over several families is not a cell here (it is asserted not to occur).
    """
    marginals = our.marginals()
    cells = []
    for line in (leaf for requirement in target.requirements for leaf in leaves(requirement)):
        if line.min_roll is not None:
            continue  # a line that asks a roll is covered by its roll cell only (`roll_cells`)
        accepted = set(line.tier_ok if line.tier_ok is not None else line.mod_ids)
        if accepted & our.kept:
            continue  # the item already holds it: see the test of the kept mods
        possible = accepted & marginals.keys()
        if not possible:
            continue
        families = {family for mod_id in possible for family in data.mods[mod_id].families}
        assert len(families) == 1, f"{case}: the goal line {line.family or line.stat!r} reaches several families {families}"
        name = line_name(line)
        seen = sum(record["mods"].get(mod_id, 0) for mod_id in possible)
        chance = float(sum(marginals[mod_id] for mod_id in possible))
        cells.append(Cell(case, "tier", name, record["applied"], seen, chance))
    return cells


def roll_cells(data, case, record, our, target) -> list[Cell]:
    """For each goal line that asks a roll: the share of finished items whose roll reaches it, the emulator's against ours."""
    marginals = our.marginals()
    cells = []
    for line in (leaf for requirement in target.requirements for leaf in leaves(requirement)):
        if line.min_roll is None or not (line.mod_ids & marginals.keys()):
            continue
        cells.append(roll_cell(data, case, line_name(line), record, our, line))
    return cells


@pytest.fixture(scope="module")
def family(data, all_cells) -> int:
    """The one family of the module's Bonferroni correction: every testable binomial cell and every testable histogram cell."""
    histograms = [cell for case in HISTOGRAM_CASES for cell in histogram_cells(data, case, CASES[case], "+# to maximum Life")]
    return len([cell for cell in all_cells if cell.testable]) + len([cell for cell in histograms if cell.testable])


@pytest.fixture(scope="module")
def all_cells(data, ours, targets, uses):
    cells = []
    for case, record in CASES.items():
        if "target" in record:
            cells += target_cells(case, record, uses[case])
        cells += mod_cells(case, record, ours[case])
        cells += shape_cells(case, record, ours[case])
        cells += joint_cells(case, record, ours[case])
        if TARGET_OF[case]:
            cells += tier_cells(data, case, record, ours[case], targets[TARGET_OF[case]])
            cells += roll_cells(data, case, record, ours[case], targets[TARGET_OF[case]])
        if case in ROLL_TARGET_OF:
            cells += roll_cells(data, case, record, ours[case], targets[ROLL_TARGET_OF[case]])
    return cells


# --- the statistic itself --------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "k", "p"), [(10, 0, 0.5), (10, 10, 0.5), (60, 11, 0.3), (60, 25, 0.3), (200, 3, 0.04), (200, 21, 0.04), (500, 250, 0.5)])
def test_the_binomial_p_value_is_twice_the_exact_tail_on_the_side_of_k(n, k, p):
    from math import comb

    def pmf(i):
        return Fraction(comb(n, i)) * Fraction(p) ** i * (1 - Fraction(p)) ** (n - i)

    lower = sum(pmf(i) for i in range(0, k + 1))
    upper = sum(pmf(i) for i in range(k, n + 1))
    expected = min(1.0, 2 * float(lower if k <= n * p else upper))
    assert binomial_two_sided(n, k, p) == pytest.approx(expected, rel=1e-9)


def test_a_cell_of_chance_zero_or_one_is_judged_exactly():
    assert binomial_two_sided(100, 0, 0.0) == 1.0 and binomial_two_sided(100, 1, 0.0) == 0.0
    assert binomial_two_sided(100, 100, 1.0) == 1.0 and binomial_two_sided(100, 99, 1.0) == 0.0


# --- the recorded data ----------------------------------------------------------------------------


def test_the_recorded_file_carries_its_provenance():
    provenance = RECORDED["provenance"]
    for key in ("recorded", "copy_fetched", "package_js_sha256", "poec_data_json_sha256", "coe_data_version", "seeded"):
        assert provenance[key]
    for case, record in CASES.items():
        assert record["runs"], case
        assert sum(run["repeats"] for run in record["runs"]) == record["applied"] + record["refused"], case
        assert len({run["seed"] for run in record["runs"]}) == len(record["runs"]), f"{case}: two runs share a seed"
    assert set(CASES) == set(TARGET_OF)


def test_the_recorded_file_holds_no_craft_of_exile_code():
    text = (Path(__file__).resolve().parent / "fixtures" / "coe_recorded" / "b1_core.json").read_text(encoding="utf-8")
    assert not re.search(r"function\s*[\w(]|=>|\bpoec_(sim|compute)|\bcrsim_|\bvar \w+\s*=", text)
    assert len(text) < 400_000  # counts and provenance, not a copy of anything


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_emulator_refused_nothing_our_system_applies(case):
    assert CASES[case]["refused"] == 0


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_samples_are_large_enough_to_see_a_tier_line(case):
    """A recorded case of fewer than 10,000 applications cannot tell a 1% mod from a 1.5% one."""
    assert CASES[case]["applied"] >= 10000


# --- support and kept mods -------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_mod_the_emulator_gave_is_one_our_model_can_give(ours, case):
    possible = set(ours[case].marginals()) | ours[case].kept
    gave = set(CASES[case]["mods"])
    assert gave <= possible, f"{case}: the emulator gave {sorted(gave - possible)} that our model never gives"


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_kept_mods_are_on_every_finished_item(ours, case):
    n = CASES[case]["applied"]
    for mod_id in ours[case].kept:
        assert CASES[case]["mods"].get(mod_id) == n, f"{case}: {mod_id} is kept by our model, the emulator has it on {CASES[case]['mods'].get(mod_id)}/{n}"


@pytest.mark.parametrize("case", sorted(FORCED_BY_GOAL))
def test_the_essence_forces_exactly_the_mod_the_goal_asks(data, ours, targets, case):
    """OR-2: the mod line of the target names the essence's mod, and the emulator's essence puts exactly that mod on every item."""
    forced = FORCED_BY_GOAL[case]
    lines = [leaf for requirement in targets[TARGET_OF[case]].requirements for leaf in leaves(requirement)]
    assert any(line.mod_ids == frozenset({forced}) for line in lines), f"{case}: no line of the target asks {forced}"
    assert ours[case].outcomes.forced == forced
    assert CASES[case]["mods"].get(forced) == CASES[case]["applied"]


@pytest.mark.parametrize("case", sorted(FORCED_BY_DATA))
def test_the_essence_the_key_hides_forces_the_mod_of_the_game_data_on_every_item(data, ours, targets, case):
    """#627: our essence and the emulator's put the same forced mod on every finished item, and it is the one `essences.json` gives."""
    forced = FORCED_BY_DATA[case]
    record = CASES[case]
    (essence,) = [e for e in data.essences.values() if e.name == record["action"]]
    assert essence.mod_for(data.base_items[record["item"]["base"]].item_class) == forced
    assert ours[case].outcomes.forced == forced
    assert record["mods"].get(forced) == record["applied"]
    assert all(t.actions is not None and "essence" not in t.actions for t in [targets[TARGET_OF[case]]]), f"{case}: the target's key no longer hides the essence"


@pytest.mark.parametrize("case", ["essence-r08-fear", "essence-r09-spite"])
def test_the_essence_the_key_hides_ends_in_the_target_as_often_as_the_planner_says(uses, case):
    """#627: one use of the essence on the start boots ends in the target, or one bench craft short of it, at the planner's chance (the
    review of 2026-11-12: 2.23% for R08's Shrieking Fear, 2.36% for R09's Screaming Spite); the binomial cells of the module test it against the
    emulator, and here the planner's number is pinned so that a change of it is seen."""
    use = uses[case]
    assert use["error"] is None
    expected = {"essence-r08-fear": 0.0222956, "essence-r09-spite": 0.0236223}[case]
    assert use["chance"] + use["short"] == pytest.approx(expected, abs=1e-6)


# #637: the Exalted Orb the `actions:` key of J01 and V01 hides, on the states the plans with the orb added take it in (run 42378616946). The
# chance that one use ends in the target, worked by hand from the weights of the empty base's pool (`IncreasedLife9` and the jewel mods: the
# family and side of each, the side cap of 2 on a jewel and 3 on a helmet): the wanted mod's weight over the weights the orb can still add,
# without the families the item holds.
EXALT_CHECKS = Path(__file__).resolve().parents[1] / "tools" / "coe_emulator" / "checks" / "637-exalt-key.json"
EXALT_BY_HAND = {
    "exalt-j01-wants-attack-speed": Fraction(500, 17520),  # only a suffix: Attack Speed 500 of 17,520 (the five ailment suffixes are one family, gone)
    "exalt-j01-wants-wand-speed": Fraction(500, 17900),  # only a prefix: Wand attack speed 500 of 17,900
    "exalt-j01-wants-life": Fraction(350, 17750),  # only a prefix: % increased maximum Life 350 of 17,750
    "exalt-v01-minion-three-mods": Fraction(1000, 97400),  # either side: Life tier 1 1,000 of 97,400
    "exalt-v01-minion-four-mods": Fraction(1000, 90400),  # either side, one filler prefix: its family's 7,000 leaves the 97,400
    "exalt-v01-minion-five-mods": Fraction(1000, 32000),  # the suffixes are full: Life tier 1 1,000 of the prefixes' 32,000
    "exalt-v01-life-three-mods": Fraction(250, 87675),  # either side: +1 to Level of all Minion Skill Gems 250 of 87,675
}


def exalt_use(data, case: dict) -> dict:
    """The planner's numbers of one Exalted Orb on the case's item, on its target with the orb added to the key (as `actions_key.py plus=exalted-orb`)."""
    from crafting_system.cli._benchmark_use import per_use_of
    from crafting_system.planner._plan import make_plan
    from crafting_system.prices import load_price_file

    target = load_target(Path(__file__).resolve().parents[1] / case["target"], data)
    target = replace(target, actions=(*target.actions, "exalted-orb"))
    prices = load_price_file(target.price_file if target.price_file is not None else PRICES)
    plan = make_plan(data, target, prices, solve_it=False)
    return per_use_of(plan, plan.abstraction.compress(build_item(data, case)), "Exalted Orb")


@pytest.mark.parametrize("case", sorted(EXALT_BY_HAND))
def test_one_exalted_orb_ends_in_the_target_at_the_chance_worked_by_hand(data, case):
    """#637: the planner's chance of one use of the Exalted Orb on the plan's states is the hand-worked one (the side cap and the families held)."""
    (spec,) = [check for check in json.loads(EXALT_CHECKS.read_text(encoding="utf-8")) if check["id"] == case]
    use = exalt_use(data, spec)
    assert use["error"] is None, use["error"]
    assert not use["short"]  # no sure bench step on J01 or V01: None
    assert use["chance"] == pytest.approx(float(EXALT_BY_HAND[case]), abs=1e-12)


def test_the_judge_reads_a_later_item_at_its_recorded_rarity_with_the_target_s_own_prices(data):
    """#637: the emulator's target count of V01 (a Normal start item, its own price file) judges the finished rare helmet, not a Normal one."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "coe_emulator"))
    from target_judge import TargetJudge

    judge = TargetJudge(data, "examples/targets/v01-minion-helmet.yaml", "rare")
    assert judge.target.start_item.rarity.value == "normal"
    held = ["GlobalIncreaseMinionSpellSkillGemLevel1", "Dexterity8", "ColdResist7"]
    assert judge.reading([*held, "IncreasedLife9"]) == "goal"
    assert judge.reading([*held, "IncreasedLife8"]) == "other"  # tier 2 Life: not the goal's tier 1 (OR-1)
    assert judge.reading([*held, "FireResist7"]) == "other"


def test_the_keys_still_hide_the_exalted_orb():
    """#637: J01's and V01's keys do not name the Exalted Orb; when #405 takes the keys out, this test and the cases above stay as the check."""
    import yaml

    for name in ("j01-cobalt-life-attack-speed", "v01-minion-helmet"):
        key = yaml.safe_load((TARGETS / f"{name}.yaml").read_text(encoding="utf-8")).get("actions")
        assert key is None or "exalted-orb" not in key, name


# --- the statistical test --------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_emulator_frequencies_are_ours_under_the_binomial_test(all_cells, family, case):
    """Every testable cell of the case (each mod, the shape, each tier line) has p >= ALPHA / m over the module's m cells."""
    cells = [cell for cell in all_cells if cell.case == case]
    assert any(cell.kind == "mod" and cell.testable for cell in cells)
    bad = [cell for cell in failures(all_cells, family=family) if cell.case == case]
    assert not bad, "\n".join(cell.describe() for cell in bad)


def test_the_module_tests_many_cells_with_a_stated_correction(all_cells):
    testable = [cell for cell in all_cells if cell.testable]
    assert len(testable) >= 200
    assert {cell.kind for cell in testable} == {"mod", "shape", "tier", "joint", "roll", "target"}
    assert ALPHA == 0.01 and MIN_EXPECTED == 5


def test_every_goal_line_of_the_five_routes_is_a_tested_or_a_forced_cell(data, ours, targets, all_cells):
    """Each mod line the route's target file asks is a tested tier cell, a mod the item already holds, or one the action cannot give.

    The lines are read from the target files as they stand (a line the guide gives no tier, a roll, a named mod), never from
    a list of names written here, so a target that is re-read cannot slip out of the comparison. A line is "forced" only when
    the item holds its mod already (`kept`: the fractured start mod, the essence's forced mod) or our model's chance of it is
    exactly 0 (the action cannot add it: a suffix to a full magic item, a bench-only mod).
    """
    tested = {(cell.case, cell.kind, cell.name) for cell in all_cells if cell.kind in ("tier", "roll") and cell.testable}
    asked = set()
    for case, target_name in (*TARGET_OF.items(), *ROLL_TARGET_OF.items()):
        if not target_name:
            continue
        marginals = ours[case].marginals()
        for line in (leaf for requirement in targets[target_name].requirements for leaf in leaves(requirement)):
            accepted = set(line.tier_ok if line.tier_ok is not None else line.mod_ids)
            if accepted & ours[case].kept:
                continue
            possible = accepted & marginals.keys()
            if sum(marginals[mod_id] for mod_id in possible) == 0:
                continue
            asked.add((case, "roll" if line.min_roll is not None else "tier", line_name(line)))
    assert asked <= tested, f"goal lines with no tested cell: {sorted(asked - tested)}"
    # a line that asks a roll is covered by its roll cell alone: no tier cell (the mods of the line, any roll) stands for it
    rolls = {(case, name) for case, kind, name in asked if kind == "roll"}
    assert {case for case, _ in rolls} == set(ROLL_TARGET_OF)
    assert not [cell for cell in all_cells if cell.kind == "tier" and (cell.case, cell.name) in rolls]
    # the lines that matter are among them: Life T1 on the belt, Defences and Movement Speed on the boots, Life on the other routes
    for case, kind, family in [
        ("alteration-r13-belt", "tier", "IncreasedLife"),
        ("regal-r13-belt", "tier", "IncreasedLife"),
        ("augmentation-r13-belt", "tier", "IncreasedLife"),
        ("fossil-r08-boots", "tier", "DefencesPercent"),
        ("fossil-r08-boots", "tier", "MovementVelocity"),
        ("fossil-r09-boots", "tier", "IncreasedLife"),
        ("fossil-r09-boots", "tier", "MovementVelocity"),
        ("essence-r10-boots", "roll", "+# to maximum Life"),  # the guide's "at least 70", from `r10-fractured-boots-70-life.yaml`
        ("essence-r10-boots", "tier", "+# to maximum Life"),  # the owner's targets (#895): Life tier 1 or 2 on the boots,
        ("essence-r11-helmet", "tier", "+# to maximum Life"),  # tier 1 on the helmet,
        ("essence-r11-helmet", "tier", "DefencesPercent"),  # and Evasion tier 1 to tier 3
    ]:
        assert any(c == case and k == kind and name.startswith(family + " ") for c, k, name in asked), (case, family)


ROLL_CASES = {"essence-r10-boots": 70}  # the roll each goal line asks, as the target file (`ROLL_TARGET_OF`) writes it


@pytest.mark.parametrize("case", sorted(ROLL_CASES))
def test_the_roll_line_is_a_testable_cell_that_passes_the_binomial_test(data, ours, targets, all_cells, family, case):
    """One roll cell for the case's roll line, testable under MIN_EXPECTED, and not a failure at the module's correction."""
    (line,) = [leaf for requirement in targets[ROLL_TARGET_OF[case]].requirements for leaf in leaves(requirement) if leaf.min_roll is not None]
    assert line.min_roll == (ROLL_CASES[case],) and line.stat == "+# to maximum Life"
    (cell,) = [cell for cell in all_cells if cell.case == case and cell.kind == "roll"]
    assert cell.name == line_name(line) and cell.testable, cell.describe()
    assert cell not in failures(all_cells, family=family), cell.describe()


@pytest.mark.parametrize("case", HISTOGRAM_CASES)
def test_the_recorded_rolls_are_of_the_finished_items_and_inside_our_ranges(data, case):
    """The histogram of a Life mod adds up to the items the record counts with that mod, and no rolled value is outside our range."""
    record = CASES[case]
    histograms = record["rolls"]["+# to maximum Life"]
    assert histograms
    for mod_id, histogram in histograms.items():
        assert sum(histogram.values()) == record["mods"][mod_id], (case, mod_id)
        (stat,) = data.mods[mod_id].stats
        low, high = min(stat.min, stat.max), max(stat.min, stat.max)
        assert all(low <= float(value) <= high for value in histogram), (case, mod_id, low, high, sorted(histogram, key=float))


@pytest.mark.parametrize("case", HISTOGRAM_CASES)
def test_the_histogram_of_each_life_mod_is_our_roll_law_under_the_correction(data, family, case):
    """One histogram cell per Life mod the record holds: its rolled values against the uniform law, not a failure at the module's correction."""
    cells = histogram_cells(data, case, CASES[case], "+# to maximum Life")
    assert len(cells) >= 8 and all(cell.testable and len(cell.bins()) >= 2 for cell in cells)
    bad = histogram_failures(cells, family)
    assert not bad, "\n".join(cell.describe() for cell in bad)


@pytest.mark.parametrize("by", [1, -1])
@pytest.mark.parametrize("case", HISTOGRAM_CASES)
def test_a_model_with_the_roll_ranges_shifted_by_one_fails_the_histogram_cells(data, family, case, by):
    """The control: our law with every range moved by one gives chance 0 to a value the emulator gave (one edge of the range).

    The threshold cell cannot be the control: the shift moves its chance by 0.17% (R10) and 0.24% (R11), which needs
    about 1.2M and 0.6M applications to see. The histogram of the rolled values sees it at the recorded sample.
    """
    wrong = histogram_cells(data, case, CASES[case], "+# to maximum Life", by)
    rejected = histogram_failures(wrong, family)
    assert len(wrong) >= 8 and rejected == wrong, f"mods the shifted law did not reject: {[cell.mod_id for cell in wrong if cell not in rejected]}"
    assert all(cell.unsupported for cell in rejected)
    assert not histogram_failures(histogram_cells(data, case, CASES[case], "+# to maximum Life"), family)


@pytest.mark.parametrize(
    ("statistic", "df", "tail"),
    [(3.841458820694124, 1, 0.05), (5.991464547107979, 2, 0.05), (18.307038053275146, 10, 0.05), (4.0, 2, 0.1353352832366127), (0.0, 5, 1.0), (30.0, 4, 16 * math.exp(-15))],
)
def test_the_chi_square_tail(statistic, df, tail):
    assert chi_square_sf(statistic, df) == pytest.approx(tail, rel=1e-6)


def test_c02_the_life_and_a_resistance_together_are_the_emulator_s(all_cells, family):
    """C02 (Deafening Essence of Envy on a Royal Burgonet): the pair of families the prototype asked for, on the emulator's own draw.

    The calculator gives our chance of the two TOP tiers 2.09% above its own number (`test_proto_coe_comparison.py`); the
    top tiers are too rare to count (about 1 in 1,200 items), so the pair is counted at family level, where the same
    dependence between the two sides (the shape of the item) decides it, and our model must be the emulator's here.
    """
    joints = [cell for cell in all_cells if cell.case == "essence-c02-helmet" and cell.kind == "joint"]
    assert {cell.name for cell in joints} >= {"IncreasedLife+FireResistance"}
    assert all(cell.testable for cell in joints)
    assert not failures(joints, ALPHA, family)


# --- the test has power ----------------------------------------------------------------------------


def test_the_test_rejects_a_model_in_which_a_mod_is_half_as_likely_again(all_cells, family):
    """A model that makes its most expected mod 1.5 times as likely is rejected at the module's correction: the test can fail."""
    testable = [cell for cell in all_cells if cell.testable]
    m = family
    biggest = max((cell for cell in testable if cell.kind == "mod"), key=lambda cell: cell.expected)
    wrong = binomial_two_sided(biggest.n, biggest.seen, min(biggest.ours * 1.5, 0.999))
    assert wrong < ALPHA / m, biggest.describe()
    assert binomial_two_sided(biggest.n, biggest.seen, biggest.ours) >= ALPHA / m


def test_the_regal_counts_are_not_the_augmentation_s_distribution(data, ours):
    """Two different actions are told apart: the Regal Orb's recorded mods against the Augmentation's model fail the same test."""
    regal, augmentation = CASES["regal-r13-belt"], ours["augmentation-r13-belt"]
    cells = mod_cells("regal-vs-augmentation", regal, augmentation)
    assert failures(cells)


# --- the marginals by family are exact -------------------------------------------------------------


@pytest.mark.parametrize("case", ["augmentation-r13-belt", "essence-r05-ring", "fossil-r08-boots"])
def test_the_marginals_by_family_are_the_exact_ones(ours, case):
    """The chance of a mod from the chance of its family and its weight in the family equals the exact distribution of that mod alone."""
    marginals = ours[case].marginals()
    top = sorted(marginals, key=lambda mod_id: -marginals[mod_id])
    for mod_id in (top[0], top[len(top) // 2], top[-1]):
        assert ours[case].exact_marginal(mod_id) == marginals[mod_id], f"{case}: {mod_id}"


# --- a crafted mod is not a tier (OR-1) --------------------------------------------------------------


def test_a_crafted_life_does_not_meet_the_goal_s_life_tier_one(data, targets):
    """The emulator offers the bench's Life as a mod of its own group; our goal asks the natural tier, which a bench craft has none of (OR-1)."""
    target = targets["r13-life-resist-belt"]
    (life,) = [leaf for requirement in target.requirements for leaf in leaves(requirement) if leaf.family == "IncreasedLife"]
    crafted = data.mods["EinharMasterIncreasedLife2"]  # the bench's (26-40) Life
    natural = data.mods["IncreasedLife9"]  # tier 1 on the belt, (130-144)
    belt = "Metadata/Items/Belts/Belt3"
    as_crafted = build_item(
        data, {"base": belt, "item_level": 86, "rarity": "rare", "mods": [crafted.id]}
    )
    as_rolled = build_item(data, {"base": belt, "item_level": 86, "rarity": "rare", "mods": [natural.id]})
    assert as_crafted.mods[0].crafted and not life.is_met_by(as_crafted)
    assert life.is_met_by(as_rolled)
