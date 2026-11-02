"""The mutation step of the measurement chain (ticket #399, step 5): operators, test selection, slicing, runner, summary.

Small hand-made inputs only. No real mutation round runs here: the runner is tested with a fake pytest.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mutation_ops as ops  # noqa: E402
import mutation_plan as plan_module  # noqa: E402
import mutation_run as run  # noqa: E402
import mutation_select as select  # noqa: E402
import mutation_summary as summary  # noqa: E402

SOURCE = '''\
LIMIT = 3


def pick(a, b, items: list[int]) -> int:
    """Doc."""
    if a < b and not items:
        return a + b
    log.debug("x" + str(a))
    if a == 4:
        raise ValueError("bad " + str(5))
    flag = True
    return a * 2
'''

EXPECTED = [
    (6, "compare", "a < b", "a <= b"),
    (6, "boolop", "a < b and not items", "a < b or not items"),
    (6, "not", "not items", "items"),
    (7, "arith", "a + b", "a - b"),
    (7, "return", "return a + b", "return 0"),
    (9, "compare", "a == 4", "a != 4"),
    (9, "const", "4", "5"),
    (11, "bool", "True", "False"),
    (12, "arith", "a * 2", "a / 2"),
    (12, "const", "2", "3"),
    (12, "return", "return a * 2", "return 0"),
]


def listing(source: str) -> list[tuple]:
    return [(m.line, m.operator, m.original, m.mutated) for m in ops.find_mutants(source, "x.py")]


def test_the_operators_give_the_numbered_mutants_of_a_small_source():
    assert sorted(listing(SOURCE)) == sorted(EXPECTED)


def test_the_list_is_the_same_on_every_call_and_in_source_order():
    first = ops.find_mutants(SOURCE, "x.py")
    assert first == ops.find_mutants(SOURCE, "x.py")
    assert [(m.line, m.col) for m in first] == sorted((m.line, m.col) for m in first)


def test_docstrings_raises_logging_and_module_constants_are_not_mutated():
    lines = {line for line, *_ in listing(SOURCE)}
    assert not lines & {1, 5, 8, 10}


def test_every_mutated_source_parses_changes_one_place_and_keeps_the_line_count():
    for mutant in ops.find_mutants(SOURCE, "x.py"):
        changed = ops.apply_mutant(SOURCE, mutant)
        ast.parse(changed)
        assert changed != SOURCE
        assert changed.count("\n") == SOURCE.count("\n")
        before, after = SOURCE.splitlines(), changed.splitlines()
        untouched = [n for n in range(len(before)) if not mutant.line - 1 <= n <= mutant.end_line - 1]
        assert all(before[n] == after[n] for n in untouched)
        assert mutant.mutated in after[mutant.line - 1]


def test_a_node_after_non_ascii_text_is_replaced_at_the_right_column():
    source = 'def f(x):\n    name = "é—ü"; return x < 2\n'
    mutants = [m for m in ops.find_mutants(source) if m.operator == "compare"]
    assert [ops.apply_mutant(source, m) for m in mutants] == ['def f(x):\n    name = "é—ü"; return x <= 2\n']


def test_the_comparison_flips_cover_both_sides_and_each_operator_of_a_chain():
    source = "def f(a, b, c):\n    return a < b <= c\n"
    flips = sorted(m.mutated for m in ops.find_mutants(source) if m.operator == "compare")
    assert flips == ["a < b < c", "a <= b <= c"]


def test_strings_and_literal_lists_are_not_added_or_subtracted_and_ints_in_text_are_left_alone():
    source = 'def f(x):\n    a = "p" + x\n    b = [1] + x\n    c = x + (1,)\n    d = f"{x}1"\n    return a, b, c, d\n'
    assert [m.operator for m in ops.find_mutants(source) if m.operator == "arith"] == []


def test_return_becomes_the_neutral_value_of_the_annotated_type_only():
    source = (
        "from fractions import Fraction\n\n"
        "def a(x) -> Fraction:\n    return x * x\n"
        "def b(x) -> list[int]:\n    return sorted(x)\n"
        "def c(x) -> int | None:\n    return len(x)\n"
        "def d(x) -> frobnicate:\n    return len(x)\n"
        "def e(x):\n    return len(x)\n"
        "def g(x) -> int:\n    yield x\n"
    )
    found = {m.line: m.mutated for m in ops.find_mutants(source) if m.operator == "return"}
    assert found == {4: "return Fraction(0)", 6: "return []", 8: "return None"}


def test_a_pragma_comment_keeps_a_statement_out_and_a_not_is_dropped_with_parentheses_where_needed():
    source = "def f(a, b):\n    if not (a or b):\n        return 1  # no mutate\n    return 0\n"
    assert [(m.operator, m.mutated) for m in ops.find_mutants(source) if m.operator == "not"] == [("not", "(a or b)")]
    assert not [m for m in ops.find_mutants(source) if m.line == 3]


# --- the tests of a line ----------------------------------------------------------------------------------------------


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "crafting_system" / "actions").mkdir(parents=True)
    (tmp_path / "src" / "crafting_system" / "__init__.py").write_text("")
    (tmp_path / "src" / "crafting_system" / "actions" / "__init__.py").write_text("from .scour import ScouringOrb\n")
    (tmp_path / "src" / "crafting_system" / "actions" / "scour.py").write_text(
        "class ScouringOrb:\n    def apply(self, x):\n        return x < 2\n"
    )
    (tmp_path / "tests" / "test_scour.py").write_text(
        "import pytest\nfrom crafting_system.actions import ScouringOrb\n\n"
        "def test_first():\n    pass\n\n"
        "class TestGroup:\n    def test_second(self):\n        pass\n"
    )
    (tmp_path / "tests" / "test_other.py").write_text("from helpers import thing\n\ndef test_other():\n    pass\n")
    (tmp_path / "tests" / "helpers.py").write_text("from crafting_system.actions.scour import ScouringOrb\n\nthing = 1\n")
    (tmp_path / "tests" / "test_unrelated.py").write_text("def test_nothing():\n    pass\n")
    return tmp_path


def test_a_context_name_becomes_a_pytest_node_id(tmp_path):
    index = select.build_index(make_repo(tmp_path) / "tests", tmp_path)
    assert select.resolve_context(index, "test_scour.test_first") == "tests/test_scour.py::test_first"
    assert select.resolve_context(index, "test_scour.TestGroup.test_second") == "tests/test_scour.py::TestGroup::test_second"
    assert select.resolve_context(index, "tests.test_scour.test_first") == "tests/test_scour.py::test_first"
    assert select.resolve_context(index, "test_scour.test_missing") is None
    assert select.resolve_context(index, "nowhere.test_first") is None


def test_the_test_files_that_use_a_module_include_those_that_import_it_through_a_helper(tmp_path):
    root = make_repo(tmp_path)
    index = select.build_index(root / "tests", root)
    graph = select.build_src_graph(root / "src")
    assert select.import_fallback(index, graph, "crafting_system.actions.scour") == ["tests/test_other.py", "tests/test_scour.py"]


def test_a_line_runs_the_tests_of_its_contexts_and_whole_files_when_it_also_ran_in_a_fixture(tmp_path):
    root = make_repo(tmp_path)
    index = select.build_index(root / "tests", root)
    graph = select.build_src_graph(root / "src")
    module = "crafting_system.actions.scour"
    contexts = {3: ["test_scour.test_first", "test_scour.TestGroup.test_second"], 2: ["", "test_scour.test_first"], 1: []}
    ids, origin, cut = select.tests_for_line(index, graph, module, contexts, 3)
    assert (ids, origin, cut) == (["tests/test_scour.py::TestGroup::test_second", "tests/test_scour.py::test_first"], "coverage", 0)
    assert select.tests_for_line(index, graph, module, contexts, 2)[0] == ["tests/test_scour.py"]
    assert select.tests_for_line(index, graph, module, contexts, 1)[1] == "none"  # no test ran it: unreached
    assert select.tests_for_line(index, graph, module, contexts, 1, reach_fallback=True)[1] == "imports"
    assert select.tests_for_line(index, graph, module, None, 1)[1] == "imports"  # no data file at all


def test_the_slowest_files_are_cut_first_when_a_set_is_too_big(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    index = select.build_index(root / "tests", root)
    graph = select.build_src_graph(root / "src")
    monkeypatch.setattr(select, "MAX_TESTS", 1)
    speeds = {"tests/test_scour.py": 5.0, "tests/test_other.py": 0.1}
    assert select.tests_for_line(index, graph, "crafting_system.actions.scour", None, 1, speeds) == (["tests/test_other.py"], "imports", 1)


def test_file_speeds_add_the_groups_of_one_file():
    durations = {"tests/a.py": {"seconds": 6, "tests": 2}, "tests/a.py[x#0]": {"seconds": 4, "tests": 3}, "tests/b.py": {"seconds": 1, "tests": 4}}
    assert select.file_speeds(durations) == {"tests/a.py": 2.0, "tests/b.py": 0.25}


def test_lines_and_contexts_are_read_from_a_coverage_data_file(tmp_path):
    coverage = pytest.importorskip("coverage", reason="the coverage package is installed by the workflow, not by the project")
    data_file = tmp_path / ".coverage"
    data = coverage.CoverageData(basename=str(data_file))
    name = "src/crafting_system/actions/scour.py"
    for context, lines in {"test_a.test_one": [1, 2], "test_a.test_two": [2, 3], "": [1]}.items():
        data.set_context(context)
        data.add_lines({name: lines})
    data.write()
    found = select.read_line_contexts(data_file, "src/crafting_system/actions/scour.py")
    assert {line: sorted(names) for line, names in found.items()} == {1: ["", "test_a.test_one"], 2: ["test_a.test_one", "test_a.test_two"], 3: ["test_a.test_two"]}
    assert select.read_line_contexts(data_file, "src/crafting_system/other.py") is None


# --- the plan -------------------------------------------------------------------------------------------------------


def test_the_plan_orders_by_tier_and_interleaves_files_inside_a_tier(tmp_path):
    root = make_repo(tmp_path)
    (root / "src" / "crafting_system" / "solver").mkdir()
    (root / "src" / "crafting_system" / "solver" / "_a.py").write_text("def f(x):\n    return x < 1\n\ndef g(y):\n    return y > 2\n")
    (root / "src" / "crafting_system" / "solver" / "_b.py").write_text("def h(z):\n    return z == 3\n")
    (root / "tests" / "test_solver.py").write_text("from crafting_system.solver import _a, _b\n\ndef test_s():\n    pass\n")
    first = plan_module.build_plan(root, None, None, trial=False)
    again = plan_module.build_plan(root, None, None, trial=False)
    assert first == again
    order = [(m["tier"], Path(m["file"]).name, m["line"]) for m in first["mutants"]]
    assert [number["id"] for number in first["mutants"]] == list(range(len(order)))
    assert [name for tier, name, _ in order if tier == 3] == ["_a.py", "_b.py", "_a.py", "_a.py", "_b.py", "_a.py"]
    assert [tier for tier, *_ in order] == sorted(tier for tier, *_ in order)
    assert all(m["set"] in first["sets"] for m in first["mutants"])
    assert set(first["hashes"]) == set(first["files"])


def test_the_trial_plan_is_at_most_20_mutants_of_one_file(tmp_path):
    root = make_repo(tmp_path)
    sparse = root / "src" / "crafting_system" / "solver"
    sparse.mkdir()
    (sparse / "_sparse.py").write_text("".join(f"def f{i}(x):\n    return x < {i}\n" for i in range(30)))
    (root / "tests" / "test_sparse.py").write_text("from crafting_system.solver import _sparse\n\ndef test_s():\n    pass\n")
    trial = plan_module.build_plan(root, None, None, trial=True)
    assert len(trial["mutants"]) == 20
    assert {m["file"] for m in trial["mutants"]} == {"src/crafting_system/solver/_sparse.py"}


def test_a_sample_keeps_evenly_spaced_mutants_renumbered_with_their_sets():
    plan = {"mutants": [{"id": n, "set": "a" if n < 5 else "b"} for n in range(10)], "sets": {"a": 1, "b": 2, "c": 3}, "x": 7}
    sample = plan_module.sample_plan(plan, 3)
    assert [(m["id"], m["set"]) for m in sample["mutants"]] == [(0, "a"), (1, "a"), (2, "b")]  # old numbers 0, 3, 6
    assert sample["sets"] == {"a": 1, "b": 2} and sample["x"] == 7
    assert [m["id"] for m in plan["mutants"]] == list(range(10))  # the plan itself is not changed


# --- the slices -----------------------------------------------------------------------------------------------------


def test_the_jobs_of_a_round_take_disjoint_stripes_of_what_is_pending():
    mutants = [{"id": number} for number in range(10)]
    done = {0, 1, 4}
    stripes = [[m["id"] for m in run.slice_of(mutants, done, job, 3)] for job in (1, 2, 3)]
    assert stripes == [[2, 6, 9], [3, 7], [5, 8]]
    assert sorted(sum(stripes, [])) == [2, 3, 5, 6, 7, 8, 9]


def test_only_earlier_rounds_count_as_done(tmp_path):
    for name, round_number, ids in (("a", 1, [0, 1]), ("b", 2, [2]), ("c", 3, [3])):
        folder = tmp_path / f"measure-mut-{name}"
        folder.mkdir()
        (folder / "results.jsonl").write_text("".join(json.dumps({"id": i, "round": round_number}) + "\n" for i in ids))
    assert run.load_done(tmp_path, before_round=3) == {0, 1, 2}
    assert run.load_done(tmp_path) == {0, 1, 2, 3}
    assert run.load_done(None) == set()


def test_the_job_stops_at_the_deadline_or_its_own_minutes_whichever_is_first():
    assert run.stop_time(1000.0, 320, "", False) == 1000.0 + 320 * 60
    assert run.stop_time(0.0, 320, "1970-01-01T01:00:00Z", False) == 3600.0
    assert run.stop_time(0.0, 6, "1970-01-01T01:00:00Z", True) == 360.0  # the trial does not wait for a deadline


# --- one slice through the runner -------------------------------------------------------------------------------------


class FakePytest:
    """Stands in for the pytest child: the file's text decides the exit code, and every call is remembered."""

    def __init__(self, path: Path, codes: dict[str, int | None]):
        self.path, self.codes, self.original, self.calls = path, codes, path.read_text(encoding="utf-8"), []

    def __call__(self, node_ids, timeout):
        text = self.path.read_text(encoding="utf-8")
        self.calls.append((list(node_ids), timeout, text))
        code = 0 if text == self.original else next(c for k, c in self.codes.items() if k in text)
        return run.RunResult(code, 2.0)


