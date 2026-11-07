"""The naive crafter on a tiny hand-made export, one test per rule (ticket #555).

No real dump is read. The export is a made-up ring with the mods below, so every rule of `rules.py` has a case whose answer is worked out
by hand in the test. Rolls are tested with fixed seeds and a z limit of 4.5 (the chance of a false alarm of one is about 7e-6), laws are
tested exactly where an exact answer exists.

  prefixes (ring item level 80)            suffixes
    PA  group GA  1000                       SC  group GC 1000      SC2 group GC 1000 (the same group as SC)
    PB  group GB  1000                       SD  group GD 2000
    PF  group GF  1000                       SH  group GH 1000
    PG  group GG  1000                       SI  group GI 1000
    PD  group GDef 500 (spawn "default")     (the pool: prefixes 5,500 and suffixes 6,000 in all)
    PM  group GM  1000 level 50 (needs level 50)
  left out of the pool: ESS (essence-only), SCRoyale (a Battle Royale copy), HIGH (level 90), FLASK (domain flask),
  ZERO (first spawn entry 0), UNIQ (generation type unique), EssForced (the essence's forced mod, level 90), BenchX (a crafted mod).
"""

import json
import math
from random import Random

import pytest
import yaml
from independent.export import RawExport
from naive_crafter import __main__ as command
from naive_crafter import tally as t
from naive_crafter.craft import Crafter, Held, Item, Laws, Pool, Refused
from naive_crafter.play import Gap, Judge, Player, RouteError, lacking, read_route
from naive_crafter.world import RESTART, UnpricedError, World

RING = "Metadata/Items/Rings/TestRing"
CHAOS = "Metadata/Items/Currency/CurrencyRerollRare"
ESS_LOW = "Metadata/Items/Currency/CurrencyEssenceLow"
Z = 4.5


def mod(group, side, level, weight, *, domain="item", essence=False, low=1, high=10, spawn=None, text=None, generation_weights=()):
    return {
        "domain": domain,
        "generation_type": side,
        "groups": [group],
        "type": group,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": w} for tag, w in (spawn if spawn is not None else (("ring", weight), ("default", 0)))],
        "generation_weights": [{"tag": tag, "weight": w} for tag, w in generation_weights],
        "stats": [{"id": f"stat_{group}", "min": low, "max": high}],
        "text": text if text is not None else f"+({low}-{high}) to {group}",
        "is_essence_only": essence,
        "name": group,
    }


def tiny_mods() -> dict:
    return {
        "PA": mod("GA", "prefix", 1, 1000),
        "PB": mod("GB", "prefix", 1, 1000),
        "PF": mod("GF", "prefix", 1, 1000),
        "PG": mod("GG", "prefix", 1, 1000),
        "PD": mod("GDef", "prefix", 1, 0, spawn=(("amulet", 1000), ("default", 500))),
        "PM": mod("GM", "prefix", 50, 1000),
        "SC": mod("GC", "suffix", 1, 1000),
        "SC2": mod("GC", "suffix", 30, 1000),
        "SD": mod("GD", "suffix", 1, 2000),
        "SH": mod("GH", "suffix", 1, 1000),
        "SI": mod("GI", "suffix", 1, 1000),
        "ESS": mod("GE0", "suffix", 1, 1000, essence=True),
        "SCRoyale": mod("GR", "suffix", 1, 1000),
        "HIGH": mod("GHigh", "prefix", 90, 1000),
        "FLASK": mod("GFl", "prefix", 1, 1000, domain="flask"),
        "ZERO": mod("GZ", "prefix", 1, 0, spawn=(("ring", 0), ("default", 1000))),
        "UNIQ": mod("GU", "unique", 1, 1000),
        "EssForced": mod("GE", "suffix", 90, 0, essence=True, spawn=(("default", 0),), low=7, high=8),
        "BenchX": mod("GBench", "suffix", 1, 0, domain="crafted", spawn=(), low=3, high=3, text="(3-3)% bench"),
    }


def currency(name):
    return {"name": name, "tags": ["currency"], "item_class": "StackableCurrency", "domain": "undefined", "release_state": "released"}


