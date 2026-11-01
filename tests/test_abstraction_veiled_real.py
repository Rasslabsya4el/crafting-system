"""The veils and the unveil offer in the compressed state on the real 3.29.3.3 dump, R24's boots (ticket #145, ADR-0026).

These skip cleanly when the dump is not cached (CI has it). The route R24 (reference routes, 3.29 Mana-fractured Avoid Shock / Suppression boots)
fractures a Mana prefix, keeps an Avoid Shock essence suffix, a Spell Suppression suffix and a resistance, locks the suffixes with the bench and
rolls the open prefixes with Veiled Chaos Orbs until Movement Speed + Onslaught is on offer. The boots here are Wrapped Boots (a Dex-Int base, which
Mana, Spell Suppression and the resistances can roll on) at item level 86; the model is the five veiled actions (the lock is the bench craft, kept
out of the model: a state with the lock is the start of the loop).

* layer 1 (ADR-0019) on those boots: for every concrete item that the unveil, the picks, the Veiled Exalted Orb and the Annulment reach from four starts,
  the kernel of its state equals the finished items of the action, compressed one by one and added up exactly;
* the Veiled Chaos Orb on the real pool: every outcome holds one placeholder, the fractured Mana and the locked suffixes stay, and the side of the
  veil is a fair choice between the sides that have room;
* the offer states of R24: how many concrete offers the unveil of its loop state has, how many offer states they make, the states of the loop.
"""

from collections import defaultdict
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from abstraction_veiled_support import closure, concrete_pushforward, veiled_chaos_finished

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ActionError, AnnulmentOrb, BenchCraft, NotApplicableError, Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table, veiled_placeholder

BOOTS = "Metadata/Items/Armours/Boots/BootsDexInt1"  # Wrapped Boots
LEVEL = 86  # Spell Suppression tier 1 needs item level 85
MANA = "IncreasedMana12"  # tier 1
SHOCK = "ChanceToAvoidShockEssence7"
SUPPRESSION = "ChanceToSuppressSpells5__"  # tier 1
FIRE = "FireResist7"  # tier 2
COLD = "ColdResist8"  # tier 1
LOCK = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix that locks the suffixes
MOVEMENT = "MovementVelocity1"  # the ordinary Movement Speed prefix
MS_ONSLAUGHT = "JunMasterVeiledMovementVelocityAndOnslaughtOnKill"
LIFE_REGEN = "JunMasterVeiledBaseLifeAndManaRegen_"
OFFERS = (Pick(1), Pick(2), Pick(3))


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def tiers(data):
    return tier_table(data, BOOTS)


class R24:
    """The pieces of R24's model on the real boots: items, goal and the abstraction."""

    def __init__(self, data, tiers):
        self.data, self.tiers = data, tiers
        mods = data.mods
        self.goal = Goal(
            (
                Wanted(frozenset(m.id for m in mods.values() if m.families == ("IncreasedMana",) and m.domain == "item")),
                Wanted(frozenset({MS_ONSLAUGHT})),
                Wanted(frozenset(m.id for m in mods.values() if m.families == ("ReducedShockChance",))),
                Wanted(frozenset(m.id for m in mods.values() if m.families == ("ChanceToSuppressSpells",) and m.domain == "item"), min_tier=1),
                Wanted(
                    frozenset(
                        m.id for m in mods.values() if m.domain == "item" and m.families in (("FireResistance",), ("ColdResistance",), ("LightningResistance",))
                    ),
                    min_tier=2,
                ),
            )
        )
        self.actions = [VeiledChaosOrb(), Unveil(), *OFFERS]
        self.ability = Abstraction(data, self.goal, BOOTS, LEVEL, self.actions, metamods=True)

    def roll(self, mod_id: str, **flags) -> ExplicitMod:
        mod = self.data.mods[mod_id]
        return ExplicitMod(mod_id, self.tiers.get(mod_id, 1), tuple(min(s.min, s.max) for s in mod.stats), **flags)

    def boots(self, *mods: ExplicitMod, **fields) -> Item:
        return Item.build(self.data, base_id=BOOTS, item_level=LEVEL, rarity=Rarity.RARE, mods=mods, **fields)

    def veil(self, side: str = "prefix") -> ExplicitMod:
        return veiled_placeholder(self.data, "VeiledPrefix" if side == "prefix" else "VeiledSuffix")

    def locked(self, *extra: ExplicitMod) -> tuple[ExplicitMod, ...]:
        """The fractured Mana and the three suffixes of the route, the lock on top."""
        return (self.roll(MANA, fractured=True), self.roll(SHOCK), self.roll(SUPPRESSION), self.roll(FIRE), *extra)

    def start(self) -> Item:
        return self.boots(*self.locked(self.roll(LOCK, crafted=True)))

    def loop(self) -> Item:
        """The state the Veiled Chaos Orb leaves behind: the route's mods and a prefix placeholder (the lock is gone with the reroll)."""
        return self.boots(*self.locked(self.veil()))


