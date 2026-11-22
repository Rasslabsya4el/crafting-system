"""Scheme S, the steps of the planner's widening (#1276, research note 2026-11-18-rounds-design, section 5; #1389).

The offers are split once into a seed and families fixed by what their actions declare to the model; each step is the offers accepted so far
plus one family, accepted only when its bound's build completes; a family that cannot beat the plan in hand is set aside, and one second pass
tries the families set aside or undone again, with nothing set aside in it. Every figure here is hand-worked; no test reads the clock."""

from types import SimpleNamespace

import pytest

from crafting_system.planner import _plan as planner_plan
from crafting_system.planner import _rounds
from crafting_system.planner._envelope import Beaten, Incomplete


def _offer(label: str, kind: str):
    return SimpleNamespace(label=label, kind=kind, blocks=None)


def _plan(cost: float):
    return SimpleNamespace(search=SimpleNamespace(lower=cost, touched=3), mean_remaining=cost)


def _widen(groups, offers, run, complete=lambda plan: True, meter=None):
    return _rounds.widen(
        groups, offers, run, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: None, clock_now=lambda: 0.0, complete=complete, meter=meter,
    )  # fmt: skip


def test_the_steps_are_the_seed_then_the_families_by_what_their_offers_add_the_same_for_every_target():
    offers = [
        _offer("Alteration", "alteration-orb"), _offer("Exalted", "exalted-orb"), _offer("Annul", "annulment-orb"), _offer("Fracture", "fracturing-orb"),
        _offer("Matron", "wild-bristle-matron"), _offer("Lock", "bench-craft"), _offer("Imprint", "imprint"), _offer("Restore", "restore"),
        _offer("Unveil", "unveil"), _offer("Veiled Exalt", "veiled-exalted-orb"), _offer("Add Remove", "harvest-add-remove"),
        _offer("Awaken", "awakener-orb"), _offer("Dominance", "orb-of-dominance"), *(_offer(f"Essence {n}", "essence") for n in range(3)),
        *(_offer(f"Fossils {n}", "fossil-set") for n in range(5)), _offer("Craft", "bench-craft"), _offer("Craft 2", "bench-craft"),
        _offer("Named", "chaos-orb"),
    ]  # fmt: skip
    adds = {
        "Exalted": {"junk", "pool weights"}, "Annul": {"junk"}, "Fracture": {"junk", "fractures", "pool weights"}, "Matron": {"junk", "metamods", "pool weights"},
        "Lock": {"junk", "metamods", "pool weights"}, "Imprint": {"junk", "imprints"}, "Restore": {"junk", "imprints"}, "Unveil": {"junk", "unveil offer", "veiled mods"},
        "Veiled Exalt": {"junk", "veiled mods"}, "Add Remove": {"junk", "draw tags", "pool weights"}, "Awaken": {_rounds.SECOND_ITEM},
        "Dominance": {"junk", "influence mods"}, "Craft": {"junk"}, "Craft 2": {"junk"},
    }  # fmt: skip
    asked = []

    def seed():
        asked.append(True)
        return (offers.index(next(o for o in offers if o.label == "Essence 1")),)

    steps = _rounds.round_groups(offers, ("Named",), lambda offer: frozenset(adds.get(offer.label, ())), seed)
    labels = [sorted(offers[i].label for i in step.positions) for step in steps]
    assert asked and labels == [
        ["Essence 1", "Named"],  # the seed: the run's named methods and the offers of least cost over chance on a wanted mod
        ["Alteration", "Exalted"],  # the single orbs that reroll, move or add by pool weight
        ["Annul"],  # the single offers that read the junk and add nothing: removals
        ["Fracture"], ["Lock", "Matron"], ["Awaken"], ["Imprint", "Restore"], ["Unveil", "Veiled Exalt"], ["Add Remove"], ["Dominance"],  # the ladder
        ["Craft", "Craft 2"], ["Essence 0", "Essence 2"], [f"Fossils {n}" for n in range(5)],  # the kinds of many offers, the fewest first
    ]
    # nothing refines the model beyond the junk count: one step of every offer, and the seed is never asked
    plain = [_offer("a", "alteration-orb"), _offer("b", "bench-craft")]
    asked.clear()
    (only,) = _rounds.round_groups(plain, (), lambda offer: frozenset({"junk"}) if offer.label == "b" else frozenset(), seed)
    assert only.positions == (0, 1) and not asked