def tiny_raw(mods=None) -> RawExport:
    bases = {
        RING: {"name": "Test Ring", "tags": ["ring", "default"], "item_class": "Ring", "domain": "item", "release_state": "released", "implicits": []},
        CHAOS: currency("Chaos Orb"),
    }
    options = [{"actions": {"add_explicit_mod": "BenchX"}, "cost": {CHAOS: 2}, "item_classes": ["Ring"], "bench_tier": 1}]
    essences = {
        "Metadata/Items/Currency/CurrencyEssenceHigh": {"name": "Shrieking Essence of Test", "level": 6, "item_level_restriction": None, "mods": {"Ring": "EssForced"}},
        ESS_LOW: {"name": "Weeping Essence of Test", "level": 3, "item_level_restriction": 35, "mods": {"Ring": "EssForced"}},
    }
    return RawExport(mods if mods is not None else tiny_mods(), bases, options, essences, "tiny")


def crafter(mods=None, laws=None, level=80) -> Crafter:
    return Crafter(tiny_raw(mods), RING, level, laws=laws)


def held(*ids, fractured=()):
    return tuple(Held(mod_id, (1,), fractured=mod_id in fractured) for mod_id in ids)


def z_of(hits: int, n: int, p: float) -> float:
    return (hits - n * p) / math.sqrt(n * p * (1 - p))


# --- the pool -----------------------------------------------------------------------------------------------------------


def test_the_pool_holds_the_mods_the_rules_allow_with_their_weights():
    pool = crafter().pool()

    assert dict(zip(pool.ids, pool.weights, strict=True)) == {
        "PA": 1000, "PB": 1000, "PF": 1000, "PG": 1000, "PD": 500, "PM": 1000, "SC": 1000, "SC2": 1000, "SD": 2000, "SH": 1000, "SI": 1000,
    }  # fmt: skip
    for left_out in ("ESS", "SCRoyale", "HIGH", "FLASK", "ZERO", "UNIQ", "EssForced", "BenchX"):
        assert left_out not in pool.ids


def test_the_first_matching_spawn_entry_decides_the_weight_and_a_later_one_is_ignored():
    mods = tiny_mods()
    mods["PA"]["spawn_weights"] = [{"tag": "amulet", "weight": 7}, {"tag": "ring", "weight": 300}, {"tag": "default", "weight": 9000}]

    assert dict(zip(crafter(mods).pool().ids, crafter(mods).pool().weights, strict=True))["PA"] == 300


def test_the_generation_weight_multiplies_by_value_over_100_and_a_zero_removes_the_mod():
    mods = tiny_mods()
    mods["PA"]["generation_weights"] = [{"tag": "ring", "weight": 50}]
    mods["PB"]["generation_weights"] = [{"tag": "ring", "weight": 0}]
    pool = crafter(mods).pool()
    weights = dict(zip(pool.ids, pool.weights, strict=True))

    assert weights["PA"] == 500 and "PB" not in weights and weights["PF"] == 1000


def test_the_item_level_gates_the_mods_by_required_level():
    low = crafter(level=49).pool().ids
    edge = crafter(level=50).pool().ids

    assert "PM" not in low and "PM" in edge and "SC2" in low


def test_an_essence_cap_below_the_item_level_gates_the_random_mods_and_a_cap_above_it_does_not():
    assert "PM" not in crafter().pool(35).ids
    assert "PM" in crafter().pool(95).ids  # the item level (80) is the lower one


# --- the draw ---------------------------------------------------------------------------------------------------------------


def test_a_draw_picks_a_mod_with_its_weight_over_the_sum_of_the_allowed_weights():
    pool = crafter().pool()
    rng = Random(1)
    n = 40_000
    picks = [pool.draw(rng, frozenset({"GA"}), ()) for _ in range(n)]
    total = 5500 + 6000 - 1000  # the group GA is blocked

    assert "PA" not in picks
    for mod_id, weight in (("PB", 1000), ("SD", 2000), ("PD", 500)):
        assert abs(z_of(picks.count(mod_id), n, weight / total)) < Z, mod_id


def test_a_full_side_closes_and_the_other_side_is_the_whole_pool():
    pool = crafter().pool()
    rng = Random(2)
    picks = {pool.draw(rng, frozenset(), ("prefix",)) for _ in range(2000)}

    assert picks <= {"SC", "SC2", "SD", "SH", "SI"} and len(picks) == 5


