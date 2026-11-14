"""The `Requirements:` line of the text report and the `requirements` of the JSON policy say a k-of-n group once, as the page does (tickets #551, #630, OR-15).

Reading `plan.leaf_labels` as a flat list said that every member of a group is required: for R05 Life and all three resistances.
The line is built from the target's requirements: the plain ones, then each group once as "at least k of n of: a (prefix); b (suffix)".
"""

import json
from pathlib import Path
from types import SimpleNamespace

from abstraction_support import real_game_data
from items_support import DATA
from route_view_support import COLD_REQ, LIFE, belt

from crafting_system.planner._plan import leaf_labels
from crafting_system.cli._report import FORMAT, requirements_document, requirements_text
from crafting_system.targets import KOfN, StartKind, Target, load_target

# R05 as it was read before #895 ("at least 1 of Life and the three resistances"): the real group these texts were written for
R05 = Path(__file__).resolve().parent / "real_targets" / "r05-life-or-resistance.yaml"


def stand_in(data, target):
    """What `requirements_text` reads of a plan: the target, its leaf labels and the data of its abstraction."""
    return SimpleNamespace(target=target, leaf_labels=leaf_labels(target), abstraction=SimpleNamespace(data=data))


def test_a_group_is_said_once_with_the_side_of_each_member_and_a_plain_requirement_stays_plain():
    start = belt()
    target = Target(start.base_id, start.item_level, frozenset(), (COLD_REQ, KOfN(1, (LIFE, COLD_REQ))), start, start=StartKind.BOUGHT)

    line = requirements_text(stand_in(DATA, target))

    plain, group = line.split("; at least ")
    assert "at least" not in plain  # the plain requirement comes first and says no group
    assert group.startswith("1 of 2 of: ") and line.count("at least") == 1
    assert group.count("(prefix)") + group.count("(suffix)") == 2  # every member says its side in words


def test_r05_does_not_read_as_if_life_and_all_three_resistances_were_required():
    data = real_game_data()
    target = load_target(R05, data)

    line = requirements_text(stand_in(data, target))

    plain, group = line.split("; at least ")
    assert "IncreasedLife" not in plain and "Resistance" not in plain  # only the attributes and the Strength are required outright
    assert group.startswith("1 of 4 of: ") and group.count(";") == 3
    assert group.count("(prefix)") == 1 and group.count("(suffix)") == 3  # Life takes one of the three open prefixes, the resistances suffixes


# --- the JSON policy keeps the group (ticket #630) ------------------------------------------------------------------------------


def test_the_json_keeps_the_group_apart_from_the_plain_requirements():
    start = belt()
    target = Target(start.base_id, start.item_level, frozenset(), (COLD_REQ, KOfN(1, (LIFE, COLD_REQ))), start, start=StartKind.BOUGHT)
    plan = stand_in(DATA, target)

    found = requirements_document(plan)

    assert set(found) == {"plain", "groups"}
    assert found["plain"] == [leaf_labels(target)[0]]
    [group] = found["groups"]
    assert group["at_least"] == 1 and len(group["of"]) == 2
    assert [member["requirement"] for member in group["of"]] == list(leaf_labels(target)[1:])  # the members keep the order of the target
    assert all(member["side"] in ("prefix", "suffix") for member in group["of"])
    json.dumps(found)  # strict JSON


def test_a_group_inside_a_group_is_kept_inside_it():
    start = belt()
    target = Target(start.base_id, start.item_level, frozenset(), (KOfN(2, (LIFE, KOfN(1, (COLD_REQ, LIFE)), COLD_REQ)),), start, start=StartKind.BOUGHT)

    found = requirements_document(stand_in(DATA, target))

    assert found["plain"] == []
    [outer] = found["groups"]
    assert outer["at_least"] == 2 and len(outer["of"]) == 3
    inner = outer["of"][1]
    assert inner["at_least"] == 1 and [member["requirement"] for member in inner["of"]] == list(leaf_labels(target)[1:3])
    assert "requirement" in outer["of"][0] and "requirement" in outer["of"][2]


def test_r05_json_does_not_list_life_and_the_resistances_as_required():
    data = real_game_data()
    target = load_target(R05, data)

    found = requirements_document(stand_in(data, target))

    assert not any("IncreasedLife" in label or "Resistance" in label for label in found["plain"])  # only the attributes and the Strength are required outright
    [group] = found["groups"]
    assert group["at_least"] == 1 and len(group["of"]) == 4
    assert [member["side"] for member in group["of"]].count("prefix") == 1 and [member["side"] for member in group["of"]].count("suffix") == 3
    assert {label for member in group["of"] for label in [member["requirement"]]} <= set(leaf_labels(target))
    assert len(found["plain"]) + len(group["of"]) == len(leaf_labels(target))  # every leaf is said once


def test_the_format_name_moved_with_the_shape_of_requirements():
    assert FORMAT == "crafting-system-policy/3"
