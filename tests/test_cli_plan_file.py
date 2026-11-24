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
    return route_page(build_report(plan, DATA), DATA, buy_spec=spec, cache_dir=load_config().cache_dir)


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


def test_a_plan_saved_by_another_python_is_refused_before_it_is_read(planned, tmp_path: Path, monkeypatch):
    from crafting_system.cli import _plan_file

    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    monkeypatch.setattr(_plan_file, "_python", lambda: ("cpython", 3, 99, 0))
    monkeypatch.setattr(_plan_file._Reader, "load", lambda self: pytest.fail("the plan was read"))  # its closures are another Python's bytecode

    with pytest.raises(PlanFileError, match="another version of the program.s interpreter"):
        load_plan(path, DATA)


def test_a_plan_made_by_changed_planning_code_is_refused(planned, tmp_path: Path, monkeypatch):
    from crafting_system.cli import _plan_file

    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    hashed = _plan_file._source_hash
    monkeypatch.setattr(_plan_file, "_source_hash", lambda module: "edited" if module.startswith("crafting_system.planner.") else hashed(module))

    with pytest.raises(PlanFileError, match=r"other code than this one \(crafting_system\.planner\."):
        load_plan(path, DATA)


def test_a_plan_is_drawn_again_after_the_page_code_changed(planned, tmp_path: Path, monkeypatch):
    """The page's own modules are not stamped: a page change is checked against an old plan, which is what the file is for."""
    from crafting_system.cli import _plan_file

    plan, target = planned
    path = save_plan(tmp_path / "two.plan", plan, target, DATA, "two.yaml")
    hashed = _plan_file._source_hash
    page_code = ("crafting_system.cli._route", "crafting_system.cli._page_main", "crafting_system.cli._report")
    monkeypatch.setattr(_plan_file, "_source_hash", lambda module: "edited" if module.startswith(page_code) else hashed(module))

    assert _page(load_plan(path, DATA).plan) == _page(plan)


def test_a_plan_file_of_the_first_format_is_refused_in_words(planned, tmp_path: Path):
    from crafting_system.cli import _plan_file

    plan, target = planned
    path = tmp_path / "old.plan"
    with path.open("wb") as file:  # the first format: one pickle of the data's identity, then the plan
        _plan_file._Writer(file, DATA).dump((_plan_file._identity(DATA), plan, target, "two.yaml"))

    with pytest.raises(PlanFileError, match="older version of --save-plan"):
        load_plan(path, DATA)


def test_a_header_that_names_modules_of_no_planner_is_refused_without_looking_them_up(tmp_path: Path, monkeypatch):
    import pickle

    from crafting_system.cli import _plan_file

    path = tmp_path / "odd.plan"
    path.write_bytes(pickle.dumps((_plan_file.MAGIC, _plan_file._python(), _plan_file._identity(DATA), {"evil.mod": "x"})))
    monkeypatch.setattr(_plan_file, "_source_hash", lambda module: pytest.fail(f"looked up {module}"))

    with pytest.raises(PlanFileError, match="modules of no planner"):
        load_plan(path, DATA)


def test_two_saves_to_one_path_write_two_temp_files(tmp_path: Path, monkeypatch):
    from crafting_system.cli import _plan_file

    parts = []
    replace = Path.replace
    monkeypatch.setattr(Path, "replace", lambda self, target: (parts.append(self.name), replace(self, target))[1])
    save_plan(tmp_path / "one.plan", 1, None, DATA)
    save_plan(tmp_path / "one.plan", 2, None, DATA)

    assert len(set(parts)) == 2 and all(name.startswith(f"one.plan.{_plan_file.os.getpid()}.") for name in parts)
    assert load_plan(tmp_path / "one.plan", DATA).plan == 2


def test_a_given_route_the_saved_plan_was_not_offered_is_priced_on_the_guides_own_plan(tmp_path: Path, monkeypatch):
    """#1305: the reference pages are site plans, which are not offered every action their guide names (R08's fossils, R14's restart route);
    the page command then prices the guide on its own plan of those actions, as the benchmark judges it (`guide_plan`, #1442), so the page can
    say where the two costs differ."""
    from types import SimpleNamespace

    from test_cli_route_view import RESTART_ROUTE

    from crafting_system.cli import _route_view
    from crafting_system.cli._route import route_actions

    route = tmp_path / "route.yaml"
    route.write_text(RESTART_ROUTE, encoding="utf-8")  # it names the Chaos Orb (and restart)
    own = SimpleNamespace(name="the guide's own plan")
    asked = []
    monkeypatch.setattr(_route_view, "guide_plan", lambda data, target, prices, labels: asked.append((target, labels)) or own)

    def plan_offering(*labels):
        return SimpleNamespace(offers=[SimpleNamespace(label=label) for label in labels], starts=None, target="t", prices="p")

    offering = plan_offering("Chaos Orb", "Exalted Orb")
    labels = route_actions(route)
    assert _route_view.judged_on(offering, labels, DATA, "file") is offering and asked == []
    # the guide's own plan is made on the target as its file states it, not the plan's searched one (#1596: R17's catalyst quality)
    assert _route_view.judged_on(plan_offering("Exalted Orb"), labels, DATA, "file") is own and asked == [("file", ("Chaos Orb",))]
