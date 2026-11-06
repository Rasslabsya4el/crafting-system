"""The planner against the goal oracle, on probe items of all 14 benchmark targets (ticket #411, rebuild step 2a).

For every requirement of every `examples/targets/*.yaml` the oracle (`tests/oracle/goal_oracle.py`, which reads only the target text, the
raw repoe-fork export and the owner's rules) lists probe mods: each natural tier of the family at its lowest and highest roll, a roll one
below and at each `min_roll`, every bench craft whose stats overlap the requirement's, the essence mod a target names, a fractured copy
of the top tier, and the target's own start item. `goal_oracle_support.py` builds each probe `Item` by the planner's own path (no tier
set by hand) and asks the planner's `Target.unmet` and the oracle the same question. Where they differ, the planner contradicts a rule
of `docs/owner-rules.md`.

Every disagreement found today is committed by its exact probe id and direction in `tests/fixtures/goal_oracle_known.txt`, and its class
is in `KNOWN` below with its issue, its rule and its cause (a tier comparison, or an empty natural ladder). `test_the_disagreements_are_exactly_the_committed_ones`
fails on any difference in either direction, so a fix offset by a new disagreement in the same requirement shows. Each class has a strict
`xfail` test of its own that fails when the class disappears. A rebuild of steps 3 to 6 of the audit shows as these `xfail`s turning into
passes, and the committed file shrinking. The targets are taken from `examples/targets/*.yaml`, so a 15th target is compared at once.

What is not here: the disagreements of #404 (a target that disagrees with the guide's words). The oracle reads a target as written, so
`r10-fractured-boots.yaml` asking Life tier 1 where the guide says "at least 70" is not a planner-against-oracle disagreement; the
guide-to-target step is not checked here. Implicits, quality, sockets, enchantment and corruption are not judged (#416).
"""

from dataclasses import dataclass

import pytest
from goal_oracle_support import TARGETS, Disagreement, Result, compare_target, load_export, read_known, target_stems
from oracle import goal_oracle as g

from crafting_system.data import MissingDataError, load_game_data

BENCHMARKS = (  # the 14 targets that must be there; the tests below run on every file of the folder
    "j01-cobalt-life-attack-speed", "r03-avoid-shock-boots", "r04-penetrating-quiver", "r05-strength-ring",
    "r06-strength-heavy-belt", "r08-energy-shield-boots", "r09-life-boots", "r10-fractured-boots-70-life",
    "r10-fractured-boots", "r11-reservation-helmet", "r12-lightning-amulet", "r13-life-resist-belt",
    "r14-hunter-bow", "v01-minion-helmet",
)  # fmt: skip
TIER_COMPARISON = "tier comparison"
EMPTY_LADDER = "empty ladder"

# What the oracle does not judge in each target (the rest of the 14 have nothing of the kind); #416.
UNJUDGED = {
    "r03-avoid-shock-boots": ("implicits",),
    "r06-strength-heavy-belt": ("implicits", "quality"),
}


@dataclass(frozen=True)
class Known:
    """A known class of disagreement: whose fault it is, and where the oracle's "not met" comes from.

    `cause` is `tier comparison` (the leaf has a natural ladder at the item level and the probe's tier or values lose on it) or
    `empty ladder` (the leaf's family has no natural mod on this base at the item level, so only `mod:` can meet it; OR-2).
    """

    issue: str
    rules: str
    cause: str
    why: str


BENCH = "bench craft"
BELOW_TOP = "natural tier below the top"
START = "start item"
BENCH_AS_TIER_1 = "a bench craft is stored as tier 1 (actions/bench.py:57) and a crafted mod meets a requirement with no `not_crafted`"

