"""Report / cli (ADR-0015). May import only: data, rules, items, actions, abstraction, solver, risk, simulator, prices, targets, planner.

`python -m crafting_system.cli TARGET.yaml` plans a target: it reads the YAML target, the price file
and the pinned game data, asks the planner for the cheapest policy (`planner.plan_target`), prints a short text tree (what to do in each
state, the odds of each outcome, the mean cost and p90) and writes the policy as JSON. `--verify`
runs the policy on concrete items with the simulator and compares the mean with the computed one.

The report and the command line are one module here (ADR-0018 lists them as `report` / `cli`). Planning is not: it is the module
`planner` (ADR-0018, ticket #880), and this package reaches it only through its public names (`tests/test_layering.py`). What is here:

* `main(argv)`: the command, and `main(["benchmark", "--out", DIR])`: the solver and the given route of every
  benchmark route, the published odds, machine info and run times, written to `benchmark.json`.
* `build_report(plan, data)`, `render_text(report)`, `policy_document(report)`: the outputs.
* `first_step` (`_start_step`, ticket #331): a start made at a vendor opens the report with its own first step: the bill with counts,
  the recipes with their tiers, the item that comes back and the start price, in the text, the JSON and row 1 of the route page.
* `verify(data, plan)`: the simulator against the computed mean (a normal-approximate interval); for an approximate
  plan, the lifted policy (`_lift`) against the certified interval, with a simulated p90 and CVaR.
* `weight_share`, `start_shares`: the guide's single-draw weight shares from the pool builder.
* `parse_route`, `load_route`, `evaluate_route`: a given route (rules in YAML) read and evaluated as a fixed
  policy with `risk.evaluate`; `--route ROUTE.yaml` prints it next to the policy, first divergence and gaps included.
* `write_route_page(path, report, data, ...)`: the route view, one self-contained HTML page next to the JSON
  (`<target>.route.html`): the goal card, then a row per step with its card and the item after it; the buy step of a
  target that buys its start item gets the trade-site search link of the buy spec computed from the target. The page model is `_route_view`, the HTML `_route_html`.

The planner's names this package gave out before the move (`make_plan`, `plan_with_starts`, `Plan`, `Offer`, `offers_for`, the start
records, ...) are still importable from here, unchanged, for the tests and tools that read them from here.

The page's maths (`_reach`, `_route_flow`, `_route_chain`) also tells the planner what the page cannot show of a finished plan
(`_page_limits`, named to the planner below; issue #882).

Costs are in Chaos Orbs. The click cost of a Harvest reforge is its lifeforce price times the
count in the rules registry (`harvest_reforge.lifeforce_cost`); the start item costs what the price
file says under the price key computed from the target (a trade-API price, a hand override on top), or
`--start-price`.
"""

from crafting_system.planner import (
    RESTART,
    STRANDS_OFF,
    BuyStartItem,
    ConsideredStart,
    DroppedOffer,
    Limit,
    Offer,
    OfferSet,
    Plan,
    PlanError,
    PricedOffer,
    ReadingChoice,
    RefusedStart,
    StartCandidate,
    StartChoice,
    StartContext,
    StartList,
    StartPrice,
    StartSource,
    StrandSetting,
    bought_base_starts,
    default_offers,
    make_plan,
    offers_for,
    plan_with_starts,
    present_with,
    price_offers,
    strand_setting,
    vendor_recipe_starts,
)
from ._main import main
from ._report import Report, build_report, policy_document, render_text
from ._route import Divergence, Gap, Route, RouteError, RouteResult, Rule, When, evaluate_route, load_route, parse_route
from ._shares import WeightShare, start_shares, weight_share
from ._start_step import FirstStep, first_step
from ._verify import Verification, verify
from ._page_limits import page_limits as _page_limits

present_with(_page_limits)  # a finished plan lists what the page cannot show of it; the maths is this package's (issue #882)

__all__ = [
    "RESTART",
    "STRANDS_OFF",
    "BuyStartItem",
    "ConsideredStart",
    "Divergence",
    "DroppedOffer",
    "Gap",
    "Limit",
    "Offer",
    "OfferSet",
    "Plan",
    "PlanError",
    "PricedOffer",
    "Report",
    "Route",
    "RouteError",
    "ReadingChoice",
    "RefusedStart",
    "RouteResult",
    "Rule",
    "StartCandidate",
    "StartChoice",
    "StartContext",
    "StartList",
    "StartPrice",
    "StartSource",
    "StrandSetting",
    "Verification",
    "WeightShare",
    "When",
    "bought_base_starts",
    "build_report",
    "default_offers",
    "evaluate_route",
    "load_route",
    "main",
    "make_plan",
    "offers_for",
    "parse_route",
    "plan_with_starts",
    "policy_document",
    "price_offers",
    "render_text",
    "start_shares",
    "strand_setting",
    "vendor_recipe_starts",
    "verify",
    "weight_share",
]
