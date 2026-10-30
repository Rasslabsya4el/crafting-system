"""The rules registry (ADR-0004): loading, provenance, validation, lookup and packaging."""

import datetime
import os
import re
import shutil
import subprocess
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

import crafting_system.rules
from crafting_system.rules import (
    RegistryError,
    Rule,
    SourceKind,
    UnknownRuleError,
    get_rule,
    load_registry,
)

SEEDS = {
    "affix_count.rare_reroll_ratio": SourceKind.WIKI,
    "affix_draw.family_exclusion": SourceKind.WIKI,
    "fossils.factor_stacking": SourceKind.OWNER,
}


def test_shipped_registry_holds_the_seed_rules():
    registry = load_registry()

    for rule_id, kind in SEEDS.items():
        assert registry[rule_id].source_kind is kind
    assert registry["affix_count.rare_reroll_ratio"].value == {4: 8, 5: 3, 6: 1}
    assert registry["affix_draw.family_exclusion"].value is None
    assert get_rule("affix_count.rare_reroll_ratio") == registry["affix_count.rare_reroll_ratio"]
    assert isinstance(get_rule("fossils.factor_stacking"), Rule)


# --- helpers: temporary claims folders -------------------------------------------------------

REQUIRED_FIELDS = (
    "id", "statement", "source_kind", "url", "quote", "patch_verified", "date_checked",
)  # fmt: skip

MISSING = object()


def valid_entry(**changes) -> dict:
    """A valid entry of family `fam`; a change whose value is `MISSING` removes that field."""
    entry = {
        "id": "fam.thing",
        "statement": "A thing happens.",
        "source_kind": "wiki",
        "url": "https://example.org/page",
        "quote": "A thing happens.",
        "patch_verified": "3.29.3.3",
        "date_checked": datetime.date(2026, 10, 30),
    }
    entry.update(changes)
    return {key: val for key, val in entry.items() if val is not MISSING}


def claims_dir(root: Path, files: dict[str, str | list[dict]]) -> Path:
    """Write a claims folder; a list of entries is dumped as YAML, a string is written as is."""
    folder = root / "claims"
    folder.mkdir()
    for name, content in files.items():
        if not isinstance(content, str):
            content = yaml.safe_dump({"rules": content}, sort_keys=False)
        (folder / name).write_text(content, encoding="utf-8")
    return folder


def load_entry(tmp_path: Path, **changes) -> Mapping[str, Rule]:
    return load_registry(claims_dir(tmp_path, {"fam.yaml": [valid_entry(**changes)]}))


# --- the happy path -----------------------------------------------------------------------


def test_a_minimal_valid_entry_loads_with_no_value(tmp_path):
    rule = load_entry(tmp_path)["fam.thing"]

    assert rule == Rule(
        id="fam.thing",
        statement="A thing happens.",
        source_kind=SourceKind.WIKI,
        url="https://example.org/page",
        quote="A thing happens.",
        patch_verified="3.29.3.3",
        date_checked=datetime.date(2026, 10, 30),
        value=None,
    )


@pytest.mark.parametrize(
    "value", [7, 0.5, "text", [1, 2, 3], {"a": {"b": [1, None]}}, {4: 8, 5: 3}, False]
)
def test_a_value_of_any_shape_is_kept_as_is(tmp_path, value):
    assert load_entry(tmp_path, value=value)["fam.thing"].value == value


def test_all_six_source_kinds_are_accepted(tmp_path):
    kinds = ["official", "wiki", "datamined", "experiment", "coe", "owner"]
    entries = [valid_entry(id=f"fam.k{i}", source_kind=kind) for i, kind in enumerate(kinds)]

    registry = load_registry(claims_dir(tmp_path, {"fam.yaml": entries}))

    assert [registry[f"fam.k{i}"].source_kind for i in range(6)] == [SourceKind(k) for k in kinds]


@pytest.mark.parametrize("patch", ["3.29.3", "3.29.3.3", "3.29.3.3a"])
def test_a_patch_with_three_or_four_parts_or_a_letter_suffix_is_accepted(tmp_path, patch):
    assert load_entry(tmp_path, patch_verified=patch)["fam.thing"].patch_verified == patch


def test_a_quote_of_exactly_400_characters_is_accepted(tmp_path):
    assert len(load_entry(tmp_path, quote="q" * 400)["fam.thing"].quote) == 400


