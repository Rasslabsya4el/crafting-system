"""The socket contract and the Jeweller's Orb, the Orb of Fusing and the bench's count and link crafts (ticket #228, B6 S2; ADR-0046, ADR-0047).

"Done when", test by test:

* the contract suite passes for each action (`test_each_socket_action_meets_the_contract_on_every_socket_fixture`; the shared suite asks them
  too, through `contract_fixtures_sockets.py`) and checks that an action not declaring sockets leaves them unchanged and that no socket
  action changes mods (the `test_the_suite_catches_*` tests and `test_no_other_kind_changes_sockets`);
* the expected Jeweller's Orbs to six sockets at item level 84 are 214.9 (plan) and 222.6 (second reading), to five or more 35.7 and 36.9, by
  value iteration over the kernel (`test_expected_jewellers_orbs_by_value_iteration_over_the_kernel`);
* Fusing all linked is 66.1, 33.7, 19.9, 0.83 and 0.10% for 2 to 6 sockets and the 6-link one in a thousand (`test_fusing_all_linked`);
* `chance_all` against exhaustive enumeration on four sockets (`test_chance_all_equals_exhaustive_enumeration_on_four_sockets`);
* the claims' marks and the registry are in `test_actions_sockets_claims.py`, the bench options of the real data in `test_actions_sockets_real.py`.
"""

import dataclasses
import itertools
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2
from contract_support import CONTRACT_DATA, GOAL, check_action, check_socket_declarations, finished, fixture_items, extra_fixture_items
from items_support import AMULET, BODY
from sockets_support import (
    ABYSS_MOD,
    BOW,
    FOUR_SOCKET_WEIGHTS,
    FUSING_WEIGHTS,
    GATE,
    HELMET,
    PLAN_WEIGHTS,
    SECOND_WEIGHTS,
    SWORD,
    B,
    G,
    R,
    W,
    abyss_data,
    bench_data,
    expected_jeweller_orbs,
    jeweller_chances,
    socket_data,
    socketed,
    sockets_of,
    white,
)

from crafting_system.actions import (
    JEWELLER_TABLE,
    Action,
    Adds,
    BenchSocketCount,
    BenchSocketLinks,
    JewellersOrb,
    NotApplicableError,
    OrbOfFusing,
    OutOfScopeError,
    Reading,
    Reads,
    ScouringOrb,
    catalog,
    fusing_links,
    item_level_gate,
    jeweller_weights,
    kinds,
    model_readings,
    resized_sockets,
)
from crafting_system.items import ExplicitMod, Item, Rarity, Sockets

DATA = socket_data()
SECOND = Reading.of({"jeweller_table": "chris_wilson_2014"})
SOCKET_KINDS = ("jewellers-orb", "orb-of-fusing", "bench-socket-count", "bench-socket-links")


def jeweller(item, *, omen=False, reading=None):
    return JewellersOrb(omen=omen).outcomes_under(DATA, item, reading)


def counts(outcomes) -> dict[int, Fraction]:
    return {sockets.count: chance for sockets, chance in outcomes.by_sockets.items()}


# --- the declarations on the contract ---------------------------------------------------------------------------------------------------


def test_the_socket_flags_default_to_leaving_the_sockets_alone():
    assert not Reads().sockets and not Adds().sockets
    assert not any(builder().sockets for builder in (Reads.adding, Reads.nothing))
    assert not any(builder().sockets for builder in (Adds.removal, Adds.rerolling, Adds.erasing))
    assert not Adds().only_sockets


def test_the_sockets_are_not_item_state():
    assert not Reads(socket_count=True, socket_links=True, socket_colours=True).item_state
    assert not Adds(socket_count=True, socket_links=True, socket_colours=True).item_state
    assert Reads(socket_links=True, quality=True).item_state and Adds(socket_links=True, offer=True).item_state


def test_a_change_of_the_count_changes_the_links_and_the_colours_too():
    with pytest.raises(ValueError, match="link groups and the colours"):
        Adds(socket_count=True)
    with pytest.raises(ValueError, match="link groups and the colours"):
        Adds(socket_count=True, socket_links=True)
    assert Adds(socket_count=True, socket_links=True, socket_colours=True).sockets


def test_a_socket_action_adds_no_mod_and_draws_none():
    links = Adds.socket_action(links=True)
    assert (links.socket_count, links.socket_links, links.socket_colours) == (False, True, False)
    assert links.named == frozenset() and not links.draws and links.keeps_crafted and links.only_sockets
    count = Adds.socket_action(count=True)
    assert (count.socket_count, count.socket_links, count.socket_colours) == (True, True, True)
    assert Adds.socket_action(colours=True).socket_colours and not Adds.socket_action(colours=True).socket_links
    with pytest.raises(ValueError, match="count, the links or the colours"):
        Adds.socket_action()
    assert not Adds(named=frozenset(), draws=False).only_sockets
    assert not Adds(socket_links=True).only_sockets  # it may draw mods


