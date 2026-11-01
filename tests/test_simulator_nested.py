"""The simulator's nested runs for the inputs of a step (ticket #222, ADR-0022, ADR-0062), on hand-solved chains.

A step with inputs first runs each input's sub-policy from its start item to its goal, adds the cost, then applies the
two-item action to the concrete items. The chains here have closed forms, so the simulated figures are compared with the
exact ones at five standard errors (a correct run fails about once in 1.7 million); the seeds are fixed. The solver's
values on the toy of ticket #180 and on the real recombinator are in `test_simulator_nested_solver.py`.

* `E -> Q`: `craft` costs 3 and gives `Q` with chance 1/2, else stays at `E`: a geometric number of clicks, cost 6, 2 clicks.
* the main chain: from `E`, `graft` costs 2, consumes a `Q` made by that run, and gives `PQ` with chance 1/4, else stays at `E`;
  an attempt costs 2 + 6 = 8 and takes 1 + 2 clicks, four attempts on average: cost 32, 12 clicks, 4 donors.
"""

import math

import pytest
from nested_support import STATES, ToyAction, state_of
from simulator_support import DATA

from crafting_system.simulator import DonorMismatchError, Input, SimulationReport, Step, simulate

E, P, Q, PQ, J = (STATES[name] for name in ("E", "P", "Q", "PQ", "J"))
RUNS = 20_000


def is_q(item):
    return item == Q


def is_pq(item):
    return item == PQ


CRAFT_Q = ToyAction((("Q", 1), ("E", 1)))
GRAFT = ToyAction((("PQ", 1), ("E", 3)), wants="Q")


def donor_policy(cost=3.0):
    return lambda item: Step(CRAFT_Q, cost) if item == E else None


def graft_step(item, **fields):
    inputs = fields.pop("inputs", None)
    inputs = (Input(E, donor_policy(), is_q, **fields),) if inputs is None else inputs
    return Step(GRAFT, 2.0, inputs, lambda donors: GRAFT.bound(donors[0]))


def main_policy(item):
    return graft_step(item) if item == E else None


def run(policy=main_policy, **arguments):
    arguments.setdefault("runs", RUNS)
    return simulate(DATA, policy, E, is_pq, seed=arguments.pop("seed", 5), **arguments)


def assert_mean_is(report, expected):
    assert report.cost.agrees_with(expected), (report.cost, expected)


def test_a_step_pays_its_input_runs_on_every_attempt():
    report = run()

    assert report.successes == RUNS and report.stopped == report.unfinished == 0
    assert_mean_is(report, 32.0)


def test_the_donors_are_counted_and_so_are_the_clicks_of_the_nested_runs():
    report = run()

    assert report.nested_runs > 0
    assert report.mean_nested_runs == pytest.approx(4.0, abs=0.15)  # one donor per attempt, four attempts on average
    assert report.mean_steps == pytest.approx(12.0, abs=0.5)  # (1 graft + 2 crafts) per attempt


def test_a_policy_with_no_inputs_has_no_nested_runs():
    report = simulate(DATA, lambda item: Step(CRAFT_Q, 3.0) if item == E else None, E, is_q, runs=2_000, seed=1)

    assert report.nested_runs == 0 and report.mean_nested_runs == 0.0
    assert_mean_is(report, 6.0)


def test_the_action_is_applied_to_the_donor_the_nested_run_made():
    seen = []

    def bind(donors):
        seen.append(donors)
        return GRAFT.bound(donors[0])

    run(lambda item: Step(GRAFT, 2.0, (Input(E, donor_policy(), is_q),), bind) if item == E else None, runs=50)

    assert seen and all(donors == (Q,) for donors in seen)


def test_an_unbound_two_item_action_refuses_to_run_without_its_donor():
    with pytest.raises(AssertionError, match="without a donor"):
        run(lambda item: Step(GRAFT, 2.0, (Input(E, donor_policy(), is_q),)) if item == E else None, runs=5)


def test_an_input_that_is_already_its_want_costs_only_its_start():
    policy = lambda item: graft_step(item, inputs=(Input(Q, donor_policy(), is_q, start_cost=5.0),)) if item == E else None  # noqa: E731
    report = run(policy)

    assert_mean_is(report, 4 * (2.0 + 5.0))  # four attempts of 2 + 5, the donor never needs a click
    assert report.mean_steps == pytest.approx(4.0, abs=0.2)


def test_the_start_cost_of_an_input_is_paid_on_every_attempt():
    policy = lambda item: graft_step(item, inputs=(Input(E, donor_policy(), is_q, start_cost=1.5),)) if item == E else None  # noqa: E731

    assert_mean_is(run(policy), 4 * (2.0 + 1.5 + 6.0))


