"""The natural tier ladder of a mod on a base, built from the raw mods and bases (no planner code).

What a tier is, from the game data alone: the mods that can spawn on a base are the mods whose
`spawn_weights` give a positive weight for the base's tags (the first entry whose tag the base has
decides, and the last entry is the `default` tag). Mods of one ladder share a mod `type`, a
generation type (prefix or suffix) and a domain. Within a ladder the mod with the highest required
level is tier 1; a mod's tier is 1 plus the number of mods with a strictly higher required level.
The ladder does not depend on the item level (a tier the item level does not allow is still a tier).

The ticket calls the ladder "of a family". Mods of one `groups` family can have several mod types (the
five "+1 to Level of all X Skill Gems" amulet prefixes), each its own ladder, so the type is used.

Battle Royale copies (a mod id with `Royale` in it) are left out: four of them have a positive spawn weight
in the data (issue #248) and the Craft of Exile emulator never rolls them, so on Sorcerer Boots
`MovementVelocity1` is tier 6 of 6, not 7 of 7. The same goes for Royale bases.
"""

import re

# raw item class -> the trade site's `category` option. A fact about the trade site, not the planner.
TRADE_CATEGORY = {
    "Amulet": "accessory.amulet",
    "Ring": "accessory.ring",
    "Belt": "accessory.belt",
    "Boots": "armour.boots",
    "Gloves": "armour.gloves",
    "Helmet": "armour.helmet",
    "Body Armour": "armour.chest",
    "Shield": "armour.shield",
    "Quiver": "armour.quiver",
    "Bow": "weapon.bow",
}

_RANGE = re.compile(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def is_royale(identifier: str) -> bool:
    """A Battle Royale mod or base: its id says so."""
    return "Royale" in identifier


def spawn_weight(mod: dict, tags) -> int:
    """The weight of `mod` on an item with `tags`: the first spawn entry the tags satisfy, else 0."""
    for entry in mod.get("spawn_weights", ()):
        if entry["tag"] in tags:
            return entry["weight"]
    return 0


def ladder(mods: dict, base_tags, mod_id: str) -> dict[str, int]:
    """Tier by mod id of every mod in the ladder of `mod_id` on a base with `base_tags`.

    The ladder holds the mods of the same type, generation type and domain that can spawn on the base.
    `mod_id` itself is in it only if it can spawn there.
    """
    own = mods[mod_id]
    key = (own["type"], own["generation_type"], own["domain"])
    members = {
        other_id: other["required_level"]
        for other_id, other in mods.items()
        if not is_royale(other_id)
        and (other["type"], other["generation_type"], other["domain"]) == key
        and spawn_weight(other, base_tags) > 0
    }
    return {
        member: 1 + sum(level > own_level for level in members.values()) for member, own_level in members.items()
    }


def stat_ranges(mod: dict) -> list[tuple[float, float]]:
    """The (min, max) of each stat of the mod, in the order the data lists them."""
    return [(stat["min"], stat["max"]) for stat in mod["stats"]]


def normalise_stat_text(text: str) -> str:
    """A stat line with every number and every range replaced by `#`, as the buy specs write it."""
    text = _RANGE.sub("#", text)
    text = _NUMBER.sub("#", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def bases_named(bases: dict, name: str) -> list[str]:
    """The ids of the bases a player can hold under the English name `name`, sorted.

    Released bases only, Royale bases never. Where a name is shared and some of its bases are on sale, the
    ones tagged `not_for_sale` are dropped (the second Leather Belt is `BeltRoyale1`); where all are tagged
    so (the three Two-Toned Boots, the Atlas bases), all stay, since none is the better reading.
    """
    ids = [
        base_id
        for base_id, base in bases.items()
        if base["name"] == name and base["release_state"] == "released" and not is_royale(base_id)
    ]
    on_sale = [base_id for base_id in ids if "not_for_sale" not in bases[base_id]["tags"]]
    return sorted(on_sale or ids)


def base_ids_of(bases: dict, reference: str) -> list[str]:
    """The base ids a target's `base:` value can mean: itself if it is an id, else every base of that name."""
    if reference in bases:
        return [reference]
    return bases_named(bases, reference)


def bases_of_category(bases: dict, category: str) -> list[str]:
    """The ids of the bases on sale in a trade category (a search without a base type accepts all of them)."""
    classes = {item_class for item_class, option in TRADE_CATEGORY.items() if option == category}
    return sorted(
        base_id
        for base_id, base in bases.items()
        if base["item_class"] in classes
        and base["release_state"] == "released"
        and not is_royale(base_id)
        and "not_for_sale" not in base["tags"]
    )


def pool_of(mods: dict, base_tags, cache: dict | None = None) -> frozenset:
    """The ids of the ordinary mods (domain `item`, no Royale copy) that can spawn on a base with `base_tags`."""
    key = (id(mods), tuple(sorted(base_tags)))
    if cache is not None and key in cache:
        return cache[key]
    found = frozenset(
        mod_id
        for mod_id, mod in mods.items()
        if mod["domain"] == "item" and not is_royale(mod_id) and spawn_weight(mod, base_tags) > 0
    )
    if cache is not None:
        cache[key] = found
    return found
