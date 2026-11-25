"""What the route page says of a step a player would otherwise read as a mistake or as asking too much (#1622, #1625, #1629, #1632).

* #1622: a step's Goal named each member of a k-of-n group as a mod the target asks by itself (R13: Fire, Cold and Lightning Resistance on a
  belt that needs 2 of 3, read as four suffixes on a three-suffix belt). The members a step aims at are one line, said with their group.
"""

import dataclasses
import textwrap

from items_support import DATA  # noqa: F401  (the fixture's data loads the rules the toy plans read)
from listing_support import prices, rare_toy

from crafting_system.cli import make_plan
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.targets import parse_target

GROUP_TARGET = """\
base: Toy Listing Boots
item_level: 86
start_item:
  rarity: rare
start: given
requirements:
  - family: ToyP1
    min_tier: any
  - at_least: 2
    of:
      - family: ToyS1
        min_tier: any
      - family: ToyS2
        min_tier: any
      - family: ToyS3
        min_tier: any
"""


def field(row, label: str) -> list[str]:
    return [line.text for entry in row.fields if entry.label == label for line in entry.lines]


def test_a_step_goal_says_the_members_of_a_k_of_n_group_with_their_group_never_alone():
    data = rare_toy()
    aim = dataclasses.replace(parse_target(textwrap.dedent(GROUP_TARGET), data, source="toy-group.yaml"), actions=("chaos-orb",))
    plan = make_plan(data, aim, prices(None))

    rows = build_section(route_input(plan), data, None).rows
    goals = [line for row in rows for line in field(row, "Goal")]
    grouped = [line for line in goals if "the target asks 2 of" in line]
    assert grouped, goals
    assert all(line.startswith("one of +# to ToyS") and line.endswith("(the target asks 2 of these 3)") for line in grouped), grouped
    assert not any(line.startswith("+# to ToyS") for line in goals), goals  # a member is never a mod the target asks by itself
    assert any(line.startswith("+# to ToyP1") for line in goals), goals  # a leaf asked by itself stays as it was
