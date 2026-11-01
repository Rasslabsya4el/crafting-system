"""Imprint and restore as exact actions and their state (ticket #219, ADR-0034, ADR-0060).

Done when -> test:

* "Contract suite passes": the kinds `imprint` and `restore` are found by `test_actions_contract.py` on the fixture items of
  `contract_fixtures_imprint.py`; `test_the_contract_suite_runs_both_kinds_on_items_that_hold_imprints` runs `check_action` on them here too.
* "An imprint of a rare non-Talisman item is refused": `test_an_imprint_of_a_rare_item_that_is_not_a_talisman_is_refused` (the action and the kernel).
* "Restoring undoes an Awakener's Orb on the receiver": `test_a_restore_undoes_an_awakeners_orb_on_the_receiver` (concrete items and the compressed state).
* "Two imprints of one item can both be used": `test_two_imprints_of_one_item_can_both_be_used` (concrete items and the compressed state, cap 2).

The rest: the rules of ADR-0034 one by one, the claims, the beast prices, the state (a set in a stable order, forgotten with a fracture or a
corruption, carried by every other action, dropped by an action that builds a new item), the cap and the replacement, and the toy loop of
ADR-0060 solved by `solver.solve` (68 without an imprint, 12 with one).
"""

import dataclasses
import pickle
from fractions import Fraction

import pytest
from abstraction_pool import DAMAGE_1, GEM, LIFE_1, MANA_1, RESIST_2
from awakener_support import CRUSADER_SUFFIX, SHAPER_PREFIX
from contract_support import CONTRACT_DATA, GOAL, _item, _roll, check_action, contract_pairs, fixture_items
from items_support import AMULET

from crafting_system.abstraction import Abstraction, CompressedState, Goal, Wanted, integer_weights
from crafting_system.actions import (
    DEFAULT_MAX_IMPRINTS,
    Action,
    ActionError,
    Adds,
    Finite,
    FracturingOrb,
    AnnulmentOrb,
    AwakenersOrb,
    ChaosOrb,
    Imprint,
    ImprintMove,
    NotApplicableError,
    Reads,
    Restore,
    catalog,
    imprint_actions,
    kinds,
)
from crafting_system.cli._offers import FREE_ACTION_SHARE, offer_of, price_offers
from crafting_system.config import load_config
from crafting_system.data import BaseItem
from crafting_system.items import ExplicitMod, Influence, Item, ImprintError, Rarity
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.rules import rule_by_id
from crafting_system.solver import Action as SolverAction
from crafting_system.solver import Outcome, solve

CROAKER, ARACHNID = "magic", "rare_talisman"
MAGIC_BEAST, TALISMAN_BEAST = "Craicic Croaker", "Fenumal Plagued Arachnid"

NOT_A_TALISMAN = dataclasses.replace(
    CONTRACT_DATA,
    base_items={
        **CONTRACT_DATA.base_items,
        AMULET: dataclasses.replace(
            CONTRACT_DATA.base_items[AMULET], tags=tuple(tag for tag in CONTRACT_DATA.base_items[AMULET].tags if tag != "talisman")
        ),
    },
)


def item(rarity: Rarity, *mod_ids: str, **fields) -> Item:
    return _item(rarity, *(_roll(mod_id) for mod_id in mod_ids), **fields)


def magic(*mod_ids: str, **fields) -> Item:
    return item(Rarity.MAGIC, *mod_ids, **fields)


def rare(*mod_ids: str, **fields) -> Item:
    return item(Rarity.RARE, *mod_ids, **fields)


def with_imprints(held: Item, *snapshots: Item) -> Item:
    return dataclasses.replace(held, imprints=snapshots)


def space(*actions: Action, goal: Goal = GOAL) -> Abstraction:
    return Abstraction(CONTRACT_DATA, goal, AMULET, 84, list(actions))


# --- the contract suite -----------------------------------------------------------------------------