def test_when_nearly_all_the_weight_is_not_allowed_the_listed_draw_still_gives_the_exact_chance():
    mods = {"Heavy": mod("GHeavy", "prefix", 1, 1_000_000), "Light": mod("GLight", "prefix", 1, 1), "Lighter": mod("GLighter", "prefix", 1, 3)}
    pool = Pool(crafter(mods).book, crafter(mods).tags, "item", 80)
    rng = Random(3)
    n = 20_000
    picks = [pool.draw(rng, frozenset({"GHeavy"}), ()) for _ in range(n)]

    assert "Heavy" not in picks and abs(z_of(picks.count("Lighter"), n, 0.75)) < Z


def test_a_pool_with_nothing_allowed_gives_none():
    pool = crafter().pool()

    assert pool.draw(Random(4), frozenset(), ("prefix", "suffix")) is None


def test_the_rolls_are_uniform_integers_with_both_ends_and_a_fixed_stat_is_fixed():
    book = crafter().book
    rng = Random(5)
    rolls = [book.roll("PA", rng)[0] for _ in range(20_000)]

    assert set(rolls) == set(range(1, 11))
    assert abs(z_of(rolls.count(10), 20_000, 0.1)) < Z and abs(z_of(rolls.count(1), 20_000, 0.1)) < Z
    assert crafter().book.roll("BenchX", rng) == (3,)


# --- the orbs -------------------------------------------------------------------------------------------------------------------


def test_transmutation_makes_a_magic_item_of_one_or_two_mods_with_equal_chance_and_one_per_side_at_most():
    c = crafter()
    rng = Random(6)
    made = [c.transmute(Item("normal"), rng) for _ in range(20_000)]
    counts = [len(item.mods) for item in made]

    assert all(item.rarity == "magic" for item in made)
    assert set(counts) == {1, 2} and abs(z_of(counts.count(2), 20_000, 0.5)) < Z
    assert all(c.side_counts(item.mods)[side] <= 1 for item in made for side in ("prefix", "suffix"))
    with pytest.raises(Refused):
        c.transmute(Item("magic"), rng)


def test_alteration_keeps_the_fractured_mod_removes_the_rest_and_counts_the_kept_in_the_total():
    c = crafter()
    rng = Random(7)
    start = Item("magic", (Held("PA", (4,), fractured=True), Held("SC", (4,))))
    made = [c.alter(start, rng) for _ in range(20_000)]

    assert all(item.mods[0] == Held("PA", (4,), fractured=True) for item in made)
    assert all(len(item.mods) in (1, 2) for item in made)
    two = sum(len(item.mods) == 2 for item in made)
    assert abs(z_of(two, 20_000, 0.5)) < Z  # the total is 1 or 2 with the fractured mod counted: one more mod half of the time
    assert all(c.book.side(item.mods[1].mod_id) == "suffix" for item in made if len(item.mods) == 2)  # the prefix side is full
    with pytest.raises(Refused):
        c.alter(Item("rare"), rng)


def test_alteration_of_a_magic_item_without_a_fractured_mod_rerolls_everything():
    c = crafter()
    rng = Random(8)
    made = [c.alter(Item("magic", held("PA", "SC")), rng) for _ in range(5000)]

    assert any(item.mods and item.mods[0].mod_id != "PA" for item in made) and all(not any(h.crafted for h in item.mods) for item in made)


def test_augmentation_adds_one_mod_on_the_open_side_and_is_refused_on_a_full_item():
    c = crafter()
    rng = Random(9)
    start = Item("magic", held("PA"))
    made = [c.augment(start, rng) for _ in range(2000)]

    assert all(len(item.mods) == 2 and c.book.side(item.mods[1].mod_id) == "suffix" for item in made)
    assert {item.mods[1].mod_id for item in made} == {"SC", "SC2", "SD", "SH", "SI"}
    with pytest.raises(Refused):
        c.augment(Item("magic", held("PA", "SC")), rng)
    assert len(c.augment(Item("magic"), rng).mods) == 1  # an empty magic item has two open slots


def test_regal_keeps_every_mod_adds_one_and_makes_the_item_rare_with_both_sides_open():
    c = crafter()
    rng = Random(10)
    start = Item("magic", held("PA", "SC"))
    made = [c.regal(start, rng) for _ in range(3000)]

    assert all(item.rarity == "rare" and item.mods[:2] == start.mods and len(item.mods) == 3 for item in made)
    assert all(item.mods[2].mod_id not in ("SC", "SC2", "PA") for item in made)  # the groups of the item are blocked
    with pytest.raises(Refused):
        c.regal(Item("rare", held("PA")), rng)


