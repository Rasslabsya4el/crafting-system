"""The prototype's Craft of Exile comparisons that are about landed mechanics, rerun offline (ticket #73).

The prototype (`docs/validation/coe_cases.md` of `archive/prototype`) froze twelve comparisons of its
engine with Craft of Exile's own probability kernel (`poec_computeFinalProbsV2`) on the real
pool. The four carried here are those of the Chaos Orb and of an essence, whose mechanics have
landed: C01, C06 and C09 (Chaos Orb on a rare helmet, ring and amulet) and C02 (Deafening Essence
of Envy on a rare helmet, which forces Chaos Resistance). The other eight wait for their tickets:

* C03 (Exalted Orb on a rare helmet): #67.
* C04, C05, C07, C08, C10, C11, C12 (Alchemy on a normal item, Alteration and Regal on a magic
  item): #64.

Each case is an item level 86 rare item with no explicit mod, on the base the prototype used, and
asks for the chance that the finished item holds all its targets. Three kinds of test:

* The oracle: the rerun of Craft of Exile's kernel gives the number the prototype froze, to 1e-12
  relative. It needs the local Craft of Exile copy (git-ignored, pinned by SHA256; see
  `coe_support.py`) and Node, and skips cleanly without them.
* Our engine against the oracle on today's data (repoe-fork 3.29.3.3, the cached dump, which the
  CI does not have): within the prototype's 5% investigation threshold, and pinned to the
  difference measured now (within 0.1 percentage point) so that a drift is noticed.
* The side totals: the weight of the eligible prefixes and suffixes in both sources, against the
  doc's table. They agree except on the amulet, whose difference is explained below.

C09 changed since the prototype (-0.536% then, -1.184% now), almost wholly for one reason in today's
data, shown by the tests below with the engine's own arithmetic on a regrouped pool: the 3.29.3.3
dump holds `IncreasedCastSpeed2Royale` (a Battle Royale suffix, level 4, weight 800 on an amulet) that
Craft of Exile and the PoB projection do not have; without it the difference is -0.530%. A minor second
reason is that the dump puts the five "+1 to Level of all <type> Skill Gems" prefixes in one family
(`GlobalDamageTypeGemLevel`, one of them at most per item) where the other two sources treat them as
five separate groups (about 0.005 percentage points). With both undone the engine gives the
prototype's number to the last digit.

What remains of each difference (+0.14%, +2.09%, -1.27% and -0.5%) is not attributed to a cause: the
prototype's doc names the structural difference (Craft of Exile factorizes the side requirements and
their count composition, the engine keeps the joint family state through all draws) but claims no
unique cause for each small discrepancy. They are within the 5% threshold and pinned, nothing more.

Not carried from the prototype's pack: its hand fixtures run through the original JS kernel
(weights 1/1/2, P(A)=7/12, P(A,C)=5/12, one draw 1/4); they are KA01-KA08 of
`test_proto_known_answers_draw.py` on our engine, but no longer an independent run through Craft of
Exile's code. Also not carried: the check that a modified level or range fixture fails.
"""

import pytest
from abstraction_support import real_game_data
from coe_support import (
    BY_ID,
    CASES,
    check_correspondences,
    our_chance,
    our_outcomes,
    our_outcomes_as_coe_pools,
    our_side_totals,
    relative_percent,
    run_oracle,
)

ROYALE = "IncreasedCastSpeed2Royale"
GEM_LEVELS = "GlobalDamageTypeGemLevel"

# The doc's table: Craft of Exile's probability and the prototype's own, as frozen on 2026-09-21,
# and the eligible (prefix, suffix) weight of both sources there.
FROZEN_COE = {
    "C01": 0.0003668380441541475,
    "C02": 0.0008579182295252153,
    "C06": 0.0001101634950524083,
    "C09": 0.0001042588117746307,
}
PROTOTYPE_OURS = {
    "C01": 0.0003673650969794048,
    "C02": 0.0008758259906074872,
    "C06": 0.00010876109551498082,
    "C09": 0.00010370039891240398,
}
DOC_TOTALS = {
    "C01": {"prefix": 39275, "suffix": 78400},
    "C02": {"prefix": 39275, "suffix": 76900},
    "C06": {"prefix": 60250, "suffix": 103600},
    "C09": {"prefix": 88600, "suffix": 125250},
}

# The relative difference (ours - CoE) / CoE in percent, measured on 3.29.3.3 and today's rules,
# against the doc's row (+0.1437, +2.0874, -1.2730, -0.5356): only C09 moved, see the docstring.
MEASURED_PERCENT = {"C01": 0.14367, "C02": 2.08735, "C06": -1.27302, "C09": -1.18391}
THRESHOLD_PERCENT = 5.0  # the prototype's investigation threshold
DRIFT_PERCENT = 0.1  # the pin tolerance, in percentage points

