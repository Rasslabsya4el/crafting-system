"""The missing mods' table (`planner/_missing_mods.py`, #1496, H21 of #1434, OR-39, OR-40, OR-55): a lower bound of V* per state that counts
every missing mod, built from a round's offers' floors and read by the envelope search.

Hand-worked: on the veiled amulet of `test_free_action_floors` with the Life goal, the one way to Life is the Veiled Chaos Orb (an erasing
reroll at 5, chance `VEILED_CHAOS_LIFE` of Life, exact): V* = 5 / p, about 15.2205, and the table's exact law gives that figure (its
Veiled Exalted Orb is a veil, which removes and adds a placeholder and can pass no leaf). On the magic amulet of `test_pattern_imprint`
(three wanted mods, Alteration, Augmentation, Regal, Annulment) the table is checked state by state against the exact graph: it is at most V*
everywhere, and at the start within 1e-6 of it, where the offers' floor rho is 0.18. Each "off" case, and the check's fallback, gives 0.

On a rare amulet of the small pool (`TOY`: the pool, a crafted prefix and the Attack metamod made craftable on amulets, the veiled placeholders)
each law is met against the exact graph of its offers, state by state (`test_each_law_is_at_most_the_exact_cost_at_every_state`): the bench
craft, Remove Crafted Mods, the Orb of Annulment with a tag metamod that protects junk, the veil, the Beastcraft side swap, the Harvest
likelihood reforge, and a leaf of two families (Cold OR Fire resistance), whose mod the draws' chances count among the held mods (#1496 checker
round 1: a slot reserved for it without its family left out of the pool gave a chance of 0.1163 where the item has 0.1316).
"""

import dataclasses
from dataclasses import replace
from fractions import Fraction

import pytest

import test_free_action_floors as veiled
import test_pattern_imprint as imprinted
from abstraction_pool import COLD_GEM, COLD_RESIST, DAMAGE_2, FIRE_GEM, FIRE_RESIST, LEVEL, MANA_1, POOL_IDS, RESIST_3, roll
from items_support import AMULET, DATA
from pattern_support import exact_values
from veiled_support import veiled_mods

from crafting_system.abstraction import Abstraction, Goal, Status, Wanted
from crafting_system.abstraction._pattern import PatternOffer
from crafting_system.actions import NotApplicableError, AlterationOrb, AnnulmentOrb, ChaosOrb, ExaltedOrb
from crafting_system.actions.beast_mods import BeastSideSwap
from crafting_system.actions.bench import BenchCraft, RemoveCraftedMods
from crafting_system.actions.harvest_likelihood import HarvestReforgeLikelihood
from crafting_system.actions.magic import AugmentationOrb, RegalOrb, TransmutationOrb
from crafting_system.actions.scour import ScouringOrb
from crafting_system.actions.veiled import VeiledExaltedOrb
from crafting_system.cli import Offer
from crafting_system.items import ExplicitMod, Item, Rarity, Side
from crafting_system.items.quality import PlainQuality
from crafting_system.items.sockets import SocketColour, Sockets
from crafting_system.actions import drawable_mod_ids
from crafting_system.planner._offers import offers_for
from crafting_system.targets import load_target
from abstraction_support import real_game_data
from targets_support import EXAMPLES
from crafting_system.planner import _missing_mods
from crafting_system.planner._envelope import Beaten
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._missing_mods import missing_mods_table, refused_by_shape
from crafting_system.planner._offer_floor import OfferFloors
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.planner import _pattern_bound
from crafting_system.planner._pattern_bound import TABLE_CLOSED, pattern_lower_bound

TOLERANCE = 1e-9


