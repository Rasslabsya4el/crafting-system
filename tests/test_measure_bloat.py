"""The bloat measurement of ticket #399 (`.github/scripts/state_bloat.py`): the projections, the counting of what they merge, the lumped
chain, the tables, and one fixture route end to end. No real route runs here (R04 and R14 are heavy and go to GitHub).
"""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from cli_support import price_file
from targets_support import DATA

from crafting_system.abstraction import CompressedState, Flags, FracturedMod, ImplicitSide, OfferedMod, Slot, Status
from crafting_system.cli._benchmark import BENCHMARKS
from crafting_system.config import find_project_root, load_config
from crafting_system.items import PlainQuality, Rarity, Side
from crafting_system.solver import Action, Outcome

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "state_bloat.py"
spec = importlib.util.spec_from_file_location("state_bloat", SCRIPT)
bloat = importlib.util.module_from_spec(spec)
sys.modules["state_bloat"] = bloat
spec.loader.exec_module(bloat)

ABSENT, PASSING = Status.ABSENT, Status.PASSING
JUNK_ONE = Slot(Side.PREFIX, "~1", (ABSENT,))
JUNK_TWO = Slot(Side.PREFIX, "~2", (ABSENT,))
NAMED_A = Slot(Side.PREFIX, "FamilyA", (ABSENT,))  # a junk mod kept by its family key: a name, which the junk projection drops
NAMED_B = Slot(Side.PREFIX, "FamilyB", (ABSENT,))
WANTED = Slot(Side.SUFFIX, "FamilyWanted", (PASSING,))


def state(**changes) -> CompressedState:
    fields = {
        "flags": Flags(Rarity.RARE, False, frozenset()),
        "fractured": (FracturedMod("m1", (PASSING,)),),
        "status": (ABSENT,),
        "slots": (JUNK_ONE, WANTED),
        "implicits": (),
        "quality": None,
        "offer": (),
        "imprints": (),
    }
    fields.update(changes)
    return CompressedState(**fields)


OTHER = {
    "flags": Flags(Rarity.MAGIC, False, frozenset()),
    "fractured": (),
    "status": (PASSING,),
    "slots": (WANTED,),
    "implicits": (ImplicitSide(1, (ABSENT,)),),
    "quality": PlainQuality(20),
    "offer": (OfferedMod("a", (ABSENT,)),),
    "imprints": (state(slots=()),),
}


# --- the projections -----------------------------------------------------------------------------


def test_the_parts_are_the_fields_of_the_state_in_order():
    assert bloat.PARTS == tuple(field.name for field in dataclasses.fields(CompressedState))
    assert set(OTHER) == set(bloat.PARTS)


@pytest.mark.parametrize("part", bloat.PARTS)
def test_a_projection_merges_states_that_differ_only_in_that_part(part):
    one, other = state(), state(**{part: OTHER[part]})

    assert one != other
    for column in bloat.PARTS:
        project = bloat.projector(column)
        assert (project(one) == project(other)) is (column == part), column


@pytest.mark.parametrize("part", bloat.COLUMNS)
def test_a_projection_is_hashable_and_a_set_of_them_counts_the_distinct_states(part):
    project = bloat.projector(part)

    assert len({project(state()), project(state()), project(state(flags=OTHER["flags"], fractured=()))}) == 2


def test_the_junk_projection_drops_the_name_of_a_junk_mod_only():
    project = bloat.projector(bloat.JUNK)

    named_one, named_two = NAMED_A, NAMED_B
    assert project(state(slots=(named_one, WANTED))) == project(state(slots=(named_two, WANTED)))
    assert state(slots=(named_one, WANTED)) != state(slots=(named_two, WANTED))
    # a numbered family type is a class of pool weights, so odds: it is no name and stays
    assert project(state(slots=(JUNK_ONE, WANTED))) != project(state(slots=(JUNK_TWO, WANTED)))
    # a mod that gives the goal something keeps its name; so do a crafted mod, the side and a repeat
    named = Slot(Side.SUFFIX, "FamilyOther", (PASSING,))
    assert project(state(slots=(WANTED,))) != project(state(slots=(named,)))
    crafted_one, crafted_two = Slot(Side.PREFIX, "craft1", (ABSENT,), True), Slot(Side.PREFIX, "craft2", (ABSENT,), True)
    assert project(state(slots=(crafted_one,))) != project(state(slots=(crafted_two,)))
    assert project(state(slots=(JUNK_ONE,))) != project(state(slots=(Slot(Side.SUFFIX, "~1", (ABSENT,)),)))
    assert project(state(slots=(JUNK_ONE,))) != project(state(slots=(JUNK_ONE, JUNK_TWO)))
    # the tag of a mod is a class and stays; the slots are a multiset again after the names go
    attack, caster = Slot(Side.PREFIX, "~3@attack", (ABSENT,)), Slot(Side.PREFIX, "~3@caster", (ABSENT,))
    assert project(state(slots=(attack,))) != project(state(slots=(caster,)))
    assert project(state(slots=(Slot(Side.PREFIX, "A", (ABSENT,)), JUNK_ONE))) == project(state(slots=(JUNK_ONE, Slot(Side.PREFIX, "B", (ABSENT,)))))


