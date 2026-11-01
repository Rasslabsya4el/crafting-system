"""The planner on several cores gives the same answers as on one, on the real 3.29.3.3 dump (ticket #250).

Done when 2 of the ticket: R05 is planned with `CRAFTING_WORKERS=1` and `=4` and the JSON policy documents are
byte-identical (the seconds it took are the one field that is not part of the answer). The dump comes from the cache
(`CRAFTING_CACHE_DIR`); the tests skip without it. The approximate answer is compared in `test_cli_parallel.py` on the
committed fixture, and the distributions made ahead in the pool are compared with the ones a serial abstraction makes.
"""

import json
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, Goal
from crafting_system.actions import ActionError
from crafting_system.cli import build_report, make_plan, policy_document
from crafting_system.cli._offers import offers_for
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGETS = ROOT / "examples" / "targets"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def answer(data, name: str, workers: int, monkeypatch) -> str:
    monkeypatch.setenv("CRAFTING_WORKERS", str(workers))
    plan = make_plan(data, load_target(TARGETS / f"{name}.yaml", data), load_price_file(PRICES))
    document = policy_document(build_report(plan, data), None, target_name=f"{name}.yaml")
    document.pop("timings_seconds", None)
    return json.dumps(document, sort_keys=True, indent=1)


def test_r05_is_byte_identical_for_one_and_four_workers(data, monkeypatch):
    from crafting_system.abstraction import _prime

    made: list[int] = []
    real = _prime.prime

    def counting(abstraction, requests, **options):
        made.append(real(abstraction, requests, **options))
        return made[-1]

    monkeypatch.setattr(_prime, "prime", counting)
    pooled = answer(data, "r05-strength-ring", 4, monkeypatch)
    if parallel.can_inherit():
        assert sum(made) > 0  # the pool really made distributions
    assert pooled == answer(data, "r05-strength-ring", 1, monkeypatch)


@pytest.mark.skipif(not parallel.can_inherit(), reason="the distributions are primed in forked workers; there is no fork here")
def test_distributions_primed_in_the_pool_give_the_kernels_of_a_serial_abstraction(data, monkeypatch):
    monkeypatch.setenv("CRAFTING_WORKERS", "2")
    target = load_target(TARGETS / "r12-lightning-amulet.yaml", data)
    goal = Goal.from_target(target)
    actions = [offer.action for offer in offers_for(data, goal, target.base_id, target.start_item, target.actions).offers]
    reading = [action for action in actions if action.reads(data).junk]

    def fresh() -> Abstraction:
        return Abstraction(data, goal, target.base_id, target.item_level, reading)

    primed, plain = fresh(), fresh()
    start = primed.compress(target.start_item)
    requests = [(start, action) for action in actions]

    assert primed.prime(requests, workers=2) >= 2
    for _, action in requests:
        try:
            expected = plain.kernel(start, action)
        except ActionError:
            continue
        assert list(primed.kernel(start, action).items()) == list(expected.items())
