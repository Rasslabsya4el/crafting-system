"""Every example target is in one class of the rule of a bought start (#640, ADR-0064): drawn, names its mods, normal, or given.

A new target file that is none of these four fails here, so the rule is read for it on purpose and not by accident.
"""

from pathlib import Path

from abstraction_support import real_game_data

from crafting_system.actions import unopened_listing
from crafting_system.items import Rarity
from crafting_system.targets import StartKind, load_target

DRAWN = {"r07-minion-wand", "r08-energy-shield-boots", "r09-life-boots", "r13-life-resist-belt", "r14-hunter-bow", "r20-rf-helmet"}
NAMES_ITS_MODS = {  # a bought rare with its fractured mod listed (the mods it does not list: ticket #656)
    "r03-avoid-shock-boots", "r05-strength-ring", "r10-fractured-boots", "r10-fractured-boots-70-life", "r11-reservation-helmet", "r12-lightning-amulet",
    "r24-avoid-shock-boots",
}
NORMAL = {"r04-penetrating-quiver", "r06-strength-heavy-belt", "v01-minion-helmet"}  # a normal base holds no mods; V01's vendor recipes name theirs (ADR-0059)
GIVEN = {"j01-cobalt-life-attack-speed"}  # the item the player holds, as written (OR-6)


def test_every_example_target_is_in_one_class_of_the_rule():
    data = real_game_data()
    root = Path(__file__).resolve().parents[1] / "examples" / "targets"
    found: dict[str, set[str]] = {"drawn": set(), "names": set(), "normal": set(), "given": set()}
    for path in sorted(root.glob("*.yaml")):
        aim = load_target(path, data)
        if aim.start is StartKind.GIVEN:
            found["given"].add(path.stem)
        elif unopened_listing(data, aim.start_item) is not None:
            found["drawn"].add(path.stem)
        elif aim.start_item.mods:
            found["names"].add(path.stem)
        else:
            assert aim.start_item.rarity is Rarity.NORMAL, path.stem
            found["normal"].add(path.stem)

    assert found == {"drawn": DRAWN, "names": NAMES_ITS_MODS, "normal": NORMAL, "given": GIVEN}
