"""The Blessed Orb and the catalysts declare what they do with Memory Strands (ticket #287, ADR-0041).

Both neither cut nor spend. On an item with 60 strands their result is not `Spent`: `strands_after` is `{60: 1}` and every
finished item, in the distribution and in a sample, keeps the 60. The declaration rests on `memory_strands.cut_follows_spend_table`
(approximate); it is listed by `strand_claims` and not by `claims`, which would put a strand claim on every answer of B1 to B4.
"""

import random
from fractions import Fraction

from abstraction_pool import RESIST_2
from contract_support import finished
from implicits_support import BELT, EXTENDED
from item_state_support import ITEM_DATA, amulet, roll

from crafting_system.actions import (
    ApplyCatalyst,
    BlessedOrb,
    CUT_FOLLOWS_SPEND_TABLE,
    Spent,
    StrandUse,
    strands_after,
)
from crafting_system.items import CatalystType, ImplicitMod, Item, Rarity

STRENGTH = "StrengthImplicitBelt1"
STRANDS = 60
CLAIM = "memory_strands.cut_follows_spend_table"


def belt_with_strands() -> Item:
    """A Heavy Belt of `EXTENDED` with its ranged implicit at 30, and 60 strands."""
    belt = Item.build(
        EXTENDED,
        base_id=BELT,
        item_level=84,
        rarity=Rarity.RARE,
        implicits=(ImplicitMod(STRENGTH, 0, (30,)),),
    )
    return belt.changed(EXTENDED, memory_strands=STRANDS)


def amulet_with_strands() -> Item:
    """The fixture amulet of the catalyst tests, at item level 84, with 60 strands."""
    return amulet(roll(RESIST_2)).changed(ITEM_DATA, item_level=84, memory_strands=STRANDS)


# --- the result: neither cut nor spend --------------------------------------------------------------


def test_the_blessed_orb_on_an_item_with_strands_is_not_spent_and_every_finished_item_keeps_them():
    result = BlessedOrb().outcomes(EXTENDED, belt_with_strands())
    assert not isinstance(result, Spent)
    assert strands_after(result, STRANDS) == {STRANDS: Fraction(1)}
    assert all(item.memory_strands == STRANDS for _, item in finished(result, EXTENDED))
    rng = random.Random(1)
    assert all(result.sample(rng).memory_strands == STRANDS for _ in range(200))


def test_the_catalyst_on_an_item_with_strands_is_not_spent_and_every_finished_item_keeps_them():
    result = ApplyCatalyst(CatalystType.INTRINSIC).outcomes(ITEM_DATA, amulet_with_strands())
    assert not isinstance(result, Spent)
    assert strands_after(result, STRANDS) == {STRANDS: Fraction(1)}
    assert all(item.memory_strands == STRANDS for _, item in finished(result, ITEM_DATA))
    rng = random.Random(1)
    assert all(result.sample(rng).memory_strands == STRANDS for _ in range(200))


# --- the declaration: no cut, no spend, one claim ---------------------------------------------------


def test_the_blessed_orb_declares_no_cut_and_no_spend_on_the_claim_of_the_spend_table():
    action = BlessedOrb()
    use = action.strand_use(EXTENDED)
    assert use == StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)
    assert not use.cuts and use.spend is None  # the spend is absent
    assert action.strand_claims(EXTENDED) == frozenset({CLAIM})
    assert CLAIM not in action.claims(EXTENDED)


def test_the_catalyst_declares_no_cut_and_no_spend_on_the_claim_of_the_spend_table():
    action = ApplyCatalyst(CatalystType.INTRINSIC)
    use = action.strand_use(ITEM_DATA)
    assert use == StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)
    assert not use.cuts and use.spend is None  # the spend is absent
    assert action.strand_claims(ITEM_DATA) == frozenset({CLAIM})
    assert CLAIM not in action.claims(ITEM_DATA)
