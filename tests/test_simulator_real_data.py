"""The R12 craft on the pinned 3.29.3.3 dump: the simulator against the exact chance of the real pool.

Skipped when the dump is not on this machine (it is never committed, ADR-0003). It is looked for in
`.claude/scratch/repoe-3.29.3.3` of this checkout, and of the main checkout when this one is a
worktree. The five pinned files are COPIED into a pytest temporary folder laid out as the data cache
and read with `load_game_data`, which checks them against the pin; nothing is written next to the dump.

The start item is a rare Paua Amulet at item level 86 with a fractured Lightning Resistance (tier 1,
lowest roll), the policy is "Harvest reforge Lightning until the item holds +1 to Level of all Lightning
Skill Gems" at cost 3.0 a click. Only the fractured mod is kept, so the chance q of one click is the
same every time: `chance_all` gives it exactly (about 3.17%, as the ticket-23 notes record), the
expected cost is 3.0 / q and the number of clicks is geometric with mean 1 / q.

A real draw takes 0.3 to 0.8 ms (the exact outcomes about 66 ms, built once through `Memoized`; the
exact `chance_all` about 1.3 s, loading the dump about 1 s), so about 30 clicks a run cost about 10 ms.
N = 3_000 runs for the mean (measured: about 12 s); N = 5_000 single clicks for the chance (about 1 s).
Tolerances are five standard errors as in the other simulator tests, so a correct result fails about
once in 1.7 million runs; with N = 3_000 five standard errors are about 9% of the mean, a check against
gross mistakes (a wrong pool, cost or goal), not against small ones: the exact side is tested elsewhere.
"""

import math
import shutil
import sys
from pathlib import Path

import pytest
from repoe_support import no_network  # noqa: F401
from simulator_support import FIVE_SIGMA, Memoized

from crafting_system.actions import HarvestReforge
from crafting_system.data.load import load_game_data
from crafting_system.data.pin import PIN
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table
from crafting_system.simulator import Step, simulate

REPO_ROOT = Path(__file__).resolve().parents[1]
DUMP_NAME = f"repoe-{PIN.version}"
AMULET = "Metadata/Items/Amulets/Amulet1"
RESIST = "LightningResist1"
TARGET = "GlobalLightningGemLevel1"
COST = 3.0
RUNS = 3_000
CLICKS = 5_000


def dump_folder() -> Path | None:
    """The folder with the five pinned files, in this checkout's scratch folder or the main checkout's."""
    candidates = [REPO_ROOT / ".claude" / "scratch" / DUMP_NAME]
    if REPO_ROOT.parent.name == "worktrees":  # <main checkout>/.claude/worktrees/<this worktree>
        candidates.append(REPO_ROOT.parents[1] / "scratch" / DUMP_NAME)
    return next(
        (folder for folder in candidates if all((folder / pinned.name).is_file() for pinned in PIN.files)),
        None,
    )


def test_the_dump_is_looked_for_in_this_checkout_and_the_main_one(tmp_path, monkeypatch):
    worktree = tmp_path / "main" / ".claude" / "worktrees" / "feature"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", worktree)
    assert dump_folder() is None

    main_dump = tmp_path / "main" / ".claude" / "scratch" / DUMP_NAME
    main_dump.mkdir(parents=True)
    for pinned in PIN.files[:-1]:
        (main_dump / pinned.name).write_bytes(b"")
    assert dump_folder() is None  # one pinned file missing: the dump is not there

    (main_dump / PIN.files[-1].name).write_bytes(b"")
    assert dump_folder() == main_dump


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    source = dump_folder()
    if source is None:
        pytest.skip(f"the pinned dump {DUMP_NAME} is not on this machine")
    cache = tmp_path_factory.mktemp("cache")
    copy = cache / "repoe-fork" / PIN.version
    copy.mkdir(parents=True)
    for pinned in PIN.files:
        shutil.copy2(source / pinned.name, copy / pinned.name)
    return load_game_data(PIN, cache)


@pytest.fixture(scope="module")
def start(data):
    mod = data.mods[RESIST]
    fractured = ExplicitMod(
        RESIST,
        tier_table(data, AMULET)[RESIST],
        tuple(min(stat.min, stat.max) for stat in mod.stats),
        fractured=True,
    )
    return Item.build(data, base_id=AMULET, rarity=Rarity.RARE, item_level=86, mods=(fractured,))


@pytest.fixture(scope="module")
def chance(data, start):
    """The exact chance that one Harvest reforge Lightning click leaves the target mod, as a float."""
    return float(HarvestReforge("lightning").outcomes(data, start).chance_all([TARGET]))


def holds_target(item) -> bool:
    return any(entry.mod_id == TARGET for entry in item.mods)


def test_the_real_chance_of_one_click_is_the_recorded_three_percent(chance):
    assert chance == pytest.approx(0.0317, abs=0.0001)


def test_harvest_reforge_lightning_until_the_target_costs_the_click_over_the_chance(data, start, chance):
    step = Step(Memoized(HarvestReforge("lightning")), COST)

    report = simulate(data, lambda item: step, start, holds_target, runs=RUNS, seed=2511)

    assert report.successes == RUNS and report.stopped == 0 and report.unfinished == 0
    assert report.cost.agrees_with(COST / chance)
    assert abs(report.mean_steps - 1 / chance) <= 5 * math.sqrt(1 - chance) / chance / math.sqrt(RUNS)


def test_one_click_then_stop_succeeds_with_the_real_chance(data, start, chance):
    step = Step(Memoized(HarvestReforge("lightning")), COST)

    def one_click(item):
        return step if item is start else None

    report = simulate(data, one_click, start, holds_target, runs=CLICKS, seed=2512, confidence=FIVE_SIGMA)

    assert report.successes + report.stopped == CLICKS and report.unfinished == 0
    assert report.success_rate.contains(chance)
    assert report.costs == (COST,) * CLICKS
