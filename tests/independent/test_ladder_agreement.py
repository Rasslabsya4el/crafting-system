"""The two tier ladders that were merged into `independent/ladder.py`, compared on every benchmark base (ticket #419).

Before the merge the goal oracle (#411, `tests/oracle/goal_oracle.py`) and the reconciliation checks (#412,
`tests/reconcile/ladder.py`) each built the natural tier ladder from the raw repoe-fork export. The ticket asked to run both on
every base the 14 benchmark targets and their buy specs name, every mod of every ladder, before merging, and to treat a difference
as a finding. Both predecessors are kept below as they were (`oracle_ladders_v411`, `reconcile_groups_v412`), so the comparison
stays runnable and the settled differences stay pinned:

  * the ladders the oracle built are the ladders the reconcile copy built, tier for tier, on every base (no difference of count or order);
  * the reconcile copy also built ladders the oracle never does: for mods of ANOTHER domain than the base and for generation types
    other than prefix and suffix. On a gear base those are flask, map, heist ... mods with a `default` weight, which nobody asks a tier for.
    On the Cobalt Jewel they include ten `IncreasedLife` and nine `LifeRegeneration` mods of domain `item`: the one place where the answer to a
    question the reconcile checks could ask differs. The base's domain decides (the planner agrees: `items/model.py` refuses a mod whose
    domain does not fit the base's domain), so the oracle's reading is kept;
  * an influence adds ladders that no influence-less tag set shows, and changes no tier of a ladder that exists without it;
  * the Battle Royale copies are in neither;
  * a name means one base by the oracle's old rule and a list by the reconcile rule: on the 14 targets and 8 buy specs they agree; across
    the whole export they differ on 61 names, all maps, where the oracle took the first of four ids (a retired `not_for_sale` map) and the
    reconcile rule takes the one on sale.

The real export is in `CRAFTING_CACHE_DIR` (default `local/cache`), read by `independent/export.py`; without it these tests skip with the message CI reads as missing data.
"""

from pathlib import Path

import pytest
import yaml
from independent import export as shared_export
from independent import ladder as shared

REPO = Path(__file__).resolve().parents[2]
TARGETS_DIR = REPO / "examples" / "targets"
BUY_DIR = REPO / "tests" / "reconcile" / "derived_specs"  # the buy specs the planner computes from the targets (#474); the hand-written ones are gone
SIDES = ("prefix", "suffix")


# --- the two predecessors, as they were ----------------------------------------------------------------------------


def first_weight(mod, tags):
    for entry in mod.get("spawn_weights", []):
        if entry["tag"] in tags:
            return entry["weight"]
    return 0


def oracle_ladders_v411(mods, tags, domain):
    """`Export.ladders` of the oracle before #419: (type, generation type) -> tier by mod id, for the base's domain."""
    groups = {}
    for mod_id, mod in mods.items():
        if (
            mod["domain"] == domain
            and mod["generation_type"] in SIDES
            and not mod.get("is_essence_only", False)
            and "Royale" not in mod_id
            and first_weight(mod, tags) > 0
        ):
            groups.setdefault((mod["type"], mod["generation_type"]), []).append(mod_id)
    return {
        key: {m: 1 + sum(mods[o]["required_level"] > mods[m]["required_level"] for o in members) for m in members}
        for key, members in groups.items()
    }


def reconcile_groups_v412(mods, tags):
    """`ladder()` of the reconcile copy before #419, for every mod at once.

    It scoped the ladder of a mod by that mod's own (type, generation type, domain) and kept every mod of the key with a positive
    weight and no `Royale` in its id; so the whole function is one group per key: (type, generation type, domain) -> tier by mod id.
    """
    groups = {}
    for mod_id, mod in mods.items():
        if "Royale" not in mod_id and first_weight(mod, tags) > 0:
            groups.setdefault((mod["type"], mod["generation_type"], mod["domain"]), []).append(mod_id)
    return {
        key: {m: 1 + sum(mods[o]["required_level"] > mods[m]["required_level"] for o in members) for m in members}
        for key, members in groups.items()
    }


def oracle_base_v411(bases, reference):
    """`Export.base_id` of the oracle before #419: an id, else the first released non-Royale base of that name."""
    if reference in bases:
        return reference
    found = sorted(
        base_id
        for base_id, entry in bases.items()
        if entry.get("name") == reference and "Royale" not in base_id and entry.get("release_state", "released") == "released"
    )
    return found[0] if found else None


# --- the real export and the benchmark bases -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def export():
    try:
        raw = shared_export.load_export()
    except shared_export.ExportMissing as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")
    return {"mods": raw.mods, "base_items": raw.bases}


def _yaml_files(folder):
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.yaml"))]


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


@pytest.fixture(scope="module")
def subjects(export):
    return benchmark_subjects(export["base_items"])


