from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from craftoracle.coe_metamods import CoEMetamodParseError, build_metamod_table, serialize_metamod_table


FIXTURE = """<!doctype html>
<div class="gen_msg"><div class="warning"></div> Warning:  source\n text </div>
<table class="mmode_none coe_tbl"><tbody>
<tr class="header"><td class="label">Crafting method</td><td>Prefix</td><td>Suffix</td><td>Attack</td><td>Caster</td></tr>
<tr><td class="label">Orb</td><td class="yes">&nbsp;</td><td class="no"><div class="note"> source note </div></td><td class="na">&nbsp;</td><td class="">&nbsp;</td></tr>
<tr class="group"><td colspan="5">Harvest</td></tr>
<tr><td class="label">Reroll</td><td class="yes">&nbsp;</td><td class="yes">&nbsp;</td><td class="yesno"><div class="note">note</div></td><td class="yesno">&nbsp;</td></tr>
</tbody></table>"""


def test_build_preserves_literal_cells_and_source_order() -> None:
    table = build_metamod_table(FIXTURE, "fixture.html")

    assert table["warning"] == "Warning: source text"
    assert table["columns"] == ["Prefix", "Suffix", "Attack", "Caster"]
    assert [group["heading"] for group in table["groups"]] == ["General", "Harvest"]
    assert table["groups"][0]["actions"][0] == {
        "label": "Orb",
        "source_line": 6,
        "cells": [
            {"status": "yes", "note": "", "source_line": 6},
            {"status": "no", "note": "source note", "source_line": 6},
            {"status": "na", "note": "", "source_line": 6},
            {"status": "", "note": "", "source_line": 6},
        ],
    }
    assert table["groups"][1]["actions"][0]["cells"][2]["note"] == "note"


def test_note_stops_at_its_closing_div() -> None:
    source = FIXTURE.replace(
        '<div class="note"> source note </div>',
        '<div class="note"> source note </div> trailing text',
    )

    table = build_metamod_table(source, "fixture.html")

    assert table["groups"][0]["actions"][0]["cells"][1]["note"] == "source note"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (FIXTURE.replace("<td>Suffix</td>", "<td>Prefix</td>"), "missing/duplicate metamod columns"),
        (
            FIXTURE.replace(
                '<td class="na">&nbsp;</td><td class="">&nbsp;</td>',
                '<td class="">&nbsp;</td>',
                1,
            ),
            "action row.*expected five cells",
        ),
        (FIXTURE.replace('class="yes"', 'class="maybe"', 1), "unknown status"),
        (FIXTURE.replace('class="mmode_none coe_tbl"', 'class="coe_tbl"'), "missing metamod table"),
        (FIXTURE.replace("</table>", "</table><table class=\"mmode_none coe_tbl\"></table>"), "duplicate metamod table"),
        (FIXTURE.replace("Warning:  source\n text", "No warning"), "missing warning"),
    ],
)
def test_invalid_structure_fails_explicitly(source: str, message: str) -> None:
    with pytest.raises(CoEMetamodParseError, match=message):
        build_metamod_table(source, "fixture.html")


def test_builder_cli_outputs_independent_deterministic_bytes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "sources/raw/coe/metamods.html"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = [sys.executable, str(root / "tools/build_coe_metamods.py"), str(source)]

    subprocess.run([*command, str(first)], check=True)
    subprocess.run([*command, str(second)], check=True)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == serialize_metamod_table(
        build_metamod_table(source.read_bytes().decode("utf-8"), "sources/raw/coe/metamods.html")
    )


def test_committed_table_reproduces_s14_snapshot() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "sources/raw/coe/metamods.html").read_bytes().decode("utf-8")
    committed = json.loads((root / "data/rules/coe_metamods.json").read_text(encoding="utf-8"))
    rebuilt = build_metamod_table(source, "sources/raw/coe/metamods.html")

    assert committed == rebuilt
    assert committed["source"]["sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert committed["source"]["sha256"] == "979a268175e91f2a073545dd50df7ef62054cdb8382e06e36e92efb62f384aef"
    assert len(committed["columns"]) == 4
    assert sum(len(group["actions"]) for group in committed["groups"]) == 33
    cells = [cell for group in committed["groups"] for action in group["actions"] for cell in action["cells"]]
    assert len(cells) == 132
    assert sum(bool(cell["note"]) for cell in cells) == 33
    assert sum(cell["status"] == "" for cell in cells) == 2
    assert [(group["heading"], len(group["actions"])) for group in committed["groups"]] == [
        ("General", 16), ("Harvest", 10), ("Beastcrafting", 2), ("Scourge", 2), ("Eldritch", 3)
    ]

    groups = {group["heading"]: {action["label"]: action for action in group["actions"]} for group in committed["groups"]}
    assert [cell["status"] for cell in groups["Eldritch"]["Chaos Orb"]["cells"]] == ["no", "no", "", ""]
    fossils = groups["General"]["Fossils"]["cells"]
    essences = groups["General"]["Essences"]["cells"]
    assert [cell["status"] for cell in fossils] == ["no", "no", "na", "na"]
    assert [cell["note"] for cell in fossils] == ["Prevents usage"] * 4
    assert [cell["status"] for cell in essences] == ["no", "no", "na", "na"]
    assert [cell["note"] for cell in essences] == ["Prevents usage"] * 4
    for label in ("Reroll", "Reroll+"):
        cells = groups["Harvest"][label]["cells"]
        assert [cell["status"] for cell in cells] == ["yes", "yes", "yesno", "yesno"]
        assert [cell["note"] for cell in cells[2:]] == ["Only for the first added modifier"] * 2
    assert [cell["status"] for cell in groups["General"]["Veiled orb"]["cells"]] == ["yes", "yes", "no", "no"]
    assert groups["Beastcrafting"]["Suffix > Prefix"]["cells"][3]["note"] == "Will not protects attack mods from removal"
