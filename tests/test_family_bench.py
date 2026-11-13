"""The generated-family benchmark's generator (ticket #824): deterministic from a seed, every v1 method family at three sizes, refused ones marked.

The quick tests work on a small subset of the families (a few seconds); `test_the_full_list_is_the_committed_one` generates every case
(about 15 s) and compares it with `tests/fixtures/family_bench/cases-seed824.json`, the list the committed baseline was measured on, so a change
of the game data, the parser or the generator that changes a case shows here and the baseline is re-run with it.
"""

import argparse
import dataclasses
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data

import family_bench_support as F
from crafting_system.cli import make_plan
from crafting_system.actions.pool import tiers_of
from crafting_system.cli._plan import PlanError
from crafting_system.items.model import Item, Rarity

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "family_bench" / "cases-seed824.json"
BASELINE = ROOT / "tests" / "fixtures" / "family_bench" / "baseline-main.json"

# The method families the ticket names (#824, "Generator"), by batch: every one must have a family in `METHODS`.
TICKET_FAMILIES = {
    "B1": {"basic-orbs", "alchemy-scouring", "essences", "fossil-sets", "bench-metamods", "fracturing", "divine-roll-limits"},
    "B2": {"harvest", "beasts", "eldritch", "influence", "veiled", "quality", "catalysts"},
    "B3": {"imprints", "awakener", "recombinators"},
    "B4": {"vaal", "locus", "bloodstained"},
    "B5": {"strands", "remembrance", "unravelling", "foulborn"},
    "B6": {"sockets"},
    "B7": {"enchants"},
    "B8": {"hinekora-lock"},
    "start": {"start-bought", "start-fractured", "start-vendor-recipe", "start-given"},
}
# The method sets growing by batch of the research note, section 10 (each holds the one before it).
GROWING = ("basic", "essences", "fossils", "harvest", "unveil", "lock", "donors", "strands")
SUBSET = ("basic-orbs", "essences", "veiled", "eldritch", "remembrance", "start-given")


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def subset(names=SUBSET):
    return [m for m in F.METHODS if m.name in names]


def test_every_family_of_the_ticket_is_generated_at_three_sizes_or_more():
    by_batch: dict[str, set[str]] = {}
    for method in F.METHODS:
        by_batch.setdefault(method.batch, set()).add(method.name)
    for batch, names in TICKET_FAMILIES.items():
        assert names <= by_batch.get(batch, set()), f"{batch}: missing {sorted(names - by_batch.get(batch, set()))}"
    assert len(F.SIZES) >= 3
    assert [s.wanted for s in F.SIZES] == [(1, 2), (3, 4), (5, 6)]  # 1 to 6 wanted families
    assert {t for s in F.SIZES for t in range(s.tiers[0], s.tiers[1] + 1)} == {1, 2, 3}  # tiers T1 to T3
    assert F.FOSSILS_KEPT == (4, 7, 12)  # up to 15, 98 and 793 sets: 10 to 1,000 sets
    assert sum(math.comb(F.FOSSILS_KEPT[0], k) for k in range(1, 5)) == 15
    assert sum(math.comb(F.FOSSILS_KEPT[2], k) for k in range(1, 5)) == 793
    assert F.STRANDS[-1] == 100 and F.STRANDS_GROWING == (0, 50, 100)
    growing = [m for m in F.METHODS if m.batch == "growing"]
    assert [m.name for m in growing] == [f"growing-{i + 1}-{name}" for i, name in enumerate(GROWING)]
    for smaller, larger in zip(growing, growing[1:]):
        assert set(smaller.actions) < set(larger.actions), larger.name


def test_the_same_seed_gives_the_same_cases_and_another_seed_others(data):
    first = F.cases(data, 824, methods=subset())
    again = F.cases(data, 824, methods=subset())
    other = F.cases(data, 825, methods=subset())
    assert [c.digest() for c in first] == [c.digest() for c in again]
    assert [c.id for c in first] == [f"{m.name}/{s.name}" for m in subset() for s in F.SIZES]
    assert [c.digest() for c in first] != [c.digest() for c in other]


def test_a_family_alone_gives_the_same_case_as_in_a_longer_list(data):
    """The heavy script generates one case by its family (`family_bench.case_by_id`): it must be the case of the full list."""
    longer = {c.id: c.digest() for c in F.cases(data, 824, methods=subset())}
    alone = {c.id: c.digest() for c in F.cases(data, 824, methods=subset(("veiled",)))}
    assert alone == {key: longer[key] for key in alone}


def test_sizes_grow_and_the_cases_parse_with_their_wanted_mods(data):
    found = F.cases(data, 824, methods=subset())
    for method in SUBSET:
        mine = [c for c in found if c.method == method]
        wanted = [c.wanted for c in mine]
        for case, size in zip(mine, F.SIZES):
            assert size.wanted[0] <= case.wanted <= size.wanted[1], case.id
        assert wanted == sorted(wanted), method
        for case in mine:
            target = F.target_of(case, data)
            assert target.base_id == case.base_id and target.item_level == case.item_level
            assert len(target.requirements) == case.wanted
        for case in mine:  # every tier asked is one the item level rolls: a case is never out of reach by its tier
            item = Item(case.base_id, case.item_level, Rarity.RARE, influences=frozenset(F.target_of(case, data).influences))
            pool, tiers = F.single_family_mods(data, item), tiers_of(data, item)
            for entry in yaml.safe_load(case.target_yaml)["requirements"]:
                if "min_tier" in entry:
                    assert entry["min_tier"] >= min(tiers[m] for m in pool[entry["family"]]), (case.id, entry)
    veiled = [c for c in found if c.method == "veiled"]
    for case in veiled:  # one wanted mod is a veiled one, which only an unveil gives
        assert any(r.mod_ids and all(data.mods[m].domain == "unveiled" for m in r.mod_ids) for r in F.target_of(case, data).requirements), case.id


