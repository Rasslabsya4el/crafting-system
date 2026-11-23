"""The guide's route is priced with its own actions (#1442): a site plan (`benchmark --net`) runs the target alone, so its offers may lack an
action the guide names; the guide is then evaluated on `guide_plan`, its actions from the catalog, and its cost is the one it has on a plan that
offers them all. A guide action the model does not hold is named in the entry ("guide not evaluable: <action> is not modelled"), and the
plan itself stands. On the fixture data, R12: the guide's one action is Harvest Reforge Lightning, and a site plan made with the Chaos Orb alone
does not offer it.
"""

import dataclasses
from pathlib import Path

import pytest
from cli_support import R12, TODAY, price_file, read_json
from targets_support import DATA

import crafting_system.cli._benchmark as benchmark_module
from crafting_system.cli import main
from crafting_system.cli._route import evaluate_route, load_route
from crafting_system.planner import NotModelled, guide_plan, make_plan
from crafting_system.targets import load_target

COMMAND = "bench" + "mark"  # a bare string with the name would trip tests/test_no_timing.py
GUIDE = Path(__file__).resolve().parents[1] / "examples" / "routes" / "r12-lightning-amulet.yaml"
REFORGE = "Harvest Reforge Lightning"


def run_benchmark(out_dir: Path, *arguments: str) -> dict:
    code = main([COMMAND, "--out", str(out_dir), *arguments], data=DATA, prices=price_file(), env={}, today=TODAY)
    assert code == 0
    return next(entry for entry in read_json(out_dir / "benchmark.json")["routes"] if entry["id"] == "R12")


@pytest.fixture
def chaos_only_site(monkeypatch):
    """R12 alone, its site plan made with the Chaos Orb alone: a plan whose offers do not hold the guide's action."""
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", (benchmark_module.BENCHMARKS[0],))
    real = benchmark_module.plan_target
    seen = []

    def chaos_only(data, target, prices, settings):
        plan = real(data, target, prices, dataclasses.replace(settings, methods=("chaos-orb",)) if settings.budget is not None else settings)
        seen.append({priced.label for priced in plan.offers})
        return plan

    monkeypatch.setattr(benchmark_module, "plan_target", chaos_only)
    return seen


def test_a_guide_action_outside_the_site_plan_s_offers_is_priced_all_the_same(tmp_path, chaos_only_site):
    site = run_benchmark(tmp_path / "site", "--net")
    assert REFORGE not in chaos_only_site[0]  # the site plan never offers the guide's action
    assert site["error"] is None and site["guide_not_evaluable"] is None
    given = site["given_route"]
    assert given is not None and given["gaps"] == 0 and given["mean"] is not None
    assert given["first_divergence"] is None  # the planner's policy is of another model: no state of it is compared
    # the same figure as on the guided plan, whose first round leads with the guide's action (#1110): it holds every action the guide takes
    guided = run_benchmark(tmp_path / "guided")
    assert REFORGE in chaos_only_site[1]
    assert given["mean"] == pytest.approx(guided["given_route"]["mean"], rel=1e-9)
    assert given["success"] == pytest.approx(guided["given_route"]["success"], rel=1e-9)
    assert site["solver_not_dearer"] is (site["solver"]["mean"] <= given["mean"] * (1 + 1e-9))


def test_a_guide_action_the_model_does_not_hold_is_named_and_the_plan_stands(tmp_path, monkeypatch, capsys):
    route = tmp_path / "guide.yaml"
    route.write_text("rules:\n  - do: Harvest Reforge Lightning\n  - do: Orb of Nonsense\n", encoding="utf-8")
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", (dataclasses.replace(benchmark_module.BENCHMARKS[0], route=str(route)),))
    entry = run_benchmark(tmp_path / "out", "--net")
    assert entry["guide_not_evaluable"] == "guide not evaluable: Orb of Nonsense is not modelled"
    assert entry["error"] is None and entry["solver"]["mean"] > 0 and entry["record"]["mean"] == entry["solver"]["mean"]
    assert entry["given_route"] is None and entry["solver_not_dearer"] is None
    assert "  guide not evaluable: Orb of Nonsense is not modelled" in capsys.readouterr().out.splitlines()


def test_the_guide_s_plan_offers_its_actions_alone_and_names_each_one_the_model_does_not_hold():
    target = load_target(R12, DATA)
    plan = guide_plan(DATA, target, price_file(), (REFORGE,))
    assert {priced.label for priced in plan.offers} <= {REFORGE, "restart"} and REFORGE in {priced.label for priced in plan.offers}
    assert plan.policy == {}  # nothing is searched: the route is a fixed policy on its own reach
    with pytest.raises(NotModelled) as refused:
        guide_plan(DATA, target, price_file(), (REFORGE, "Orb of Nonsense", "Awakened Nonsense"))
    assert refused.value.labels == ("Awakened Nonsense", "Orb of Nonsense") and str(refused.value) == "Awakened Nonsense, Orb of Nonsense are not modelled"


def test_the_guide_costs_the_same_on_its_own_offers_as_on_a_plan_that_offers_every_method():
    target = load_target(R12, DATA)
    own = guide_plan(DATA, target, price_file(), (REFORGE,))
    wide = make_plan(DATA, dataclasses.replace(target, actions=("chaos-orb", "harvest-reforge", "essence")), price_file(), solve_it=False)
    assert REFORGE in {priced.label for priced in wide.offers} and len(wide.offers) > len(own.offers)
    on_own = evaluate_route(own, load_route(GUIDE, own, DATA), DATA).risk
    on_wide = evaluate_route(wide, load_route(GUIDE, wide, DATA), DATA).risk
    assert on_own.mean.value == pytest.approx(on_wide.mean.value, rel=1e-12) and own.start_price.chaos == wide.start_price.chaos