def small_plan(file: str, source: str, tests=("tests/test_a.py",)) -> dict:
    mutants = [{**m.to_json(), "tier": 1, "set": "s1", "id": number} for number, m in enumerate(ops.find_mutants(source, file))]
    return {"mutants": mutants, "sets": {"s1": {"tests": list(tests), "source": "coverage", "cut": 0}}, "hashes": {}, "files": {}}


def test_each_mutant_gets_its_outcome_and_the_file_is_restored(tmp_path):
    target = tmp_path / "m.py"
    source = "def f(x):\n    return x < 2\n"
    target.write_text(source)
    plan = small_plan("m.py", source)
    assert [m["mutated"] for m in plan["mutants"]] == ["x <= 2", "3"]
    fake = FakePytest(target, {"x <= 2": 1, "x < 3": None})
    out = tmp_path / "out.jsonl"
    status = run.process_slice(plan, plan["mutants"], tmp_path, fake, out, stop_at=10**12, round_number=1, job=1, max_clean=100, max_limit=600)
    results = {r["mutated"]: r["outcome"] for r in map(json.loads, out.read_text().splitlines())}
    assert results == {"x <= 2": "killed", "3": "timeout"}
    assert target.read_text() == source  # restored
    assert status["done"] == len(plan["mutants"]) and status["not_reached"] == []
    assert fake.calls[0][2] == source  # the first call is the clean run
    clean_calls = [c for c in fake.calls if c[2] == source]
    assert len(clean_calls) == 1  # measured once per set
    assert all(call[1] == 60.0 for call in fake.calls[1:])  # max(60, 3 x 2 s)