@pytest.fixture
def floors_on(monkeypatch):
    """The offers' floors, and so the table, for a round of a few offers (the planner builds them from `MIN_OFFERS` offers)."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)


@pytest.fixture
def short(monkeypatch):
    """A table iterated 200 times: weaker, as sound (the check decides), and quicker."""
    monkeypatch.setattr(_missing_mods, "ITERATIONS", 200)


def no_imprints():
    """The magic amulet without the Craicic Croaker: (abstraction, start state, priced offers)."""
    ab = imprinted.abstraction(None)
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in imprinted.CRAFTS.items()]
    offers.append(PricedOffer(Offer(RESTART, BuyStartItem(imprinted.START), {}), imprinted.RESTART_PRICE, ()))
    return ab, ab.compress(imprinted.START), offers


@pytest.fixture(scope="module")
def amulet():
    ab, first, offers = no_imprints()
    floors = OfferFloors(ab, first, offers, imprinted.START)
    table = missing_mods_table(floors)
    exact = exact_values(ab, first, imprinted.pattern_offers(None))
    return ab, first, offers, floors, table, exact


def test_the_one_reroll_to_life_gives_its_cost_over_its_chance():
    floors = veiled.floors_of("life")
    table = missing_mods_table(floors)
    assert table.off is None
    assert table.start == pytest.approx(5.0 / float(veiled.VEILED_CHAOS_LIFE), rel=1e-8)
    assert table.start <= 5.0 / float(veiled.VEILED_CHAOS_LIFE)
    assert table.lower(floors.start) == table.start


def test_the_table_is_at_most_the_exact_cost_at_every_state_and_near_it_at_the_start(amulet):
    ab, first, _offers, floors, table, exact = amulet
    assert table.off is None
    for state, value in exact.items():
        assert table.lower(state) <= value * (1 + TOLERANCE)
    assert floors.rho == pytest.approx(0.18)
    assert table.start == pytest.approx(exact[first], rel=1e-6)  # the iteration stops at its cap of 3,000 here, 1.4e-7 below


def test_an_imprint_makes_a_state_off_and_the_croaker_is_a_cut():
    """With the Croaker offered (cap 1) a state holding an imprint is OFF (0), and the imprint is priced at its cost alone (a CUT), so the
    table's figure at the start is the beast's 2 (less the check's shrink), below the exact cost."""
    cap = 1
    ab = imprinted.abstraction(cap)
    first = ab.compress(imprinted.START)
    table = missing_mods_table(OfferFloors(ab, first, imprinted.priced_offers(cap), imprinted.START))
    exact = exact_values(ab, first, imprinted.pattern_offers(cap))
    assert table.off is None
    assert table.start == pytest.approx(imprinted.BEAST, rel=1e-8)
    held = [state for state in exact if state.imprints]
    assert held and all(table.lower(state) == 0.0 for state in held)
    assert all(table.lower(state) <= value * (1 + TOLERANCE) for state, value in exact.items())


def test_a_state_the_table_does_not_model_reads_zero(amulet, monkeypatch):
    ab, first, _offers, _floors, table, _exact = amulet
    assert table.lower(first) > 0
    assert table.lower(replace(first, strands=1)) == 0.0  # Memory Strands
    assert table.lower(replace(first, imprints=(first,))) == 0.0  # an imprint
    assert table.lower(replace(first, flags=replace(first.flags, corrupted=True))) == 0.0  # a shape the floors do not know
    monkeypatch.setattr(type(ab), "_holds_lock", lambda self, state: True)
    assert table.lower(first) == 0.0  # a lock


def test_the_table_is_off_without_junk_slots_and_reads_zero():
    ab = Abstraction(imprinted.SMALL, imprinted.GOAL, imprinted.AMULET, imprinted.LEVEL, (AlterationOrb(),))
    assert not ab.keeps_junk
    offers = [PricedOffer(Offer("Orb of Alteration", AlterationOrb(), {"Orb of Alteration": 1}), 0.1, ())]
    offers.append(PricedOffer(Offer(RESTART, BuyStartItem(imprinted.START), {}), imprinted.RESTART_PRICE, ()))
    first = ab.compress(imprinted.START)
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START))
    assert table.off is not None and "junk" in table.off
    assert table.start == 0.0 and table.lower(first) == 0.0