KNOWN: dict[tuple[str, str, str], Known] = {
    # R05: the file's own header says a bench craft "counts as tier 1 ... whatever its range" (r05-strength-ring.yaml:26, :61-72).
    ("r05-strength-ring", "requirements[2].of[0]", BENCH): Known("#403", "OR-1, OR-2", TIER_COMPARISON, "R05's bench Life, +(15-25) to +(41-55) or with Mana regeneration, meets Life T1, +(100-114): " + BENCH_AS_TIER_1),
    ("r05-strength-ring", "requirements[2].of[1]", BENCH): Known("#403", "OR-1, OR-2", TIER_COMPARISON, "a bench Fire Resistance meets Fire Resistance T2, +(42-45)%: " + BENCH_AS_TIER_1),
    ("r05-strength-ring", "requirements[2].of[2]", BENCH): Known("#403", "OR-1, OR-2", TIER_COMPARISON, "a bench Cold Resistance meets Cold Resistance T2: " + BENCH_AS_TIER_1),
    ("r05-strength-ring", "requirements[2].of[3]", BENCH): Known("#403", "OR-1, OR-2", TIER_COMPARISON, "a bench Lightning Resistance meets Lightning Resistance T2: " + BENCH_AS_TIER_1),
    # R06: the same root; the target file is not in the list of #403, hence #415.
    ("r06-strength-heavy-belt", "requirements[0].of[0]", BENCH): Known("#415", "OR-1", TIER_COMPARISON, "a bench Life craft meets Life T1 on R06's belt: " + BENCH_AS_TIER_1),
    ("r06-strength-heavy-belt", "requirements[0].of[1]", BENCH): Known("#415", "OR-1", TIER_COMPARISON, "a bench Armour craft meets Armour T3 on R06's belt: " + BENCH_AS_TIER_1),
    # R12: "every tier of the mod counts, because no minimum tier is given" (r12-lightning-amulet.yaml:28); the start mod is written as tier 3 (:48-49).
    ("r12-lightning-amulet", "requirements[1]", BELOW_TOP): Known("#403", "OR-1", TIER_COMPARISON, "a Lightning Resistance below the top tier meets a requirement with no tier (the model reads no tier as any tier, targets/model.py:57)"),
    ("r12-lightning-amulet", "requirements[1]", BENCH): Known("#403", "OR-1", TIER_COMPARISON, "a bench Lightning Resistance meets a requirement with no tier: " + BENCH_AS_TIER_1),
    ("r12-lightning-amulet", "requirements[1]", START): Known("#403", "OR-1, OR-3", TIER_COMPARISON, "the start amulet's fractured LightningResist2, written as tier 3 while the data has tier 7, meets the requirement with no tier"),
    # R13: "a crafted damage modifier" read as any tier of two families (r13-life-resist-belt.yaml:53-65), the cheapest craft against the given route's dearer one.
    ("r13-life-resist-belt", "requirements[2].of[0]", BENCH): Known("#403", "OR-2, OR-1", EMPTY_LADDER, "All Damage has no natural mod on a belt, so by OR-2 the target should name the craft with `mod:`; a bench All Damage craft meets 'any tier of All Damage': " + BENCH_AS_TIER_1),
    ("r13-life-resist-belt", "requirements[2].of[1]", BELOW_TOP): Known("#403", "OR-1", TIER_COMPARISON, "an Elemental Damage with Attacks tier below the top meets a requirement with no tier"),
    ("r13-life-resist-belt", "requirements[2].of[1]", BENCH): Known("#403", "OR-2, OR-1", TIER_COMPARISON, "a bench Elemental Damage with Attacks craft meets the requirement with no tier: " + BENCH_AS_TIER_1),
}  # fmt: skip


def classify(found: Disagreement) -> tuple[str, str, str]:
    """(target, the requirement the probe was for, the class of probe): the key of `KNOWN`."""
    if found.probe == "start item":
        return (found.target, found.path, START)
    leaf, _, probe = found.probe.partition(" | ")
    if probe.startswith("bench "):
        return (found.target, leaf, BENCH)
    if probe.startswith(("natural ", "fractured natural ")):
        return (found.target, leaf, BELOW_TOP)
    return (found.target, leaf, probe.split(" ")[0])


@pytest.fixture(scope="module")
def results() -> dict[str, Result]:
    try:
        data = load_game_data()
        export = load_export()
    except (MissingDataError, FileNotFoundError) as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")
    return {stem: compare_target(data, export, stem) for stem in target_stems()}


