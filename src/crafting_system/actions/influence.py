"""The influence crafts of a single item: the six influenced Exalted Orbs, the Orb of Dominance and the beast influence recipes
(ticket #154, rules of research ticket #86 and grill B2, ADR-0030; claims `influence.*`, `dominance.*` and `influence_beast.*`).

* `InfluencedExaltedOrb(influence)` (Shaper's, Elder's, Crusader's, Hunter's, Redeemer's, Warlord's): adds its influence and one
  mod of that influence to a rare item of item level 68 or more that has an open slot. The mod is drawn through the shared add
  (item level, family exclusion, side capacity, spawn weights, the lock and Attack/Caster metamods) but only among the mods of the
  orb's influence. Refused on any influenced item (the orb's own influence included), on a fractured item and on one with an
  Eldritch implicit.
* `OrbOfDominance`: on a magic or rare body armour, boots, gloves or helmet with at least two influenced mods, removes one
  influenced mod and upgrades another by one tier (a top-tier mod becomes its Elevated version, `data/elevated.json`; an Elevated
  mod is rerolled). Both picks are uniform, the removal first, so each ordered pair has chance 1/(n(n-1)). A side that
  `Prefixes` / `Suffixes Cannot Be Changed` locks is left out of both picks; the Attack and Caster metamods are ignored.
* `BeastInfluenceRecipe(influence)`: the six beast recipes "Add a Mod to a <influence> Item". No source says which mod they add; the
  model borrows the pool of the influence's Exalted Orb (the item already has the influence), and the claim is marked approximate.

Each answers with an exact list or pool draw and none is a planner kind yet: the compressed state does not tell the influenced mods
apart where Dominance reads them, nor tier an Elevated mod (ticket #155). A mod an action puts on the item is rolled at its lowest
values (`Finite`), as for every action that lists its results.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import ModuleType

from crafting_system.data import GameData, Mod
from crafting_system.data.elevated import is_elevated, load_elevated
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.rules import Rule, get_rule

from . import add, metamods, outcomes, pool
from .add import refuse_if_nothing_to_draw
from .beasts import ANY_RARE_CREATURE, ANY_RARE_CREATURE_PRICE, CHAOS_ORB
from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .harvest_influence import influence_spawn_test
from .metamods import locked_sides, on_locked_side
from .outcomes import Outcomes
from .pool import INFLUENCE_TAGS, PoolFamily, build_pool, item_tags, tiers_of

EXALT_ADDS_INFLUENCE_AND_ONE_MOD = get_rule("influence.exalt_adds_influence_and_one_mod")
EXALT_REFUSED_ON_INFLUENCED = get_rule("influence.exalt_refused_on_influenced_item")
EXALT_REFUSED_ON_FRACTURED = get_rule("influence.exalt_refused_on_fractured_item")
EXALT_REFUSED_ON_ELDRITCH_IMPLICIT = get_rule("influence.exalt_refused_on_eldritch_implicit")
EXALT_RARE_WITH_OPEN_SLOT = get_rule("influence.exalt_rare_with_open_slot")
EXALT_MIN_ITEM_LEVEL = get_rule("influence.exalt_min_item_level")
EXALT_DRAWS_FROM_THAT_INFLUENCE = get_rule("influence.exalt_draws_from_that_influence_only")
EXALT_CATALYST_IGNORED = get_rule("influence.exalt_catalyst_quality_ignored")
EXALT_RESPECTS_METAMODS = get_rule("influence.exalt_respects_metamods")
EXALT_REFUSED_ON_CORRUPTED = get_rule("influence.exalt_refused_on_corrupted")
EXALT_REFUSED_WITHOUT_LEGAL_MOD = get_rule("influence.exalt_refused_without_legal_mod")
EXALT_COST = get_rule("influence.cost")
EXALT_CONQUEROR_TYPE_BLOCKS = get_rule("influence.exalt_conqueror_respects_type_blocks_since_3_9_2c")
INFLUENCE_STAYS_ON_THE_ITEM = get_rule("influence.state_is_on_the_item")
ONE_INFLUENCE_TWO_BY_AWAKENER = get_rule("influence.one_normally_two_by_awakener")

DOMINANCE_GATE = get_rule("dominance.gate")
DOMINANCE_REMOVES_ONE_UPGRADES_ANOTHER = get_rule("dominance.removes_one_upgrades_another")
DOMINANCE_PICKS_UNIFORM = get_rule("dominance.picks_uniform_remove_first")
DOMINANCE_UPGRADE = get_rule("dominance.upgrade_next_tier_top_becomes_elevated")
DOMINANCE_UPGRADE_IGNORES_ITEM_LEVEL = get_rule("dominance.upgrade_ignores_item_level")
DOMINANCE_ELEVATED_STEP_NO_ITEM_LEVEL = get_rule("dominance.elevated_step_has_no_item_level")
DOMINANCE_ELEVATED_ONLY_BY_DOMINANCE = get_rule("dominance.elevated_mods_only_by_dominance")
DOMINANCE_LOCKS = get_rule("dominance.respects_side_locks_ignores_type_blocks")
DOMINANCE_ELEVATED_MAPPING = get_rule("dominance.elevated_mapping_is_coe_table")
DOMINANCE_REFUSED_ON_CORRUPTED = get_rule("dominance.refused_on_corrupted")
DOMINANCE_NEVER_FRACTURED = get_rule("dominance.influenced_item_is_never_fractured")
DOMINANCE_COST = get_rule("dominance.cost")
INFLUENCED_MODS = get_rule("harvest_reforge.influence_mod_is_influence_spawn")

BEAST_RECIPES = get_rule("influence_beast.recipes")
BEAST_USES_ITEM_LEVEL = get_rule("influence_beast.uses_item_level")
BEAST_ADDS_A_MOD_OF_THAT_INFLUENCE = get_rule("influence_beast.adds_a_mod_of_that_influence")
BEAST_REFUSED_ON_CORRUPTED = get_rule("influence_beast.refused_on_corrupted")

ONE, ZERO = Fraction(1), Fraction(0)
ELEVATED_TIER = 1  # an Elevated mod has no tier in the data (it never spawns); `Item` needs one, from 1
MIN_INFLUENCED_MODS = 2  # the Orb of Dominance removes one influenced mod and upgrades another
WORDS = {influence: influence.value.capitalize() for influence in Influence}  # Shaper, Elder, ... as the orbs and recipes read


def _claims_of(own: Iterable[Rule], *helpers: ModuleType) -> frozenset[str]:
    """The ids of the rules `own` and of the rules held as constants by the `helpers`: what an answer that uses the action reads."""
    return frozenset(rule.id for rule in own) | frozenset(
        value.id for module in helpers for value in vars(module).values() if isinstance(value, Rule)
    )


def _low(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


def influence_tag(data: GameData, item: Item, influence: Influence) -> str:
    """The spawn tag of `influence` on the item class of `item`, such as `helmet_shaper` (`affix_pool.influence_tags`).

    Raises `OutOfScopeError` for an item class with no admitted class key (jewels and flasks take no influence).
    """
    base = data.base_items.get(item.base_id)
    class_key = None if base is None else INFLUENCE_TAGS.value["classes"].get(base.item_class)
    if class_key is None:
        raise OutOfScopeError(
            f"the item class ({'unknown' if base is None else base.item_class}) has no admitted influence class key, "
            "so the influence mods of its pool are not modelled"
        )
    return f"{class_key}_{INFLUENCE_TAGS.value['influences'][influence.value]}"


def influence_pool(data: GameData, item: Item, influence: Influence) -> tuple[PoolFamily, ...]:
    """The mods that one more draw on `item` can add from `influence` alone, grouped by family.

    `item` has the influence (its tag is among the tags of the spawn weights). A mod belongs to the influence when the first
    entry of its spawn weights that the item has is the influence's tag, the test of `harvest_reforge.influence_mod_is_influence_spawn`;
    it is then drawn at that weight, through the item level gate, the families on the item, and the Attack/Caster metamods.
    """
    tag, tags = influence_tag(data, item, influence), item_tags(data, item)

    def decided_by_the_influence(mod: Mod) -> Fraction:
        return ONE if next((entry.tag for entry in mod.spawn_weights if entry.tag in tags), None) == tag else ZERO

    return build_pool(data, item, factor=decided_by_the_influence)


def _draw_one(data: GameData, retained: Item, influence: Influence, what: str) -> Outcomes:
    """One more mod of `influence` on `retained`, which keeps every mod it has and holds the influence; refused when none is legal."""
    pool_ = influence_pool(data, retained, influence)
    refuse_if_nothing_to_draw(data, retained, pool_, what)
    return Outcomes(data, retained, pool_, {len(retained.mods) + 1: ONE}, None)


# --- the six influenced Exalted Orbs -------------------------------------------------------------------------------


@dataclass(frozen=True)
class InfluencedExaltedOrb(Action):
    """One Shaper's, Elder's, Crusader's, Hunter's, Redeemer's or Warlord's Exalted Orb."""

    influence: Influence

    def __post_init__(self) -> None:
        if not isinstance(self.influence, Influence):
            raise ValueError(f"the influence of an influenced Exalted Orb must be an Influence, not {self.influence!r}")

    def label(self, data: GameData | None = None) -> str:
        return f"{WORDS[self.influence]}'s Exalted Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {EXALT_COST.value[self.influence.value]: 1}

    def reads(self, data: GameData) -> Reads:
        # The families on the item decide which mods of the influence are out of the pool, and the pool is that of the new influence,
        # which the state's family types (made for the influences the item has now) do not cover: every family is told apart. The
        # orb is refused on an item with an Eldritch implicit.
        return Reads(junk=True, families=None, pool_weight=False, implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=None, draws=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        own = (
            EXALT_ADDS_INFLUENCE_AND_ONE_MOD, EXALT_REFUSED_ON_INFLUENCED, EXALT_REFUSED_ON_FRACTURED, EXALT_REFUSED_ON_ELDRITCH_IMPLICIT,
            EXALT_RARE_WITH_OPEN_SLOT, EXALT_MIN_ITEM_LEVEL, EXALT_DRAWS_FROM_THAT_INFLUENCE, EXALT_CATALYST_IGNORED,
            EXALT_RESPECTS_METAMODS, EXALT_CONQUEROR_TYPE_BLOCKS, EXALT_REFUSED_ON_CORRUPTED, EXALT_REFUSED_WITHOUT_LEGAL_MOD, EXALT_COST,
            INFLUENCE_STAYS_ON_THE_ITEM, ONE_INFLUENCE_TWO_BY_AWAKENER,
        )
        return _claims_of(own, add, pool, outcomes, metamods)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`: its influence, and one more mod of that influence.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, already has an influence, has a fractured mod or an
        Eldritch implicit, is below item level 68, has no open slot, or for which no mod of the influence is legal;
        `OutOfScopeError` for an item class that takes no influence (a jewel).
        """
        what = self.label()
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"{what} works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {what}")
        if item.influences:
            raise NotApplicableError(f"{what} cannot be used on an item that already has an influence")
        if item.fractured_mods:
            raise NotApplicableError(f"{what} cannot be used on an item with a fractured mod")
        if item.eldritch_implicits(data):
            raise NotApplicableError(f"{what} cannot be used on an item with an Eldritch implicit")
        if item.item_level < EXALT_MIN_ITEM_LEVEL.value:
            raise NotApplicableError(
                f"{what} needs item level {EXALT_MIN_ITEM_LEVEL.value} (no mod of an influence can roll below it), and this item is level {item.item_level}"
            )
        retained = item.changed(data, influences=frozenset({self.influence}))
        return _draw_one(data, retained, self.influence, what)