def test_the_two_kinds_are_registered_outside_the_planner_and_listed_for_a_magic_item():
    registered = {entry.name: entry for entry in kinds()}
    for name in ("imprint", "restore"):
        assert not registered[name].planner and "#223" in registered[name].why_not and registered[name].reads_item_state_while_not_planner == "any"
    listed = catalog(CONTRACT_DATA, magic(LIFE_1))
    assert [a for a in listed if isinstance(a, (Imprint, Restore))] == [
        Imprint(CROAKER),
        Imprint(CROAKER, 1, 0),
        Imprint(ARACHNID),  # the fixture amulet is a Talisman
        Imprint(ARACHNID, 1, 0),
        Restore(0),
    ]
    assert not [a for a in catalog(NOT_A_TALISMAN, magic(LIFE_1)) if isinstance(a, Imprint) and a.beast == ARACHNID]
    assert imprint_actions(CONTRACT_DATA, magic(LIFE_1, corrupted=True)) == ()


def test_the_contract_suite_runs_both_kinds_on_items_that_hold_imprints():
    pairs = [(action, name) for kind, action, name in contract_pairs() if kind in ("imprint", "restore")]
    assert {name for _, name in pairs} >= {"magic", "magic_imprinted", "rare_imprinted", "rare_junk"}
    applied = {type(action).__name__ for action, name in pairs if check_action(action, fixture_items()[name])}
    assert applied == {"Imprint", "Restore"}


def test_the_declarations_of_both_kinds():
    for action in (Imprint(CROAKER), Imprint(ARACHNID, 2, 1), Restore(1)):
        reads, adds = action.reads(CONTRACT_DATA), action.adds(CONTRACT_DATA)
        assert reads.imprints and reads.junk and reads.families == frozenset() and not reads.block_invariant and not reads.variants
        assert adds.imprints and adds.item_state and not adds.draws and adds.named in (frozenset(), None) and not adds.corrupts
        assert action.inputs(CONTRACT_DATA) == ()
    assert Imprint(CROAKER).imprint_move() == ImprintMove(False, None) and Imprint(CROAKER, 2, 1).imprint_move() == ImprintMove(False, 1)
    assert Restore(1).imprint_move() == ImprintMove(True, 1)
    assert ChaosOrb().imprint_move() is None and not ChaosOrb().reads(CONTRACT_DATA).imprints and not ChaosOrb().adds(CONTRACT_DATA).imprints
    with pytest.raises(ValueError):
        ImprintMove(restore=True)


# --- the rules of ADR-0034 --------------------------------------------------------------------------


def test_an_imprint_of_a_rare_item_that_is_not_a_talisman_is_refused():
    plain = rare(RESIST_2, LIFE_1)
    for beast in (CROAKER, ARACHNID):
        with pytest.raises(NotApplicableError):
            Imprint(beast).outcomes(NOT_A_TALISMAN, plain)
    for action in (Imprint(CROAKER), Imprint(ARACHNID)):  # the compressed state refuses it the same way
        ab = Abstraction(NOT_A_TALISMAN, GOAL, AMULET, 84, [action])
        with pytest.raises(NotApplicableError):
            ab.kernel(ab.compress(plain), action)
    Imprint(ARACHNID).outcomes(CONTRACT_DATA, plain)  # the same rare item is a rare Talisman in the fixture data
    with pytest.raises(NotApplicableError, match="Talisman"):
        Imprint(ARACHNID).outcomes(CONTRACT_DATA, magic(LIFE_1))
    with pytest.raises(NotApplicableError, match="magic"):
        Imprint(CROAKER).outcomes(CONTRACT_DATA, plain)
    with pytest.raises(NotApplicableError):
        Imprint(CROAKER).outcomes(CONTRACT_DATA, item(Rarity.NORMAL))


def test_the_croaker_imprints_a_magic_item_and_the_arachnid_a_rare_talisman_and_the_imprint_is_the_item_as_it_was():
    held = magic(LIFE_1)
    (chance, made), = Imprint(CROAKER).outcomes(CONTRACT_DATA, held).results
    assert chance == 1 and made.imprints == (held,) and dataclasses.replace(made, imprints=()) == held
    talisman = rare(RESIST_2, LIFE_1)
    (chance, made), = Imprint(ARACHNID).outcomes(CONTRACT_DATA, talisman).results
    assert made.imprints == (talisman,) and made.mods == talisman.mods


