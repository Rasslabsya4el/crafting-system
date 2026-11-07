"""Whether a stored price was taken for the item a buy spec describes (#474, OR-3, OR-7).

A trade price keeps the body of the search it came from (`detail.query`). When the spec computed from a target searches another item than
that body did, the price is not the price of the item the key names. `other_item` says in words what the stored search asked for instead;
the report and the page print that next to the price, so a number is never shown as the price of a narrower item than it is.
"""

from collections.abc import Mapping
from typing import Any

from .trade_query import BuySpec


def _filters(body: Mapping[str, Any], group: str) -> Mapping[str, Any]:
    return ((body.get("filters") or {}).get(group) or {}).get("filters") or {}


def _level_words(low: int | None, high: int | None) -> str:
    if low is None and high is None:
        return "any item level"
    if high is None:
        return f"item level {low} or more"
    if low is None:
        return f"item level {high} or less"
    return f"item level {low}" if low == high else f"item level {low} to {high}"


def other_item(spec: BuySpec, stored: Mapping[str, Any]) -> str | None:
    """One phrase saying how the stored search differs from `spec`, or None when it asked for the same item.

    `stored` is the body kept in the price entry (`{"query": {...}}`). The stat ids are compared by their group (`fractured`, `implicit`,
    `explicit`, `pseudo`) and minimum, not by id: the stat list of the site is not needed to read a price. Wider means the stored search
    also matched the item of the spec (a lower level, no base type, no minimum); another means it asked for a different rarity, influence
    or corruption.
    """
    query = stored.get("query") if isinstance(stored.get("query"), Mapping) else stored
    parts: list[str] = []
    another = False
    type_filters = _filters(query, "type_filters")
    rarity = (type_filters.get("rarity") or {}).get("option")
    if rarity != spec.rarity:
        parts.append(f"rarity {rarity or 'any'}")
        another = True
    stored_type, category = query.get("type"), (type_filters.get("category") or {}).get("option")
    if spec.base_type is not None and stored_type is None:
        parts.append(f"any {_category_words(category)} base" if category else "any base")
    elif spec.base_type is not None and stored_type != spec.base_type:
        parts.append(f"base {stored_type}")
        another = True
    level = _filters(query, "misc_filters").get("ilvl") or {}
    if (level.get("min"), level.get("max")) != (spec.item_level_min, spec.item_level_max):
        parts.append(_level_words(level.get("min"), level.get("max")))
    stored_corrupted = (_filters(query, "misc_filters").get("corrupted") or {}).get("option")
    if stored_corrupted is None:
        parts.append("corrupted or not")
    elif stored_corrupted == "true" and not spec.corrupted:
        parts.append("corrupted")
        another = True
    elif stored_corrupted == "false" and spec.corrupted:
        parts.append("not corrupted")
        another = True
    ids = [found for group in query.get("stats") or [] for found in group.get("filters") or []]
    stored_stats = sorted(
        (str(found["id"]).split(".", 1)[0], (found.get("value") or {}).get("min")) for found in ids if not str(found["id"]).startswith("pseudo.")
    )
    stored_pseudo = {str(found["id"]) for found in ids if str(found["id"]).startswith("pseudo.")}
    wanted_stats = sorted(
        ("implicit" if mod.implicit else "fractured" if mod.fractured else "explicit", mod.minimum) for mod in spec.mods
    )
    if [group for group, _ in stored_stats] != [group for group, _ in wanted_stats]:
        own = any(mod.own for mod in spec.mods)
        if own and "implicit" not in {group for group, _ in stored_stats}:
            parts.append("any base of the name")
        else:
            parts.append("other mod filters")
            another = True
    elif stored_stats != wanted_stats:
        parts.append("a lower minimum" if all((s or 0) <= (w or 0) for (_, s), (_, w) in zip(stored_stats, wanted_stats, strict=True)) else "another minimum")
    wanted_pseudo = {f"pseudo.pseudo_has_{name}_influence" for name in spec.influences}
    if stored_pseudo != wanted_pseudo:
        parts.append("other influences")
        another = True
    if not parts:
        return None
    return f"price taken for {'another' if another else 'a wider'} item ({', '.join(parts)})"


_CATEGORY_WORDS = {"armour.chest": "body armour"}


def _category_words(category: str) -> str:
    """The trade site's category option in words (`accessory.ring` -> `ring`): a page never prints the option itself (#553, #481)."""
    return _CATEGORY_WORDS.get(category, category.rsplit(".", 1)[-1])
