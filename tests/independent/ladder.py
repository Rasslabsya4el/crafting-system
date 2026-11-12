"""The one natural tier ladder and the one base-name rule of the independent checks (ticket #419).

`tests/oracle/` (the goal oracle, #411) and `tests/reconcile/` (the reconciliation checks, #412) both need the
tier of a mod on a base, worked out from the raw repoe-fork export with no planner code. They had a copy each;
this is the one they now share. It imports the standard library only (`test_independent_guard.py` scans it).

What a tier is, from the game data alone
  * A mod is natural on an item when its domain is the base's own domain (`item` for gear, `misc` for jewels),
    it is a prefix or a suffix, it is not essence-only, it is not a Battle Royale copy (its id holds `Royale`),
    and its spawn weight on the item's tags is above zero.
  * The spawn weight is the weight of the FIRST entry of the mod's `spawn_weights` whose tag the item has; a
    later entry is ignored. The last entry is normally the `default` tag.
  * The item's tags are the base's tags, plus for each influence the base's tags with the influence's suffix
    (`belt` + hunter -> `belt_basilisk`).
  * The natural mods of one mod `type` and one generation type form a ladder. In it, tier 1 is the highest
    required level, and a mod's tier is 1 plus the number of ladder mods of a strictly higher required level.
  * The ladder does not depend on the item level: a tier the item level does not allow is still a tier.

Settled when the two copies were merged (the comparison is `test_ladder_agreement.py`)
  * Domain. The reconcile copy scoped a ladder by the domain of the MOD asked about; the oracle by the domain
    of the BASE. They agree on every gear base. They differ on a jewel: ten `IncreasedLife` and nine
    `LifeRegeneration` mods of domain `item` carry a `default` weight, so the reconcile copy let them spawn on
    the Cobalt Jewel (domain `misc`). The game rolls on a base only the mods of the base's domain, so the base
    decides.
  * Influence. The reconcile copy had no influence tags, so a Hunter belt or bow showed none of its Hunter
    ladders. The oracle's tags are kept.
  * Essence-only and generation types other than prefix and suffix. The oracle's rule is kept: the data holds no
    essence-only mod with a positive weight, so it changes no tier today, and a unique or a corrupted mod is no
    rung of a tier ladder.
  * Battle Royale copies. Both copies leave them out (four have a positive spawn weight, issue #248).
  * An influence on a class that takes none (ticket #433). `item_tags` refuses it (`InfluenceError`), as the planner refuses
    it (`OutOfScopeError`, `actions/influence.py`): the item class of the base must be one of `INFLUENCE_CLASSES`. An unknown
    influence name is the same error with the six names listed. A base entry without a name or a list of tags is
    `MalformedBase` in `bases_named` and `bases_of_category`, not skipped.
  * A base given by name. The reconcile copy left out Royale bases and, where a name has bases on sale, the ones
    tagged `not_for_sale`; the oracle left out Royale bases only and took the first id. Now one rule, below.
"""

SIDES = ("prefix", "suffix")
ROYALE_MARKER = "Royale"

# The tag an influence adds to a base tag: `belt_basilisk` is a Hunter belt (the export's own spelling).
INFLUENCE_TAG = {
    "shaper": "shaper",
    "elder": "elder",
    "crusader": "crusader",
    "hunter": "basilisk",
    "redeemer": "eyrie",
    "warlord": "adjudicator",
}

# The item classes that take an influence: the ones whose bases have an influence tag in the spawn weights of the mods
# (`<base tag>_shaper` and the like). Read from the raw export, 24 classes of 3.29.3.3; `test_ladder_agreement.py` derives the
# same set from the data. A jewel, a flask or a tincture is not among them.
INFLUENCE_CLASSES = frozenset(
    {
        "Amulet",
        "Belt",
        "Body Armour",
        "Boots",
        "Bow",
        "Claw",
        "Dagger",
        "Gloves",
        "Helmet",
        "One Hand Axe",
        "One Hand Mace",
        "One Hand Sword",
        "Quiver",
        "Ring",
        "Rune Dagger",
        "Sceptre",
        "Shield",
        "Staff",
        "Thrusting One Hand Sword",
        "Two Hand Axe",
        "Two Hand Mace",
        "Two Hand Sword",
        "Wand",
        "Warstaff",
    }
)


class InfluenceError(ValueError):
    """An influence that no item of the class can have, or that does not exist; the message says which."""


class MalformedBase(ValueError):
    """A base entry of the export that lacks what the rule needs; the message names the entry."""


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
    "Wand": "weapon.wand",
}


def is_royale(identifier: str) -> bool:
    """A Battle Royale mod or base: its id says so."""
    return ROYALE_MARKER in identifier


def item_tags(base_tags, influences=(), item_class=None) -> frozenset[str]:
    """The tags of an item: the base's tags, plus each base tag with the suffix of each influence.

    An influence needs the item class of the base (`item_class`, the export's own spelling) and the class must take an
    influence, as the planner refuses an influence on a jewel or a flask (`actions/influence.py`, `influence_tag`).
    `InfluenceError` for an influence that is not one of the six, for an influence without a class, and for a class that
    takes none. With no influence the class is not asked.
    """
    tags = set(base_tags)
    for influence in influences:
        if influence not in INFLUENCE_TAG:
            raise InfluenceError(f"no influence named {influence!r}; the influences are {', '.join(sorted(INFLUENCE_TAG))}")
        if item_class is None:
            raise InfluenceError(f"the influence {influence!r} needs the item class of the base, and none was given")
        if item_class not in INFLUENCE_CLASSES:
            raise InfluenceError(f"an item of class {item_class!r} takes no influence (asked for {influence!r})")
        suffix = INFLUENCE_TAG[influence]
        tags.update(f"{tag}_{suffix}" for tag in base_tags)
    return frozenset(tags)


