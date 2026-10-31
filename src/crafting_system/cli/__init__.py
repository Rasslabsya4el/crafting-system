"""Report / cli (ADR-0015). May import only: data, rules, items, actions, abstraction, solver, risk, simulator, prices, targets.

`python -m crafting_system.cli TARGET.yaml` plans a target: it reads the YAML target, the price file
and the pinned game data, solves the cheapest policy, prints a short text tree (what to do in each
state, the odds of each outcome, the mean cost and p90) and writes the policy as JSON. `--verify`
runs the policy on concrete items with the simulator and compares the mean with the computed one.

The report and the command line are one module here (ADR-0018 lists them as `report` / `cli`):

* `make_plan(data, target, prices)`: targets -> prices -> abstraction -> solver -> risk, as a `Plan`.
* `build_report(plan, data)`, `render_text(report)`, `policy_document(report)`: the outputs.
* `verify(data, plan)`: the simulator against the computed mean (a normal-approximate interval).
* `weight_share`, `start_shares`: the guide's single-draw weight shares from the pool builder.
* `main(argv)`: the command.

Costs are in Chaos Orbs. The click cost of a Harvest reforge is its lifeforce price times the
count in the rules registry (`harvest_reforge.lifeforce_cost`); the start item costs what the price
file says under the target's `start_price` name (a trade-API price, a hand override on top), or
`--start-price`.
"""

from ._main import main
from ._offers import DroppedOffer, Offer, PricedOffer, default_offers, price_offers
from ._plan import Plan, PlanError, StartPrice, make_plan
from ._report import Report, build_report, policy_document, render_text
from ._shares import WeightShare, start_shares, weight_share
from ._verify import Verification, verify

__all__ = [
    "DroppedOffer",
    "Offer",
    "Plan",
    "PlanError",
    "PricedOffer",
    "Report",
    "StartPrice",
    "Verification",
    "WeightShare",
    "build_report",
    "default_offers",
    "main",
    "make_plan",
    "policy_document",
    "price_offers",
    "render_text",
    "start_shares",
    "verify",
    "weight_share",
]
