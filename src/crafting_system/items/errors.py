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


class ImplicitError(ItemError):
    """An implicit of the item is neither an implicit of its base nor an Eldritch one, has the wrong grade,
    or the item holds two Eldritch implicits of one side."""


class QualityError(ItemError):
    """The quality is malformed (a catalyst type or a percent outside its range) or sits on a base that takes none: a catalyst
    quality on anything but a ring, an amulet or a belt, a plain quality on anything but a weapon or armour."""


class SocketError(ItemError):
    """The sockets of the item are malformed (colours, link groups that do not add up to the sockets) or do not fit its base:
    more sockets than the class maximum, or sockets on an item class that has none."""


class VeilOfferError(ItemError):
    """The unveil offer does not fit the item: no single veiled placeholder, too many or repeated mods, or
    a mod of the wrong domain, side or family."""


class EnchantmentError(ItemError):
    """The enchantment of the item is not an enchantment mod, was removed from the pool, or does not fit the
    base (a weapon enchant on body armour, or a base that takes none)."""


class MemoryStrandsError(ItemError):
    """The Memory Strands count of the item is not a whole number from 0 to 100, or a pasted item text holds
    the `Memory Strands:` line badly (twice, or with something other than a whole number)."""


class ImprintError(ItemError):
    """The imprints of the item are not a tuple of items that hold no imprint themselves (ADR-0060)."""


class TierError(ItemError):
    """A mod has no tier on a base because it cannot spawn there: its spawn weight is 0 for the base's tags."""