@dataclasses.dataclass(frozen=True)
class Undeclared(ScouringOrb):
    """An action that declares nothing: it reads and adds everything, the sockets included, like it reads every mod."""

    def reads(self, data):
        return Action.reads(self, data)

    def adds(self, data=None, item=None):
        return Action.adds(self, data, item)


def test_an_action_that_declares_nothing_reads_and_adds_the_sockets():
    reads, adds = Undeclared().reads(DATA), Undeclared().adds(DATA, None)
    assert (reads.socket_count, reads.socket_links, reads.socket_colours) == (True, True, True)
    assert (adds.socket_count, adds.socket_links, adds.socket_colours) == (True, True, True)
    assert not adds.only_sockets  # it may change mods as well


DECLARED = {
    # action: (reads: count, links, colours; adds: count, links, colours)
    JewellersOrb(): ((True, False, False), (True, True, True)),
    JewellersOrb(omen=True): ((True, False, False), (True, True, True)),
    OrbOfFusing(): ((True, True, False), (False, True, False)),
    OrbOfFusing(omen=True): ((True, True, False), (False, True, False)),
    BenchSocketCount(2): ((True, False, False), (True, True, True)),
    BenchSocketLinks(2): ((True, True, False), (False, True, False)),
}


@pytest.mark.parametrize("action", list(DECLARED), ids=lambda action: action.label(DATA))
def test_each_socket_action_declares_what_it_reads_and_sets(action):
    reads, adds = action.reads(DATA), action.adds(DATA, None)
    wanted_reads, wanted_adds = DECLARED[action]
    assert (reads.socket_count, reads.socket_links, reads.socket_colours) == wanted_reads
    assert (adds.socket_count, adds.socket_links, adds.socket_colours) == wanted_adds
    assert adds.only_sockets and not reads.item_state or isinstance(action, OrbOfFusing)  # only the Orb of Fusing reads (the plain) quality
    assert reads.junk and reads.families == frozenset() and not reads.block_invariant


def test_the_socket_kinds_are_in_the_catalog_and_outside_the_planner():
    by_name = {entry.name: entry for entry in kinds()}
    for name in SOCKET_KINDS:
        assert not by_name[name].planner and "ADR-0045" in by_name[name].why_not and by_name[name].applies_only_to
    planner = {type(action) for action in catalog(bench_data(), socketed(white(2)), planner_only=True)}
    assert not planner & {JewellersOrb, OrbOfFusing, BenchSocketCount, BenchSocketLinks}


def test_the_kinds_list_their_actions_only_for_a_class_that_takes_sockets():
    amulet = fixture_items()["rare_junk"]
    assert amulet.base_id == AMULET and not any(type(a) in {JewellersOrb, OrbOfFusing, BenchSocketCount, BenchSocketLinks} for a in catalog(CONTRACT_DATA, amulet))
    labels = [action.label(DATA) for action in catalog(bench_data(), socketed(white(2)))]
    for label in ("Jeweller's Orb", "Jeweller's Orb with Omen of the Jeweller", "Orb of Fusing", "Orb of Fusing with Omen of Connections"):
        assert label in labels
    assert [a.label(DATA) for a in catalog(bench_data(), socketed(white(2))) if isinstance(a, BenchSocketCount)] == [f"Bench craft {n} sockets" for n in range(2, 7)]
    assert [a.label(DATA) for a in catalog(bench_data(), socketed(white(2))) if isinstance(a, BenchSocketLinks)] == [f"Bench craft {n} links" for n in range(2, 7)]


# --- the contract suite on each action --------------------------------------------------------------------------------------------------


EXTRA = extra_fixture_items()
SOCKET_ITEMS = sorted(name for name in EXTRA if name.startswith("sockets_"))
APPLIES = {  # the items an action is not refused on (the rest are refused by the game or by the rules)
    "jewellers-orb": {"sockets_body_three", "sockets_body_linked_stranded", "sockets_body_low_level", "sockets_sword_two", "sockets_bow_five"},
    "orb-of-fusing": {"sockets_body_three", "sockets_body_linked_stranded", "sockets_body_low_level"},
    "bench-socket-count": {"sockets_body_three", "sockets_body_linked_stranded", "sockets_body_six_linked", "sockets_bow_five"},
    "bench-socket-links": {"sockets_body_three", "sockets_body_six_linked", "sockets_body_low_level", "sockets_bow_five"},
}


@pytest.mark.parametrize("name", SOCKET_ITEMS)
@pytest.mark.parametrize("kind_name", SOCKET_KINDS)
def test_each_socket_action_meets_the_contract_on_every_socket_fixture(kind_name, name):
    extra = EXTRA[name]
    entry = next(entry for entry in kinds() if entry.name == kind_name)
    actions = list(entry.members(extra.data, extra.item))
    assert actions, f"{kind_name} lists an action for the item {name}"
    for action in actions:
        assert isinstance(check_action(action, extra.item, extra.data), bool)  # False where the game refuses it: the check then holds the refusal