@pytest.mark.parametrize("make", [lambda: magic(LIFE_1, corrupted=True), lambda: rare(RESIST_2, LIFE_1, corrupted=True)])
def test_a_corrupted_item_takes_no_imprint_and_no_restore(make):
    corrupted = make()
    for action in (Imprint(CROAKER), Imprint(ARACHNID), Restore(0)):
        with pytest.raises(NotApplicableError, match="corrupted"):
            action.outcomes(CONTRACT_DATA, with_imprints(corrupted, magic(MANA_1)))


def test_a_fractured_item_takes_no_imprint_and_no_restore():
    fractured = Item.build(
        CONTRACT_DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=(_roll(RESIST_2, fractured=True), _roll(LIFE_1), _roll(MANA_1), _roll(DAMAGE_1))
    )
    for action in (Imprint(ARACHNID), Restore(0)):
        with pytest.raises(NotApplicableError, match="fractured"):
            action.outcomes(CONTRACT_DATA, with_imprints(fractured, magic(MANA_1)))


def test_an_imprint_is_refused_on_a_jewel():
    jewel_data = dataclasses.replace(
        CONTRACT_DATA, base_items={**CONTRACT_DATA.base_items, AMULET: dataclasses.replace(CONTRACT_DATA.base_items[AMULET], item_class="Jewel")}
    )
    with pytest.raises(NotApplicableError, match="jewel"):
        Imprint(CROAKER).outcomes(jewel_data, magic(LIFE_1))
    assert imprint_actions(jewel_data, magic(LIFE_1)) == ()


def test_a_restore_returns_the_item_to_the_imprint_and_uses_it_up():
    snapshot = magic(MANA_1)
    held = with_imprints(rare(RESIST_2, LIFE_1), snapshot, magic(LIFE_1))
    (chance, made), = Restore(0).outcomes(CONTRACT_DATA, held).results
    assert chance == 1 and made == dataclasses.replace(snapshot, imprints=(magic(LIFE_1),))  # the other imprint stays
    (_, other), = Restore(1).outcomes(CONTRACT_DATA, held).results
    assert other == dataclasses.replace(magic(LIFE_1), imprints=(snapshot,))
    with pytest.raises(NotApplicableError, match="holds 2 imprints"):
        Restore(2).outcomes(CONTRACT_DATA, held)
    with pytest.raises(NotApplicableError):
        Restore(0).outcomes(CONTRACT_DATA, rare(RESIST_2, LIFE_1))


def test_a_restore_brings_back_the_strands_and_the_rarity_with_the_mods():
    snapshot = dataclasses.replace(magic(LIFE_1), memory_strands=7)
    later = dataclasses.replace(with_imprints(rare(RESIST_2, MANA_1), snapshot), memory_strands=2)
    (_, back), = Restore(0).outcomes(CONTRACT_DATA, later).results
    assert back.memory_strands == 7 and back.rarity is Rarity.MAGIC and [e.mod_id for e in back.mods] == [LIFE_1] and back.imprints == ()


def test_a_recombinator_output_is_a_new_item_and_holds_no_imprint():
    # an action that builds a new item (Item.build) gives it no imprints, so nothing restores it (imprint.not_for_derived_items)
    from crafting_system.actions import Recombinator

    first = with_imprints(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1), rare(RESIST_2, LIFE_1))
    action = next(a for a in catalog(CONTRACT_DATA, first) if isinstance(a, Recombinator))
    outcomes = action.outcomes(CONTRACT_DATA, first)
    results = [part.retained for _, part in outcomes.components]
    assert results and all(result.imprints == () for result in results)


# --- prices and claims ------------------------------------------------------------------------------


