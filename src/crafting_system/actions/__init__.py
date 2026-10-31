"""Primitives, each with its exact outcome distribution and sampling on a concrete item. May import only: data, rules, items.

Three random actions so far, `ChaosOrb()`, `HarvestReforge("lightning")` and `ApplyEssence("Shrieking
Essence of Spite")` (an essence is named as in the game data or by its record id). Each has one method,
`outcomes(data, item) -> Outcomes`, and `Outcomes` is the whole result.

The crafting bench has two deterministic ones, `BenchCraft(mod_id)` (one per bench option that adds a
crafted mod, listed by `bench_crafts(data)`) and `RemoveCraftedMods()`. Each has `outcomes(data,
item) -> BenchOutcomes`, with the same `chance_all`, `distribution` and `sample` and one outcome of
probability 1, and `cost(data)`, the price as `CurrencyCost(currency name, count)`. A bench craft
is refused (`NotApplicableError`) on a corrupted item, for an item class the option is not offered for,
below the mod's required item level, with a family already on the item, on a full side, and on an
item that already holds a crafted mod; a normal item and an item holding the multimod are
`OutOfScopeError`. Remove Crafted Mods removes every crafted mod, metamods included.

A Chaotic resonator with fossils is `ApplyFossils(("Dense Fossil", "Shuddering Fossil"))`: one
action per set of one to four different fossils, the resonator size following from their number.
Its `outcomes(data, item)` is a `FossilOutcomes`, a mixture of `Outcomes` (a Tangled Fossil draws one
of 420 tag pairs and a Glyphic Fossil one forced mod) with the same `chance_all`, `distribution` and
`sample`; `fossil_actions(data, item)` lists every set the item could take. See `fossil.py` for its
refusals.

Refusals, raised by `outcomes` in this order (a message names the reason):

* `NotApplicableError`: the game refuses and nothing would be consumed: the item is not rare (an
  essence: it is magic, or rare and the essence is one of the normal-only levels 1 to 4); it is
  corrupted; for the Harvest reforge, the pool holds no mod with the tag that the item has a free
  family and a free slot for; for an essence, its item class takes no essence, or its forced mod
  shares a family with a fractured mod.
* `OutOfScopeError`: the item is in a state no admitted rule covers yet: an influence, a crafted
  metamod (an ordinary crafted mod is not: a reroll removes it), a jewel base (the 8:3:1 ratio is
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

from .bench import BenchCraft, BenchOutcomes, CurrencyCost, RemoveCraftedMods, bench_crafts
from .chaos import ChaosOrb
from .draw import Outcome
from .errors import ActionError, NotApplicableError, OutOfScopeError
from .essence import ApplyEssence
from .fossil import ApplyFossils, FossilOutcomes, Fractured, fossil_actions, usable_fossils
from .harvest import HarvestReforge
from .outcomes import Outcomes
from .pool import PoolFamily, PoolMod, build_pool

__all__ = [
    "ActionError",
    "ApplyEssence",
    "ApplyFossils",
    "BenchCraft",
    "BenchOutcomes",
    "ChaosOrb",
    "CurrencyCost",
    "FossilOutcomes",
    "Fractured",
    "HarvestReforge",
    "NotApplicableError",
    "Outcome",
    "Outcomes",
    "OutOfScopeError",
    "PoolFamily",
    "PoolMod",
    "RemoveCraftedMods",
    "bench_crafts",
    "build_pool",
    "fossil_actions",
    "usable_fossils",
]