def test_the_table_is_off_when_the_check_fails(monkeypatch):
    """The check h <= T h is the proof: a table scaled up past its fixed point fails it, and the table is off, today's floors standing."""
    monkeypatch.setattr(_missing_mods, "SHRINK", (-1.0,))  # h doubled before the check
    ab, first, offers = no_imprints()
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START))
    assert table.off is not None and "check" in table.off
    assert table.lower(first) == 0.0


def test_the_table_is_off_when_the_net_is_reached():
    ab, first, offers = no_imprints()
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START), stop=lambda: "the clock")
    assert table.off is not None and "the clock" in table.off


def test_the_search_reads_the_table_and_gives_the_exact_plan(amulet, floors_on, short):
    ab, first, offers, _floors, _table, exact = amulet
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START)
    assert bound.table is not None and bound.table.off is None
    result = envelope_result(ab, first, offers, item=imprinted.START, bound=bound)
    info = result.info["envelope"]
    assert info.exact
    assert result.solution.values[first] == pytest.approx(exact[first], rel=TOLERANCE)
    assert bound.table.start <= info.lower * (1 + 1e-6) <= exact[first] * (1 + 1e-6)


def test_a_round_whose_table_reaches_the_plan_in_hand_closes_before_any_model_is_grown(amulet, floors_on):
    """A plan in hand at the exact cost: the table's figure at the start reaches it to the certified 1e-6, so the build grows no model
    (phase "table") and the search ends at once, beaten."""
    ab, first, offers, _floors, table, exact = amulet
    held = exact[first] * (1 + 1e-7)
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START, closes=lambda lower: held <= (1 + 1e-6) * lower)
    assert bound.phase == "table" and bound.stopped == TABLE_CLOSED
    with pytest.raises(Beaten) as beaten:
        envelope_result(ab, first, offers, item=imprinted.START, beaten_at=held)
    assert beaten.value.lower >= table.start


def test_a_search_of_other_offers_does_not_read_the_table(amulet, floors_on, short):
    ab, first, offers, _floors, _table, _exact = amulet
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START)
    assert bound.table.serves(offers) and not bound.table.serves(list(offers[:-1]))
    assert not bound.table.serves([replace(offer) for offer in offers])


CRAFTED_DAMAGE = "JunMaster2AllDamage2_"  # a crafted prefix of one family, no Attack or Caster tag: a sure leaf whose mod is crafted
NO_ATTACKS = "IntMasterItemGenerationCannotRollAttackAffixes"  # a tag metamod: the Annulment cannot remove an Attack mod while it is held


def _toy():
    bench = tuple(
        dataclasses.replace(option, item_classes=(*option.item_classes, "Amulet")) if option.actions.add_explicit_mod == CRAFTED_DAMAGE else option
        for option in DATA.bench_options
    )
    template = next(option for option in bench if option.actions.add_explicit_mod == CRAFTED_DAMAGE)
    bench = (*bench, dataclasses.replace(template, actions=dataclasses.replace(template.actions, add_explicit_mod=NO_ATTACKS)))
    mods = {mod_id: mod for mod_id, mod in DATA.mods.items() if mod_id in POOL_IDS | {CRAFTED_DAMAGE, NO_ATTACKS}}
    return dataclasses.replace(DATA, mods={**mods, **veiled_mods()}, bench_options=bench)


