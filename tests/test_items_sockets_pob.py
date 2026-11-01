"""The class maximum against Path of Building's `socketLimit` (ADR-0046, ticket #227): a test oracle, not a source.

The oracle file `tests/fixtures/sockets/pob_socket_limits.json` holds the `socketLimit` of the 408 bases of five item classes
(body armour, helmet, gloves, boots, bow) that the read-only prototype (branch `archive/prototype`) extracted from Path of Building.
`items.class_maximum` is compared base by base on the real 3.29.3.3 dump. Every base where the two differ is a finding for the
pull request and changes nothing silently: `EXPECTED_DIFFERENCES` lists them, and the test fails when the list changes either way.
Run with `-s` to print the report. The tests skip cleanly when the dump is not cached (CI fetches it).
"""

import json
import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from repoe_support import no_network  # noqa: F401

from crafting_system.items import SOCKET_ITEM_CLASSES, class_maximum

ORACLE = Path(__file__).resolve().parent / "fixtures" / "sockets" / "pob_socket_limits.json"
COVERED = {"Body Armour", "Boots", "Bow", "Gloves", "Helmet"}
EXPECTED_DIFFERENCES: list[tuple[str, str, int, int]] = []  # (base id, item class, our maximum, Path of Building's socketLimit)
NOT_IN_ORACLE = {  # bases of the five classes that the prototype's Path of Building extraction does not hold
    "Metadata/Items/Armours/Boots/BootsDescent1": "Avian Slippers",
    "Metadata/Items/Armours/Helmets/HelmetDemigods1": "Golden Visage",
    "Metadata/Items/Armours/BodyArmours/BodyStrTemp": "Kaom's Plate",
    "Metadata/Items/Armours/Boots/BootsStrTemp": "Kaom's Greaves",
}


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def oracle():
    return json.loads(ORACLE.read_text(encoding="utf-8"))["bases"]


def our_bases(real, name: str, item_class: str):
    """The bases of the real data that Path of Building's `name` stands for: the same name, or (for the three Two-Toned Boots) the name without its parenthesis."""
    found = [base for base in real.base_items.values() if base.name == name and base.item_class == item_class]
    if not found:
        short = re.sub(r" \(.*\)$", "", name)
        found = [base for base in real.base_items.values() if base.name == short and base.item_class == item_class]
    return found


def compare(real, oracle):
    differences, unmatched = [], []
    seen: set[str] = set()
    for row in oracle:
        bases = our_bases(real, row["name"], row["type"])
        if not bases:
            unmatched.append(row["name"])
        for base in bases:
            seen.add(base.id)
            ours = class_maximum(base)
            if ours != row["socketLimit"]:
                differences.append((base.id, base.item_class, ours, row["socketLimit"]))
    ours_only = {
        base.id: base.name for base in real.base_items.values() if base.item_class in COVERED and base.id not in seen
    }
    return differences, unmatched, ours_only


def test_the_oracle_covers_five_classes_and_every_base_has_a_limit(oracle):
    assert len(oracle) == 408
    assert {row["type"] for row in oracle} == COVERED
    assert COVERED <= SOCKET_ITEM_CLASSES
    assert all(isinstance(row["socketLimit"], int) for row in oracle)


def test_every_class_of_the_oracle_has_one_limit_in_path_of_building(oracle):
    assert {(row["type"], row["socketLimit"]) for row in oracle} == {
        ("Body Armour", 6),
        ("Boots", 4),
        ("Bow", 6),
        ("Gloves", 4),
        ("Helmet", 4),
    }


def test_the_class_maximum_differs_from_path_of_building_on_exactly_the_listed_bases(real, oracle, capsys):
    differences, unmatched, ours_only = compare(real, oracle)
    with capsys.disabled():
        print(f"\nPath of Building socketLimit against the class maximum: {len(oracle)} oracle bases, {len(differences)} differ")
        for base_id, item_class, ours, theirs in differences:
            print(f"  {base_id} ({item_class}): ours {ours}, Path of Building {theirs}")
        print(f"  oracle names with no base in the real data: {unmatched or 'none'}")
        print(f"  bases of the five classes the oracle does not hold: {sorted(ours_only.values())}")
        print(f"  classes the oracle does not cover: {sorted(SOCKET_ITEM_CLASSES - COVERED)}")
    assert differences == EXPECTED_DIFFERENCES


def test_every_oracle_base_is_found_in_the_real_data(real, oracle):
    _, unmatched, _ = compare(real, oracle)
    assert unmatched == []


def test_the_bases_the_oracle_does_not_hold_are_the_four_known_ones(real, oracle):
    _, _, ours_only = compare(real, oracle)
    assert ours_only == NOT_IN_ORACLE
    assert all(class_maximum(real.base_items[base_id]) in (4, 6) for base_id in ours_only)
