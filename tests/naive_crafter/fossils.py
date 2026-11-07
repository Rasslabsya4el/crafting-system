"""The fossils of a resonator and the weight they give a mod (ticket #608).

The records are the export's `fossils.json` (read as a plain dict, like the other files). A fossil here is one that only changes the weights of
tags: a list of boosted tags (`positive_mod_weights`) and a list of cut or blocked tags (`negative_mod_weights`), each a weight in percent
(rule `fossil_weight_is_percent_factor`). A fossil with any other effect is refused by name with `Unsupported` (it adds mods to the pool, forces
a mod, fractures one, makes the item corrupted, rolls twice, restricts the base, or changes the pool by a rule of its own).

The weight of a mod under a set (rules `fossil_tags_are_implicit_tags`, `fossil_factors_stack_per_tag`, `fossil_block_wins`):
  * 0 when any tag of the mod is blocked by a fossil of the set;
  * else the weight times P times N, where P is the sum over the tags of the mod of the boost factor of the tag (the boosts of the fossils that
    boost the tag added; 1 when no tag of the mod is boosted) and N is the product of the cut factors of the tags of the mod.
"""

import json
from pathlib import Path

from .craft import Unsupported

FILE = "fossils.json"
# the fossils that do something besides change weights of tags, by what they do
SPECIAL = {
    "Opulent Fossil": "removes every mod without a tag from the pool",
    "Sanctified Fossil": "multiplies the weight by the level of the mod and rolls the values twice",
    "Corroded Fossil": "boosts the hybrid tags (bleed, poison) and bypasses the other fossils' factors on them",
    "Tangled Fossil": "applies one random pair of a boost and a block",
    "Fractured Fossil": "fractures one of the mods",
    "Bloodstained Fossil": "corrupts the item",
    "Gilded Fossil": "adds a vendor-value implicit",
    "Faceted Fossil": "adds mods to the pool",
    "Hollow Fossil": "forces a mod and restricts the base",
    "Glyphic Fossil": "forces a mod of the corrupted essences",
}


def read_fossils(source: str) -> dict[str, dict]:
    """The fossil records of an export folder by name; empty when the folder has no `fossils.json` (a made-up export)."""
    path = Path(source) / FILE
    if not path.is_file():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {record["name"]: record for key, record in records.items() if "RandomFossilOutcome" not in key and record.get("name")}


class FossilSet:
    """The fossils of one resonator: the factors they give by tag, the tags they block, and what they ask of the base."""

    def __init__(self, names: tuple[str, ...], records: dict[str, dict]):
        if len(set(names)) != len(names):
            raise Unsupported(f"a resonator holds one fossil of each type, and {names} names one twice")
        self.names = names
        self.boost: dict[str, float] = {}
        self.cut: dict[str, float] = {}
        self.blocked: set[str] = set()
        self.allowed: list[frozenset[str]] = []
        self.forbidden: set[str] = set()
        for name in names:
            if name in SPECIAL:
                raise Unsupported(f"{name!r}: this player lacks the fossil that {SPECIAL[name]}")
            record = records.get(name)
            if record is None:
                raise Unsupported(f"{name!r}: no fossil of this name in the export")
            if record["added_mods"] or record["forced_mods"] or record["sell_price_mods"] or record["rolls_lucky"] or record["mirrors"] or record["changes_quality"]:
                raise Unsupported(f"{name!r}: this player lacks a fossil that adds, forces or fractures a mod or changes the roll")
            if record["allowed_tags"]:
                self.allowed.append(frozenset(record["allowed_tags"]))
            self.forbidden |= set(record["forbidden_tags"])
            for entry in (*record["positive_mod_weights"], *record["negative_mod_weights"]):
                tag, factor = entry["tag"], entry["weight"] / 100
                if factor == 0:
                    self.blocked.add(tag)
                elif factor < 1:
                    self.cut[tag] = self.cut.get(tag, 1.0) * factor
                else:
                    self.boost[tag] = self.boost.get(tag, 0.0) + factor
        self.key = tuple(sorted(names))

    def refuses(self, base_tags) -> str | None:
        """Why the resonator does not take an item of a base with these tags (the rule `fossil_use_restrictions`), or None."""
        if self.forbidden & set(base_tags):
            return f"a fossil forbids the base tags {sorted(self.forbidden & set(base_tags))}"
        for allowed in self.allowed:
            if not allowed & set(base_tags):
                return f"a fossil asks for one of the base tags {sorted(allowed)}"
        return None

    def factor(self, tags, boost: bool = True, block: bool = True) -> float:
        """The factor of a mod with these `implicit_tags`; `boost` and `block` are the two laws a test may turn off."""
        if block and self.blocked.intersection(tags):
            return 0.0
        total, found = 0.0, False
        cut = 1.0
        for tag in tags:
            if boost and tag in self.boost:
                total += self.boost[tag]
                found = True
            cut *= self.cut.get(tag, 1.0)
        return (total if found else 1.0) * cut