TOY = _toy()
TOY_ACTIONS = {
    "chaos": (ChaosOrb(), 1.0), "exalt": (ExaltedOrb(), 1.5), "annul": (AnnulmentOrb(), 2.0), "craft": (BenchCraft(CRAFTED_DAMAGE), 0.7),
    "no attacks": (BenchCraft(NO_ATTACKS), 0.4), "remove crafted": (RemoveCraftedMods(), 0.3), "swap": (BeastSideSwap(Side.SUFFIX), 0.9),
    "veil": (VeiledExaltedOrb(), 3.0), "likelihood": (HarvestReforgeLikelihood(more=True), 2.5),
    "scour": (ScouringOrb(), 0.1), "transmute": (TransmutationOrb(), 0.1), "augment": (AugmentationOrb(), 0.1), "regal": (RegalOrb(), 0.2),
    "cheap swap": (BeastSideSwap(Side.SUFFIX), 0.05),
}  # fmt: skip
TOY_LEAVES = {
    "cold or fire": Wanted(frozenset({COLD_RESIST, FIRE_RESIST})), "lightning": Wanted(frozenset({RESIST_3})),
    "crafted damage": Wanted(frozenset({CRAFTED_DAMAGE})), "attack damage": Wanted(frozenset({DAMAGE_2})),
    "lightning or cold": Wanted(frozenset({RESIST_3, COLD_RESIST})), "cold or fire gems": Wanted(frozenset({COLD_GEM, FIRE_GEM})),
}  # fmt: skip
TOY_RESTART = 4.0


def toy(actions, leaves):
    """(abstraction, start state, priced offers, pattern offers) of a rare amulet of `TOY` holding one mana leech suffix."""
    acts = {name: TOY_ACTIONS[name] for name in actions}
    start = Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE, mods=(roll(MANA_1),))
    ab = Abstraction(TOY, Goal(tuple(TOY_LEAVES[name] for name in leaves)), AMULET, LEVEL, tuple(action for action, _ in acts.values()))
    offers = [PricedOffer(Offer(name, action, {name: 1}), cost, ()) for name, (action, cost) in acts.items()]
    offers.append(PricedOffer(Offer(RESTART, BuyStartItem(start), {}), TOY_RESTART, ()))
    patterns = [PatternOffer(name, action, cost) for name, (action, cost) in acts.items()] + [PatternOffer(RESTART, None, TOY_RESTART)]
    return ab, ab.compress(start), offers, patterns, start


LAWS = {
    "bench craft, Remove Crafted Mods, Annulment": (("chaos", "exalt", "annul", "craft", "remove crafted"), ("crafted damage", "lightning")),
    "metamod protects junk, a two-family leaf": (("chaos", "exalt", "annul", "craft", "no attacks", "remove crafted"), ("cold or fire", "crafted damage")),
    "side swap, veil": (("chaos", "exalt", "swap", "veil", "craft", "remove crafted"), ("cold or fire", "lightning", "crafted damage")),
    "likelihood reforge": (("chaos", "exalt", "likelihood", "annul", "no attacks"), ("cold or fire", "lightning")),
    "two-family leaves that overlap": (("chaos", "exalt", "swap", "annul", "craft", "remove crafted"), ("cold or fire", "lightning or cold")),
    "two two-family leaves, one per side": (("chaos", "exalt", "swap", "veil", "annul"), ("cold or fire", "cold or fire gems")),
    "an attack leaf (not sure), swap": (("exalt", "annul", "craft", "no attacks", "remove crafted", "swap"), ("lightning", "attack damage")),
}  # fmt: skip


@pytest.mark.parametrize("law", list(LAWS))
def test_each_law_is_at_most_the_exact_cost_at_every_state(law):
    ab, first, offers, patterns, start = toy(*LAWS[law])
    table = missing_mods_table(OfferFloors(ab, first, offers, start))
    exact = exact_values(ab, first, patterns)
    assert table.off is None
    assert table.start > 0
    assert all(table.lower(state) <= value * (1 + TOLERANCE) for state, value in exact.items())
    assert sum(1 for state in exact if table.lower(state) > 0) > len(exact) // 3  # many states are read, not OFF (goal states read 0)


def test_the_bench_craft_table_is_the_exact_cost_at_the_start():
    """Chaos, Exalted, Annulment, the crafted prefix and Remove Crafted Mods to Lightning resistance and the crafted prefix: the table's figure at
    the start is the exact graph's mean to 1e-8."""
    ab, first, offers, patterns, start = toy(*LAWS["bench craft, Remove Crafted Mods, Annulment"])
    table = missing_mods_table(OfferFloors(ab, first, offers, start))
    assert table.start == pytest.approx(exact_values(ab, first, patterns)[first], rel=1e-8)


