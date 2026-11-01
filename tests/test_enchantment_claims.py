"""The enchantment claims and their weight tables (ticket #237, ADR-0050 to ADR-0053).

* The 28 draft claims of the research note (ticket #100) are admitted unchanged in source and quote, plus two new ones.
* The claims the ADRs call approximate carry the mark and a reason.
* The two pool counts (136 weapon, 54 body armour) are recomputed from the pinned dump, and the stored tables
  cover exactly those pools.
* The shares recomputed from the stored tables equal the closed forms of ADR-0051 within the rounding shown there.
* The output of the research script `2026-10-31-enchantments-samples.py` equals the stored tables.

The tests that read the dump skip cleanly when it is not cached (CI fetches it).
"""

import json
import subprocess
import sys
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data

from crafting_system.data.fetch import cache_folder
from crafting_system.rules import SourceKind, load_registry

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "docs" / "research" / "2026-10-31-enchantments-claims.yaml"
SAMPLES_SCRIPT = ROOT / "docs" / "research" / "2026-10-31-enchantments-samples.py"
SAMPLES_DATA = ROOT / "docs" / "research" / "2026-10-31-enchantments-data"

ARMOUR_CLAIM = "enchantment.body_armour_weight_classes"
WEAPON_CLAIM = "enchantment.weapon_weights_depend_on_tag"
NEW_CLAIMS = {
    "enchantment.crafted_slot_with_multimod_takes_the_larger",
    "enchantment.scrap_gain_follows_catalyst_formula",
}
APPROXIMATE = {
    "enchantment.armour_pool_54",
    "enchantment.pool_is_weighted",
    ARMOUR_CLAIM,
    WEAPON_CLAIM,
    "enchantment.extra_crafted_modifier_curio_display_rate",
    "enchantment.quality_enchant_replaces_heist_enchant",
    *NEW_CLAIMS,
}

WEAPON_GROUP = "EnchantmentHeistWeapon"
ARMOUR_GROUP = "EnchantmentHeistArmour"
# The stats of the enchants the 3.29.0 note removed from both orbs.
REMOVED_STATS = {"local_has_X_white_sockets", "local_all_sockets_are_red", "local_all_sockets_are_green", "local_all_sockets_are_blue"}
SOCKET_STATS = {"local_all_sockets_linked", "local_cannot_have_red_sockets", "local_cannot_have_green_sockets", "local_cannot_have_blue_sockets", "local_maximum_sockets_+"}


