"""The `Requirements:` line of the text report says a k-of-n group once, as the page does (ticket #551, OR-15).

Reading `plan.leaf_labels` as a flat list said that every member of a group is required: for R05 Life and all three resistances.
The line is built from the target's requirements: the plain ones, then each group once as "at least k of n of: a (prefix); b (suffix)".
"""

from pathlib import Path
from types import SimpleNamespace

from abstraction_support import real_game_data
from items_support import DATA
from route_view_support import COLD_REQ, LIFE, belt

from crafting_system.cli._plan import leaf_labels
from crafting_system.cli._report import requirements_text
from crafting_system.targets import KOfN, StartKind, Target, load_target

R05 = Path(__file__).resolve().parents[1] / "examples" / "targets" / "r05-strength-ring.yaml"


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