IDS = [case.id for case in CASES]


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def coe():
    return run_oracle()


class Ours:
    """Our engine's outcomes and chances per case, each worked out once for the module (exact, so slow)."""

    def __init__(self, data):
        self.data = data
        self.outcomes_by_id = {}
        self.chance_by_id = {}

    def outcomes(self, case):
        if case.id not in self.outcomes_by_id:
            self.outcomes_by_id[case.id] = our_outcomes(self.data, case)
        return self.outcomes_by_id[case.id]

    def chance(self, case) -> float:
        if case.id not in self.chance_by_id:
            self.chance_by_id[case.id] = float(our_chance(self.outcomes(case), case))
        return self.chance_by_id[case.id]


@pytest.fixture(scope="module")
def ours(data):
    return Ours(data)


# --- the oracle itself ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", IDS)
def test_the_rerun_of_the_coe_kernel_gives_the_frozen_probability(coe, case_id):
    assert coe[case_id]["probability"] == pytest.approx(FROZEN_COE[case_id], rel=1e-12, abs=0)


@pytest.mark.parametrize("case_id", IDS)
def test_coes_side_totals_are_the_docs(coe, case_id):
    assert coe[case_id]["pool_totals"] == DOC_TOTALS[case_id]


@pytest.mark.parametrize("case_id", IDS)
def test_every_target_is_the_same_tier_in_both_sources(data, ours, coe, case_id):
    """The aid alone is not a tier: side, required level and value range must match (Life9 / Life8)."""
    case = BY_ID[case_id]

    checked = check_correspondences(data, case, ours.outcomes(case), coe[case_id])

    assert checked == len(case.targets) + (case.forced_mod is not None)


# --- our engine against the oracle ----------------------------------------------------------------


@pytest.mark.parametrize("case_id", IDS)
def test_our_chance_is_within_the_investigation_threshold_of_coes(ours, coe, case_id):
    difference = relative_percent(ours.chance(BY_ID[case_id]), coe[case_id]["probability"])

    assert abs(difference) < THRESHOLD_PERCENT


@pytest.mark.parametrize("case_id", IDS)
def test_the_difference_with_coe_is_the_one_measured(ours, coe, case_id):
    difference = relative_percent(ours.chance(BY_ID[case_id]), coe[case_id]["probability"])

    assert difference == pytest.approx(MEASURED_PERCENT[case_id], abs=DRIFT_PERCENT)


# --- the side totals ------------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", ["C01", "C02", "C06"])
def test_our_side_totals_are_coes_and_the_docs(ours, coe, case_id):
    totals = our_side_totals(ours.outcomes(BY_ID[case_id]))

    assert totals == coe[case_id]["pool_totals"] == DOC_TOTALS[case_id]


def test_the_amulet_pool_has_800_more_suffix_weight_than_coes(ours, coe):
    case = BY_ID["C09"]

    totals = our_side_totals(ours.outcomes(case))

    assert totals["prefix"] == coe["C09"]["pool_totals"]["prefix"]
    assert totals["suffix"] == coe["C09"]["pool_totals"]["suffix"] + 800


def test_that_difference_is_the_battle_royale_cast_speed_suffix(data, ours):
    case = BY_ID["C09"]
    royale = data.mods[ROYALE]
    family = next(f for f in ours.outcomes(case).pool if f.family == royale.families[0])
    assert (royale.generation_type, royale.required_level) == ("suffix", 4)
    assert next(e.weight for e in family.mods if e.mod.id == ROYALE) == 800

    without = our_outcomes_as_coe_pools(data, case, dropped=(ROYALE,))

    assert our_side_totals(without) == DOC_TOTALS["C09"]


# --- what is left of the amulet's difference with the prototype ----------------------------------


@pytest.mark.parametrize("case_id", ["C01", "C02", "C06"])
def test_the_engine_still_gives_the_prototypes_own_chance(ours, case_id):
    assert ours.chance(BY_ID[case_id]) == pytest.approx(PROTOTYPE_OURS[case_id], rel=1e-12, abs=0)


def test_c09_is_the_prototypes_chance_without_the_royale_mod_and_with_split_gem_levels(data):
    """The two differences of today's amulet pool explain the whole move from the prototype's number."""
    case = BY_ID["C09"]

    regrouped = our_outcomes_as_coe_pools(data, case, dropped=(ROYALE,), split=(GEM_LEVELS,))

    assert float(our_chance(regrouped, case)) == pytest.approx(PROTOTYPE_OURS["C09"], rel=1e-12, abs=0)


def test_c09_without_the_royale_mod_alone_is_half_a_percent_from_coe(data, coe):
    case = BY_ID["C09"]

    without = our_outcomes_as_coe_pools(data, case, dropped=(ROYALE,))

    difference = relative_percent(float(our_chance(without, case)), coe["C09"]["probability"])
    assert difference == pytest.approx(-0.5301, abs=0.01)
