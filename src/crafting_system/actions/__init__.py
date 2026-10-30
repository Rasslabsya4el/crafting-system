"""Primitives, each with its exact outcome distribution and sampling on a concrete item. May import only: data, rules, items.

Two actions so far, `ChaosOrb()` and `HarvestReforge("lightning")`. Each has one method,
`outcomes(data, item) -> Outcomes`, and `Outcomes` is the whole result.

Refusals, raised by `outcomes` in this order (a message names the reason):

* `NotApplicableError`: the game refuses and nothing would be consumed: the item is not rare; it is
  corrupted; for the Harvest reforge, the pool holds no mod with the tag that the item has a free
  family and a free slot for.
* `OutOfScopeError`: the item is in a state no admitted rule covers yet: an influence, a crafted mod
  or metamod, a jewel base (the 8:3:1 ratio is admitted for regular items only), or a pool mod
  with other than one family. A planner treats the action as unavailable.
* `HarvestReforge("fire")` raises `ValueError` at construction: only admitted tags exist.

What an `Outcomes` gives, on the item before any mod is drawn (`retained`: the original item with
only its fractured mods, which stay and count inside the total of 4, 5 or 6 mods):

* `chance_all(mod_ids)`: the exact `Fraction` chance that the finished item holds all of these mods,
  kept or newly drawn, jointly; 0 when two of them share a family; `ValueError` for an unknown id.
* `distribution(label)`: the exact distribution of the new mods seen through `label`, a pure
  function from a `Mod` to a hashable. An `Outcome` is a frozenset of `(label, how many new mods got
  it)` pairs; labels with a count of zero are left out and the kept mods are not in it. The
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

from .chaos import ChaosOrb
from .draw import Outcome
from .errors import ActionError, NotApplicableError, OutOfScopeError
from .harvest import HarvestReforge
from .outcomes import Outcomes
from .pool import PoolFamily, PoolMod, build_pool

__all__ = [
    "ActionError",
    "ChaosOrb",
    "HarvestReforge",
    "NotApplicableError",
    "Outcome",
    "Outcomes",
    "OutOfScopeError",
    "PoolFamily",
    "PoolMod",
    "build_pool",
]