def test_the_actions_apply_where_the_game_lets_them_and_the_suite_checked_them_there():
    for kind_name, wanted in APPLIES.items():
        entry = next(entry for entry in kinds() if entry.name == kind_name)
        for name in SOCKET_ITEMS:
            extra = EXTRA[name]
            applied = []
            for action in entry.members(extra.data, extra.item):
                try:
                    action.outcomes_under(extra.data, extra.item)
                    applied.append(action)
                except (NotApplicableError, OutOfScopeError):
                    pass
            assert bool(applied) == (name in wanted), f"{kind_name} on {name}"


# --- the suite catches a wrong declaration ----------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SilentFusing(OrbOfFusing):
    """An Orb of Fusing that changes the links and does not say so."""

    def adds(self, data=None, item=None):
        return Adds(named=frozenset(), draws=False)


@dataclasses.dataclass(frozen=True)
class SilentJeweller(JewellersOrb):
    """A Jeweller's Orb that says it changes the links only."""

    def adds(self, data=None, item=None):
        return Adds.socket_action(links=True)


@dataclasses.dataclass(frozen=True)
class RecolouringFusing(OrbOfFusing):
    """An Orb of Fusing that turns the sockets white and says it changes the links only."""

    def outcomes(self, data, item):
        found = super().outcomes(data, item)
        whitened = tuple((chance, result.changed(data, sockets=Sockets((W,) * result.sockets.count, result.sockets.links))) for chance, result in found.results)
        return type(found)(data, item, whitened)


@dataclasses.dataclass(frozen=True)
class ModEatingFusing(OrbOfFusing):
    """An Orb of Fusing, declared as a socket action, that also removes the item's last mod."""

    def outcomes(self, data, item):
        found = super().outcomes(data, item)
        return type(found)(data, item, tuple((chance, result.changed(data, mods=result.mods[:-1])) for chance, result in found.results))


@dataclasses.dataclass(frozen=True)
class NeedsALink(OrbOfFusing):
    """An Orb of Fusing that refuses an item with no link yet, and does not say it reads the links."""

    def reads(self, data):
        return Reads(junk=True, families=frozenset(), quality=True, socket_count=True)

    def outcomes(self, data, item):
        if all(size == 1 for size in item.sockets.links):
            raise NotApplicableError("the toy needs a link")
        return super().outcomes(data, item)


@dataclasses.dataclass(frozen=True)
class ColourBlindJeweller(JewellersOrb):
    """A Jeweller's Orb that never gives five sockets to an item whose first socket is red, and does not say it reads the colours."""

    def outcomes(self, data, item, reading=None):
        found = super().outcomes(data, item, reading)
        keep = [(chance, result) for chance, result in found.results if not (item.sockets.colours[0] is R and result.sockets.count == 5)]
        total = sum(chance for chance, _ in keep)
        return type(found)(data, item, tuple((chance / total, result) for chance, result in keep))


@dataclasses.dataclass(frozen=True)
class SocketThief(ScouringOrb):
    """An Orb of Scouring that also resets the sockets, and declares the mods only."""

    def outcomes(self, data, item):
        found = super().outcomes(data, item)
        return type(found)(data, found.retained.changed(data, sockets=white(1)))


LINKED = socketed(sockets_of(R, R, G, W, links=(2, 1, 1)), mods=(RESIST_2, LIFE_1))
MIXED = socketed(sockets_of(R, G, B), mods=(RESIST_2, LIFE_1))


def test_an_action_that_changes_the_links_without_adds_socket_links_is_caught():
    with pytest.raises(AssertionError, match="adds.socket_links"):
        check_action(SilentFusing(), MIXED, DATA)


def test_an_action_that_changes_the_count_without_adds_socket_count_is_caught():
    with pytest.raises(AssertionError, match="adds.socket_count"):
        check_action(SilentJeweller(), MIXED, DATA)


def test_an_action_that_changes_the_colours_without_adds_socket_colours_is_caught():
    with pytest.raises(AssertionError, match="adds.socket_colours"):
        check_action(RecolouringFusing(), MIXED, DATA)


def test_a_socket_action_that_changes_a_mod_is_caught():
    with pytest.raises(AssertionError, match="changes no mod"):
        check_action(ModEatingFusing(), MIXED, DATA)


def test_an_action_that_depends_on_the_links_without_reads_socket_links_is_caught():
    with pytest.raises(AssertionError, match="reads.socket_links"):
        check_action(NeedsALink(), LINKED, DATA)


def test_an_action_that_depends_on_the_colours_without_reads_socket_colours_is_caught():
    with pytest.raises(AssertionError, match="reads.socket_colours"):
        check_action(ColourBlindJeweller(), socketed(sockets_of(R, G), mods=(LIFE_1,)), DATA)


def test_a_mod_action_that_changes_the_sockets_without_declaring_it_is_caught():
    with pytest.raises(AssertionError, match="adds.socket_count"):
        check_action(SocketThief(), socketed(sockets_of(R, G, B), mods=(RESIST_2,)), DATA)


def test_an_action_that_declares_nothing_passes_on_socketed_items():
    assert check_action(Undeclared(), MIXED, DATA)


def test_a_carried_over_part_is_not_read():
    # the Jeweller's Orb keeps colours and links of the sockets that stay and declares it reads neither: the suite takes them off and compares
    assert check_action(JewellersOrb(), LINKED, DATA)
    assert check_action(BenchSocketCount(2), LINKED, DATA)
    assert not JewellersOrb().reads(DATA).socket_links and not JewellersOrb().reads(DATA).socket_colours


