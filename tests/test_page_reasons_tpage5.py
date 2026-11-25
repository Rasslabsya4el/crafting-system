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
    grouped = [line for line in goals if "2 of these 3" in line]
    assert grouped, goals
    assert all(line.startswith("2 of these 3: +# to ToyS") for line in grouped), grouped
    assert not any(line.startswith("+# to ToyS") for line in goals), goals  # a member is never a mod the target asks by itself
    assert any(line.startswith("+# to ToyP1") for line in goals), goals  # a leaf asked by itself stays as it was


# --- #1625: the unveil and its pick are one move ------------------------------------------------------------


def test_an_unveil_and_its_pick_are_joined_into_one_move_with_the_product_of_their_chances_and_their_summed_cost():
    from crafting_system.cli._route_flow import chain_of_policy
    from crafting_system.cli._route_unveil import joined_picks
    from crafting_system.solver import Action

    # s: unveil -> o1 (1/4) or o2 (3/4); on o1 the pick reaches the goal g; on o2 the pick reaches g (1/3) or goes back to s (2/3)
    policy = {
        "s": Action("Unveil", 0.5, (("o1", 1), ("o2", 3))),
        "o1": Action("Pick 1", 0.25, (("g", 1),)),
        "o2": Action("Pick 2", 0.75, (("g", 1), ("s", 2))),
    }
    chain = chain_of_policy("s", policy, lambda state: state == "g")
    joined, picks = joined_picks(chain, lambda state: state.startswith("o"))

    assert list(joined.states) == ["s"] and list(joined.goals) == ["g"]
    k = int(joined.kernel[0])
    lo, hi = joined.kernels.k_ptr[k], joined.kernels.k_ptr[k + 1]
    moves = dict(zip(joined.kernels.k_succ[lo:hi].tolist(), joined.kernels.k_prob[lo:hi].tolist(), strict=True))
    assert moves == {1: 1 / 4 + 3 / 4 * 1 / 3, 0: 3 / 4 * 2 / 3}  # the goal is m + 0 = 1, the state itself 0
    assert joined.cost[0] == 0.5 + 1 / 4 * 0.25 + 3 / 4 * 0.75
    assert [(p.offered, p.chance, p.pick.label) for p in picks["s"]] == [("o1", 0.25, "Pick 1"), ("o2", 0.75, "Pick 2")]
    assert joined.keys[joined.key[0]] == ("action", "Unveil") and joined.action_of(0).label == "Unveil"


def test_a_chain_where_an_item_holding_an_offer_is_reached_otherwise_is_left_as_it_is():
    from crafting_system.cli._route_flow import chain_of_policy
    from crafting_system.cli._route_unveil import joined_picks
    from crafting_system.solver import Action

    policy = {
        "s": Action("Unveil", 0.5, (("o1", 1), ("t", 1))),  # not every outcome holds an offer
        "o1": Action("Pick 1", 0.25, (("g", 1),)),
        "t": Action("Chaos", 1.0, (("g", 1),)),
    }
    chain = chain_of_policy("s", policy, lambda state: state == "g")
    assert joined_picks(chain, lambda state: state.startswith("o")) == (chain, {})