@pytest.fixture(scope="module")
def export() -> g.Export:
    try:
        return load_export()
    except (MissingDataError, FileNotFoundError) as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def oracle_for(export: g.Export, stem: str) -> tuple[g.OracleTarget, g.Oracle]:
    spec = g.OracleTarget.from_text((TARGETS / f"{stem}.yaml").read_text(encoding="utf-8"))
    return spec, g.Oracle(export, spec)


def empty_ladder(export: g.Export, stem: str, leaf_path: str) -> bool:
    """Whether the requirement leaf has no natural mod on the target's base at its item level (only `mod:` can then meet it)."""
    spec, oracle = oracle_for(export, stem)
    leaf = next(leaf for node in spec.requirements for leaf in g.leaves(node) if leaf.path == leaf_path)
    ladders = export.selected_ladders(oracle.base_id, spec.influences, leaf.family, leaf.stat)
    return not any(
        rung.level <= spec.item_level and export.selects(rung.mod_id, leaf.family, leaf.stat) for ladder in ladders.values() for rung in ladder
    )


def unmeetable_leaves(export: g.Export, stem: str) -> set[str]:
    """The requirement leaves of the target that no probe meets under the oracle: a leaf that cannot be met at all."""
    spec, oracle = oracle_for(export, stem)
    probes = g.probe_specs(export, spec)
    return {
        leaf.path
        for node in spec.requirements
        for leaf in g.leaves(node)
        if not any(
            oracle.counts(leaf, g.OMod(p.mod_id, p.values, p.fractured)) for p in probes if p.path == leaf.path
        )
    }


# A leaf the oracle cannot meet with any probe is itself a fault of the target (a requirement that nothing satisfies) or of the oracle.
UNMEETABLE: dict[tuple[str, str], Known] = {
    ("r13-life-resist-belt", "requirements[2].of[0]"): Known(
        "#403", "OR-2", EMPTY_LADDER,
        "`family: AllDamage` has no natural mod on a belt, so under the oracle no mod meets it; a crafted damage modifier is a craft, "
        "and by OR-2 the target should name it with `mod:` (r13-life-resist-belt.yaml:53-65)",
    ),
}  # fmt: skip


def test_all_14_benchmark_targets_are_compared(results):
    assert set(BENCHMARKS) <= set(results)
    for stem in BENCHMARKS:
        assert results[stem].probes > 0, f"{stem}: no probe was built"


@pytest.mark.parametrize("stem", target_stems())
def test_every_probe_is_built_and_the_unjudged_keys_are_the_ones_listed(results, stem):
    assert not results[stem].skipped, "a probe the planner cannot build is a probe nobody checks:\n" + "\n".join(results[stem].skipped)
    assert results[stem].unjudged == UNJUDGED.get(stem, ())


@pytest.mark.parametrize("stem", target_stems())
def test_the_disagreements_are_exactly_the_committed_ones(results, stem):
    """Probe by probe, with the direction: the found set equals `tests/fixtures/goal_oracle_known.txt` for this target, no more, no less."""
    found = {d.id: d.direction for d in results[stem].disagreements}
    committed = read_known().get(stem, {})
    detail = [f"new: {probe} ({found[probe]})" for probe in sorted(found.keys() - committed.keys())]
    detail += [f"gone: {probe}" for probe in sorted(committed.keys() - found.keys())]
    detail += [f"direction changed: {probe} was {committed[probe]}, now {found[probe]}" for probe in sorted(found.keys() & committed.keys()) if found[probe] != committed[probe]]
    assert not detail, "\n".join(detail)


def test_every_committed_disagreement_belongs_to_a_known_class(results):
    """Each committed id is in a class of `KNOWN` (with its issue and rule), each class has an id, and the direction is planner met, oracle not met."""
    classes_found: set[tuple[str, str, str]] = set()
    for stem, ids in read_known().items():
        by_id = {d.id: d for d in results[stem].disagreements}
        for probe_id, direction in ids.items():
            assert direction == "planner=met oracle=not-met", f"{probe_id}: {direction}"
            classes_found.add(classify(by_id[probe_id]))
    assert classes_found == set(KNOWN)


