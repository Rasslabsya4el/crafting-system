"""The reconciliation on the real files: every benchmark target against its buy spec, its price entry and the game data (#412).

One test per (target, slot). A slot with a known disagreement (`known.py`) is a strict `xfail` naming its issue and its owner
rule: the test fails when a NEW disagreement appears (an unknown slot disagrees) and when a known one DISAPPEARS (the strict
xfail then passes unexpectedly). The game data is the raw repoe-fork export in `CRAFTING_CACHE_DIR`; without it the tests skip
with the message CI reads as missing data. Rules: OR-3 (the tier the price was taken for), OR-26 (roots), OR-29 (issues).
"""

import re

import pytest

from .checks import reconcile_files, slots
from .export import REPO_ROOT, ExportMissing, load_export
from .files import buy_spec_of, read_buy_specs, read_targets
from .known import KNOWN
from .ladder import base_ids_of, ladder

TARGETS = read_targets()
SPECS = read_buy_specs()
CASES = [(target.name, slot) for target in TARGETS for slot in slots(target, buy_spec_of(target, SPECS))]


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


def test_every_target_file_is_checked():
    assert {target.name for target in TARGETS} == {slot_target for slot_target, _ in CASES}
    assert len(TARGETS) >= 14


def test_every_known_disagreement_names_a_slot_an_issue_and_a_rule():
    rules = (REPO_ROOT / "docs" / "owner-rules.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^### (OR-\d+)\.", rules, flags=re.MULTILINE))

    assert set(KNOWN) <= set(CASES)
    for key, known in KNOWN.items():
        assert re.fullmatch(r"#\d+", known.issue), key
        assert known.rule in defined, key
        assert known.why, key


def test_the_r12_start_mod_tier_is_a_known_strict_xfail():
    known = KNOWN[("r12-lightning-amulet", "start_mod.LightningResist2.tier")]

    assert known.issue == "#403"
    assert known.rule == "OR-3"


def test_the_ladder_puts_the_r12_start_mod_at_tier_7_of_8_on_the_paua_amulet(export):
    (paua,) = base_ids_of(export.bases, "Paua Amulet")

    tiers = ladder(export.mods, export.bases[paua]["tags"], "LightningResist2")

    assert tiers["LightningResist2"] == 7
    assert len(tiers) == 8
    assert tiers["LightningResist8"] == 1
    assert tiers["LightningResist1"] == 8
