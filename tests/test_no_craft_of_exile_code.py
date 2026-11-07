"""No Craft of Exile code in any tracked file (ticket #544).

This repo is public and Craft of Exile's code is not ours: it stays in the git-ignored local copy
(`.claude/scratch/coe/`). A docstring describes the calculator's behaviour in words and never quotes it.

The test reads every text file git tracks and looks for names that exist only inside Craft of Exile's code
(its calculator's variables) and for the shape of one of its statements. Two files are exempt:

* this file, which holds the names as strings;
* `tests/coe_oracle/coe_bridge.cjs`, our bridge, which hands two empty context keys to the kernel it loads from the local
  copy: there only those two names are allowed, each only in the form `name: {}`.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
THIS_FILE = "tests/test_no_craft_of_exile_code.py"
BRIDGE = "tests/coe_oracle/coe_bridge.cjs"
BRIDGE_KEYS = ("pavgaffs", "pavgcnts")

CRAFT_OF_EXILE_NAMES = ("pfWeightBOrd", "stweights", "affcnt", "pavgaffs", "pavgcnts")
NAME_PATTERN = re.compile("|".join(CRAFT_OF_EXILE_NAMES))
FRAGMENT_PATTERN = re.compile(r"\bcomputes\s*=\s*\{\s*prefix\b")  # the calculator's prefix/suffix statement
EMPTY_KEY_PATTERN = re.compile(r"\b(?:" + "|".join(BRIDGE_KEYS) + r")\s*:\s*\{\}")
BINARY_SUFFIXES = {".gz", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".woff", ".woff2", ".pdf", ".parquet", ".bin"}


def text_of(path: Path) -> str | None:
    """The text of a tracked file, or None for a binary one (a known suffix, a NUL byte or invalid UTF-8)."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return None
    raw = path.read_bytes()
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def tracked_texts() -> dict[str, str]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True
    ).stdout.decode("utf-8")
    texts = {}
    for name in filter(None, listing.split("\0")):
        path = REPO / name
        if path.is_file():  # a deleted-but-tracked file or a submodule has nothing to read
            text = text_of(path)
            if text is not None:
                texts[name] = text
    return texts


def offences(name: str, text: str) -> list[str]:
    """What is wrong in one file's text (the exemptions of the module docstring applied)."""
    if name == THIS_FILE:
        return []
    if name == BRIDGE:
        text = EMPTY_KEY_PATTERN.sub("", text)
    found = [f"line {number}: {match.group(0)}" for number, line in enumerate(text.splitlines(), 1) for match in NAME_PATTERN.finditer(line)]
    found += [f"line {number}: {match.group(0)}" for number, line in enumerate(text.splitlines(), 1) for match in FRAGMENT_PATTERN.finditer(line)]
    return found


def test_no_tracked_file_holds_craft_of_exile_code():
    bad = {name: found for name, text in tracked_texts().items() if (found := offences(name, text))}
    assert not bad, f"Craft of Exile identifiers or code in tracked files: {bad}"


def test_the_scan_sees_the_files_it_is_meant_to():
    texts = tracked_texts()
    assert BRIDGE in texts and "tests/test_proto_coe_comparison.py" in texts
    assert len(texts) > 100


@pytest.mark.parametrize("name", CRAFT_OF_EXILE_NAMES)
def test_each_name_is_caught_in_an_ordinary_file(name):
    assert offences("src/anything.py", f'"""it uses {name} to weigh"""\n')


def test_a_docstring_that_quotes_the_calculator_is_caught():
    """The wording the first version of the C02 docstring had: names inside prose and code spans."""
    for quote in (
        "from rounded average weights (`pavgaffs.prefix` over `pavgcnts.prefix`)",
        "removes them in order (`pfWeightBOrd`, sorted descending) from `stweights`",
        "the count in `affcnt`",
        "works each side out apart (computes = { prefix: one, suffix: two })",
    ):
        assert offences("tests/test_proto_coe_comparison.py", quote)


def test_the_bridge_may_give_only_the_two_empty_keys():
    assert not offences(BRIDGE, "    pavgaffs: {},\n    pavgcnts: {},\n")
    assert offences(BRIDGE, "    pavgaffs: {prefix: 3},\n")
    assert offences(BRIDGE, "    stweights: {},\n")
    assert offences(BRIDGE, "    x = pavgcnts.prefix;\n")