def test_a_crash_inside_the_run_still_restores_the_file(tmp_path):
    target = tmp_path / "m.py"
    source = "def f(x):\n    return x < 2\n"
    target.write_text(source)
    plan = small_plan("m.py", source)
    calls = []

    def crashing(node_ids, timeout):
        calls.append(target.read_text())
        if len(calls) == 1:
            return run.RunResult(0, 1.0)
        raise RuntimeError("the machine died")

    with pytest.raises(RuntimeError):
        run.process_slice(plan, plan["mutants"], tmp_path, crashing, tmp_path / "o.jsonl", 10**12, 1, 1, 100, 600)
    assert calls[1] != source and target.read_text() == source


def test_a_set_that_fails_clean_skips_its_mutants_and_the_limit_grows_with_the_clean_time(tmp_path):
    target = tmp_path / "m.py"
    source = "def f(x):\n    return x < 2\n"
    target.write_text(source)
    plan = small_plan("m.py", source)
    out = tmp_path / "bad.jsonl"
    run.process_slice(plan, plan["mutants"], tmp_path, lambda ids, timeout: run.RunResult(1, 1.0), out, 10**12, 1, 1, 100, 600)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert {r["outcome"] for r in rows} == {"skipped"} and "clean run failed" in rows[0]["detail"]

    seen = []
    slow = lambda ids, timeout: (seen.append(timeout), run.RunResult(0, 50.0))[1]  # noqa: E731
    run.process_slice(plan, plan["mutants"][:1], tmp_path, slow, tmp_path / "slow.jsonl", 10**12, 1, 1, 100, 600)
    assert seen == [100, 150.0]  # the clean run gets max_clean, the mutant 3 x 50 s


