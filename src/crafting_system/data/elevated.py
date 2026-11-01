"""The Elevated mods: which Elevated mod a top-tier influence mod becomes under an Orb of Dominance (ticket #154).

The export has no link from a mod to its Elevated version. Craft of Exile has one, the table `poecd.maeven.bmods`
(key `<base id>-<modifier id>`, value an entry of `poecd.maeven.ind`), and the decision of grill B2 (issue #93, claim
`dominance.elevated_mapping_is_coe_table`) is to use it. Its ids are not the export's, and it is older than the export
(its data is patch 3.29.0.3, the export 3.29.3.3), so this module turns the table into a mapping between *export* ids:

    `elevated.json`  =  { top-tier ordinary mod id  ->  Elevated mod id }

`build_elevated` reads Craft of Exile's `poec_data.json` and the pinned `mods.json` and writes that file; the command is
`python -m crafting_system.data elevated <folder of Craft of Exile's data>`. The file is committed and read offline by
`load_elevated`; nothing at run time needs Craft of Exile. The patch-update skill reruns the command when the pin moves,
and a test fails until it has.

How a table entry is read in the export. A table entry names a base group of armour (helmet, gloves, boots, body armour),
an influence, a side, a family and a text, so the two mods it links are found by the tag `<class>_<influence>` of the
export's spawn weights, the generation type, the family, and then the text with its numbers blanked. Where the wording or the
numbers changed between the two patches, the top tier of the entry (its level and value ranges) names the ordinary mod, and
the Elevated entry's level and ranges name the Elevated one; a family with one Elevated mod on that tag has no other
candidate. What no step settles is kept in `unresolved` with the reason, and the Orb of Dominance treats such a mod as
unknown (out of scope), never as a guess.
"""

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from .errors import DataError
from .model import GameData, Mod

ELEVATED_FILE = Path(__file__).with_name("elevated.json")
CLASS_OF_BASE_GROUP = {"2": "body_armour", "3": "boots", "4": "helmet", "5": "gloves"}  # Craft of Exile's base groups
SIDES = ("prefix", "suffix")
ELEVATED_WORD = "Elevated"  # every Elevated mod of the export has it in its name ("Elevated Shaper's", "of the Elevated Elder")


def is_elevated(mod: Mod) -> bool:
    """Whether `mod` is an Elevated mod (an Orb of Dominance makes it; no draw does): the word is in its name."""
    return ELEVATED_WORD in (mod.name or "")


class ElevatedError(DataError):
    """Craft of Exile's table or the export does not have the shape the step reads, or `elevated.json` is malformed."""


@dataclass(frozen=True)
class Unresolved:
    """A kind of table entry the step could not link in the export: where it is and why."""

    tag: str
    family: str
    side: str
    text: str
    reason: str
    entries: int  # how many keys of the table (one per base) say it


@dataclass(frozen=True)
class ElevatedMods:
    """The committed mapping: from the export version it was made for."""

    repoe_version: str
    poec_data_sha256: str
    of_top_tier: Mapping[str, str]  # ordinary top-tier mod id -> Elevated mod id
    unresolved: tuple[Unresolved, ...]

    def for_data(self, data: GameData) -> Mapping[str, str]:
        """The mapping when `data` is the export it was made for, else nothing (the ids of another export mean something else)."""
        return self.of_top_tier if data.version == self.repoe_version else {}


# --- reading the committed file --------------------------------------------------------------------------------


@cache
def load_elevated(path: Path = ELEVATED_FILE) -> ElevatedMods:
    """Read the committed mapping. Raises `ElevatedError` for a missing or malformed file."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        mapping = document["elevated"]
        if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise ValueError("`elevated` must map mod ids to mod ids")
        unresolved = tuple(Unresolved(**row) for row in document["unresolved"])
        return ElevatedMods(str(document["repoe_version"]), str(document["poec_data_sha256"]), dict(mapping), unresolved)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ElevatedError(f"{path} is not a valid Elevated mapping: {error}") from error


# --- building it ------------------------------------------------------------------------------------------------


def parse_poec_data(text: str) -> dict[str, Any]:
    """The tables of Craft of Exile's `poec_data.json` (a JavaScript assignment of one JSON object)."""
    try:
        return json.loads(text[text.index("=") + 1 :].rstrip().rstrip(";"))
    except (ValueError, json.JSONDecodeError) as error:
        raise ElevatedError(f"poec_data.json is not the file the step reads: {error}") from error


