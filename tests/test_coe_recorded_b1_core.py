"""Our exact outcome distribution against recorded Craft of Exile emulator frequencies, for the B1 core (ticket #544).

The counts are in `tests/fixtures/coe_recorded/b1_core.json` (our measurement, with its sample sizes, seeds, date and the
hashes of the Craft of Exile copy; no Craft of Exile code). They were recorded on the real bases of the benchmark routes:

* the Chaos Orb (R12's amulet with a fractured mod, R13's belt with four ordinary mods);
* the essences of R05 (Deafening Rage), R10 (Shrieking Spite) and R11 (Shrieking Loathing) on the routes' start items;
* Alteration, Augmentation and Regal on R13's belt, tested at the goal's tier (Life, Fire/Cold/Lightning Resistance T1);
* the fossil pairs of R08 (Dense + Shuddering) and R09 (Pristine + Shuddering) on their boots.

The statistic is stated in `coe_recorded_support.py`: an exact two-sided binomial test per cell, a Bonferroni correction
over every cell of this module, `ALPHA` = 0.01 for the module. There is no percentage threshold. A cell that fails is a
disagreement between our model and the emulator: it is filed as an issue (OR-29), never hidden by a wider test.

The tier-aware cells (OR-1, OR-2) put the emulator's chance that the finished item holds a mod "at tier T1" beside
what OUR GOAL says is that mod: the target file of the route is loaded, and each of its mod lines is judged by the
requirement's own `tier_ok` set (`accepted_by_tier`), not by a tier number written here.

Needs the cached dump (`CRAFTING_CACHE_DIR`); CI fetches it, so these run there.
"""

import re
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
    failures,
    joint_cells,
    load_recorded,
    mod_cells,
    shape_cells,
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
}
# the essence cases: the target's `mod:` line that the essence's forced mod must be (OR-2)
FORCED_BY_GOAL = {
    "essence-r05-ring": "StrengthEssence7_",
    "essence-r10-boots": "Intelligence8",
    "essence-r11-helmet": "ManaReservationEfficiencyEssence6_",
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def ours(data):
    return {case: OurCase(data, record) for case, record in CASES.items()}


@pytest.fixture(scope="module")
def targets(data):
    return {name: load_target(TARGETS / f"{name}.yaml", data) for name in set(TARGET_OF.values()) if name}


def leaves(node):
    if isinstance(node, KOfN):
        for member in node.of:
            yield from leaves(member)
    else:
        yield node


def line_name(line) -> str:
    """The name of a goal line's cell: the line as the target file writes it (a tier, or the mods it names / accepts)."""
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


@pytest.fixture(scope="module")
def all_cells(data, ours, targets):
    cells = []
    for case, record in CASES.items():
        cells += mod_cells(case, record, ours[case])
        cells += shape_cells(case, record, ours[case])
        cells += joint_cells(case, record, ours[case])
        if TARGET_OF[case]:
            cells += tier_cells(data, case, record, ours[case], targets[TARGET_OF[case]])
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


# --- the statistical test --------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_emulator_frequencies_are_ours_under_the_binomial_test(all_cells, case):
    """Every testable cell of the case (each mod, the shape, each tier line) has p >= ALPHA / m over the module's m cells."""
    cells = [cell for cell in all_cells if cell.case == case]
    assert any(cell.kind == "mod" and cell.testable for cell in cells)
    bad = [cell for cell in failures(all_cells) if cell.case == case]
    assert not bad, "\n".join(cell.describe() for cell in bad)


def test_the_module_tests_many_cells_with_a_stated_correction(all_cells):
    testable = [cell for cell in all_cells if cell.testable]
    assert len(testable) >= 200
    assert {cell.kind for cell in testable} == {"mod", "shape", "tier", "joint"}
    assert ALPHA == 0.01 and MIN_EXPECTED == 5


def test_every_goal_line_of_the_five_routes_is_a_tested_or_a_forced_cell(data, ours, targets, all_cells):
    """Each mod line the route's target file asks is a tested tier cell, a mod the item already holds, or one the action cannot give.

    The lines are read from the target files as they stand (a line the guide gives no tier, a roll, a named mod), never from
    a list of names written here, so a target that is re-read cannot slip out of the comparison. A line is "forced" only when
    the item holds its mod already (`kept`: the fractured start mod, the essence's forced mod) or our model's chance of it is
    exactly 0 (the action cannot add it: a suffix to a full magic item, a bench-only mod).
    """
    tested = {(cell.case, cell.name) for cell in all_cells if cell.kind == "tier" and cell.testable}
    asked = set()
    for case, target_name in TARGET_OF.items():
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
            asked.add((case, line_name(line)))
    assert asked <= tested, f"goal lines with no tested cell: {sorted(asked - tested)}"
    # the lines that matter are among them: Life T1 on the belt, Defences and Movement Speed on the boots, Life on the other routes
    for case, family in [
        ("alteration-r13-belt", "IncreasedLife"),
        ("regal-r13-belt", "IncreasedLife"),
        ("augmentation-r13-belt", "IncreasedLife"),
        ("fossil-r08-boots", "DefencesPercent"),
        ("fossil-r08-boots", "MovementVelocity"),
        ("fossil-r09-boots", "IncreasedLife"),
        ("fossil-r09-boots", "MovementVelocity"),
        ("essence-r10-boots", "+# to maximum Life"),
        ("essence-r11-helmet", "+# to maximum Life"),
        ("essence-r11-helmet", "DefencesPercent"),
    ]:
        assert any(c == case and name.startswith(family + " ") for c, name in asked), (case, family)


def test_c02_the_life_and_a_resistance_together_are_the_emulator_s(all_cells):
    """C02 (Deafening Essence of Envy on a Royal Burgonet): the pair of families the prototype asked for, on the emulator's own draw.

    The calculator gives our chance of the two TOP tiers 2.09% above its own number (`test_proto_coe_comparison.py`); the
    top tiers are too rare to count (about 1 in 1,200 items), so the pair is counted at family level, where the same
    dependence between the two sides (the shape of the item) decides it, and our model must be the emulator's here.
    """
    joints = [cell for cell in all_cells if cell.case == "essence-c02-helmet" and cell.kind == "joint"]
    assert {cell.name for cell in joints} >= {"IncreasedLife+FireResistance"}
    assert all(cell.testable for cell in joints)
    assert not failures(joints, ALPHA)


# --- the test has power ----------------------------------------------------------------------------


def test_the_test_rejects_a_model_in_which_a_mod_is_half_as_likely_again(all_cells):
    """A model that makes its most expected mod 1.5 times as likely is rejected at the module's correction: the test can fail."""
    testable = [cell for cell in all_cells if cell.testable]
    m = len(testable)
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
