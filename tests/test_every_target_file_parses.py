"""Every target file in the repo is read by the target loader, so none can silently stop loading (#545).

A target file is any `.yaml` with a top-level `requirements:` key: `examples/targets/`, the research targets (`research/`,
`docs/research/`) and the target fixtures under `tests/fixtures/`. The heavy runs and the research scripts read some of them raw, where a
required key that went missing would be seen only on a runner, so a quick test parses each one here.

Two things are allowed for, and named:

* The research files of the strand routes and two older ones still carry `start_price:` (they predate #474 and #505) and the strand words
  (`memory_strands`, the strand action kinds); they are read as today's loaders read them (`without_strand_words`, as the heavy test does).
* `tests/fixtures/impact_repo/` holds text fixtures for the impact scanner, with line numbers pinned and a base of the seeded second version
  of the data; nothing loads them as targets.
"""

import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from targets_support import DATA as FIXTURE_DATA
from test_strand_routes import without_strand_words

from crafting_system.targets import parse_target

ROOT = Path(__file__).resolve().parents[1]
SKIPPED_FOLDERS = {".git", ".claude", "local", "node_modules", ".venv", "__pycache__"}
TEXT_FIXTURES = ROOT / "tests" / "fixtures" / "impact_repo"
FIXTURE_DATA_FOLDER = ROOT / "tests" / "fixtures"
TARGET_KEY = re.compile(r"(?m)^requirements\s*:")


def target_files() -> list[Path]:
    found = []
    for path in sorted(ROOT.rglob("*.yaml")):
        relative = path.relative_to(ROOT)
        if SKIPPED_FOLDERS & set(relative.parts) or TEXT_FIXTURES in path.parents:
            continue
        if TARGET_KEY.search(path.read_text(encoding="utf-8")):
            found.append(path)
    return found


FILES = target_files()


def test_the_search_finds_the_targets_of_every_place_they_live():
    names = {path.relative_to(ROOT).as_posix() for path in FILES}

    assert len([name for name in names if name.startswith("examples/targets/")]) == 16
    assert {name for name in names if "strand-routes-files/targets/" in name} >= {
        f"docs/research/2026-11-01-strand-routes-files/targets/{stem}.yaml"
        for stem in ("s01-es-ring-forum-guide", "s02-fire-res-ring-showcase", "s11-remembrance-belt", "s12-stranded-ring", "s13-unravelling-belt")
    }
    assert {"research/218/r14-attack-speed.yaml", "research/312/r08-alchemy-target.yaml", "tests/fixtures/trade/r12_target.yaml"} <= names


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_the_target_file_is_read_by_the_target_loader(real, path):
    text = path.read_text(encoding="utf-8")
    if "start_price:" in text:  # an older research file: its price is the name of a buy spec, today's key is `start: bought`
        text = re.sub(r"(?m)^start_price:.*$", "start: bought", text)
    data = FIXTURE_DATA if FIXTURE_DATA_FOLDER in path.parents else real

    target = parse_target(without_strand_words(text), data, source=path.name)

    assert target.requirements
    assert re.search(r"(?m)^start_item\s*:", text) and re.search(r"(?m)^\s+rarity\s*:", text)  # the file states its start item itself