def test_an_input_that_needs_an_input_of_its_own_nests_to_any_depth():
    # Q is made from E by `refine` (cost 1, chance 1/2) which consumes a P made by `craft P` (cost 1, chance 1/2):
    # a P costs 2, a refine attempt 1 + 2 = 3, a Q 6, an attempt of the main step 2 + 6 = 8, four attempts: 32.
    refine = ToyAction((("Q", 1), ("E", 1)), wants="P")
    craft_p = ToyAction((("P", 1), ("E", 1)))
    p_policy = lambda item: Step(craft_p, 1.0) if item == E else None  # noqa: E731
    q_policy = lambda item: Step(refine, 1.0, (Input(E, p_policy, lambda it: it == P),), lambda d: refine.bound(d[0])) if item == E else None  # noqa: E731
    policy = lambda item: Step(GRAFT, 2.0, (Input(E, q_policy, is_q),), lambda d: GRAFT.bound(d[0])) if item == E else None  # noqa: E731
    report = run(policy)

    assert_mean_is(report, 32.0)
    assert report.mean_nested_runs == pytest.approx(4.0 * (1 + 2), abs=0.4)  # per main attempt: one Q run with two P runs


def test_two_inputs_are_made_in_order_and_both_are_paid():
    graft_two = ToyAction((("PQ", 1), ("E", 1)))
    donors_seen = []

    def bind(donors):
        donors_seen.append(donors)
        return graft_two

    craft_p = ToyAction((("P", 1),))  # a P is one click
    p_policy = lambda item: Step(craft_p, 4.0) if item == E else None  # noqa: E731
    policy = lambda item: Step(graft_two, 1.0, (Input(E, donor_policy(), is_q), Input(E, p_policy, lambda it: it == P)), bind) if item == E else None  # noqa: E731
    report = run(policy, runs=4_000)

    assert all(donors == (Q, P) for donors in donors_seen)
    assert_mean_is(report, 2 * (1.0 + 6.0 + 4.0))  # two attempts on average, each 1 + a Q (6) + a P (4)


def test_a_donor_the_step_refuses_raises_donor_mismatch():
    policy = lambda item: graft_step(item, matches=lambda donor: donor == J) if item == E else None  # noqa: E731

    with pytest.raises(DonorMismatchError):
        run(policy, runs=5)


def test_a_donor_the_step_accepts_passes_the_check():
    seen = []

    def accepts(donor):
        seen.append(donor)
        return donor == Q

    policy = lambda item: graft_step(item, matches=accepts) if item == E else None  # noqa: E731
    run(policy, runs=100)

    assert seen and set(seen) == {Q}


def test_a_nested_run_that_the_policy_stops_stops_the_run_that_asked_with_the_cost_paid():
    policy = lambda item: graft_step(item, inputs=(Input(E, lambda it: None, is_q, start_cost=1.0),)) if item == E else None  # noqa: E731
    report = run(policy, runs=500)

    assert report.stopped == 500 and report.successes == 0
    assert set(report.costs) == {3.0}  # the graft's 2 and the donor's start 1, then nothing
    assert report.mean_nested_runs == 1.0


def test_a_nested_run_that_does_not_finish_leaves_the_run_unfinished():
    spin = ToyAction((("E", 1),))
    policy = lambda item: graft_step(item, inputs=(Input(E, lambda it: Step(spin, 1.0), is_q),)) if item == E else None  # noqa: E731
    report = run(policy, runs=50, max_steps=25)

    assert report.unfinished == 50 and report.successes == report.stopped == 0
    assert set(report.costs) == {2.0 + 25.0}  # the graft, then 25 clicks of the donor


def test_the_step_budget_is_shared_by_the_whole_tree_of_runs():
    # every attempt takes 1 + 2 clicks on average; a budget of 2 clicks cannot even finish one attempt with a donor run of 2+
    report = run(runs=2_000, max_steps=2)

    assert report.unfinished > 0 and report.successes < 2_000
    assert report.mean_steps <= 2.0


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_the_blocks_give_the_same_report_for_any_number_of_workers(workers):
    serial = run(runs=1_000, block=100, workers=1)
    pooled = run(runs=1_000, block=100, workers=workers)

    assert pooled == serial and pooled.nested_runs == serial.nested_runs


def test_the_same_seed_gives_the_same_nested_report_and_another_seed_another():
    assert run(runs=500, seed=3) == run(runs=500, seed=3)
    assert run(runs=500, seed=3).costs != run(runs=500, seed=4).costs


# --- readings -------------------------------------------------------------------------------------------------------------------------


class ReadingAction:
    """Records the reading it is asked for; `outcomes` is the plan, `outcomes_under` the reading."""

    def __init__(self, row, log):
        self.row, self.log = row, log

    def outcomes(self, data, item):
        self.log.append(None)
        return ToyAction(self.row).outcomes(data, item)

    def outcomes_under(self, data, item, reading=None):
        self.log.append(reading)
        return ToyAction(self.row).outcomes(data, item)


