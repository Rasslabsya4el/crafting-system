"""Ticket #271: put the strand sheet's crafts on our pool: base, item level, the mods before and after, the pool.

Needs the project package on the path (`src/`) and the pinned game data in a cache directory
(`python -m crafting_system.data fetch`, or the CRAFTING_CACHE_DIR of CI). Python 3.12 or later.
"""
from __future__ import annotations

import csv
import io
import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from itemtext import ModLine, ParsedItem, parse_item

# Four Battle Royale duplicates of ordinary suffixes and prefixes ("IncreasedCastSpeed2Royale", ...) are spawnable in the
# pinned export but are not in the game's tier tables: the sheet's own tier counts are one lower exactly for their mod
# types (31 of 1,834 mods in the foulborn tab, 0 elsewhere) and the Unravelling sheet's weights leave them out.
ROYALE_IDS = frozenset({"MovementVelocity2Royale", "IncreasedCastSpeed2Royale", "LocalIncreasedAttackSpeed2Royale____",
                        "IncreasedAttackSpeed2Royale"})

_GAME_POOLS: dict[int, tuple] = {}


def game_pool(data, item):
    """`pool_candidates` of the project with the four Royale duplicates taken out (cached by the identity of the pool)."""
    from crafting_system.actions.pool import pool_candidates

    candidates = pool_candidates(data, item)
    found = _GAME_POOLS.get(id(candidates))
    if found is None or found[0] is not candidates:
        found = _GAME_POOLS[id(candidates)] = (candidates, tuple(c for c in candidates if c.mod.id not in ROYALE_IDS))
    return found[1]


CLASS_NAMES = {
    "Body Armours": "Body Armour", "Rings": "Ring", "Boots": "Boots", "Gloves": "Gloves", "Helmets": "Helmet",
    "Shields": "Shield", "Bows": "Bow", "One Hand Swords": "One Hand Sword", "Rune Daggers": "Rune Dagger",
    "Claws": "Claw", "Belts": "Belt", "Amulets": "Amulet",
}


def read_sheet_csv(path: Path) -> list[dict[str, str]]:
    """The tab as a list of dicts; the CSV holds multi-line cells, so the csv module does the splitting."""
    text = Path(path).read_bytes().decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text, newline="")))


@dataclass
class Craft:
    index: int
    currency: str
    strands: int  # before the craft
    strands_after: int
    base_id: str
    item_level: int
    rarity_before: str
    rarity_after: str
    before: ParsedItem
    after: ParsedItem
    rows: list[dict[str, str]] = field(default_factory=list)  # the sheet rows of this craft (one per mod)
    problem: str = ""


class Mapper:
    """Resolve base names and mod names of the sheet to ids of the pinned data."""

    def __init__(self, data):
        self.data = data
        self.bases: dict[str, list] = {}
        for base in data.base_items.values():
            if base.domain == "item":
                self.bases.setdefault(base.item_class, []).append(base)
        self.by_name: dict[tuple[str, str], list] = {}
        for mod in data.mods.values():
            if mod.generation_type in ("prefix", "suffix") and mod.domain == "item" and mod.id not in ROYALE_IDS:
                self.by_name.setdefault((mod.generation_type, mod.name), []).append(mod)

    def base_for(self, parsed: ParsedItem) -> str | None:
        cls = CLASS_NAMES.get(parsed.item_class)
        if cls is None:
            return None
        bases = self.bases.get(cls, [])
        text = parsed.name_lines[-1] if parsed.rarity != "magic" else parsed.name_lines[0]
        found = [b for b in bases if b.name and b.name in text]
        if parsed.rarity == "rare" and len(parsed.name_lines) >= 2:
            found = [b for b in bases if b.name == parsed.name_lines[-1]] or found
        if not found:
            return None
        found.sort(key=lambda b: -len(b.name))
        best = len(found[0].name)
        top = [b for b in found if len(b.name) == best]
        names = {b.name for b in top}
        if len(names) != 1:
            return None
        # several bases of one name (a unique's twin): the tags are what matter for the pool; take the first
        return top[0].id

    def mod_for(self, line: ModLine, base_id: str, tiers: dict[str, int], tags: tuple[str, ...]):
        """The mod of the data that a mod line of the sheet shows on this base, or None when not one.

        Name and side give the candidates; the ones that cannot spawn on the base go; the tier of the header and
        the value ranges in the text decide between what is left. Returns (mod, how) where `how` names the test
        that was needed ("name", "tier", "range")."""
        from crafting_system.items import spawn_weight

        cands = [m for m in self.by_name.get((line.side, line.name), []) if spawn_weight(m, tags) > 0]
        if len(cands) == 1:
            return cands[0], "name"
        if not cands:
            return None, "none"
        if line.tier is not None:
            by_tier = [m for m in cands if tiers.get(m.id) == line.tier]
            if len(by_tier) == 1:
                return by_tier[0], "tier"
            if by_tier:
                cands = by_tier
        ranges = [(int(a), int(b)) for a, b in re.findall(r"\((-?\d+)-(-?\d+)\)", " ".join(line.text))]
        fit = [m for m in cands if [(s.min, s.max) for s in m.stats if (s.min, s.max) != (0, 0)][: len(ranges)] == ranges]
        if len(fit) == 1:
            return fit[0], "range"
        return None, f"ambiguous{len(cands)}"
