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
guide-to-target step is not checked here. Sockets, enchantment, corruption and the start item as a goal state are not judged (#416).

The implicits and the quality of a target (ticket #416) are compared too. R03 and R06 ask an implicit, R06 a catalyst quality. Each has
probes of its own (`goal_oracle.implicit_probes`, `quality_probes`), and
`test_the_implicit_and_quality_requirements_are_each_met_by_a_probe` fails when a requirement of those kinds has no probe that both
sides call met, so a comparison that asks nothing cannot pass. The `influence:` list of a target (R06, R14) is not compared: it is a
start input, the influences on the base the route starts from, not a condition on the finished item (decided on #416 and #444).
"""

from dataclasses import dataclass

import pytest
from goal_oracle_support import TARGETS, Disagreement, Result, compare_target, load_export, read_known, target_stems
from independent.export import ExportMissing
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

# What the oracle does not judge in each target (sockets, enchantment, corruption; none of the 14 has one today); #416.
UNJUDGED: dict[str, tuple[str, ...]] = {}


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

# Empty since ticket #457 (one judgement, the tier from the game data): every class that stood here, the 85 probes of R05, R06, R12 and R13
# (a bench craft stored as tier 1, a tier-less requirement read as "any tier", the start mod's written tier), is gone, and the planner and the
# oracle agree on every probe of all 14 targets. A new disagreement is a new entry here with its issue, rule and cause, and its lines in
# `tests/fixtures/goal_oracle_known.txt`.
KNOWN: dict[tuple[str, str, str], Known] = {}


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
    except (MissingDataError, ExportMissing) as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")
    return {stem: compare_target(data, export, stem) for stem in target_stems()}


@pytest.fixture(scope="module")
def export() -> g.Export:
    try:
        return load_export()
    except (MissingDataError, ExportMissing) as problem:
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
# None today: R13's damage line used to be one (`family: AllDamage` has no natural mod on a belt) until ticket #457 named the craft with `mod:`.
UNMEETABLE: dict[tuple[str, str], Known] = {}


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


def test_the_cause_of_each_class_is_what_the_registry_says(export):
    for (stem, leaf_path, _), entry in KNOWN.items():
        node_leaf = leaf_path  # a start-item class is keyed by its top-level requirement, which is a leaf in every target that has one
        assert (EMPTY_LADDER if empty_ladder(export, stem, node_leaf) else TIER_COMPARISON) == entry.cause, (stem, leaf_path)


@pytest.mark.parametrize("stem", target_stems())
def test_the_leaves_nothing_can_meet_are_exactly_the_registered_ones(export, stem):
    registered = {leaf for (target, leaf) in UNMEETABLE if target == stem}
    assert unmeetable_leaves(export, stem) == registered


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


@pytest.mark.parametrize("stem", ["r05-strength-ring", "r06-strength-heavy-belt", "r12-lightning-amulet", "r13-life-resist-belt"])
def test_the_four_targets_that_stood_in_issues_403_and_415_no_longer_split_the_planner_and_the_oracle(results, stem):
    """R05's bench Life craft met 'Life T1' (12.2 c against the guide route's 135 c); R06, R12 and R13 had the same root. All agree now."""
    assert results[stem].probes > 0 and results[stem].disagreements == []


# --- implicits and quality (#416) --------------------------------------------------------------------------------------


def other_kind_paths(spec: g.OracleTarget) -> set[str]:
    """The requirements of the kinds of #416 that the target asks and the oracle judges: `implicits[i]` and `quality`."""
    paths = {req.path for req in spec.implicits if not req.corrupted}
    if spec.quality is not None:
        paths.add(spec.quality.path)
    return paths


@pytest.mark.parametrize("stem", target_stems())
def test_the_implicit_and_quality_requirements_are_each_met_by_a_probe(results, export, stem):
    """Every such requirement has at least one probe that planner and oracle both call met: the comparison cannot pass by asking nothing."""
    spec, _ = oracle_for(export, stem)
    assert results[stem].met_paths == other_kind_paths(spec)


def test_the_benchmarks_ask_the_kinds_this_ticket_covers(export):
    """The probes exist because targets ask for them: R03 and R06 an implicit, R06 a quality."""
    asked = {stem: other_kind_paths(oracle_for(export, stem)[0]) for stem in BENCHMARKS}
    assert {stem: paths for stem, paths in asked.items() if paths} == {
        "r03-avoid-shock-boots": {"implicits[0]"},
        "r06-strength-heavy-belt": {"implicits[0]", "quality"},
    }


def test_the_oracle_alone_reads_the_implicits_of_r03_and_r06_as_the_data_and_the_target_say(export):
    r03, oracle3 = oracle_for(export, "r03-avoid-shock-boots")
    stat = r03.implicits[0]  # "#% chance to Avoid being Shocked", min_roll 40: any of the six Eldritch grades whose roll reaches 40
    assert export.implicit_grade("AvoidShockEldritchImplicit1") == 1 and export.implicit_grade("AvoidShockEldritchImplicit6") == 6
    assert oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit3", (40,)))  # grade 3 holds 39-41
    assert not oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit3", (39,)))  # one below the roll asked
    assert oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit6", (48,)))  # a higher grade counts by its own roll
    assert not oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit1", (35,)))
    # a "Unique Enemy in your Presence" variant is found by its Presence stat, which makes it a second value, so R03's one-entry
    # `min_roll` rejects it by length whatever the Presence rule says: a real-data assertion of "the text selector does not count it"
    # would be vacuous here, and the data has no variant with one value. The rule itself is tested without a `min_roll` in
    # tests/test_goal_oracle.py::test_or2_a_presence_variant_is_counted_only_when_mod_names_it. Here: `mod:` does count it (OR-2).
    variant = "AvoidShockEldritchImplicitUniquePresence2"
    assert export.is_presence_variant(variant) and variant in export.implicit_candidates(oracle3.base_id)
    named = g.OImplicitReq("implicits[0]", stat="#% chance to Avoid being Shocked", mod=variant, min_roll=(40, None))
    assert oracle3.implicit_counts(named, g.OImplicit(variant, (45, 1)))
    # an implicit that is not one of this base (the amulet's Strength, a corrupted Avoid Shock) never counts
    assert not oracle3.implicit_counts(stat, g.OImplicit("AvoidShockCorruption", (20,)))

    r06, oracle6 = oracle_for(export, "r06-strength-heavy-belt")
    assert export.implicit_candidates(oracle6.base_id) == ["StrengthImplicitBelt1"]  # a belt takes no Eldritch implicit
    strength = r06.implicits[0]  # StrengthImplicitBelt1, min_roll 35: the top of +(25-35)
    assert oracle6.implicit_counts(strength, g.OImplicit("StrengthImplicitBelt1", (35,)))
    assert not oracle6.implicit_counts(strength, g.OImplicit("StrengthImplicitBelt1", (34,)))
    assert not oracle6.implicit_counts(strength, g.OImplicit("StrengthImplicitAmulet1", (30,)))
    # R06 asks 20% Intrinsic quality; the oracle takes the type and the percent, nothing else
    quality = r06.quality
    assert oracle6.quality_met(quality, g.OQuality("intrinsic", 20)) and oracle6.quality_met(quality, g.OQuality("intrinsic", 21))
    assert not oracle6.quality_met(quality, g.OQuality("intrinsic", 19))
    assert not oracle6.quality_met(quality, g.OQuality("abrasive", 20)) and not oracle6.quality_met(quality, None)
    assert not oracle6.quality_met(quality, g.OQuality(None, 20))  # plain quality is another kind


def test_the_catalyst_types_and_the_eldritch_grades_come_from_the_export(export):
    types = export.catalyst_types()
    assert set(types) == {
        "abrasive", "accelerating", "dextral", "fertile", "imbued", "intrinsic", "noxious", "prismatic", "sinistral", "tempering",
        "turbulent", "unstable",
    }  # fmt: skip
    assert all(classes == {"ring", "amulet", "belt"} for classes in types.values())  # the Tainted Catalyst "applies a random type": none
    # the grade is the digit of the id because the roll of one family rises with it (Lesser 33-35 ... Perfect 48-50 for Avoid Shock)
    lows = [min(stat["min"], stat["max"]) for grade in range(1, 7) for stat in export.mods[f"AvoidShockEldritchImplicit{grade}"]["stats"]]
    assert lows == sorted(lows) and len(set(lows)) == 6