def test_a_regal_with_no_legal_mod_is_refused():
    mods = {key: value for key, value in tiny_mods().items() if key in ("PA", "SC")}
    c = crafter(mods)

    with pytest.raises(Refused):
        c.regal(Item("magic", held("PA", "SC")), Random(11))


def test_a_chaos_orb_leaves_four_five_or_six_mods_in_the_ratio_eight_three_one():
    c = crafter()
    rng = Random(12)
    n = 30_000
    sizes = [len(c.chaos(Item("rare", held("PA", "PB", "SC", "SD")), rng).mods) for _ in range(n)]

    assert set(sizes) == {4, 5, 6}
    for size, share in ((4, 8 / 12), (5, 3 / 12), (6, 1 / 12)):
        assert abs(z_of(sizes.count(size), n, share)) < Z, size
    with pytest.raises(Refused):
        c.chaos(Item("magic"), rng)


def test_a_chaos_orb_keeps_the_fractured_mod_counts_it_in_the_total_and_blocks_its_group():
    c = crafter()
    rng = Random(13)
    n = 20_000
    start = Item("rare", (Held("SC", (5,), fractured=True), *held("PA", "PB", "SD")))
    made = [c.chaos(start, rng) for _ in range(n)]

    assert all(item.mods[0] == Held("SC", (5,), fractured=True) for item in made)
    assert all(not {"SC2"} & {h.mod_id for h in item.mods} for item in made)  # SC2 shares the fractured mod's group
    sizes = [len(item.mods) for item in made]
    assert abs(z_of(sizes.count(4), n, 8 / 12)) < Z  # the total is 4, 5 or 6 with the fractured mod in it, not 5, 6 or 7


def test_a_dry_pool_leaves_fewer_mods():
    mods = {key: value for key, value in tiny_mods().items() if key in ("PA", "PB", "SC")}
    c = crafter(mods)
    made = [c.chaos(Item("rare"), Random(seed)) for seed in range(50)]

    assert {len(item.mods) for item in made} == {3}


def test_a_side_holds_three_mods_on_a_rare_item_and_no_more():
    c = crafter()
    rng = Random(14)
    for _ in range(3000):
        counts = c.side_counts(c.chaos(Item("rare"), rng).mods)
        assert counts["prefix"] <= 3 and counts["suffix"] <= 3


def test_an_essence_forces_its_mod_counts_it_in_the_total_and_works_on_a_normal_or_a_rare_item():
    c = crafter()
    record = c.export.essences["Metadata/Items/Currency/CurrencyEssenceHigh"]
    rng = Random(15)
    n = 20_000
    made = [c.essence(Item("rare", held("PA", "SD")), rng, record) for _ in range(n)]

    assert all(any(h.mod_id == "EssForced" for h in item.mods) and item.rarity == "rare" for item in made)
    assert abs(z_of(sum(len(item.mods) == 4 for item in made), n, 8 / 12)) < Z
    assert c.essence(Item("normal"), rng, record).rarity == "rare"
    with pytest.raises(Refused):
        c.essence(Item("magic"), rng, record)


def test_the_forced_mod_ignores_the_item_level_and_a_low_essence_takes_only_a_normal_item():
    c = crafter(level=60)
    high = c.export.essences["Metadata/Items/Currency/CurrencyEssenceHigh"]
    low = c.export.essences[ESS_LOW]
    rng = Random(16)

    assert any(h.mod_id == "EssForced" for h in c.essence(Item("normal"), rng, high).mods)  # level 90 on an item of level 60
    assert c.essence(Item("normal"), rng, low).rarity == "rare"
    with pytest.raises(Refused):
        c.essence(Item("rare"), rng, low)


def test_an_essence_with_a_cap_draws_no_random_mod_above_the_cap():
    c = crafter()
    low = c.export.essences[ESS_LOW]
    rng = Random(17)
    drawn = {h.mod_id for _ in range(3000) for h in c.essence(Item("normal"), rng, low).mods}

    assert "PM" not in drawn and "SC2" in drawn  # PM needs level 50 (cap 35); SC2 level 30


