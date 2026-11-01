"""A small made-up export for the tests of asked and allowed corruption in a target (ticket #257, ADR-0036).

`DATA` holds three jewellery bases (a ring with one base implicit, a ring with none, a belt), a body armour with both Eldritch sides, a
flask (no corrupted pool) and the mods the tests need: corrupted implicits of three item levels and four mod groups, a corrupted implicit
only the belt can get, a base implicit and an explicit suffix that share the text of corrupted ones, and Eldritch implicits.

`parse` puts `HEADER` before the text of a test, so the text starts on line 7; the file is called `t.yaml`.
"""

import textwrap

from crafting_system.data import GameData, normalize_game_data
from crafting_system.targets import Target, TargetError, parse_target

RING = "Metadata/Items/Rings/Ring8"  # Prismatic Ring: one base implicit
PLAIN_RING = "Metadata/Items/Rings/Ring1"  # no implicit
BELT = "Metadata/Items/Belts/Belt1"
BODY = "Metadata/Items/Armours/BodyArmours/BodyStr1"
FLASK = "Metadata/Items/Flasks/FlaskLife1"
QUIVER = "Metadata/Items/Quivers/Quiver1"  # its only corrupted implicit needs item level 20

ALL_RES = "+#% to all Elemental Resistances"
COLD_DAMAGE = "Adds # to # Cold Damage to Spells and Attacks"
FIRE_DAMAGE = "Adds # to # Fire Damage to Spells and Attacks"
HEADER = """\
base: Prismatic Ring
item_level: 84
requirements:
  - family: ColdResistance
"""
HEADER_LINES = len(HEADER.splitlines())


def _mod(mod_id, *, text, weights, group=None, level=1, generation_type="corrupted", domain="item", low=1, high=2):
    return {
        "name": mod_id,
        "text": text,
        "type": group or mod_id,
        "groups": [group or mod_id],
        "domain": domain,
        "generation_type": generation_type,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in weights],
        "generation_weights": [],
        "adds_tags": [],
        "implicit_tags": [],
        "stats": [{"id": f"{mod_id}_stat", "min": low, "max": high}],
        "is_essence_only": False,
    }


def _base(name, item_class, tags, implicits=()):
    return {
        "name": name,
        "item_class": item_class,
        "domain": "item",
        "drop_level": 1,
        "tags": tags,
        "implicits": list(implicits),
        "release_state": "released",
    }


def _cold(number, level):
    return _mod(
        f"ColdCorrupted{number}", text="Adds (3-4) to (7-8) Cold Damage to Spells and Attacks",
        weights=[("ring", 1000), ("default", 0)], group="AddedCold", level=level, low=3, high=4,
    )  # fmt: skip


RAW_MODS = {
    # the base implicit of the Prismatic Ring: the same text as the corrupted one, another family
    "RingResistImplicit": _mod(
        "RingResistImplicit", text="+(8-10)% to all Elemental Resistances", weights=[], group="AllResistances",
        generation_type="unique", low=8, high=10,
    ),  # fmt: skip
    "ResistCorrupted": _mod(
        "ResistCorrupted", text="+(14-16)% to all Elemental Resistances",
        weights=[("ring", 1000), ("belt", 500), ("body_armour", 500), ("default", 0)], group="AllResistancesCorrupted",
        low=14, high=16,
    ),  # fmt: skip
    "ColdCorrupted1": _cold(1, 1),
    "ColdCorrupted2": _cold(2, 31),
    "ColdCorrupted3": _cold(3, 81),
    "FireCorrupted1": _mod(
        "FireCorrupted1", text="Adds (3-4) to (7-8) Fire Damage to Spells and Attacks",
        weights=[("ring", 1000), ("default", 0)], group="AddedFire", low=3, high=4,
    ),  # fmt: skip
    "ChaosCorrupted": _mod(
        "ChaosCorrupted", text="+(10-14)% to Chaos Resistance", weights=[("ring", 250), ("default", 0)],
        group="ChaosResistanceCorrupted", low=10, high=14,
    ),  # fmt: skip
    "BeltOnlyCorrupted": _mod(
        "BeltOnlyCorrupted", text="(10-15)% increased Stun Duration", weights=[("belt", 500), ("default", 0)],
        group="StunDurationCorrupted", low=10, high=15,
    ),  # fmt: skip
    "LateCorrupted": _mod(
        "LateCorrupted", text="+(1-2)% to Quality of Supported Gems", weights=[("ring", 200), ("default", 0)],
        group="LateCorruptedGroup", level=81, low=1, high=2,
    ),  # fmt: skip
    "QuiverCorrupted": _mod(
        "QuiverCorrupted", text="(5-8)% increased Projectile Speed", weights=[("quiver", 1000), ("default", 0)],
        group="QuiverCorruptedGroup", level=20, low=5, high=8,
    ),  # fmt: skip
    # an explicit suffix, found by the ordinary lookup only
    "ColdResist1": _mod(
        "ColdResist1", text="+(6-11)% to Cold Resistance", weights=[("ring", 1000), ("default", 0)], group="ColdResistance",
        generation_type="suffix", low=6, high=11,
    ),  # fmt: skip
    # Eldritch implicits of both sides on body armour (the grade is the last digit of the id)
    "AvoidShockEldritchImplicit1": _mod(
        "AvoidShockEldritchImplicit1", text="(33-35)% chance to Avoid being Shocked", weights=[("body_armour", 700), ("default", 0)],
        group="AvoidShock", generation_type="searing_exarch_implicit", level=75, low=33, high=35,
    ),  # fmt: skip
    "ChanceToShockEldritchImplicit1": _mod(
        "ChanceToShockEldritchImplicit1", text="(8-9)% chance to Shock", weights=[("body_armour", 700), ("default", 0)],
        group="ChanceToShock", generation_type="eater_of_worlds_implicit", level=75, low=8, high=9,
    ),  # fmt: skip
}
RAW_BASES = {
    RING: _base("Prismatic Ring", "Ring", ["ring", "jewellery", "default"], ["RingResistImplicit"]),
    PLAIN_RING: _base("Iron Ring", "Ring", ["ring", "jewellery", "default"]),
    BELT: _base("Leather Belt", "Belt", ["belt", "default"]),
    BODY: _base("Plate Vest", "Body Armour", ["body_armour", "armour", "default"]),
    FLASK: _base("Small Life Flask", "LifeFlask", ["flask", "default"]),
    QUIVER: _base("Serpent Quiver", "Quiver", ["quiver", "default"]),
}

DATA: GameData = normalize_game_data(RAW_MODS, RAW_BASES, {}, {}, [], version="0.0-test")


def parse(text: str, *, header: bool = True) -> Target:
    """Parse `text` on `DATA`; unless `header` is false it follows `HEADER` (so it starts on line `HEADER_LINES + 1`)."""
    body = textwrap.dedent(text).lstrip("\n")
    return parse_target(HEADER + body if header else body, DATA, source="t.yaml")


def parse_error(text: str, *, header: bool = True) -> str:
    """The message of the `TargetError` that parsing `text` raises; fails the test if none is raised."""
    try:
        parse(text, header=header)
    except TargetError as error:
        return str(error)
    raise AssertionError("the target parsed without an error")


def assert_error(message: str, line: int, key: str, *causes: str) -> None:
    assert message.startswith(f"t.yaml:{line}: "), message
    assert f": {key}: " in message, message
    for cause in causes:
        assert cause in message, message
