"""A claim's `history` (what it said before a patch changed it) and `rules stale` (ticket #120)."""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from crafting_system.data import PIN_FILE, load_pin
from crafting_system.rules import HistoryEntry, RegistryError, SourceKind, load_registry
from crafting_system.rules.__main__ import main
from crafting_system.rules.registry import patch_order_key
from crafting_system.rules.stale import stale_rules

HISTORY_ENTRY = {
    "statement": "A thing used to happen twice.",
    "value": {"times": 2},
    "held_until": "3.29.0.2",
    "source_kind": "official",
    "url": "https://example.org/notes",
    "quote": "A thing now happens once.",
}

CLAIM_HEAD = """rules:
  - id: fam.thing
    statement: A thing happens.
    source_kind: wiki
    url: https://example.org/page
    quote: A thing happens.
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-30
"""


def claims_folder(root: Path, text: str, name: str = "fam.yaml") -> Path:
    folder = root / "claims"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    return folder


def with_history(*entries: dict, head: str = CLAIM_HEAD) -> str:
    return head + "    history:\n" + "".join(
        "      - " + yaml.safe_dump(entry, sort_keys=False).replace("\n", "\n        ").rstrip() + "\n"
        for entry in entries
    )


# --- Done when 1: a claim loads with a history entry, a malformed one is refused with file and line


def test_a_claim_with_a_history_entry_loads(tmp_path):
    rule = load_registry(claims_folder(tmp_path, with_history(HISTORY_ENTRY)))["fam.thing"]

    assert rule.history == (
        HistoryEntry(
            held_until="3.29.0.2",
            source_kind=SourceKind.OFFICIAL,
            url="https://example.org/notes",
            quote="A thing now happens once.",
            statement="A thing used to happen twice.",
            value=rule.history[0].value,
        ),
    )
    assert dict(rule.history[0].value) == {"times": 2}
    assert hash(rule) == hash(rule)  # the history is frozen like the value


def test_a_claim_without_history_has_an_empty_one(tmp_path):
    rule = load_registry(claims_folder(tmp_path, CLAIM_HEAD))["fam.thing"]

    assert rule.history == ()


def test_the_old_value_alone_or_the_old_text_alone_is_enough(tmp_path):
    only_text = {k: v for k, v in HISTORY_ENTRY.items() if k != "value"}
    only_value = {k: v for k, v in HISTORY_ENTRY.items() if k != "statement"}

    rule = load_registry(claims_folder(tmp_path, with_history(only_value, {**only_text, "held_until": "3.29.1.1"})))[
        "fam.thing"
    ]

    assert [(h.statement, h.value is None) for h in rule.history] == [
        (None, False),
        ("A thing used to happen twice.", True),
    ]


def test_a_history_does_not_change_the_value_code_reads(tmp_path):
    text = with_history(HISTORY_ENTRY) + "    value: {times: 1}\n"

    rule = load_registry(claims_folder(tmp_path, text))["fam.thing"]

    assert dict(rule.value) == {"times": 1}


MALFORMED = {
    "no old text or value": (
        {k: v for k, v in HISTORY_ENTRY.items() if k not in ("statement", "value")},
        "give the old statement or the old value",
    ),
    "missing held_until": ({k: v for k, v in HISTORY_ENTRY.items() if k != "held_until"}, "missing required field held_until"),
    "missing url": ({k: v for k, v in HISTORY_ENTRY.items() if k != "url"}, "missing required field url"),
    "missing quote": ({k: v for k, v in HISTORY_ENTRY.items() if k != "quote"}, "missing required field quote"),
    "missing source_kind": (
        {k: v for k, v in HISTORY_ENTRY.items() if k != "source_kind"},
        "missing required field source_kind",
    ),
    "only a null value": ({k: v for k, v in HISTORY_ENTRY.items() if k != "statement"} | {"value": None}, "give the old statement or the old value"),
    "unknown key": ({**HISTORY_ENTRY, "note": "x"}, "unknown key note"),
    "bad patch": ({**HISTORY_ENTRY, "held_until": "latest"}, "held_until must be a quoted patch"),
    "unquoted patch": ({**HISTORY_ENTRY, "held_until": 3.29}, "held_until 3.29 was read as a number"),
    "bad source kind": ({**HISTORY_ENTRY, "source_kind": "rumour"}, "source_kind must be one of"),
    "bad url": ({**HISTORY_ENTRY, "url": "not a url"}, "url must start with https://"),
    "empty quote": ({**HISTORY_ENTRY, "quote": " "}, "quote must be a non-empty string"),
    "long quote": ({**HISTORY_ENTRY, "quote": "x" * 401}, "at most 400 characters"),
    "empty statement": ({**HISTORY_ENTRY, "statement": ""}, "statement must be a non-empty string"),
    "held until after the claim's patch": ({**HISTORY_ENTRY, "held_until": "3.30.0.1"}, "must not be later than the claim's patch_verified"),
}


