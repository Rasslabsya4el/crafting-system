"""The default prices of Thaumaturgic Dust and Gold (ADR-0035, ticket #216), and of a use of the Locus of Corruption (ADR-0038, ticket #262).

Neither Dust nor Gold is on poe.ninja or the trade site, so the price file carries a dated default for each, marked with
the source "default"; the owner overrides either in the hand-written price_overrides.toml. Every price is in
Chaos Orbs per ONE unit.

A use of the Locus of Corruption has no market at all: the temple is not bought per use. Its price is a **standing default**,
0 Chaos Orbs, that holds whenever neither the price file nor the overrides name it (`standing_defaults`), so a price file fetched
before the entry existed prices it too and the Locus stays on by default. The owner sets another price in price_overrides.toml
(an override is above zero). A price file never holds it: the file takes prices above zero only.
"""

from .price_file import PriceEntry

DUST = "Thaumaturgic Dust"
GOLD = "Gold"
LOCUS_USE = "Locus of Corruption (use)"  # the claim `locus.cost` names the same price-file name
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


def standing_defaults() -> dict[str, PriceEntry]:
    """The prices that hold when neither the price file nor the overrides name them, keyed by price name: a use of the Locus, 0 Chaos Orbs."""
    return {
        LOCUS_USE: PriceEntry(
            0.0,
            DEFAULT_SOURCE,
            note="ADR-0038 default: a use of the Locus of Corruption costs 0 Chaos Orbs (the temple is not bought per use); set another price in price_overrides.toml",
        ),
    }
