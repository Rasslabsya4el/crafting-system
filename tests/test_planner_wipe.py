"""A wiped item is offered what its new rarity takes (ticket #973, OR-42, OR-37): the offers are listed for every rarity the actions reach.

Until #973 the planner listed its offers once, for the start item, and a kind lists only what the item's rarity takes, so on a Rare start the
Normal item an Orb of Scouring leaves (or the Magic one holding its fractured mod) was offered nothing it takes. Each test plans through the
planner's one entry (`plan_target`) on R12's fixture amulet, with its start item given (no restart: the wipe is the only way back), and checks
the mean against a figure worked by hand from one draw's chance:

* **Scouring, then Alchemy, on a Rare start with no fractured mod.** An Orb of Alchemy on a Normal item draws as a Chaos Orb on a Rare one
  (`actions/alchemy.py`), so a try costs the Scouring and the Alchemy (`s + a`) where a Chaos Orb costs 1 Chaos with the same chance `p`:
  the cheaper try is taken at every state, and the mean is `(s + a) / p` against `1 / p`.
* **Scouring once, then Alterations, on R12's own Rare start, whose Lightning Resistance is fractured.** The Scouring leaves the amulet Magic
  with that suffix; an Alteration then rerolls the prefix alone. The plan scours once and alters until the prefix is the wanted one:
  `s + alt / p_alt`, with `p_alt` the Alteration's chance on the scoured amulet, cheaper here than Chaos Orbs at `1 / p_chaos`.
"""

import dataclasses
import datetime

import pytest
from cli_support import R12, given
from targets_support import DATA

import crafting_system.cli  # noqa: F401 - names the presenter of plans (`planner.present_with`, issue #882)
from crafting_system.abstraction import Goal
from crafting_system.actions import AlterationOrb, ChaosOrb, ScouringOrb
from crafting_system.items import Rarity
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

SCOURING, ALCHEMY, ALTERATION = 0.05, 0.1, 0.01  # Chaos; a Chaos Orb is worth 1 Chaos whatever a file says (`price_offers`)
DAY = "2026-10-30"


def prices() -> PriceFile:
    names = {"Orb of Scouring": SCOURING, "Orb of Alchemy": ALCHEMY, "Orb of Alteration": ALTERATION}
    entries = {name: PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", DAY, 1e9)) for name, chaos in names.items()}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, entries)


def plan(target, methods: tuple[str, ...]):
    return plan_target(DATA, target, prices(), PlanSettings(recipe_starts=False, methods=methods))


def chance(outcomes, goal: Goal) -> float:
    """The chance that one use finishes `goal` (R12's leaves, each a set of mods one of which the item must hold): exact, from the draw seen
    through the leaves each mod passes."""

    def leaves_of(mod_id: str) -> frozenset[int]:
        return frozenset(index for index, leaf in enumerate(goal.leaves) if mod_id in leaf.mod_ids)

    every = frozenset(range(len(goal.leaves)))
    total = 0.0
    for share, part in outcomes.components:
        kept = frozenset().union(*(leaves_of(entry.mod_id) for entry in part.retained.mods))
        for outcome, each in part.distribution(lambda mod: leaves_of(mod.id)).items():
            if kept.union(*(passed for passed, _ in outcome)) == every:
                total += float(share * each)
    return total


def test_a_rare_start_with_no_fractured_mod_is_scoured_and_alchemised_where_that_costs_less_than_a_chaos_orb():
    r12 = load_target(R12, DATA)
    bare = r12.start_item.changed(DATA, rarity=Rarity.RARE, mods=())
    target = given(dataclasses.replace(r12, start_item=bare))
    goal = Goal.from_target(target)
    p = chance(ChaosOrb().outcomes(DATA, bare), goal)
    assert 0 < p < 1

    wiped = plan(target, ("chaos-orb", "scouring-orb", "alchemy-orb"))

    assert wiped.mean_remaining == pytest.approx((SCOURING + ALCHEMY) / p, rel=1e-9)
    assert {"Orb of Scouring", "Orb of Alchemy"} <= {priced.label for priced in wiped.offers}


def test_r12s_fractured_rare_start_is_scoured_once_to_magic_and_altered_where_that_costs_less_than_chaos_orbs():
    target = given(load_target(R12, DATA))
    goal = Goal.from_target(target)
    scoured = ScouringOrb().outcomes(DATA, target.start_item).retained
    assert scoured.rarity is Rarity.MAGIC and [entry.fractured for entry in scoured.mods] == [True]
    p_alt = chance(AlterationOrb().outcomes(DATA, scoured), goal)
    p_chaos = chance(ChaosOrb().outcomes(DATA, target.start_item), goal)
    assert SCOURING + ALTERATION / p_alt < 1 / p_chaos  # the wipe is the cheaper way here

    wiped = plan(target, ("chaos-orb", "scouring-orb", "alteration-orb"))

    assert wiped.mean_remaining == pytest.approx(SCOURING + ALTERATION / p_alt, rel=1e-9)
    assert plan(target, ("chaos-orb",)).mean_remaining == pytest.approx(1 / p_chaos, rel=1e-9)
