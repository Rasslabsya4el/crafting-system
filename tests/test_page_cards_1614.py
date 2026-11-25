"""The target card and the title as a player counts them (#1533, #1614), the item bought for a paid opening (#1540), and a use that loses
the item (#1602): small hand-made cases on the fixture's real mods and the toy listing boots.

* #1533: R13's goal card drew the multimod, two `any mod or empty` and a group of three resistances on a belt's three suffixes. A k-of-n group
  whose members are on one side fills `at_least` of that side's slots, each "one of" its members; the side still has its capacity.
* #1614: R14's goal card drew the multimod its two crafted mods need as `any mod or empty`, and its title named those crafted mods as if
  rolled.
* #1540: a start bought as a Normal base (R08, R09) or at any rarity (R14) drew the item the orbs make in step 1; the orbs' step read as the
  free draw's ("Accepts: 4, 5 or 6 mods", the mods as its goal).

#1602 (a use that loses the item says that share first) is held in `test_cli_route_view.py`, on its restart route.
"""

from items_support import DATA, item
from listing_support import magic_toy, prices, rare_toy, target
from test_start_listing_paid import searched_at, with_scouring

from crafting_system.cli import make_plan
from crafting_system.cli._route_card import ANY_OR_EMPTY, EMPTY, Slot, card_of_target
from crafting_system.cli._route_view import build_section, page_title, route_input
from crafting_system.targets import KOfN, Requirement, StartKind, Target, start_price_key

BELT = "Metadata/Items/Belts/Belt3"
FIRE, COLD, LIGHTNING = "FireResist1", "ColdResist1", "LightningResist1"
DAMAGE = "JunMaster2AllDamage2_"  # a crafted prefix
LOCK = "StrMasterItemGenerationCannotChangePrefixes"  # a crafted suffix
MULTIMOD = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"


def leaf(mod_id: str) -> Requirement:
    return Requirement(None, mod_id, frozenset({mod_id}))  # the stat text is only a label here


def belt_target(*requirements) -> Target:
    return Target(BELT, 86, frozenset(), tuple(requirements), item(base_id=BELT, item_level=86), start=StartKind.GIVEN)


def slots(card) -> list[str]:
    return [slot.text for slot in card.suffixes]


# --- #1533: a group on one side fills its slots ------------------------------------------------------------


def test_a_group_of_two_of_three_suffixes_fills_two_suffix_slots_and_the_side_keeps_its_capacity():
    card = card_of_target(DATA, belt_target(leaf(LOCK), KOfN(2, (leaf(FIRE), leaf(COLD), leaf(LIGHTNING)))))

    one_of = "one of Fire Resistance / Cold Resistance / Lightning Resistance"
    assert slots(card) == ["Prefixes Cannot Be Changed", one_of, one_of]  # three suffixes, never the lock, two open ones and three members
    assert card.suffixes[1] == Slot(one_of, "wanted", stands_for="group")
    assert [len(group.members) for group in card.groups] == [3]  # the members are still said once, under their heading (OR-15)
    assert card.prefixes == (ANY_OR_EMPTY,) * 3


def test_a_group_never_draws_more_slots_than_its_side_has_left():
    card = card_of_target(DATA, belt_target(leaf(LOCK), leaf(FIRE), KOfN(2, (leaf(COLD), leaf(LIGHTNING)))))

    assert len(card.suffixes) == 3 and slots(card)[2] == "one of Cold Resistance / Lightning Resistance"


# --- #1614: the multimod two crafted mods need, and the title ---------------------------------------------


def test_two_crafted_mods_draw_the_multimod_they_need_never_any_mod():
    card = card_of_target(DATA, belt_target(leaf(DAMAGE), leaf(LOCK)))

    assert slots(card) == ["Prefixes Cannot Be Changed", "Can have up to 3 Crafted Modifiers", "any mod or empty"]
    assert card.suffixes[1].note == "crafted, to hold the other crafted mods" and card.suffixes[1].stands_for == "needed"