def test_a_job_stops_starting_mutants_at_its_stop_time_and_reports_what_it_did_not_reach(tmp_path):
    target = tmp_path / "m.py"
    source = "def f(x):\n    return x < 2\n"
    target.write_text(source)
    plan = small_plan("m.py", source)
    clock = iter([0, 0, 0, 0, 0, 100, 100, 100])
    status = run.process_slice(
        plan, plan["mutants"], tmp_path, lambda ids, timeout: run.RunResult(0, 1.0), tmp_path / "o.jsonl", 50, 1, 1, 100, 600, now=lambda: next(clock)
    )
    assert status["done"] == 2 and status["not_reached"] == [m["id"] for m in plan["mutants"][2:]]


def test_the_exit_code_of_pytest_gives_the_outcome():
    assert [run.outcome_of(run.RunResult(code, 1.0)) for code in (0, 1, 2, 4, 5, None)] == [
        "survived", "killed", "error", "error", "error", "timeout",
    ]  # fmt: skip


# --- the summary ------------------------------------------------------------------------------------------------------


def record(number, file, outcome, line=1, tier=1, **more):
    base = {
        "id": number, "file": f"src/crafting_system/{file}", "line": line, "operator": "compare", "original": "a < b",
        "mutated": "a <= b", "tier": tier, "set": "s1", "tests": 2, "source": "coverage", "cut": 0, "round": 1, "job": 1,
        "outcome": outcome, "seconds": 1.0, "detail": "",
    }  # fmt: skip
    return base | more