@kind(
    "influenced-exalted-orb",
    order=76,
    planner=False,
    why_not="no compressed-state kernel for the influence orbs yet (#155)",
)
def _influenced_exalted_orbs(data: GameData, item: Item):
    if item.rarity is Rarity.RARE and not item.influences:
        for influence in Influence:
            yield InfluencedExaltedOrb(influence)


# --- the Orb of Dominance ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OrbOfDominance(Action):
    """One Orb of Dominance.

    `elevated` are the `(top-tier mod id, Elevated mod id)` pairs the orb knows; None (the default) takes the committed mapping
    of `data/elevated.json`, which holds for the export it was made for and for no other.
    """

    elevated: tuple[tuple[str, str], ...] | None = None

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Dominance"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(DOMINANCE_COST.value)

    def reads(self, data: GameData) -> Reads:
        # Which mods are influenced, and their tiers, decide the result: every family of the junk is told apart. The side locks
        # are crafted mods of the item, which a state always holds.
        return Reads(junk=True, families=None, pool_weight=False)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It removes one mod and puts the next tier of another on the item: a mod it does not name in advance.
        return Adds(named=None, draws=False)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        own = (
            DOMINANCE_GATE, DOMINANCE_REMOVES_ONE_UPGRADES_ANOTHER, DOMINANCE_PICKS_UNIFORM, DOMINANCE_UPGRADE,
            DOMINANCE_UPGRADE_IGNORES_ITEM_LEVEL, DOMINANCE_ELEVATED_STEP_NO_ITEM_LEVEL, DOMINANCE_ELEVATED_ONLY_BY_DOMINANCE,
            DOMINANCE_LOCKS, DOMINANCE_ELEVATED_MAPPING, DOMINANCE_REFUSED_ON_CORRUPTED, DOMINANCE_NEVER_FRACTURED, DOMINANCE_COST,
            INFLUENCED_MODS, INFLUENCE_TAGS, INFLUENCE_STAYS_ON_THE_ITEM, ONE_INFLUENCE_TWO_BY_AWAKENER,
        )
        return _claims_of(own, metamods)

    def _elevated_of(self, data: GameData) -> Mapping[str, str]:
        return dict(self.elevated) if self.elevated is not None else load_elevated().for_data(data)

    def _upgraded(self, data: GameData, item: Item, entry: ExplicitMod, tiers: Mapping[str, int]) -> ExplicitMod:
        """`entry` one tier better (a top-tier mod: its Elevated version; an Elevated mod: itself), at the lowest values of the new mod.

        The next tier is a mod of the held mod's own influence: on an item with two influences, two mods of one type can both
        spawn (Elder's and Crusader's maximum Mana), and the next tier of an Elder mod is never the other influence's mod. The
        tier number stored is that of `tiers_of`, as for every other action.
        """
        mod = data.mods[entry.mod_id]
        if is_elevated(mod):
            return ExplicitMod(mod.id, ELEVATED_TIER, _low(mod))
        if mod.id not in tiers:
            raise OutOfScopeError(f"the influenced mod {mod.id} has no tier on this item, so its upgrade is not modelled")
        held_tags = frozenset(item_tags(data, item))

        def decided_by(other: Mod) -> str | None:
            return next((spawn.tag for spawn in other.spawn_weights if spawn.tag in held_tags), None)

        chain = [
            other for other in map(data.mods.__getitem__, tiers)
            if (other.type, other.generation_type, other.domain) == (mod.type, mod.generation_type, mod.domain)
            and decided_by(other) == decided_by(mod)
        ]
        better = [other for other in chain if other.required_level > mod.required_level]
        if not better:
            elevated_id = self._elevated_of(data).get(mod.id)
            if elevated_id is None or elevated_id not in data.mods:
                raise OutOfScopeError(
                    f"{mod.id} is a top-tier mod and no Elevated version of it is known for data version {data.version} "
                    "(dominance.elevated_mapping_is_coe_table; `python -m crafting_system.data elevated` lists what it could not link)"
                )
            return ExplicitMod(elevated_id, ELEVATED_TIER, _low(data.mods[elevated_id]))
        level = min(other.required_level for other in better)
        next_tier = [other for other in better if other.required_level == level]
        if len(next_tier) != 1:
            raise OutOfScopeError(
                f"the next tier of {mod.id} is ambiguous ({', '.join(sorted(other.id for other in next_tier))} share required level {level})"
            )
        # the chain only picks the mod; its tier number is the one every other action gives it (`tiers_of`)
        return ExplicitMod(next_tier[0].id, tiers[next_tier[0].id], _low(next_tier[0]))

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of using the orb on `item`: one result per ordered pair (removed, upgraded) of influenced mods, each 1/(n(n-1)).

        An influenced mod is one the item's influence tags decide (`harvest_reforge.influence_mod_is_influence_spawn`); the n of them
        on an unlocked side are the candidates of both picks. A mod an Elevated mod already is stays the same mod (its values are
        rerolled, which this list does not show). Raises `NotApplicableError` for a normal or corrupted item, a class that is no body
        armour, boots, gloves or helmet, and fewer than two influenced mods; `OutOfScopeError` for an influenced item with a fractured
        mod or a candidate whose upgrade the data cannot name (a top-tier mod with no known Elevated version).
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Orb of Dominance works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Dominance")
        item_class = data.base_items[item.base_id].item_class
        if item_class not in DOMINANCE_GATE.value:
            raise NotApplicableError(f"an Orb of Dominance works on body armour, boots, gloves and helmets only, and this item is a {item_class}")
        if item.influences and item.fractured_mods:
            raise OutOfScopeError("an influenced item with a fractured mod does not exist in the game (dominance.influenced_item_is_never_fractured)")
        locked = locked_sides(data, item)
        is_influenced = influence_spawn_test(data, item)
        eligible = [
            entry for entry in item.mods if not on_locked_side(data, entry, locked) and is_influenced(data.mods[entry.mod_id])
        ]
        if len(eligible) < MIN_INFLUENCED_MODS:
            raise NotApplicableError(
                f"an Orb of Dominance needs {MIN_INFLUENCED_MODS} influenced mods on a side that is not locked, and this item has {len(eligible)}"
            )
        tiers = tiers_of(data, item)
        upgraded = {entry.mod_id: self._upgraded(data, item, entry, tiers) for entry in eligible}
        share = Fraction(1, len(eligible) * (len(eligible) - 1))
        results = []
        for removed in eligible:
            for chosen in eligible:
                if chosen is removed:
                    continue
                mods = tuple(
                    upgraded[entry.mod_id] if entry is chosen else entry for entry in item.mods if entry is not removed
                )
                results.append((share, item.changed(data, mods=mods)))
        return Finite(data, item, tuple(results))


