"""Primitives, each with its exact outcome distribution and sampling on a concrete item. May import only: data, rules, items.

**One contract (ticket #108).** Every action subclasses `Action` (`contract.py`) and answers five
questions: `label(data)` (the stable name routes and the CLI use), `outcomes(data, item)` (the exact
result), `resources(data)` (what one use consumes, by price-file name, read from claims), `reads(data)`
(what of the item besides its fractured mods the result depends on: `Reads`) and `adds(data, item)`
(what it puts on the item: `Adds`). The catalog (`catalog.py`) lists the actions of every registered
kind for an item; a module registers its kinds with the `kind` decorator, so a new method is one file
and nothing outside `actions` imports a concrete action: `abstraction`, `cli` and `simulator` use the
contract and the catalog only. See ADR-0024 (extending to new methods and patches).

Two-item actions and rule axes (ticket #210, B3): two more questions, empty by default. `inputs(data, item)` is a tuple of
`Need(start, want)`, the other items one use consumes (ADR-0022); `rule_axes(data)` is a tuple of `Axis(name, readings, plan)`,
the rules the action reads that the sources leave open (ADR-0033). An action with axes takes a `Reading` in `outcomes(data,
item, reading=None)`; `outcomes_under(data, item, reading)` is the call that works for every action, and `model_readings(data,
actions)` lists the readings of a model, the plan's first. `Reads.input_mods` says that the result depends on the mods of the
inputs. A new kind with inputs is correct by default and needs no edit outside `actions`.

Random rerolls: `ChaosOrb()`, `HarvestReforge("lightning")` (sixteen tagged crafts, one per tag of the claim
`harvest_reforge.tagged_rare_reforge_exists`), `HarvestReforgeInfluence()` (an influenced item, one influence mod
guaranteed), `HarvestReforgeLikelihood(more=True)` (the mods the item holds are 10 times more, or with `more=False`
10 times less, likely to return; the item keeps at least as many mods) and `ApplyEssence("Shrieking Essence of
Spite")` (an essence is named as in the game data or by its record id). Each has one method,
`outcomes(data, item) -> Outcomes`, and `Outcomes` is the whole result.

The crafting bench has two deterministic ones, `BenchCraft(mod_id)` (one per bench option that adds a
crafted mod, listed by `bench_crafts(data)`) and `RemoveCraftedMods()`. Each has `outcomes(data,
item) -> BenchOutcomes`, with the same `chance_all`, `distribution` and `sample` and one outcome of
probability 1, and `cost(data)`, the price as `CurrencyCost(currency name, count)`. A bench craft
is refused (`NotApplicableError`) on a corrupted item, for an item class the option is not offered for,
below the mod's required item level, with a family already on the item, on a full side, and on an
item that already holds as many crafted mods as it may (one, two with the extra crafted slot enchant, three with the multimod); a normal item
is `OutOfScopeError`. Remove Crafted Mods removes every crafted mod that is not fractured, metamods included.

A Chaotic resonator with fossils is `ApplyFossils(("Dense Fossil", "Shuddering Fossil"))`: one
action per set of one to four different fossils, the resonator size following from their number.
Its `outcomes(data, item)` is a `FossilOutcomes`, a mixture of `Outcomes` (a Tangled Fossil draws one
of 420 tag pairs and a Glyphic Fossil one forced mod) with the same `chance_all`, `distribution` and
`sample`; `fossil_actions(data, item)` lists every set the item could take. See `fossil.py` for its
refusals.

The orbs of the early crafting steps are `TransmutationOrb()` (normal to magic with 1 or 2 mods, 1/2
each), `AlterationOrb()` (rerolls a magic item the same way), `AugmentationOrb()` (adds one mod to a
magic item with a free slot), `RegalOrb()` (magic to rare, adds one mod) and `AlchemyOrb()` (normal to
rare with 4, 5 or 6 mods, 8:3:1). Each returns an `Outcomes` like the Chaos Orb. They draw through
`add.py`, the shared add: `add_one_mod(data, item, what)` (one more mod on an item that keeps all
it has, the Exalted Orb's too) and `draw_onto(data, retained, totals)`; a present family is out of the
pool, a full side closes, and an add of one mod with no legal mod is refused (`NotApplicableError`)
and consumes nothing. `ScouringOrb()` has one result of probability 1, a `ScourOutcomes` with the
same `chance_all`, `distribution` and `sample`: it removes every mod but the fractured ones and those on a
side that a lock metamod protects, and the item is normal with none left, magic with one and rare with two or
more; it keeps its influences.

The orbs of the rare item are `ExaltedOrb()` (one more mod through the same shared add, on a rare item with an
open slot), `AnnulmentOrb()` (removes one mod that is not fractured, uniformly, D5; the rarity stays) and
`FracturingOrb()` (a rare item of 4 or more mods that is not influenced, fractured or corrupted: fractures one
mod, uniformly, D6; a crafted mod or a metamod is a candidate, and a fractured one stays). The Exalted and Annulment orbs return an `Outcomes` and a `Finite`; the Fracturing Orb a `FractureOutcomes`,
a `Finite` whose `fractures` is True. None is a planner kind yet. An influenced item draws from the pool of its
base tags plus the influence tags (`item_tags` in `pool.py`), so the mods of an influence join every pool.

The Divine Orb (`DivineOrb()`, `divine.py`, ticket #71) rerolls the values of the mods an item holds, in place, and nothing
else: every explicit mod that is not fractured and not on a side a lock protects gets a fresh value per stat, uniform over the
integers of its range, and the tiers stay. Its result is a `DivineOutcomes` whose only component is a `Rerolled` part
(`contract.py`) with the `(mod id, fractured, crafted)` keys of the changed mods; it reads `Reads.rerolls_values` and declares
`Adds.needs_roll_limit`, so a planner offers it only for a target with a roll limit. It refuses a normal or a corrupted item and
an item with no mod to change. A Sanctified Fossil in a resonator sets `Outcomes.rolls_lucky` on every part of its result: each value
of the mods it puts on the item is rolled twice and the better one kept (`rolls.py`).

The five metamods (`metamods.py`, ticket #68): `Prefixes` / `Suffixes Cannot Be Changed` keep the mods of
the locked side through a reroll (Chaos, Alteration, Harvest), a Scouring and an Annulment, and the open slots
still fill; `Cannot roll Attack` / `Caster Modifiers` keep the mods with that tag out of every draw on an item that
still holds the metamod (a reroll that removes it is not filtered), out of an Annulment's candidates, and, on a
Harvest reforge, out of the first (guaranteed) mod only; essences and resonators refuse the four; the multimod
lifts the crafted-mod limit to three, and the enchantment "Can have 1 additional Crafted Modifier" to two (the larger of
the two with both, ADR-0053; `crafted_limit_of`). No action raises `OutOfScopeError` for a metamod.

The beast crafts (`beasts.py`, ticket #147): `TalismanFracture(1 or 2)` fractures one or two mods of a rare Talisman,
uniformly, as the Fracturing Orb does (4 or 6 mods needed), and `AspectBeast(aspect, level)` adds the suffix that
grants an aspect skill at level 20 or 30, and is offered only when a target names it (`Adds.wanted_only`).
`beast_mods.py` holds `WildBristleMatron()` (adds one of the five metamods, uniformly among those the item allows) and
`BeastSideSwap(Side.PREFIX or Side.SUFFIX, beast_level=83)` (Farric Wolf and Lynx: draws a mod on one side, capped by the
level of the beast and not of the item, then removes one mod of the other side uniformly). A beast craft consumes beasts priced by name and rare beasts of any kind at a setting (`rare_creature_price`, 1 chaos).
None is a planner kind yet.

The Awakener's Orb (`awakener.py`, ticket #213, ADR-0032) is the first real two-input action: `AwakenersOrb(base, level, donor
influence, donor mod)` has one donor `Need` (a rare item of the other influence that holds the influenced mod to carry over) and
one rule axis, the group conflict (`receiver` is the plan, `donor` the other reading). It keeps one influenced mod of the receiver
and the donor's, picks the pair uniformly among the valid ones, and rerolls the rest as a Chaos Orb does, the kept mods counting
inside the total. Its kind is not a planner kind until the solver prices donors (#211, #212).

The influence crafts (`influence.py`, ticket #154, ADR-0030): `InfluencedExaltedOrb(Influence.SHAPER)` and its five siblings add the influence and one mod of
that influence (an `Outcomes` over the pool `influence_pool(data, item, influence)`; refused on an influenced, fractured or Eldritch-implicit item, below item level
68, and when no mod is legal); `OrbOfDominance()` removes one influenced mod and upgrades another (a `Finite`, each ordered pair of the n influenced mods on
unlocked sides 1/(n(n-1)); a top-tier mod becomes its Elevated version from `data/elevated.json`); `BeastInfluenceRecipe(Influence.SHAPER)` borrows the pool of the
influence's orb for an item that has it (unverified, approximate). None is a planner kind yet (#155).

Refusals, raised by `outcomes` in this order (a message names the reason):

* `NotApplicableError`: the game refuses and nothing would be consumed: the item is not rare (an
  essence: it is magic, or rare and the essence is one of the normal-only levels 1 to 4); it is
  corrupted; for the Harvest reforge, the pool holds no mod with the tag that the item has a free
  family and a free slot for; for an essence, its item class takes no essence, or its forced mod
  shares a family with a fractured mod, or the item holds a lock or an Attack/Caster metamod (essence and resonator).
* `OutOfScopeError`: the item is in a state no admitted rule covers yet: an influenced item of a class with no admitted influence class key, a magic
  item whose Orb of Alteration keeps an Attack or Caster metamod, a cluster jewel (its pool depends on its
  enchantments), a jewel for the actions that are not modelled on one (Harvest crafts; the ordinary orbs, fossils and the
  Fracturing Orb work on jewels, `jewel.ordinary_orbs_work_on_jewels`), a base that exists as a unique only, a pool mod with other than one family; for an essence also
  Essence of Desolation (not a B1 action) and fractured mods that fill the side of the forced mod.
  A planner treats the action as unavailable.
* `HarvestReforge("nothing")` raises `ValueError` at construction: only the admitted crafts exist; an
  `ApplyEssence` name that is no essence of the data raises it from `outcomes`.

What an `Outcomes` gives, on the item before any mod is drawn (`retained`: a rare item with only the
fractured mods of the original, which stay and count inside the total of 4, 5 or 6 mods, and, for an
essence, its forced mod, which is on the item above the item level and counts inside the total too;
a low essence (levels 1 to 4) also caps the required level of the drawn mods):

* `chance_all(mod_ids)`: the exact `Fraction` chance that the finished item holds all of these mods,
  kept or newly drawn, jointly; 0 when two of them share a family; `ValueError` for an unknown id.
* `distribution(label)`: the exact distribution of the new mods seen through `label`, a pure
  function from a `Mod` to a hashable. An `Outcome` is a frozenset of `(label, how many new mods got
  it)` pairs; labels with a count of zero are left out and the kept mods (fractured, forced) are not in it. The
  probabilities are `Fraction`s that sum to exactly 1. This is the input of the compressed state.
* `sample(rng)`: one finished item from a seeded `random.Random`: the same process, with a value
  rolled for every stat and the tier of every drawn mod. Values exist only here; no exact result
  depends on them.

Exactness and cost: nothing is rounded. Families the label cannot tell apart (same side, same
weight per label) are counted, not identified, so the work grows with the number of distinct
(side, weight, label) classes in the pool, not with the number of families. A real amulet pool
(about 40 families) with a coarse label takes about 0.3 to 3 s; a pool of 40 families that all
have different weights took about 70 s, and a label that gives every mod its own value is worse.
The fractions are exact and can be thousands of bits long: `str()` of one can hit Python's
4300-digit limit, so convert with `float()` or `Fraction.limit_denominator` to display it.

The Eldritch currency (`eldritch.py`, ticket #151, ADR-0025): `EldritchImplicitCurrency(side, grade)` (an Ember or an Ichor of grade 1 to
4: an implicit drawn by the spawn weight of the item class, replacing every implicit but the other side's), `EldritchChaosOrb()`,
`EldritchExaltedOrb()` and `EldritchAnnulmentOrb()` (they act on the dominant side, derived from the two grades: `item_dominant_side`) and
`OrbOfConflict()` (raises one implicit by a grade and lowers the other, odds `conflict_raise_chance(difference)`). They work on a body
armour, boots, gloves or helmet that is not corrupted and not influenced, and none is a planner kind yet.

The corrupted implicit pool of a base at an item level (`corrupted_implicit_pool(data, base_id, item_level)`, `corrupted_pool.py`,
ADR-0037) is what a Vaal Orb, a Bloodstained resonator and the Locus of Corruption draw their implicit from: the corrupted mods of the
base's domain with a positive weight on its first matching spawn tag and a required level of at most the item level. Cluster and
Timeless jewels raise `OutOfScopeError`, a class with no pool `NotApplicableError`.

The pool a draw uses is `build_pool(data, item)`: the mods that could be drawn next, grouped by
family, with exact `Fraction` weights.
"""

