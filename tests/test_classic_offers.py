"""The classic offers (`cli_support.CLASSIC_KINDS`): what a target with no `actions:` was offered before #886 turned every beta method on.

The real routes' CI tests plan with them, so a kind added to the catalog, or a classic kind renamed, must fail here, not move those tests
silently: every planner kind is either classic or one #886 or #973 turned on (or a deferred kind, opt-in still).
"""

import pytest
from cli_support import CLASSIC_CORRUPTING_KINDS, CLASSIC_KINDS, classic_offers

from crafting_system.actions import kinds
from crafting_system.planner import _offers
from crafting_system.targets import corrupted

TURNED_ON_BY_886 = {
    "harvest-add-remove", "harvest-resistance-swap", "harvest-damage-swap", "corrupted-essence", "fossil-set", "exalted-orb",
    "veiled-chaos-orb", "veiled-exalted-orb", "unveil", "pick", "annulment-orb", "fracturing-orb", "talisman-fracture", "aspect-beast",
    "beast-side-swap", "wild-bristle-matron", "imprint", "restore",
}
TURNED_ON_LATER = {"influenced-exalted-orb", "catalyst", "orb-of-dominance", "alchemy-orb", "scouring-orb", "blessed-orb", "harvest-reforge-likelihood"}  # beta methods made planner kinds after #886, on by default (#818, #159, #1195, #1231, #975, OR-41; #973: the offers are listed for the item a Scouring leaves)
DEFERRED = {"recombinator", "foulborn-exalted-orb"}  # opt-in with or without the classic offers (OR-37)
CLASSIC_DEFERRED = {"vaal", "locus"}  # B4: classic kinds, opt-in since #1125 (OR-37) and on again under the classic offers


def test_every_planner_kind_is_classic_turned_on_by_886_or_973_or_deferred():
    planner = [entry.name for entry in kinds(planner_only=True)]

    assert len(set(CLASSIC_KINDS)) == len(CLASSIC_KINDS) == 23
    assert set(planner) == set(CLASSIC_KINDS) | TURNED_ON_BY_886 | TURNED_ON_LATER | DEFERRED
    assert [name for name in planner if name in CLASSIC_KINDS] == list(CLASSIC_KINDS)  # the catalog's order
    assert {entry.name for entry in kinds(planner_only=True) if entry.opt_in} == DEFERRED | CLASSIC_DEFERRED  # every beta method (#886, OR-37)
    assert CLASSIC_DEFERRED <= set(CLASSIC_KINDS)


def test_with_the_classic_offers_the_default_is_the_classic_kinds_and_it_is_undone_after():
    with pytest.MonkeyPatch.context() as patch:
        classic_offers(patch)

        assert [entry.name for entry in kinds(planner_only=True) if not entry.opt_in] == list(CLASSIC_KINDS)
        assert _offers.BLOCKING_CRAFTS is False and _offers.ELDRITCH_GATE is True
        assert dict(corrupted.DEFAULT_CORRUPTING_KINDS) == CLASSIC_CORRUPTING_KINDS == {"vaal": 1, "locus": 2}

    assert {entry.name for entry in kinds(planner_only=True) if entry.opt_in} == DEFERRED | CLASSIC_DEFERRED
    assert _offers.BLOCKING_CRAFTS is True and _offers.ELDRITCH_GATE is False