def test_no_other_kind_changes_sockets():
    """Every kind but the four socket kinds, on socketed rare, magic and normal items of an amulet-like base: no result differs in a socket.

    The fixture amulet takes no sockets, so the checks of the contract suite had nothing to hold on; the base here is a body armour that
    spawns the mods of the contract pool (the amulet's tags), so the mod kinds draw on it. A kind the item refuses is skipped, as everywhere.
    """
    amulet = CONTRACT_DATA.base_items[AMULET]
    clone = dataclasses.replace(amulet, id="Metadata/Items/Armours/BodyArmours/ContractSocketBody", name="Contract Socket Body", item_class="Body Armour")
    data = dataclasses.replace(CONTRACT_DATA, base_items={**CONTRACT_DATA.base_items, clone.id: clone})
    from contract_support import _roll

    def build(rarity, *mod_ids):
        from crafting_system.items import Item

        return Item.build(data, base_id=clone.id, item_level=84, rarity=rarity, mods=tuple(_roll(mod_id) for mod_id in mod_ids), sockets=sockets_of(R, G, B, links=(2, 1)))

    held = [build(Rarity.NORMAL), build(Rarity.MAGIC, LIFE_1), build(Rarity.RARE, RESIST_2, LIFE_1)]
    checked = set()
    for item in held:
        for entry in kinds():
            if entry.name in SOCKET_KINDS:
                continue
            for action in list(entry.members(data, item))[:3]:
                try:
                    outcomes = action.outcomes_under(data, item)
                except (NotApplicableError, OutOfScopeError):
                    continue
                reads, adds = action.reads(data), action.adds(data, item)
                check_socket_declarations(action, reads, adds, finished(outcomes, data), item, data)
                checked.add(entry.name)
    assert len(checked) >= 15 and {"chaos-orb", "scouring-orb", "bench-craft", "essence"} <= checked


# --- the Jeweller's Orb -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_jewellers_orb_rolls_a_different_count_by_the_wiki_table_renormalised(count):
    found = counts(jeweller(socketed(white(count))))
    assert found == jeweller_chances(PLAN_WEIGHTS, count, 6)
    assert count not in found and sum(found.values()) == 1


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_second_reading_is_the_2014_table(count):
    found = counts(jeweller(socketed(white(count)), reading=SECOND))
    assert found == jeweller_chances(SECOND_WEIGHTS, count, 6)


def test_the_plan_reading_is_the_default_and_the_axis_lists_two_readings():
    item = socketed(white(2))
    plain = jeweller(item).by_sockets
    assert plain == jeweller(item, reading=Reading()).by_sockets == jeweller(item, reading=Reading.of({"jeweller_table": "wiki_developer_table"})).by_sockets
    assert JewellersOrb().outcomes(DATA, item).by_sockets == plain
    assert JewellersOrb().rule_axes(DATA) == (JEWELLER_TABLE,) and JewellersOrb(omen=True).rule_axes(DATA) == ()
    assert [dict(reading.values) for reading in model_readings(DATA, [JewellersOrb()])] == [
        {"jeweller_table": "wiki_developer_table"},
        {"jeweller_table": "chris_wilson_2014"},
    ]
    assert jeweller(item, reading=SECOND).by_sockets != plain


def test_the_four_socket_classes_have_their_own_table_and_both_readings_agree():
    helmet = socketed(white(2), base_id=HELMET)
    found = counts(jeweller(helmet))
    assert found == jeweller_chances(FOUR_SOCKET_WEIGHTS, 2, 4) and max(found) == 4
    assert counts(jeweller(helmet, reading=SECOND)) == found
    assert jeweller_weights(4) == FOUR_SOCKET_WEIGHTS and jeweller_weights(4, SECOND) == FOUR_SOCKET_WEIGHTS


def test_the_three_socket_classes_use_the_first_three_weights_of_the_six_socket_table():
    sword = socketed(white(1), base_id=SWORD)
    assert counts(jeweller(sword)) == jeweller_chances(PLAN_WEIGHTS, 1, 3)
    assert counts(jeweller(sword, reading=SECOND)) == jeweller_chances(SECOND_WEIGHTS, 1, 3)
    assert jeweller_weights(3) == PLAN_WEIGHTS[:3] and jeweller_weights(3, SECOND) == SECOND_WEIGHTS[:3]


@pytest.mark.parametrize("level,gate", [(1, 2), (2, 3), (24, 3), (25, 4), (34, 4), (35, 5), (49, 5), (50, 6), (84, 6), (100, 6)])
def test_the_item_level_gate(level, gate):
    assert item_level_gate(level) == gate
    found = counts(jeweller(socketed(white(1), item_level=level)))
    assert max(found) == gate and set(found) == set(range(2, gate + 1))
    assert all(GATE[count] <= level for count in found)