from .add import add_one_mod, draw_onto
from .alchemy import AlchemyOrb
from .annul import AnnulmentOrb
from .awakener import AwakenersOrb
from .beast_mods import BeastSideSwap, WildBristleMatron
from .beasts import AspectBeast, TalismanFracture, TalismanFractureOutcomes, recipe_resources
from .bench import BenchCraft, BenchOutcomes, CurrencyCost, RemoveCraftedMods, bench_crafts, without_ranges
from .catalog import Kind, catalog, kind, kinds, register, registered
from .chaos import ChaosOrb
from .contract import Action, ActionOutcomes, Adds, Axis, Fixed, Need, Reading, Reads, Rerolled, model_readings
from .corrupted_pool import (
    CORRUPTING_KINDS,
    DEFAULT_CORRUPTING_KINDS,
    CorruptedImplicit,
    CorruptedImplicitPool,
    corrupted_implicit_pool,
)
from .divine import DivineOrb, DivineOutcomes
from .draw import Outcome, guaranteed_candidates
from .eldritch import (
    EldritchAnnulmentOrb,
    EldritchChaosOrb,
    EldritchExaltedOrb,
    EldritchImplicitCurrency,
    OrbOfConflict,
    conflict_raise_chance,
    implicit_pool,
    item_dominant_side,
)
from .errors import ActionError, NotApplicableError, OutOfScopeError
from .essence import ApplyEssence
from .exalted import ExaltedOrb
from .finite import Finite
from .fossil import ApplyFossils, fossil_actions, usable_fossils
from .fracture import FractureOutcomes, FracturingOrb
from .harvest import HarvestReforge
from .harvest_augment import HarvestAddRemove, HarvestDamageSwap, HarvestResistanceSwap
from .harvest_influence import HarvestReforgeInfluence
from .harvest_likelihood import HarvestReforgeLikelihood
from .influence import BeastInfluenceRecipe, InfluencedExaltedOrb, OrbOfDominance, beast_recipe_resources, influence_pool
from .magic import AlterationOrb, AugmentationOrb, RegalOrb, TransmutationOrb
from .metamods import BLOCKED_TAG, BLOCKING, allowed_by_tags, blocked_tags, crafted_limit_of, grants_extra_crafted_slot
from .mixture import FossilOutcomes, Fractured, Mixture
from .outcomes import Outcomes
from .pool import PoolFamily, PoolMod, build_pool, drawable_mod_ids, partners, tiers_of
from .scour import ScouringOrb, ScourOutcomes