def spawn_weight(mod: dict, tags) -> int:
    """The weight of `mod` on an item with `tags`: the first spawn entry the tags satisfy, else 0."""
    for entry in mod.get("spawn_weights", ()):
        if entry["tag"] in tags:
            return entry["weight"]
    return 0


def is_natural(mod_id: str, mod: dict, tags, domain: str) -> bool:
    """Whether the mod can be rolled by the game on an item of this domain with these tags."""
    return (
        mod["domain"] == domain
        and mod["generation_type"] in SIDES
        and not mod.get("is_essence_only", False)
        and not is_royale(mod_id)
        and spawn_weight(mod, tags) > 0
    )


def tiers_of(levels: dict[str, int]) -> dict[str, int]:
    """Tier by mod id from required level by mod id: tier 1 is the highest level, ties share a tier."""
    return {mod_id: 1 + sum(other > level for other in levels.values()) for mod_id, level in levels.items()}


def natural_ladders(mods: dict, tags, domain: str) -> dict[tuple[str, str], dict[str, int]]:
    """Every natural ladder on an item: tier by mod id, for each (mod type, generation type)."""
    groups: dict[tuple[str, str], dict[str, int]] = {}
    for mod_id, mod in mods.items():
        if is_natural(mod_id, mod, tags, domain):
            groups.setdefault((mod["type"], mod["generation_type"]), {})[mod_id] = mod["required_level"]
    return {key: tiers_of(levels) for key, levels in groups.items()}


def ladder_of(mods: dict, tags, domain: str, mod_id: str) -> dict[str, int]:
    """Tier by mod id of the ladder `mod_id` belongs to (its type and generation type) on an item.

    `mod_id` itself is in it only if it is natural there; otherwise the ladder of its type is still returned.
    """
    own = mods[mod_id]
    key = (own["type"], own["generation_type"])
    levels = {
        other_id: other["required_level"]
        for other_id, other in mods.items()
        if (other["type"], other["generation_type"]) == key and is_natural(other_id, other, tags, domain)
    }
    return tiers_of(levels)


# --- the base a name or an id stands for ---------------------------------------------------------------------------


def checked_base(base_id: str, base, *keys: str) -> dict:
    """The base entry itself when it is a mapping that holds every key in `keys`; else `MalformedBase`, naming the entry.

    A text key (`name`, `item_class`) must hold text; `tags` must hold a list. An entry that fails is not skipped: a rule that
    passes over it would answer for the rest of the export while one base is unread.
    """
    if not isinstance(base, dict):
        raise MalformedBase(f"base entry {base_id!r} is {type(base).__name__}, not a mapping")
    for key in keys:
        if key not in base:
            raise MalformedBase(f"base entry {base_id!r} has no {key!r}")
        if key == "tags":
            if not isinstance(base[key], list):
                raise MalformedBase(f"base entry {base_id!r}: 'tags' is {type(base[key]).__name__}, not a list")
        elif not isinstance(base[key], str):
            raise MalformedBase(f"base entry {base_id!r}: {key!r} is {type(base[key]).__name__}, not text")
    return base


def bases_named(bases: dict, name: str) -> list[str]:
    """The ids of the bases a player can hold under the English name `name`, sorted.

    Released bases only, Royale bases never. Where a name is shared and some of its bases are on sale, the
    ones tagged `not_for_sale` are dropped (the second Leather Belt is `BeltRoyale1`); where all are tagged so
    (the three Two-Toned Boots, the Atlas bases), all stay, since none is the better reading.

    Every entry is read, so a malformed one (no `name`, no list of `tags`, not a mapping) is `MalformedBase`, not skipped.
    A missing `release_state` reads as released.
    """
    ids = []
    for base_id, entry in bases.items():
        base = checked_base(base_id, entry, "name", "tags")
        if base["name"] == name and base.get("release_state", "released") == "released" and not is_royale(base_id):
            ids.append(base_id)
    on_sale = [base_id for base_id in ids if "not_for_sale" not in bases[base_id]["tags"]]
    return sorted(on_sale or ids)


def base_ids_of(bases: dict, reference: str) -> list[str]:
    """The base ids a target's `base:` value can mean: itself if it is an id, else every base of that name."""
    if reference in bases:
        return [reference]
    return bases_named(bases, reference)


def bases_of_category(bases: dict, category: str) -> list[str]:
    """The ids of the bases on sale in a trade category (a search without a base type accepts all of them).

    Every entry is read, so a malformed one (no `item_class`, no list of `tags`, not a mapping) is `MalformedBase`.
    """
    classes = {item_class for item_class, option in TRADE_CATEGORY.items() if option == category}
    found = []
    for base_id, entry in bases.items():
        base = checked_base(base_id, entry, "item_class", "tags")
        if (
            base["item_class"] in classes
            and base.get("release_state", "released") == "released"
            and not is_royale(base_id)
            and "not_for_sale" not in base["tags"]
        ):
            found.append(base_id)
    return sorted(found)
