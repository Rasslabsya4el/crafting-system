"""The reconciliation on the real files: every benchmark target against its buy spec, its price entry and the game data (#412).

One test per (target, slot). A slot with a known disagreement (`known.py`) is a strict `xfail` naming its issue and its owner
rule: the test fails when a NEW disagreement appears (an unknown slot disagrees) and when a known one DISAPPEARS (the strict
xfail then passes unexpectedly). A second test pins the two values of each known disagreement, so one that CHANGES fails too.
The set of checks itself is committed (`expected_checks.txt`) and must equal the set built from the files, so a check cannot
vanish while the suite stays green. The game data is the raw repoe-fork export in `CRAFTING_CACHE_DIR`; without it the tests
skip with the message CI reads as missing data. Rules: OR-3 (the target, the buy spec and the price agree), OR-26, OR-29.
"""

import re

import pytest

from .checks import check_ids, reconcile_files, slots
from .export import REPO_ROOT, ExportMissing, load_export
from .files import buy_spec_of, read_buy_specs, read_targets
from .known import KNOWN
from .ladder import base_ids_of, bases_named, ladder

TARGETS = read_targets()
SPECS = read_buy_specs()
CASES = [(target.name, slot) for target in TARGETS for slot in slots(target, buy_spec_of(target, SPECS))]
EXPECTED = REPO_ROOT / "tests" / "reconcile" / "expected_checks.txt"


def _case(target: str, slot: str):
    known = KNOWN.get((target, slot))
    marks = []
    if known:
        marks.append(
            pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{known.issue} {known.rule}: {known.why}")
        )
    return pytest.param(target, slot, id=f"{target}::{slot}", marks=marks)


@pytest.fixture(scope="module")
def export():
    try:
        return load_export()
    except ExportMissing as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


@pytest.fixture(scope="module")
def results(export):
    return {target.name: reconcile_files(target, SPECS, export) for target in TARGETS}


@pytest.mark.parametrize(("target", "slot"), [_case(*case) for case in CASES])
def test_the_places_agree(results, target, slot):
    found = results[target][slot]

    assert not found, "\n".join(str(item) for item in found)


@pytest.mark.parametrize(("target", "slot"), sorted(KNOWN))
def test_a_known_disagreement_is_exactly_the_pinned_one(results, target, slot):
    known = KNOWN[(target, slot)]

    assert {item.values for item in results[target][slot]} == {known.values}


def test_the_set_of_checks_is_the_committed_one():
    committed = [line for line in EXPECTED.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    built = check_ids(TARGETS, SPECS)

    assert len(committed) == len(set(committed)), "a check is listed twice"
    assert set(built) - set(committed) == set(), "checks built but not committed in expected_checks.txt"
    assert set(committed) - set(built) == set(), "checks committed but no longer built (a start_price or a buy spec lost?)"
    assert built == committed


def test_every_target_file_is_checked_for_how_its_start_item_is_had():
    assert len(TARGETS) >= 14
    for target in TARGETS:
        names = slots(target, buy_spec_of(target, SPECS))
        assert {"start_price.written", "buy_spec.exists"} <= set(names), target.name


def test_every_known_disagreement_names_a_slot_an_issue_and_a_rule():
    rules = (REPO_ROOT / "docs" / "owner-rules.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^### (OR-\d+)\.", rules, flags=re.MULTILINE))

    assert set(KNOWN) <= set(CASES)
    for key, known in KNOWN.items():
        assert re.fullmatch(r"#\d+", known.issue), key
        assert known.rule in defined, key
        assert known.why and known.value_a and known.value_b, key


def test_no_known_disagreement_is_about_a_written_tier():
    """Ticket #484: a start mod writes no tier, so there is no slot that compares one; the R12 row is gone."""
    assert not [key for key in KNOWN if key[1].endswith(".tier")]
    assert ("r12-lightning-amulet", "start_mod.LightningResist2.ladder") not in KNOWN


def test_a_bought_target_with_no_price_key_or_no_buy_spec_fails_unless_it_is_a_known_disagreement(results):
    for target in TARGETS:
        for slot in ("start_price.written", "buy_spec.exists"):
            if results[target.name][slot]:
                assert (target.name, slot) in KNOWN, (target.name, slot)


def test_every_target_says_given_or_bought_and_only_a_bought_one_has_a_price_key():
    for target in TARGETS:
        assert target.start in ("given", "bought"), target.name
        assert (target.start_price is not None) == (target.start == "bought"), target.name
    assert [target.name for target in TARGETS if target.start == "given"] == ["j01-cobalt-life-attack-speed"]


def test_no_known_disagreement_is_left_of_the_427_rows_of_targets_without_a_start_price():
    assert not [key for key, known in KNOWN.items() if known.issue == "#427" or key[1] in ("start_price.written", "buy_spec.exists")]


def test_the_ladder_puts_the_r12_start_mod_at_tier_7_of_8_on_the_paua_amulet(export):
    (paua,) = base_ids_of(export.bases, "Paua Amulet")

    tiers = ladder(export.mods, export.bases[paua]["tags"], export.bases[paua]["domain"], "LightningResist2")

    assert tiers["LightningResist2"] == 7
    assert len(tiers) == 8
    assert tiers["LightningResist8"] == 1
    assert tiers["LightningResist1"] == 8


def test_the_movement_speed_ladder_on_sorcerer_boots_has_6_tiers_without_the_battle_royale_copy(export):
    (boots,) = bases_named(export.bases, "Sorcerer Boots")

    tiers = ladder(export.mods, export.bases[boots]["tags"], export.bases[boots]["domain"], "MovementVelocity1")

    assert "MovementVelocity2Royale" in export.mods  # in the data, and spawnable on boots, but never rolled (#248)
    assert "MovementVelocity2Royale" not in tiers
    assert len(tiers) == 6
    assert tiers["MovementVelocity1"] == 6
    assert tiers["MovementVelocity5"] == 2
    assert tiers["MovementVelocity6"] == 1


def test_the_second_leather_belt_is_a_battle_royale_base_and_not_a_name_clash(export):
    assert bases_named(export.bases, "Leather Belt") == ["Metadata/Items/Belts/Belt3"]
    assert "Metadata/Items/Belts/BeltRoyale1" in export.bases
