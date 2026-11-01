"""A fingerprint of what B1 offers and what its kernels give on the routes R05 and R10 to R13, to show it did not move (ticket #142).

Ticket #142 added the implicits, the quality and the offer to the contract and to the compressed state. A route of
B1 holds none of the three, so its offers and the kernels of its start state must be what they were: the same
labels, resources and left-out reasons, and the same states (by their `repr`) with the same integer weights.
`fingerprint(data)` summarises them as counts and SHA-256 digests; `tests/golden/b1_unchanged_142.json` holds the
result of the code of main before the ticket (made by `python tests/b1_unchanged_support.py <data dir> > ...` with that
code on the path), and `test_b1_unchanged.py` compares it with today's.

The fingerprint reads only what exists in both versions: it enables the actions that read the junk, as the planner did.
"""

import hashlib
import json
import sys
from pathlib import Path

from crafting_system.abstraction import Abstraction, Goal, integer_weights
from crafting_system.actions import ActionError
from crafting_system.cli._offers import offers_for
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "r05-strength-ring",
    "r10-fractured-boots",
    "r10-fractured-boots-70-life",
    "r11-reservation-helmet",
    "r12-lightning-amulet",
    "r13-life-resist-belt",
)
KERNELS_PER_ROUTE = 40


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _kernel_of(ab: Abstraction, start, action):
    try:
        weights = integer_weights(ab.kernel(start, action))
    except (ActionError, ValueError) as refusal:
        return ["refused", type(refusal).__name__]
    return sorted([repr(state), weight] for state, weight in weights.items())


def route_fingerprint(data, stem: str) -> dict:
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    goal = Goal.from_target(target)
    chosen = offers_for(data, goal, target.base_id, target.start_item, target.actions)
    offers = [[offer.label, sorted(offer.resources.items()), offer.tag, offer.shares] for offer in chosen.offers]
    left_out = sorted(repr(entry) for entry in chosen.left_out)
    enabled = [offer.action for offer in chosen.offers if offer.action.reads(data).junk]
    ab = Abstraction(data, goal, target.base_id, target.item_level, enabled)
    start = ab.compress(target.start_item)
    step = max(1, len(chosen.offers) // KERNELS_PER_ROUTE)
    kernels = {chosen.offers[i].label: _kernel_of(ab, start, chosen.offers[i].action) for i in range(0, len(chosen.offers), step)}
    return {
        "offers": len(offers),
        "offers_sha": _digest(offers),
        "left_out": len(left_out),
        "left_out_sha": _digest(left_out),
        "start": repr(start),
        "kernels": len(kernels),
        "kernels_sha": _digest(kernels),
    }


def fingerprint(data) -> dict:
    return {stem: route_fingerprint(data, stem) for stem in TARGETS}


if __name__ == "__main__":
    from crafting_system.data import load_game_data

    print(json.dumps(fingerprint(load_game_data()), indent=1, sort_keys=True))