def test_the_gate_cuts_the_table_before_it_is_renormalised():
    found = counts(jeweller(socketed(white(1), item_level=30)))  # 2, 3 or 4 sockets: weights 120, 100, 30
    assert found == {2: Fraction(120, 250), 3: Fraction(100, 250), 4: Fraction(30, 250)}


def test_the_orb_is_not_used_at_the_maximum():
    with pytest.raises(NotApplicableError, match="most a Jeweller's Orb can give"):
        jeweller(socketed(white(6)))
    with pytest.raises(NotApplicableError, match="class maximum 3"):
        jeweller(socketed(white(3), base_id=SWORD))
    with pytest.raises(NotApplicableError, match="item level 30"):
        jeweller(socketed(white(4), item_level=30))  # the gate at item level 30 is 4
    assert counts(jeweller(socketed(white(5), item_level=30))) == jeweller_chances(PLAN_WEIGHTS, 5, 4)  # bench sockets above the gate roll down


def test_added_sockets_are_white_and_unlinked_and_the_old_ones_keep_their_colours_and_links():
    item = socketed(sockets_of(R, G, B, links=(2, 1)))
    assert resized_sockets(item.sockets, 5) == sockets_of(R, G, B, W, W, links=(2, 1, 1, 1))
    results = jeweller(item).by_sockets
    assert sockets_of(R, G, B, W, W, links=(2, 1, 1, 1)) in results and sockets_of(R, G, B, W, W, W, links=(2, 1, 1, 1, 1)) in results


def test_a_lower_count_removes_the_last_sockets_and_cuts_the_link_group():
    sockets = Sockets((R, G, B, B, W, R), (3, 2, 1))
    assert resized_sockets(sockets, 4) == Sockets((R, G, B, B), (3, 1))
    assert resized_sockets(sockets, 3) == Sockets((R, G, B), (3,))
    assert resized_sockets(sockets, 2) == Sockets((R, G), (2,))
    assert resized_sockets(sockets, 1) == Sockets((R,), (1,))
    assert resized_sockets(sockets, 6) == sockets
    assert resized_sockets(Sockets((R, G, B, B), (2, 2)), 3) == Sockets((R, G, B), (2, 1))
    results = jeweller(socketed(Sockets((R, G, B, B, W), (3, 2)))).by_sockets
    assert Sockets((R, G, B), (3,)) in results and Sockets((R,), (1,)) in results


def test_a_jewellers_orb_changes_the_sockets_and_nothing_else():
    item = socketed(sockets_of(R, G, B), mods=(RESIST_2, LIFE_1))
    for _, result in jeweller(item).results:
        assert dataclasses.replace(result, sockets=item.sockets) == item


def test_the_omen_of_the_jeweller_rolls_the_maximum_of_class_and_item_level():
    assert jeweller(socketed(white(1)), omen=True).by_sockets == {white(6): 1}
    assert jeweller(socketed(sockets_of(R, G, links=(2,))), omen=True).by_sockets == {Sockets((R, G, W, W, W, W), (2, 1, 1, 1, 1)): 1}
    assert counts(jeweller(socketed(white(1), item_level=30), omen=True)) == {4: 1}  # the gate
    assert counts(jeweller(socketed(white(1), base_id=SWORD), omen=True)) == {3: 1}  # the class
    assert counts(jeweller(socketed(white(2), base_id=HELMET), omen=True)) == {4: 1}
    with pytest.raises(NotApplicableError):
        jeweller(socketed(white(6)), omen=True)


def test_the_jewellers_orb_is_priced_by_the_game_names_of_the_orb_and_the_omen():
    assert dict(JewellersOrb().resources(DATA)) == {"Jeweller's Orb": 1}
    assert dict(JewellersOrb(omen=True).resources(DATA)) == {"Jeweller's Orb": 1, "Omen of the Jeweller": 1}
    assert JewellersOrb().label(DATA) == "Jeweller's Orb" and JewellersOrb(omen=True).label(DATA) == "Jeweller's Orb with Omen of the Jeweller"


def bench_data_with_abyss():
    return dataclasses.replace(bench_data(), mods=abyss_data().mods)


def test_the_jewellers_orb_refusals():
    with pytest.raises(NotApplicableError, match="corrupted"):
        jeweller(socketed(white(2), corrupted=True))
    with pytest.raises(NotApplicableError, match="takes no sockets"):
        JewellersOrb().outcomes(CONTRACT_DATA, fixture_items()["rare_junk"])
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        jeweller(socketed(None))
    abyss = abyss_data()
    with_abyss = Item.build(abyss, base_id=BODY, item_level=84, rarity=Rarity.RARE, mods=(ExplicitMod(ABYSS_MOD, 1, (1,)),), sockets=white(2))
    for action in (JewellersOrb(), JewellersOrb(omen=True), OrbOfFusing(), BenchSocketCount(5), BenchSocketLinks(2)):
        with pytest.raises(OutOfScopeError, match="Abyssal"):
            action.outcomes(bench_data_with_abyss(), with_abyss)


