"""The independent tier ladder against the planner's tiers, on every benchmark base (ticket #457, audit #396 class 1).

`tests/independent/ladder.py` works the natural tier ladder out from the raw repoe-fork export with no planner code; the goal oracle
and the reconciliation checks read it. `items/tiers.py` (`tier_table`, `natural_tiers`) and `actions.tiers_of` (the table of an item
with influences) are what the planner reads. The inventory of rebuild step 3 found no test that compares the two: the only agreement
test, `tests/independent/test_ladder_agreement.py`, compares the oracle's and the reconcile package's former copies of the ladder.

For every base that a benchmark target or a buy spec names, with the influence of the file that names it, the mods and the tier of
each mod must be the same on both sides. The planner side is the table the parser uses to resolve a tier leaf (`natural_tiers` of the
base, with `tiers_of` for an influenced item).
"""

from pathlib import Path

import pytest
import yaml
from independent import export as shared_export
from independent import ladder as shared

from crafting_system.actions import tiers_of
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import Influence, Item, Rarity, natural_tiers

REPO = Path(__file__).resolve().parents[1]
TARGETS_DIR = REPO / "examples" / "targets"
BUY_DIR = REPO / "examples" / "buy"


def _yaml_files(folder):
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.yaml"))]


@pytest.fixture(scope="module")
def planner():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


@pytest.fixture(scope="module")
def raw():
    try:
        return shared_export.load_export()
    except shared_export.ExportMissing as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def benchmark_subjects(bases):
    """(base id, influences) of every base a target or a buy spec names, with the influence of the file that names it."""
    subjects = set()
    for target in _yaml_files(TARGETS_DIR):
        for base_id in shared.base_ids_of(bases, target["base"]):
            subjects.add((base_id, frozenset(target.get("influence") or ())))
    for spec in _yaml_files(BUY_DIR):
        ids = shared.bases_named(bases, spec["base_type"]) if spec.get("base_type") else shared.bases_of_category(bases, spec["category"])
        for base_id in ids:
            subjects.add((base_id, frozenset(spec.get("influence") or ())))
    return sorted(subjects, key=lambda subject: (subject[0], sorted(subject[1])))


def planner_tiers(data, base_id, influences):
    """The tier by natural mod id that the parser reads for a base with these influences."""
    table = None
    if influences:
        probe = Item.build(
            data,
            base_id=base_id,
            item_level=84,
            rarity=Rarity.RARE,
            influences=frozenset(Influence(name) for name in influences),
        )
        table = tiers_of(data, probe)
    return dict(natural_tiers(data, base_id, table))


def test_the_independent_ladder_and_the_planner_tiers_are_the_same_on_every_benchmark_base(planner, raw):
    subjects = benchmark_subjects(raw.bases)
    assert len({base_id for base_id, _ in subjects}) > 100  # the category-only buy specs accept 16 rings and 88 amulets
    assert sum(1 for _, influences in subjects if influences) == 2  # the Hunter belt and the Hunter bow
    compared, differences = 0, []
    for base_id, influences in subjects:
        base = raw.bases[base_id]
        tags = shared.item_tags(base["tags"], influences, base["item_class"])
        independent = {
            mod_id: tier for ladder in shared.natural_ladders(raw.mods, tags, base["domain"]).values() for mod_id, tier in ladder.items()
        }
        ours = planner_tiers(planner, base_id, influences)
        compared += len(independent)
        if ours != independent:
            wrong = {m for m in ours.keys() & independent.keys() if ours[m] != independent[m]}
            differences.append((base_id, sorted(influences), sorted(ours.keys() - independent.keys())[:3], sorted(independent.keys() - ours.keys())[:3], sorted(wrong)[:3]))

    assert compared > 20_000  # not vacuous: 28,061 mod tiers on 116 bases
    assert differences == []