def test_the_benchmark_names_many_bases_and_two_influenced_ones(export, subjects):
    assert len(_yaml_files(TARGETS_DIR)) == 16
    assert len({base_id for base_id, _ in subjects}) >= 14  # the computed buy specs name a base each (the old category-only ones accepted 16 rings and 88 amulets)
    assert sum(1 for _, influences in subjects if influences) == 2  # the Hunter belt and the Hunter bow


# --- 1. the ladders both built are the same ladders ------------------------------------------------------------------


def test_the_old_oracle_and_the_old_reconcile_copy_build_the_same_ladder_on_every_benchmark_base(export, subjects):
    """Every mod of every ladder the oracle builds: the same mods, the same tiers, with the oracle's own tags (influence included)."""
    mods, bases = export["mods"], export["base_items"]
    compared, differences = 0, []
    for base_id, influences in subjects:
        tags = shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"])
        domain = bases[base_id]["domain"]
        theirs = reconcile_groups_v412(mods, tags)
        for (type_, side), ours in oracle_ladders_v411(mods, tags, domain).items():
            compared += 1
            if theirs.get((type_, side, domain)) != ours:
                differences.append((base_id, sorted(influences), type_, side))

    assert compared > 400  # not vacuous: over 400 ladders on 14 bases (4000 on 116 while the buy specs were by category)
    assert differences == []


def test_the_shared_ladder_is_the_oracle_ladder_and_holds_every_old_reconcile_ladder_of_the_base_domain(export, subjects):
    mods, bases = export["mods"], export["base_items"]
    for base_id, influences in subjects:
        tags = shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"])
        domain = bases[base_id]["domain"]
        merged = shared.natural_ladders(mods, tags, domain)

        assert merged == oracle_ladders_v411(mods, tags, domain), base_id
        for (type_, side, mod_domain), ladder in reconcile_groups_v412(mods, tags).items():
            if mod_domain == domain and side in SIDES:
                assert merged[(type_, side)] == ladder, base_id


def test_the_merged_ladder_of_a_mod_equals_the_old_reconcile_ladder_of_that_mod_on_a_gear_base(export):
    mods, bases = export["mods"], export["base_items"]
    boots = shared.base_ids_of(bases, "Sorcerer Boots")[0]
    tags = bases[boots]["tags"]
    old = reconcile_groups_v412(mods, tags)

    for mod_id in ("MovementVelocity1", "IncreasedLife1", "FireResist1", "ColdResist2"):
        if mod_id in mods:
            key = (mods[mod_id]["type"], mods[mod_id]["generation_type"], mods[mod_id]["domain"])
            assert shared.ladder_of(mods, tags, bases[boots]["domain"], mod_id) == old[key]


# --- 2. what only the old reconcile copy built: another domain, another generation type -------------------------------


def test_every_ladder_only_the_old_reconcile_copy_built_is_of_another_domain_or_another_generation_type(export, subjects):
    mods, bases = export["mods"], export["base_items"]
    reasons = set()
    for base_id, influences in subjects:
        tags = shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"])
        domain = bases[base_id]["domain"]
        oracle = oracle_ladders_v411(mods, tags, domain)
        for type_, side, mod_domain in reconcile_groups_v412(mods, tags):
            if mod_domain == domain and side in SIDES:
                assert (type_, side) in oracle, (base_id, type_, side)  # an essence-only ladder would be the third reason: there is none
            else:
                reasons.add("other domain" if mod_domain != domain else "other generation type")

    assert reasons == {"other domain", "other generation type"}


def test_no_mod_of_the_export_is_essence_only_and_can_spawn(export):
    mods = export["mods"]

    assert not [m for m, mod in mods.items() if mod.get("is_essence_only") and any(e["weight"] > 0 for e in mod.get("spawn_weights", []))]