def template(text: str) -> str:
    """A mod text with its numbers, ranges and signs blanked, lower case, lines joined: what two patches of one mod share."""
    text = text.replace("\n", ", ")
    text = re.sub(r"\([-+]?\d+(?:\.\d+)?-[-+]?\d+(?:\.\d+)?\)", "#", text)
    text = re.sub(r"(?<![A-Za-z#])\d+(?:\.\d+)?", "#", text)
    text = text.replace("+", "").replace("-#", "#")
    text = re.sub(r"#+", "#", text)
    return re.sub(r"\s+", " ", text).strip().lower()


Signature = tuple[tuple[int | float, int | float], ...]


def _signature_of_stats(mod: Mapping[str, Any]) -> Signature:
    return tuple(sorted((min(s["min"], s["max"]), max(s["min"], s["max"])) for s in mod["stats"]))


def _signature_of_values(nvalues: Any) -> Signature:
    values = json.loads(nvalues) if isinstance(nvalues, str) else nvalues
    return tuple(sorted((min(v), max(v)) if isinstance(v, list) else (v, v) for v in values))


def _weight_on(mod: Mapping[str, Any], tag: str) -> int | None:
    return next((entry["weight"] for entry in mod["spawn_weights"] if entry["tag"] == tag), None)


def build_elevated(coe: Mapping[str, Any], mods: Mapping[str, Any], *, repoe_version: str, poec_data_sha256: str) -> dict[str, Any]:
    """The document of `elevated.json` from Craft of Exile's tables `coe` and the export's raw `mods`.

    Raises `ElevatedError` when a table the step reads is missing.
    """
    try:
        modifiers = {entry["id_modifier"]: entry for entry in coe["modifiers"]["seq"]}
        base_group = {entry["id_base"]: entry["id_bgroup"] for entry in coe["bases"]["seq"]}
        influence_key = {g["id_mgroup"]: g["poedb_id"] for g in coe["mgroups"]["seq"] if g["is_influence"] == "1"}
        table, entries, tiers = coe["maeven"]["bmods"], coe["maeven"]["ind"], coe["tiers"]
    except (KeyError, TypeError) as error:
        raise ElevatedError(f"Craft of Exile's data lacks the table {error}") from error

    ordinary_on: dict[str, list[str]] = defaultdict(list)  # tag -> ordinary item mods that spawn on it
    elevated_on: dict[str, list[str]] = defaultdict(list)  # tag -> Elevated item mods listed under it
    for mod_id, mod in mods.items():
        if mod["domain"] != "item" or mod["generation_type"] not in SIDES:
            continue
        if ELEVATED_WORD in (mod.get("name") or ""):
            for entry in mod["spawn_weights"]:
                elevated_on[entry["tag"]].append(mod_id)
        else:
            for entry in mod["spawn_weights"]:
                if entry["weight"] > 0:
                    ordinary_on[entry["tag"]].append(mod_id)

    linked: dict[str, set[str]] = defaultdict(set)
    failures: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    for key in sorted(table):
        base, modifier_id = key.split("-")
        modifier = modifiers.get(modifier_id)
        if modifier is None or modifier["id_mgroup"] not in influence_key or base_group.get(base) not in CLASS_OF_BASE_GROUP:
            failures[("", "", "", key, "the table names a modifier or a base the step does not read")] += 1
            continue
        tag = f"{CLASS_OF_BASE_GROUP[base_group[base]]}_{influence_key[modifier['id_mgroup']]}"
        family, side, text = modifier["modgroup"], modifier["affix"], template(modifier["name_modifier"])
        entry = entries[table[key]]
        top = max(tiers.get(modifier_id, {}).get(base) or [{"ilvl": "0", "nvalues": "[]"}], key=lambda tier: int(tier["ilvl"]))
        ordinary = _find_ordinary(mods, ordinary_on[tag], family, side, text, int(top["ilvl"]), _signature_of_values(top["nvalues"]))
        if ordinary[0] is None:
            failures[(tag, family, side, text, ordinary[1])] += 1
            continue
        elevated = _find_elevated(
            mods, elevated_on[tag], family, side, template(entry["oname"]), int(entry["ilvl"]), _signature_of_values(entry["nvalues"])
        )
        if elevated[0] is None:
            failures[(tag, family, side, text, elevated[1])] += 1
            continue
        linked[ordinary[0]].add(elevated[0])

    conflicts = {top_id for top_id, found in linked.items() if len(found) > 1}
    for top_id in sorted(conflicts):
        failures[("", "", "", top_id, "two Elevated mods for one ordinary mod")] += 1
    mapping = {top_id: next(iter(found)) for top_id, found in sorted(linked.items()) if top_id not in conflicts}
    unresolved = [
        {"tag": tag, "family": family, "side": side, "text": text, "reason": reason, "entries": count}
        for (tag, family, side, text, reason), count in sorted(failures.items())
    ]
    return {
        "source": (
            "Craft of Exile poec_data.json, tables maeven, modifiers, tiers, bases and mgroups, read against the pinned "
            "repoe-fork mods.json by `python -m crafting_system.data elevated` (src/crafting_system/data/elevated.py)"
        ),
        "repoe_version": repoe_version,
        "poec_data_sha256": poec_data_sha256,
        "elevated": mapping,
        "unresolved": unresolved,
    }


