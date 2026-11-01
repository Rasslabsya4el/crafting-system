"""The influence crafts on the real 3.29.3.3 dump (ticket #154).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip
cleanly when it is not there, with the reason; CI fetches it (ticket #165), so they run there.

The pool sizes are those of research ticket #86 (`docs/research/2026-10-31-influence.md`, "Worked pools"): records of an influence on a
class at item level 100, the weight of each side. The Shaper helmet pool is pinned at 11 prefix and 20 suffix records.
"""

from fractions import Fraction

import pytest

from crafting_system.actions import BeastInfluenceRecipe, InfluencedExaltedOrb, OrbOfDominance, influence_pool
from crafting_system.data import MissingDataError, PIN, load_game_data
from crafting_system.data.elevated import is_elevated, load_elevated
from crafting_system.items import ExplicitMod, Influence, Item, Rarity, Side

HELMET = "Metadata/Items/Armours/Helmets/HelmetStr10"  # Royal Burgonet
SHAPER, ELDER, HUNTER = Influence.SHAPER, Influence.ELDER, Influence.HUNTER


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def rare(data, base_id, *mod_ids, level=100, **fields):
    mods = tuple(ExplicitMod(i, 1, tuple(min(s.min, s.max) for s in data.mods[i].stats)) for i in mod_ids)
    return Item.build(data, base_id=base_id, item_level=level, rarity=Rarity.RARE, mods=mods, **fields)


def base_named(data, name):
    return next(base.id for base in data.base_items.values() if base.name == name and base.release_state == "released")


def pool_shape(outcomes) -> dict[str, tuple[int, int]]:
    """Per side: how many mod records the pool holds, and their weights added up."""
    shape = {}
    for side in Side:
        entries = [entry for family in outcomes.pool if family.side is side for entry in family.mods]
        shape[side.value] = (len(entries), int(sum(entry.weight for entry in entries)))
    return shape


def test_the_shaper_helmet_pool_is_11_prefix_and_20_suffix_records(data):
    outcomes = InfluencedExaltedOrb(SHAPER).outcomes(data, rare(data, HELMET))

    assert pool_shape(outcomes) == {"prefix": (11, 5600), "suffix": (20, 11100)}
    sides = outcomes.distribution(lambda mod: mod.generation_type)
    assert sides == {frozenset({("prefix", 1)}): Fraction(5600, 16700), frozenset({("suffix", 1)}): Fraction(11100, 16700)}


@pytest.mark.parametrize(
    ("base", "influence", "level", "expected"),
    [
        ("Heavy Belt", HUNTER, 75, {"prefix": (4, 1750), "suffix": (7, 3250)}),
        ("Heavy Belt", ELDER, 75, {"prefix": (8, 4600), "suffix": (14, 10400)}),
        ("Titanium Spirit Shield", SHAPER, 100, {"prefix": (1, 800), "suffix": (10, 8000)}),
        ("Astral Plate", ELDER, 100, {"prefix": (6, 2200), "suffix": (8, 5600)}),
    ],
)
def test_the_other_worked_pools_of_the_research(data, base, influence, level, expected):
    outcomes = InfluencedExaltedOrb(influence).outcomes(data, rare(data, base_named(data, base), level=level))
    assert pool_shape(outcomes) == expected


def test_the_pool_of_an_influence_never_holds_an_ordinary_mod_or_an_elevated_one(data):
    item = rare(data, HELMET).changed(data, influences=frozenset({SHAPER}))
    mods = [entry.mod for family in influence_pool(data, item, SHAPER) for entry in family.mods]
    assert mods and not any(is_elevated(mod) for mod in mods)
    assert all(next(w.tag for w in mod.spawn_weights if w.weight > 0) == "helmet_shaper" for mod in mods)


def test_a_hunters_exalted_orb_and_the_hunter_recipe_draw_from_the_same_pool(data):
    belt = base_named(data, "Heavy Belt")
    orb = InfluencedExaltedOrb(HUNTER).outcomes(data, rare(data, belt, level=75))
    recipe = BeastInfluenceRecipe(HUNTER).outcomes(data, rare(data, belt, level=75, influences=frozenset({HUNTER})))
    assert pool_shape(recipe) == pool_shape(orb) == {"prefix": (4, 1750), "suffix": (7, 3250)}


# --- the Orb of Dominance and the committed Elevated mapping ------------------------------------------------------------------


def _helmet_shaper_pairs(data):
    """The committed (top-tier mod, Elevated mod) pairs that are Shaper helmet mods, one per family."""
    seen, found = set(), []
    for top, elevated in load_elevated().of_top_tier.items():
        if top in data.mods and elevated in data.mods and data.mods[elevated].spawn_weights[0].tag == "helmet_shaper":
            mod = data.mods[top]
            if mod.families[0] not in seen:
                seen.add(mod.families[0])
                found.append((top, elevated))
    return found