def hand_made():
    plan = {
        "coverage": True,
        "sets": {"s1": {"tests": ["tests/t.py"], "source": "coverage", "cut": 0}},
        "files": {
            "src/crafting_system/actions/draw.py": {"tier": 1, "mutants": 4, "unreached": 3, "no_tests": 0},
            "src/crafting_system/solver/_solve.py": {"tier": 3, "mutants": 3, "unreached": 0, "no_tests": 0},
            "src/crafting_system/risk/_x.py": {"tier": 4, "mutants": 2, "unreached": 0, "no_tests": 0},
        },
        "mutants": [{"id": number} for number in range(9)],
    }
    results = {
        r["id"]: r
        for r in [
            record(0, "actions/draw.py", "killed"), record(1, "actions/draw.py", "survived", line=7),
            record(2, "actions/draw.py", "killed"), record(3, "actions/draw.py", "timeout"),
            record(4, "solver/_solve.py", "survived", line=9, cut=5), record(5, "solver/_solve.py", "survived", line=11),
            record(6, "solver/_solve.py", "error"), record(7, "risk/_x.py", "skipped", tier=4),
        ]
    }
    return plan, results


def test_the_summary_ranks_modules_by_survival_rate_and_counts_what_was_not_reached():
    plan, results = hand_made()
    rows = summary.module_rows(plan, results)
    assert [(row["module"], row["checked"], row["survived"], row["not_reached"]) for row in rows] == [
        ("solver/_solve.py", 3, 2, 0), ("actions/draw.py", 4, 1, 0), ("risk/_x.py", 0, 0, 2),
    ]  # fmt: skip
    text, survivors, headline = summary.build(plan, results)
    assert text.startswith("# mutation\n")
    assert "| solver/_solve.py | 3 | 3 | 0 | 2 | 0 | 1 | 66.7 | 0 |" in text
    assert text.count("\n") <= 150
    assert survivors.splitlines() == [
        "actions/draw.py:7  compare  a < b → a <= b",
        "solver/_solve.py:9  compare  a < b → a <= b [tests cut]",
        "solver/_solve.py:11  compare  a < b → a <= b",
    ]
    assert headline == "Мутантов проверено: 7; выжило (тесты не заметили поломку): 3 (42.9%); хуже всего покрыт solver/_solve.py.\n"
    assert len(headline) <= 200


def test_the_summary_of_nothing_says_so_in_one_line(tmp_path):
    plan, _ = hand_made()
    text, survivors, headline = summary.build(plan, {})
    assert survivors == "" and headline.startswith("Мутантов проверено: 0")
    assert "# mutation" in text


def test_the_last_record_of_a_mutant_wins_when_read_from_many_jobs(tmp_path):
    for name, outcome in (("1-1", "survived"), ("2-1", "killed")):
        folder = tmp_path / f"measure-mut-{name}"
        folder.mkdir()
        (folder / "results.jsonl").write_text(json.dumps(record(5, "actions/draw.py", outcome)) + "\n")
    assert summary.read_results(tmp_path)[5]["outcome"] == "killed"  # folders are read in name order: round 2 after round 1
    assert len(summary.read_results(tmp_path)) == 1