def test_a_claim_rewritten_on_the_patch_it_was_verified_on_may_hold_its_old_text_until_that_patch(tmp_path):
    """A design change (ticket #274: B5 turned 'items carry no strands' into 'only when the query says so') rewrites a claim
    without a patch behind it, so the old text held until the patch the new one is verified on."""
    rule = load_registry(claims_folder(tmp_path, with_history({**HISTORY_ENTRY, "held_until": "3.29.3.3"})))["fam.thing"]

    assert [h.held_until for h in rule.history] == ["3.29.3.3"]
    assert rule.patch_verified == "3.29.3.3"


@pytest.mark.parametrize("entry, problem", MALFORMED.values(), ids=MALFORMED)
def test_a_malformed_history_entry_is_refused_with_file_claim_and_line(tmp_path, entry, problem):
    text = with_history(entry)
    folder = claims_folder(tmp_path, text)

    with pytest.raises(RegistryError, match=re.escape(problem)) as raised:
        load_registry(folder)

    message = str(raised.value)
    assert message.startswith("fam.yaml: rule fam.thing: history entry #1")
    line = int(re.search(r"\(line (\d+)\)", message).group(1))
    assert 1 <= line <= len(text.splitlines())


@pytest.mark.parametrize("field, bad", [("url", "nope"), ("held_until", "3.30.0.1"), ("source_kind", "rumour")])
def test_the_line_of_a_problem_is_the_line_of_the_field(tmp_path, field, bad):
    text = with_history({**HISTORY_ENTRY, field: bad})
    folder = claims_folder(tmp_path, text)

    with pytest.raises(RegistryError) as raised:
        load_registry(folder)

    line = int(re.search(r"\(line (\d+)\)", str(raised.value)).group(1))
    assert text.splitlines()[line - 1].split(":")[0].strip() == field


def test_history_that_is_not_a_list_of_mappings_is_refused(tmp_path):
    for body, problem in (
        ("    history: oops\n", "history must be a non-empty list"),
        ("    history: []\n", "history must be a non-empty list"),
        ("    history:\n      - just text\n", "a history entry must be a mapping"),
    ):
        folder = claims_folder(tmp_path, CLAIM_HEAD + body)
        with pytest.raises(RegistryError, match=problem) as raised:
            load_registry(folder)
        assert "fam.yaml: rule fam.thing: history" in str(raised.value)
        assert re.search(r"\(line \d+\)", str(raised.value))


def test_a_history_that_is_not_a_list_names_the_line_of_the_history_key(tmp_path):
    folder = claims_folder(tmp_path, CLAIM_HEAD + "    history: oops\n")

    with pytest.raises(RegistryError, match=r"history \(line 9\)"):
        load_registry(folder)


def test_history_must_be_listed_oldest_first_and_strictly(tmp_path):
    older = {**HISTORY_ENTRY, "held_until": "3.28.0.1"}
    for first, second in ((HISTORY_ENTRY, older), (HISTORY_ENTRY, HISTORY_ENTRY)):
        folder = claims_folder(tmp_path, with_history(first, second))
        with pytest.raises(RegistryError, match=r"history entry #2 \(line \d+\): held_until .* must be later than"):
            load_registry(folder)

    rule = load_registry(claims_folder(tmp_path, with_history(older, HISTORY_ENTRY)))["fam.thing"]
    assert [h.held_until for h in rule.history] == ["3.28.0.1", "3.29.0.2"]


def test_a_repeated_key_in_a_history_entry_is_refused_with_its_line(tmp_path):
    text = with_history(HISTORY_ENTRY) + "        url: https://example.org/again\n"
    folder = claims_folder(tmp_path, text)

    with pytest.raises(RegistryError, match=r"(?s)fam\.yaml.*duplicate key 'url'.*line 17"):
        load_registry(folder)


def test_patch_names_sort_as_patches():
    names = ["3.29.3a", "3.9.0", "3.29.3", "3.29.3.0", "3.29.10", "3.29.3.3", "3.29.3.3a"]

    ordered = sorted(names, key=patch_order_key)

    assert ordered == ["3.9.0", "3.29.3", "3.29.3.0", "3.29.3a", "3.29.3.3", "3.29.3.3a", "3.29.10"]
    assert patch_order_key("3.29.3") == patch_order_key("3.29.3.0")


