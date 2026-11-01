"""Report / cli (ADR-0015). May import only: data, rules, items, actions, abstraction, solver, risk, simulator, prices, targets.

`python -m crafting_system.cli TARGET.yaml` plans a target: it reads the YAML target, the price file
and the pinned game data, solves the cheapest policy, prints a short text tree (what to do in each
state, the odds of each outcome, the mean cost and p90) and writes the policy as JSON. `--verify`
runs the policy on concrete items with the simulator and compares the mean with the computed one.

The report and the command line are one module here (ADR-0018 lists them as `report` / `cli`):

* `make_plan(data, target, prices)`: targets -> prices -> abstraction -> solver -> risk, as a `Plan`. Its
  model offers, for the target (`offers_for`): a Chaos Orb, the Harvest reforge of Lightning, every essence
  the item class takes, Remove Crafted Mods, the bench crafts whose mod counts toward a requirement (the
  others are left out and listed, see `offers_for`), and `restart`, buying the start item again.
* `build_report(plan, data)`, `render_text(report)`, `policy_document(report)`: the outputs.
* `verify(data, plan)`: the simulator against the computed mean (a normal-approximate interval); for an approximate
  plan, the lifted policy (`_lift`) against the certified interval, with a simulated p90 and CVaR.
* `weight_share`, `start_shares`: the guide's single-draw weight shares from the pool builder.
* `parse_route`, `load_route`, `evaluate_route`: a given route (rules in YAML) read and evaluated as a fixed
  policy with `risk.evaluate`; `--route ROUTE.yaml` prints it next to the policy, first divergence and gaps included.
* `write_route_page(path, report, data, ...)`: the route view, one self-contained HTML page next to the JSON
  (`<target>.route.html`): the goal card, then a row per step with its card and the item after it; `--buy-spec`
  gives the buy step its trade-site search link. The page model is `_route_view`, the HTML `_route_html`.
* `main(argv)`: the command, and `main(["benchmark", "--out", DIR])`: the solver and the given route of every
  benchmark route, the published odds, machine info and run times, written to `benchmark.json`.

Costs are in Chaos Orbs. The click cost of a Harvest reforge is its lifeforce price times the
count in the rules registry (`harvest_reforge.lifeforce_cost`); the start item costs what the price
file says under the target's `start_price` name (a trade-API price, a hand override on top), or
`--start-price`.
"""

from ._main import main
from ._offers import (
    RESTART,
    BuyStartItem,
    DroppedOffer,
    LeftOut,
    Offer,
    OfferSet,
    PricedOffer,
    default_offers,
    offers_for,
    price_offers,
)
from ._plan import Plan, PlanError, StartPrice, make_plan
from ._report import Report, build_report, policy_document, render_text
from ._route import Divergence, Gap, Route, RouteError, RouteResult, Rule, When, evaluate_route, load_route, parse_route
from ._shares import WeightShare, start_shares, weight_share
from ._verify import Verification, verify

__all__ = [
    "RESTART",
    "BuyStartItem",
    "Divergence",
    "DroppedOffer",
    "Gap",
    "LeftOut",
    "Offer",
    "OfferSet",
    "Plan",
    "PlanError",
    "PricedOffer",
    "Report",
    "Route",
    "RouteError",
    "RouteResult",
    "Rule",
    "StartPrice",
    "Verification",
    "WeightShare",
    "When",
    "build_report",
    "default_offers",
    "evaluate_route",
    "load_route",
    "main",
    "make_plan",
    "offers_for",
    "parse_route",
    "policy_document",
    "price_offers",
    "render_text",
    "start_shares",
    "verify",
    "weight_share",
]
