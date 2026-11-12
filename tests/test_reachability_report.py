"""The reachability report of ticket #414 (`.github/scripts/reachability_report.py`).

Two kinds of test:

* the AST engine on small source trees written here: where a value is read, where it is only passed on, what the planner entry reaches;
* the real report against its committed copy `tests/golden/reachability.md`. It fails with a unified diff when the report changes, so
  a kind that becomes reachable, or a setting that gets a reader, is seen in review. `UPDATE_GOLDEN=1` rewrites the copy. The real game
  data is needed (CI has it; without it the test skips, as the other real-data tests do).
"""

import importlib.util
import os
import sys
import threading
from pathlib import Path

import golden_diff
import pytest
from abstraction_support import real_game_data

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "reachability_report.py"
GOLDEN = ROOT / "tests" / "golden" / "reachability.md"

spec = importlib.util.spec_from_file_location("reachability_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
sys.modules["reachability_report"] = report
spec.loader.exec_module(report)


def tree(tmp_path: Path, files: dict[str, str]) -> report.SourceIndex:
    """A package `toy` with the given modules (`a.py`, `sub/b.py`) and its index."""
    for name, text in files.items():
        path = tmp_path / "toy" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return report.SourceIndex(tmp_path / "toy", "toy")


def config_reads(index: report.SourceIndex, field: str) -> report.Trace:
    tracer = report.Tracer(index)
    klass = index.classes[("class", "toy.config", "Config")]
    typed, _ = tracer.attribute_reads(klass, field, extra=("config",), factories=("load_config",), skip=lambda module: module == "toy.config")
    return tracer.trace(typed)


CONFIG = '''
from dataclasses import dataclass


@dataclass
class Config:
    price_source: str = "both"
    strands: bool = False


def load_config():
    return Config()
'''


# --- where a value is read -------------------------------------------------------------------------------------------


def test_a_value_passed_on_and_stored_but_never_used_is_not_read(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\nfrom .run import run\n\n\ndef main():\n    config = load_config()\n    return run(price_source=config.price_source)\n",
            "run.py": "from dataclasses import dataclass\n\n\n@dataclass\nclass Context:\n    n: int\n    price_source: str\n\n\ndef run(price_source='x'):\n    return Context(1, price_source)\n",
            "use.py": "from .run import Context\n\n\ndef use(context: Context):\n    return context.n\n",
        },
    )
    trace = config_reads(index, "price_source")
    assert trace.sites == set()
    assert trace.ends == {"the field `Context.price_source`"}


def test_a_value_that_is_compared_is_read_and_the_place_is_named(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\nfrom .run import run\n\n\ndef main():\n    config = load_config()\n    return run(config.price_source)\n",
            "run.py": "def run(source):\n    wanted = source\n    if wanted == 'trade':\n        return 1\n    return 0\n",
        },
    )
    trace = config_reads(index, "price_source")
    assert trace.sites == {report.Site("toy.run", "run", "compared")}


def test_a_value_is_followed_into_a_field_and_out_of_it(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\nfrom .run import Context\n\n\ndef main():\n    config = load_config()\n    return Context(config.price_source)\n",
            "run.py": "from dataclasses import dataclass\n\n\n@dataclass\nclass Context:\n    price_source: str\n\n\ndef price(context: Context):\n    return len(context.price_source)\n",
        },
    )
    trace = config_reads(index, "price_source")
    assert [site.func for site in trace.sites] == ["price"]
    assert trace.ends == set()


def test_a_value_passed_through_kwargs_reaches_the_parameter_it_names(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\nfrom .run import outer\n\n\ndef main():\n    config = load_config()\n    return outer(strands=config.strands)\n",
            "run.py": "def outer(**kwargs):\n    return inner(**kwargs)\n\n\ndef inner(strands=False):\n    if strands:\n        raise ValueError('on')\n",
        },
    )
    trace = config_reads(index, "strands")
    assert trace.sites == {report.Site("toy.run", "inner", "decides a branch")}


