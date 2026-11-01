"""The default prices of Thaumaturgic Dust and Gold (ADR-0035, ticket #216).

Neither is on poe.ninja or the trade site, so the price file carries a dated default for each, marked with
the source "default"; the owner overrides either in the hand-written price_overrides.toml. Every price is in
Chaos Orbs per ONE unit.
"""

from .price_file import PriceEntry

DUST = "Thaumaturgic Dust"
GOLD = "Gold"
DEFAULT_SOURCE = "default"
DUST_PER_CHAOS = 150_000
CHAOS_PER_MILLION_GOLD = 500


def default_prices() -> dict[str, PriceEntry]:
    """The two default entries, keyed by price name."""
    return {
        DUST: PriceEntry(
            1 / DUST_PER_CHAOS, DEFAULT_SOURCE, note="ADR-0035 default: 150,000 Thaumaturgic Dust per Chaos Orb"
        ),
        GOLD: PriceEntry(
            CHAOS_PER_MILLION_GOLD / 1_000_000, DEFAULT_SOURCE, note="ADR-0035 default: 500 Chaos Orbs per million Gold"
        ),
    }
