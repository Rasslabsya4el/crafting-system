"""`benchmark`: every place where the planner and the guide's route part, and the review line (ticket #554, audit TESTS-22 part 1).

`benchmark` used to check one side: the planner is not dearer than the guide. A planner far cheaper than the guide passed in
silence, and that is as likely a defect (a missed cost, a wrong chance, a mechanic the guide knows and we do not) as a find. So each
benchmark route with a given route now carries:

* every state of the planner's main line where the route takes another action than the planner, each in plain words (what the item
  is, what the guide does, what the planner does) with the chance a run visits the state under the planner's policy and under the
  route's own (`_route_flow.reach_of`, the visit solve of the route page; the item is told by `describe_state`);
* the ratio planner mean / guide mean;
* a review line, one value of the config (`[benchmark] review_ratio`): a ratio below it is "needs a human". The line is a prompt for
  a person to look, never a cut of the search (OR-12), and a planner dearer than the guide stays a failed check as before.

The lines are sorted by the larger of the two chances; lines past `SHOWN` are counted, with the sum of their chances under each policy
(a sum over states, so a run that visits two of them is counted twice), never dropped in silence. A chance that is not measured is None
(a state from which the route cannot finish), and one that is only an upper bound says so (`exact` false).
"""

import time

from crafting_system.abstraction import CompressedState
from crafting_system.data import GameData

from . import _packed
from ._plan import Plan
from ._report import describe_state, number_states, percent
from ._route import Divergence, RouteResult
from ._route_chain import chain_of_plan
from ._route_flow import Chain, Reach, chain_of_policy, reach_of

DESCRIPTION_CUT = 80  # the characters of an item description in the `needs a human` row, which names three states on one line
SHOWN = 10  # the lines of divergence shown for a route; the rest are counted, with their chances, in `more`


def mean_ratio(solver_mean: float | None, given_mean: float | None) -> float | None:
    """Planner mean / guide mean, or None when either never finishes or the guide costs nothing."""
    if solver_mean is None or given_mean is None or given_mean <= 0:
        return None
    return solver_mean / given_mean


def review_of(ratio: float | None, line: float) -> dict:
    """The review of a route: its ratio, the review line, and whether a human should look (the ratio is below the line)."""
    return {"line": line, "ratio": ratio, "needs_human": ratio is not None and ratio < line}


def divergences_of(plan: Plan, result: RouteResult, data: GameData) -> dict:
    """`{"count", "shown", "more"}`: the divergences of `result` from the planner's policy, the top `SHOWN` as lines and the rest counted."""
    found = result.divergences
    if not found:
        return {"count": 0, "shown": [], "more": None}
    began = time.perf_counter()
    say = _packed.PROGRESS or (lambda _text: None)  # a measuring script sets it to see each phase as it ends
    planner = chain_of_plan(plan)
    route = _route_chain(plan, result)
    say(f"divergences: {len(found):,}; the chains of the planner ({planner.m:,} states) and of the route ({route.m:,}) made ({time.perf_counter() - began:.1f} s)")
    planner_reach = _chances(planner, [d.state for d in found])
    say(f"divergences: the visit chances under the planner ({time.perf_counter() - began:.1f} s)")
    route_reach = _chances(route, [d.state for d in found])
    say(f"divergences: the visit chances under the route ({time.perf_counter() - began:.1f} s)")
    ids = number_states(plan)
    rows = [
        _row(plan, data, ids, divergence, planner_reach[number], route_reach[number])
        for number, divergence in enumerate(found)
    ]
    rows.sort(key=lambda row: -max(row["planner_chance"] or 0.0, row["route_chance"] or 0.0))
    rest = rows[SHOWN:]
    more = (
        None
        if not rest
        else {
            "count": len(rest),
            "planner_chance": sum(row["planner_chance"] or 0.0 for row in rest),
            "route_chance": sum(row["route_chance"] or 0.0 for row in rest),
            # the sums count a chance that is not measured as 0 and a bound as the number it is: these say how much of each sum is that
            "planner_chance_exact": all(row["planner_chance_exact"] for row in rest if row["planner_chance"] is not None),
            "route_chance_exact": all(row["route_chance_exact"] for row in rest if row["route_chance"] is not None),
            "planner_unmeasured": sum(row["planner_chance"] is None for row in rest),
            "route_unmeasured": sum(row["route_chance"] is None for row in rest),
        }
    )
    return {"count": len(rows), "shown": rows[:SHOWN], "more": more}


