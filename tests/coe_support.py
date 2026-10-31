"""Support for the Craft of Exile comparison of the prototype's cases (ticket #73).

Two sides of one question, what is the chance that a reroll leaves given mods on a rare item:

* the oracle: Craft of Exile's own probability kernel, run offline from the local copy of the
  site (`tests/coe_oracle/coe_bridge.cjs`, on Node). The copy is git-ignored third-party data and is
  found in `$CRAFTING_COE_DIR`, else in `sources/raw/coe/` of the checkout (for a worktree of
  `.claude/worktrees/`, of the main checkout). It is pinned by the SHA256 of its package.js and
  poec_data.json; a missing or different copy is a clean skip, never a failure.
* our engine: `ChaosOrb` / `ApplyEssence` on a rare item of the real 3.29.3.3 data at item level 86.

A case lists our mod ids (the repoe ids, the same as the prototype's PoB ids) and the Craft of
Exile modifier ids (aids) they correspond to. An aid alone is not a tier (aid 1775 is Life9 on a
helmet and Life8 on an amulet), so `check_correspondences` compares the side, the required level and
the value range of every target and of the forced essence mod between the two sources.
"""

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pytest

from crafting_system.actions import ApplyEssence, ChaosOrb, Outcomes
from crafting_system.actions.pool import PoolFamily
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity, Side

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = Path(__file__).resolve().parent / "coe_oracle" / "coe_bridge.cjs"
COE_DIR_VARIABLE = "CRAFTING_COE_DIR"

# The copy of Craft of Exile the prototype's numbers were frozen on (data version 3.29.0.3, cached
# 2026-09-20).
PACKAGE_SHA256 = "faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639"
DATA_SHA256 = "2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a"

ITEM_LEVEL = 86

HELMET = "Metadata/Items/Armours/Helmets/HelmetStr10"  # Royal Burgonet; CoE base 52
RING = "Metadata/Items/Rings/Ring1"  # Iron Ring; CoE base 1
AMULET = "Metadata/Items/Amulets/Amulet1"  # Paua Amulet; CoE base 2

# Craft of Exile modifier ids of the families the cases name
LIFE, CHAOS, FIRE, COLD = "1775", "661", "1628", "684"

SIDES = ("prefix", "suffix")


@dataclass(frozen=True)
class Case:
    """One of the prototype's twelve comparisons (docs/validation/coe_cases.md of `archive/prototype`)."""

    id: str
    base_name: str
    base_id: str  # the repoe base
    coe_base: str
    action: str  # "chaos" or "essence"
    targets: tuple[str, ...]  # our mod ids, all wanted on the finished item
    coe_targets: dict[str, tuple[str, ...]]  # CoE aids by side
    essence: str | None = None  # our essence name
    coe_essence: str | None = None  # its name in CoE
    forced_mod: str | None = None  # our id of the mod it forces
    coe_excluded: tuple[str, ...] = ()  # aids whose groups the forced mod removes from CoE's pool
    forced_side: str | None = None

    def coe_input(self) -> dict:
        """The case as the bridge reads it."""
        payload = {
            "id": self.id,
            "base_id": self.coe_base,
            "item_level": ITEM_LEVEL,
            "method": self.action,
            "req_max_groups": 3,
            "targets": {side: list(self.coe_targets.get(side, ())) for side in SIDES},
        }
        if self.essence is not None:
            payload |= {
                "exclude_aids": list(self.coe_excluded),
                "forced_side": self.forced_side,
                "forced_essence_name": self.coe_essence,
            }
        return payload


CASES = (
    Case(
        "C01", "Royal Burgonet", HELMET, "52", "chaos", ("IncreasedLife9", "ChaosResist6"),
        {"prefix": (LIFE,), "suffix": (CHAOS,)},
    ),
    Case(
        "C02", "Royal Burgonet", HELMET, "52", "essence", ("IncreasedLife9", "FireResist8"),
        {"prefix": (LIFE,), "suffix": (FIRE,)},
        essence="Deafening Essence of Envy", coe_essence="Envy", forced_mod="ChaosResist6",
        coe_excluded=(CHAOS,), forced_side="suffix",
    ),
    Case(
        "C06", "Iron Ring", RING, "1", "chaos", ("ColdResist8", "ChaosResist6"),
        {"suffix": (COLD, CHAOS)},
    ),
    Case(
        "C09", "Paua Amulet", AMULET, "2", "chaos", ("IncreasedLife8", "ChaosResist6"),
        {"prefix": (LIFE,), "suffix": (CHAOS,)},
    ),
)  # fmt: skip
BY_ID = {case.id: case for case in CASES}


# --- the oracle ---------------------------------------------------------------------------------