def thaw(value):
    """A frozen claim value as plain dicts and lists."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


def draft_claims() -> dict[str, dict]:
    return {entry["id"]: entry for entry in yaml.safe_load(DRAFT.read_text(encoding="utf-8"))["rules"]}


def enchantment_rules():
    return {rule_id: rule for rule_id, rule in load_registry().items() if rule_id.startswith("enchantment.")}


# --- the claims ----------------------------------------------------------------------------------


def test_the_registry_holds_the_28_drafts_and_the_two_new_claims():
    drafts = draft_claims()

    assert len(drafts) == 28
    assert set(enchantment_rules()) == set(drafts) | NEW_CLAIMS


@pytest.mark.parametrize("claim_id", sorted(draft_claims()))
def test_an_admitted_draft_keeps_its_source(claim_id):
    draft = draft_claims()[claim_id]
    rule = enchantment_rules()[claim_id]

    assert rule.source_kind is SourceKind(draft["source_kind"])
    assert (rule.url, rule.quote, rule.patch_verified) == (draft["url"], draft["quote"], draft["patch_verified"])
    assert rule.date_checked == draft["date_checked"]
    if claim_id not in {ARMOUR_CLAIM, WEAPON_CLAIM}:  # the two weight claims say more about their value
        assert rule.statement == draft["statement"]


def test_the_claims_the_adrs_name_are_approximate_and_no_other():
    rules = enchantment_rules()

    assert {rule_id for rule_id, rule in rules.items() if rule.approximate} == APPROXIMATE
    for rule_id in APPROXIMATE:
        assert rules[rule_id].approximate_reason.strip()


def test_the_extra_slot_limit_is_the_larger_never_the_sum():
    limits = thaw(enchantment_rules()["enchantment.crafted_slot_with_multimod_takes_the_larger"].value)

    assert limits == {"neither": 1, "extra_slot": 2, "multimod": 3, "both": 3}
    assert limits["both"] == max(limits["extra_slot"], limits["multimod"])


def test_the_scrap_claim_quotes_the_official_3_25_note():
    rule = enchantment_rules()["enchantment.scrap_gain_follows_catalyst_formula"]

    assert rule.source_kind is SourceKind.OFFICIAL
    assert rule.url == "https://www.pathofexile.com/forum/view-thread/3531661"
    assert "Armourer's Scraps" in rule.quote and "based on the item level" in rule.quote


# --- the pools and the tables, against the pinned dump -----------------------------------------------


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def pool(data, group):
    """The mods of a Heist enchant group the orb can still roll: the group less the removed white-socket and one-colour mods."""
    return {mod.id: mod for mod in data.mods.values() if mod.families == (group,) and not ({s.id for s in mod.stats} & REMOVED_STATS)}


def all_of_group(data, group):
    return [mod for mod in data.mods.values() if mod.families == (group,)]


def test_the_two_pool_counts_are_recomputed_from_the_dump(data):
    assert (len(all_of_group(data, WEAPON_GROUP)), len(pool(data, WEAPON_GROUP))) == (181, 136)
    assert (len(all_of_group(data, ARMOUR_GROUP)), len(pool(data, ARMOUR_GROUP))) == (75, 54)


def test_the_removed_mods_are_exactly_the_white_socket_and_one_colour_ones(data):
    for group, white, one_colour in ((WEAPON_GROUP, 12, 33), (ARMOUR_GROUP, 6, 15)):
        mods = all_of_group(data, group)
        with_white = [mod for mod in mods if "local_has_X_white_sockets" in {s.id for s in mod.stats}]
        with_colour = [mod for mod in mods if {s.id for s in mod.stats} & (REMOVED_STATS - {"local_has_X_white_sockets"})]
        assert (len(with_white), len(with_colour)) == (white, one_colour)


def armour_weights():
    value = thaw(enchantment_rules()[ARMOUR_CLAIM].value)
    return {mod_id: Fraction(value["kinds"][kind]["items"], value["kinds"][kind]["enchants"]) for mod_id, kind in value["kind_of"].items()}


def weapon_weights():
    return {mod_id: Fraction(count) for mod_id, count in thaw(enchantment_rules()[WEAPON_CLAIM].value)["count_of"].items()}


def test_the_stored_tables_cover_exactly_the_two_pools(data):
    assert set(armour_weights()) == set(pool(data, ARMOUR_GROUP))
    assert set(weapon_weights()) == set(pool(data, WEAPON_GROUP))


def test_every_armour_kind_is_used_and_its_enchants_are_counted_right():
    value = thaw(enchantment_rules()[ARMOUR_CLAIM].value)
    used = {}
    for kind in value["kind_of"].values():
        used[kind] = used.get(kind, 0) + 1

    assert {kind: entry["enchants"] for kind, entry in value["kinds"].items()} == used


def magnitudes(mod, tag):
    stats = {s.id: s.min for s in mod.stats}
    return stats.get(f"heist_enchantment_{tag}_mod_effect_+%", 0) > 0


def has_downside(mod):
    """Less of another tag, higher attribute requirements, or fewer maximum sockets (ADR-0050)."""
    stats = {s.id: s.min for s in mod.stats}
    return any(key.startswith("heist_enchantment_") and value < 0 for key, value in stats.items()) or stats.get("local_attribute_requirements_+%", 0) > 0 or "local_maximum_sockets_+" in stats


def has_socket_rider(mod):
    return bool({s.id for s in mod.stats} & SOCKET_STATS)


def share(data, group, weights, tag, clean):
    """The chance per click of the set (a positive `tag` magnitude and no downside; `clean` also no socket rider), and its size."""
    mods = pool(data, group)
    chosen = [mod_id for mod_id, mod in mods.items() if magnitudes(mod, tag) and not has_downside(mod) and not (clean and has_socket_rider(mod))]
    return sum(weights[mod_id] for mod_id in chosen) / sum(weights[mod_id] for mod_id in mods), len(chosen)


# (group, tag, clean, percent per click and expected orbs as ADR-0051 shows them, enchants in the set, tolerance in
# percentage points). The tolerance is half the last digit shown, except for "any Life": ADR-0051 prints 23.2% from the raw
# counts of the eight enchants, the stored kind means give 23.3% (the hybrids differ from their kind mean), so it is 0.15.
CLOSED_FORMS = [
    (ARMOUR_GROUP, "life", True, "20.1", "5.0", 4, "0.05"),
    (ARMOUR_GROUP, "life", False, "23.2", "4.3", 8, "0.15"),
    (ARMOUR_GROUP, "defence", True, "18.7", "5.35", None, "0.05"),
    (ARMOUR_GROUP, "resistance", True, "14.4", "7.0", 4, "0.05"),
    (WEAPON_GROUP, "critical", True, "11.8", "8.5", 9, "0.05"),
    (WEAPON_GROUP, "speed", True, "12.7", "7.9", 9, "0.05"),
    (WEAPON_GROUP, "physical", True, "9.4", "10.6", 6, "0.05"),
]


@pytest.mark.parametrize(("group", "tag", "clean", "percent", "orbs", "size", "tolerance"), CLOSED_FORMS)
def test_the_shares_from_the_stored_tables_equal_the_closed_forms(data, group, tag, clean, percent, orbs, size, tolerance):
    weights = armour_weights() if group == ARMOUR_GROUP else weapon_weights()
    p, found = share(data, group, weights, tag, clean)

    assert abs(100 * p - Fraction(percent)) <= Fraction(tolerance)
    assert abs(1 / p - Fraction(orbs)) <= Fraction(5, 10 ** (len(orbs.split(".")[1]) + 1))  # half the last digit shown
    if size is not None:
        assert found == size


def test_the_clean_defence_share_uses_the_kind_means_not_the_raw_counts(data):
    """ADR-0051: the kind means give 18.7% and the raw counts 18.5%; the stored table holds the kind means."""
    p, _ = share(data, ARMOUR_GROUP, armour_weights(), "defence", True)

    assert abs(float(p) - 0.187) < 0.0005


# --- the research script ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def script_output(data):
    """Run the research script on the pinned dump and the CSV copies in the repo; split its output at the tables."""
    folder = cache_folder()
    done = subprocess.run(
        [sys.executable, "-I", str(SAMPLES_SCRIPT), str(folder), str(SAMPLES_DATA)],
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=300,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    printed, _, tables = done.stdout.partition("== claim tables\n")
    return printed, json.loads(tables)


def test_the_script_output_equals_the_stored_tables(script_output):
    _, tables = script_output
    rules = enchantment_rules()

    assert set(tables) == {ARMOUR_CLAIM, WEAPON_CLAIM}
    for claim_id, table in tables.items():
        assert table == thaw(rules[claim_id].value)


def test_the_script_prints_the_numbers_the_draft_claims_state(script_output):
    printed, _ = script_output

    assert "'Can have 1 additional Crafted Modifier': 36 of 5078 = 0.71%" in printed
    assert "'Can have 1 additional Crafted Modifier': 32 of 7742 = 0.41%" in printed
    assert "in the 3.29 pool 136 rows with 6718 items" in printed
    assert "in the 3.29 pool 54 rows with 4318 items" in printed
    assert "chi-square against a uniform pool of 136: 19,025" in printed
    assert "chi-square against a uniform pool of 54: 16,460" in printed
    assert "chi-square of the tally against Curio shares, restricted to the 71 common rows (n=263): 5.0, df 5" in printed