def test_the_beasts_are_priced_from_the_price_file_and_a_restore_is_free():
    assert dict(Imprint(CROAKER).resources()) == {MAGIC_BEAST: 1} and dict(Imprint(ARACHNID, 2, 0).resources()) == {TALISMAN_BEAST: 1}
    assert dict(Restore(0).resources()) == {}
    prices = {MAGIC_BEAST: PriceEntry(7.0, "test"), TALISMAN_BEAST: PriceEntry(40.0, "test")}
    import datetime

    file = PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, prices)
    offers = [offer_of(a, a.label(CONTRACT_DATA), CONTRACT_DATA, magic(LIFE_1)) for a in (Imprint(CROAKER), Imprint(ARACHNID), Restore(0))]
    priced, dropped = price_offers(offers, file)
    assert not dropped
    costs = {entry.label: entry.cost for entry in priced}
    assert costs["Imprint with the Craicic Croaker"] == 7.0 and costs["Imprint with the Fenumal Plagued Arachnid"] == 40.0
    assert costs["Restore imprint 1"] == pytest.approx(FREE_ACTION_SHARE * 7.0)  # a free action costs a share of the cheapest offer that costs something


def test_the_eleven_claims_are_in_the_registry_with_the_unverified_ones_stamped():
    ids = [
        "imprint.eternal_orb_creates",
        "imprint.eternal_orb_not_dropped",
        "imprint.beast_recipes",
        "imprint.restores_state",
        "imprint.refused_on_fractured",
        "imprint.refused_on_corrupted_mirrored",
        "imprint.not_for_derived_items",
        "imprint.talisman_craft_replaced_transform",
        "imprint.consumed_on_restore",
        "imprint.several_per_item",
        "imprint.allflame_copy_not_restorable",
    ]
    rules = {rule_id: rule_by_id(rule_id) for rule_id in ids}
    assert dict(rules["imprint.beast_recipes"].value) == {"magic": MAGIC_BEAST, "rare_talisman": TALISMAN_BEAST}
    stamped = {rule_id for rule_id, rule in rules.items() if rule.statement.startswith("UNVERIFIED")}
    assert stamped == {"imprint.consumed_on_restore", "imprint.several_per_item", "imprint.allflame_copy_not_restorable"}
    assert not any(rule.approximate for rule in rules.values())  # the owner decided used up and several (grill B3): not marked approximate
    assert Imprint(CROAKER).claims() <= set(ids) and Restore(0).claims() == {
        "imprint.restores_state", "imprint.refused_on_fractured", "imprint.refused_on_corrupted_mirrored", "imprint.not_for_derived_items",
        "imprint.consumed_on_restore", "awakener.imprint_restores_receiver_only",
    }


# --- the Awakener's Orb -----------------------------------------------------------------------------


def shaper(*mod_ids: str, rarity: Rarity = Rarity.MAGIC, **fields) -> Item:
    return item(rarity, *mod_ids, influences=frozenset({Influence.SHAPER}), **fields)


def test_a_restore_undoes_an_awakeners_orb_on_the_receiver():
    receiver = shaper(SHAPER_PREFIX)
    orb = AwakenersOrb(AMULET, 84, Influence.CRUSADER, CRUSADER_SUFFIX)
    (_, imprinted), = Imprint(CROAKER).outcomes(CONTRACT_DATA, receiver).results
    results = [part.retained for _, part in orb.outcomes(CONTRACT_DATA, imprinted).components]
    assert results and all(r.rarity is Rarity.RARE and r.influences == {Influence.SHAPER, Influence.CRUSADER} for r in results)
    for awakened in results:
        assert awakened.imprints == (receiver,)  # the receiver keeps its imprint through the orb
        (_, restored), = Restore(0).outcomes(CONTRACT_DATA, awakened).results
        assert restored == receiver  # the receiver as it was, with both influences gone and the imprint used up
    (need,) = orb.inputs(CONTRACT_DATA, imprinted)
    assert need.start.imprints == () == need.want.imprints  # the donor is consumed with nothing of its own: never brought back

    ab = space(orb, Imprint(CROAKER), Restore(0))  # the same in the compressed state
    start = ab.compress(receiver)
    (held,) = ab.kernel(start, Imprint(CROAKER))
    assert held.imprints == (start,)
    awakened = ab.kernel(held, orb)
    assert awakened and all(state.flags.rarity is Rarity.RARE and state.imprints == (start,) for state in awakened)
    for state in awakened:
        assert dict(ab.kernel(state, Restore(0))) == {start: 1}
    assert ab.inputs(held, orb)[0].want.imprints == ()


