"""A finished plan saved with `--save-plan` and read back draws the same route page, so a page change is checked without planning (#1442).

A plain pickle of a plan failed: the game data holds a mappingproxy and the abstraction local closures (its per-context profile). The file
names the game data and rebuilds the closures from their code and values (`cli/_plan_file.py`).
"""

from pathlib import Path

import pytest
from cli_support import price_file
from items_support import DATA
from test_cli_route_view import TWO_LEAVES, judged_plan

from crafting_system.cli import main
from crafting_system.cli._plan_file import PlanFileError, load_plan, save_plan
from crafting_system.cli._report import build_report
from crafting_system.cli._route_view import route_page
from crafting_system.config import load_config
from crafting_system.prices import PriceEntry
from crafting_system.targets import buy_spec_of, parse_target, start_price_key


@pytest.fixture(scope="module")
def planned():
    target = parse_target(TWO_LEAVES, DATA, source="two.yaml")
    prices = price_file(start=None)
    prices.prices[start_price_key(DATA, target)] = PriceEntry(4.0, "trade-api")
    return judged_plan(target, prices), target


def _page(plan, target=None) -> str:
    """The page of `plan`; with `target`, with the trade link of its bought start item, as the command draws it."""
    spec = None if target is None else buy_spec_of(DATA, target)
    return route_page(build_report(plan, DATA), DATA, buy_spec=spec, cache_dir=load_config().cache_dir, target_name="two.yaml")


def test_a_saved_plan_read_back_draws_the_same_page(planned, tmp_path: Path):
    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")

    saved = load_plan(path, DATA)

    assert saved.target_name == "two.yaml" and saved.target == target
    assert _page(saved.plan) == _page(plan)


def test_the_page_command_writes_the_page_of_a_saved_plan(planned, tmp_path: Path):
    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    out = tmp_path / "again.html"

    assert main(["page", str(path), "--out", str(out)], data=DATA) == 0
    assert out.read_text(encoding="utf-8") == _page(plan, target)


def test_a_closure_is_saved_with_its_values(tmp_path: Path):
    def made(offset: int):
        return lambda value: value + offset  # a local function, as the abstraction's profile is

    path = save_plan(tmp_path / "fn.plan", made(5), None, DATA)

    assert load_plan(path, DATA).plan(2) == 7


def test_a_file_that_is_not_a_whole_plan_is_refused_in_words(planned, tmp_path: Path, capsys):
    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])  # a save stopped half way

    with pytest.raises(PlanFileError):
        load_plan(path, DATA)
    assert main(["page", str(path), "--out", str(tmp_path / "p.html")], data=DATA) == 1
    assert "is not a plan this code can read" in capsys.readouterr().err


def test_a_save_that_fails_leaves_no_file(tmp_path: Path):
    def gen():
        yield 1

    with pytest.raises(TypeError):
        save_plan(tmp_path / "bad.plan", gen(), None, DATA)  # a generator does not pickle
    assert list(tmp_path.iterdir()) == []


def test_a_plan_made_on_other_game_data_is_refused(planned, tmp_path: Path, monkeypatch):
    from crafting_system.cli import _plan_file

    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    monkeypatch.setattr(_plan_file, "_identity", lambda data: "another snapshot")

    with pytest.raises(PlanFileError, match="other game data"):
        load_plan(path, DATA)