def test_a_value_handed_to_code_outside_src_counts_as_used(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\n\n\ndef main():\n    config = load_config()\n    print(config.price_source)\n",
        },
    )
    trace = config_reads(index, "price_source")
    assert {site.how for site in trace.sites} == {"passed to `print` (outside src)"}


def test_a_value_returned_is_followed_to_its_callers(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\nfrom .run import pick\n\n\ndef main():\n    config = load_config()\n    return pick(config)\n\n\ndef pick(config):\n    return config.price_source\n",
        },
    )
    trace = config_reads(index, "price_source")
    assert trace.sites == set()
    assert trace.ends == {"the return value of `main`"}  # `pick` returns it to `main`, which returns it to a caller outside the tree


def test_getattr_with_a_name_is_a_read(tmp_path):
    index = tree(
        tmp_path,
        {
            "config.py": CONFIG,
            "main.py": "from .config import load_config\n\n\ndef main():\n    config = load_config()\n    if getattr(config, 'strands', False):\n        return 1\n",
        },
    )
    trace = config_reads(index, "strands")
    assert {site.how for site in trace.sites} == {"decides a branch"}


def test_a_flag_is_read_from_the_namespace_of_parse_args(tmp_path):
    index = tree(
        tmp_path,
        {
            "cli.py": (
                "import argparse\n\n\ndef main(argv):\n    parser = argparse.ArgumentParser()\n"
                "    parser.add_argument('--used')\n    parser.add_argument('--stored-only', dest='stored_only')\n"
                "    args = parser.parse_args(argv)\n    other = args.stored_only\n    if args.used:\n        return 1\n    return other\n"
            ),
        },
    )
    tracer = report.Tracer(index)
    assert {site.how for site in tracer.trace(tracer.flag_reads("used")).sites} == {"decides a branch"}
    flags = [flag for flag, *_ in report.cli_flags(index, "toy.")]
    assert flags == ["--stored-only", "--used"]


# --- what the planner entry reaches ----------------------------------------------------------------------------------


ENTRY_FILES = {
    "plan.py": "from .rules import offer\nfrom .types import Wide\n\n\ndef make_plan(x: Wide):\n    return offer(x)\n",
    "rules.py": "def offer(x):\n    return helper(x)\n\n\ndef helper(x):\n    return x\n\n\ndef floor(x):\n    return x\n",
    "types.py": "class Wide:\n    pass\n\n\nclass Base:\n    def __init__(self):\n        super().__init__()\n",
    "unused.py": "from .rules import floor\n\n\ndef nobody_calls_me():\n    return floor(1)\n",
}


def test_what_the_entry_calls_is_reached_and_what_nobody_calls_is_not(tmp_path):
    index = tree(tmp_path, ENTRY_FILES)
    reach = index.reachable_from([("func", "toy.plan", "make_plan")])
    assert ("func", "toy.rules", "offer") in reach
    assert ("func", "toy.rules", "helper") in reach
    assert ("func", "toy.rules", "floor") not in reach  # only an unreached function refers to it
    assert ("func", "toy.unused", "nobody_calls_me") not in reach


def test_a_type_annotation_is_not_a_use(tmp_path):
    index = tree(tmp_path, ENTRY_FILES)
    reach = index.reachable_from([("func", "toy.plan", "make_plan")])
    assert ("class", "toy.types", "Wide") not in reach  # named in `make_plan(x: Wide)` only


def test_who_refers_to_a_name_is_listed(tmp_path):
    index = tree(tmp_path, ENTRY_FILES)
    assert index.referrers(("func", "toy.rules", "floor")) == [("func", "toy.unused", "nobody_calls_me")]