@kind(
    "orb-of-dominance",
    order=77,
    planner=False,
    why_not="the compressed state does not tell the influenced mods apart where Dominance reads them, nor tier an Elevated mod (#155)",
)
def _orb_of_dominance(data: GameData, item: Item):
    if item.rarity is not Rarity.NORMAL and item.influences and data.base_items[item.base_id].item_class in DOMINANCE_GATE.value:
        yield OrbOfDominance()


# --- the beast influence recipes -----------------------------------------------------------------------------------


def beast_recipe_resources(influence: Influence, rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value) -> Mapping[str, int]:
    """What one use of the recipe of `influence` consumes by price-file name: its beasts, and the rare beasts as Chaos Orbs."""
    resources: dict[str, int] = {}
    for name, count in BEAST_RECIPES.value[influence.value].items():
        if name == ANY_RARE_CREATURE:
            resources[CHAOS_ORB] = count * rare_creature_price
        else:
            resources[name] = count
    return resources


@dataclass(frozen=True)
class BeastInfluenceRecipe(Action):
    """The beast recipe "Add a Mod to a <influence> Item": one more mod, drawn from the pool of that influence (unverified)."""

    influence: Influence
    rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value

    def __post_init__(self) -> None:
        if not isinstance(self.influence, Influence):
            raise ValueError(f"the influence of a beast influence recipe must be an Influence, not {self.influence!r}")

    def label(self, data: GameData | None = None) -> str:
        return f"Beastcraft Add a Mod to a {WORDS[self.influence]} Item"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return beast_recipe_resources(self.influence, self.rare_creature_price)

    def reads(self, data: GameData) -> Reads:
        # As the orb of the influence reads, except that the item has the influence already and the recipe refuses no Eldritch implicit.
        return Reads(junk=True, families=None, pool_weight=False)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=None, draws=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        own = (BEAST_RECIPES, BEAST_USES_ITEM_LEVEL, BEAST_ADDS_A_MOD_OF_THAT_INFLUENCE, BEAST_REFUSED_ON_CORRUPTED, EXALT_DRAWS_FROM_THAT_INFLUENCE,
               EXALT_RESPECTS_METAMODS, ANY_RARE_CREATURE_PRICE)
        return _claims_of(own, add, pool, outcomes, metamods)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of the recipe on `item`: one more mod of the recipe's influence, drawn as its Exalted Orb would draw it.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, does not have the influence, has no open slot or has
        no legal mod of the influence.
        """
        what = self.label()
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a beast influence recipe works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no beast craft")
        if self.influence not in item.influences:
            raise NotApplicableError(f"{what} needs an item with {WORDS[self.influence]} influence")
        return _draw_one(data, item, self.influence, what)


@kind(
    "beast-influence-recipe",
    order=88,
    planner=False,
    why_not="no compressed-state kernel for the influence crafts yet (#155)",
)
def _beast_influence_recipes(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        for influence in sorted(item.influences):
            yield BeastInfluenceRecipe(influence)