# --- Done when 2: `rules stale` lists exactly the claims verified on an older patch -------------


def stale_claims(root: Path) -> Path:
    entries = [
        ("older", "3.28.0.1"),
        ("oldest", "3.9.0"),
        ("same", "3.29.4.1"),
        ("newer", "3.30.0.1"),
        ("last_hotfix", "3.29.4.0"),
        ("letter", "3.29.4.1a"),
    ]
    rules = [
        {
            "id": f"fam.{name}",
            "statement": f"The {name} thing.",
            "source_kind": "wiki",
            "url": f"https://example.org/{name}",
            "quote": "q",
            "patch_verified": patch,
            "date_checked": datetime.date(2026, 10, 30),
        }
        for name, patch in entries
    ]
    return claims_folder(root, yaml.safe_dump({"rules": rules}, sort_keys=False))


def pin_file(root: Path, version: str) -> Path:
    document = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    document["version"] = version
    path = root / "PIN.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_stale_lists_exactly_the_claims_verified_before_the_pinned_patch(tmp_path, capsys):
    claims = stale_claims(tmp_path)
    pin = pin_file(tmp_path, "3.29.4.1")

    assert [r.id for r in stale_rules(load_registry(claims), "3.29.4.1")] == [
        "fam.older",
        "fam.oldest",
        "fam.last_hotfix",
    ]
    assert main(["stale", "--claims", str(claims), "--pin-file", str(pin)]) == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "3 of 6 claims were last verified before 3.29.4.1:"
    assert [line.split()[0] for line in out[1:]] == ["fam.older", "fam.oldest", "fam.last_hotfix"]
    assert "3.28.0.1" in out[1] and "wiki" in out[1] and "https://example.org/older" in out[1]


def test_pinning_a_newer_patch_makes_more_claims_stale(tmp_path, capsys):
    claims = stale_claims(tmp_path)

    assert main(["stale", "--claims", str(claims), "--pin-file", str(pin_file(tmp_path, "3.31.0.1"))]) == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "6 of 6 claims were last verified before 3.31.0.1:"
    assert len(out) == 7


def test_stale_says_so_when_every_claim_is_current(tmp_path, capsys):
    claims = stale_claims(tmp_path)

    assert main(["stale", "--claims", str(claims), "--pin-file", str(pin_file(tmp_path, "3.9.0"))]) == 0

    assert capsys.readouterr().out.strip() == "All 6 claims were verified on 3.9.0 or later."


def test_stale_reads_the_pin_file_of_the_checkout_by_default(capsys):
    assert main(["stale"]) == 0

    registry = load_registry()
    pinned = load_pin().version
    stale = [r.id for r in registry.values() if patch_order_key(r.patch_verified) < patch_order_key(pinned)]
    out = capsys.readouterr().out.splitlines()
    assert pinned in out[0] and str(len(registry)) in out[0]
    assert [line.split()[0] for line in out[1:]] == stale


def test_stale_with_a_broken_pin_file_or_claims_is_an_error_not_a_traceback(tmp_path, capsys):
    claims = stale_claims(tmp_path)
    broken = tmp_path / "PIN.json"
    broken.write_text("{not json", encoding="utf-8")

    assert main(["stale", "--claims", str(claims), "--pin-file", str(broken)]) == 1
    assert "error:" in capsys.readouterr().err
    assert main(["stale", "--claims", str(tmp_path / "missing"), "--pin-file", str(pin_file(tmp_path, "3.29.4.1"))]) == 1
    assert "error:" in capsys.readouterr().err


def test_a_command_is_required(capsys):
    assert main([]) == 2


def test_the_module_runs_as_python_dash_m(tmp_path):
    claims = stale_claims(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "crafting_system.rules", "stale", "--claims", str(claims), "--pin-file", str(pin_file(tmp_path, "3.29.4.1"))],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("3 of 6 claims were last verified before 3.29.4.1:")


def test_stale_never_changes_the_claims_folder(tmp_path):
    claims = stale_claims(tmp_path)
    before = {p.name: p.read_bytes() for p in claims.iterdir()}

    main(["stale", "--claims", str(claims), "--pin-file", str(pin_file(tmp_path, "3.31.0.1"))])

    assert {p.name: p.read_bytes() for p in claims.iterdir()} == before