def _expected_orbs(reading, wanted, reach=6, level=84):
    """Orbs to reach `wanted` sockets or more from each count, by value iteration over the kernel: the action's own chance of each new count."""
    chances = {c: counts(jeweller(socketed(white(c), item_level=level), reading=reading)) for c in range(1, reach)}
    value = {c: 0.0 for c in range(1, reach + 1)}
    for _ in range(100_000):
        new = {c: 0.0 if c >= wanted else 1.0 + sum(float(p) * value[n] for n, p in chances[c].items()) for c in range(1, reach + 1)}
        if max(abs(new[c] - value[c]) for c in value) < 1e-12:
            return new
        value = new
    raise AssertionError("value iteration did not converge")


def test_expected_jewellers_orbs_by_value_iteration_over_the_kernel():
    """Item level 84, a body armour: 214.9 / 222.6 orbs to six sockets, 35.7 / 36.9 to five or more (plan / second reading).

    The figures of the design are one number for "any count", and the counts differ by a fraction of an orb (under 0.4, under 4% between the readings):
    plan to six 214.91 from one socket, 214.68 from two, 214.74, 214.97, 215.05 from five; second reading 222.58, 222.62, 222.65, 222.81, 222.90;
    to five or more plan 35.69, 35.47, 35.53, 35.76 and second 36.84, 36.87, 36.90, 37.07 from one to four. The figures are reached from one socket
    (214.9, 222.6, 35.7) and, for the last, from three (36.9); every other start lies within 0.4.
    """
    plan6, second6 = _expected_orbs(None, 6), _expected_orbs(SECOND, 6)
    plan5, second5 = _expected_orbs(None, 5), _expected_orbs(SECOND, 5)
    assert round(plan6[1], 1) == 214.9 and round(second6[1], 1) == 222.6
    assert round(plan5[1], 1) == 35.7 and round(second5[3], 1) == 36.9
    for found, low, high in ((plan6, 214.6, 215.1), (second6, 222.5, 222.9), (plan5, 35.4, 35.8)):
        assert all(low <= found[c] <= high for c in range(1, 6 if found is plan6 or found is second6 else 5)), found
    assert all(36.8 <= second5[c] <= 37.1 for c in range(1, 5))
    assert 0.03 < second6[1] / plan6[1] - 1 < 0.04  # under 4% apart
    # the same numbers from a restatement of the weights that does not go through the action
    assert plan6[1] == pytest.approx(expected_jeweller_orbs(PLAN_WEIGHTS, 1, 6, 6), abs=1e-6)
    assert second6[2] == pytest.approx(expected_jeweller_orbs(SECOND_WEIGHTS, 2, 6, 6), abs=1e-6)
    assert plan5[1] == pytest.approx(expected_jeweller_orbs(PLAN_WEIGHTS, 1, 5, 6), abs=1e-6)


# --- the Orb of Fusing ------------------------------------------------------------------------------------------------------------------


def fusing(item, *, omen=False):
    return OrbOfFusing(omen=omen).outcomes(DATA, item)


def compositions(count: int):
    """Every tuple of group sizes that adds up to `count`."""
    if count == 0:
        yield ()
        return
    for first in range(1, count + 1):
        for rest in compositions(count - first):
            yield (first, *rest)


def composition_chance(sizes: tuple[int, ...]) -> Fraction:
    """The chance of a composition by the sequential rule, written out here: each size from the weights cut to the sockets left."""
    left, chance = sum(sizes), Fraction(1)
    for size in sizes:
        chance *= Fraction(FUSING_WEIGHTS[size - 1], sum(FUSING_WEIGHTS[:left]))
        left -= size
    return chance


@pytest.mark.parametrize("count,percent", [(2, 66.1), (3, 33.7), (4, 19.9), (5, 0.83), (6, 0.10)])
def test_fusing_all_linked(count, percent):
    found = fusing(socketed(white(count)))
    assert found.chance_all_linked() == Fraction(FUSING_WEIGHTS[count - 1], sum(FUSING_WEIGHTS[:count]))
    assert float(found.chance_all_linked()) * 100 == pytest.approx(percent, abs=0.05 if count < 5 else 0.005)


def test_the_six_link_is_one_in_a_thousand():
    assert fusing(socketed(white(6))).chance_all_linked() == Fraction(1, 1000)


@pytest.mark.parametrize("count", [2, 3, 4, 5, 6])
def test_every_fusing_result_is_a_composition_with_the_sequential_chance(count):
    found = {sockets.links: chance for sockets, chance in fusing(socketed(white(count))).by_sockets.items()}
    assert set(found) == set(compositions(count)) and sum(found.values()) == 1
    assert found == {sizes: composition_chance(sizes) for sizes in compositions(count)}
    assert fusing_links(count) == found