def test_an_essence_is_refused_when_its_mod_shares_a_group_with_a_fractured_mod():
    mods = tiny_mods()
    mods["Clash"] = mod("GE", "prefix", 1, 1000)
    c = crafter(mods)
    record = c.export.essences["Metadata/Items/Currency/CurrencyEssenceHigh"]

    with pytest.raises(Refused):
        c.essence(Item("rare", (Held("Clash", (1,), fractured=True),)), Random(18), record)


def test_an_essence_on_a_class_it_has_no_mod_for_is_refused():
    c = crafter()

    with pytest.raises(Refused):
        c.essence(Item("normal"), Random(19), {"level": 6, "mods": {"Boots": "EssForced"}})


def test_the_bench_adds_its_fixed_mod_once_to_a_slot_that_is_open():
    c = crafter()
    rng = Random(20)
    crafted = c.bench(Item("rare", held("PA", "SD")), rng, "BenchX")

    assert crafted.mods[-1] == Held("BenchX", (3,), crafted=True)
    with pytest.raises(Refused):
        c.bench(crafted, rng, "BenchX")  # one crafted mod only
    with pytest.raises(Refused):
        c.bench(Item("normal"), rng, "BenchX")
    with pytest.raises(Refused):
        c.bench(Item("rare", held("SC", "SD", "SH")), rng, "BenchX")  # no open suffix
    with pytest.raises(Refused):
        c.bench(Item("magic", held("SC")), rng, "BenchX")  # the magic item's one suffix is taken


def test_a_reroll_removes_a_crafted_mod():
    c = crafter()
    rng = Random(21)
    crafted = c.bench(Item("rare", held("PA")), rng, "BenchX")

    assert all(not any(h.crafted for h in c.chaos(crafted, rng).mods) for _ in range(200))


# --- a route on a tiny target -------------------------------------------------------------------------------------------------

TARGET = """
base: Test Ring
item_level: 80
requirements:
  - family: GC
    mod: SC
start_item:
  rarity: normal
start: bought
"""
ROUTE = """
name: spam
rules:
  - when: {rarity: normal}
    do: Orb of Transmutation
  - do: Orb of Alteration
"""
PRICES = {
    "prices": {
        "Orb of Transmutation": {"chaos": 1.0},
        "Orb of Alteration": {"chaos": 2.0},
        "Regal Orb": {"chaos": 3.0},
        "Orb of Augmentation": {"chaos": 0.5},
        "Chaos Orb": {"chaos": 4.0},
        "Shrieking Essence of Test": {"chaos": 6.0},
        "Test Ring, normal": {"chaos": 5.0},
    }
}


def world(target=TARGET, laws=None, start_key="Test Ring, normal") -> World:
    return World(tiny_raw(), target, PRICES, start_key, laws)


def player(route=ROUTE, target=TARGET, laws=None) -> Player:
    w = world(target, laws)
    judge = Judge(w)
    return Player(w, read_route(route, w, judge), judge)


def exact_chance_of_sc_on_a_magic_item() -> float:
    """The chance that a magic ring (Transmutation or Alteration) holds SC: one mod (1/2), or two (1/2) with the second on the other side.

    Weights: prefixes 5,500, suffixes 6,000, SC 1,000. One mod: 1000 / 11500. Two mods: SC first, 1000 / 11500, or a prefix first
    (5500 / 11500) and SC second from the suffixes (1000 / 6000).
    """
    first = 1000 / 11500
    second = (5500 / 11500) * (1000 / 6000)
    return 0.5 * first + 0.5 * (first + second)


def exact_mean_of_the_spam(p: float) -> float:
    """One Transmutation (1 chaos), then Alterations (2 chaos) until SC: the number of Alterations is geometric, (1 - p) / p on average."""
    return 1.0 + 2.0 * (1 - p) / p


def test_the_naive_mean_of_a_tiny_spam_agrees_with_the_mean_worked_out_by_hand():
    p = exact_chance_of_sc_on_a_magic_item()
    tally = t.simulate(player(), 6000, seed=22)
    verdict = t.verdict_on("tiny spam", exact_mean_of_the_spam(p), tally.mean_se())

    assert verdict.agrees, str(verdict)
    assert tally.uses_mean("Orb of Transmutation") == 1.0


