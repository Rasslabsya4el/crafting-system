"""What an answer leaves out, as one record (ticket #459, OR-13).

A `Limit` is one thing the answer does not cover and what it still guarantees: a kind of action that was not offered,
offers dropped for lack of a price, an offer proved not needed, a given start item, a percentile the grid could not reach.
`Plan.limits` holds them all, and the text report, the JSON policy (`crafting-system-policy/3`) and the route page's goal card
show the same records in the same words, so no surface keeps a second copy.

The fields:

* `kind` is the group of the limit, one of the constants below; the page groups by it and the order of `GROUPS` is the order shown.
* `what` is the short head ("Not offered", "The start item is given"), `why` the cause in plain words, `guarantee` one sentence that says what
  the answer still guarantees (OR-13). `what`, `why` and `guarantee` are in player words: no setting key, no module name, no ticket number, none of the solver's own words (#481;
  `tests/test_cli_limit_words.py` reads every limit the planner can write).
* `labels` are the things left out, by their names in the game ("Exalted Orb", "Bench craft Cannot roll Attack Modifiers").
* `names` are the things the cause is about, for a limit that has them: the items with no price of an unpriced group.

* `approximate` is the guarantee for an approximate answer, required when `guarantee` claims the cheapest plan; `claim` writes both, and
  `Plan` swaps them (`approximate_limits`) when its answer is approximate, so a claim of cheapness comes from the solve that made the answer.

The text report and the JSON name every label (nothing left out is hidden, OR-16); the page names the first `SHOWN_LABELS` and holds the rest in a closed
"details" element. The cause may hold `{names}`, filled from `names` when shown (`Limit.reason`), so the names live in one place.

A limit that is not about a list has no labels. `kind` is a plain string so that the limits the next step records (a model gap met
inside a solve, a price's provenance, a constant of the risk run or the solver) are new values of it, not a new type.

`detail` is where the developer's text behind a cause goes (#557). The causes of the model gaps, of the decision (G12, G13: `whole_search_limit`), of the
timing run, of the skipped levels and of the bound pruning's fallback are sentences a player reads (`names`, `why`); the text an exception keeps for a
developer (`OutOfScopeError.detail`, the solver's error) is `Limit.detail`, which `limit_document` writes to the JSON policy and no text prints. It reaches
no other place: a route line (`cli/_route.py`) and the `Error:` line of the command say the sentence only, and nothing is logged.

The model gaps (ticket #506) are the limits of a refusal that is not the game's: `model_gap_limits` writes what `Abstraction.gaps` holds, and
`pruning_limits` what `Abstraction.prunings` holds. A game refusal is silent (the plan is exact under it); a model gap never is.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace

from crafting_system.risk._linear import SAID_ABOVE  # one definition: a certified relative error above it is said (4 significant digits; as `cli/_route_flow.STIFF_ERROR` is for the chances of a step)

NOT_NAMED = "kinds-not-named"
OPT_IN = "kinds-opt-in"
NOT_BUILT = "kinds-not-built"
LISTING_GAP = "kinds-model-gap"
CORRUPTING = "corrupting"
CORRUPT_ASKED = "corrupting-asked"
STRANDS = "strands"
CRAFTS = "crafts"
FIXED_MOD = "fixed-mod"
ROLLS = "rolls"
CRAFTED_MODS = "crafted-mods"
UNPRICED = "unpriced"
CONSUMES = "consumes-items"
MODEL_GAP = "model-gap"
PROVED = "proved-unneeded"
START = "start-item"
SOLVE = "how-solved"
DISPLAY = "display"
STEPS = "step-numbers"
STATE_LINE = "state-line"
RISK = "risk"

GROUPS: tuple[tuple[str, str], ...] = (
    (NOT_NAMED, "Methods the target does not name"),
    (OPT_IN, "Methods offered only when the target names them"),
    (NOT_BUILT, "Methods the planner cannot use yet"),
    (LISTING_GAP, "Methods the model cannot list for this item"),
    (CORRUPTING, "Corrupting methods the target does not ask for"),
    (CORRUPT_ASKED, "Corrupting sets offered only to a target that asks for a corrupted implicit"),
    (STRANDS, "Memory Strands"),
    (CRAFTS, "Bench crafts that count for nothing"),
    (FIXED_MOD, "Actions that add one fixed mod nobody wants"),
    (ROLLS, "Value rerolls without a roll limit"),
    (CRAFTED_MODS, "Removing crafted mods"),
    (UNPRICED, "Actions with no price"),
    (CONSUMES, "Actions that consume other items"),
    (MODEL_GAP, "Actions the model has no rule for in some states"),
    (PROVED, "Actions proved not needed"),
    (START, "The start item"),
    (SOLVE, "How the answer was found"),
    (DISPLAY, "What is shown"),
    (STEPS, "What the steps show"),
    (STATE_LINE, "What a state line shows"),
    (RISK, "Percentiles"),
)
TITLES = dict(GROUPS)
ORDER = {kind: number for number, (kind, _) in enumerate(GROUPS)}

HEADING = "What this answer leaves out"  # the section of the route page and the block of the text report

SHOWN_LABELS = 3  # the page names this many labels of a limit and puts the rest in a closed "details" element; the text report and the JSON name every label

_SMALL = {"of", "the", "to", "a", "and"}
_NAMES = {  # the kinds whose name in the catalog does not read as the game's word
    "essence": "Essences",
    "corrupted-essence": "Corrupted essences",
    "bench-craft": "Bench crafts",
    "fossil-set": "Fossil sets",
    "remove-crafted-mods": "Remove Crafted Mods",
    "awakeners-orb": "Awakener's Orb",
    "jewellers-orb": "Jeweller's Orb",
    "harvest-reforge": "Harvest reforges",
    "harvest-reforge-influence": "Harvest reforges of an influence",
    "harvest-reforge-likelihood": "Harvest reforges that favour a mod",
    "harvest-add-remove": "Harvest add or remove a mod",
    "harvest-resistance-swap": "Harvest resistance swaps",
    "harvest-damage-swap": "Harvest damage swaps",
    "harvest-quality-enchant": "Harvest quality enchants",
    "unveil": "Unveil",
    "pick": "Pick from the unveil offer",
    "vaal": "Vaal Orb",
    "locus": "Locus of Corruption",
    "talisman-fracture": "Talisman fracture",
    "aspect-beast": "Aspect beast",
    "beast-side-swap": "Beast side swap",
    "wild-bristle-matron": "Wild Bristle Matron",
    "beast-influence-recipe": "Beast influence recipe",
    "re-anoint": "Re-anoint",
    "recombinator": "Recombinators",
    "catalyst": "Catalysts",
    "eldritch-implicit-currency": "Eldritch implicit currency",
    "bench-socket-count": "Bench socket count",
    "bench-socket-links": "Bench socket links",
    "bench-socket-colours": "Bench socket colours",
    "quality-currency": "Quality currency",
}


@dataclass(frozen=True)
class Limit:
    """One thing an answer leaves out and what it still guarantees (see the module text)."""

    kind: str
    what: str
    why: str
    guarantee: str
    labels: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    approximate: str = ""  # the guarantee when the answer is approximate; required when `guarantee` claims the cheapest plan (see `claim`)
    detail: tuple[str, ...] = field(default=(), repr=False)  # the developer's text behind the causes (ids, ADR and ticket numbers), JSON only (#557): one for one with `names` (the count of the rest last), or one entry for a limit with no names; left out of the repr so that the fingerprints of the limits (`b1_unchanged_142.json`) are those of a limit without it

    def __post_init__(self) -> None:
        if not self.guarantee.strip():
            raise ValueError(f"a limit of kind {self.kind!r} needs a guarantee (OR-13)")
        if "cheapest" in self.guarantee and WITHIN_GAP not in self.guarantee and not self.approximate:
            raise ValueError(f"the guarantee of a limit of kind {self.kind!r} claims the cheapest plan, so it needs the sentence for an approximate answer (`claim`)")

    def reason(self) -> str:
        """The cause as shown: `why`, with `{names}` replaced by the names the cause is about (they live in `names` only)."""
        return self.why.replace("{names}", ", ".join(self.names))


WITHIN_GAP = "within the stated gap of the cheapest"


def claim(among: str, rest: str = "") -> dict[str, str]:
    """The guarantee "the plan is the cheapest among `among`", and its form for an approximate answer: `Limit(..., **claim("the kinds offered"))`.

    A claim of cheapness comes from the solve that made the answer. An exact solve makes it; an approximate one only reaches the cheapest
    to within the gap it states (`Plan` swaps the sentences with `approximate_limits`), so no cheapness claim is written outside this function.
    """
    tail = f" {rest}" if rest else ""
    return {
        "guarantee": f"The plan is the cheapest among {among}.{tail}",
        "approximate": f"The plan is {WITHIN_GAP} among {among}.{tail}",
    }


def approximate_limits(limits: Iterable[Limit]) -> tuple[Limit, ...]:
    """The limits of an approximate answer: each guarantee that claims the cheapest plan says "within the stated gap of the cheapest" instead."""
    return tuple(replace(limit, guarantee=limit.approximate, approximate="") if limit.approximate else limit for limit in limits)


def kind_title(name: str) -> str:
    """An action kind of the catalog as a player writes it: `exalted-orb` is "Exalted Orb"."""
    if name in _NAMES:
        return _NAMES[name]
    words = name.split("-")
    return " ".join(word if (number and word in _SMALL) else word.capitalize() for number, word in enumerate(words))


def limit_text(limit: Limit, shown: int | None = None) -> str:
    """The limit in one sentence group: what, the labels, the cause and the guarantee.

    The text report names every label (OR-13, OR-16: nothing withheld is hidden). With `shown` (the page) a limit with more labels names the
    first `shown` and says how many more there are; the page holds the rest in a closed "details" element (`more_labels`).
    """
    head = limit.what
    if limit.labels:
        if shown is not None and len(limit.labels) > shown:
            head += f", {len(limit.labels):,} in all: {', '.join(limit.labels[:shown])} and {len(limit.labels) - shown:,} more"
        elif len(limit.labels) > SHOWN_LABELS:
            head += f", {len(limit.labels):,} in all: {', '.join(limit.labels)}"
        else:
            head += f": {', '.join(limit.labels)}"
    if limit.why:
        head += f" ({limit.reason()})"
    return f"{head}. {limit.guarantee}"


def more_labels(limit: Limit, shown: int = SHOWN_LABELS) -> tuple[str, ...]:
    """The labels `limit_text(limit, shown)` does not name."""
    return limit.labels[shown:]


def limit_document(limit: Limit) -> dict:
    """The JSON form of a limit: every label."""
    document = {
        "kind": limit.kind,
        "what": limit.what,
        "why": limit.reason(),
        "guarantee": limit.guarantee,
        "count": len(limit.labels),
        "labels": list(limit.labels),
        "names": list(limit.names),
    }
    if limit.detail:
        document["detail"] = list(limit.detail)
    return document


def ordered(limits: Iterable[Limit]) -> list[Limit]:
    """The limits in the order of their groups (a kind not in `GROUPS` last), each group in the order it was written."""
    return sorted(limits, key=lambda limit: ORDER.get(limit.kind, len(ORDER)))


def grouped(limits: Iterable[Limit]) -> list[tuple[str, list[Limit]]]:
    """(group title, its limits) in the order of `GROUPS`; a kind that has no title is its own group named by the kind."""
    found: dict[str, list[Limit]] = {}
    for limit in ordered(limits):
        found.setdefault(limit.kind, []).append(limit)
    return [(TITLES.get(kind, kind), group) for kind, group in found.items()]


def _own_price_head(kind: str, count: int) -> str:
    """"These essences have no price", for one action "This action has no price" (the label follows): the kind is plural only when there are several."""
    if count == 1:
        return "This action has no price"
    title = kind_title(kind).lower()
    return f"These {title if title.endswith('s') else title + 's'} have no price"


def unpriced_limits(dropped: Iterable[tuple]) -> tuple[Limit, ...]:
    """The limits of the offers left out for lack of a price: `dropped` holds (label, missing names) or (label, missing names, kind).

    The offers whose missing price is their own item (an essence that no price source lists) are one limit for each kind, "These essences have
    no price", with every one of them named in the line (#487); the JSON keeps them all. Any other offer is grouped by the prices it lacks:
    the offers that lack the same prices are one limit that names the prices.
    """
    own: dict[str, list[str]] = {}
    by_missing: dict[tuple[str, ...], list[str]] = {}
    for label, missing, *rest in dropped:
        kind = rest[0] if rest else ""
        if kind and tuple(missing) == (label,):
            own.setdefault(kind, []).append(label)
        else:
            by_missing.setdefault(tuple(missing), []).append(label)
    found = [
        Limit(
            UNPRICED,
            _own_price_head(kind, len(labels)),
            "",
            labels=tuple(labels),
            **claim("the actions that have a price", "A price for these could make it cheaper."),
        )
        for kind, labels in own.items()
    ]
    found += [
        Limit(
            UNPRICED,
            "Not offered",
            "no price for {names}",
            labels=tuple(labels),
            names=missing,
            **claim("the actions that have a price", "A price for these could make it cheaper."),
        )
        for missing, labels in by_missing.items()
    ]
    return tuple(found)


SHOWN_CAUSES = 3  # the causes of the model gaps one limit names; the rest are one more of the same


def _states(count: int, blocks: bool = False) -> str:
    """"3 states", or for an approximate answer "3 groups of states" (a group stands for many states)."""
    if blocks:
        return f"{count:,} group of states" if count == 1 else f"{count:,} groups of states"
    return f"{count:,} state" if count == 1 else f"{count:,} states"


def model_gap_limits(gaps: Iterable) -> tuple[Limit, ...]:
    """The limits of the actions the model had no rule for (K14, G6): the `Gap`s of `Abstraction.gaps`.

    An action that consumes other items (G6) is refused in every state, so its limit names the action; any other gap names the action and the
    number of states it was left out of, and the first cause of each action. A game refusal is not here: the plan is exact under it.
    """
    gaps = tuple(gaps)
    found: list[Limit] = []
    consuming = [gap for gap in gaps if gap.consumes_inputs]
    if consuming:
        found.append(
            Limit(
                CONSUMES,
                "Not offered",
                "they consume other items, and the planner does not price those yet, so it would count them as free",
                labels=tuple(gap.label for gap in consuming),
                **claim("the actions that consume no other item", "An action that consumes other items could make it cheaper."),
            )
        )
    others = [gap for gap in gaps if not gap.consumes_inputs]
    if others:
        causes = tuple(dict.fromkeys(gap.cause for gap in others))
        detail_of: dict[str, str] = {}
        for gap in others:
            detail_of.setdefault(gap.cause, gap.detail or gap.cause)
        has_detail = any(gap.detail for gap in others)
        shown = causes[:SHOWN_CAUSES] + ((f"{len(causes) - SHOWN_CAUSES} more causes",) if len(causes) > SHOWN_CAUSES else ())
        found.append(
            Limit(
                MODEL_GAP,
                "Left out where the model has no rule",
                "the model has no rule for them there, so they are not offered there: {names}",
                labels=tuple(f"{gap.label} in {_states(gap.states, gap.blocks)}" for gap in others),
                names=shown,
                detail=(tuple(detail_of[cause] for cause in causes[:SHOWN_CAUSES]) + shown[SHOWN_CAUSES:]) if has_detail else (),  # one for one with `names`, the count of the rest last
                **claim("the actions the model can apply in each state", "An action the model has no rule for could make it cheaper."),
            )
        )
    return tuple(found)


def pruning_limits(prunings) -> tuple[Limit, ...]:
    """The limits of the offers left out of the states that cannot use them (K13): exact, so each says that nothing is lost."""
    found: list[Limit] = []
    corrupting = prunings.labels("corrupting")
    if corrupting:
        found.append(
            Limit(
                PROVED,
                "Offered only once the rest of the target is met",
                "a corrupting action ends the craft, so from any other state it could only lose the item",
                labels=corrupting,
                **claim("the methods offered", "Offering them in the other states would change no cost."),
            )
        )
    quality = prunings.labels("quality")
    if quality:
        found.append(
            Limit(
                PROVED,
                "Offered only once the rest of the target is met",
                "quality changes no odds, so setting it later costs the same",
                labels=quality,
                **claim("the methods offered", "Offering them in the other states would change no cost."),
            )
        )
    return tuple(found)


def twins_limit(twins: Sequence[tuple[str, str]]) -> Limit:
    """The limit of offers left out because a cheaper offer does the same (K15, G17): `twins` are (dropped label, kept label)."""
    return Limit(
        PROVED,
        "Not searched",
        "same outcome as a cheaper action",
        "The answer is exact among the methods offered: a cheaper action does the same.",
        tuple(dropped for dropped, _ in twins),
        approximate=f"The plan is {WITHIN_GAP} among the methods offered: a cheaper action does the same.",
    )


def unresolved(risk, estimate) -> bool:
    """Whether a quantile or CVaR is infinite only because the budget grid could not reach it: the odds are 1."""
    return math.isinf(estimate.value) and risk.success_probability.value >= 1.0 and not risk.grid.cause


UNRESOLVED = "not computed (the cost of the whole craft is far above its cheapest step)"


NOT_COMPUTED = {
    "subcritical": "not computed: the plan starts more runs of its inputs than it finishes, so its cost has no finite mean",
    "undecided": "not computed: the chances of the plan are so close to 1 that the arithmetic could not fix the cost to within 1%",
    "unordered": "not computed: the inputs of the plan depend on each other in a cycle",
    "improper": "not computed: the plan can reach a state from which it cannot finish, and its inputs depend on each other in a cycle",
    "stuck": "not computed: the plan can reach a state from which it cannot finish, so its cost has no finite mean",
}  # by the cause of `GridInfo` (M7, #506) and of `risk.Expected` (#512); the text report, the route page and the interval say the same words


def not_shown(risk, estimate) -> str | None:
    """Why a quantile of `risk` is not shown, in the words the text report and the route page share (#512); None when it is a number to show.

    Its own cause (M7) when the report has one and the quantile is infinite; `UNRESOLVED` when only the grid could not reach it (the odds
    are 1); None otherwise, a finite quantile or one of a plan that may not finish (each reader words that case itself).
    """
    if risk.grid.cause and math.isinf(estimate.value):  # its own cause, not the grid's; a quantile the grid did compute is shown
        return NOT_COMPUTED[risk.grid.cause]
    return UNRESOLVED if unresolved(risk, estimate) else None


PERCENTILE_WORDS = {
    "success": "the success chance",
    "mean": "the mean cost",
    "variance": "the variance",
    "p50": "the median cost",
    "p90": "the cost 9 runs in 10 stay under",
    "CVaR": "the average of the worst tenth",
}  # the figures of a risk report as a player reads them
QUANTILES = ("p50", "p90", "CVaR")  # the three that need the percentile calculation


def figures(*names: str) -> str:
    """"the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth": the figures `names` (keys of `PERCENTILE_WORDS`) in a list."""
    words = [PERCENTILE_WORDS[name] for name in names]
    if len(words) > 2:
        return ", ".join(words[:-1]) + ", and " + words[-1]
    return " and ".join(words)


def not_computed(*names: str) -> str:
    """"Not computed: the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth": the figures `names` (keys of `PERCENTILE_WORDS`)."""
    return f"Not computed: {figures(*names)}"


def risk_limits(risk) -> tuple[Limit, ...]:
    """The limit of a risk report whose percentiles the grid could not reach (empty when it reached them all)."""
    if risk is None:
        return ()
    found: list[Limit] = []
    if risk.grid.cause in ("subcritical", "improper", "undecided"):
        gone = [
            name
            for name, estimate in (("mean", risk.mean), ("variance", risk.variance), ("p50", risk.p50), ("p90", risk.p90), ("CVaR", risk.cvar))
            if math.isinf(estimate.value)
        ]  # the ones the report leaves infinite: a grid that did run may still have given some
        found.append(
            Limit(
                RISK,
                not_computed(*gone),
                {
                    "subcritical": "the plan starts more runs of its inputs than it finishes, so the cost of the whole craft has no finite mean",
                    "undecided": "the chances of the plan are so close to 1 (a step that almost always repeats itself) that the arithmetic could not fix the cost of the whole craft to within one in a hundred",
                    "improper": "the plan can reach a state from which it cannot finish, and its inputs depend on each other in a cycle, so no cost of the whole craft is computed",
                }[risk.grid.cause],
                "Only the bracket around the success chance is certified; no cost is claimed.",
            )
        )
    elif risk.grid.cause == "unordered":
        found.append(
            Limit(
                RISK,
                not_computed(*QUANTILES),
                "the inputs of the plan depend on each other in a cycle, so the cost of a run has no order to follow",
                "The success chance, the mean cost and the variance are exact.",
            )
        )
    loose = loose_figures(risk)
    if loose is not None:
        found.append(loose)
    cut = [name for name, estimate in (("p50", risk.p50), ("p90", risk.p90), ("CVaR", risk.cvar)) if unresolved(risk, estimate)]
    if cut:
        found.append(
            Limit(
                RISK,
                not_computed(*cut),
                "the cost of the whole craft is far above its cheapest step, so the calculation of these figures cannot reach them"
                + (f"; the faster methods gave up first: {'; '.join(risk.grid.gave_up)}" if risk.grid.gave_up else ""),
                "The success chance and the mean cost are exact.",
            )
        )
    elif risk.grid.gave_up:
        found.append(
            Limit(
                RISK,
                "Cost figures by a slower method",
                "; ".join(risk.grid.gave_up),
                "Each cost figure shown is certified by the method that finished; one it could not reach is marked as not computed.",
            )
        )
    return tuple(found)




def relative_error(estimate) -> float:
    """The most the certified range of `estimate` is from its value, relative to the value; 0 for a figure that is zero or not finite (no range to speak of)."""
    if not (math.isfinite(estimate.value) and estimate.value > 0.0):
        return 0.0
    high = estimate.high - estimate.value if math.isfinite(estimate.high) else math.inf
    return max(high, estimate.value - estimate.low) / estimate.value


def loose_figures(risk) -> Limit | None:
    """The limit of a mean cost or variance whose certified range is wider than 4 significant digits: it is printed to more digits than the arithmetic supports (OR-13).

    The range is the certificate of the linear solve behind the figure (`risk._inputs`, `risk._moments`): the forward error of the answer, with the
    rounding of the check included, so it is not a guess at the digits but what the calculation can show.
    """
    error = max(relative_error(risk.mean), relative_error(risk.variance))
    if not error > SAID_ABOVE:
        return None
    digits = max(0, int(-math.log10(error))) if math.isfinite(error) else 0
    return Limit(
        RISK,
        "The cost figures are good to fewer digits than printed",
        f"the chances of the plan are so close to 1 that the mean cost and the variance can be certified only to about {digits} significant digits",
        "The mean cost and the variance lie in the range printed beside each; they are not exact to the digits printed.",
    )


def with_limits(limits: Sequence[Limit], added: Iterable[Limit], kind: str | None = None) -> tuple[Limit, ...]:
    """`limits` with `added` after them; with `kind`, the limits already there of that kind are replaced."""
    kept = [limit for limit in limits if kind is None or limit.kind != kind]
    return (*kept, *added)