def _route_chain(plan: Plan, result: RouteResult) -> Chain:
    """The route's policy on item states: the chain the packed reading kept, else made from the route's policy with its gaps as states with no action."""
    if result.chain is not None:
        return result.chain  # type: ignore[return-value]
    reasons = {gap.state: gap.reason for gap in result.gaps}
    return chain_of_policy(plan.start, result.policy, plan.is_goal, reasons)


def _chances(chain: Chain, states: list[CompressedState]) -> list[Reach]:
    """The chance a run of `chain` visits each of `states`; 0 for a state the chain never reaches."""
    index = {state: i for i, state in enumerate(chain.states)}
    wanted = [index[state] for state in states if state in index]
    reached = iter(reach_of(chain, wanted))
    return [next(reached) if state in index else Reach(0.0) for state in states]


def _row(plan: Plan, data: GameData, ids: dict, divergence: Divergence, planner: Reach, route: Reach) -> dict:
    return {
        "state": ids.get(divergence.state),
        "description": describe_state(plan, data, divergence.state),
        "solver_action": divergence.solver_action,
        "route_action": divergence.route_action,
        "planner_chance": planner.chance,
        "planner_chance_exact": planner.exact,
        "route_chance": route.chance,
        "route_chance_exact": route.exact,
    }


# --- the words ----------------------------------------------------------------------------------


def chance_text(chance: float | None, exact: bool = True) -> str:
    """A chance for a line: `?` when not measured, `at most` when only an upper bound."""
    if chance is None:
        return "?"
    return percent(chance) if exact else "at most " + percent(chance)


def _one_line(text: str) -> str:
    """A description on one line: a mod that reads on several lines in the game (a bench mod) is joined with ` / `."""
    return " / ".join(part.strip() for part in text.splitlines() if part.strip())


def _cut(text: str, length: int = DESCRIPTION_CUT) -> str:
    """`text` cut to `length` characters, with `...` when something was left out."""
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


def _sum_text(total: float) -> str:
    """A sum of chances, which may pass 1: a plain number, not a percentage capped at 100%."""
    return f"{total:.4g}"


def divergence_lines(block: dict) -> list[str]:
    """The lines of one route's divergences: the count, one line to a state, and the rest counted with their chances."""
    count = block["count"]
    if not count:
        return []
    lines = [f"  divergences: {count} state(s) of the planner's main line where the guide does something else, the likeliest first"]
    for row in block["shown"]:
        name = row["state"] or "a state"
        lines.append(
            f"    {name}: {_one_line(row['description'])}: the guide does {row['route_action']}, the planner does {row['solver_action']}"
            f" (the planner visits it with chance {chance_text(row['planner_chance'], row['planner_chance_exact'])},"
            f" the guide with chance {chance_text(row['route_chance'], row['route_chance_exact'])})"
        )
    more = block["more"]
    if more is not None:
        lines.append(
            f"    and {more['count']} more, visited {_more_text(more, 'planner')} times by the planner and {_more_text(more, 'route')} times by the guide, "
            "summed over the states (a run that visits two of them counts twice)"
        )
    return lines


def _more_text(more: dict, side: str) -> str:
    """One sum of the hidden rows: `at most` when any of its chances is a bound, and how many states are left out of it because their chance is not measured."""
    text = ("" if more.get(f"{side}_chance_exact", True) else "at most ") + _sum_text(more[f"{side}_chance"])
    unmeasured = more.get(f"{side}_unmeasured", 0)
    return f"{text} (and {unmeasured} not measured, left out)" if unmeasured else text


def review_lines(label: str, ratio_block: dict, divergences: dict) -> list[str]:
    """The ratio line of a route and, below the review line, the `needs a human` row that names the top divergences."""
    ratio = ratio_block["ratio"]
    if ratio is None:
        return []
    lines = [f"  planner mean / {label} mean: {ratio:.3f} (review line {ratio_block['line']:g})"]
    if ratio_block["needs_human"]:
        lines.append(
            f"  NEEDS A HUMAN: the planner costs {percent(ratio)} of the {label}, below the review line {percent(ratio_block['line'])}: "
            "a missed cost, a wrong chance or a mechanic the guide knows would all look like this"
        )
        top = divergences["shown"][:3]
        if top:
            lines.append(
                "    top divergences: "
                + "; ".join(
                    f"{row['state'] or 'a state'} ({_cut(_one_line(row['description']))}): the guide does {row['route_action']}, the planner does {row['solver_action']}"
                    for row in top
                )
            )
    return lines