def test_a_wrong_law_of_the_number_of_mods_is_a_disagreement_the_verdict_names():
    p = exact_chance_of_sc_on_a_magic_item()
    wrong = t.simulate(player(laws=Laws(magic=((1, 1), (2, 3)))), 6000, seed=23)
    verdict = t.verdict_on("tiny spam, three of four items with two mods", exact_mean_of_the_spam(p), wrong.mean_se())

    assert not verdict.agrees and "tiny spam" in str(verdict) and "standard errors" in str(verdict)


def test_a_wrong_draw_rule_is_a_disagreement_too():
    mods = tiny_mods()
    mods["SD"]["spawn_weights"] = [{"tag": "ring", "weight": 1000}, {"tag": "default", "weight": 0}]  # the suffix SD weighs 1000 instead of 2000
    w = World(tiny_raw(mods), TARGET, PRICES, "Test Ring, normal")
    judge = Judge(w)
    wrong = t.simulate(Player(w, read_route(ROUTE, w, judge), judge), 6000, seed=24)
    verdict = t.verdict_on("tiny spam with a lighter SD", exact_mean_of_the_spam(exact_chance_of_sc_on_a_magic_item()), wrong.mean_se())

    assert not verdict.agrees


def test_the_verdict_is_four_standard_errors_and_a_zero_error_is_exact_equality():
    assert t.K == 4.0
    assert t.Verdict("a", 10.0, 10.39, 0.1).agrees
    assert not t.Verdict("a", 10.0, 10.41, 0.1).agrees
    assert t.Verdict("a", 3.0, 3.0, 0.0).agrees
    assert not t.Verdict("a", 3.0, 3.1, 0.0).agrees
    assert t.Verdict("a", 3.0, 3.0 + 1e-12, 0.0).agrees  # the float error of an exact value


def test_tallies_add_and_the_standard_error_is_the_sample_one():
    first, second = t.simulate(player(), 50, seed=25), t.simulate(player(), 70, seed=26)
    merged = first.merge(second)
    plays = [t.Play(cost=c, spend={"x": c}, uses={"x": 1}) for c in (1.0, 2.0, 3.0, 4.0)]
    small = t.Tally()
    for play in plays:
        small.add(play)

    assert merged.n == 120 and merged.total == pytest.approx(first.total + second.total)
    assert small.mean_se() == (2.5, math.sqrt(5 / 3 / 4))
    assert t.Tally.from_dict(merged.to_dict()).mean_se() == merged.mean_se()
    assert t.Tally().merge(t.Tally()).n == 0


# --- the route's rules -----------------------------------------------------------------------------------------------------------------


def play_of(route, target=TARGET, seed=0, start=None):
    p = player(route, target)
    if start is not None:
        p.world.start_item = start
    return p.play(Random(seed))


def test_the_first_rule_whose_conditions_hold_is_followed_and_a_goal_is_never_acted_on():
    already = Item("magic", held("SC"))

    play = play_of(ROUTE, start=already)

    assert play.cost == 0.0 and play.uses == {}


def test_an_item_no_rule_covers_is_a_gap_that_names_the_item():
    route = "rules:\n  - when: {rarity: normal}\n    do: Orb of Transmutation\n"

    with pytest.raises(Gap, match="no rule covers a magic item"):
        play_of(route, seed=3, start=Item("magic", held("PA")))


def test_an_action_the_game_refuses_is_a_gap_unless_the_route_skips_refused_rules():
    route = "rules:\n  - do: Regal Orb\n"
    skipping = "skip_refused: true\nrules:\n  - do: Regal Orb\n  - when: {rarity: normal}\n    do: Orb of Transmutation\n  - do: Chaos Orb\n"

    with pytest.raises(Gap, match="is refused"):
        play_of(route, start=Item("normal"))
    assert play_of(skipping, seed=4, start=Item("normal")).uses.get("Orb of Transmutation", 0) >= 1


def test_a_restart_pays_the_start_price_and_puts_the_start_item_back():
    route = "rules:\n  - when: {rarity: normal}\n    do: Orb of Transmutation\n  - when: {rarity: magic}\n    do: restart\n"
    play = play_of(route, seed=5)

    assert play.uses["Orb of Transmutation"] == play.uses.get(RESTART, 0) + 1  # a restart is followed by a new Transmutation, and the last one is the goal
    assert play.spend.get(RESTART, 0.0) == 5.0 * play.uses.get(RESTART, 0)
    assert play.cost == pytest.approx(1.0 * play.uses["Orb of Transmutation"] + play.spend.get(RESTART, 0.0))
    assert world().action(RESTART).cost == 5.0