def test_chance_all_equals_exhaustive_enumeration_on_four_sockets():
    item = socketed(sockets_of(R, G, B, W), mods=(RESIST_2, LIFE_1))
    found = fusing(item)
    every = list(compositions(4))
    assert len(every) == 8
    assert found.chance_all_linked() == sum(composition_chance(sizes) for sizes in every if len(sizes) == 1)
    assert dict(found.by_sockets) == {Sockets(item.sockets.colours, sizes): composition_chance(sizes) for sizes in every}
    # the contract's chance_all (the chance the finished item holds all of these mods): the mods are never touched
    for mod_ids in ([LIFE_1], [RESIST_2], [LIFE_1, RESIST_2], []):
        assert found.chance_all(mod_ids) == sum((chance for chance, result in found.results if {e.mod_id for e in result.mods} >= set(mod_ids)), Fraction(0)) == 1
    assert found.chance_all(["Strength1"] if "Strength1" in DATA.mods else [list(DATA.mods)[0]]) in (0, 1)
    assert found.chance_count(4) == 1 and found.chance_count(3) == 0


def test_fusing_links_from_the_first_socket_and_keeps_the_count_and_the_colours():
    item = socketed(sockets_of(R, G, B, W, G, B, links=(2, 2, 1, 1)))
    for _, result in fusing(item).results:
        assert result.sockets.colours == item.sockets.colours and result.sockets.count == 6
        assert dataclasses.replace(result, sockets=item.sockets) == item
    assert item.sockets in fusing(item).by_sockets or Sockets(item.sockets.colours, (2, 2, 1, 1)) in fusing(item).by_sockets  # it may leave them as they were


def test_the_links_the_item_holds_do_not_change_the_odds():
    one = counts_by_links(fusing(socketed(white(4))))
    other = counts_by_links(fusing(socketed(white(4, (2, 1, 1)))))
    assert one == other


def counts_by_links(outcomes):
    return {sockets.links: chance for sockets, chance in outcomes.by_sockets.items()}


def test_the_omen_of_connections_links_every_socket():
    item = socketed(sockets_of(R, G, B, W, links=(2, 1, 1)))
    assert fusing(item, omen=True).by_sockets == {Sockets(item.sockets.colours, (4,)): 1}
    assert fusing(item, omen=True).chance_all_linked() == 1
    assert dict(OrbOfFusing(omen=True).resources(DATA)) == {"Orb of Fusing": 1, "Omen of Connections": 1}
    assert dict(OrbOfFusing().resources(DATA)) == {"Orb of Fusing": 1}
    assert OrbOfFusing(omen=True).label(DATA) == "Orb of Fusing with Omen of Connections"


@pytest.mark.parametrize("quality", [20, 25, 30])
def test_from_20_percent_quality_the_20_percent_table_is_used(quality):
    assert fusing(socketed(white(4), quality=quality)).by_sockets == fusing(socketed(white(4), quality=20)).by_sockets


@pytest.mark.parametrize("quality", [0, 1, 19])
def test_below_20_percent_quality_there_is_no_table(quality):
    with pytest.raises(OutOfScopeError, match="20% quality"):
        fusing(socketed(white(4), quality=quality))


def test_the_orb_of_fusing_refusals():
    with pytest.raises(NotApplicableError, match="one socket"):
        fusing(socketed(white(1)))
    with pytest.raises(NotApplicableError, match="all linked"):
        fusing(socketed(white(3, (3,))))
    with pytest.raises(NotApplicableError, match="corrupted"):
        fusing(socketed(white(3), corrupted=True))
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        fusing(socketed(None))
    with pytest.raises(NotApplicableError, match="takes no sockets"):
        OrbOfFusing().outcomes(CONTRACT_DATA, fixture_items()["rare_junk"])
    assert fusing(socketed(white(2))).chance_all_linked() > 0  # two unlinked: allowed


# --- the bench count and link crafts ----------------------------------------------------------------------------------------------------


BENCH = bench_data()


@pytest.mark.parametrize("count,price", [(2, 1), (3, 3), (4, 10), (5, 70), (6, 350)])
def test_a_bench_count_craft_costs_its_jewellers_orbs(count, price):
    assert dict(BenchSocketCount(count).resources(BENCH)) == {"Jeweller's Orb": price}
    assert BenchSocketCount(count).cost(BENCH)[0].count == price


@pytest.mark.parametrize("links,price", [(2, 1), (3, 3), (4, 5), (5, 150), (6, 1500)])
def test_a_bench_link_craft_costs_its_orbs_of_fusing(links, price):
    assert dict(BenchSocketLinks(links).resources(BENCH)) == {"Orb of Fusing": price}


def test_a_bench_count_craft_sets_the_count_exactly_and_keeps_what_stays():
    item = socketed(sockets_of(R, G, B, links=(2, 1)))
    up = BenchSocketCount(5).outcomes(BENCH, item)
    assert up.by_sockets == {sockets_of(R, G, B, W, W, links=(2, 1, 1, 1)): 1}
    down = BenchSocketCount(2).outcomes(BENCH, item)
    assert down.by_sockets == {Sockets((R, G), (2,)): 1}
    low = socketed(white(1), item_level=1)
    assert BenchSocketCount(6).outcomes(BENCH, low).by_sockets == {white(6): 1}  # the bench ignores the item-level gate
    for result in (up, down):
        for _, found in result.results:
            assert dataclasses.replace(found, sockets=item.sockets) == item


