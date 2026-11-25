"""The planner's limits in a player's words on the route page (#893, #1442, #1508, #1514; OR-13, OR-15).

The planner writes its limits once for every surface (the text report, the JSON, the page) and in its own terms: "the model has no rule",
"kinds the run's methods setting names", "states", "rounds", a fossil set named "Fossils Glyphic Fossil". The saved plans hold those
sentences as they were written, so the page says them in a player's words when it draws them, and changes nothing a limit claims:

* `page_limits` before the limits are grouped: a fossil set is named as the game names its fossils ("Glyphic Fossil + Frigid Fossil"),
  and on a target that asks for no sockets the socket methods the planner cannot use yet are said apart, as methods that could not help
  this target (#1514: "Jeweller's Orb, Orb of Fusing, Chromatic Orb ..." among the methods that leave the plan unproved);
* `group_words` the title of a group of limits;
* `display_text` and `state_line_text` the two notes on what the route draws, which speak of states, a tree and the model;
* `player_words` every other sentence: the model is the planner, a kind is a method, a state is an item along the route.

Only the page's words change: the text report and the JSON keep the planner's sentences.
"""

from __future__ import annotations

import dataclasses
import re

from crafting_system.planner import KINDS_NOT_BUILT as NOT_BUILT
from crafting_system.planner import LIMIT_DISPLAY as DISPLAY
from crafting_system.planner import STATE_LINE, Limit, kind_title

FOSSIL_SET = "Fossils "  # `actions.fossil.ApplyFossils.label`: the planner's name of a fossil set, before the fossils' game names
SOCKET_KINDS = ("jewellers-orb", "orb-of-fusing", "chromatic-orb", "bench-socket-count", "bench-socket-links", "bench-socket-colours")

GROUP_TITLES = {  # the planner's group title -> the page's
    "Methods offered only when the run's setting names them": "Methods this run was not set to use",
    "Methods this run's setting leaves out": "Methods this run was set not to use",
    "Methods the model cannot list for this item": "Methods the planner cannot work out on this item",
    "Actions the model has no rule for in some states": "Actions the planner cannot work out on some items of the route",
    "Methods searched in rounds": "How the methods were searched",
    "What a state line shows": "What an item card shows",
    "What is shown": "Items drawn together",
}

_PHRASES = (  # (planner's words, page's words), in this order: the longer phrases before the words they hold
    ("kinds that are offered only when the run's methods setting names them", "left out of a run unless it is set to use them"),
    ("kinds the run's methods setting does not name", "this run was set not to use them"),
    ("the run's methods setting", "the run's settings"),
    ("Among the kinds offered", "Among the methods offered"),
    ("among the kinds offered", "among the methods offered"),
    ("A kind left out could be cheaper.", "A method left out could be cheaper."),
    ("the model has no rule for them on this item", "the planner cannot yet work out what they do on this item"),
    ("the actions the model can list for this item", "the actions the planner can work out on this item"),
    ("the actions the model can apply in each state", "the actions the planner can work out on each item along the route"),
    ("An action the model has no rule for could make it cheaper.", "An action the planner cannot work out could make it cheaper."),
    ("Left out where the model has no rule", "Left out where the planner has no rule"),
    ("the model has no rule", "the planner has no rule"),
    ("The model has no rule", "The planner has no rule"),
)
_MODEL = re.compile(r"\b(T|t)he model\b")
_STATES = re.compile(r"\b(in|at) ([\d,]+) states?\b")  # a model gap's label "Chaos Orb in 1,280 states" (`_limits._states`)
_LOOKED = re.compile(r"it looked at the actions of ([\d,]+) of the ([\d,]+) states it found and built ([\d,]+) of the ([\d,]+) actions offered at them")
_ROUNDS_LOOKED = re.compile(r", after [\d,]+ rounds? and ([\d,]+) states looked at")  # the SOLVE limit (`_envelope_plan.envelope_limits`)
_GROUPS = re.compile(r"passes through ([\d,]+) states and the tree shows ([\d,]+) groups")