@pytest.fixture(scope="module")
def r24(data, tiers):
    return R24(data, tiers)


def test_layer_1_on_real_boots_for_the_unveil_the_picks_the_veiled_exalted_orb_and_the_annulment(r24):
    cheap = [VeiledExaltedOrb(), Unveil(), *OFFERS, AnnulmentOrb()]
    ability = Abstraction(r24.data, r24.goal, BOOTS, LEVEL, cheap, metamods=True)
    starts = [
        r24.loop(),
        r24.start(),
        r24.boots(r24.roll(MANA, fractured=True), r24.roll(MOVEMENT), r24.veil("suffix")),  # the ordinary Movement Speed blocks the family of the unveiled ones
        r24.boots(r24.roll(MS_ONSLAUGHT), r24.roll(FIRE), r24.roll(COLD)),  # a mod unveiled from the pool: no Veiled Exalted Orb
        r24.boots(r24.veil(), r24.roll(COLD), veil_offer=(MS_ONSLAUGHT, LIFE_REGEN)),  # an offer drawn: only a pick leaves it
    ]
    items = closure(r24.data, starts, cheap, limit=260)
    assert len(items) >= 200
    applied = {action: 0 for action in cheap}
    for item in items:
        state = ability.compress(item)
        for action in cheap:
            if item.veil_offer and not action.reads(r24.data).offer:
                with pytest.raises(NotApplicableError, match="choice node"):
                    ability.kernel(state, action)
                continue
            try:
                expected = concrete_pushforward(ability, r24.data, item, action)
            except ActionError as refusal:
                with pytest.raises(type(refusal)):
                    ability.kernel(state, action)
                continue
            assert dict(ability.kernel(state, action)) == expected, (action.label(), [e.mod_id for e in item.mods], item.veil_offer)
            applied[action] += 1
    assert all(applied.values()), applied


def test_layer_1_of_the_veiled_chaos_orb_on_real_boots_against_the_oracle_of_the_metamods(r24):
    ability = r24.ability
    starts = {
        "r24_start": r24.start(),  # the three suffixes locked: the veil is a prefix and at most one more mod is drawn
        "a_veil_on_the_open_side": r24.boots(*r24.locked(r24.roll(LOCK, crafted=True), r24.veil())),  # the veil and the lock are rerolled away with the open prefixes
        "a_second_fracture": r24.boots(r24.roll(MANA, fractured=True), r24.roll(SHOCK, fractured=True), r24.roll(SUPPRESSION), r24.roll(COLD), r24.roll(LOCK, crafted=True)),
    }
    for name, item in starts.items():
        expected: dict = defaultdict(Fraction)
        for result, chance in veiled_chaos_finished(r24.data, item):
            expected[ability.compress(result)] += chance
        kernel = ability.kernel(ability.compress(item), VeiledChaosOrb())
        assert dict(kernel) == dict(expected), name
        assert len(kernel) > 1 and sum(kernel.values()) == 1


