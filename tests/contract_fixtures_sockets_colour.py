"""The colour and quality actions' part of the contract suite's fixture (ticket #229).

The Chromatic Orb and the bench's colour crafts read the attribute requirements of the base, so their items are the body armour (intelligence),
the one-handed sword (strength and dexterity), the bow (dexterity) and a dexterity-intelligence helmet of `sockets_colour_support.colour_data()`; the
Whetstone and the Scrap are asked on weapons and armours of several qualities. Each item is asked about the kinds named here and no other kind:

* `colours_body_three`: three coloured, unlinked sockets, 20% quality; * `colours_body_white_six`: six white sockets in groups of three, two and one;
* `colours_body_one`: one white socket (always coloured); * `colours_body_two`: two sockets (no Omen); * `colours_helmet_four`: four white
  sockets on a dexterity-intelligence helmet; * `colours_sword_three_stranded`: 45 Memory Strands; * `colours_bow_five_plain`: no quality;
  * `colours_body_none`, `colours_body_corrupted`: the refusals;
* `quality_sword_plain`, `quality_body_ten`, `quality_helmet_nineteen`, `quality_bow_at_cap`, `quality_body_stranded`.
"""

from contract_registry import register_extra_item

COLOUR_KINDS = ("chromatic-orb", "bench-socket-colours")
QUALITY_KINDS = ("quality-currency",)


def _data():
    from sockets_colour_support import colour_data  # late: contract_support loads this module while it builds CONTRACT_DATA

    return colour_data()


def _items():
    from abstraction_pool import LIFE_1, RESIST_2
    from sockets_support import BOW, HELMET, SWORD, B, G, R, W, socketed, sockets_of, white

    from crafting_system.items import Rarity

    return {
        "colours_body_three": lambda: socketed(sockets_of(R, G, B), mods=(RESIST_2, LIFE_1)),
        "colours_body_white_six": lambda: socketed(white(6, (3, 2, 1)), mods=(LIFE_1,)),
        "colours_body_one": lambda: socketed(white(1), mods=(LIFE_1,)),
        "colours_body_two": lambda: socketed(sockets_of(W, R, links=(2,)), mods=(LIFE_1,)),
        "colours_helmet_four": lambda: socketed(white(4, (2, 1, 1)), base_id=HELMET, mods=(LIFE_1,)),
        "colours_sword_three_stranded": lambda: socketed(sockets_of(R, W, G, links=(2, 1)), base_id=SWORD, quality=10, mods=(LIFE_1,), memory_strands=45),
        "colours_bow_five_plain": lambda: socketed(white(5, (3, 1, 1)), base_id=BOW, rarity=Rarity.NORMAL, quality=0),
        "colours_body_none": lambda: socketed(None, mods=(LIFE_1,)),
        "colours_body_corrupted": lambda: socketed(white(3), mods=(LIFE_1,), corrupted=True),
    }


def _quality_items():
    from abstraction_pool import LIFE_1
    from sockets_support import BOW, HELMET, SWORD, socketed, white

    return {
        "quality_sword_plain": lambda: socketed(white(3), base_id=SWORD, quality=0, mods=(LIFE_1,)),
        "quality_body_ten": lambda: socketed(None, quality=10, item_level=75, mods=(LIFE_1,)),
        "quality_helmet_nineteen": lambda: socketed(white(2), base_id=HELMET, quality=19, mods=(LIFE_1,)),
        "quality_bow_at_cap": lambda: socketed(white(5), base_id=BOW, quality=20, item_level=95),
        "quality_body_stranded": lambda: socketed(white(2), quality=5, mods=(LIFE_1,), memory_strands=45),
    }


for _name in ("colours_body_three", "colours_body_white_six", "colours_body_one", "colours_body_two", "colours_helmet_four",
              "colours_sword_three_stranded", "colours_bow_five_plain", "colours_body_none", "colours_body_corrupted"):
    register_extra_item(_name, COLOUR_KINDS, _data, lambda name=_name: _items()[name]())
for _name in ("quality_sword_plain", "quality_body_ten", "quality_helmet_nineteen", "quality_bow_at_cap", "quality_body_stranded"):
    register_extra_item(_name, QUALITY_KINDS, _data, lambda name=_name: _quality_items()[name]())