def test_the_junk_projection_reads_the_states_held_in_imprints_too():
    project = bloat.projector(bloat.JUNK)

    assert project(state(imprints=(state(slots=(NAMED_A,)),))) == project(state(imprints=(state(slots=(NAMED_B,)),)))


def test_a_new_field_of_the_state_makes_the_projection_fail_loudly():
    @dataclasses.dataclass(frozen=True)
    class Wider(CompressedState):
        extra: int = 0

    with pytest.raises(ValueError, match="extra"):
        bloat.check_fields(Wider)
    for column in bloat.COLUMNS:
        with pytest.raises(ValueError, match="measures"):
            bloat.projector(column, Wider)
    bloat.check_fields()  # the real state passes


def test_an_unknown_part_is_refused():
    with pytest.raises(KeyError):
        bloat.projector("rarity")


# --- what a projection merges --------------------------------------------------------------------


def test_measure_part_counts_the_groups_and_what_differs_in_them():
    # the key is the first letter; group a holds three states (values differ), b two (action differs), c two equal, d one
    states = ["a1", "a2", "a3", "b1", "b2", "c1", "c2", "d1"]
    values = [10.0, 10.0, 11.0, 5.0, 5.0 * (1 + 1e-12), 7.0, 7.0, 1.0]
    actions = ["x", "x", "x", "p", "q", "z", "z", "y"]

    found = bloat.measure_part(states, values, actions, lambda s: s[0])

    assert found["states"] == 4
    assert found["groups"] == 3
    assert found["value_groups"] == 1  # b's values differ by 1e-12, below the tolerance
    assert found["action_groups"] == 1
    assert found["changing_groups"] == 2
    assert found["max_rel"] == pytest.approx(1 / 11)


def test_a_value_against_infinity_is_a_difference_but_two_infinities_are_not():
    inf = float("inf")

    both = bloat.measure_part(["a1", "a2", "b1", "b2"], [1.0, inf, inf, inf], [None] * 4, lambda s: s[0])

    assert both["value_groups"] == 1
    assert both["max_rel"] == 0.0  # a group with an infinite value gives no finite difference


def test_a_projection_that_merges_nothing_changes_nothing():
    found = bloat.measure_part(["a", "b", "c"], [1.0, 2.0, 3.0], ["x", "y", "z"], lambda s: s)

    assert found == {"states": 3, "groups": 0, "value_groups": 0, "action_groups": 0, "changing_groups": 0, "max_rel": 0.0}


def test_measure_all_projects_every_column_of_real_states():
    states = [state(slots=(NAMED_A, WANTED)), state(slots=(NAMED_A, WANTED), quality=PlainQuality(20)), state(slots=(NAMED_B, WANTED))]

    found = bloat.measure_all(states, [4.0, 4.0, 4.0], ["go", "go", "go"])

    assert set(found) == set(bloat.COLUMNS)
    assert found["quality"]["states"] == 2 and found["quality"]["groups"] == 1
    assert found[bloat.JUNK]["states"] == 2
    assert found["flags"]["states"] == 3
    assert all(each["changing_groups"] == 0 for each in found.values())


# --- the lumped chain ----------------------------------------------------------------------------


def chain(**moves):
    """`{name: (cost, {successor: weight})}` as a policy; 'goal' is the goal."""
    return {name: Action(name, cost, tuple(Outcome(s, w) for s, w in outs.items())) for name, (cost, outs) in moves.items()}


def is_goal(node) -> bool:
    return node == "goal"


def test_equal_nodes_lump_into_one_block():
    policy = chain(a=(1.0, {"goal": 1, "b": 1}), b=(1.0, {"goal": 2, "c": 2}), c=(1.0, {"goal": 3, "c": 3}))

    assert bloat.lump_chain(policy, "a", is_goal) == (3, 1)