def test_one_crafted_mod_or_an_asked_multimod_draws_no_second_multimod():
    assert "Can have up to 3 Crafted Modifiers" not in slots(card_of_target(DATA, belt_target(leaf(LOCK))))
    asked = card_of_target(DATA, belt_target(leaf(DAMAGE), leaf(LOCK), leaf(MULTIMOD)))
    assert slots(asked).count("Can have up to 3 Crafted Modifiers") == 1 and asked.suffixes[1].stands_for == ""


def test_the_title_says_crafted_of_a_crafted_mod_and_names_neither_a_group_slot_nor_the_needed_multimod():
    title = page_title(DATA, belt_target(leaf(DAMAGE), leaf(LOCK), KOfN(1, (leaf(FIRE), leaf(COLD)))))

    assert "crafted Damage" in title and "crafted Prefixes Cannot Be Changed" in title
    assert "Crafted Modifiers" not in title and "one of" not in title and "1 of Fire Resistance / Cold Resistance" in title


# --- #1540: the item bought for a paid opening ------------------------------------------------------------


def paid(data, aim, rarity: str, scouring: bool = False):
    key = start_price_key(data, aim)
    file = searched_at(prices(key), key, rarity)
    return make_plan(data, aim, with_scouring(file) if scouring else file)


def field(row, label: str) -> list[str]:
    return [line.text for entry in row.fields if entry.label == label for line in entry.lines]


def test_a_start_bought_as_a_normal_base_draws_the_normal_base_and_the_alchemy_makes_it_rare_once():
    data = rare_toy()
    plan = paid(data, target(data, rarity="rare", actions="alchemy-orb, chaos-orb", wanted=("ToyP1", "ToyS1")), "normal")

    rows = build_section(route_input(plan), data, None).rows
    assert rows[0].after.properties[0] == "Normal" and rows[0].after.prefixes == (EMPTY,) * 3 and rows[0].after.suffixes == (EMPTY,) * 3
    alchemy = rows[1]
    assert alchemy.title == "Orb of Alchemy on the bought Normal base"
    assert field(alchemy, "Goal") == ["a rare item"]  # never the mods, as if the orb were used again toward them (crafter on R08)
    assert field(alchemy, "Accepts") == []  # the free draw's words (crafter on R09, Q11)
    assert field(alchemy, "Used on")[0] == "the Normal Toy Listing Boots bought in step 1"
    assert field(alchemy, "Used on")[1].startswith("it comes out Rare")


def test_a_start_bought_at_any_rarity_draws_the_item_as_bought_and_the_orbs_make_it_magic():
    data = magic_toy()
    plan = paid(data, target(data, actions="alteration-orb, augmentation-orb"), "nonunique", scouring=True)

    rows = build_section(route_input(plan), data, None).rows
    bought = rows[0].after
    assert bought.properties[0] == "Any rarity but unique" and set(bought.prefixes) == {ANY_OR_EMPTY}  # its mods are any (OR-17)
    opened = rows[1]
    assert field(opened, "Goal") == ["a magic item"]
    assert field(opened, "Used on")[0] == "the Toy Listing Boots bought in step 1 (any rarity)"
    assert opened.after.properties[0] == "Magic"


def test_a_start_priced_at_its_own_rarity_keeps_the_listing_card_and_the_draw():
    data = magic_toy()
    plan = paid(data, target(data, actions="alteration-orb, augmentation-orb"), "magic")

    rows = build_section(route_input(plan), data, None).rows
    assert rows[0].after.properties[0] == "Magic" and not field(rows[1], "Used on")


def test_a_group_across_both_sides_reserves_no_slot_and_a_crafted_member_is_titled_crafted():
    card = card_of_target(DATA, belt_target(KOfN(1, (leaf(DAMAGE), leaf(FIRE)))))

    assert set(card.prefixes) == {ANY_OR_EMPTY} and set(card.suffixes) == {ANY_OR_EMPTY}  # which side the member takes is not known
    assert "1 of crafted Damage / Fire Resistance" in page_title(DATA, belt_target(KOfN(1, (leaf(DAMAGE), leaf(FIRE)))))


def test_the_needed_multimod_never_draws_a_line_past_the_side():
    card = card_of_target(DATA, belt_target(leaf(DAMAGE), leaf(LOCK), leaf(FIRE), leaf(COLD)))

    assert len(card.suffixes) == 3 and "Can have up to 3 Crafted Modifiers" not in slots(card)
