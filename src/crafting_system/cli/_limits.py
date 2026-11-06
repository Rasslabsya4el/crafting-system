"""What an answer leaves out, as one record (ticket #459, OR-13).

A `Limit` is one thing the answer does not cover and what it still guarantees: a kind of action that was not offered,
offers dropped for lack of a price, an offer proved not needed, a given start item, a percentile the grid could not reach.
`Plan.limits` holds them all, and the text report, the JSON policy (`crafting-system-policy/2`) and the route page's goal card
show the same records in the same words, so no surface keeps a second copy.

The fields:

* `kind` is the group of the limit, one of the constants below; the page groups by it and the order of `GROUPS` is the order shown.
* `what` is the short head ("Not offered", "The start item is given"), `why` the cause in plain words, `guarantee` one sentence that says what
  the answer still guarantees (OR-13). `guarantee` is in player words: no setting key, no module name, no ticket number.
* `labels` are the things left out, by their names in the game ("Exalted Orb", "Bench craft Cannot roll Attack Modifiers").
* `names` are the things the cause is about, for a limit that has them: the items with no price of an unpriced group.

* `approximate` is the guarantee for an approximate answer, required when `guarantee` claims the cheapest plan; `claim` writes both, and
  `Plan` swaps them (`approximate_limits`) when its answer is approximate, so a claim of cheapness comes from the solve that made the answer.

The text report and the JSON name every label (nothing left out is hidden, OR-16); the page names the first `SHOWN_LABELS` and holds the rest in a closed
"details" element. The cause may hold `{names}`, filled from `names` when shown (`Limit.reason`), so the names live in one place.

A limit that is not about a list has no labels. `kind` is a plain string so that the limits the next step records (a model gap met
inside a solve, a price's provenance, a constant of the risk run or the solver) are new values of it, not a new type.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

NOT_NAMED = "kinds-not-named"
OPT_IN = "kinds-opt-in"
NOT_BUILT = "kinds-not-built"
CORRUPTING = "corrupting"
CORRUPT_ASKED = "corrupting-asked"
STRANDS = "strands"
CRAFTS = "crafts"
FIXED_MOD = "fixed-mod"
ROLLS = "rolls"
CRAFTED_MODS = "crafted-mods"
UNPRICED = "unpriced"
PROVED = "proved-unneeded"
START = "start-item"
SOLVE = "how-solved"
DISPLAY = "display"
RISK = "risk"

GROUPS: tuple[tuple[str, str], ...] = (
    (NOT_NAMED, "Methods the target does not name"),
    (OPT_IN, "Methods offered only when the target names them"),
    (NOT_BUILT, "Methods the planner cannot use yet"),
    (CORRUPTING, "Corrupting methods the target does not ask for"),
    (CORRUPT_ASKED, "Corrupting sets offered only to a target that asks for a corrupted implicit"),
    (STRANDS, "Memory Strands"),
    (CRAFTS, "Bench crafts that count for nothing"),
    (FIXED_MOD, "Actions that add one fixed mod nobody wants"),
    (ROLLS, "Value rerolls without a roll limit"),
    (CRAFTED_MODS, "Removing crafted mods"),
    (UNPRICED, "Actions with no price"),
    (PROVED, "Actions proved not needed"),
    (START, "The start item"),
    (SOLVE, "How the answer was found"),
    (DISPLAY, "What is shown"),
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
    return {
        "kind": limit.kind,
        "what": limit.what,
        "why": limit.reason(),
        "guarantee": limit.guarantee,
        "count": len(limit.labels),
        "labels": list(limit.labels),
        "names": list(limit.names),
    }


def ordered(limits: Iterable[Limit]) -> list[Limit]:
    """The limits in the order of their groups (a kind not in `GROUPS` last), each group in the order it was written."""
    return sorted(limits, key=lambda limit: ORDER.get(limit.kind, len(ORDER)))


def grouped(limits: Iterable[Limit]) -> list[tuple[str, list[Limit]]]:
    """(group title, its limits) in the order of `GROUPS`; a kind that has no title is its own group named by the kind."""
    found: dict[str, list[Limit]] = {}
    for limit in ordered(limits):
        found.setdefault(limit.kind, []).append(limit)
    return [(TITLES.get(kind, kind), group) for kind, group in found.items()]


def unpriced_limits(dropped: Iterable[tuple[str, Sequence[str]]]) -> tuple[Limit, ...]:
    """One limit for each set of missing prices: the offers (label, missing names) that lack the same prices are one limit."""
    by_missing: dict[tuple[str, ...], list[str]] = {}
    for label, missing in dropped:
        by_missing.setdefault(tuple(missing), []).append(label)
    return tuple(
        Limit(
            UNPRICED,
            "Not offered",
            "no price for {names}",
            labels=tuple(labels),
            names=missing,
            **claim("the actions that have a price", "A price for these could make it cheaper."),
        )
        for missing, labels in by_missing.items()
    )


def unresolved(risk, estimate) -> bool:
    """Whether a quantile or CVaR is infinite only because the budget grid could not reach it: the odds are 1."""
    return math.isinf(estimate.value) and risk.success_probability.value >= 1.0


def risk_limits(risk) -> tuple[Limit, ...]:
    """The limit of a risk report whose percentiles the grid could not reach (empty when it reached them all)."""
    if risk is None:
        return ()
    cut = [name for name, estimate in (("p50", risk.p50), ("p90", risk.p90), ("CVaR", risk.cvar)) if unresolved(risk, estimate)]
    if not cut:
        return ()
    return (
        Limit(
            RISK,
            f"Not computed: {', '.join(cut)}",
            "the cost of the whole craft is far above its cheapest step, so the grid that measures percentiles cannot reach them",
            "The success chance and the mean cost are exact.",
        ),
    )


def with_limits(limits: Sequence[Limit], added: Iterable[Limit], kind: str | None = None) -> tuple[Limit, ...]:
    """`limits` with `added` after them; with `kind`, the limits already there of that kind are replaced."""
    kept = [limit for limit in limits if kind is None or limit.kind != kind]
    return (*kept, *added)