def coe_folder() -> Path | None:
    """The folder of the local Craft of Exile copy, None when there is none ($CRAFTING_COE_DIR wins alone)."""
    if os.environ.get(COE_DIR_VARIABLE):
        candidates = [Path(os.environ[COE_DIR_VARIABLE])]
    else:
        candidates = [REPO_ROOT / "sources" / "raw" / "coe"]
        if REPO_ROOT.parent.name == "worktrees" and REPO_ROOT.parent.parent.name == ".claude":
            candidates.append(REPO_ROOT.parents[2] / "sources" / "raw" / "coe")
    return next((folder for folder in candidates if (folder / "package.js").is_file()), None)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_oracle(cases=CASES) -> dict[str, dict]:
    """Craft of Exile's own result for `cases`, by case id; skips when the copy or Node is absent or differs."""
    folder = coe_folder()
    if folder is None:
        pytest.skip(
            f"no local Craft of Exile copy (set {COE_DIR_VARIABLE}, or put it in sources/raw/coe/)"
        )
    for name, wanted in (("package.js", PACKAGE_SHA256), ("poec_data.json", DATA_SHA256)):
        found = sha256(folder / name)
        if found != wanted:
            pytest.skip(f"the Craft of Exile copy differs from the frozen one: {name} is {found}")
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed, and the Craft of Exile kernel runs on it")
    done = subprocess.run(
        [node, str(BRIDGE), str(folder)],
        input=json.dumps({"cases": [case.coe_input() for case in cases]}),
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=300,
    )  # fmt: skip
    assert done.returncode == 0, f"the CoE bridge failed: {done.stderr.strip()}"
    return {entry["id"]: entry for entry in json.loads(done.stdout)["cases"]}


# --- our side -----------------------------------------------------------------------------------


def rare_item(data: GameData, case: Case) -> Item:
    """A rare item of the case's base at item level 86 with no explicit mod."""
    return Item.build(
        data, base_id=case.base_id, item_level=ITEM_LEVEL, rarity=Rarity.RARE, mods=()
    )


def our_outcomes(data: GameData, case: Case) -> Outcomes:
    action = ChaosOrb() if case.essence is None else ApplyEssence(case.essence)
    return action.outcomes(data, rare_item(data, case))


def our_outcomes_as_coe_pools(
    data: GameData, case: Case, *, dropped: tuple[str, ...] = (), split: tuple[str, ...] = ()
) -> Outcomes:
    """A Chaos Orb's outcomes on a pool shaped the way the other sources shape it.

    `dropped` are mods taken out of the pool (weight 0) and `split` are families that become one
    family per mod, so that their mods can sit together on the item. Used only to show where a
    difference with Craft of Exile (and PoB, the prototype's source) comes from; the engine's own
    outcomes are `our_outcomes`.
    """
    assert case.essence is None
    base = Outcomes.reroll(
        data, rare_item(data, case), tag=None,
        factor=lambda mod: Fraction(0 if mod.id in dropped else 1),
    )  # fmt: skip
    pool = []
    for family in base.pool:
        if family.family in split:
            pool.extend(PoolFamily(entry.mod.id, family.side, (entry,)) for entry in family.mods)
        else:
            pool.append(family)
    return Outcomes.over(data, base.retained, tuple(pool), None, None)


def our_chance(outcomes: Outcomes, case: Case) -> Fraction:
    """The exact chance that the finished item holds every target of the case."""
    return outcomes.chance_all(case.targets)


def our_side_totals(outcomes: Outcomes) -> dict[str, Fraction]:
    """The weight of the pool for the draws on the retained item, per side (a forced mod's family is out of it)."""
    return {
        side.value: sum((family.weight for family in outcomes.pool if family.side is side), Fraction(0))
        for side in Side
    }  # fmt: skip


def relative_percent(ours: float, coe: float) -> float:
    """100 * (ours - CoE) / CoE, as in the prototype's table."""
    return 100 * (ours - coe) / coe


# --- the correspondence of the two sources' mods --------------------------------------------------


def ours_of(data: GameData, mod_id: str) -> tuple[str, int, list[list[int]]]:
    mod = data.mods[mod_id]
    return mod.generation_type, mod.required_level, [[stat.min, stat.max] for stat in mod.stats]


def check_correspondences(data: GameData, case: Case, outcomes: Outcomes, coe: dict) -> int:
    """Require every target (and the forced mod) to be the same tier in both sources; return how many were checked.

    The tier is the side, the required level and the value range: Craft of Exile scores the highest
    tier of the aid that the item level allows, we score the exact mod id.
    """
    checked = 0
    for side in SIDES:
        wanted = [mod_id for mod_id in case.targets if data.mods[mod_id].generation_type == side]
        found = coe["targets"][side]
        assert len(wanted) == len(found), f"{case.id}: target count on the {side} side differs"
        for mod_id, tier in zip(wanted, found, strict=True):
            assert (tier["side"], tier["level"], json.loads(tier["range"])) == ours_of(data, mod_id), (
                f"{case.id}: {mod_id} is not the CoE tier of aid {tier['aid']}"
            )
            checked += 1
    if case.forced_mod is not None:
        forced = coe["forced_essence"]
        assert outcomes.forced == case.forced_mod
        assert (forced["side"], forced["level"], json.loads(forced["range"])) == ours_of(
            data, case.forced_mod
        ), f"{case.id}: the forced mod {case.forced_mod} is not the CoE essence modifier {forced['aid']}"
        checked += 1
    return checked
