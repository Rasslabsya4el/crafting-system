"""Errors of the actions.

Every refusal an action raises on purpose is an `ActionError`, which is a `ValueError`. The message
names the reason in plain English. The two subclasses tell a caller what to do about it: a
`NotApplicableError` is the game refusing (nothing would be consumed, the planner must not offer
the action here), an `OutOfScopeError` is a state the admitted rules do not cover yet (the planner
must treat the action as unavailable, not as refused by the game).

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
"""

__all__ = [
    "ActionError",
    "NotApplicableError",
    "OutOfScopeError",
]


class ActionError(ValueError):
    """Base of every error an action raises on purpose."""


class NotApplicableError(ActionError):
    """The game refuses this action on this item; nothing is consumed."""


class OutOfScopeError(ActionError):
    """The item is in a state that no admitted rule covers yet, so no outcome is given."""
