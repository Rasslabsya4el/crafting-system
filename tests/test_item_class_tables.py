"""Every per-class table of `src/` covers every item class a player crafts on, walked from the game data (#1491, OR-55).

The trade category of a bought start held only the classes of the reference crafts, so a Void Sceptre or an Imperial Claw was refused in
three seconds. The walk here reads the classes from the real export, not from a list: the classes of the released bases of the domains a
player crafts on (`prices.spends.EQUIPMENT_DOMAINS`: gear, jewels, flasks; the `HiddenItem` class left out) that can take an explicit
prefix or suffix. For each such class it asks every table keyed by item class:

* `TRADE_CATEGORY`: a target that buys its start item on a base of the class gets a buy spec with that category, or the class is in
  `NO_TRADE_CATEGORY` with its reason (the error says it).
* the influence class keys (`affix_pool.influence_tags`): every gear class (domain `item`) has one, save the fishing rod, which no
  influence reaches.
* the socket table (`sockets.class_maximum_sockets`): every class whose bases are weapons or armour pieces that take sockets has a maximum.
* the trade category's words on a page (`category_words`): plain words, never the site's option.

The real export is read from the cache (CI fetches it); without it the walk skips.
"""

import pytest
from abstraction_support import real_game_data
from start_support import with_start

from crafting_system.prices.query_compare import category_words
from crafting_system.prices.spends import EQUIPMENT_DOMAINS, NOT_EQUIPMENT
from crafting_system.rules import get_rule
from crafting_system.targets import StartBuyError, buy_spec_of, parse_target
from crafting_system.targets.start_buy import NO_TRADE_CATEGORY, TRADE_CATEGORY, TRADE_CATEGORY_OF_DOMAIN, trade_category

ROYALE_MARKER = "Royale"
SOCKETED_TAGS = frozenset({"weapon", "body_armour", "boots", "gloves", "helmet", "shield"})  # the bases that hold sockets (a quiver, a ring or a flask has none)
NO_INFLUENCE = {"FishingRod"}  # no influence tag of the export names a fishing rod


def _released(base) -> bool:
    return base.release_state == "released" and ROYALE_MARKER not in base.id


def _first_explicit_family(data, base) -> str | None:
    """The family of the first prefix or suffix of the base's domain that its tags let spawn (the first tag a mod lists that the base has decides)."""
    tags = set(base.tags)
    for mod_id in sorted(data.mods):
        mod = data.mods[mod_id]
        if mod.domain != base.domain or mod.generation_type not in ("prefix", "suffix") or not mod.families or mod.is_essence_only:
            continue
        weight = next((each.weight for each in mod.spawn_weights if each.tag in tags), 0)
        if weight > 0:
            return mod.families[0]
    return None


def crafted_on_classes(data) -> dict[str, tuple[str, str]]:
    """item class -> (the id of its first released base that takes an explicit mod, that mod's family): the classes a player crafts on."""
    found: dict[str, tuple[str, str]] = {}
    for base_id in sorted(data.base_items):
        base = data.base_items[base_id]
        if base.item_class in found or not _released(base) or base.domain not in EQUIPMENT_DOMAINS or base.item_class in NOT_EQUIPMENT:
            continue
        family = _first_explicit_family(data, base)
        if family is not None:
            found[base.item_class] = (base_id, family)
    return found


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def classes(data):
    return crafted_on_classes(data)


def test_the_walk_reads_the_weapon_classes_the_reference_crafts_lack(classes):
    assert {"Sceptre", "Claw", "One Hand Sword", "Two Hand Axe", "Warstaff", "Jewel", "AbyssJewel", "LifeFlask"} <= set(classes)
    assert len(classes) >= 30


def test_every_class_a_player_crafts_on_has_a_trade_category_or_a_named_reason(classes):
    missing = sorted(item_class for item_class in classes if item_class not in TRADE_CATEGORY and item_class not in NO_TRADE_CATEGORY)
    assert missing == []
    assert set(NO_TRADE_CATEGORY) <= set(classes)  # a class left out is one the walk meets
    assert not set(NO_TRADE_CATEGORY) & set(TRADE_CATEGORY)