def default_actions() -> tuple[Action, ...]:
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return (ChaosOrb(), HarvestReforge("lightning"))


__all__ = [
    "Action",
    "ActionError",
    "ActionOutcomes",
    "Adds",
    "AlchemyOrb",
    "AlterationOrb",
    "AspectBeast",
    "Axis",
    "AnnulmentOrb",
    "ApplyEssence",
    "ApplyFossils",
    "AugmentationOrb",
    "AwakenersOrb",
    "BLOCKED_TAG",
    "BLOCKING",
    "BeastInfluenceRecipe",
    "BeastSideSwap",
    "BenchCraft",
    "BenchOutcomes",
    "CORRUPTING_KINDS",
    "ChaosOrb",
    "CorruptedImplicit",
    "CorruptedImplicitPool",
    "CurrencyCost",
    "DEFAULT_CORRUPTING_KINDS",
    "DivineOrb",
    "DivineOutcomes",
    "EldritchAnnulmentOrb",
    "EldritchChaosOrb",
    "EldritchExaltedOrb",
    "EldritchImplicitCurrency",
    "ExaltedOrb",
    "Finite",
    "Fixed",
    "Rerolled",
    "FractureOutcomes",
    "FossilOutcomes",
    "Fractured",
    "FracturingOrb",
    "HarvestAddRemove",
    "HarvestDamageSwap",
    "HarvestReforge",
    "HarvestReforgeInfluence",
    "HarvestReforgeLikelihood",
    "HarvestResistanceSwap",
    "InfluencedExaltedOrb",
    "Kind",
    "Mixture",
    "Need",
    "NotApplicableError",
    "OrbOfDominance",
    "Outcome",
    "Outcomes",
    "OrbOfConflict",
    "OutOfScopeError",
    "PoolFamily",
    "PoolMod",
    "partners",
    "Reading",
    "Reads",
    "RegalOrb",
    "RemoveCraftedMods",
    "ScouringOrb",
    "ScourOutcomes",
    "TalismanFracture",
    "TalismanFractureOutcomes",
    "TransmutationOrb",
    "WildBristleMatron",
    "add_one_mod",
    "allowed_by_tags",
    "beast_recipe_resources",
    "bench_crafts",
    "blocked_tags",
    "build_pool",
    "catalog",
    "conflict_raise_chance",
    "corrupted_implicit_pool",
    "crafted_limit_of",
    "default_actions",
    "draw_onto",
    "drawable_mod_ids",
    "fossil_actions",
    "grants_extra_crafted_slot",
    "guaranteed_candidates",
    "implicit_pool",
    "influence_pool",
    "item_dominant_side",
    "kind",
    "kinds",
    "model_readings",
    "recipe_resources",
    "register",
    "registered",
    "tiers_of",
    "usable_fossils",
    "without_ranges",
]
