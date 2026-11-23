"""Whether a stored price was taken for the item a buy spec describes (#474, OR-3, OR-7).

A trade price keeps the body of the search it came from (`detail.query`). When the spec computed from a target searches another item than
that body did, the price is not the price of the item the key names. `other_item` says in words what the stored search asked for instead;
the report and the page print that next to the price, so a number is never shown as the price of a narrower item than it is.
"""

import dataclasses
from collections.abc import Mapping
from typing import Any

from .trade_query import INFLUENCE_STAT_IDS, BuySpec


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
    also matched the item of the spec (a lower level, no base type, no minimum); another means it asked for a different rarity, influence,
    corruption or Memory Strand minimum (a stranded purchase, ADR-0043).
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
        parts.append(f"any {category_words(category)} base" if category else "any base")
    elif spec.base_type is not None and stored_type != spec.base_type:
        parts.append(f"base {stored_type}")
        another = True
    level = _filters(query, "misc_filters").get("ilvl") or {}
    if (level.get("min"), level.get("max")) != (spec.item_level_min, spec.item_level_max):
        parts.append(_level_words(level.get("min"), level.get("max")))
    stored_strands = (_filters(query, "misc_filters").get("memory_level") or {}).get("min")
    if stored_strands != spec.memory_strands_min:  # more strands cut more tiers, so a price for another minimum is of another item (ADR-0043)
        parts.append(f"{stored_strands} or more Memory Strands" if stored_strands is not None else "any Memory Strands")
        another = True
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


def searched_spec(spec: BuySpec, stored: Mapping[str, Any]) -> BuySpec:
    """`spec` as the stored search asked for it: the item a price was taken for, for the page to name (#937, OR-7).

    The rarity, the base type (none: any base of the category), the item-level window, the influences, the corruption and each mod's
    minimum are the stored body's; the mods keep `spec`'s stats, matched to the stored filters of their group (`fractured`, `implicit`,
    `explicit`) in order, and a mod whose group the stored search has no filter of is left out (the search did not ask for it).
    """
    query = stored.get("query") if isinstance(stored.get("query"), Mapping) else stored
    type_filters = _filters(query, "type_filters")
    misc = _filters(query, "misc_filters")
    level = misc.get("ilvl") or {}
    ids = [found for group in query.get("stats") or [] for found in group.get("filters") or []]
    minimums: dict[str, list[float | None]] = {}
    for found in ids:
        group = str(found["id"]).split(".", 1)[0]
        if group != "pseudo":
            minimums.setdefault(group, []).append((found.get("value") or {}).get("min"))
    mods = []
    for mod in spec.mods:
        left = minimums.get("implicit" if mod.implicit else "fractured" if mod.fractured else "explicit") or []
        if left:
            mods.append(dataclasses.replace(mod, minimum=left.pop(0)))
    stored_type = query.get("type")
    influences = tuple(name for name, stat in INFLUENCE_STAT_IDS.items() if stat in {str(found["id"]) for found in ids})
    return dataclasses.replace(
        spec,
        base_type=stored_type if isinstance(stored_type, str) else None,
        category=(type_filters.get("category") or {}).get("option") or spec.category,
        rarity=(type_filters.get("rarity") or {}).get("option") or spec.rarity,
        item_level_min=level.get("min"),
        item_level_max=level.get("max"),
        influences=influences,
        corrupted=(misc.get("corrupted") or {}).get("option") == "true",
        mods=tuple(mods),
    )


def wider_words(phrase: str | None) -> str | None:
    """`other_item`'s "price taken for a wider item (item level 84 or more)" as what it is taken for: "item level 84 or more"; None stays None."""
    if phrase is None:
        return None
    start, end = phrase.find("("), phrase.rfind(")")
    return phrase[start + 1 : end] if 0 <= start < end else phrase


_CATEGORY_WORDS = {"armour.chest": "body armour"}


def category_words(category: str) -> str:
    """The trade site's category option in words (`accessory.ring` -> `ring`): a page never prints the option itself (#553, #481)."""
    return _CATEGORY_WORDS.get(category, category.rsplit(".", 1)[-1])