def test_a_call_found_by_a_method_name_alone_follows_a_rare_name_and_never_a_dunder(tmp_path):
    index = tree(
        tmp_path,
        {
            "a.py": "class Maker:\n    def build(self):\n        return 1\n\n    def __init__(self):\n        pass\n",
            "b.py": "def go(thing):\n    thing.build()\n    thing.__init__()\n",
        },
    )
    reach = index.reachable_from([("func", "toy.b", "go")])
    assert ("func", "toy.a", "Maker.build") in reach
    assert ("func", "toy.a", "Maker.__init__") not in reach


# --- the entry's gates, and the slow target --------------------------------------------------------------------------


def test_the_gates_of_make_plan_are_read_from_its_code_in_order():
    index = report.SourceIndex(ROOT / "src" / "crafting_system")
    gates = report.entry_gates(index)
    conditions = [condition for condition, _ in gates]
    assert "target.implicits or target.quality is not None" in conditions
    assert not any("solution" in condition for condition in conditions)  # the refusal after the solve is not a gate of the entry
    assert "target.sockets is not None" not in dict(gates)  # the socket finish is attached to the goal states since #231: no longer a gate


def test_a_run_over_its_time_is_given_up_and_reported():
    stuck = threading.Event()
    finished, _ = report.run_with_limit(lambda: stuck.wait(30), 0.05)
    stuck.set()  # let the left-behind thread end
    assert finished is False
    finished, value = report.run_with_limit(lambda: 42, 5)
    assert (finished, value) == (True, 42)
    finished, value = report.run_with_limit(lambda: 1 / 0, 5)
    assert finished is True and isinstance(value, ZeroDivisionError)


def test_two_files_that_begin_alike_keep_their_whole_names():
    ids = report.short_ids(["r10-a", "r10-b", "r12-c"])
    assert ids == {"r10-a": "r10-a", "r10-b": "r10-b", "r12-c": "r12"}


# --- the real report -------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_report():
    return report.build_report(real_game_data(), seconds=300)  # a slow machine must not turn a target into "too slow"


def test_the_report_equals_its_committed_copy(real_report):
    text = real_report + "\n"
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
    assert GOLDEN.exists(), f"no committed report {GOLDEN}; run with UPDATE_GOLDEN=1 to write it"
    expected = GOLDEN.read_text(encoding="utf-8")
    golden_diff.check(
        expected,
        text,
        "text",
        "the reachability report changed. If the change is meant (a kind became reachable, a setting got a reader), "
        "run with UPDATE_GOLDEN=1 and commit tests/golden/reachability.md so the change is seen in review.",
    )


def test_every_kind_of_the_catalog_has_a_row(real_report):
    from crafting_system.actions import kinds

    for entry in kinds():
        assert f"| `{entry.name}` |" in real_report


def test_the_settings_the_audit_names_are_in_the_report(real_report):
    for name in ("price_source", "price_gap_percent", "--price-source", "max_imprints", "recombinator_junk_craft", "memory_strands"):
        assert f"| `{name}` |" in real_report


# --- the built modules ------------------------------------------------------------------------------------------------


def test_a_built_module_lists_all_its_public_names_or_only_the_ones_it_names(tmp_path):
    index = tree(tmp_path, ENTRY_FILES)
    reach = index.reachable_from([("func", "toy.plan", "make_plan")])

    whole = report.built_module_rows(index, reach, (("the rules", "toy.rules", "X-1", None),))
    some = report.built_module_rows(index, reach, (("the rules", "toy.rules", "X-1", ("floor",)),))

    assert [row[1] for row in whole] == ["`floor`", "`helper`", "`offer`"]
    assert some == [["the rules", "`floor`", "`rules.py`", "unused.py: nobody_calls_me", "**no**", "X-1"]]


def test_a_built_name_that_is_not_in_its_module_is_an_error_not_a_missing_row(tmp_path):
    index = tree(tmp_path, ENTRY_FILES)

    with pytest.raises(ValueError, match="renamed"):
        report.built_module_rows(index, set(), (("the rules", "toy.rules", "X-1", ("renamed",)),))