# --- two imprints, the cap and the replacement ------------------------------------------------------


def test_two_imprints_of_one_item_can_both_be_used():
    first, second = magic(LIFE_1), magic(MANA_1)
    held = with_imprints(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1), first, second)
    (_, one), = Restore(0).outcomes(CONTRACT_DATA, held).results
    (_, two), = Restore(0).outcomes(CONTRACT_DATA, one).results
    assert one == dataclasses.replace(first, imprints=(second,)) and two == second  # both used, one after the other
    actions = imprint_actions(CONTRACT_DATA, held, 2)
    assert Restore(0) in actions and Restore(1) in actions and Imprint(ARACHNID, 2, 1) in actions

    ab = space(*actions)  # in the compressed state
    start = ab.compress(held)
    assert len(start.imprints) == 2 and ab.tracks_imprints
    (back_first,) = ab.kernel(start, Restore(0))
    (back_second,) = ab.kernel(start, Restore(1))
    assert {len(back_first.imprints), len(back_second.imprints)} == {1} and back_first != back_second
    (last,) = ab.kernel(back_first, Restore(0))
    assert last.imprints == () and last in {ab.compress(first), ab.compress(second)}
    assert {replace_bare(back_first), replace_bare(back_second)} == {ab.compress(first), ab.compress(second)}


def replace_bare(state: CompressedState) -> CompressedState:
    return dataclasses.replace(state, imprints=())


def test_two_imprints_can_be_made_one_after_the_other_and_both_are_then_held():
    ab = space(Imprint(ARACHNID, 2), AnnulmentOrb(), Restore(0), Restore(1))
    start = ab.compress(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1))
    (one,) = ab.kernel(start, Imprint(ARACHNID, 2))
    later = next(iter(ab.kernel(one, AnnulmentOrb())))  # an annulment moves the item to another state, the imprint stays
    (two,) = ab.kernel(later, Imprint(ARACHNID, 2))
    bare = replace_bare(later)  # the state the second imprint is made at: `later` still holds the first imprint
    assert later.imprints == (start,) and replace_bare(two) == bare
    assert two.imprints == tuple(sorted({start, bare}, key=lambda s: s.order_key))
    used = []
    for index in (0, 1):  # the imprint of the state the item is in is refused (it would be burnt for nothing); the other is restored
        try:
            used.append(next(iter(ab.kernel(two, Restore(index)))))
        except NotApplicableError:
            pass
    assert used == [dataclasses.replace(start, imprints=(bare,))]  # the first imprint restored, the second still held
    assert dict(ab.kernel(used[0], Restore(0))) == {bare: 1}  # and the second restored in turn: both imprints used


def test_a_full_item_takes_a_new_imprint_only_by_replacing_one():
    ab = space(Imprint(ARACHNID, 2), Imprint(ARACHNID, 2, 0), Imprint(ARACHNID, 2, 1), AnnulmentOrb())
    start = ab.compress(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1))
    (one,) = ab.kernel(start, Imprint(ARACHNID, 2))
    later = next(iter(ab.kernel(one, AnnulmentOrb())))
    (two,) = ab.kernel(later, Imprint(ARACHNID, 2))
    with pytest.raises(NotApplicableError, match="most it may"):
        ab.kernel(two, Imprint(ARACHNID, 2))
    with pytest.raises(NotApplicableError, match="room"):
        ab.kernel(one, Imprint(ARACHNID, 2, 0))
    third = next(iter(ab.kernel(two, AnnulmentOrb())))
    for index in (0, 1):
        (replaced,) = ab.kernel(third, Imprint(ARACHNID, 2, index))
        kept = [entry for position, entry in enumerate(third.imprints) if position != index]  # the others stay, the k-th is given up
        assert replaced.imprints == tuple(sorted([*kept, replace_bare(third)], key=lambda s: s.order_key))


