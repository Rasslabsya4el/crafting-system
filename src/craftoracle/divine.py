"""Bounded ordinary Divine value rerolls.

Mechanics: ``docs/mechanics/basic_currency.md`` Divine row and worked example
5; ``docs/specs/2026-09-21-divine-values.md``; cached S3
``poec_simRerollValues`` lines 2529-2540, read 2026-09-21, confidence
``reimplemented-from-CoE``.  Range values come from datamined accepted PoB
``stat_text`` projections.  This module intentionally supports only one
integer range in one stat string per modifier; the source-shape boundary and
exact-distribution state cap are implementation limits, not game claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import random
import re

from craftoracle.actions import (
    ActionData,
    _retained_for_reroll,
    _row_for,
    _validate_action_data,
    _validate_item,
)
from craftoracle.item_model import ItemState


_NORMAL = "normal"
_DISTRIBUTION_LIMIT = 100_000
_INTEGER_RANGE = re.compile(r"\((?P<low>[+-]?\d+)\s*-\s*(?P<high>[+-]?\d+)\)")


@dataclass(frozen=True)
class RolledItem:
    """One concrete integer value for each supported ranged explicit affix.

    ``values`` follows the source item's modifier order and excludes
    non-numeric modifiers such as bench side locks.
    """

    item: ItemState
    values: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class _ValueRange:
    mod_id: str
    low: int
    high: int
    protected: bool


def divine_distribution(rolled: RolledItem, data: ActionData) -> dict[RolledItem, float]:
    """Return exact independent inclusive-integer Divine outcomes.

    The 100,000-state limit applies only to exact enumeration.  Use
    :func:`apply_divine` for a reproducible individual sample beyond it.
    """
    ranges = _validated_ranges(rolled, data)
    choices = []
    state_count = 1
    values_by_id = dict(rolled.values)
    for value_range in ranges:
        if value_range.protected:
            choices.append((values_by_id[value_range.mod_id],))
            continue
        width = value_range.high - value_range.low + 1
        state_count *= width
        if state_count > _DISTRIBUTION_LIMIT:
            raise NotImplementedError("Divine distribution work limit")
        choices.append(range(value_range.low, value_range.high + 1))
    if not ranges:
        return {rolled: 1.0}

    probability = 1.0 / state_count
    outcomes: dict[RolledItem, float] = {}
    ids = tuple(value_range.mod_id for value_range in ranges)
    for values in product(*choices):
        outcome = RolledItem(rolled.item, tuple(zip(ids, values)))
        outcomes[outcome] = probability
    return outcomes


def apply_divine(rolled: RolledItem, data: ActionData, *, rng: random.Random) -> RolledItem:
    """Sample one inclusive-integer Divine outcome with an explicit RNG."""
    ranges = _validated_ranges(rolled, data)
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    values_by_id = dict(rolled.values)
    values = tuple(
        (
            value_range.mod_id,
            values_by_id[value_range.mod_id]
            if value_range.protected
            else rng.randint(value_range.low, value_range.high),
        )
        for value_range in ranges
    )
    return RolledItem(rolled.item, values)


def _validated_ranges(rolled: RolledItem, data: ActionData) -> tuple[_ValueRange, ...]:
    """Validate a concrete valued item before inspecting range semantics."""
    _validate_action_data(data)
    if not isinstance(rolled, RolledItem):
        raise ValueError("rolled must be a RolledItem")
    _validate_item(rolled.item, data)
    if rolled.item.rarity == _NORMAL:
        raise ValueError("divine requires non-normal item")
    if not rolled.item.mods:
        raise ValueError("divine requires at least one explicit modifier")

    protected_mods = frozenset(_retained_for_reroll(rolled.item))
    ranges = tuple(
        _ValueRange(mod.id, low, high, mod in protected_mods)
        for mod in rolled.item.mods
        if (bounds := _integer_range(mod.id, _row_for(mod, data))) is not None
        for low, high in (bounds,)
    )
    _validate_values(rolled.values, ranges)
    return ranges


def _integer_range(mod_id: str, row: dict) -> tuple[int, int] | None:
    """Extract one unambiguous inclusive integer range from projected text."""
    stat_text = row.get("stat_text")
    if not isinstance(stat_text, list) or len(stat_text) != 1 or not isinstance(stat_text[0], str):
        _unsupported_shape(mod_id)
    text = stat_text[0]
    matches = tuple(_INTEGER_RANGE.finditer(text))
    if not matches:
        if re.search(r"\d", text):
            _unsupported_shape(mod_id)
        return None
    if len(matches) != 1:
        _unsupported_shape(mod_id)
    match = matches[0]
    outside = text[:match.start()] + text[match.end():]
    if re.search(r"\d", outside):
        _unsupported_shape(mod_id)
    low, high = int(match.group("low")), int(match.group("high"))
    if low > high:
        _unsupported_shape(mod_id)
    return low, high


def _validate_values(values: object, ranges: tuple[_ValueRange, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError("values must be a tuple")
    expected_ids = tuple(value_range.mod_id for value_range in ranges)
    seen: set[str] = set()
    actual_ids: list[str] = []
    values_by_id: dict[str, int] = {}
    for entry in values:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError("values must contain (modifier id, integer value) tuples")
        mod_id, value = entry
        if not isinstance(mod_id, str):
            raise ValueError("value modifier ids must be strings")
        if mod_id in seen:
            raise ValueError(f"duplicate Divine value modifier id: {mod_id}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Divine value must be an integer: {mod_id}")
        seen.add(mod_id)
        actual_ids.append(mod_id)
        values_by_id[mod_id] = value
    if set(actual_ids) != set(expected_ids) or len(actual_ids) != len(expected_ids):
        raise ValueError("Divine values must exactly match ranged affix IDs")
    if tuple(actual_ids) != expected_ids:
        raise ValueError("Divine values must use source-item order")
    for value_range in ranges:
        value = values_by_id[value_range.mod_id]
        if value < value_range.low or value > value_range.high:
            raise ValueError(f"Divine value outside source range: {value_range.mod_id}")


def _unsupported_shape(mod_id: str) -> None:
    raise NotImplementedError(f"unsupported Divine value shape: {mod_id}")
