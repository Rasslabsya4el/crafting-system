"""Errors of the item model.

Every failure the layer raises on purpose is an `ItemError`, which is a `ValueError`. The message
names the item's base, the offending mod id and the reason in plain English.
"""


class ItemError(ValueError):
    """Base of every error the item model raises on purpose; also raised for structural nonsense."""


class UnknownBaseError(ItemError):
    """The base id of the item is not in the game data."""


class UnknownModError(ItemError):
    """A mod id of the item is not in the game data."""


class ModSlotError(ItemError):
    """A mod cannot sit on this item: it is not a prefix or suffix, its domain does not fit the base,
    or the crafted flag disagrees with the mod's domain."""


class ValueRangeError(ItemError):
    """The rolled values of a mod do not match its stats: wrong count, or a value outside its range."""


class CapacityError(ItemError):
    """The item holds more prefixes or suffixes than its rarity and base allow."""


class FamilyConflictError(ItemError):
    """Two mods of the item share a family, so they exclude each other."""