def test_the_default_cap_is_one_and_the_setting_is_read_by_the_config():
    assert DEFAULT_MAX_IMPRINTS == 1 == load_config({}).max_imprints
    assert Imprint(CROAKER).limit == 1
    one = [a for a in imprint_actions(CONTRACT_DATA, magic(LIFE_1)) if isinstance(a, Imprint) and a.beast == CROAKER]
    assert one == [Imprint(CROAKER, 1), Imprint(CROAKER, 1, 0)]
    three = [a for a in imprint_actions(CONTRACT_DATA, magic(LIFE_1), 3) if isinstance(a, Restore)]
    assert three == [Restore(0), Restore(1), Restore(2)]
    with pytest.raises(NotApplicableError, match="more than"):
        Imprint(CROAKER).outcomes(CONTRACT_DATA, with_imprints(magic(LIFE_1), magic(MANA_1), magic(RESIST_2)))
    with pytest.raises(ValueError):
        Imprint(CROAKER, 0)
    with pytest.raises(ValueError):
        Imprint(CROAKER, 1, 1)
    with pytest.raises(ValueError):
        Imprint("rare")


# --- the state --------------------------------------------------------------------------------------


def test_a_state_holds_imprints_only_when_an_enabled_action_makes_or_uses_one():
    held = with_imprints(magic(LIFE_1), magic(MANA_1))
    without = space(ChaosOrb())
    assert not without.tracks_imprints and without.compress(held) == without.compress(magic(LIFE_1)) and without.compress(held).imprints == ()
    assert "imprints" not in repr(without.compress(held))
    tracking = space(Imprint(CROAKER))
    state = tracking.compress(held)
    assert tracking.tracks_imprints and len(state.imprints) == 1 and "imprints=" in repr(state)
    assert state.imprints[0] == tracking.compress(magic(MANA_1)) and state.imprints[0].imprints == ()


def test_the_imprints_of_a_state_are_a_set_in_a_stable_order():
    ab = space(Imprint(CROAKER, 3))
    one, two = magic(LIFE_1), magic(MANA_1)
    a = ab.compress(with_imprints(rare(RESIST_2, LIFE_1), one, two))
    b = ab.compress(with_imprints(rare(RESIST_2, LIFE_1), two, one))
    twice = ab.compress(with_imprints(rare(RESIST_2, LIFE_1), one, one, two))
    assert a == b == twice and hash(a) == hash(b) and len(a.imprints) == 2  # a second imprint of one state is the same state
    assert [s.order_key for s in a.imprints] == sorted(s.order_key for s in a.imprints)

    def plain(value) -> bool:
        return isinstance(value, (str, int, bool)) or (isinstance(value, tuple) and all(plain(entry) for entry in value))

    assert plain(a.order_key)
    assert pickle.loads(pickle.dumps(a)) == a and pickle.loads(pickle.dumps(a)).order_key == a.order_key


def test_the_kernel_of_an_imprint_and_of_a_restore_is_certain_and_a_dominated_move_is_refused():
    ab = space(Imprint(CROAKER), Imprint(CROAKER, 2), Restore(0))
    start = ab.compress(magic(LIFE_1))
    assert dict(ab.kernel(start, Imprint(CROAKER))) == {dataclasses.replace(start, imprints=(start,)): 1}
    with pytest.raises(NotApplicableError, match="never helps"):  # a second imprint of the state held changes nothing
        ab.kernel(dataclasses.replace(start, imprints=(start,)), Imprint(CROAKER, 2))
    with pytest.raises(NotApplicableError, match="holds 0 imprints"):
        ab.kernel(start, Restore(0))
    with pytest.raises(NotApplicableError, match="only use the imprint up"):  # a restore onto the state the item is in
        ab.kernel(dataclasses.replace(start, imprints=(start,)), Restore(0))


