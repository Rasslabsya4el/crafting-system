"""The measurement of the `actions:` key of ticket #475 (`.github/scripts/actions_key.py`): how the key is removed from a copy of a target's text, how the
jobs are dealt over the runners, the table, and the two small routes end to end. No big route runs here (R04 and R14 go to GitHub).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from abstraction_support import real_game_data

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "actions_key.py"
spec = importlib.util.spec_from_file_location("actions_key", SCRIPT)
key = importlib.util.module_from_spec(spec)
sys.modules["actions_key"] = key
spec.loader.exec_module(key)

TARGETS = ROOT / "examples" / "targets"
CARRYING = ("j01-cobalt-life-attack-speed", "r04-penetrating-quiver", "r08-energy-shield-boots", "r09-life-boots", "r13-life-resist-belt", "r14-hunter-bow", "v01-minion-helmet")


def text_of(name: str) -> str:
    return (TARGETS / f"{name}.yaml").read_bytes().decode("utf-8-sig")


@pytest.mark.parametrize("name", CARRYING)
def test_the_key_is_removed_from_the_text_and_nothing_else(name):
    text = text_of(name)

    removed = key.with_variant(text, "removed")

    assert not [line for line in removed.splitlines() if line.startswith("actions:")]
    assert len(removed.splitlines()) < len(text.splitlines())
    kept_lines = text.splitlines()
    gone = [line for line in kept_lines if line not in removed.splitlines()]
    assert gone and gone[0].startswith("actions:")  # the key line goes with its items, and the lines around them stay
    assert key.with_variant(text, "kept") == text


@pytest.mark.parametrize("name", CARRYING)
def test_the_key_is_replaced_by_every_kind_in_one_line(name):
    text = text_of(name)

    replaced = key.with_variant(text, "all", ("alteration-orb", "fossil-set"))

    keys = [line for line in replaced.splitlines() if line.startswith("actions:")]
    assert keys == ["actions: [alteration-orb, fossil-set]"]


def test_a_target_without_the_key_is_refused_for_a_variant_that_changes_it():
    text = text_of("r12-lightning-amulet")

    with pytest.raises(ValueError, match="exactly one"):
        key.with_variant(text, "removed")
    with pytest.raises(ValueError, match="variant must be one of"):
        key.with_variant(text, "nonsense")


def test_the_committed_targets_are_never_written():
    before = {name: text_of(name) for name in CARRYING}
    for name in CARRYING:
        key.with_variant(before[name], "removed")
    assert {name: text_of(name) for name in CARRYING} == before


def test_the_seven_routes_with_a_key_are_the_ones_measured():
    carrying = sorted(path.stem for path in TARGETS.glob("*.yaml") if any(line.startswith("actions:") for line in path.read_text(encoding="utf-8").splitlines()))

    # R07 and R24 came after the measurement (#146); their plans do not fit yet (#769, #770), and their key is #759
    assert [name.split("-")[0].upper() for name in carrying if name.split("-")[0].upper() not in {"R07", "R24"}] == sorted(key.ROUTES)


def test_every_job_is_dealt_once_and_within_the_minutes_of_a_runner():
    jobs = key.all_jobs()
    assert len(jobs) == len(key.ROUTES) * len(key.VARIANTS) * len(key.SOLVERS)

    for count in (16, 15):
        runners = key.bins_for(count)
        flat = [job for each in runners for job in each]
        assert sorted(flat) == sorted(jobs)
        assert all(sum(key.cap_minutes(r, v) for r, v, _ in each) <= key.BIN_MINUTES for each in runners)
    with pytest.raises(ValueError, match="use more runners"):
        key.bins_for(4)


def test_one_variant_is_dealt_over_fewer_runners():
    for variant, count in (("kept", 7), ("removed", 5), ("all", 5)):
        jobs = key.all_jobs((variant,))
        runners = key.bins_for(count, jobs)

        assert len(jobs) == len(key.ROUTES) * len(key.SOLVERS)
        assert sorted(job for each in runners for job in each) == sorted(jobs)


def test_the_envelope_and_the_walk_of_one_job_are_dealt_to_different_runners():
    runners = key.bins_for(16)
    where = {job: number for number, each in enumerate(runners) for job in each}

    assert where[("R14", "kept", "auto")] != where[("R14", "kept", "envelope")]
    assert where[("R04", "removed", "auto")] != where[("R04", "removed", "envelope")]


def record(route, variant, solver, **fields):
    base = {"route": route, "variant": variant, "solver": solver, "finished": True, "error": None, "stop": None, "path": "packed", "offers": 3, "walked": 100, "kept": 40,
            "mean": 50.0, "start_label": "Chaos Orb", "first_actions": ["Chaos Orb"], "labels_used": {"Chaos Orb": 40}, "seconds": 2.0, "peak_mb": 300}  # fmt: skip
    return {**base, **fields}


def test_the_summary_tells_what_the_key_hid():
    records = {
        ("R13", "kept", "auto"): record("R13", "kept", "auto"),
        ("R13", "removed", "auto"): record("R13", "removed", "auto", mean=60.0, start_label="Alteration Orb", labels_used={"Alteration Orb": 40, "Chaos Orb": 2}),
        ("R13", "all", "auto"): record("R13", "all", "auto", finished=False, stop="the cap of 15 minutes", live_states=2_000_000, last_lines=["[ 900 s, 9000 MB] walk: 1,900,000 states found"]),
        ("R13", "all", "envelope"): record("R13", "all", "envelope", finished=False, error="PlanError: the envelope search cannot answer this target"),
    }

    text = key.build_summary(records, "run 1")

    assert "| R13 | removed | auto | done |" in text
    assert "| R13 | all | auto | stopped: the cap of 15 minutes |" in text
    assert "alive 2,000,000" in text
    assert "| R13 | all | envelope | refused |" in text
    assert "50.0000 to 60.0000 (+20.00%)" in text and "Chaos Orb to Alteration Orb" in text
    assert "no comparison: done against stopped" in text
    assert "walk: 1,900,000 states found" in text
    assert "Runs: run 1" in text
    assert "| J01 | kept | auto | missing |" in text


def test_a_cell_says_where_a_job_stopped():
    bound = record("R04", "all", "envelope", finished=False, stop="the cap of 20 minutes", live_states=29_688, seconds=1207.0,
                   last_lines=["[ 1168.0 s, 4925 MB] keys found 4,786 expanded 257 kernels 951,697 members 848,620", "[ 1199.6 s, 4936 MB] stopping: counting the states alive"])  # fmt: skip
    memory = record("R04", "removed", "auto", finished=False, stop="the memory cap of 13,000 MB (resident 13,008 MB)", live_states=15_149_665, last_lines=[])

    assert "stopped (cap 20 min) in the bound: 4,786 keys found, 257 expanded; 1,207 s" in key.cell(bound)
    assert key.cell(memory).startswith("stopped (memory 13 GB) 15,149,665 states alive")
    assert key.cell(record("R04", "kept", "auto")).startswith("50.00; 100 known, 40 kept; 2 s; 300 MB")
    assert key.cell(None) == "missing"
    assert key.cell(record("R04", "removed", "envelope", finished=False, error="PlanError: no policy of the offered actions")) == "refused: no policy reaches the goal"


def test_the_names_of_a_key_are_read_from_a_list_and_from_lines_and_a_probe_adds_one():
    """The parser is tested on its own texts: what a committed target names changes with the guide it quotes (R13 and R14 lost their Transmutation Orb in #576)."""
    as_list = "base: x\nactions: [transmutation-orb, alteration-orb,  regal-orb]  # a flow list\nrequirements: []\n"
    as_lines = "base: x\nactions:\n  - Essence of Insanity  # a comment\n  - Deafening Essence of Rage\n  - remove-crafted-mods\nrequirements: []\n"

    assert key.key_names(as_list) == ["transmutation-orb", "alteration-orb", "regal-orb"]
    assert key.key_names(as_lines) == ["Essence of Insanity", "Deafening Essence of Rage", "remove-crafted-mods"]
    assert key.key_names("base: x\nrequirements: []\n") == []

    probed = key.with_variant("base: x\nactions: [chaos-orb]\n", "plus=divine-orb")

    assert [line for line in probed.splitlines() if line.startswith("actions:")] == ["actions: [chaos-orb, divine-orb]"]


def test_every_committed_target_with_a_key_has_names_the_parser_finds():
    for name in CARRYING:  # whatever a target names today, the parser reads at least one name from its key line
        assert key.key_names(text_of(name)), name
    assert key.key_names(text_of("r12-lightning-amulet")) == []  # a committed target with no key


def test_the_probes_add_each_kind_the_key_does_not_name_under_each_solver():
    text = "base: x\nactions: [chaos-orb, bench-craft]\n"

    jobs = key.probe_jobs(["J01"], lambda _route: text)

    kinds_added = {variant.removeprefix("plus=") for _route, variant, _solver in jobs}
    assert "chaos-orb" not in kinds_added and "bench-craft" not in kinds_added and "divine-orb" in kinds_added
    assert {solver for _route, _variant, solver in jobs} == set(key.SOLVERS)
    assert len(jobs) == len(kinds_added) * len(key.SOLVERS)


def test_the_summary_lists_the_probes_beside_the_kept_mean():
    records = {
        ("J01", "kept", "auto"): record("J01", "kept", "auto"),
        ("J01", "plus=divine-orb", "auto"): record("J01", "plus=divine-orb", "auto", finished=False, stop="the memory cap of 13,000 MB (resident 13,014 MB)", live_states=17_598_901),
        ("J01", "plus=essence", "auto"): record("J01", "plus=essence", "auto", mean=40.0),
    }

    text = key.build_summary(records)

    assert "| J01 | divine-orb | auto | stopped (memory 13 GB) 17,598,901 states alive" in text
    assert "| J01 | essence | auto | 40.00; 100 known, 40 kept; 2 s; 300 MB | mean 50.0000 to 40.0000 |" in text


def test_a_job_with_the_same_mean_and_first_action_says_same():
    records = {("J01", "kept", "auto"): record("J01", "kept", "auto"), ("J01", "removed", "auto"): record("J01", "removed", "auto", mean=50.0 + 1e-12)}

    text = key.build_summary(records)

    assert "| J01 | auto | removed | same | same |" in text


def test_the_batch_writes_one_record_per_job_and_a_stopped_job_says_where_it_was(tmp_path, monkeypatch):
    # a child that never ends: the parent stops it at the cap and writes where it was
    sleeper = tmp_path / "sleeper.py"
    sleeper.write_text("import sys, time\nprint('[   1.0 s, 5 MB] walk: 12 states found', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(key, "__file__", str(sleeper))
    monkeypatch.setattr(key.time, "sleep", lambda _seconds: None)

    found = key.run_job("J01", "kept", "auto", tmp_path / "out", cap=0.001)

    assert found["finished"] is False and found["stop"] == "the cap of 0.001 minutes"
    assert json.loads((tmp_path / "out" / "job-J01-kept-auto.json").read_text(encoding="utf-8"))["stop"] == found["stop"]


@pytest.mark.parametrize("variant", ["kept", "removed"])
def test_a_small_real_route_is_measured_in_each_variant(variant):
    data = real_game_data()

    found = key.measure("J01", variant, "auto", data)

    assert found["finished"] and found["error"] is None
    assert found["kept"] <= found["walked"] and found["mean"] > 0
    assert found["first_actions"][0] == found["start_label"]
    json.dumps(key.clean(found), allow_nan=False)


def test_the_envelope_refusal_of_a_target_is_a_record_not_a_crash():
    data = real_game_data()

    found = key.measure("J01", "all", "envelope", data)

    # since #225 "all" offers the recombinator, whose rule axis the envelope search does not take: the plan is refused before the search
    assert not found["finished"] and "`--solver envelope` does not do that" in found["error"]


def test_v01_is_planned_from_its_recipe_start_in_the_bloat_step_and_here():
    data = real_game_data()

    found = key.measure("V01", "kept", "auto", data)

    assert found["finished"] and found["start_key"] == "vendor:minion_helmet:1"