def test_g_and_h_each_beaten_alone_are_found_together_in_the_second_pass():
    # #1389, the module text's example: a plan in hand of 10 that adds mods A and B together (the seed); family G adds A for 1, family H adds B
    # for 1, the base has no other way to either. G with the base costs 11 and H with the base costs 11, so each is beaten and set aside; the
    # second pass holds G again (with no new search: the same offers closed already) and then H with it, and the plan of 2 is found and proved
    # over every offer.
    offers = ("seed", "g", "h")
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate(offers))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if "g" in chosen and "h" in chosen:
            return _plan(2.0)
        if call.upper is not None:
            raise Beaten(10.0)  # 11 with the base, no cheaper than the plan in hand
        return _plan(10.0)

    widened = _widen(groups, offers, run)
    assert seen == [("seed",), ("seed", "g"), ("seed", "h"), ("seed", "g", "h")]
    assert widened.plan.mean_remaining == 2.0
    assert [record.status for record in widened.records] == ["closed", "beaten", "beaten", "closed"]
    assert not widened.records[1].carried and widened.records[1].reason.endswith("it joined the second pass with no new search (the same methods)")
    assert _rounds.all_closed(widened.records)  # the last step held every offer and closed: the proof covers every step
    claim = _rounds.rounds_limits(widened.records, True, None)
    assert len(claim) == 1 and "every method offered" in claim[0].guarantee


def test_a_step_whose_build_does_not_complete_is_undone_named_and_tried_once_more():
    # a plan in hand of 10; the second family's build does not complete (`Incomplete`, raised before its search): it is undone, the third step
    # does not hold it, the second pass tries it once more over what was accepted, and the answer proves the plan only over the steps that closed
    offers = ("seed", "x", "y")
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate(offers))
    seen, calls = [], []

    def run(chosen, call):
        seen.append(chosen)
        calls.append((call.searches, call.held))
        if "x" in chosen:
            raise Incomplete("the time limit of 50 seconds was reached", 4.0, 100, 30)
        if "y" in chosen:
            return _plan(7.0)
        return _plan(10.0)

    widened = _widen(groups, offers, run)
    assert seen == [("seed",), ("seed", "x"), ("seed", "y"), ("seed", "x", "y")]
    # each step's share is the time left over the steps left, this one included, and the retries the second pass owes so far
    assert calls == [(3, False), (2, True), (2, True), (1, True)]
    assert [record.status for record in widened.records] == ["closed", "undone", "closed", "undone"]
    assert "30 of 100 cases worked out" in widened.records[1].reason and widened.records[1].lower == 4.0
    assert widened.plan.mean_remaining == 7.0 and not _rounds.all_closed(widened.records)
    proved, untried = _rounds.rounds_limits(widened.records, False, None)
    assert "may cost less" in proved.guarantee and "x" in untried.labels and "y" not in untried.labels


def test_a_plan_of_a_bound_not_built_whole_is_kept_said_unproved_and_its_family_undone():
    # no plan in hand: the seed's search makes a plan on a bound whose build stopped (OR-33: the answer must hold one). It is kept, but the
    # answer claims nothing of it (OR-39), not even among its own methods; a later step on a complete bound replaces it by a cheaper one
    offers = ("seed", "x", "y")
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate(offers))
    built = {("seed",): False, ("seed", "x"): False}

    def run(chosen, call):
        cost = {("seed",): 100.0, ("seed", "x"): 50.0, ("seed", "y"): 40.0}.get(chosen, 45.0)
        return SimpleNamespace(search=SimpleNamespace(lower=0.1, touched=3), mean_remaining=cost, chosen=chosen)

    widened = _widen(groups, offers, run, complete=lambda plan: built.get(plan.chosen, True))
    # x, tried again over the seed and y, completes: its second step closes with no cheaper plan, and joins (nothing is set aside there)
    assert [record.status for record in widened.records] == ["undone", "undone", "closed", "closed"]
    assert [record.unproved for record in widened.records] == [True, True, False, False]
    assert widened.plan.chosen == ("seed", "y") and not widened.unproved  # the seed is the base whatever its end; x is not
    only_unproved = _widen(groups[:1], offers[:1], run, complete=lambda plan: False)
    assert only_unproved.unproved
    proved, _ = _rounds.rounds_limits(only_unproved.records, False, None, unproved=True)
    assert "not proved" in proved.what and "cheapest" not in proved.guarantee


def test_counted_in_states_each_step_has_its_share_of_the_states_left_and_its_first_plan_what_the_steps_have_left():
    offers = ("seed", "x", "y")
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate(offers))
    nets = []

    def run(chosen, call):
        nets.append((call.states, call.first_states, call.first_any))
        return SimpleNamespace(search=SimpleNamespace(lower=5.0, touched=30), mean_remaining=10.0 - len(chosen))  # each step finds a cheaper plan

    meter = _rounds.StatesMeter(300)
    _widen(groups, offers, run, meter=meter)
    assert nets == [(100, 300, True), (135, 270, False), (240, 240, False)] and meter.spent == 90