def player_words(text: str) -> str:
    """A sentence of a limit with the planner's words said as a player reads them."""
    for planner, page in _PHRASES:
        text = text.replace(planner, page)
    text = _MODEL.sub(lambda match: f"{match.group(1)}he planner", text)
    text = _LOOKED.sub(lambda m: f"it weighed the actions on {m.group(1)} of the {m.group(2)} items it met along the way and built {m.group(3)} of the {m.group(4)} actions offered there", text)
    text = _ROUNDS_LOOKED.sub(lambda match: f", after weighing {match.group(1)} items along the way", text)
    text = _STATES.sub(lambda match: f"{match.group(1)} {match.group(2)} item{'' if match.group(2) == '1' else 's'} along the route", text)
    return fossil_name(text) if text.startswith(FOSSIL_SET) else text.replace(f" {FOSSIL_SET}", " ")


def fossil_name(label: str) -> str:
    """A fossil set by its fossils' game names: "Fossils Glyphic Fossil" is "Glyphic Fossil" (#1514)."""
    return label.removeprefix(FOSSIL_SET)


def group_words(title: str) -> str:
    """The page's title of a group of the planner's limits."""
    return GROUP_TITLES.get(title, player_words(title))


def display_text(limit: Limit) -> str | None:
    """The note on the groups the route draws (`_plan.lumped_limit`) with no state or tree; None for another limit."""
    if limit.kind != DISPLAY or (found := _GROUPS.search(limit.why)) is None:
        return None
    items, groups = found.groups()
    return (
        f"The plan tells {items} items apart by their mods; items that cost the same to finish and go on the same way with the same chances "
        f"are drawn as one ({groups} such groups), shown by one of them. The odds and every cost figure are exact for them."
    )


def state_line_text(limit: Limit) -> str | None:
    """The note on what an item card names (`_plan.states_limit`), with no state or model; None for another limit."""
    if limit.kind != STATE_LINE:
        return None
    if limit.what.startswith("A state lists the other mods only as a count per side"):
        return (
            "An item card names the mods the target asks for; every other mod shows only as \"any mod\" or \"an unwanted mod\" on its side, "
            "not by name. The odds and costs count every one of them. A card that stands for several items names a wanted mod only where "
            "every one of them holds it (\"one of A / B\" where each holds one of the two); the step's list says which item goes where."
        )
    if limit.what.startswith("A state does not list the other mods"):
        return "An item card names only the mods the target asks for. The odds and costs do not depend on the others: no method of the route reads them."
    return None


def page_limits(limits: tuple[Limit, ...], target) -> tuple[Limit, ...]:
    """The limits as the page groups them: fossil sets by their game names, and on a target that asks for no sockets the socket methods the
    planner cannot use yet said apart, as methods that could not help it (#1514)."""
    socket_titles = {kind_title(name) for name in SOCKET_KINDS}
    found: list[Limit] = []
    for limit in limits:
        labels = tuple(fossil_name(label) for label in limit.labels)
        if labels != limit.labels:
            limit = dataclasses.replace(limit, labels=labels)
        if limit.kind == NOT_BUILT and getattr(target, "sockets", None) is None and any(label in socket_titles for label in limit.labels):
            kept = tuple(label for label in limit.labels if label not in socket_titles)
            sockets = tuple(label for label in limit.labels if label in socket_titles)
            if kept:
                found.append(dataclasses.replace(limit, labels=kept))
            found.append(
                Limit(
                    limit.kind,
                    "Not offered",
                    "methods the planner cannot use yet; each changes only the sockets, and the target asks for none",
                    "The plan is unaffected: none of them could help this target.",
                    labels=sockets,
                )
            )
            continue
        found.append(limit)
    return tuple(found)


__all__ = ["display_text", "fossil_name", "group_words", "page_limits", "player_words", "state_line_text"]