def test_a_chain_is_refined_until_the_blocks_agree():
    policy = chain(a=(1.0, {"goal": 1, "b": 1}), b=(1.0, {"goal": 1, "c": 1}), c=(1.0, {"goal": 1}))

    assert bloat.lump_chain(policy, "a", is_goal) == (3, 3)


def test_a_different_cost_or_chance_keeps_nodes_apart_and_unreached_ones_do_not_count():
    policy = chain(
        a=(1.0, {"goal": 1, "b": 1}), b=(2.0, {"goal": 1}), unreached=(1.0, {"goal": 1}),
    )

    assert bloat.lump_chain(policy, "a", is_goal) == (2, 2)
    assert bloat.lump_chain(chain(a=(1.0, {"goal": 1, "a": 1})), "a", is_goal) == (1, 1)
    assert bloat.lump_chain({}, "goal", is_goal) == (0, 0)


# --- the tables ----------------------------------------------------------------------------------


def part(states, value_groups=0, action_groups=0, max_rel=0.0, groups=1):
    return {
        "states": states, "groups": groups, "value_groups": value_groups, "action_groups": action_groups,
        "changing_groups": max(value_groups, action_groups), "max_rel": max_rel,
    }  # fmt: skip


def document(route, walked, merged, **overrides):
    parts = {column: part(walked) for column in bloat.COLUMNS}
    parts.update(overrides)
    return {
        "route": route, "error": None, "solver": "packed", "walked": walked, "merged": merged, "policy_states": 9, "policy_blocks": 3,
        "route_states": 5, "route_blocks": 2, "route_gaps": 0, "seconds": 12.5, "peak_mb": 900, "parts": parts,
    }  # fmt: skip


def test_the_summary_has_the_routes_in_order_and_shows_the_missing_ones():
    documents = {
        "R14": document("R14", 816153, 589930, junk_names=part(41200), slots=part(30000, value_groups=5, max_rel=0.25)),
        "R12": document("R12", 3, None),
    }

    text, headline = bloat.build_summary(documents)

    lines = text.splitlines()
    assert lines[0] == "# bloat"
    first = [line for line in lines if line.startswith(("| R", "| V"))]
    assert [line.split(" | ")[0] for line in first[: len(bloat.ORDER)]] == ["| " + route for route in bloat.ORDER]
    assert "| R10 | missing | missing |" in text
    assert "816,153" in text and "41,200" in text and "589,930" in text
    assert "5 / 0 (0.25)" in text  # value groups / action groups (largest relative difference)
    assert len(lines) < 150
    assert headline.endswith("\n") and "\n" not in headline.strip()


def test_the_headline_names_the_part_that_removes_most_states_with_no_decision_change():
    documents = {
        "R14": document("R14", 816153, 589930, junk_names=part(41200), slots=part(1000, value_groups=2, max_rel=0.5), flags=part(800000)),
        "R12": document("R12", 3, None),
    }

    assert bloat.headline_of(documents) == "R14: 816 153 состояний; без имён мусорных модов останется 41 200, решения не меняются нигде"


def test_the_headline_says_so_when_every_part_changes_a_decision_and_when_nothing_ran():
    changing = {column: part(500, action_groups=4, groups=4) for column in bloat.COLUMNS}
    documents = {"R04": {**document("R04", 177242, 89778), "parts": changing}}

    line = bloat.headline_of(documents)

    assert line.startswith("R04: 177 242 состояний; ни одну часть нельзя убрать")
    assert line.endswith("групп со сменой решений: 4")
    assert bloat.headline_of({}) == "bloat: ни один маршрут не измерен"
    flat = {"R12": document("R12", 3, None)}
    assert bloat.headline_of(flat) == "R12: 3 состояний; ни одна часть не склеивает состояния, убирать нечего"
    assert len(bloat.headline_of(documents)) <= 200


