"""An explicit mod whose requirement asks a roll says the roll on the target card and on every line that names it (#1433).

R06 asks "(10-12)% increased Attributes" at roll 12 (`min_roll: 12`); the page printed the mod without the roll, so a player read the plan's
re-rolls as never reaching the target. By hand on the fixture belt: Cold Resistance asked at the top roll of ColdResist1 (read from the
data), the card and a step's line say "roll N or more", an item whose Cold Resistance is under it reads "below roll N".
"""

from items_support import DATA
from route_view_support import BELT, COLD, LEVEL, belt

from crafting_system.abstraction import Abstraction, Goal, Status
from crafting_system.cli._route_card import _StateReader, card_of_target
from crafting_system.targets import Requirement, StartKind, Target

TOP = DATA.mods[COLD].stats[0].max  # the best roll of the mod: the roll the requirement asks
COLD_AT_TOP = Requirement("ColdResistance", None, frozenset({COLD}), min_roll=(TOP,))


def _target() -> Target:
    return Target(BELT, LEVEL, frozenset(), (COLD_AT_TOP,), belt(), start=StartKind.BOUGHT)


def test_the_target_card_says_the_roll_an_explicit_mod_is_asked_at():
    card = card_of_target(DATA, _target())
    (cold,) = [slot for slot in card.suffixes if slot.tone == "wanted"]
    assert cold.note.endswith(f"roll {TOP} or more")


def test_a_line_naming_the_mod_says_its_roll_and_an_item_under_it_reads_below_the_roll():
    target = _target()
    reader = _StateReader(Abstraction(DATA, Goal.from_target(target), BELT, LEVEL))
    _, _, note = reader.leaf(0)
    assert note.endswith(f"roll {TOP} or more")
    below = reader.wanted([0], Status.BELOW)
    assert below.note == f"below roll {TOP}"  # one mod: only its roll can be short


def test_a_mod_asked_at_two_rolls_says_both_and_a_leaf_that_judges_a_tier_says_either():
    from crafting_system.cli._route_card import below_note, roll_note

    assert roll_note((None, 12)) == "roll 12 or more"
    assert roll_note((10, 12)) == "rolls 10 and 12 or more"
    assert roll_note(None) == ""
    assert below_note(False, (12,)) == "below roll 12" and below_note(True, (12,)) == "tier too low or below roll 12"
    assert below_note(True, None) == "tier too low"