def test_the_likelihood_reforge_has_its_law_and_is_no_cut():
    ab, first, offers, _patterns, start = toy(*LAWS["likelihood reforge"])
    build = _missing_mods._Build(OfferFloors(ab, first, offers, start), None)
    build.prepare()
    assert [d["cost"] for d in build.bounded] == [TOY_ACTIONS["likelihood"][1]]
    assert TOY_ACTIONS["likelihood"][1] not in [cost for _s, cost in build.cuts]
    assert all(0 < u <= 1 for u in build.bounded[0]["u"].values())


def test_a_two_family_leaf_held_leaves_the_drawn_chance_at_least_the_items():
    """The counter-example of #1496's checker round 1: with Cold OR Fire resistance held, the Exalted Orb's chance of Lightning resistance 3 at
    the table's state is at least its chance at each item of that state (0.1316 on the item; the reserved slot gave 0.1163)."""
    ab, first, offers, _patterns, start = toy(("chaos", "exalt"), ("cold or fire", "lightning"))
    build = _missing_mods._Build(OfferFloors(ab, first, offers, start), None)
    build.prepare()
    (draw,) = [d for d in build.draws if d["e"].priced.label == "exalt"]
    for held in (COLD_RESIST, FIRE_RESIST):
        item = Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE, mods=(roll(MANA_1), roll(held)))
        state = ab.compress(item)
        x = build.reader.phi(state)
        exact = sum((p for after, p in ab.kernel(state, ExaltedOrb()).items() if after.status[1] is Status.PASSING), Fraction(0))
        Q, _p1, _p2 = draw["sups"][(x[1], x[2], x[3])]
        assert Q[1] >= exact > 0


def test_a_fault_inside_the_table_turns_it_off(monkeypatch):
    ab, first, offers = no_imprints()

    def broken(self):
        raise RuntimeError("a fault")

    monkeypatch.setattr(_missing_mods._Build, "solve", broken)
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START))
    assert table.off is not None and "RuntimeError" in table.off and table.lower(first) == 0.0


def test_a_state_phi_cannot_read_is_zero(amulet, monkeypatch):
    ab, first, _offers, _floors, table, _exact = amulet

    def broken(self, state):
        raise KeyError("a fault")

    monkeypatch.setattr(_missing_mods._Reader, "phi", broken)
    assert table.lower(first) == 0.0


def test_the_table_stops_at_its_own_share_of_the_time():
    ab, first, offers = no_imprints()
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START), seconds=0.0)
    assert table.off is not None and "share" in table.off


SHAPES = (("chaos", "exalt", "cheap swap", "scour", "transmute", "augment", "regal"), ("cold or fire", "lightning"))


def test_an_offer_refused_by_its_shape_leaves_the_table_and_the_table_stays_under_the_exact_cost():
    """Three shapes (the rare start, the Normal item the Scouring Orb leaves, the Magic one of the Transmutation): the side swap, a rare-only
    craft, is refused by the rarity at the two others and leaves their min (#1496: on R10 the Eldritch Exalted Orb held the Magic shape at its
    price). Without the law the table is the Scouring Orb and the swap, 0.1 + 0.05; with it the table is under the exact cost at every state
    and near the start's (0.98 of 1.33)."""
    ab, first, offers, patterns, start = toy(*SHAPES)
    floors = OfferFloors(ab, first, offers, start)
    assert [view.item.rarity for view in floors.views] == [Rarity.RARE, Rarity.NORMAL, Rarity.MAGIC]
    build = _missing_mods._Build(floors, None)
    build.prepare()
    swap = TOY_ACTIONS["cheap swap"][1]
    assert [s for s, cost in build.cuts if cost == swap] == [] and build.by_shape > 0
    assert any(d["cost"] == swap and d["s"] == 0 for d in build.draws)  # the rare shape keeps the swap's law
    table = missing_mods_table(floors)
    exact = exact_values(ab, first, patterns)
    assert {state.flags.rarity for state in exact} == {Rarity.RARE, Rarity.MAGIC, Rarity.NORMAL}
    assert table.off is None
    assert all(table.lower(state) <= value * (1 + TOLERANCE) for state, value in exact.items())
    assert table.start > 0.9 > TOY_ACTIONS["scour"][1] + swap
    assert table.start <= exact[first]


