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

from crafting_system.budget import Binding
from crafting_system.risk._linear import SAID_ABOVE  # one definition: a certified relative error above it is said (4 significant digits; as `cli/_route_flow.STIFF_ERROR` is for the chances of a step)

NOT_NAMED = "kinds-not-named"
OPT_IN = "kinds-opt-in"
NOT_BUILT = "kinds-not-built"
LISTING_GAP = "kinds-model-gap"
CORRUPTING = "corrupting"
CORRUPT_ASKED = "corrupting-asked"
ELDRITCH_ASKED = "eldritch-asked"  # only with `_offers.ELDRITCH_GATE` (the tests' classic offers, #886)
STRANDS = "strands"
CRAFTS = "crafts"
FIXED_MOD = "fixed-mod"
ROLLS = "rolls"
QUALITY = "quality-type"
CRAFTED_MODS = "crafted-mods"
NO_VEIL = "veiled-mods"
UNPRICED = "unpriced"
CONSUMES = "consumes-items"
MODEL_GAP = "model-gap"
PROVED = "proved-unneeded"
UNTRIED = "kinds-not-tried"
ROUNDS = "rounds"
IMPRINTS = "imprints-worth-saving"  # the planner's rule of the imprints worth making (#1567): not exact, so not PROVED
START = "start-item"
SOLVE = "how-solved"
REACHED = "plan-reached"  # a plan the search walked to when its first plan reached no goal, and a net stopped it there (#1142)
BUDGET = "time-and-memory"
DISPLAY = "display"
STEPS = "step-numbers"
STATE_LINE = "state-line"
RISK = "risk"
FINISH = "socket-finish"
QUALITY_FINISH = "quality-finish"
IMPLICIT_FINISH = "implicit-finish"