def test_the_veiled_chaos_orb_on_the_real_pool_keeps_the_fractured_mana_and_the_locked_suffixes_and_puts_one_veil(r24):
    ability, start = r24.ability, r24.ability.compress(r24.start())
    kernel = ability.kernel(start, VeiledChaosOrb())
    assert sum(kernel.values()) == 1 and len(kernel) > 1
    for state, chance in kernel.items():
        assert len(state.fractured) == 1 and state.fractured[0].mod_id.startswith("IncreasedMana")
        kinds = [slot.kind for slot in state.slots]
        assert sum(kind in ("VeiledPrefix", "VeiledSuffix") for kind in kinds) == 1
        assert sum(slot.side.value == "suffix" for slot in state.slots) == 3  # the locked suffixes stay and fill the side: the veil is a prefix
        assert state.offer == ()
    assert {slot.kind for state in kernel for slot in state.slots if slot.kind.startswith("Veiled")} == {"VeiledPrefix"}
    # the lock is a prefix and goes with the reroll; the route has to craft it again before the next veil
    assert all(not slot.crafted for state in kernel for slot in state.slots)


def test_the_unveil_of_the_loop_state_makes_a_dozen_offer_states_out_of_the_concrete_offers(r24):
    ability, loop = r24.ability, r24.ability.compress(r24.loop())
    offers = ability.kernel(loop, Unveil())
    concrete = {frozenset(result.veil_offer): chance for chance, result in Unveil().outcomes(r24.data, r24.loop()).results}
    # the concrete offers add up to 1 as the offer states do; the goal tells apart only the wanted mod, so several offers are one state
    assert sum(concrete.values()) == 1 == sum(offers.values())
    wanted = sum(chance for offer, chance in concrete.items() if MS_ONSLAUGHT in offer)
    assert wanted == sum(chance for state, chance in offers.items() if any(entry.mod_id == MS_ONSLAUGHT for entry in state.offer))
    assert 0 < wanted < 1 and len(offers) < len(concrete)
    print(f"R24 loop state: {len(concrete)} concrete offers, {len(offers)} offer states, the wanted mod on offer with chance {float(wanted):.4f}")


def loop_graph(r24):
    """R24's loop as a graph: the Veiled Chaos Orb only from a state that holds the lock (the route crafts it before every veil), the rest as it comes.

    The full model also lets the veil roll a state that has no lock, which rerolls the whole item with the metamods modelled: that graph is
    thousands of states (a pilot count of 40 seconds had passed 9,873 states and 4.2 million transitions without finishing), and the planner
    prunes it (ticket #146); this loop is the part of it that the route lives in.
    """
    actions = [*r24.actions, BenchCraft(LOCK)]
    ability = Abstraction(r24.data, r24.goal, BOOTS, LEVEL, actions, metamods=True)
    start = ability.compress(r24.start())
    seen, queue, edges = {start}, [start], 0
    while queue:
        state = queue.pop()
        if ability.is_goal(state):
            continue
        for action in actions:
            if isinstance(action, VeiledChaosOrb) and not any(slot.crafted and slot.kind == LOCK for slot in state.slots):
                continue
            try:
                kernel = ability.kernel(state, action)
            except ActionError:
                continue
            edges += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return ability, seen, edges


def test_the_offer_states_of_the_r24_loop_are_counted(r24):
    ability, seen, edges = loop_graph(r24)
    offers = [state for state in seen if state.offer]
    placeholders = [state for state in seen if not state.offer and any(slot.kind.startswith("Veiled") for slot in state.slots)]
    counts = {
        "states": len(seen),
        "edges": edges,
        "offer states": len(offers),
        "distinct offers": len({state.offer for state in offers}),
        "placeholder states without an offer": len(placeholders),
        "goal states": sum(ability.is_goal(state) for state in seen),
    }
    print(f"R24 loop: {counts}")
    assert counts == {
        "states": 98,
        "edges": 241,
        "offer states": 47,
        "distinct offers": 7,
        "placeholder states without an offer": 9,
        "goal states": 8,
    }
    # every goal state holds the wanted mod, unveiled from an offer
    assert all(any(slot.kind == "^MovementVelocity" for slot in state.slots) for state in seen if ability.is_goal(state))
    # an offer state has the picks of the mods it shows and no other action
    for state in offers:
        assert all(ability.kernel(state, pick) for pick in OFFERS[: len(state.offer)])
        for refused in (VeiledChaosOrb(), BenchCraft(LOCK), Unveil()):
            with pytest.raises(NotApplicableError):
                ability.kernel(state, refused)