def test_a_dominance_pair_has_chance_one_over_n_times_n_minus_one_on_a_real_helmet(data):
    pairs = _helmet_shaper_pairs(data)
    chosen = [p for p in pairs if data.mods[p[0]].generation_type == "prefix"][:2] + [p for p in pairs if data.mods[p[0]].generation_type == "suffix"][:2]
    assert len(chosen) == 4
    item = rare(data, HELMET, *(top for top, _ in chosen), influences=frozenset({SHAPER}))

    outcomes = OrbOfDominance().outcomes(data, item)

    assert len(outcomes.results) == 12 and {chance for chance, _ in outcomes.results} == {Fraction(1, 12)}
    elevated = {top: up for top, up in chosen}
    for chance, result in outcomes.results:
        ids = {entry.mod_id for entry in result.mods}
        assert len(ids) == 3 and len(ids & set(elevated.values())) == 1  # one removed, one became its Elevated mod
        assert result.influences == {SHAPER}


def test_a_lower_tier_upgrades_to_the_next_tier_on_a_real_helmet(data):
    from crafting_system.actions.pool import tiers_of

    shaper = rare(data, HELMET).changed(data, influences=frozenset({SHAPER}))
    by_type: dict[tuple[str, str], dict[int, str]] = {}
    for mod_id, tier in tiers_of(data, shaper).items():
        mod = data.mods[mod_id]
        if next((w.tag for w in mod.spawn_weights if w.weight > 0), None) == "helmet_shaper":
            by_type.setdefault((mod.type, mod.generation_type), {})[tier] = mod_id
    lower, better = next(
        (found[2], found[1]) for (_, side), found in by_type.items() if side == "prefix" and 2 in found and 1 in found
    )
    suffix_top, suffix_elevated = next((t, e) for t, e in _helmet_shaper_pairs(data) if data.mods[t].generation_type == "suffix")
    held = rare(data, HELMET, lower, suffix_top, influences=frozenset({SHAPER}))

    outcomes = OrbOfDominance().outcomes(data, held)

    assert {frozenset(entry.mod_id for entry in result.mods) for _, result in outcomes.results} == {
        frozenset({better}),  # removed the suffix, upgraded the lower prefix to the next tier
        frozenset({suffix_elevated}),  # removed the prefix, upgraded the top-tier suffix to its Elevated version
    }


def test_the_committed_mapping_is_for_the_pinned_export(data):
    elevated = load_elevated()
    assert elevated.repoe_version == PIN.version == data.version
    assert len(elevated.of_top_tier) >= 200 and elevated.unresolved


def test_every_committed_pair_links_an_ordinary_mod_to_an_elevated_mod_of_its_family_and_tag(data):
    for top, elevated in load_elevated().of_top_tier.items():
        ordinary, raised = data.mods[top], data.mods[elevated]
        assert not is_elevated(ordinary) and is_elevated(raised), top
        assert set(ordinary.families) & set(raised.families), top
        assert ordinary.generation_type == raised.generation_type, top
        tag = raised.spawn_weights[0].tag
        assert all(w.weight == 0 for w in raised.spawn_weights), elevated
        assert any(w.tag == tag and w.weight > 0 for w in ordinary.spawn_weights), top


def test_every_committed_top_tier_mod_is_tier_one_on_a_base_of_its_class(data):
    from crafting_system.actions.pool import tiers_of

    classes = {"helmet": "Helmet", "gloves": "Gloves", "boots": "Boots", "body_armour": "Body Armour"}
    keys = {"shaper": Influence.SHAPER, "elder": Influence.ELDER, "crusader": Influence.CRUSADER, "basilisk": Influence.HUNTER,
            "eyrie": Influence.REDEEMER, "adjudicator": Influence.WARLORD}
    bases = {item_class: [b.id for b in data.base_items.values() if b.item_class == item_class and b.release_state == "released"] for item_class in classes.values()}
    checked = 0
    for top, elevated in load_elevated().of_top_tier.items():
        tag = next(w.tag for w in data.mods[elevated].spawn_weights if w.tag.split("_")[0] in ("helmet", "gloves", "boots", "body"))
        cls, key = ("body_armour", tag[len("body_armour_"):]) if tag.startswith("body_armour") else tag.split("_")
        tiers = None
        for base_id in bases[classes[cls]]:
            item = rare(data, base_id).changed(data, influences=frozenset({keys[key]}))
            tiers = tiers_of(data, item)
            if top in tiers:
                break
        assert tiers is not None and tiers.get(top) == 1, (top, tag, tiers.get(top) if tiers else None)
        checked += 1
    assert checked == len(load_elevated().of_top_tier)
