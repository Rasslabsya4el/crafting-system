"""The planner: a target, prices and settings in, a `Plan` out (ADR-0018, ticket #880). May import only: data, rules, items, actions, abstraction, solver, risk, simulator, prices, targets.

`plan_target(data, target, prices, settings)` is the one entry. It chooses a start (`_starts`, `_start_options`, `_bought_starts`), collects and
prices the actions a run may use (`_offers`), leaves out the ones a state cannot use (`_prune`), picks how the cheapest route is searched
(`_decide`) and searches (`_envelope`, `_envelope_plan` with its bound `_pattern_bound` and `_offer_floor`; the older walks `_packed`,
`_bound_prune`, `_approx`), adds the socket finish (`_finish`), Hinekora's Lock (`_foresight`) and second items (`_donors`), measures the risk
(`_plan`), and says what the answer leaves out (`_limits`). It loads no file, reads no date and prints nothing: `cli` parses the
arguments, loads the inputs, calls the entry and presents the `Plan` (the report, the route page, the benchmark command). It times its own stages (the run's budget, `crafting_system.budget`) and takes the number of worker processes from `crafting_system.parallel`,
and the envelope search reads the memory the process holds against the run's memory limit (`_envelope.resident_mb`): a stop there is said in the answer.

The other names here are what a presenter of a plan reads: the records a `Plan` is made of (its offers, its start options, its limits and
their words, the words of a rule axis), and the pieces `cli` still needs to evaluate a given route on a plan's graph (`offer_action`,
`evaluate_risk`, `packed_risk`, `main_view`, `lumped_policy`, `lumped_view`). `make_plan` and `plan_with_starts` are the entry's own steps,
public while tests and tools still call them by name (issue #883 shrinks this list to the entry and the records). `cli` imports the
planner only through these names, each by a `from crafting_system.planner import ...` (`tests/test_layering.py`).

`present_with` is the seam of issue #882: the page's maths still lives in `cli`, and a finished plan lists what the page cannot show.
Importing `crafting_system.cli` names its page; a plan finished with no presenter named is a `RuntimeError` (`_presenter`).
"""

from ._approx import Approximation
from ._axes import axis_name, axis_what, reading_pair, value_text
from ._bought_starts import bought_base_starts
from ._decide import BUDGET_SECONDS
from ._entry import PlanSettings, plan_target, progress, say_progress_to
from ._foresight import Status as LockStatus
from ._limits import (
    HEADING,
    NOT_COMPUTED,
    PERCENTILE_WORDS,
    SHOWN_LABELS,
    STATE_LINE,
    STEPS,
    STRANDS,
    UNPRICED,
    UNRESOLVED,
    Limit,
    claim,
    figures,
    grouped,
    limit_document,
    limit_text,
    more_labels,
    not_shown,
    ordered,
    unresolved,
)
from ._offers import (
    RESTART,
    BuyStartItem,
    DroppedOffer,
    Offer,
    OfferSet,
    PricedOffer,
    default_offers,
    free_action_cost,
    offers_for,
    price_offers,
    without_ranges,
)
from ._packed import SOLVERS, PackedPolicy, PackedResult, Walked, lumped_policy, lumped_view
from ._plan import (
    GIVEN_SOURCE,
    STRANDS_OFF,
    Plan,
    PlanError,
    StartPrice,
    StrandSetting,
    chance,
    evaluate_risk,
    main_view,
    make_plan,
    offer_action,
    packed_risk,
    strand_setting,
)
from ._presenter import present_with
from ._start_options import ORB_OF_AUGMENTATION, StartContext, StartList, StartSource, base_kind, good_name, vendor_recipe_starts
from ._start_types import (
    NO_TARGET_MOD,
    SOURCE_PLAIN,
    SOURCE_VENDOR_RECIPE,
    ConsideredStart,
    ReadingChoice,
    RefusedStart,
    StartCandidate,
    StartChoice,
)
from ._start_types import Reading as StartReading
from ._starts import plan_with_starts

__all__ = [
    "BUDGET_SECONDS",
    "GIVEN_SOURCE",
    "HEADING",
    "NOT_COMPUTED",
    "NO_TARGET_MOD",
    "ORB_OF_AUGMENTATION",
    "PERCENTILE_WORDS",
    "RESTART",
    "SHOWN_LABELS",
    "SOLVERS",
    "SOURCE_PLAIN",
    "SOURCE_VENDOR_RECIPE",
    "STATE_LINE",
    "STEPS",
    "STRANDS",
    "STRANDS_OFF",
    "UNPRICED",
    "UNRESOLVED",
    "Approximation",
    "BuyStartItem",
    "ConsideredStart",
    "DroppedOffer",
    "Limit",
    "LockStatus",
    "Offer",
    "OfferSet",
    "PackedPolicy",
    "PackedResult",
    "Plan",
    "PlanError",
    "PlanSettings",
    "PricedOffer",
    "ReadingChoice",
    "RefusedStart",
    "StartCandidate",
    "StartChoice",
    "StartContext",
    "StartList",
    "StartPrice",
    "StartReading",
    "StartSource",
    "StrandSetting",
    "Walked",
    "axis_name",
    "axis_what",
    "base_kind",
    "bought_base_starts",
    "chance",
    "claim",
    "default_offers",
    "evaluate_risk",
    "figures",
    "free_action_cost",
    "good_name",
    "grouped",
    "limit_document",
    "limit_text",
    "lumped_policy",
    "lumped_view",
    "main_view",
    "make_plan",
    "more_labels",
    "not_shown",
    "offer_action",
    "offers_for",
    "ordered",
    "packed_risk",
    "plan_target",
    "plan_with_starts",
    "present_with",
    "price_offers",
    "progress",
    "reading_pair",
    "say_progress_to",
    "strand_setting",
    "unresolved",
    "value_text",
    "vendor_recipe_starts",
    "without_ranges",
]