def test_a_route_that_failed_is_a_row_with_its_error_and_the_summary_reads_the_files(tmp_path):
    failed = {"route": "R10", "error": "no price for the start item", "format": bloat.FORMAT}
    folder = tmp_path / "measure-bloat-R10"
    folder.mkdir()
    (folder / "route-R10.json").write_text(json.dumps(failed), encoding="utf-8")
    other = tmp_path / "measure-bloat-R12"
    other.mkdir()
    (other / "route-R12.json").write_text(json.dumps(document("R12", 3, None)), encoding="utf-8")

    read = bloat.read_documents(tmp_path)
    text, _ = bloat.build_summary(read)
    code = bloat.main(["summary", "--dir", str(tmp_path), "--out", str(tmp_path / "out")])

    assert set(read) == {"R10", "R12"}
    assert "error: no price for the start item" in text
    assert code == 0 and (tmp_path / "out" / "summary.md").read_text(encoding="utf-8") == text
    assert (tmp_path / "out" / "headline.txt").read_text(encoding="utf-8").startswith("R12:")


# --- one fixture route end to end ----------------------------------------------------------------


@pytest.mark.parametrize("solver", ["auto", "packed", "object"])
def test_the_counts_of_a_fixture_route_are_self_consistent(solver):
    bench = next(b for b in BENCHMARKS if b.id == "R12")

    found = bloat.bloat_route(bench, DATA, find_project_root(), load_config({}), price_file(), solver=solver)

    assert found["error"] is None and found["route_error"] is None
    assert found["walked"] >= 1
    assert found["policy_blocks"] <= found["policy_states"] <= found["walked"]
    assert found["route_blocks"] <= found["route_states"]
    assert solver == "auto" or found["solver"] == solver
    assert (found["merged"] is not None) is (found["solver"] == "packed")
    assert set(found["parts"]) == set(bloat.COLUMNS)
    for column, each in found["parts"].items():
        assert 1 <= each["states"] <= found["walked"], column
        assert each["groups"] <= each["states"], column
        assert 2 * each["groups"] <= found["walked"], column  # a group holds at least two walked states
        assert each["value_groups"] <= each["changing_groups"] <= each["groups"], column
        assert each["action_groups"] <= each["changing_groups"], column
    json.dumps(bloat._clean(found), allow_nan=False)


def test_the_run_command_writes_one_file_per_route(tmp_path, monkeypatch):
    bench = next(b for b in BENCHMARKS if b.id == "R12")
    plan_of = bloat.plan_of
    monkeypatch.setattr(bloat, "load_game_data", lambda **_: DATA)
    monkeypatch.setattr(bloat, "plan_of", lambda b, d, root, config, prices, solver="auto": plan_of(b, d, root, config, price_file(), solver))

    code = bloat.main(["run", "--route", bench.id, "--out", str(tmp_path)])

    written = json.loads((tmp_path / "route-R12.json").read_text(encoding="utf-8"))
    assert code == 0 and written["route"] == "R12" and written["walked"] >= 1
    assert bloat.main(["run", "--route", "R99", "--out", str(tmp_path)]) == 2


# --- the workflow --------------------------------------------------------------------------------


def test_the_workflow_is_a_reusable_one_job_per_route_with_the_limits_of_the_chain():
    import yaml

    path = SCRIPT.parents[1] / "workflows" / "measure-bloat.yml"
    text = path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    call = workflow[True]["workflow_call"]  # YAML reads the key `on` as True
    route, summary = workflow["jobs"]["route"], workflow["jobs"]["summary"]

    assert call["inputs"]["trial"] == {"type": "boolean", "required": True}
    assert workflow["permissions"] == {"contents": "read"}
    assert route["timeout-minutes"] == 300 and route["strategy"]["max-parallel"] == 16 and route["strategy"]["fail-fast"] is False
    for route_id in bloat.ORDER:
        assert f'"{route_id}"' in text
    assert "inputs.trial && fromJSON('[\"R10\"]')" in text
    assert summary["needs"] == "route" and summary["if"] == "${{ !cancelled() }}"
    assert "actions/checkout@v7.0.1" in text and "./.github/actions/real-data" in text
    uploads = [step["with"]["name"] for job in (route, summary) for step in job["steps"] if "upload-artifact" in step.get("uses", "")]
    assert uploads == ["measure-bloat-${{ matrix.route }}", "measure-bloat"]


def test_v01_is_measured_from_its_recipe_start_with_the_prices_its_target_names():
    from abstraction_support import real_game_data

    bench = next(b for b in BENCHMARKS if b.id == "V01")
    assert "V01" in bloat.ORDER and bench.start is not None and bench.route is None

    found = bloat.bloat_route(bench, real_game_data(), find_project_root(), load_config({}))

    assert found["error"] is None and found["route_error"] is None
    assert found["walked"] >= 1 and found["policy_blocks"] <= found["policy_states"] <= found["walked"]
    assert set(found["parts"]) == set(bloat.COLUMNS)