def test_a_bought_start_is_accepted_on_a_base_of_every_class_with_a_category(data, classes):
    for item_class, (base_id, family) in sorted(classes.items()):
        text = f"base: {base_id}\nitem_level: 84\nstart: bought\nrequirements:\n  - family: {family}\n"
        target = parse_target(with_start(text), data, source=f"{item_class}.yaml")
        if item_class in NO_TRADE_CATEGORY:
            with pytest.raises(StartBuyError, match=item_class):
                buy_spec_of(data, target)
            continue
        spec = buy_spec_of(data, target)
        assert spec.category == TRADE_CATEGORY[item_class], item_class
        assert spec.base_type == data.base_items[base_id].name


def test_a_cluster_jewel_is_searched_as_a_cluster_jewel_not_as_a_jewel(data):
    clusters = [base for base in data.base_items.values() if base.domain in TRADE_CATEGORY_OF_DOMAIN and _released(base)]

    assert clusters
    assert {trade_category(base) for base in clusters} == {"jewel.cluster"}
    assert {base.item_class for base in clusters} == {"Jewel"}  # the class alone would say jewel.base
    for base in clusters:  # and a bought start on one gets that category in its buy spec
        text = f"base: {base.id}\nitem_level: 84\nstart: bought\nrequirements:\n  - family: {_first_explicit_family(data, base)}\n"
        assert buy_spec_of(data, parse_target(with_start(text), data, source="cluster.yaml")).category == "jewel.cluster"


@pytest.mark.parametrize(
    ("text", "category"),
    [
        (  # N06 of H22 (`.claude/scratch/th22/targets/`), refused before #1491
            "base: Void Sceptre\nitem_level: 86\ninfluence: [shaper]\nrequirements:\n"
            '  - stat: "#% increased Spell Damage"\n    min_tier: 2\n    not_crafted: true\n'
            "  - family: IncreasedCastSpeed\n    min_tier: 2\n    not_crafted: true\n"
            '  - stat: "Damage Penetrates #% Elemental Resistances"\n    min_tier: 2\n    not_crafted: true\n'
            "start_item:\n  rarity: normal\nstart: bought\n",
            "weapon.sceptre",
        ),
        (  # N07 of H22
            "base: Imperial Claw\nitem_level: 84\ninfluence: []\nrequirements:\n"
            "  - family: LocalPhysicalDamagePercent\n    min_tier: 2\n    not_crafted: true\n"
            "  - family: PhysicalDamage\n    min_tier: 2\n    not_crafted: true\n"
            "  - family: IncreasedAttackSpeed\n    min_tier: 2\n    not_crafted: true\n"
            "  - family: CriticalStrikeMultiplier\n    min_tier: 2\n    not_crafted: true\n"
            "start_item:\n  rarity: normal\nstart: bought\n",
            "weapon.claw",
        ),
    ],
)
def test_the_two_refused_targets_of_h22_are_accepted(data, text, category):
    spec = buy_spec_of(data, parse_target(text, data, source="h22.yaml"))

    assert spec.category == category


def test_every_gear_class_has_an_influence_class_key(data, classes):
    keys = get_rule("affix_pool.influence_tags").value["classes"]
    gear = {item_class for item_class, (base_id, _) in classes.items() if data.base_items[base_id].domain == "item"}

    assert sorted(gear - set(keys) - NO_INFLUENCE) == []
    assert NO_INFLUENCE <= gear


def test_every_class_of_socketed_bases_has_a_socket_maximum(data, classes):
    by_class = get_rule("sockets.class_maximum_sockets").value["by_class"]
    socketed = {item_class for item_class, (base_id, _) in classes.items() if SOCKETED_TAGS & set(data.base_items[base_id].tags)}

    assert sorted(socketed - set(by_class) - NO_INFLUENCE) == []  # the fishing rod is tagged a weapon and takes no sockets table here


@pytest.mark.parametrize("category", sorted({*TRADE_CATEGORY.values(), *TRADE_CATEGORY_OF_DOMAIN.values()}))
def test_every_trade_category_reads_as_plain_words(category):
    words = category_words(category)

    assert "." not in words
    assert not words.startswith(("base", "one", "two", "rune")) or " " in words  # "basestaff", "oneaxe" are the site's option, not words