def _narrow(mods: Mapping[str, Any], found: list[str], level: int, signature: Signature) -> list[str]:
    """The mods of `found` with Craft of Exile's level and value ranges (all of them when none has)."""
    same = [m for m in found if mods[m]["required_level"] == level and _signature_of_stats(mods[m]) == signature]
    return same or found


def _find_ordinary(
    mods: Mapping[str, Any], on_tag: list[str], family: str, side: str, text: str, level: int, signature: Signature
) -> tuple[str | None, str]:
    """The export id of the top tier of the table's ordinary modifier, or None and the reason it cannot be told."""
    in_family = [m for m in on_tag if mods[m]["generation_type"] == side and family in mods[m]["groups"]]
    by_text = [m for m in in_family if template(mods[m]["text"] or "") == text]
    if by_text:
        best = max(mods[m]["required_level"] for m in by_text)
        tops = _narrow(mods, [m for m in by_text if mods[m]["required_level"] == best], level, signature)
    else:
        tops = [m for m in in_family if (mods[m]["required_level"], _signature_of_stats(mods[m])) == (level, signature)]
    if len(tops) == 1:
        return tops[0], ""
    return None, "no ordinary mod of the export has this text, level and values" if not tops else "several ordinary mods fit"


def _find_elevated(
    mods: Mapping[str, Any], on_tag: list[str], family: str, side: str, text: str, level: int, signature: Signature
) -> tuple[str | None, str]:
    """The export id of the Elevated mod of a table entry, or None and the reason it cannot be told."""
    in_family = [m for m in on_tag if mods[m]["generation_type"] == side and family in mods[m]["groups"]]
    found = [m for m in in_family if template(mods[m]["text"] or "") == text]
    if len(found) != 1:
        found = [m for m in (found or in_family) if (mods[m]["required_level"], _signature_of_stats(mods[m])) == (level, signature)]
    if len(found) != 1 and len(in_family) == 1:
        found = in_family
    if len(found) == 1:
        return found[0], ""
    return None, "no Elevated mod of the export fits" if not found else "several Elevated mods fit"


def render_elevated(document: Mapping[str, Any]) -> str:
    """The document as JSON with one pair and one unresolved entry per line, so that a change shows as a line in a diff."""
    lines = ["{"]
    for field in ("source", "repoe_version", "poec_data_sha256"):
        lines.append(f" {json.dumps(field)}: {json.dumps(document[field])},")
    pairs = ",\n".join(f"  {json.dumps(top)}: {json.dumps(elevated)}" for top, elevated in document["elevated"].items())
    lines += [' "elevated": {', pairs, " },"]
    rows = ",\n".join(f"  {json.dumps(row)}" for row in document["unresolved"])
    lines += [' "unresolved": [', rows, " ]", "}"]
    return "\n".join(lines) + "\n"
