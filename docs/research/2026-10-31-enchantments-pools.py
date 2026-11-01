"""Pools of the Tempering Orb and the Tailoring Orb in 3.29, rebuilt from the repoe-fork dump (ticket #100).

Usage: python -I docs/research/2026-10-31-enchantments-pools.py <repoe-fork 3.29.3.3 folder>

The dump holds every Heist enchant mod ever made (group EnchantmentHeistWeapon / EnchantmentHeistArmour,
generation_type "unique", no spawn weights). The 3.29.0 notes remove the enchants "related to White Sockets or those
that set all Sockets to be Blue, Green or Red"; this script applies that removal by stat id and prints the pools,
the level groups and the socket-touching share, and the 14 Harvest quality enchants.
"""
import collections
import json
import sys

REMOVED_STATS = {
    "local_has_X_white_sockets",
    "local_all_sockets_are_red",
    "local_all_sockets_are_green",
    "local_all_sockets_are_blue",
}
SOCKET_STATS = {
    "local_all_sockets_linked",
    "local_cannot_have_red_sockets",
    "local_cannot_have_green_sockets",
    "local_cannot_have_blue_sockets",
    "local_maximum_sockets_+",
}
EFFECT_PREFIX = "heist_enchantment_"


def main(folder):
    mods = json.load(open(folder + "/mods.json", encoding="utf8"))
    pools = {"weapon": "EnchantmentHeistWeapon", "armour": "EnchantmentHeistArmour"}
    for name, group in pools.items():
        every = {k: v for k, v in mods.items() if v["groups"] == [group]}
        stats = lambda v: {s["id"] for s in v["stats"]}
        live = {k: v for k, v in every.items() if not (stats(v) & REMOVED_STATS)}
        print(f"== {name}: dump {len(every)}, removed in 3.29.0 {len(every) - len(live)}, current pool {len(live)}")
        assert all(not v["spawn_weights"] and not v["generation_weights"] for v in every.values())
        by_level = collections.Counter(v["required_level"] for v in live.values())
        print("   by required_level (the wiki's number column):", sorted(by_level.items()))
        touching = [k for k, v in live.items() if stats(v) & SOCKET_STATS]
        print(f"   touch sockets: {len(touching)} of {len(live)}")
        kinds = collections.Counter()
        for v in live.values():
            s = stats(v)
            if "local_can_have_additional_crafted_mods" in s:
                kinds["additional crafted modifier"] += 1
            elif "local_attribute_requirements_+%" in s and not any(i.startswith(EFFECT_PREFIX) for i in s):
                kinds["attribute requirements only"] += 1
            elif "local_all_sockets_linked" in s and not any(i.startswith(EFFECT_PREFIX) for i in s):
                kinds["sockets linked only"] += 1
            else:
                kinds["magnitude effect (+ rider)"] += 1
        print("   kinds:", dict(kinds))
        riders = collections.Counter()
        for v in live.values():
            for i in stats(v):
                if i in SOCKET_STATS or i == "local_attribute_requirements_+%":
                    riders[i] += 1
        print("   rider stats:", dict(riders))
    quality = {
        k: v
        for k, v in mods.items()
        if v["groups"] and v["groups"][0] in ("AlternateWeaponQuality", "AlternateArmourQuality")
    }
    print(f"== Harvest quality enchants in the dump: {len(quality)}")
    for k, v in sorted(quality.items()):
        print("  ", v["groups"][0], k, "|", v["text"].replace("\n", " / "))


if __name__ == "__main__":
    main(sys.argv[1])
