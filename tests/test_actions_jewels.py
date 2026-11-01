"""Crafting jewels with the ordinary orbs, on the real 3.29.3.3 dump (ticket #201).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.

Done when (the ticket), and the test of each:

1. Each listed action accepts a jewel where the game allows it and refuses it with a reason where it does not, with
   the claim and its source: `test_each_orb_works_on_a_jewel_and_cites_its_claim` (Transmutation, Alteration,
   Augmentation, Regal, Alchemy, Chaos, Exalted, Annulment, Scouring), `test_a_resonator_works_on_a_jewel...`,
   `test_an_essence_is_refused...`, `test_the_bench_is_refused...`, the cluster jewel and the actions that are not
   modelled on a jewel, and `test_the_claims_of_the_jewel_rules_have_their_sources`.
2. Jewel affix limits come from the data and a third prefix is never drawn: `test_the_capacity_of_a_jewel_comes_from_the_claim`,
   `test_a_third_prefix_is_never_drawn_*`.
3. The end-to-end plan for a Cobalt Jewel (life and two attack-speed mods) is in `test_cli_jewel_real.py`.
4. Doubtful points: the comment on #198 (the emulator) and the claims marked approximate.

The hand chances come from `jewel_oracle`, which reads the raw mods and shares no code with the engine.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from jewel_oracle import PREFIX, SUFFIX, chance_of_families, family_table

from crafting_system.actions import (
    AlchemyOrb,
    AlterationOrb,
    AnnulmentOrb,
    ApplyEssence,
    ApplyFossils,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    DivineOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    RegalOrb,
    ScouringOrb,
    TransmutationOrb,
    build_pool,
)
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, Side, capacity, tier_table
from crafting_system.rules import rule_by_id

COBALT = "Metadata/Items/Jewels/JewelInt"
CRIMSON = "Metadata/Items/Jewels/JewelStr"
VIRIDIAN = "Metadata/Items/Jewels/JewelDex"
MURDEROUS_EYE = "Metadata/Items/Jewels/JewelAbyssMelee"
GHASTLY_EYE = "Metadata/Items/Jewels/JewelAbyssSummoner"
LARGE_CLUSTER = "Metadata/Items/Jewels/JewelPassiveTreeExpansionLarge"
BELT = "Metadata/Items/Belts/Belt3"
JEWELS = (COBALT, CRIMSON, VIRIDIAN, MURDEROUS_EYE, GHASTLY_EYE)

LIFE = "PercentIncreasedLifeJewel"  # (5-7)% increased maximum Life, prefix, family MaximumLifeIncreasePercent
MINION_LIFE = "MinionLifeJewel"  # prefix
WAND_SPEED = "WandAttackSpeedJewel"  # prefix, family SpecificWeaponSpeed
ATTACK_SPEED = "AttackSpeedJewel"  # (3-5)% increased Attack Speed, suffix, family IncreasedAttackSpeed
MINION_DAMAGE = "MinionDamageJewel"  # prefix, family DamageForm
SPELL_DAMAGE = "SpellDamageJewel"  # suffix, family DamageForm
DAMAGE = "DamageJewel"  # suffix, family DamageForm

ORB_CLAIM = "jewel.ordinary_orbs_work_on_jewels"
ORBS = {
    "transmutation": (TransmutationOrb(), Rarity.NORMAL),
    "alteration": (AlterationOrb(), Rarity.MAGIC),
    "augmentation": (AugmentationOrb(), Rarity.MAGIC),
    "regal": (RegalOrb(), Rarity.MAGIC),
    "alchemy": (AlchemyOrb(), Rarity.NORMAL),
    "chaos": (ChaosOrb(), Rarity.RARE),
    "exalted": (ExaltedOrb(), Rarity.RARE),
    "annulment": (AnnulmentOrb(), Rarity.RARE),
    "scouring": (ScouringOrb(), Rarity.RARE),
    "divine": (DivineOrb(), Rarity.RARE),
}
MOD_SIDES = {  # the sides of the mods each orb finds on the jewel it is tried on (magic for the magic orbs)
    "alteration": (Side.PREFIX,),
    "augmentation": (Side.PREFIX,),
    "regal": (Side.PREFIX,),
    "chaos": (Side.PREFIX, Side.SUFFIX),
    "exalted": (Side.PREFIX, Side.SUFFIX),
    "annulment": (Side.PREFIX, Side.SUFFIX),
    "scouring": (Side.PREFIX, Side.SUFFIX),
    "divine": (Side.PREFIX, Side.SUFFIX),
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def jewel(data, rarity, *mod_ids, base_id=COBALT, level=84):
    """A jewel of `base_id` holding `mod_ids` at their table tiers and lowest rolls."""
    tiers = tier_table(data, base_id)
    return Item.build(
        data, base_id=base_id, item_level=level, rarity=rarity,
        mods=tuple(
            ExplicitMod(mod_id, tiers[mod_id], tuple(min(s.min, s.max) for s in data.mods[mod_id].stats))
            for mod_id in mod_ids
        ),
    )  # fmt: skip


def side_counts(data, outcomes):
    """`{(prefixes, suffixes): chance}` of the finished item, kept mods included."""
    kept = [data.mods[entry.mod_id].generation_type for entry in outcomes.retained.mods]
    shown = outcomes.distribution(lambda mod: mod.generation_type)
    found: dict[tuple[int, int], Fraction] = {}
    for outcome, chance in shown.items():
        sides = kept + [side for side, count in outcome for _ in range(count)]
        key = (sides.count(PREFIX), sides.count(SUFFIX))
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# --- 1. each orb works on a jewel, with its claim --------------------------------------------------------------------


def held_jewel(data, base_id, rarity, *sides):
    """A jewel of `base_id` and `rarity` holding the first mod of its pool for each of `sides`."""
    pool = build_pool(data, Item.build(data, base_id=base_id, item_level=84, rarity=Rarity.RARE))
    first = {side: next(f.mods[0].mod.id for f in pool if f.side is side) for side in Side}
    return jewel(data, rarity, *(first[side] for side in sides), base_id=base_id)


@pytest.mark.parametrize("base_id", JEWELS)
@pytest.mark.parametrize("name", ORBS)
def test_each_orb_works_on_a_jewel_and_cites_its_claim(data, name, base_id):
    action, rarity = ORBS[name]

    outcomes = action.outcomes(data, held_jewel(data, base_id, rarity, *MOD_SIDES.get(name, ())))

    assert outcomes.components
    assert ORB_CLAIM in action.claims()
    rule = rule_by_id(ORB_CLAIM)
    assert rule.source_kind.value == "wiki" and rule.url == "https://www.poewiki.net/wiki/Jewel"


def test_a_normal_jewel_is_what_a_scouring_leaves(data):
    scoured = ScouringOrb().outcomes(data, jewel(data, Rarity.RARE, LIFE, ATTACK_SPEED)).retained

    assert scoured.rarity is Rarity.NORMAL and not scoured.mods


def test_an_annulment_removes_one_mod_of_a_jewel_with_chance_one_in_n(data):
    result = AnnulmentOrb().outcomes(data, jewel(data, Rarity.RARE, LIFE, ATTACK_SPEED, WAND_SPEED))

    assert sorted(len(item.mods) for _, item in result.results) == [2, 2, 2]
    assert {chance for chance, _ in result.results} == {Fraction(1, 3)}


# --- 2. the limits come from the data and a third prefix is never drawn ----------------------------------------------


@pytest.mark.parametrize("base_id", JEWELS)
def test_the_capacity_of_a_jewel_comes_from_the_claim(data, base_id):
    claim = rule_by_id("affix_count.rare_jewel_max_per_side")

    assert claim.value["rare"] == 2 and data.base_items[base_id].item_class in claim.value["item_classes"]
    ranks = (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE)
    assert [capacity(data, base_id, rarity).prefix for rarity in ranks] == [0, 1, 2]
    assert [capacity(data, base_id, rarity).suffix for rarity in ranks] == [0, 1, 2]
    assert capacity(data, BELT, Rarity.RARE).prefix == 3  # equipment keeps its three


def test_a_rare_jewel_cannot_be_built_with_a_third_prefix(data):
    with pytest.raises(ItemError):
        jewel(data, Rarity.RARE, LIFE, MINION_LIFE, WAND_SPEED)


@pytest.mark.parametrize("base_id", JEWELS)
@pytest.mark.parametrize("orb", [ChaosOrb(), AlchemyOrb()])
def test_a_third_prefix_is_never_drawn_by_a_reroll(data, orb, base_id):
    item = jewel(data, Rarity.NORMAL if isinstance(orb, AlchemyOrb) else Rarity.RARE, base_id=base_id)

    counts = side_counts(data, orb.outcomes(data, item))

    assert set(counts) == {(2, 1), (1, 2), (2, 2)}  # 3 mods (65%) or 4 (35%, `jewel.reroll_mod_count`), never a third on a side
    assert counts[2, 2] == Fraction(35, 100) and counts[2, 1] + counts[1, 2] == Fraction(65, 100)


def test_a_third_prefix_is_never_drawn_by_an_exalted_orb(data):
    result = ExaltedOrb().outcomes(data, jewel(data, Rarity.RARE, LIFE, MINION_LIFE, ATTACK_SPEED))

    assert side_counts(data, result) == {(2, 2): 1}  # the one open slot is a suffix
    assert all(entry.mod.generation_type == SUFFIX for family in result.pool for entry in family.mods if family.side is Side.SUFFIX)
    with pytest.raises(NotApplicableError):
        ExaltedOrb().outcomes(data, jewel(data, Rarity.RARE, LIFE, MINION_LIFE, ATTACK_SPEED, SPELL_DAMAGE))


def test_a_regal_orb_on_a_magic_jewel_opens_the_second_slot_of_each_side(data):
    result = RegalOrb().outcomes(data, jewel(data, Rarity.MAGIC, LIFE))

    assert result.retained.rarity is Rarity.RARE
    assert side_counts(data, result) == {(1, 1): result.distribution(lambda mod: mod.generation_type)[frozenset({(SUFFIX, 1)})]} | {
        (2, 0): result.distribution(lambda mod: mod.generation_type)[frozenset({(PREFIX, 1)})]
    }


def test_a_magic_jewel_holds_one_prefix_and_one_suffix(data):
    assert side_counts(data, TransmutationOrb().outcomes(data, jewel(data, Rarity.NORMAL))).keys() <= {(1, 0), (0, 1), (1, 1)}
    with pytest.raises(NotApplicableError):
        AugmentationOrb().outcomes(data, jewel(data, Rarity.MAGIC, LIFE, ATTACK_SPEED))  # full


# --- the pool of a jewel: item level and families on both sides -------------------------------------------------------


def weights(data, item):
    return {entry.mod.id: entry.weight for family in build_pool(data, item) for entry in family.mods}


@pytest.mark.parametrize("base_id", [COBALT, CRIMSON, VIRIDIAN])
def test_a_base_jewel_has_the_same_pool_at_item_level_1_and_84(data, base_id):
    low = weights(data, jewel(data, Rarity.RARE, base_id=base_id, level=1))

    assert low == weights(data, jewel(data, Rarity.RARE, base_id=base_id, level=84)) and len(low) > 100


def test_the_mods_of_an_abyss_jewel_are_gated_by_the_item_level(data):
    low = weights(data, jewel(data, Rarity.RARE, base_id=MURDEROUS_EYE, level=1))
    high = weights(data, jewel(data, Rarity.RARE, base_id=MURDEROUS_EYE, level=84))

    assert set(low) < set(high)


@pytest.mark.parametrize(
    ("held", "absent"),
    [
        (MINION_DAMAGE, (SPELL_DAMAGE, DAMAGE)),  # a prefix of the family DamageForm keeps its suffixes out
        (SPELL_DAMAGE, (MINION_DAMAGE, "TrapDamageJewel")),  # and a suffix keeps its prefixes out
    ],
)
def test_a_mod_on_one_side_keeps_the_rest_of_its_family_out_of_the_other_side(data, held, absent):
    side_full = jewel(data, Rarity.MAGIC, held)
    result = AugmentationOrb().outcomes(data, side_full)
    in_pool = {entry.mod.id for family in result.pool for entry in family.mods}

    assert not in_pool & set(absent)
    assert in_pool  # the other side still draws


SPANNING = {  # the families with weight on both sides of the pool: the claim lists the five that have mods on both sides
    COBALT: {"DamageForm"},
    VIRIDIAN: {"DamageForm"},
    GHASTLY_EYE: {"MinionLifeRegeneration"},
}


@pytest.mark.parametrize("base_id", sorted(SPANNING))
def test_a_chaos_orb_never_gives_two_mods_of_a_family_that_spans_both_sides(data, base_id):
    spanning = SPANNING[base_id]
    pool = build_pool(data, jewel(data, Rarity.RARE, base_id=base_id))
    sides = {}
    for family in pool:
        sides.setdefault(family.family, set()).add(family.side)
    label = lambda mod: mod.families[0] if mod.families[0] in spanning else None  # noqa: E731

    assert {name for name, found in sides.items() if len(found) == 2} == spanning
    for outcome in ChaosOrb().outcomes(data, jewel(data, Rarity.RARE, base_id=base_id)).distribution(label):
        assert all(count == 1 for name, count in outcome if name is not None)


# --- hand chances ---------------------------------------------------------------------------------------------------


COBALT_TABLE = {}


def table(data, base_id=COBALT, level=84):
    return family_table(data, base_id, level)


def test_an_augmentation_hits_a_named_suffix_with_its_weight_over_the_open_suffixes(data):
    item = jewel(data, Rarity.MAGIC, LIFE)
    hand = table(data)
    open_suffixes = sum(sides[SUFFIX] for name, sides in hand.items() if SUFFIX in sides and name != "MaximumLifeIncreasePercent")

    result = AugmentationOrb().outcomes(data, item)

    assert result.chance_all([ATTACK_SPEED]) == hand["IncreasedAttackSpeed"][SUFFIX] / open_suffixes


@pytest.mark.parametrize("wanted", [("MaximumLifeIncreasePercent",), ("IncreasedAttackSpeed",), ("DamageForm",)])
def test_a_transmutation_holds_a_named_family_with_the_hand_chance(data, wanted):
    hand = table(data)
    half = chance_of_families(hand, {PREFIX: 1, SUFFIX: 1}, 1, wanted) + chance_of_families(hand, {PREFIX: 1, SUFFIX: 1}, 2, wanted)

    label = lambda mod: wanted[0] if mod.families[0] == wanted[0] else None  # noqa: E731
    shown = TransmutationOrb().outcomes(data, jewel(data, Rarity.NORMAL)).distribution(label)
    engine = sum(chance for outcome, chance in shown.items() if any(name == wanted[0] for name, _ in outcome))

    assert engine == half / 2  # one or two mods, 1/2 each


def test_a_chaos_orb_gives_a_life_and_two_attack_speed_families_with_the_hand_chance(data):
    wanted = ("MaximumLifeIncreasePercent", "IncreasedAttackSpeed", "SpecificWeaponSpeed")
    room = {PREFIX: 2, SUFFIX: 2}
    hand = Fraction(65, 100) * chance_of_families(table(data), room, 3, wanted) + Fraction(35, 100) * chance_of_families(
        table(data), room, 4, wanted
    )
    label = lambda mod: mod.families[0] if mod.families[0] in wanted else None  # noqa: E731

    shown = ChaosOrb().outcomes(data, jewel(data, Rarity.RARE)).distribution(label)
    engine = sum(chance for outcome, chance in shown.items() if set(wanted) <= {name for name, _ in outcome})

    assert engine == hand and 0 < hand < Fraction(1, 1000)


def test_an_alchemy_orb_gives_the_same_chances_as_a_chaos_orb_on_a_rare_jewel(data):
    wanted = ("MaximumLifeIncreasePercent", "IncreasedAttackSpeed")
    label = lambda mod: mod.families[0] if mod.families[0] in wanted else None  # noqa: E731

    chaos = ChaosOrb().outcomes(data, jewel(data, Rarity.RARE)).distribution(label)
    alchemy = AlchemyOrb().outcomes(data, jewel(data, Rarity.NORMAL)).distribution(label)

    assert chaos == alchemy


def test_an_exalted_orb_hits_a_named_suffix_with_its_weight_over_the_open_suffixes(data):
    hand = table(data)
    held = ("MaximumLifeIncreasePercent", "MinionLife", "SpecificWeaponSpeed")  # no: two prefixes only
    item = jewel(data, Rarity.RARE, LIFE, MINION_LIFE, SPELL_DAMAGE)
    taken = {"MaximumLifeIncreasePercent", "MinionLife", "DamageForm"}
    open_suffixes = sum(sides[SUFFIX] for name, sides in hand.items() if SUFFIX in sides and name not in taken)

    result = ExaltedOrb().outcomes(data, item)

    assert held and result.chance_all([ATTACK_SPEED]) == hand["IncreasedAttackSpeed"][SUFFIX] / open_suffixes


# --- fossils, essences, the bench and what is not modelled ------------------------------------------------------------


def test_a_resonator_works_on_a_rare_jewel_and_cites_its_claim(data):
    action = ApplyFossils.of("Scorched Fossil")

    plain = ChaosOrb().outcomes(data, jewel(data, Rarity.RARE))
    fossil = action.outcomes(data, jewel(data, Rarity.RARE))

    assert "jewel.fossils_work_on_jewels" in action.claims()
    rule = rule_by_id("jewel.fossils_work_on_jewels")
    assert rule.source_kind.value == "coe" and rule.approximate
    fire = [
        e for f in build_pool(data, jewel(data, Rarity.RARE)) for e in f.mods
        if "fire" in e.mod.implicit_tags and "cold" not in e.mod.implicit_tags
    ]  # fmt: skip
    (_, part), = fossil.components
    boosted = {e.mod.id: e.weight for f in part.pool for e in f.mods}
    assert fire and all(boosted[e.mod.id] > e.weight for e in fire)
    assert not any("cold" in e.mod.implicit_tags for f in part.pool for e in f.mods)  # the Scorched Fossil takes cold mods out
    assert plain.pool != part.pool


def test_the_fractured_fossil_works_on_a_jewel_and_cites_its_claim(data):
    action = ApplyFossils.of("Fractured Fossil")

    outcomes = action.outcomes(data, jewel(data, Rarity.RARE))

    assert outcomes.fractures and "jewel.fracturing_orb_works_on_jewels" in action.claims()


def test_an_essence_is_refused_on_a_jewel_and_cites_its_claim(data):
    essence = ApplyEssence("Deafening Essence of Greed")

    with pytest.raises(NotApplicableError, match="takes no essence"):
        essence.outcomes(data, jewel(data, Rarity.NORMAL))
    assert "jewel.essence_takes_no_jewel" in essence.claims()
    assert rule_by_id("jewel.essence_takes_no_jewel").source_kind.value == "datamined"


def test_the_bench_is_refused_on_a_jewel_and_cites_its_claim(data):
    craft = BenchCraft("StrMasterItemGenerationCannotChangePrefixes")

    with pytest.raises(NotApplicableError, match="does not offer"):
        craft.outcomes(data, jewel(data, Rarity.RARE, LIFE))
    jewel_classes = {"Jewel", "AbyssJewel"}
    offered = [o for o in data.bench_options if jewel_classes & set(o.item_classes) and o.actions.add_explicit_mod]
    assert not offered  # claim jewel.bench_adds_no_mod_to_jewels
    assert rule_by_id("jewel.bench_adds_no_mod_to_jewels").source_kind.value == "datamined"


def test_a_cluster_jewel_is_refused_because_its_pool_depends_on_its_enchantments(data):
    item = jewel(data, Rarity.RARE, base_id=LARGE_CLUSTER)

    for name in ("transmutation", "alteration", "augmentation", "regal", "alchemy", "chaos", "exalted"):
        action, rarity = ORBS[name]
        with pytest.raises(OutOfScopeError, match="cluster jewel"):
            action.outcomes(data, jewel(data, rarity, base_id=LARGE_CLUSTER))
    with pytest.raises(OutOfScopeError, match="cluster jewel"):
        ApplyFossils.of("Scorched Fossil").outcomes(data, item)
    assert rule_by_id("jewel.cluster_pool_depends_on_enchantments").url == "https://www.poewiki.net/wiki/Cluster_Jewel"


def test_a_harvest_craft_is_not_modelled_on_a_jewel(data):
    with pytest.raises(OutOfScopeError, match="jewel"):
        HarvestReforge("lightning").outcomes(data, jewel(data, Rarity.RARE, LIFE, ATTACK_SPEED, WAND_SPEED, SPELL_DAMAGE))


def test_a_fracturing_orb_works_on_a_jewel_of_four_mods_only(data):
    four = jewel(data, Rarity.RARE, LIFE, ATTACK_SPEED, WAND_SPEED, SPELL_DAMAGE)

    result = FracturingOrb().outcomes(data, four)

    assert len(result.results) == 4 and "jewel.fracturing_orb_works_on_jewels" in FracturingOrb().claims()
    assert rule_by_id("jewel.fracturing_orb_works_on_jewels").approximate
    with pytest.raises(NotApplicableError, match="at least 4"):
        FracturingOrb().outcomes(data, jewel(data, Rarity.RARE, LIFE, ATTACK_SPEED, WAND_SPEED))


@pytest.mark.parametrize("base_id", ["Metadata/Items/Jewels/JewelTimeless", "Metadata/Items/Jewels/JewelPrismatic", "Metadata/Items/Jewels/JewelAbyssConglomerate"])
def test_a_base_that_exists_as_a_unique_only_is_out_of_scope(data, base_id):
    with pytest.raises(OutOfScopeError, match="unique item only"):
        ChaosOrb().outcomes(data, jewel(data, Rarity.RARE, base_id=base_id))


def test_the_claims_of_the_jewel_rules_have_their_sources():
    ids = [
        "jewel.ordinary_orbs_work_on_jewels",
        "jewel.reroll_mod_count",
        "jewel.base_jewel_mods_have_no_level_or_tier",
        "jewel.abyss_mods_depend_on_item_level",
        "jewel.cluster_pool_depends_on_enchantments",
        "jewel.essence_takes_no_jewel",
        "jewel.fossils_work_on_jewels",
        "jewel.fracturing_orb_works_on_jewels",
        "jewel.bench_adds_no_mod_to_jewels",
        "jewel.recombinator_refused",
        "affix_pool.family_may_span_both_sides",
        "affix_count.rare_jewel_max_per_side",
    ]
    for rule_id in ids:
        rule = rule_by_id(rule_id)
        assert rule.url.startswith("https://") and rule.quote and rule.patch_verified == "3.29.3.3"
    assert rule_by_id("jewel.recombinator_refused").source_kind.value == "owner"
    assert rule_by_id("jewel.reroll_mod_count").approximate