def test_the_registry_reads_files_in_sorted_order_and_is_read_only(tmp_path):
    folder = claims_dir(
        tmp_path,
        {
            "beta.yaml": [valid_entry(id="beta.one")],
            "alpha.yaml": [valid_entry(id="alpha.one"), valid_entry(id="alpha.two")],
        },
    )

    registry = load_registry(folder)

    assert list(registry) == ["alpha.one", "alpha.two", "beta.one"]
    with pytest.raises(TypeError):
        registry["new.rule"] = registry["alpha.one"]  # type: ignore[index]


# --- provenance: an entry without a field is an error -------------------------------------------


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_an_entry_missing_a_provenance_field_is_rejected(tmp_path, field):
    folder = claims_dir(tmp_path, {"fam.yaml": [valid_entry(**{field: MISSING})]})

    with pytest.raises(RegistryError) as raised:
        load_registry(folder)

    message = str(raised.value)
    assert field in message
    assert "fam.yaml" in message
    if field != "id":
        assert "fam.thing" in message


def test_every_shipped_rule_has_all_fields_filled_and_valid():
    registry = load_registry()

    assert registry
    for rule_id, rule in registry.items():
        assert rule.id == rule_id
        assert re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", rule.id)
        assert rule.statement.strip()
        assert rule.quote.strip()
        assert len(rule.quote) <= 400
        assert isinstance(rule.source_kind, SourceKind)
        assert rule.url.startswith(("https://", "http://"))
        assert re.fullmatch(r"\d+(\.\d+){2,3}[a-z]?", rule.patch_verified)
        assert type(rule.date_checked) is datetime.date


# --- validation: each rule has a failing case ---------------------------------------------------

BAD_VALUES = [
    ("id", "Fam.thing"),
    ("id", "fam.Thing"),
    ("id", "fam"),
    ("id", "fam.thing.extra"),
    ("id", "fam.1thing"),
    ("id", "fam.thing-x"),
    ("id", ".thing"),
    ("id", 5),
    ("id", "other.thing"),  # the family must equal the file name stem
    ("statement", ""),
    ("statement", "   "),
    ("statement", 5),
    ("quote", ""),
    ("quote", "  "),
    ("quote", "q" * 401),
    ("quote", ["a"]),
    ("source_kind", "reddit"),
    ("source_kind", "Wiki"),
    ("source_kind", 5),
    ("url", "poewiki.net/wiki/Chaos_Orb"),
    ("url", "ftp://example.org/x"),
    ("url", ""),
    ("url", 5),
    ("patch_verified", 3.29),  # unquoted in YAML: a float
    ("patch_verified", "3.29"),
    ("patch_verified", "latest"),
    ("patch_verified", "3.29.3.3.1"),
    ("patch_verified", "3.29.3.3A"),
    ("date_checked", "2026-10-30"),  # quoted in YAML: a string
    ("date_checked", datetime.datetime(2026, 10, 30, 12, 0)),
    ("date_checked", 20261030),
    ("date_checked", None),
]


@pytest.mark.parametrize(("field", "bad"), BAD_VALUES)
def test_a_bad_field_value_is_rejected_naming_file_entry_and_field(tmp_path, field, bad):
    folder = claims_dir(tmp_path, {"fam.yaml": [valid_entry(**{field: bad})]})

    with pytest.raises(RegistryError) as raised:
        load_registry(folder)

    message = str(raised.value)
    assert "fam.yaml" in message
    assert field in message
    if field != "id":
        assert "fam.thing" in message
    assert str(tmp_path) not in message  # the file name, not the full path


def test_a_float_patch_tells_the_author_to_quote_it(tmp_path):
    with pytest.raises(RegistryError, match="quote"):
        load_entry(tmp_path, patch_verified=3.29)


def test_a_string_date_tells_the_author_to_leave_it_unquoted(tmp_path):
    with pytest.raises(RegistryError, match="unquoted YYYY-MM-DD"):
        load_entry(tmp_path, date_checked="2026-10-30")


def test_an_id_that_belongs_to_another_file_is_rejected(tmp_path):
    # Ids start with the file's stem, so two files can never legitimately share an id: the
    # second one to claim it breaks the family rule.
    folder = claims_dir(
        tmp_path,
        {
            "alpha.yaml": [valid_entry(id="alpha.same")],
            "beta.yaml": [valid_entry(id="alpha.same")],
        },
    )

    with pytest.raises(RegistryError, match=r"beta\.yaml.*alpha\.same"):
        load_registry(folder)


def test_a_duplicate_id_inside_one_file_is_rejected(tmp_path):
    folder = claims_dir(
        tmp_path, {"fam.yaml": [valid_entry(), valid_entry(statement="Another statement.")]}
    )

    with pytest.raises(RegistryError, match=r"fam\.yaml.*fam\.thing.*duplicate"):
        load_registry(folder)


