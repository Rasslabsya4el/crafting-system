"""Smoke tests for S1: PoB ModExplicit.lua key Strength1 (2026-09-20)."""

from pathlib import Path

import pytest

from craftoracle.pob_row import parse_mod_row


SOURCE = Path(__file__).resolve().parents[1] / "sources/pob/Data/ModExplicit.lua"


def _strength1_row() -> str:
    assert SOURCE.is_file(), (
        "S1 source missing: expected sources/pob/Data/ModExplicit.lua "
        "for PoB key Strength1"
    )
    return next(
        line for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if '["Strength1"]' in line
    )


def test_strength1_projection_from_pob_s1() -> None:
    """S1 / Strength1 values are from ModExplicit.lua line 5, read 2026-09-20."""
    parsed = parse_mod_row(_strength1_row())

    assert parsed == {
        "id": "Strength1",
        "type": "Suffix",
        "affix": "of the Brute",
        "level": 1,
        "group": "Strength",
        "weightKey": [
            "ring", "amulet", "belt", "str_armour", "str_dex_armour",
            "str_int_armour", "str_dex_int_armour", "sword", "mace",
            "sceptre", "staff", "axe", "default",
        ],
        "weightVal": [
            1000, 1000, 1000, 1000, 500, 500, 333, 500, 1000, 500, 500,
            500, 0,
        ],
        "modTags": ["attribute"],
    }
    assert len(parsed) == 8
    assert sum(parsed["weightVal"]) == 8333


def test_spec_pob_row_rejects_three_malformed_inputs() -> None:
    """S1 / Strength1 is the source row for the malformed-input variants."""
    row = _strength1_row()
    missing_level = row.replace(" level = 1,", "", 1)
    unequal_weights = row.replace(
        ", 0 }, modTags", " }, modTags", 1
    )

    for malformed in (missing_level, unequal_weights, "return {"):
        with pytest.raises(ValueError):
            parse_mod_row(malformed)