GROUPS: tuple[tuple[str, str], ...] = (
    (NOT_NAMED, "Methods this run's setting leaves out"),
    (OPT_IN, "Methods offered only when the run's setting names them"),
    (NOT_BUILT, "Methods the planner cannot use yet"),
    (LISTING_GAP, "Methods the model cannot list for this item"),
    (CORRUPTING, "Corrupting methods the target does not ask for"),
    (CORRUPT_ASKED, "Corrupting sets offered only to a target that asks for a corrupted implicit"),
    (ELDRITCH_ASKED, "Eldritch currencies not tried as tools on a target that names no Eldritch implicit"),
    (STRANDS, "Memory Strands"),
    (CRAFTS, "Bench crafts that count for nothing"),
    (FIXED_MOD, "Actions that add one fixed mod nobody wants"),
    (ROLLS, "Value rerolls without a roll limit"),
    (QUALITY, "Catalysts of another quality type"),
    (CRAFTED_MODS, "Removing crafted mods"),
    (NO_VEIL, "Unveiling with no veiled mod"),
    (UNPRICED, "Actions with no price"),
    (CONSUMES, "Actions that consume other items"),
    (MODEL_GAP, "Actions the model has no rule for in some states"),
    (PROVED, "Actions proved not needed"),
    (UNTRIED, "Actions not tried before a time or memory limit"),
    (ROUNDS, "Methods searched in rounds"),
    (IMPRINTS, "Imprints made only of an item worth coming back to"),
    (START, "The start item"),
    (FINISH, "The sockets"),
    (QUALITY_FINISH, "The quality"),
    (IMPLICIT_FINISH, "The implicit"),
    (SOLVE, "How the answer was found"),
    (REACHED, "A plan that reaches the target, not one shown near the best"),
    (BUDGET, "Time and memory limits that stopped a stage"),
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
    "unravelling-orb": "Orb of Unravelling",
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
    "hinekora-lock": "Hinekora's Lock",
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


def budget_limit(bindings: Sequence[Binding]) -> Limit | None:
    """The one limit that lists every time or memory limit that stopped a stage of the run, in the order they stopped (#378, #825; OR-12, OR-13).

    None when nothing bound. Each name is the stage, the limit with its figure and what was spent, and what the stage kept (`Binding.words`).
    """
    if not bindings:
        return None
    return Limit(
        BUDGET,
        "Stopped by a time or memory limit",
        "the run has a limit of time and memory, and these stages reached it: {names}",
        "Each stage that stopped kept what it says here; nothing was left out for being unlikely or by a count, and every other stage ran to its end.",
        names=tuple(binding.words() for binding in bindings),
    )


def claim(among: str, rest: str = "", rest_approximate: str | None = None) -> dict[str, str]:
    """The guarantee "the plan is the cheapest among `among`", and its form for an approximate answer: `Limit(..., **claim("the kinds offered"))`.

    A claim of cheapness comes from the solve that made the answer. An exact solve makes it; an approximate one only reaches the cheapest
    to within the gap it states (`Plan` swaps the sentences with `approximate_limits`), so no cheapness claim is written outside this function.
    """
    tail = f" {rest}" if rest else ""
    loose = tail if rest_approximate is None else f" {rest_approximate}" if rest_approximate else ""  # a `rest` that itself claims the best plan has its own form
    return {
        "guarantee": f"The plan is the cheapest among {among}.{tail}",
        "approximate": f"The plan is {WITHIN_GAP} among {among}.{loose}",
    }


def approximate_limits(limits: Iterable[Limit]) -> tuple[Limit, ...]:
    """The limits of an approximate answer: each guarantee that claims the cheapest plan says "within the stated gap of the cheapest" instead."""
    return tuple(replace(limit, guarantee=limit.approximate, approximate="") if limit.approximate else limit for limit in limits)


RISK_EXACT = "The odds, the mean and the variance are exact."  # a risk whose quantiles do not fit in memory (`_plan.packed_risk`)
UNORDERED_EXACT = "The success chance, the mean cost and the variance are exact."
UNRESOLVED_EXACT = "The success chance and the mean cost are exact."
GROUPS_EXACT = "The odds and every cost figure are exact for the groups."  # the tree of groups (`_plan.lumped_limit`)
EXACT_MEAN_SENTENCES = (RISK_EXACT, UNORDERED_EXACT, UNRESOLVED_EXACT, GROUPS_EXACT)


def rough_mean_limits(limits: Iterable[Limit], mean_error: float) -> tuple[Limit, ...]:
    """The limits of a plan whose mean is certified only to `mean_error` of itself, above the solver's 1e-6 (a plan of very many steps that a
    search with a gap or a net returned, #867): each guarantee that calls its mean or its figures exact says how far they are worked out instead,
    so that no text of the plan says "exact" (the reading of OR-32 of 2026-11-14). The gap the search states already holds that error."""
    rough = (
        f"The plan takes so many steps that its mean cost is worked out only to within {mean_error:.2g} of itself, and its other figures are not "
        "claimed any closer."
    )
    return tuple(replace(limit, guarantee=rough) if limit.guarantee in EXACT_MEAN_SENTENCES else limit for limit in limits)


USED_ON_THE_ITEM = " used on the item"


def _orb_names(text: str) -> frozenset[str]:
    """The two ways the game and the catalog write one orb: "Scouring Orb" and "Orb of Scouring" are the same currency."""
    names = {text}
    if text.endswith(" Orb") and " " not in text[: -len(" Orb")]:
        names.add(f"Orb of {text[: -len(' Orb')]}")
    if text.startswith("Orb of ") and " " not in text[len("Orb of ") :]:
        names.add(f"{text[len('Orb of ') :]} Orb")
    return frozenset(names)


def spent_kinds_named(limits: Iterable[Limit], spent: Iterable[str]) -> tuple[Limit, ...]:
    """The limits with each kind that is named by a currency the plan spends (a bench craft's Divine or Chaos Orb, the Orb of Scouring of
    Remove Crafted Mods) named by its use, "Divine Orb used on the item": a kind left out is the currency used as a craft on the item, and no
    note may call a currency that a step pays with not offered (#983, OR-7). `spent` are the names of the price list (`cli._price_marks`)."""
    paid = frozenset(name for each in spent for name in _orb_names(each))
    if not paid:
        return tuple(limits)
    return tuple(
        replace(limit, labels=tuple(label + USED_ON_THE_ITEM if label in paid else label for label in limit.labels)) if paid.intersection(limit.labels) else limit
        for limit in limits
    )


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
    """The limits of the offers left out of the states that cannot use them (K13). The corrupting and the quality ones are exact, so each says
    that nothing is lost; the imprints worth saving (#1567) are the planner's rule, not exact, and the limit says the plan is the best found."""
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
    imprints = prunings.labels("imprint")
    if imprints:
        found.append(
            Limit(
                IMPRINTS,
                "Imprinted only when the item is worth coming back to",
                "an imprint is made only of an item that holds a wanted mod and no unwanted, crafted or veiled one (#1567)",
                "An imprint made at another state could make the plan cheaper: the plan is the best found, not proved the least dear.",
                labels=imprints,
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
STOPPED_FIGURE = "not computed (the work on the cost figures was stopped at its time limit)"  # `GridInfo.stopped` (#738)
STOPPED_FIGURE_MEMORY = "not computed (the work on the cost figures was stopped at its memory limit)"


def stopped_figure(risk) -> str:
    """The cell of a figure the net of the cost figures stopped (#738), by the net that stopped it."""
    return STOPPED_FIGURE_MEMORY if risk.grid.stopped_by == "memory" else STOPPED_FIGURE


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
    are 1), or `STOPPED_FIGURE` when the net of the cost figures stopped them first (#738); None otherwise, a finite quantile or one of a plan that may not finish (each reader words that case itself).
    """
    if risk.grid.cause and math.isinf(estimate.value):  # its own cause, not the grid's; a quantile the grid did compute is shown
        return NOT_COMPUTED[risk.grid.cause]
    if unresolved(risk, estimate):
        return stopped_figure(risk) if risk.grid.stopped else UNRESOLVED
    return None


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
                UNORDERED_EXACT,
            )
        )
    loose = loose_figures(risk)
    if loose is not None:
        found.append(loose)
    cut = [name for name, estimate in (("p50", risk.p50), ("p90", risk.p90), ("CVaR", risk.cvar)) if unresolved(risk, estimate)]
    if risk.grid.stopped and not cut:  # a plan that may not finish: its stopped figures are not "unresolved", the stop is said all the same (#738)
        found.append(
            Limit(
                RISK,
                "The work on the cost figures was stopped",
                risk.grid.stopped,
                "Each cost figure shown is certified as far as the work reached; one it did not reach is marked as not computed.",
            )
        )
    if cut and risk.grid.stopped:  # the net of the cost figures stopped them (#738, OR-40), not the size of the grid
        found.append(
            Limit(
                RISK,
                not_computed(*cut),
                risk.grid.stopped + (f"; the faster methods gave up first: {'; '.join(risk.grid.gave_up)}" if risk.grid.gave_up else ""),
                UNRESOLVED_EXACT,
            )
        )
    elif cut:
        found.append(
            Limit(
                RISK,
                not_computed(*cut),
                "the cost of the whole craft is far above its cheapest step, so the calculation of these figures cannot reach them"
                + (f"; the faster methods gave up first: {'; '.join(risk.grid.gave_up)}" if risk.grid.gave_up else ""),
                UNRESOLVED_EXACT,
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


def feeder_donors_limit() -> Limit:
    """The limit of a plan that makes donors (ticket #225, ADR-0062 decision 4): the donors offered are the target's own mods only (OR-13).

    A recombination is offered only when the item in hand and its second item both hold nothing but mods the target asks for (one alone, or a
    few together: the single-mod and two-mod items the guides build first). Recombining an item with some other mod could in principle be cheaper.
    """
    return Limit(
        CONSUMES,
        "Recombinations only of items made of wanted mods",
        "a recombination is offered only when both items hold nothing but mods the target asks for, at a tier it accepts",
        **claim(
            "the plans that recombine only items made of wanted mods",
            "Recombining an item that also holds some other mod could make it cheaper.",
        ),
    )


def lock_with_donors_limit() -> Limit:
    """The limit of a plan that makes second items while the target allows Hinekora's Lock (ticket #225): the Lock is not offered there."""
    return Limit(
        SOLVE,
        "Hinekora's Lock is not offered",
        "the plan makes second items for its recombinations, and the planner cannot weigh the Lock in such a plan yet",
        **claim("the plans without Hinekora's Lock", "Taking the Lock could make it cheaper."),
    )


def lock_with_quality_limit() -> Limit:
    """The limit of a plan of a target that asks for quality when the run names Hinekora's Lock (#159): the Lock is not offered there."""
    return Limit(
        SOLVE,
        "Hinekora's Lock is not offered",
        "the target asks for quality, and the burn the Lock's previews need keeps no quality yet",
        **claim("the plans without Hinekora's Lock", "Taking the Lock could make it cheaper."),
    )


def second_items_shown_limit() -> Limit:
    """What the steps of a plan that makes second items leave out (ticket #225): how each second item is made is not drawn yet."""
    return Limit(
        DISPLAY,
        "How each second item is made is not shown",
        "the steps show the target's own item; a recombination's second item is made by its own run of orbs, which the steps do not draw yet",
        "The costs and the odds count every second item and every orb used to make it.",
    )


def free_donor_base_limit() -> Limit:
    """The approximate input of a plan that makes second items (ticket #225, OR-23): the Normal base each second item starts from costs nothing."""
    return Limit(
        CONSUMES,
        "A second item's base is not counted",
        "every second item starts as a Normal base of the item, and the planner does not price that base",
        "The plan costs at least what it says: each second item it makes adds the price of one Normal base, about a Chaos Orb or less.",
    )
