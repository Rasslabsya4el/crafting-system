"""The planner on several cores gives the same answers as on one (ticket #250).

`CRAFTING_WORKERS` sets the size of the process pool. The answer a plan gives (the JSON policy document, the prices,
the policy, the certificate and the approximate marks) must be byte-identical for 1 and for N workers. The cases here use
the committed fixture of `coarse_support.py`, so they need no game data and run on every system; the real routes are in
`test_cli_parallel_real.py`.
"""

import json
from datetime import UTC, datetime

import pytest
from coarse_support import CHAOS, CRAFTS, DATA, HYBRID_CRAFT, MANA, REMOVE
from abstraction_pool import MANA_1

from crafting_system.cli import Offer, build_report, make_plan, policy_document
from crafting_system.cli._decide import Rates
from crafting_system.prices import PriceFile
from crafting_system.targets import parse_target

CH = "Chaos Orb"
TARGET = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - family: ColdResistance
    mod: {HYBRID_CRAFT}
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: {MANA_1}
      tier: 1
      values: {[min(stat.min, stat.max) for stat in DATA.mods[MANA_1].stats]}
"""
OFFERS = [
    Offer("Chaos Orb", CHAOS, {CH: 1}),
    *(Offer(f"Craft {craft.mod_id}", craft, {CH: 2}) for craft in CRAFTS),
    Offer("Remove Crafted Mods", REMOVE, {CH: 1}),
]
PRICES = PriceFile("Test", datetime(2026, 10, 30, tzinfo=UTC), 300.0, {})


def answer_of(plan) -> str:
    """The JSON policy document of a plan, as the CLI writes it, without the seconds it took."""
    document = policy_document(build_report(plan, DATA), None, target_name="t.yaml")
    document.pop("timings_seconds", None)
    return json.dumps(document, sort_keys=True, indent=1)


def planned(monkeypatch, workers: int, **options):
    monkeypatch.setenv("CRAFTING_WORKERS", str(workers))
    target = parse_target(TARGET, DATA, source="t.yaml")
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, **options)


@pytest.fixture
def primed(monkeypatch):
    """The numbers of label distributions each `prime` call made in a process pool."""
    from crafting_system.abstraction import _prime

    made: list[int] = []
    real = _prime.prime

    def counting(abstraction, requests, **options):
        found = real(abstraction, requests, **options)
        made.append(found)
        return found

    monkeypatch.setattr(_prime, "prime", counting)
    return made


def test_one_worker_primes_nothing(monkeypatch, primed):
    planned(monkeypatch, 1)

    assert sum(primed) == 0


@pytest.mark.parametrize("workers", [2, 4])
def test_an_exact_plan_is_byte_identical_for_one_and_many_workers(monkeypatch, primed, workers):
    serial = answer_of(planned(monkeypatch, 1))
    pooled = answer_of(planned(monkeypatch, workers))

    assert pooled == serial


def test_the_solution_values_are_equal_to_the_last_bit(monkeypatch):
    serial = planned(monkeypatch, 1)
    pooled = planned(monkeypatch, 4)

    assert list(pooled.solution.values.items()) == list(serial.solution.values.items())
    assert {s: (a.label, a.cost, a.outcomes) for s, a in pooled.policy.items()} == {
        s: (a.label, a.cost, a.outcomes) for s, a in serial.policy.items()
    }


def approximate_options(monkeypatch):
    """A budget between the forecast of the first coarse level and the exact one, at injected rates (as `test_cli_approximate.py`)."""
    from crafting_system.abstraction import Coarsening

    exact = planned(monkeypatch, 1)
    forecast = exact.abstraction.estimate([exact.start], [offer.action for offer in OFFERS])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    budget = (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2
    return dict(budget=budget, rates=Rates(1.0, 1.0))


def test_an_approximate_answer_is_byte_identical_for_one_and_many_workers(monkeypatch):
    options = approximate_options(monkeypatch)
    serial = planned(monkeypatch, 1, **options)
    pooled = planned(monkeypatch, 4, **options)

    assert serial.approximation is not None  # it really is the approximate answer
    assert answer_of(pooled) == answer_of(serial)
    assert (pooled.approximation.lower, pooled.approximation.upper, pooled.approximation.gap, pooled.approximation.level) == (
        serial.approximation.lower, serial.approximation.upper, serial.approximation.gap, serial.approximation.level,
    )