def test_the_cobalt_jewel_is_the_one_base_where_a_mod_of_the_other_domain_would_have_a_ladder_a_check_could_ask_for(export, subjects):
    """Gear bases are domain `item`. On the Cobalt Jewel (domain `misc`) the old reconcile copy gave `IncreasedLife1` a ladder of ten
    item-domain tiers; the game, the oracle and the planner give a jewel no item-domain mod."""
    mods, bases = export["mods"], export["base_items"]
    jewel = shared.base_ids_of(bases, "Cobalt Jewel")[0]
    tags = bases[jewel]["tags"]
    types = set()
    for base_id, influences in subjects:
        if bases[base_id]["domain"] == "item":
            continue
        for (type_, side, mod_domain), ladder in reconcile_groups_v412(mods, shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"])).items():
            if mod_domain == "item" and side in SIDES:
                types.add((type_, side))

    old = reconcile_groups_v412(mods, tags)[("IncreasedLife", "prefix", "item")]
    assert bases[jewel]["domain"] == "misc"
    assert types == {("IncreasedLife", "prefix"), ("LifeRegeneration", "suffix")}
    assert len(old) == 10 and "IncreasedLife1" in old
    assert shared.ladder_of(mods, tags, "misc", "IncreasedLife1") == {}
    assert ("IncreasedLife", "prefix") not in shared.natural_ladders(mods, tags, "misc")


# --- 3. influence -------------------------------------------------------------------------------------------------------


def test_an_influence_adds_ladders_of_its_own_and_changes_no_tier_of_a_ladder_that_exists_without_it(export, subjects):
    mods, bases = export["mods"], export["base_items"]
    influenced = [(base_id, influences) for base_id, influences in subjects if influences]
    assert {base_id.split("/")[-1] for base_id, _ in influenced} == {"Belt4", "Bow16"}
    for base_id, influences in influenced:
        domain = bases[base_id]["domain"]
        plain = shared.natural_ladders(mods, shared.item_tags(bases[base_id]["tags"]), domain)
        raised = shared.natural_ladders(mods, shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"]), domain)

        assert set(plain) < set(raised)  # new ladders ...
        assert all(raised[key] == plain[key] for key in plain)  # ... and no tier moved in the old ones
        for key in set(raised) - set(plain):
            assert all(first_weight(mods[m], shared.item_tags(bases[base_id]["tags"])) == 0 for m in raised[key])


# --- 3b. which classes take an influence (ticket #433) ----------------------------------------------------------------------


INFLUENCE_SUFFIXES = tuple(shared.INFLUENCE_TAG.values())


def test_the_classes_that_take_an_influence_are_those_whose_base_tags_the_mods_give_an_influence_weight_to(export):
    """`INFLUENCE_CLASSES` is read from the data: a class takes an influence when one of its base tags with an influence suffix
    is a tag in the spawn weights of some mod. The 24 classes of the list are exactly those."""
    mods, bases = export["mods"], export["base_items"]
    weighted = {entry["tag"] for mod in mods.values() for entry in mod.get("spawn_weights", ())}
    derived = {
        base["item_class"]
        for base in bases.values()
        if any(f"{tag}_{suffix}" in weighted for tag in base["tags"] for suffix in INFLUENCE_SUFFIXES)
    }

    assert derived == shared.INFLUENCE_CLASSES


def test_a_jewel_a_flask_a_tincture_and_every_other_class_without_influence_tags_refuses_an_influence(export):
    bases = export["base_items"]
    refused = {base["item_class"] for base in bases.values() if base["item_class"] not in shared.INFLUENCE_CLASSES}

    assert {"Jewel", "AbyssJewel", "LifeFlask", "ManaFlask", "Tincture"} <= refused
    for item_class in sorted(refused):
        with pytest.raises(shared.InfluenceError, match="takes no influence"):
            shared.item_tags(["default"], ["hunter"], item_class)
    for base in bases.values():
        if base["domain"] in {"misc", "abyss_jewel", "affliction_jewel", "flask", "tincture"}:
            assert base["item_class"] in refused, base["name"]


# --- 4. Battle Royale copies --------------------------------------------------------------------------------------------


def test_a_royale_copy_with_a_spawn_weight_is_in_no_ladder(export, subjects):
    mods, bases = export["mods"], export["base_items"]
    seen = set()
    for base_id, influences in subjects:
        tags = shared.item_tags(bases[base_id]["tags"], influences, bases[base_id]["item_class"])
        spawnable = {m for m, mod in mods.items() if "Royale" in m and first_weight(mod, tags) > 0}
        seen |= spawnable
        in_ladders = {m for ladder in shared.natural_ladders(mods, tags, bases[base_id]["domain"]).values() for m in ladder}

        assert not spawnable & in_ladders
    assert seen  # not vacuous: the data does give some a positive weight (issue #248)


# --- 5. a base given by name ----------------------------------------------------------------------------------------------


def test_the_old_oracle_rule_and_the_shared_rule_name_the_same_base_for_every_name_the_benchmark_uses(export):
    bases = export["base_items"]
    references = [target["base"] for target in _yaml_files(TARGETS_DIR)] + [spec["base_type"] for spec in _yaml_files(BUY_DIR) if spec.get("base_type")]

    assert len(references) == 16 + 14  # the computed specs: one per bought start item, the two R10 files sharing one
    for reference in references:
        merged = shared.base_ids_of(bases, reference)
        assert merged and oracle_base_v411(bases, reference) in merged
        assert oracle_base_v411(bases, reference) == merged[0]


def test_the_two_rules_differ_only_on_maps_across_the_whole_export(export):
    bases = export["base_items"]
    differing = {}
    for name in {base["name"] for base in bases.values()}:
        old = oracle_base_v411(bases, name)
        new = shared.base_ids_of(bases, name)
        if old != (new[0] if new else None):
            differing[name] = {bases[base_id]["item_class"] for base_id in bases if bases[base_id]["name"] == name}

    assert differing  # not vacuous
    assert set().union(*differing.values()) == {"Map"}
