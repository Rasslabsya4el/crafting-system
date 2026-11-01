"""The Elevated mapping step of the data layer (ticket #154): Craft of Exile's table read against the export, on a toy of both.

The toy has one influence (Shaper), one base group (helmets) and four table entries, one for each way the step reads an entry:
by the text of the mods, by their level and value ranges when the wording changed between the patches, by the one Elevated mod of the
family, and not at all (no Elevated mod in the export, a modifier the table dropped).
"""

import json

import pytest
from repoe_support import no_network  # noqa: F401

from crafting_system.data.elevated import (
    ElevatedError,
    ElevatedMods,
    build_elevated,
    is_elevated,
    load_elevated,
    parse_poec_data,
    render_elevated,
    template,
)
from crafting_system.data.model import Mod


def raw_mod(name, family, side, level, ranges, text, tag="helmet_shaper", weight=300):
    return {
        "domain": "item",
        "generation_type": side,
        "groups": [family],
        "name": name,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": weight}, {"tag": "default", "weight": 0}],
        "stats": [{"id": f"stat{n}", "min": low, "max": high} for n, (low, high) in enumerate(ranges)],
        "text": text,
    }


MODS = {
    # family A: text unchanged
    "A1": raw_mod("Shaper's", "FamA", "prefix", 68, [(1, 1)], "+1 to Level of Gems"),
    "A2": raw_mod("Shaper's", "FamA", "prefix", 80, [(2, 2)], "+2 to Level of Gems"),
    "A_MAVEN": raw_mod("Elevated Shaper's", "FamA", "prefix", 90, [(3, 3), (10, 5)], "+3 to Level of Gems\n+(5-10)% Quality", weight=0),
    # family B: the wording of the export differs from the table's, the level and the ranges do not
    "B1": raw_mod("of Shaping", "FamB", "suffix", 75, [(4, 6)], "Rewritten wording of (4-6)% B"),
    "B_MAVEN": raw_mod("of Elevated Shaping", "FamB", "suffix", 90, [(7, 9), (1, 2)], "Other rewritten wording (7-9)%, (1-2)%", weight=0),
    "B_MAVEN_2": raw_mod("of Elevated Shaping", "FamB", "suffix", 85, [(1, 1)], "Something else", weight=0),
    # family C: no Elevated mod in the export
    "C1": raw_mod("Shaper's", "FamC", "prefix", 70, [(5, 5)], "C is # more"),
    # family D: one Elevated mod, wording and ranges both changed
    "D1": raw_mod("of Shaping", "FamD", "suffix", 70, [(5, 5)], "D is # better"),
    "D_MAVEN": raw_mod("of Elevated Shaping", "FamD", "suffix", 95, [(8, 8)], "Elevated D", weight=0),
    # not an item mod: ignored
    "MAP": {**raw_mod("Elevated Map", "FamA", "prefix", 1, [], ""), "domain": "area"},
}


def entry(name, level, nvalues):
    return {"oname": name, "ilvl": str(level), "nvalues": nvalues}


COE = {
    "mgroups": {"seq": [{"id_mgroup": "1", "is_influence": "0", "poedb_id": None}, {"id_mgroup": "2", "is_influence": "1", "poedb_id": "shaper"}]},
    "bases": {"seq": [{"id_base": "52", "id_bgroup": "4"}, {"id_base": "53", "id_bgroup": "4"}, {"id_base": "7", "id_bgroup": "9"}]},
    "modifiers": {
        "seq": [
            {"id_modifier": str(n), "id_mgroup": "2", "modgroup": family, "affix": side, "name_modifier": text}
            for n, family, side, text in (
                (10, "FamA", "prefix", "+# to Level of Gems"),
                (11, "FamB", "suffix", "#% B"),
                (12, "FamC", "prefix", "C is # more"),
                (13, "FamD", "suffix", "D is # better"),
            )
        ]
    },
    "tiers": {
        "10": {"52": [{"ilvl": "68", "nvalues": "[1]"}, {"ilvl": "80", "nvalues": "[2]"}]},
        "11": {"52": [{"ilvl": "75", "nvalues": "[[4,6]]"}]},
        "12": {"52": [{"ilvl": "70", "nvalues": "[5]"}]},
        "13": {"52": [{"ilvl": "70", "nvalues": "[5]"}]},
    },
    "maeven": {
        "bmods": {"52-10": "1", "53-10": "1", "52-11": "2", "52-12": "3", "52-13": "4", "52-99": "5", "7-10": "1"},
        "ind": {
            "1": entry("+# to Level of Gems, +#% Quality", 90, "[3,[5,10]]"),
            "2": entry("Not the export's words", 90, "[[7,9],[1,2]]"),
            "3": entry("Nothing like it", 99, "[1]"),
            "4": entry("Different again", 1, "[0]"),
            "5": entry("gone", 1, "[0]"),
        },
    },
}