def test_a_refusal_that_reads_a_mod_is_not_read_as_the_shapes():
    """The side swap at the rare bare item is refused for want of a suffix to remove: a read of the mods, which a state of the shape may hold, so
    the probe does not call it refused by the shape; at the Magic and Normal items the rarity alone refuses it, and the Exalted Orb as well."""
    swap, exalt = TOY_ACTIONS["cheap swap"][0], TOY_ACTIONS["exalt"][0]
    rare, magic, normal = (Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=rarity) for rarity in (Rarity.RARE, Rarity.MAGIC, Rarity.NORMAL))
    assert not refused_by_shape(TOY, rare, swap) and not refused_by_shape(TOY, rare, exalt)
    assert refused_by_shape(TOY, magic, swap) and refused_by_shape(TOY, normal, swap) and refused_by_shape(TOY, normal, exalt)
    assert not refused_by_shape(TOY, normal, TOY_ACTIONS["transmute"][0]) and not refused_by_shape(TOY, magic, TOY_ACTIONS["augment"][0])


class _RefusesOnQuality:
    """A craft refused by what a state of a shape may differ in: by an identity test of the quality (no poison sees it), or by its value."""

    def __init__(self, by_identity):
        self.by_identity = by_identity

    def outcomes(self, data, item):
        if self.by_identity and item.quality is None:
            raise NotApplicableError("needs quality")
        if not self.by_identity and item.quality is not None and item.quality.value > 0:
            raise NotApplicableError("refused on quality")
        raise NotApplicableError("refused on the mods") if len(item.mods) > 9 else NotApplicableError("refused")


def test_a_refusal_that_reads_a_field_a_state_may_differ_in_is_not_the_shapes():
    """The probe's poisons and its None probe: a refusal by the quality, read by value or by an identity test, is not read as the shape's."""
    rare = Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE)
    assert not refused_by_shape(TOY, rare, _RefusesOnQuality(by_identity=True))
    assert not refused_by_shape(TOY, rare, _RefusesOnQuality(by_identity=False))


class _RefusesOnQualityKind:
    """A craft a state with plain quality takes, refused otherwise: by a type test (no method of the value called) or an exact type test."""

    def __init__(self, exact):
        self.exact = exact

    def outcomes(self, data, item):
        plain = type(item.quality) is PlainQuality if self.exact else isinstance(item.quality, PlainQuality)
        if not plain:
            raise NotApplicableError("needs plain quality")
        return None


@pytest.mark.parametrize("exact", [False, True])
def test_a_refusal_by_the_kind_of_quality_is_not_the_shapes(exact):
    rare = Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE)
    assert not refused_by_shape(TOY, rare, _RefusesOnQualityKind(exact))


def test_every_field_of_the_item_is_on_one_side_of_the_law():
    """A field added to `Item` must be put among the shared or the varying ones of `_missing_mods`, with its reason, before the law reads it."""
    fields = {field.name for field in dataclasses.fields(Item)}
    assert set(_missing_mods.SHARED) | set(_missing_mods.VARYING) == fields
    assert not set(_missing_mods.SHARED) & set(_missing_mods.VARYING)


