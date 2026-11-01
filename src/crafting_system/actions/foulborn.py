"""The three Foulborn orbs: Foulborn Orb of Augmentation, Foulborn Regal Orb, Foulborn Exalted Orb (ADR-0043, ticket #279).

Each acts as its plain version (the same item it accepts, the same refusals, the same pool and the same draw: the classes below
subclass the plain orb and change nothing in `outcomes`) with three differences:

* **the cut adds 75 to `D`** (ADR-0040): `cut_of` gives the pool `Cut.of(item, foulborn=True)`, the same formula on a stranded item and on
  a 0-strand one. On a 0-strand item `D = 175`, the case the wiki's list of kept tiers fixes (N = 1 to 13: 1, 1, 2, 2, 3, 3, 4, 5, 5, 6,
  6, 7, 7); that case rests on the wiki alone (`foulborn.zero_strand_cut_matches_eleven_strands`, `approximate`). The cut uses the count the
  item has before the craft, and a second Foulborn orb on an item whose strands the first spent has no test: it applies the same rules
  to the count that is left (`approximate`, ADR-0043);
* **the spend is the orb's own** (`strand_use`, ADR-0041): Foulborn Augmentation 0 to 32 and Foulborn Regal 0 to 48 (claim
  `foulborn.spend_ranges`); the Foulborn Exalted Orb's ceiling follows the mods on the item before the craft, 46, 52, 56, 60, 62, 66 for
  0 to 5 (claim `foulborn.exalted_spend_by_mod_count`, `approximate`). The ticket text lists the Exalted row as 29, 40, 47, 58, 62, the plain
  row times 62/34; the amendment of ADR-0041 dropped that scaling for the emulator's row, and the claim is what the plan reads;
* **the price is the market's.** The orbs are born only on the Genesis Tree, which the planner does not model (claim
  `foulborn.availability`), so each is a currency in the price file under its own name (`FOULBORN_AUGMENTATION`, `FOULBORN_REGAL`,
  `FOULBORN_EXALTED`). An orb with no price is dropped from the offers and the report names it, like any resource without a price
  (`price_offers`).

The three kinds exist only in a plan that considers Memory Strands (`needs_strands`, ADR-0040): `catalog(..., strands=True)`, or an item
that holds strands, lists them. Foulborn Exalted is `opt_in` like the plain Exalted Orb. Nothing else needs to know the three orbs:
the kernel reads their cut pool through `outcomes` like any other draw, and the claims behind the cut and the spend are listed by
`strand_claims`, not `claims`, so an answer that does not consider strands never names them.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import Rule, get_rule

from .catalog import kind
from .cut import Cut
from .exalted import ExaltedOrb
from .magic import AugmentationOrb, RegalOrb
from .strand_use import SpendLaw, StrandUse

__all__ = [
    "FOULBORN_AUGMENTATION",
    "FOULBORN_EXALTED",
    "FOULBORN_REGAL",
    "FoulbornAugmentationOrb",
    "FoulbornExaltedOrb",
    "FoulbornRegalOrb",
]

FOULBORN_AUGMENTATION = "Foulborn Orb of Augmentation"  # the price-file names, as the game and the wiki write them
FOULBORN_REGAL = "Foulborn Regal Orb"
FOULBORN_EXALTED = "Foulborn Exalted Orb"

# The claims of the Foulborn declarations are looked up by id when a declaration is built and are not module constants: `Action.claims`
# lists the `Rule` constants a module holds, and a strand claim belongs to `strand_claims` (see `strand_use.py`).
_CUT_CLAIM_IDS = (
    "foulborn.effect_tier_cull",
    "foulborn.on_stranded_item",
    "foulborn.bonus_is_added_to_the_strand_denominator",
    "foulborn.zero_strand_cut_matches_eleven_strands",
    "foulborn.availability",
)


def _cut_claims() -> tuple[Rule, ...]:
    return tuple(get_rule(claim) for claim in _CUT_CLAIM_IDS)


def _spend_ranges() -> Rule:
    return get_rule("foulborn.spend_ranges")


def _exalted_row() -> Rule:
    return get_rule("foulborn.exalted_spend_by_mod_count")


class _Foulborn:
    """What the three share: the cut of a Foulborn orb, which adds 75 to `D` (the plain orb they extend gives `Cut.of(item)`)."""

    def cut_of(self, data: GameData | None, item: Item) -> Cut | None:
        """The cut of the count the item has before the craft, with the Foulborn bonus: it applies even at 0 strands."""
        return Cut.of(item, foulborn=True)


@dataclass(frozen=True)
class FoulbornAugmentationOrb(_Foulborn, AugmentationOrb):
    """One Foulborn Orb of Augmentation: an Orb of Augmentation whose draw sees the cut with the Foulborn bonus and which spends 0 to 32 strands."""

    def label(self, data: GameData | None = None) -> str:
        return "Foulborn Orb of Augmentation"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.cutting(SpendLaw.uniform(_spend_ranges().value["augmentation"]), *_cut_claims(), _spend_ranges())

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {FOULBORN_AUGMENTATION: 1}


@dataclass(frozen=True)
class FoulbornRegalOrb(_Foulborn, RegalOrb):
    """One Foulborn Regal Orb: a Regal Orb whose draw sees the cut with the Foulborn bonus and which spends 0 to 48 strands."""

    def label(self, data: GameData | None = None) -> str:
        return "Foulborn Regal Orb"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.cutting(SpendLaw.uniform(_spend_ranges().value["regal"]), *_cut_claims(), _spend_ranges())

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {FOULBORN_REGAL: 1}


@dataclass(frozen=True)
class FoulbornExaltedOrb(_Foulborn, ExaltedOrb):
    """One Foulborn Exalted Orb: an Exalted Orb whose draw sees the cut with the Foulborn bonus; its ceiling follows the mods before the craft."""

    def label(self, data: GameData | None = None) -> str:
        return "Foulborn Exalted Orb"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        # claim foulborn.exalted_spend_by_mod_count: 46, 52, 56, 60, 62, 66 for 0 to 5 explicit mods on the item before the craft
        return StrandUse.cutting(SpendLaw.by_mods(*_exalted_row().value), *_cut_claims(), _exalted_row())

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {FOULBORN_EXALTED: 1}


@kind("foulborn-augmentation-orb", order=100, needs_strands=True)
def _foulborn_augmentation_orb(data: GameData, item: Item):
    if item.rarity in (Rarity.NORMAL, Rarity.MAGIC):  # a normal item becomes magic on the way, as for the plain orb's kind
        yield FoulbornAugmentationOrb()


@kind("foulborn-regal-orb", order=101, needs_strands=True)
def _foulborn_regal_orb(data: GameData, item: Item):
    if item.rarity in (Rarity.NORMAL, Rarity.MAGIC):
        yield FoulbornRegalOrb()


@kind("foulborn-exalted-orb", order=102, needs_strands=True, opt_in=True)
def _foulborn_exalted_orb(data: GameData, item: Item):
    yield FoulbornExaltedOrb()  # a normal or magic item becomes rare on the way, so the kind is listed for it too (as for the plain orb)
