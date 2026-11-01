"""The socket actions' part of the contract suite's fixture (ticket #228): weapons and armour that hold sockets.

The amulet of the fixture takes no sockets, so the four socket kinds (the Jeweller's Orb, the Orb of Fusing, the bench count and link crafts)
have nothing to do on it and declare `applies_only_to`. Their items are a body armour (class maximum 6), a one-handed sword (3) and a bow (6)
of the contract data, with sockets, plain quality and a mod or two, each asked about the four kinds and no other kind:

* `sockets_body_three`: three coloured, unlinked sockets, 20% quality, two mods; * `sockets_body_linked_stranded`: four sockets in groups
  of two, one and one, 25% quality, 45 Memory Strands (the strand checks); * `sockets_body_six_linked`: six sockets in one group (the
  maximum: the orb and Fusing refuse it); * `sockets_body_low_level`: item level 10 (the gate allows three sockets); * `sockets_sword_two`: a
  three-socket class; * `sockets_bow_five`: a normal item with five sockets and no quality (Fusing below 20% is out of scope);
  * `sockets_body_none` and `sockets_body_corrupted`: the refusals.
"""

from contract_registry import register_extra_item

KINDS = ("jewellers-orb", "orb-of-fusing", "bench-socket-count", "bench-socket-links")


def _data():
    from sockets_support import socket_data  # late: contract_support loads this module while it builds CONTRACT_DATA

    return socket_data()


def _items():
    from abstraction_pool import LIFE_1, RESIST_2
    from sockets_support import BOW, SWORD, B, G, R, W, socketed, sockets_of, white

    from crafting_system.items import Rarity

    return {
        "sockets_body_three": lambda: socketed(sockets_of(R, G, B), mods=(RESIST_2, LIFE_1)),
        "sockets_body_linked_stranded": lambda: socketed(
            sockets_of(R, R, G, W, links=(2, 1, 1)), quality=25, mods=(RESIST_2, LIFE_1), memory_strands=45
        ),
        "sockets_body_six_linked": lambda: socketed(sockets_of(R, R, G, G, B, B, links=(6,)), mods=(LIFE_1,)),
        "sockets_body_low_level": lambda: socketed(white(2), item_level=10, mods=(LIFE_1,)),
        "sockets_sword_two": lambda: socketed(sockets_of(G, B, links=(2,)), base_id=SWORD, mods=(LIFE_1,)),
        "sockets_bow_five": lambda: socketed(white(5, (3, 1, 1)), base_id=BOW, rarity=Rarity.NORMAL, quality=0),
        "sockets_body_none": lambda: socketed(None, mods=(LIFE_1,)),
        "sockets_body_corrupted": lambda: socketed(white(3), mods=(LIFE_1,), corrupted=True),
    }


def _build(name: str):
    return _items()[name]()


for _name in ("sockets_body_three", "sockets_body_linked_stranded", "sockets_body_six_linked", "sockets_body_low_level",
              "sockets_sword_two", "sockets_bow_five", "sockets_body_none", "sockets_body_corrupted"):
    register_extra_item(_name, KINDS, _data, lambda name=_name: _build(name))
