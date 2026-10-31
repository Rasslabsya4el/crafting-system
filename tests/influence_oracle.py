"""A hand oracle for the pool of the fixture Thicket Bow, plain and with the Hunter tag (ticket #67).

The table is typed by hand from the fixture excerpt (`fixtures/repoe`, the eight families of the bow
that `make_excerpts.py` picks), the sum of the weights of the mods of each family that a bow can roll
at the item level, the level gate (a required level equal to the item level is allowed) applied by
eye. It shares nothing with `crafting_system`.

The weights, by family and mod (required level in brackets), all on the bow tags (`bow`, `weapon`, ...),
the Hunter ones on the tag `bow_basilisk` (the Hunter influence on the item class bow):

* Fire Damage and Cold Damage (prefixes): Added Fire Damage Two Hand 1 (1) and Added Cold Damage Two
  Hand 1 (2) of 1400 each, the two bow mods that the fixture holds besides the eight families.
* Increased Attack Speed (suffix): Local Increased Attack Speed 1 (1), 2 (11), 2Royale (4), 3 (22) of 1000
  each, 4 (30) and 5 (37) of 500 each: 5000 from item level 37.
* Increase Socketed Gem Level (prefix): +1 to Level of Socketed Gems (50), 1000.
* Increase Specific Socketed Gem Level (prefix): Bow Gem Level 1 (9) and 2 (64), 1000 each.
* Additional Arrows (suffix): Bow 1 (70), 1000; Bow 2 (86), 100.
* Hunter only: Chaos Damage Hybrid (prefix): 1 (68) 500, 2 (71) 500, 3 (74) 400, 4 (77) 300, 5 (80) 200;
  Added Cold Damage per Dexterity (prefix): 1 (68) 200; Armour Penetration (suffix): 1 (68) 500, 2 (71) 500;
  Chance to Intimidate on Hit (suffix): 1 (78) 500, 2 (81) 500.
"""

from actions_oracle import PREFIX, SUFFIX

PLAIN = {
    77: {
        "FireDamage": (PREFIX, 1400),
        "ColdDamage": (PREFIX, 1400),
        "IncreasedAttackSpeed": (SUFFIX, 5000),
        "IncreaseSocketedGemLevel": (PREFIX, 1000),
        "IncreaseSpecificSocketedGemLevel": (PREFIX, 2000),
        "AdditionalArrows": (SUFFIX, 1000),
    },
}
PLAIN[78] = PLAIN[77]
PLAIN[80] = PLAIN[77]
PLAIN[86] = {**PLAIN[77], "AdditionalArrows": (SUFFIX, 1100)}

HUNTER_ONLY = {
    77: {
        "ChaosDamageHybrid": (PREFIX, 1700),
        "AddedColdDamagePerDexterity": (PREFIX, 200),
        "ArmourPenetration": (SUFFIX, 1000),
    },
}
HUNTER_ONLY[78] = {**HUNTER_ONLY[77], "ChanceToIntimidateOnHit": (SUFFIX, 500)}
HUNTER_ONLY[80] = {**HUNTER_ONLY[78], "ChaosDamageHybrid": (PREFIX, 1900)}
HUNTER_ONLY[86] = {**HUNTER_ONLY[80], "ChanceToIntimidateOnHit": (SUFFIX, 1000)}

LEVELS = (77, 78, 80, 86)


def families(level: int, hunter: bool) -> dict[str, tuple[str, int]]:
    """The pool of a bow of item level `level` with nothing on it: family -> (side, weight)."""
    return {**PLAIN[level], **(HUNTER_ONLY[level] if hunter else {})}