def test_every_offer_the_law_drops_on_r10_is_refused_at_real_states_of_its_shape():
    """The sweep (#1496 checker, audit entry 27) on R10's own catalogue and the real data: at the rare start's shape and the Magic shape of the same item
    (its fractured Movement Speed kept; a Normal item cannot hold it), every offer `refused_by_shape` drops is refused at real items of that shape:
    the bare item, one with each of a sample of the pool's mods added, one with plain quality, one with sockets. The law must drop the Eldritch Exalted Orb and both side swaps at the Magic shape, and keep the side swaps at the rare one."""
    data = real_game_data()
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", data)
    goal = Goal.from_target(target)
    start = target.start_item
    actions = [offer.action for offer in offers_for(data, goal, target.base_id, start).offers]
    fractured = tuple(entry for entry in start.mods if entry.fractured)
    pool = sorted(drawable_mod_ids(data, start))[::25]
    dropped = {}
    for rarity in (Rarity.RARE, Rarity.MAGIC, Rarity.NORMAL):
        try:
            shape = start.changed(data, rarity=rarity, mods=fractured)
        except Exception:  # noqa: BLE001  (a Normal item cannot hold the fractured mod: no such shape)
            continue
        states = [shape, shape.changed(data, quality=PlainQuality(20)), shape.changed(data, sockets=Sockets.unlinked((SocketColour.WHITE,) * 4))]
        for mod_id in pool:
            mod = data.mods[mod_id]
            try:
                states.append(shape.changed(data, mods=(*fractured, ExplicitMod(mod_id, tuple(stat.min for stat in mod.stats)))))
            except Exception:  # noqa: BLE001  (a mod the rarity cannot hold more of: not a state of the shape)
                continue
        for action in actions:
            if not refused_by_shape(data, shape, action):
                continue
            dropped.setdefault(rarity, []).append(action)
            for state in states:
                with pytest.raises(NotApplicableError):
                    action.outcomes(data, state)
    names = {rarity: {type(a).__name__ for a in dropped.get(rarity, ())} for rarity in (Rarity.RARE, Rarity.MAGIC)}
    assert {"EldritchExaltedOrb", "BeastSideSwap"} <= names[Rarity.MAGIC]
    assert "BeastSideSwap" not in names[Rarity.RARE]
    assert len(dropped[Rarity.MAGIC]) > 10


# --- an unopened listing start (THE LISTING, #1552, H43 of board #1434) -------------------------------------------------------------


def listing_plan(kind: str):
    """(data, target, prices, plan) of a toy boots base bought unopened (`listing_support`): "magic" wants the A prefix and the C suffix with
    Alteration and Augmentation (the hand-worked mean `mean_after_alteration`), "rare" the P3 prefix and the S3 suffix with Chaos and Exalted Orbs."""
    from listing_support import magic_toy, prices, rare_toy, target

    from crafting_system.cli import make_plan
    from crafting_system.targets import start_price_key

    if kind == "magic":
        data = magic_toy()
        aim = target(data)
        entries = prices(start_price_key(data, aim))
    else:
        data = rare_toy()
        aim = target(data, rarity="rare", actions="chaos-orb, exalted-orb", wanted=("ToyP3", "ToyS3"))
        entries = prices(start_price_key(data, aim))
        entries.prices["Chaos Orb"] = type(entries.prices["Orb of Alteration"])(1.0, "fixture")
        entries.prices["Exalted Orb"] = type(entries.prices["Orb of Alteration"])(3.0, "fixture")
    return data, aim, entries, make_plan(data, aim, entries, solver="object")


def magic_hand() -> float:
    """The least mean cost of the magic toy from its listing, by hand: the draw, then the best of the four rules of `mean_after_alteration`
    (the listing's own price, the start price, is not in it)."""
    import itertools

    from listing_support import AUGMENTATION, mean_after_alteration

    from crafting_system.planner._offers import DRAW_COST_SHARE

    hand = min(mean_after_alteration(x, y) for x, y in itertools.product((False, True), repeat=2))
    return float(hand) + DRAW_COST_SHARE * AUGMENTATION  # the draw costs a tenth of the cheapest offer that costs something