def test_statuses_are_absent_below_or_passing_by_what_the_item_holds():
    w = world()
    judge = Judge(w)
    for mods, expected in (((), 0), (held("SC2"), 1), (held("SC"), 2)):  # SC2 is in the family of the line but is not the named mod
        assert judge.statuses(Item("rare", mods)) == [expected]


def test_the_conditions_on_slots_fractured_mods_and_crafted_mods_are_read_as_the_header_says():
    spam = "rules:\n  - when: {open_suffixes: 2, fractured: none, crafted_mods: false, rarity: [rare]}\n    do: Chaos Orb\n"
    p = player(spam)
    when = p.route.rules[0].when
    world_ = p.world
    status = [0]

    assert when.matches(Item("rare", held("PA")), status, world_)
    assert not when.matches(Item("rare", held("PA", "SC", "SD", "SH")), status, world_)  # one suffix left
    assert not when.matches(Item("rare", held("PA", fractured=("PA",))), status, world_)
    assert not when.matches(Item("rare", (Held("BenchX", (3,), crafted=True),)), status, world_)
    assert not when.matches(Item("magic"), status, world_)


def test_a_condition_on_a_fractured_family_and_on_the_others_is_read():
    route = (
        "rules:\n  - when: {fractured: [{family: GA}]}\n    do: Chaos Orb\n"
        "  - when: {fractured: {without: [{family: GA}]}}\n    do: Orb of Alteration\n  - do: Regal Orb\n"
    )
    p = player(route)
    first, second = p.route.rules[0].when, p.route.rules[1].when
    a = Item("rare", (Held("PA", (1,), fractured=True),))
    b = Item("rare", (Held("PB", (1,), fractured=True),))

    assert first.matches(a, [0], p.world) and not first.matches(b, [0], p.world)
    assert second.matches(b, [0], p.world) and not second.matches(a, [0], p.world) and not second.matches(Item("rare"), [0], p.world)


@pytest.mark.parametrize(
    ("route", "message"),
    [
        ("rules: []\n", "non-empty"),
        ("rules:\n  - when: {colour: red}\n    do: Chaos Orb\n", "unknown condition"),
        ("rules:\n  - when: {rarity: epic}\n    do: Chaos Orb\n", "normal, magic or rare"),
        ("rules:\n  - when: {corrupted: true}\n    do: Chaos Orb\n", "never corrupted"),
        ("rules:\n  - when: {requirements: [{family: Nope, status: absent}]}\n    do: Chaos Orb\n", "0 lines"),
        ("rules:\n  - when: {requirements: [{family: GC, status: gone}]}\n    do: Chaos Orb\n", "absent, below or passing"),
        ("rules:\n  - do: 7\n", "name of an action"),
    ],
)
def test_a_route_file_that_cannot_be_read_says_where(route, message):
    with pytest.raises(RouteError, match=message):
        player(route)


def test_an_action_the_player_does_not_have_is_refused_when_the_route_is_read_and_named():
    for label, mechanic in (("Harvest Reforge more likely", "more or less likely"), ("Fossils Dense Fossil", "no fossil of this name"), ("Mystery", "does not know")):
        with pytest.raises(Exception, match=mechanic):
            player(f"rules:\n  - do: {label}\n")
    assert lacking("rules:\n  - do: Mystery\n  - do: Regal Orb\n", world()).keys() == {"Mystery"}


def test_a_name_with_no_price_is_an_error_and_a_given_start_item_has_no_restart():
    with pytest.raises(UnpricedError, match="Regal"):
        World(tiny_raw(), TARGET, {"prices": {}}, "Test Ring, normal").action("Regal Orb")
    given = TARGET.replace("start: bought", "start: given")
    with pytest.raises(Exception, match="given"):
        World(tiny_raw(), given, PRICES, None).action(RESTART)


