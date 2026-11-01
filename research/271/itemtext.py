"""Ticket #271: parse the item text of the strand sheet ("Item Class: ... { Prefix Modifier "Name" (Tier: N) ... }").

Standard library only. The sheet was exported as CSV with a UTF-8 em dash damaged into two characters, so the
parser reads the header lines with a pattern that does not depend on that character.
"""
import re
from dataclasses import dataclass, field

HEADER = re.compile(r'^\{ (?P<kind>[^"]*?)Modifier "(?P<name>[^"]+)"(?: \(Tier: (?P<tier>\d+)\))?.*\}$')


@dataclass
class ModLine:
    side: str  # prefix or suffix
    name: str
    tier: int | None
    text: tuple[str, ...]
    fractured: bool = False
    crafted: bool = False


@dataclass
class ParsedItem:
    item_class: str = ""
    rarity: str = ""
    name_lines: tuple[str, ...] = ()
    item_level: int | None = None
    strands: int = 0
    influences: tuple[str, ...] = ()
    unidentified: bool = False
    mods: list[ModLine] = field(default_factory=list)


INFLUENCES = {"Crusader", "Hunter", "Redeemer", "Warlord", "Shaper", "Elder", "Searing", "Tangled"}


def parse_item(text: str) -> ParsedItem:
    lines = text.replace("\r", "").split("\n")
    item = ParsedItem()
    sections: list[list[str]] = [[]]
    for line in lines:
        if line.strip() == "--------":
            sections.append([])
        else:
            sections[-1].append(line)
    head = [ln for ln in sections[0] if ln.strip()]
    for ln in head:
        if ln.startswith("Item Class: "):
            item.item_class = ln[len("Item Class: "):].strip()
        elif ln.startswith("Rarity: "):
            item.rarity = ln[len("Rarity: "):].strip().lower()
    item.name_lines = tuple(ln.strip() for ln in head if not ln.startswith(("Item Class:", "Rarity:")))
    infl = []
    for section in sections:
        for ln in section:
            if ln.startswith("Item Level: "):
                item.item_level = int(ln.split(":")[1])
            elif ln.startswith("Memory Strands: "):
                item.strands = int(ln.split(":")[1])
            elif ln.strip() == "Unidentified":
                item.unidentified = True
            elif ln.strip().endswith(" Item") and ln.strip().split()[0] in INFLUENCES:
                infl.append(ln.strip().split()[0])
    item.influences = tuple(infl)
    for section in sections:
        current: ModLine | None = None
        for ln in section:
            m = HEADER.match(ln.strip())
            if m is not None and ("Prefix" in m.group("kind") or "Suffix" in m.group("kind")):
                kind = m.group("kind")
                current = ModLine(
                    "prefix" if "Prefix" in kind else "suffix",
                    m.group("name"),
                    int(m.group("tier")) if m.group("tier") else None,
                    (),
                    fractured="Fractured" in kind,
                    crafted="Crafted" in kind,
                )
                item.mods.append(current)
            elif ln.startswith("{"):
                current = None
            elif current is not None and ln.strip():
                current.text = (*current.text, ln.strip())
    return item
