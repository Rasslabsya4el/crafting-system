"""Rebuild `corrupted_pools.json` next to this file from the local copy of Craft of Exile (ticket #256, ADR-0003).

Usage: python -I make_corrupted_pools.py <folder with Craft of Exile's poec_data.json> [<output file>]

The output file defaults to `corrupted_pools.json` beside this script. It keeps, for the three item classes
whose corrupted implicit pools are compared mod by mod (ring, amulet, belt), every tier of every corrupted
modifier that Craft of Exile lists for the class: its group, name, item level, weight and value ranges, read
from the `modifiers`, `basemods` and `tiers` tables. That is a table of numbers (facts of the game), not the
site's data file, which stays git-ignored third-party data.

This file is a script, not a test: pytest does not collect it (its name has no `test_` prefix).
"""

import hashlib
import json
import sys
from pathlib import Path

CLASSES = {"Ring": "1", "Amulet": "2", "Belt": "3"}  # Craft of Exile's base ids
CORRUPTED_AFFIX = "corrupted"


def main() -> None:
    folder = Path(sys.argv[1])
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "corrupted_pools.json"
    raw = (folder / "poec_data.json").read_bytes()
    text = raw.decode("utf-8")
    data = json.loads(text[text.index("=") + 1 :].rstrip().rstrip(";"))
    modifiers = {entry["id_modifier"]: entry for entry in data["modifiers"]["seq"]}
    classes = {}
    for name, base in CLASSES.items():
        rows = []
        for modifier_id in data["basemods"][base]:
            modifier = modifiers[modifier_id]
            if modifier["affix"] != CORRUPTED_AFFIX:
                continue
            for tier in data["tiers"][modifier_id][base]:
                rows.append(
                    {
                        "modifier": int(modifier_id),
                        "group": modifier["modgroup"],
                        "name": modifier["name_modifier"],
                        "ilvl": int(tier["ilvl"]),
                        "weight": int(tier["weighting"]),
                        "values": json.loads(tier["nvalues"]),
                    }
                )
        classes[name] = rows
    document = {
        "source": "Craft of Exile poec_data.json, tables modifiers, basemods and tiers, affix 'corrupted'",
        "poec_data_sha256": hashlib.sha256(raw).hexdigest(),
        "classes": classes,
    }
    output.write_text(one_row_per_line(document), encoding="utf-8")


def one_row_per_line(document: dict) -> str:
    """The document as JSON with each tier on one line, so that a change shows as a line in a diff."""
    lines = [
        "{",
        f' "source": {json.dumps(document["source"])},',
        f' "poec_data_sha256": {json.dumps(document["poec_data_sha256"])},',
        ' "classes": {',
    ]
    names = list(document["classes"])
    for number, name in enumerate(names):
        rows = "\n".join(f"   {json.dumps(row)}," for row in document["classes"][name]).rstrip(",")
        lines += [f"  {json.dumps(name)}: [", rows, "  ]" + ("," if number < len(names) - 1 else "")]
    lines += [" }", "}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