@pytest.mark.parametrize(
    "key",
    [
        pytest.param(
            key,
            id=":".join(key),
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{entry.issue} {entry.rules} ({entry.cause}): {entry.why}"),
        )
        for key, entry in KNOWN.items()
    ],
)
def test_known_disagreement(results, key):
    """The planner and the oracle agree on this class of probes. They do not today; when they do, this test passes and the strict xfail fails."""
    stuck = [d for d in results[key[0]].disagreements if classify(d) == key]
    assert not stuck, f"{len(stuck)} probes split, e.g. {stuck[0].probe}: planner {stuck[0].planner}, oracle {stuck[0].oracle}"


def test_the_cause_of_each_class_is_what_the_registry_says(export):
    for (stem, leaf_path, _), entry in KNOWN.items():
        node_leaf = leaf_path  # a start-item class is keyed by its top-level requirement, which is a leaf in every target that has one
        assert (EMPTY_LADDER if empty_ladder(export, stem, node_leaf) else TIER_COMPARISON) == entry.cause, (stem, leaf_path)


@pytest.mark.parametrize("stem", target_stems())
def test_the_leaves_nothing_can_meet_are_exactly_the_registered_ones(export, stem):
    registered = {leaf for (target, leaf) in UNMEETABLE if target == stem}
    assert unmeetable_leaves(export, stem) == registered


@pytest.mark.parametrize(
    "key",
    [
        pytest.param(
            key,
            id=":".join(key),
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{entry.issue} {entry.rules} ({entry.cause}): {entry.why}"),
        )
        for key, entry in UNMEETABLE.items()
    ],
)
def test_every_requirement_can_be_met_by_some_probe(export, key):
    """A requirement that no probe meets under the oracle cannot be met by any item the oracle knows; it is a strict xfail with its reason."""
    assert key[1] not in unmeetable_leaves(export, key[0])


def test_the_oracle_alone_reads_r05_as_the_rules_do(export):
    """Not a comparison: the oracle's own reading of R05 (Amethyst Ring, item level 75), the numbers of the ticket and of OR-1."""
    spec = g.OracleTarget.from_text((TARGETS / "r05-strength-ring.yaml").read_text(encoding="utf-8"))
    oracle = g.Oracle(export, spec)

    def ladder(family: str):
        return next(iter(export.selected_ladders(oracle.base_id, spec.influences, family, None).values()))

    life = ladder("IncreasedLife")
    assert (life[0].tier, life[0].stats[0][1:]) == (1, (100, 114)) and oracle.top_tier(life) == 1
    for family in ("FireResistance", "ColdResistance", "LightningResistance"):
        resist = ladder(family)
        assert resist[0].level == 84 and oracle.top_tier(resist) == 2 and resist[1].stats[0][1:] == (42, 45)
    # a bench Life craft is not Life T1, at its lowest or its highest roll
    life_leaf = spec.requirements[2].members[0]
    for craft in ("EinharMasterIncreasedLife2", "EinharMasterIncreasedLife3"):
        for roll in (g.OMod(craft, (export.mods[craft]["stats"][0]["min"],)), g.OMod(craft, (export.mods[craft]["stats"][0]["max"],))):
            assert not oracle.counts(life_leaf, roll)
    assert oracle.counts(life_leaf, g.OMod("IncreasedLife7", (100,)))
    assert not oracle.counts(life_leaf, g.OMod("IncreasedLife6", (99,)))


def test_r05_bench_life_is_one_of_the_known_disagreements(results):
    """The R05 fault of the audit: the planner says a bench Life craft meets 'Life T1'; the oracle says it does not."""
    bench_life = [
        d for d in results["r05-strength-ring"].disagreements if d.probe.startswith("requirements[2].of[0] | bench EinharMasterIncreasedLife")
    ]
    assert bench_life, "R05's bench Life no longer splits the planner and the oracle: remove its strict xfail entries"
    assert all(d.planner and not d.oracle for d in bench_life)
    assert KNOWN[("r05-strength-ring", "requirements[2].of[0]", BENCH)].issue == "#403"