def test_the_answer_says_a_step_not_finished_with_its_figure():
    record = _rounds.RoundRecord(("fossil-set",), 12, _rounds.UNDONE, "its build stopped", 4.0, None, 50.0, features=("junk",), carried=False)
    line = _rounds.round_line(3, record)
    assert line.startswith("round 3 (fossil-set that add junk to the model; 12 actions offered, 50 s): not finished (its build stopped)")
    assert "no plan with them costs less than 4.00 Chaos" in line and line.endswith("the rounds after it did not hold them)")
    said = _rounds.no_plan_words([record])
    assert said is not None and "not show that no plan exists" in said


def test_an_awakener_s_orb_no_longer_keeps_a_target_out_of_the_steps(monkeypatch):
    # #1276: an Awakener's Orb is a family of its own (`SECOND_ITEM`, after the metamods); its donors are planned in its step on the step's share
    monkeypatch.setattr(planner_plan, "interval_axes", lambda data, priced: ())
    orb = SimpleNamespace(offer=SimpleNamespace(action=SimpleNamespace()))
    monkeypatch.setattr(planner_plan, "awakener_offers", lambda priced: (orb,))
    monkeypatch.setattr(planner_plan, "takes_inputs", lambda action: True)  # the orb reads a second item, as an offer that takes donors does
    target = SimpleNamespace()
    assert planner_plan.rounds_apply(None, target, (orb,), solve_it=True, judged=False, solver="auto")
    other = SimpleNamespace(offer=SimpleNamespace(action=SimpleNamespace()))
    assert not planner_plan.rounds_apply(None, target, (orb, other), solve_it=True, judged=False, solver="auto")  # a recombinator's donors still are not
    assert _rounds.rung(frozenset({_rounds.SECOND_ITEM})) == 1 + _rounds.rung(frozenset({"metamods"}))


def test_a_family_of_several_kinds_not_finished_is_tried_one_kind_a_step_in_the_second_pass():
    # the single orbs' family (two kinds) does not build in its step; the second pass tries each kind alone over the seed, and the first of them
    # builds and makes a cheaper plan
    offers = ("seed", "alt", "regal")
    kinds = {"seed": "seed", "alt": "alteration-orb", "regal": "regal-orb"}
    groups = (_rounds.Group((0,), ("seed",), frozenset({"junk"})), _rounds.Group((1, 2), ("alteration-orb", "regal-orb"), frozenset({"junk", "pool weights"})))
    seen = []

    def run(chosen, call):
        labels = tuple(offer.label for offer in chosen)
        seen.append(chosen)
        if labels == offers:
            raise Incomplete("the time limit of 9 seconds was reached", None)
        return _plan(5.0 if "alt" in labels else 10.0)

    named = tuple(SimpleNamespace(label=o, kind=kinds[o], blocks=None) for o in offers)
    widened = _widen(groups, named, run)
    assert [tuple(o.label for o in chosen) for chosen in seen] == [("seed",), ("seed", "alt", "regal"), ("seed", "alt"), ("seed", "alt", "regal")]
    assert [record.status for record in widened.records] == ["closed", "undone", "closed", "undone"] and widened.plan.mean_remaining == 5.0
    assert widened.records[1].reason.endswith("one kind a step (2 steps)")


@pytest.mark.parametrize("bad", [ValueError("refused"), _rounds.Stopped("the time limit of 9 seconds was reached", 3.0)])
def test_a_refused_or_stopped_family_is_retried_once_in_the_second_pass(bad):
    # #1088: a refused family is not set aside for good: the second pass tries it once more, over what was accepted by then, and no more
    offers = ("seed", "x")
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate(offers))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if "x" in chosen:
            raise bad
        return _plan(10.0)

    widened = _widen(groups, offers, run)
    assert seen == [("seed",), ("seed", "x"), ("seed", "x")] and widened.plan.mean_remaining == 10.0
    assert [record.status for record in widened.records][1:] == ["refused", "refused"] if isinstance(bad, ValueError) else ["stopped", "stopped"]


def test_a_step_s_error_kept_until_the_run_ends_does_not_keep_that_step_s_search_alive():
    # #1325 (kept from the rounds): the first step's error is kept until the run ends; its traceback held the frames it was raised from, and
    # with them the step's whole search (R11: 4,084 MB at the next round's start). Here the search of the only step raises from a frame that
    # holds its store, with a cause raised one frame deeper: once `widen` returns, the error is still there and the store is freed.
    import weakref

    class Store:
        pass

    alive = []

    def deeper(store):
        raise RuntimeError("deep in the search")

    def search(chosen, call):
        store = Store()
        alive.append(weakref.ref(store))
        try:
            deeper(store)
        except RuntimeError as cause:
            raise _rounds.Stopped("the time limit of 3 seconds was reached", None) from cause

    widened = _widen((_rounds.Group((0,), ("a",), frozenset({"junk", "a"})),), ("a",), search)
    assert str(widened.error) == "deep in the search"  # (a stop keeps its cause: what the caller raises, with its words)
    assert alive and all(ref() is None for ref in alive)