def test_a_bench_count_craft_respects_the_class_and_refuses_what_changes_nothing():
    with pytest.raises(NotApplicableError, match="at most 3"):
        BenchSocketCount(4).outcomes(BENCH, socketed(white(2), base_id=SWORD))
    with pytest.raises(NotApplicableError, match="at most 4"):
        BenchSocketCount(5).outcomes(BENCH, socketed(white(2), base_id=HELMET))
    assert BenchSocketCount(4).outcomes(BENCH, socketed(white(2), base_id=HELMET)).by_sockets == {white(4): 1}
    with pytest.raises(NotApplicableError, match="already has 3 sockets"):
        BenchSocketCount(3).outcomes(BENCH, socketed(white(3)))
    with pytest.raises(NotApplicableError, match="corrupted"):
        BenchSocketCount(3).outcomes(BENCH, socketed(white(2), corrupted=True))
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        BenchSocketCount(3).outcomes(BENCH, socketed(None))
    with pytest.raises(ValueError, match="no option"):
        BenchSocketCount(7).outcomes(BENCH, socketed(white(2)))


def test_a_bench_craft_is_refused_for_a_class_its_option_is_not_offered_for():
    option = next(o for o in BENCH.bench_options if o.actions.change_socket_count == 3)
    narrowed = tuple(dataclasses.replace(o, item_classes=("Boots",)) if o is option else o for o in BENCH.bench_options)
    data = dataclasses.replace(BENCH, bench_options=narrowed)
    with pytest.raises(NotApplicableError, match="does not offer 3 sockets for the item class Body Armour"):
        BenchSocketCount(3).outcomes(data, socketed(white(2)))
    assert BenchSocketCount(3) not in catalog(data, socketed(white(2)))


def test_a_bench_link_craft_links_the_first_sockets_and_leaves_the_rest():
    item = socketed(sockets_of(R, G, B, W, G, links=(1, 1, 1, 1, 1)))
    assert BenchSocketLinks(3).outcomes(BENCH, item).by_sockets == {Sockets(item.sockets.colours, (3, 1, 1)): 1}
    assert BenchSocketLinks(5).outcomes(BENCH, item).by_sockets == {Sockets(item.sockets.colours, (5,)): 1}
    relinked = socketed(sockets_of(R, G, B, W, G, links=(4, 1)))
    assert BenchSocketLinks(2).outcomes(BENCH, relinked).by_sockets == {Sockets(relinked.sockets.colours, (2, 1, 1, 1)): 1}
    for _, found in BenchSocketLinks(3).outcomes(BENCH, item).results:
        assert dataclasses.replace(found, sockets=item.sockets) == item


def test_a_bench_link_craft_refusals():
    with pytest.raises(NotApplicableError, match="has 3 sockets"):
        BenchSocketLinks(4).outcomes(BENCH, socketed(white(3)))
    with pytest.raises(NotApplicableError, match="already one group"):
        BenchSocketLinks(2).outcomes(BENCH, socketed(white(3, (2, 1))))
    with pytest.raises(NotApplicableError, match="corrupted"):
        BenchSocketLinks(2).outcomes(BENCH, socketed(white(3), corrupted=True))
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        BenchSocketLinks(2).outcomes(BENCH, socketed(None))


@pytest.mark.parametrize("name", ["sockets_body_three", "sockets_bow_five", "sockets_body_low_level"])
def test_the_bench_crafts_pass_the_contract_suite_at_every_count(name):
    extra = EXTRA[name]
    for count in range(2, 7):
        check_action(BenchSocketCount(count), extra.item, BENCH)
    for links in range(2, 7):
        check_action(BenchSocketLinks(links), extra.item, BENCH)


# --- Memory Strands and claims ----------------------------------------------------------------------------------------------------------


def test_every_socket_action_declares_it_neither_cuts_nor_spends_and_works_on_a_stranded_item():
    stranded = EXTRA["sockets_body_linked_stranded"].item
    assert stranded.memory_strands == 45
    for action in DECLARED:
        use = action.strand_use(DATA)
        assert use is not None and not use.cuts and use.spend is None and use.claims
        assert action.strand_claims(DATA) == use.claims
    result = JewellersOrb().outcomes(DATA, stranded)
    assert all(found.memory_strands == 45 for _, found in result.results)


def test_the_claims_of_each_action_are_its_own_and_include_the_marked_ones():
    plan = JewellersOrb().claims(DATA)
    assert {"sockets.socket_count_weights", "sockets.jeweller_second_reading_2014_table", "sockets.jeweller_ignores_quality"} <= plan
    omen = JewellersOrb(omen=True).claims(DATA)
    assert "sockets.omen_of_the_jeweller_max_sockets" in omen and "sockets.socket_count_weights" not in omen
    assert "sockets.fusing_group_size_weights" in OrbOfFusing().claims(DATA)
    assert "sockets.omen_of_connections_all_linked" in OrbOfFusing(omen=True).claims(DATA)
    assert {"sockets.bench_socket_count_cost", "sockets.jeweller_removes_sockets_from_the_end"} <= BenchSocketCount(2).claims(DATA)
    assert {"sockets.bench_link_cost", "sockets.bench_link_makes_the_first_sockets_one_group"} <= BenchSocketLinks(2).claims(DATA)