def reading_policy(log):
    donor = ReadingAction((("Q", 1),), log)
    main = ReadingAction((("PQ", 1),), log)
    sub = lambda item: Step(donor, 1.0) if item == E else None  # noqa: E731
    return lambda item: Step(main, 1.0, (Input(E, sub, is_q),)) if item == E else None


def test_a_reading_is_handed_to_the_actions_of_the_run_and_of_its_nested_runs():
    log = []
    simulate(DATA, reading_policy(log), E, is_pq, runs=3, seed=1, reading="alpha-0")

    assert log == ["alpha-0"] * 6  # per run: the donor's click, then the main one


def test_without_a_reading_the_plan_is_sampled():
    log = []
    simulate(DATA, reading_policy(log), E, is_pq, runs=3, seed=1)

    assert log == [None] * 6


def test_an_action_that_takes_no_readings_ignores_one():
    report = simulate(DATA, donor_policy(), E, is_q, runs=2_000, seed=1, reading="anything")

    assert_mean_is(report, 6.0)


# --- arguments ------------------------------------------------------------------------------------------------------------------------


def test_the_input_and_the_step_check_their_arguments():
    with pytest.raises(ValueError, match="start_cost"):
        Input(E, donor_policy(), is_q, start_cost=-1.0)
    with pytest.raises(ValueError, match="start_cost"):
        Input(E, donor_policy(), is_q, start_cost=math.inf)
    with pytest.raises(ValueError, match="Input"):
        Step(GRAFT, 1.0, (donor_policy(),))
    with pytest.raises(ValueError, match="inputs"):
        Step(CRAFT_Q, 1.0, (), lambda donors: CRAFT_Q)
    with pytest.raises(ValueError, match="bind"):
        Step(GRAFT, 1.0, (Input(E, donor_policy(), is_q),), "not callable")


def test_a_step_keeps_its_inputs_as_a_tuple():
    step = Step(GRAFT, 1.0, [Input(E, donor_policy(), is_q)])

    assert isinstance(step.inputs, tuple) and len(step.inputs) == 1
    assert Step(CRAFT_Q, 1.0).inputs == () and Step(CRAFT_Q, 1.0).bind is None


def test_the_report_of_a_policy_without_inputs_is_what_it_was():
    report = simulate(DATA, lambda item: Step(CRAFT_Q, 3.0) if item == E else None, E, is_q, runs=100, seed=2)

    assert isinstance(report, SimulationReport) and report.nested_runs == 0
    assert report.successes == 100 and state_of(Q) == "Q"


# --- what the checker asked to pin (ticket #222) ---------------------------------------------------------------------------------------


def test_a_run_with_no_inputs_adds_its_costs_onto_the_start_cost_one_at_a_time_as_it_always_did():
    steps = {"E": (0.2, "P"), "P": (0.3, "PQ")}
    chain = {STATES[state]: Step(ToyAction(((target, 1),)), cost) for state, (cost, target) in steps.items()}

    report = simulate(DATA, chain.get, E, is_pq, runs=2, seed=1, start_cost=0.1)

    assert report.costs == ((0.1 + 0.2) + 0.3,) * 2  # 0.6000000000000001, not 0.1 + (0.2 + 0.3)


def test_inputs_that_ask_for_each_other_with_no_click_between_end_unfinished_not_in_a_recursion_error():
    two_way = ToyAction((("PQ", 1),))
    policies = {}
    policies["a"] = lambda item: Step(two_way, 1.0, (Input(E, policies["b"], is_q),)) if item == E else None
    policies["b"] = lambda item: Step(two_way, 1.0, (Input(E, policies["a"], is_q),)) if item == E else None

    report = simulate(DATA, policies["a"], E, is_pq, runs=3, seed=1)

    assert report.unfinished == 3 and report.successes == report.stopped == 0
    assert set(report.costs) == {101.0}  # one unit for each of the 101 levels that asked, then the cut


def test_the_cost_of_a_step_whose_nested_runs_used_the_last_click_stays_paid():
    # the donor takes one click (always a Q, 3 chaos); with a budget of 1 the graft cannot be taken after it: 3 + 2 paid
    certain = ToyAction((("Q", 1),))
    donor = lambda it: Step(certain, 3.0) if it == E else None  # noqa: E731
    policy = lambda item: Step(GRAFT, 2.0, (Input(E, donor, is_q),)) if item == E else None  # noqa: E731
    report = run(policy, runs=10, max_steps=1)

    assert report.unfinished == 10 and set(report.costs) == {5.0}
    assert report.mean_steps == 1.0