@pytest.fixture(scope="module")
def document():
    return build_elevated(COE, MODS, repoe_version="9.9.9.9", poec_data_sha256="ab" * 32)


def test_the_text_with_its_numbers_blanked_is_what_two_patches_share():
    assert template("+(8-12) to maximum Life") == template("+# to maximum Life") == "# to maximum life"
    assert template("(5-3)% reduced Damage\n+2.5 Mana") == "#% reduced damage, # mana"
    assert template("Socketed Gems are Supported by Level 25 Concentrated Effect") == "socketed gems are supported by level # concentrated effect"


def test_a_table_entry_is_read_by_text_by_level_and_ranges_or_by_the_one_elevated_mod_of_the_family(document):
    assert document["elevated"] == {"A2": "A_MAVEN", "B1": "B_MAVEN", "D1": "D_MAVEN"}  # the top tier of each family, not A1


def test_what_the_step_cannot_link_is_kept_with_its_reason_and_the_number_of_table_keys(document):
    by_text = {(row["family"] or row["text"]): row for row in document["unresolved"]}
    assert by_text["FamC"]["reason"] == "no Elevated mod of the export fits" and by_text["FamC"]["entries"] == 1
    assert by_text["52-99"]["reason"].startswith("the table names a modifier or a base the step does not read")
    assert by_text["7-10"]["entries"] == 1  # the base group 9 is no armour group
    assert {row["tag"] for row in document["unresolved"] if row["family"]} == {"helmet_shaper"}


def test_two_bases_of_one_group_say_the_same_thing_once(document):
    assert list(document["elevated"]).count("A2") == 1  # the keys 52-10 and 53-10 link one pair


def test_an_elevated_mod_is_told_by_its_name():
    mod = Mod("x", "Elevated Shaper's", None, "t", ("f",), "item", "prefix", 90, (), (), (), (), (), False)
    assert is_elevated(mod) and not is_elevated(Mod("y", "Shaper's", None, "t", ("f",), "item", "prefix", 68, (), (), (), (), (), False))


def test_the_written_file_loads_back_and_holds_for_its_own_export_only(document, tmp_path):
    path = tmp_path / "elevated.json"
    path.write_text(render_elevated(document), encoding="utf-8", newline="\n")
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(document))
    loaded = load_elevated(path)
    assert loaded.of_top_tier == document["elevated"] and loaded.repoe_version == "9.9.9.9"
    assert len(loaded.unresolved) == len(document["unresolved"])

    class Data:
        version = "9.9.9.9"

    class Other:
        version = "3.29.3.3"

    assert loaded.for_data(Data()) == document["elevated"]  # type: ignore[arg-type]
    assert loaded.for_data(Other()) == {}  # type: ignore[arg-type]
    assert isinstance(loaded, ElevatedMods)


def test_a_malformed_file_or_table_is_refused_with_a_clear_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"repoe_version": "1"}', encoding="utf-8")
    with pytest.raises(ElevatedError):
        load_elevated(bad)
    with pytest.raises(ElevatedError):
        load_elevated(tmp_path / "missing.json")
    with pytest.raises(ElevatedError, match="lacks the table"):
        build_elevated({}, MODS, repoe_version="1", poec_data_sha256="0")
    with pytest.raises(ElevatedError):
        parse_poec_data("not a javascript assignment")


def test_the_file_is_read_from_a_javascript_assignment():
    assert parse_poec_data('poecd={"a": 1};\n') == {"a": 1}


# --- the command ----------------------------------------------------------------------------------------------------------


def test_the_elevated_command_writes_the_file_from_a_folder_of_craft_of_exile_and_the_cached_export(tmp_path, monkeypatch, capsys):
    from repoe_support import fixture_pin_and_opener

    from crafting_system.data.__main__ import main

    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "cache"))
    pin, opener = fixture_pin_and_opener()
    main(["fetch"], pin=pin, open_url=opener)
    capsys.readouterr()
    folder = tmp_path / "coe"
    folder.mkdir()
    (folder / "poec_data.json").write_text("poecd=" + json.dumps(COE) + ";", encoding="utf-8")
    output = tmp_path / "elevated.json"

    code = main(["elevated", str(folder), "--output", str(output)], pin=pin, open_url=opener)

    assert code == 0 and "top-tier mods linked" in capsys.readouterr().out
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["repoe_version"] == pin.version and written["elevated"] == {}  # the fixture excerpt holds no such mods
    assert len(written["poec_data_sha256"]) == 64 and b"\r" not in output.read_bytes()


def test_the_elevated_command_names_a_folder_without_the_file(tmp_path, capsys):
    from crafting_system.data.__main__ import main

    assert main(["elevated", str(tmp_path)]) == 1
    assert "cannot read poec_data.json" in capsys.readouterr().err
