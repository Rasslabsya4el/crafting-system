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

The implicits, the quality and the influences of a target (ticket #416) are compared too. R03 and R06 ask an implicit, R06 a catalyst
quality, R06 and R14 an influence. Each has probes of its own (`goal_oracle.implicit_probes`, `quality_probes`, `influence_probes`), and
`test_the_implicit_quality_and_influence_requirements_are_each_met_by_a_probe` fails when a requirement of those kinds has no probe that
both sides call met, so a comparison that asks nothing cannot pass.
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
    `empty ladder` (the leaf's family has no natural mod on this base at the item level, so only `mod:` can meet it; OR-2) or
    `no condition` (a requirement kind of #416 whose planner goal check has no condition for it, so it can never say "not met").
    """

    issue: str
    rules: str
    cause: str
    why: str


NO_CONDITION = "no condition"
BENCH = "bench craft"
BELOW_TOP = "natural tier below the top"
START = "start item"
INFLUENCE = "influence"  # the class of a probe that replaces the finished item's influences
NO_INFLUENCE_CONDITION = (
    "`Target.is_met_by` has no influence condition (targets/model.py `unmet`), so a goal item whose influences are replaced still meets it; "
    "the search compares the influence flag itself (abstraction/_inputs.py:90), the goal check does not"
)
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
    # #416: the influence list of the target. No rule of docs/owner-rules.md speaks of it; the file's header says the list is the item's influences.
    ("r06-strength-heavy-belt", "influence", INFLUENCE): Known("#444", "none (the target header: `influence` lists the item's influences)", NO_CONDITION, NO_INFLUENCE_CONDITION),
    ("r14-hunter-bow", "influence", INFLUENCE): Known("#444", "none (the target header: `influence` lists the item's influences)", NO_CONDITION, NO_INFLUENCE_CONDITION),
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
        if entry.cause == NO_CONDITION:  # a requirement kind of #416: the target must ask for it
            spec, _oracle = oracle_for(export, stem)
            assert leaf_path == "influence" and spec.influences, (stem, leaf_path)
            continue
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


# --- implicits, quality and influence (#416) ---------------------------------------------------------------------------


def other_kind_paths(spec: g.OracleTarget) -> set[str]:
    """The requirements of the kinds of #416 that the target asks and the oracle judges: `implicits[i]`, `quality`, `influence`."""
    paths = {req.path for req in spec.implicits if not req.corrupted}
    if spec.quality is not None:
        paths.add(spec.quality.path)
    if spec.influences:
        paths.add("influence")
    return paths


@pytest.mark.parametrize("stem", target_stems())
def test_the_implicit_quality_and_influence_requirements_are_each_met_by_a_probe(results, export, stem):
    """Every such requirement has at least one probe that planner and oracle both call met: the comparison cannot pass by asking nothing."""
    spec, _ = oracle_for(export, stem)
    assert results[stem].met_paths == other_kind_paths(spec)


def test_the_benchmarks_ask_the_kinds_this_ticket_covers(export):
    """The probes exist because targets ask for them: R03 and R06 an implicit, R06 a quality, R06 and R14 an influence."""
    asked = {stem: other_kind_paths(oracle_for(export, stem)[0]) for stem in BENCHMARKS}
    assert {stem: paths for stem, paths in asked.items() if paths} == {
        "r03-avoid-shock-boots": {"implicits[0]"},
        "r06-strength-heavy-belt": {"implicits[0]", "quality", "influence"},
        "r14-hunter-bow": {"influence"},
    }


def test_the_oracle_alone_reads_the_implicits_of_r03_and_r06_as_the_data_and_the_target_say(export):
    r03, oracle3 = oracle_for(export, "r03-avoid-shock-boots")
    stat = r03.implicits[0]  # "#% chance to Avoid being Shocked", min_roll 40: any of the six Eldritch grades whose roll reaches 40
    assert export.implicit_grade("AvoidShockEldritchImplicit1") == 1 and export.implicit_grade("AvoidShockEldritchImplicit6") == 6
    assert oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit3", (40,)))  # grade 3 holds 39-41
    assert not oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit3", (39,)))  # one below the roll asked
    assert oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit6", (48,)))  # a higher grade counts by its own roll
    assert not oracle3.implicit_counts(stat, g.OImplicit("AvoidShockEldritchImplicit1", (35,)))
    # a "Unique Enemy in your Presence" variant is a conditional effect: the text selector does not count it, `mod:` does (OR-2)
    variant = "AvoidShockEldritchImplicitUniquePresence2"
    assert export.is_presence_variant(variant) and variant in export.implicit_candidates(oracle3.base_id)
    assert not oracle3.implicit_counts(stat, g.OImplicit(variant, (45, 1)))
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