def test_an_unknown_key_is_rejected(tmp_path):
    folder = claims_dir(tmp_path, {"fam.yaml": [valid_entry(confidence="high")]})

    with pytest.raises(RegistryError, match="confidence") as raised:
        load_registry(folder)

    assert "fam.yaml" in str(raised.value)
    assert "fam.thing" in str(raised.value)


FILE_LEVEL_CASES = {
    "invalid YAML": "rules: [unclosed\n",
    "no rules key": "other: []\n",
    "empty file": "",
    "rules is null": "rules:\n",
    "rules is empty": "rules: []\n",
    "rules is not a list": "rules: {id: fam.thing}\n",
    "entry is not a mapping": "rules:\n  - just a string\n",
    "extra top-level key": "rules:\n  - {}\nextra: 1\n",
    "top level is a list": "- a\n- b\n",
}


@pytest.mark.parametrize("text", FILE_LEVEL_CASES.values(), ids=FILE_LEVEL_CASES.keys())
def test_a_malformed_claims_file_is_rejected_naming_the_file(tmp_path, text):
    folder = claims_dir(tmp_path, {"fam.yaml": text})

    with pytest.raises(RegistryError, match=r"fam\.yaml"):
        load_registry(folder)


def test_an_empty_claims_folder_is_rejected(tmp_path):
    folder = claims_dir(tmp_path, {})

    with pytest.raises(RegistryError, match=r"no \.yaml"):
        load_registry(folder)


@pytest.mark.parametrize("stray", ["fam.yml", "notes.txt", "README.md", "fam.yaml.bak"])
def test_a_stray_file_next_to_the_claims_is_rejected(tmp_path, stray):
    folder = claims_dir(tmp_path, {"fam.yaml": [valid_entry()]})
    (folder / stray).write_text("rules: []\n", encoding="utf-8")

    with pytest.raises(RegistryError, match=re.escape(stray)):
        load_registry(folder)


def test_a_missing_claims_folder_is_rejected(tmp_path):
    with pytest.raises(RegistryError):
        load_registry(tmp_path / "nowhere")


def test_a_non_utf8_file_is_rejected_naming_the_file(tmp_path):
    folder = claims_dir(tmp_path, {})
    (folder / "fam.yaml").write_bytes(b"rules: \xff\xfe\n")

    with pytest.raises(RegistryError, match=r"fam\.yaml"):
        load_registry(folder)


# --- lookup by id -----------------------------------------------------------------------------


def test_an_unknown_rule_id_raises_an_error_naming_the_id():
    with pytest.raises(UnknownRuleError, match=r"nothing\.here") as raised:
        get_rule("nothing.here")

    assert isinstance(raised.value, KeyError)


def test_the_default_registry_is_loaded_once():
    assert get_rule("fossils.factor_stacking") is get_rule("fossils.factor_stacking")


# --- packaging: the claims ship with the package -------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_IN_WHEEL = "crafting_system/rules/claims/"


def find_uv() -> str:
    """The uv that is running the tests (`uv run` sets `UV`), else one on PATH."""
    found = os.environ.get("UV") or shutil.which("uv")
    if found:
        return found
    message = "uv was not found (no UV variable, not on PATH), so the wheel cannot be built"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("wheel")
    result = subprocess.run(
        [find_uv(), "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"uv build failed:\n{result.stdout}\n{result.stderr}"
    built = list(out_dir.glob("*.whl"))
    assert len(built) == 1
    return built[0]


def test_every_claims_file_ships_in_the_wheel(wheel):
    source_claims = Path(crafting_system.rules.__file__).parent / "claims"
    expected = {f"{CLAIMS_IN_WHEEL}{path.name}" for path in source_claims.glob("*.yaml")}

    with zipfile.ZipFile(wheel) as archive:
        shipped = {
            name
            for name in archive.namelist()
            if name.startswith(CLAIMS_IN_WHEEL) and not name.endswith("/")
        }

    assert expected
    assert shipped == expected


def test_the_registry_loads_from_the_claims_inside_the_wheel(wheel, tmp_path):
    with zipfile.ZipFile(wheel) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.startswith(CLAIMS_IN_WHEEL) and not name.endswith("/")
        ]
        archive.extractall(tmp_path, members)

    from_wheel = load_registry(tmp_path / "crafting_system" / "rules" / "claims")

    assert from_wheel == load_registry()
