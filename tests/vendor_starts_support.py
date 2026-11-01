"""Shared helpers for the vendor-recipe start-option tests (ticket #330): a toy game with boots and a wand, prices, targets.

The fixture game data holds no boots and none of the recipe ladders, so `toy_data()` builds a small game of its own: the Toy Boots
and the Toy Wand, the six rungs of the movement speed family and the ten rungs of the flat added fire damage family (mod ids,
required levels and values follow the pinned dump), the life and chaos resistance mods of the fixture data, and ten junk families.
Nothing else spawns, so a Chaos Orb finds 30% movement speed or T2 fire damage rarely (a rung weighs 10 against 1,000 of a junk
family) and a recipe start has something to save. The solver runs on it in well under a second.

`toy_target(...)` parses a target on the toy items; `prices(...)` is a price file with the lines the recipes need, at the fixture
prices below.
"""

import dataclasses
import datetime
import textwrap

from items_support import DATA

from crafting_system.data import BaseItem, GameData, Mod, StatRange, Weight
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import Target, parse_target

TOY_BOOTS = "Metadata/Items/Armours/Boots/ToyBoots1"
TOY_BOOTS_NAME = "Toy Boots"
TOY_WAND = "Metadata/Items/Weapons/OneHandWeapons/Wands/ToyWand1"
TOY_WAND_NAME = "Toy Wand"
SPEED_LADDER = ((1, 10), (15, 15), (30, 20), (40, 25), (55, 30), (86, 35))  # (required level, per cent), MovementVelocity1 to 6
FIRE_LEVELS = (1, 11, 18, 26, 33, 42, 51, 62, 74, 82)  # LocalAddedFireDamage1 to 10: the wiki caps the chain at T3 (rung 8), Craft of Exile at T2 (rung 9)
SPEED_WEIGHT = 10
FIRE_WEIGHT = 10

BASE_PRICE = 1.0
FLASK_PRICE = 2.0
AUGMENTATION_PRICE = 0.5
BOOTS_NAME = f"{TOY_BOOTS_NAME} (ilvl 86)"
WAND_NAME = f"{TOY_WAND_NAME} (ilvl 86)"
QUICKSILVER = "Quicksilver Flask"
RUBY = "Ruby Flask"
AUGMENTATION = "Orb of Augmentation"
CURRENCY = {
    "Orb of Transmutation": 0.1,
    "Orb of Alteration": 0.2,
    AUGMENTATION: AUGMENTATION_PRICE,
    "Regal Orb": 1.0,
    "Exalted Orb": 8.0,
    "Orb of Annulment": 3.0,
}


def _weights(weight: int) -> tuple[Weight, ...]:
    return (Weight("boots", weight), Weight("wand", weight), Weight("default", 0))


def toy_data() -> GameData:
    """The toy game: see the module docstring."""
    mods: dict[str, Mod] = {}
    for mod_id in ("IncreasedLife1", "IncreasedLife2", "IncreasedLife3", *(f"ChaosResist{n}" for n in range(1, 7))):
        weight = 250 if mod_id.startswith("Chaos") else 1000
        mods[mod_id] = dataclasses.replace(DATA.mods[mod_id], spawn_weights=_weights(weight))
    for number, (level, speed) in enumerate(SPEED_LADDER, start=1):
        mods[f"MovementVelocity{number}"] = Mod(
            id=f"MovementVelocity{number}", name=f"of Toy Speed {number}", text=f"{speed}% increased Movement Speed",
            type="MovementVelocity", families=("MovementVelocity",), domain="item", generation_type="prefix",
            required_level=level, spawn_weights=(Weight("boots", SPEED_WEIGHT), Weight("default", 0)), generation_weights=(),
            adds_tags=(), implicit_tags=("speed",), stats=(StatRange("base_movement_velocity_+%", speed, speed),),
            is_essence_only=False,
        )  # fmt: skip
    for number, level in enumerate(FIRE_LEVELS, start=1):
        mods[f"LocalAddedFireDamage{number}"] = Mod(
            id=f"LocalAddedFireDamage{number}", name=f"Toy Fire {number}", text="Adds # to # Fire Damage",
            type="LocalAddedFireDamage", families=("LocalAddedFireDamage",), domain="item", generation_type="prefix",
            required_level=level, spawn_weights=(Weight("wand", FIRE_WEIGHT), Weight("default", 0)), generation_weights=(),
            adds_tags=(), implicit_tags=("fire",),
            stats=(
                StatRange("local_minimum_added_fire_damage", 10 * number, 10 * number + 2),
                StatRange("local_maximum_added_fire_damage", 20 * number, 20 * number + 4),
            ),
            is_essence_only=False,
        )  # fmt: skip
    for side, count in (("prefix", 6), ("suffix", 4)):  # families nobody asks for, so that a Chaos Orb draws the wanted ones rarely
        for number in range(1, count + 1):
            name = f"ToyJunk{side.capitalize()}{number}"
            mods[name] = Mod(
                id=name, name=f"of {name}", text=f"+# to {name}", type=name, families=(name,), domain="item",
                generation_type=side, required_level=1, spawn_weights=_weights(1000), generation_weights=(), adds_tags=(),
                implicit_tags=(), stats=(StatRange("toy_junk", 1, 5),), is_essence_only=False,
            )  # fmt: skip
    boots = BaseItem(TOY_BOOTS, TOY_BOOTS_NAME, "Boots", "item", 1, ("boots", "armour", "default"), (), "released")
    wand = BaseItem(TOY_WAND, TOY_WAND_NAME, "Wand", "item", 1, ("wand", "weapon", "default"), (), "released")
    return GameData("toy", mods, {TOY_BOOTS: boots, TOY_WAND: wand}, {}, {}, ())


TOY = toy_data()

BOOTS_TARGET = """\
base: Toy Boots
item_level: 86
start_item:
  rarity: rare
  mods: []
actions: [chaos-orb, regal-orb, exalted-orb]
requirements:
  - family: MovementVelocity
    min_tier: 2
  - family: IncreasedLife
  - family: ChaosResistance
"""

WAND_TARGET = """\
base: Toy Wand
item_level: 86
start_item:
  rarity: rare
  mods: []
actions: [chaos-orb, regal-orb, exalted-orb]
requirements:
  - family: LocalAddedFireDamage
    min_tier: 2
  - family: IncreasedLife
  - family: ChaosResistance
"""


def toy_target(text: str = BOOTS_TARGET, data: GameData = TOY) -> Target:
    """A target on the toy items (default: 30% or better movement speed boots with life and chaos resistance, from a free rare start)."""
    return parse_target(textwrap.dedent(text), data, source="toy.yaml")


def prices(*, base: float | None = BASE_PRICE, flask: float | None = FLASK_PRICE, divine: float = 300.0, **lines: float) -> PriceFile:
    """A price file: the currency the target needs and the goods of the movement speed recipe (None leaves a line out).

    `lines` adds more, by name with underscores for spaces (`Ruby_Flask=3`); `base` is the price of the Toy Boots (ilvl 86)."""
    entries = {name: PriceEntry(chaos, "fixture") for name, chaos in CURRENCY.items()}
    if base is not None:
        entries[BOOTS_NAME] = PriceEntry(base, "trade-api")
    if flask is not None:
        entries[QUICKSILVER] = PriceEntry(flask, "trade-api")
    for name, chaos in lines.items():
        entries[name.replace("_", " ")] = PriceEntry(chaos, "fixture")
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), divine, entries)
