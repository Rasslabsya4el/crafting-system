"""Concrete ordinary Fracturing Orb outcomes.

Rules: ``docs/mechanics/fracturing.md``.  The probability is sourced from S3
``poec_simApplyCraftGO`` lines 2280-2281: each existing ordinary explicit
modifier is selected uniformly.  This family returns ``ItemState`` outcomes
because ``OutcomeClass`` would discard the chosen fractured identity.
"""

from __future__ import annotations

from dataclasses import replace
import random

from craftoracle.actions import ActionData, _is_bench, _row_for, _validate_action_data, _validate_item
from craftoracle.item_model import ItemState


def fracture_distribution(item: ItemState, data: ActionData) -> dict[ItemState, float]:
    """Return one immutable state per uniformly selected ordinary explicit."""
    _validate_fracture_input(item, data)
    probability = 1.0 / len(item.mods)
    return {
        replace(item, fractured=True, fractured_mod_id=mod.id): probability
        for mod in item.mods
    }


def apply_fracturing(item: ItemState, data: ActionData, rng: random.Random) -> ItemState:
    """Sample one direct uniform fracture using only the supplied RNG."""
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    _validate_fracture_input(item, data)
    selected = item.mods[rng.randrange(len(item.mods))]
    return replace(item, fractured=True, fractured_mod_id=selected.id)


def _validate_fracture_input(item: ItemState, data: ActionData) -> None:
    _validate_action_data(data)
    if isinstance(item, ItemState) and item.rarity != "rare":
        raise ValueError("fracturing requires a rare item")
    _validate_item(item, data)
    if item.fractured:
        raise ValueError("fracturing item is already fractured")
    if len(item.mods) < 4:
        raise ValueError("fracturing requires at least four ordinary explicit modifiers")
    for mod in item.mods:
        row = _row_for(mod, data)
        ordinary = not _is_bench(mod) and isinstance(row.get("source_path"), str) and row["source_path"].endswith("ModExplicit.lua")
        if not ordinary:
            raise ValueError("fracturing requires ordinary explicit modifiers")