def test_every_other_action_carries_the_imprints_and_a_fracture_or_a_corruption_forgets_them():
    ab = space(Imprint(ARACHNID), Restore(0), ChaosOrb(), FracturingOrb(), AnnulmentOrb())
    start = ab.compress(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1))
    (held,) = ab.kernel(start, Imprint(ARACHNID))
    for action in (ChaosOrb(), AnnulmentOrb()):
        kernel = ab.kernel(held, action)
        assert kernel and all(state.imprints == (start,) for state in kernel)
    fractured = ab.kernel(held, FracturingOrb())
    assert fractured and all(state.fractured and state.imprints == () for state in fractured)  # no imprint can be used on it, so none is kept
    for state in fractured:
        with pytest.raises(NotApplicableError):
            ab.kernel(state, Restore(0))
    corrupt = dataclasses.replace(held, flags=dataclasses.replace(held.flags, corrupted=True))
    with pytest.raises(ActionError):
        ab.kernel(corrupt, Restore(0))


def test_a_corrupted_or_fractured_start_item_holds_no_imprint_in_the_state():
    ab = space(Imprint(ARACHNID))
    start = with_imprints(rare(RESIST_2, LIFE_1), magic(MANA_1))
    assert len(ab.compress(start).imprints) == 1
    assert ab.compress(dataclasses.replace(start, corrupted=True)).imprints == ()
    fractured = Item.build(
        CONTRACT_DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE,
        mods=(_roll(RESIST_2, fractured=True), _roll(LIFE_1), _roll(MANA_1), _roll(DAMAGE_1)), imprints=(magic(MANA_1),),
    )
    assert ab.compress(fractured).imprints == ()


@dataclasses.dataclass(frozen=True)
class BuildNew(Action):
    """A toy that builds a new item from nothing (as a recombinator does): the result is a rare item with one fixed mod."""

    def label(self, data=None) -> str:
        return "Build a new item"

    def resources(self, data=None) -> dict[str, int]:
        return {"Toy": 1}

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=None, draws=False)

    def outcomes(self, data, item: Item) -> Finite:
        made = Item.build(data, base_id=item.base_id, item_level=item.item_level, rarity=Rarity.RARE, mods=(_roll(LIFE_1),))
        return Finite(data, item, ((Fraction(1), made),))


def test_an_action_that_builds_a_new_item_gives_it_no_imprint():
    ab = space(Imprint(ARACHNID), BuildNew())
    start = ab.compress(rare(RESIST_2, LIFE_1))
    (held,) = ab.kernel(start, Imprint(ARACHNID))
    (built,) = ab.kernel(held, BuildNew())
    assert built.imprints == () and built.flags.rarity is Rarity.RARE


def test_the_coarse_state_and_the_walk_of_a_pilot_count():
    from crafting_system.abstraction import Coarsening
    from crafting_system.actions import OutOfScopeError

    ab = space(Imprint(ARACHNID))
    coarsening = Coarsening.pooling_irrelevant(space())
    block = coarsening.coarsen(space().compress(rare(RESIST_2, LIFE_1)))
    for bound in ("lower", "upper"):
        with pytest.raises(OutOfScopeError):
            coarsening.kernel(block, Imprint(ARACHNID), bound)
    from crafting_system.abstraction import needs_walk

    assert needs_walk(ab, [Imprint(ARACHNID), Restore(0)])  # a real kernel is run for them: no closed form


# --- the item ---------------------------------------------------------------------------------------


def test_an_item_holds_imprints_that_hold_none_and_they_are_part_of_its_value():
    held = with_imprints(magic(LIFE_1), magic(MANA_1))
    held.validate(CONTRACT_DATA)
    assert held != magic(LIFE_1) and hash(held) != hash(magic(LIFE_1)) and held.changed(CONTRACT_DATA) == held
    with pytest.raises(ImprintError):
        dataclasses.replace(magic(LIFE_1), imprints=(held,))
    with pytest.raises(ImprintError):
        dataclasses.replace(magic(LIFE_1), imprints=[magic(MANA_1)])
    with pytest.raises(ImprintError):
        dataclasses.replace(magic(LIFE_1), imprints=("not an item",))
    assert Item(AMULET, 84, Rarity.NORMAL).imprints == ()


# --- the toy loop of ADR-0060 -----------------------------------------------------------------------

START = ("start",)


