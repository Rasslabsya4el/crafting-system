"""Primitives, each with its exact outcome distribution and sampling on a concrete item. May import only: data, rules, items.

**One contract (ticket #108).** Every action subclasses `Action` (`contract.py`) and answers five
questions: `label(data)` (the stable name routes and the CLI use), `outcomes(data, item)` (the exact
result), `resources(data)` (what one use consumes, by price-file name, read from claims), `reads(data)`
(what of the item besides its fractured mods the result depends on: `Reads`) and `adds(data, item)`
(what it puts on the item: `Adds`). The catalog (`catalog.py`) lists the actions of every registered
kind for an item; a module registers its kinds with the `kind` decorator, so a new method is one file
and nothing outside `actions` imports a concrete action: `abstraction`, `cli` and `simulator` use the
contract and the catalog only. See ADR-0024 (extending to new methods and patches).

Three random actions so far, `ChaosOrb()`, `HarvestReforge("lightning")` and `ApplyEssence("Shrieking
Essence of Spite")` (an essence is named as in the game data or by its record id). Each has one method,
`outcomes(data, item) -> Outcomes`, and `Outcomes` is the whole result.

The crafting bench has two deterministic ones, `BenchCraft(mod_id)` (one per bench option that adds a
crafted mod, listed by `bench_crafts(data)`) and `RemoveCraftedMods()`. Each has `outcomes(data,
item) -> BenchOutcomes`, with the same `chance_all`, `distribution` and `sample` and one outcome of
probability 1, and `cost(data)`, the price as `CurrencyCost(currency name, count)`. A bench craft
is refused (`NotApplicableError`) on a corrupted item, for an item class the option is not offered for,
below the mod's required item level, with a family already on the item, on a full side, and on an
item that already holds as many crafted mods as it may (one, or three with the multimod); a normal item
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

The five metamods (`metamods.py`, ticket #68): `Prefixes` / `Suffixes Cannot Be Changed` keep the mods of
the locked side through a reroll (Chaos, Alteration, Harvest), a Scouring and an Annulment, and the open slots
still fill; `Cannot roll Attack` / `Caster Modifiers` keep the mods with that tag out of every draw on an item that
still holds the metamod (a reroll that removes it is not filtered), out of an Annulment's candidates, and, on a
Harvest reforge, out of the first (guaranteed) mod only; essences and resonators refuse the four; the multimod
lifts the crafted-mod limit to three. No action raises `OutOfScopeError` for a metamod.

Refusals, raised by `outcomes` in this order (a message names the reason):

* `NotApplicableError`: the game refuses and nothing would be consumed: the item is not rare (an
  essence: it is magic, or rare and the essence is one of the normal-only levels 1 to 4); it is
  corrupted; for the Harvest reforge, the pool holds no mod with the tag that the item has a free
  family and a free slot for; for an essence, its item class takes no essence, or its forced mod
  shares a family with a fractured mod, or the item holds a lock or an Attack/Caster metamod (essence and resonator).
* `OutOfScopeError`: the item is in a state no admitted rule covers yet: an influenced item of a class with no admitted influence class key, a magic
  item whose Orb of Alteration keeps an Attack or Caster metamod, a jewel base (the 8:3:1 ratio is
  admitted for regular items only), a pool mod with other than one family; for an essence also
  Essence of Desolation (not a B1 action) and fractured mods that fill the side of the forced mod.
  A planner treats the action as unavailable.
* `HarvestReforge("fire")` raises `ValueError` at construction: only admitted tags exist; an
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

The pool a draw uses is `build_pool(data, item)`: the mods that could be drawn next, grouped by
family, with exact `Fraction` weights.
"""

from .add import add_one_mod, draw_onto
from .alchemy import AlchemyOrb
from .annul import AnnulmentOrb
from .bench import BenchCraft, BenchOutcomes, CurrencyCost, RemoveCraftedMods, bench_crafts, without_ranges
from .catalog import Kind, catalog, kind, kinds, register, registered
from .chaos import ChaosOrb
from .contract import Action, ActionOutcomes, Adds, Fixed, Reads
from .draw import Outcome
from .errors import ActionError, NotApplicableError, OutOfScopeError
from .essence import ApplyEssence
from .exalted import ExaltedOrb
from .finite import Finite
from .fossil import ApplyFossils, fossil_actions, usable_fossils
from .fracture import FractureOutcomes, FracturingOrb
from .harvest import HarvestReforge
from .magic import AlterationOrb, AugmentationOrb, RegalOrb, TransmutationOrb
from .mixture import FossilOutcomes, Fractured, Mixture
from .outcomes import Outcomes
from .pool import PoolFamily, PoolMod, build_pool
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
    "AnnulmentOrb",
    "ApplyEssence",
    "ApplyFossils",
    "AugmentationOrb",
    "BenchCraft",
    "BenchOutcomes",
    "ChaosOrb",
    "CurrencyCost",
    "ExaltedOrb",
    "Finite",
    "Fixed",
    "FractureOutcomes",
    "FossilOutcomes",
    "Fractured",
    "FracturingOrb",
    "HarvestReforge",
    "Kind",
    "Mixture",
    "NotApplicableError",
    "Outcome",
    "Outcomes",
    "OutOfScopeError",
    "PoolFamily",
    "PoolMod",
    "Reads",
    "RegalOrb",
    "RemoveCraftedMods",
    "ScouringOrb",
    "ScourOutcomes",
    "TransmutationOrb",
    "add_one_mod",
    "bench_crafts",
    "build_pool",
    "catalog",
    "default_actions",
    "draw_onto",
    "fossil_actions",
    "kind",
    "kinds",
    "register",
    "registered",
    "usable_fossils",
    "without_ranges",
]