@pytest.mark.parametrize("kind", ["magic", "rare"])
def test_the_table_at_an_unopened_listing_is_its_draw_and_never_above_the_exact_cost(kind):
    """The listing L is no state of the model; the table gives it h(L) = the draw's price + the mean of h over the draw's outcomes. It is at most
    the exact mean at L and at every opened state, and on the magic toy (Alteration, an erasing reroll, has its exact law; the Augmentation's
    chances are exact at each class: one side open, the other side's pool fixed) it is the hand-worked optimum. Before #1552 the table was
    off for a listing start and the round fell back on the floors, whose figure at L is the draw's price alone."""
    _data, aim, _entries, plan = listing_plan(kind)
    assert plan.start.flags.unopened
    floors = OfferFloors(plan.abstraction, plan.start, plan.offers, aim.start_item)
    table = missing_mods_table(floors)
    exact = plan.solution.values
    assert table.off is None
    assert table.lower(plan.start) == table.start
    assert table.start <= exact[plan.start]
    assert table.start == pytest.approx(exact[plan.start], rel=1e-6)
    assert table.start > min(offer.cost for offer in plan.offers if offer.offer.action.opens_listing)  # the floors' figure at L: the draw alone
    assert all(table.lower(state) <= value * (1 + TOLERANCE) for state, value in exact.items())
    assert sum(1 for state in exact if table.lower(state) > 0) > len(exact) // 3
    if kind == "magic":
        hand = magic_hand()
        assert exact[plan.start] == pytest.approx(hand, rel=1e-9)
        assert table.start <= hand and table.start == pytest.approx(hand, rel=1e-6)


def test_the_restart_into_a_listing_reads_h_at_the_listing_without_its_draw_twice():
    """The floors add the draw that follows a restart into a listing to the restart's cost (`through_listing`, `extra`); the table's restart law
    is the restart's own price plus h(L), which holds that draw already. The restart is the only way back to L, so with a cheap enough listing
    it is the best move at an opened state that holds no wanted mod, and the table there is c(restart) + h(L), never more."""
    _data, aim, _entries, plan = listing_plan("magic")
    floors = OfferFloors(plan.abstraction, plan.start, plan.offers, aim.start_item)
    restart = next(entry for entry in floors.entries if isinstance(entry.priced.offer.action, BuyStartItem))
    assert restart.extra > 0  # the draw that follows it
    table = missing_mods_table(floors)
    assert all(table.lower(state) <= restart.priced.cost + table.start for state in plan.solution.values)


def test_a_listing_with_no_draw_offered_has_its_table_off():
    _data, aim, _entries, plan = listing_plan("magic")
    offers = [offer for offer in plan.offers if not offer.offer.action.opens_listing]
    table = missing_mods_table(OfferFloors(plan.abstraction, plan.start, offers, aim.start_item))
    assert table.off is not None and "draw" in table.off
    assert table.lower(plan.start) == 0.0


def test_the_planner_reads_the_table_at_a_listing_and_gives_the_exact_plan(monkeypatch, floors_on):
    """Through the planner's entry: the envelope search of the magic toy builds the table with h(L) at the hand number, and its plan is exact."""
    from crafting_system.cli import make_plan
    from crafting_system.planner import _plan

    built = []

    def spy(*args, **kwargs):
        built.append(missing_mods_table(*args, **kwargs))
        return built[-1]

    monkeypatch.setattr(_plan, "MIN_OFFERS", 1)
    monkeypatch.setattr(_pattern_bound, "missing_mods_table", spy)
    _data, aim, entries, whole = listing_plan("magic")
    searched = make_plan(_data, aim, entries, solver="envelope")
    hand = magic_hand()
    assert built and built[0].off is None and built[0].start == pytest.approx(hand, rel=1e-6) and built[0].start <= hand
    assert searched.search is not None and searched.search.exact
    assert searched.solution.values[searched.start] == pytest.approx(whole.solution.values[whole.start], rel=1e-9)
    assert searched.solution.values[searched.start] == pytest.approx(hand, rel=1e-9)