@dataclasses.dataclass(frozen=True)
class Risk(Action):
    """One risky try on the starting rare Talisman: one time in four it gains the wanted mod, otherwise it is left with junk."""

    def label(self, data=None) -> str:
        return "Risky try"

    def resources(self, data=None) -> dict[str, int]:
        return {"Toy": 2}

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=None)

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=None, draws=True)

    def outcomes(self, data, item: Item) -> Finite:
        if len(item.mods) != 2:  # the starting item has two mods (a state stands for the family of each, so the ids are not asked)
            raise NotApplicableError("the try is made on the starting item only")
        won = item.changed(data, mods=(*item.mods, _roll(GEM)))
        lost = item.changed(data, mods=(_roll(MANA_1),))
        return Finite(data, item, ((Fraction(1, 4), won), (Fraction(3, 4), lost)))


@dataclasses.dataclass(frozen=True)
class Rebuild(Action):
    """Build the starting item again from a junk item, at 20."""

    def label(self, data=None) -> str:
        return "Build again"

    def resources(self, data=None) -> dict[str, int]:
        return {"Toy": 20}

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=None)

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=None, draws=False)

    def outcomes(self, data, item: Item) -> Finite:
        if len(item.mods) != 1:
            raise NotApplicableError("only the junk item is built again")
        return Finite(data, item, ((Fraction(1), rare(RESIST_2, LIFE_1)),))


class ToyLoop:
    """The solver's model over the kernels of the state: every action at its price, the restore at the nominal one."""

    COSTS = {Risk: 2.0, Rebuild: 20.0, Imprint: 1.0, Restore: 1e-6}

    def __init__(self, ab: Abstraction, offered) -> None:
        self.ab, self.offered = ab, offered

    def is_goal(self, state) -> bool:
        return self.ab.is_goal(state)

    def actions(self, state):
        found = []
        for action in self.offered:
            try:
                kernel = self.ab.kernel(state, action)
            except ActionError:
                continue
            found.append(
                SolverAction(action.label(CONTRACT_DATA), self.COSTS[type(action)], tuple(Outcome(s, w) for s, w in integer_weights(kernel).items()))
            )
        return found


def test_the_toy_loop_costs_68_without_an_imprint_and_12_with_one():
    goal = Goal((Wanted(frozenset({GEM})),))
    plain = ToyLoop(space(Risk(), Rebuild(), goal=goal), [Risk(), Rebuild()])
    imprinted_actions = [Risk(), Rebuild(), Imprint(ARACHNID), Restore(0)]
    imprinting = ToyLoop(space(*imprinted_actions, goal=goal), imprinted_actions)
    start = plain.ab.compress(rare(RESIST_2, LIFE_1))
    assert solve(plain, [start]).values[start] == pytest.approx(68.0, abs=1e-6)
    start = imprinting.ab.compress(rare(RESIST_2, LIFE_1))
    solution = solve(imprinting, [start])
    assert solution.values[start] == pytest.approx(12.0, abs=1e-4)  # 1 + 2 per try, one try in four: (1 + 2) / (1/4), the restore a few millionths
    assert [a.label for a in solution.policy.values()].count("Restore imprint 1") >= 1


def test_the_kernel_key_of_a_move_is_its_kernel_so_two_restores_are_never_merged():
    ab = space(Imprint(ARACHNID, 2), Imprint(ARACHNID, 2, 0), Imprint(ARACHNID, 2, 1), Restore(0), Restore(1), AnnulmentOrb())
    start = ab.compress(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1))
    (one,) = ab.kernel(start, Imprint(ARACHNID, 2))
    later = next(iter(ab.kernel(one, AnnulmentOrb())))
    (two,) = ab.kernel(later, Imprint(ARACHNID, 2))
    keys = {}
    for action in (Restore(0), Restore(1)):
        try:
            keys[action] = ab.kernel_key(two, action)
        except NotApplicableError:
            continue
    assert len(keys) == 1  # the other restores onto the state the item is in and is refused, as the kernel refuses it
    third = next(iter(ab.kernel(two, AnnulmentOrb())))
    assert ab.kernel_key(third, Imprint(ARACHNID, 2, 0)) != ab.kernel_key(third, Imprint(ARACHNID, 2, 1))
