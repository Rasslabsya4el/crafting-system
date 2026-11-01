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
* `plan_with_starts(data, target, prices)`: `make_plan` for a target whose start item may also be made by a vendor recipe: it plans
  each start option (`_start_options`) and keeps the cheapest total of start price and expected cost (ADR-0059, `_starts`); the
  comparison is `Plan.starts`. With the setting `recipe_starts` off it is `make_plan`.
  A start made at a vendor opens the report with its own first step (`first_step`, `_start_step`, ticket #331): the bill with counts,
  the recipes with their tiers, the item that comes back and the start price, in the text, the JSON and row 1 of the route page.
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
from ._plan import STRANDS_OFF, Plan, PlanError, StartPrice, StrandSetting, make_plan, strand_setting
from ._report import Report, build_report, policy_document, render_text
from ._route import Divergence, Gap, Route, RouteError, RouteResult, Rule, When, evaluate_route, load_route, parse_route
from ._shares import WeightShare, start_shares, weight_share
from ._start_options import StartContext, StartList, StartSource, vendor_recipe_starts
from ._start_step import FirstStep, first_step
from ._start_types import ConsideredStart, ReadingChoice, RefusedStart, StartCandidate, StartChoice
from ._starts import plan_with_starts
from ._verify import Verification, verify

__all__ = [
    "RESTART",
    "STRANDS_OFF",
    "BuyStartItem",
    "ConsideredStart",
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