def test_prices_are_the_snapshots_scaled_by_a_seeded_factor_between_03_and_3(data):
    found = F.cases(data, 824, methods=subset(("essences",)))
    small, large = found[0], found[2]
    merged = F.merge(F.merged_snapshots(), small.primary_snapshot)
    scaled = F.prices_for(small)
    assert scaled.prices[F.UNIT].chaos == merged.prices[F.UNIT].chaos == 1.0
    ratios = [scaled.prices[name].chaos / merged.prices[name].chaos for name in scaled.prices if name != F.UNIT and merged.prices[name].chaos]
    assert ratios and all(0.3 - 1e-12 <= r <= 3 + 1e-12 for r in ratios)
    assert len(set(round(r, 9) for r in ratios)) > len(ratios) // 2  # one factor per currency, not one for all
    assert F.prices_for(small) == scaled  # deterministic
    essences = lambda case: [n for n in F.prices_for(case).prices if F.is_essence_for(data, case.item_class, n)]  # noqa: E731
    assert len(essences(small)) == F.ESSENCES_KEPT[0]
    assert len(essences(large)) > len(essences(small))


def test_refused_marks_agree_with_the_planner_before_any_solve(data):
    """A case marked refused is refused by `make_plan` itself; one not marked passes the checks before the solve (`solve_it=False`)."""
    found = {c.id: c for c in F.cases(data, 824, methods=subset(("eldritch", "remembrance", "start-given", "basic-orbs")))}
    for key in ("eldritch/small", "remembrance/small"):
        case = found[key]
        assert case.refused
        with pytest.raises(PlanError):
            make_plan(data, F.target_of(case, data), F.prices_for(case), start_price=case.start_price, solve_it=False)
    for key in ("start-given/small", "basic-orbs/small"):
        case = found[key]
        assert case.refused is None
        make_plan(data, F.target_of(case, data), F.prices_for(case), start_price=case.start_price, solve_it=False)


def test_the_full_list_is_the_committed_one(data):
    """Every case of seed 824, against the list the baseline was measured on; every in-scope item class is visited."""
    found = F.cases(data, 824)
    committed = F.read_cases(CASES)
    assert [dataclasses.asdict(c) for c in found] == [dataclasses.asdict(c) for c in committed]
    assert {c.item_class for c in found} == set(F.item_classes(data))
    assert {c.method for c in found} == {m.name for m in F.METHODS}


def test_the_baseline_names_its_runs_and_covers_every_case():
    """The committed baseline of `main` (`family_bench.py summary`): its run ids, and one record per committed case, of the same case."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["run_ids"] and baseline["commit"]
    assert baseline["schema"] == F.SCHEMA
    digests = {case.id: case.digest() for case in F.read_cases(CASES)}
    recorded = {r["case"]["id"]: r["case"]["digest"] for r in baseline["records"]}
    assert recorded == digests
    assert all(r.get("status") in ("planned", "stopped", "refused", "failed", "error") for r in baseline["records"]), "a case was not run"


def bench_script():
    spec = importlib.util.spec_from_file_location("family_bench", ROOT / ".github" / "scripts" / "family_bench.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("family_bench", module)
    spec.loader.exec_module(module)
    return module


def test_a_stage_past_its_limit_is_stopped_and_says_so(tmp_path):
    """The parent's `child` runs a child that sleeps past its 1-second stage: the watch writes the record and ends it within seconds."""
    module = bench_script()
    args = argparse.Namespace(
        out=str(tmp_path), seed=824, plan_seconds=1.0, sim_seconds=1.0, risk_seconds=1.0, walk_seconds=1.0, memory_mb=1e9, upper_per_round=False,
    )  # fmt: skip
    record = module.child(args, "sleep/test", "sleep", wall=40)
    assert record["status"] == "stopped", record
    assert "passed 1 s" in record["reason"]
    assert record["stages"]["plan"]["done"] is False
    assert record["wall_seconds"] < 30


def test_the_summary_checks_read_a_record():
    module = bench_script()
    record = {
        "case": {"refused": None}, "status": "planned", "lower": 99.0, "upper": 100.0, "walk": {"optimum": 100.0},
        "simulate": {"z": -1.5, "unfinished": 0, "stopped": 0},
    }  # fmt: skip
    found = module.checks(record)
    assert found == {"lower_le_optimum": True, "optimum_le_upper": True, "gap_to_optimum": 0.0, "exact_mean_equals_optimum": True, "z": -1.5, "z_within": True, "mark_agrees": True}
    record.update(lower=101.0, simulate={"z": 4.5, "unfinished": 0, "stopped": 0}, status="refused")
    found = module.checks(record)
    assert found["lower_le_optimum"] is False and found["z_within"] is False and found["mark_agrees"] is False