def test_the_bench_craft_is_found_by_the_text_of_its_mod_and_costs_its_currencies():
    action = world().action("Bench craft (3-3)% bench")

    assert action.kind == "bench" and action.mod_id == "BenchX" and action.cost == 8.0  # two Chaos Orbs at 4


def test_the_start_item_is_read_from_the_target_with_its_fractured_mods_and_the_rarity_a_listed_mod_implies():
    text = TARGET.replace("  rarity: normal\n", "  mods:\n    - mod: PA\n      values: [4]\n      fractured: true\n")
    item = World(tiny_raw(), text, PRICES, "Test Ring, normal").start_item

    assert item == Item("rare", (Held("PA", (4,), fractured=True),))
    assert yaml.safe_load(TARGET)["start"] == "bought"


# --- pooling a long simulation that ran on several runners ---------------------------------------------------------------------------


def write_runner(folder, index, route, exact, spend, tally):
    runner = folder / f"run-ubuntu-latest-{index}"
    runner.mkdir(parents=True)
    document = {"route": route, "exact_mean": exact, "exact_spend": spend, "seed": index, "tally": tally.to_dict()}
    (runner / f"naive-{route}-{index}.json").write_text(json.dumps(document), encoding="utf-8")


def test_the_tallies_of_the_runners_are_pooled_and_judged_and_a_wrong_exact_side_is_a_disagreement(tmp_path):
    p = exact_chance_of_sc_on_a_magic_item()
    exact = exact_mean_of_the_spam(p)
    spend = {"Orb of Transmutation": 1.0, "Orb of Alteration": 2.0 * (1 - p) / p}
    for index in (1, 2):
        write_runner(tmp_path, index, "TINY", exact, spend, t.simulate(player(), 3000, seed=30 + index))

    verdicts, plays = command.merge_folder(tmp_path)

    assert plays == {"TINY": 6000} and len(verdicts) == 3 and all(v.agrees for v in verdicts)
    assert command.main(["merge", str(tmp_path)]) == 0
    wrong = tmp_path / "wrong"
    write_runner(wrong, 1, "TINY", exact * 1.2, spend, t.simulate(player(), 3000, seed=40))
    assert command.main(["merge", str(wrong)]) == 1
    assert command.main(["merge", str(tmp_path / "nothing")]) == 2


def test_runners_whose_exact_sides_differ_are_not_pooled(tmp_path):
    write_runner(tmp_path, 1, "TINY", 10.0, {"a": 10.0}, t.Tally())
    write_runner(tmp_path, 2, "TINY", 11.0, {"a": 11.0}, t.Tally())

    with pytest.raises(SystemExit, match="different exact sides"):
        command.merge_folder(tmp_path)


# --- the rules a test can turn off (the mutations of the route tests) ---------------------------------------------------------------------


def test_without_the_level_gate_a_mod_above_the_item_level_joins_the_pool():
    pool = crafter(laws=Laws(level_gate=False), level=40).pool()

    assert "PM" in pool.ids and "HIGH" in pool.ids and "PM" not in crafter(level=40).pool().ids


def test_without_family_exclusion_an_item_can_hold_two_mods_of_one_group():
    c = crafter(laws=Laws(family_exclusion=False))
    rng = Random(31)
    two_of_a_group = sum(
        {"SC", "SC2"} <= {h.mod_id for h in c.chaos(Item("rare", held("PA", "PB", "SC", "SD")), rng).mods} for _ in range(4000)
    )

    assert two_of_a_group > 0
    assert all(not {"SC", "SC2"} <= {h.mod_id for h in crafter().chaos(Item("rare", held("PA", "PB", "SC", "SD")), rng).mods} for _ in range(500))


def test_with_a_side_chosen_first_a_single_mod_is_a_prefix_half_of_the_time_not_by_the_weight_of_the_side():
    n = 20_000
    rng = Random(32)

    def prefix_share(c):
        singles = [item for item in (c.transmute(Item("normal"), rng) for _ in range(n)) if len(item.mods) == 1]
        return sum(c.book.side(item.mods[0].mod_id) == "prefix" for item in singles), len(singles)

    hits, total = prefix_share(crafter(laws=Laws(one_pool=False)))
    assert abs(z_of(hits, total, 0.5)) < Z
    hits, total = prefix_share(crafter())
    assert abs(z_of(hits, total, 5500 / 11500)) < Z  # one pool: the prefixes weigh 5,500 of 11,500
