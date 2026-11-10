"""A route's gaps and divergences are named even where the report does not show the state on its own (#662).

The report numbers `S1`, `S2`, ... the states of `Plan.view_policy`; for a big packed policy that is the lumped chain, one shown state
per block. The route is read on the whole policy, so its first divergence can be a state the report does not number: R04 at the prices of
2026-11-10 diverged on one, and the route section and the benchmark failed with a KeyError (heavy run 42907425205).
"""

from types import SimpleNamespace

from crafting_system.cli._report import name_states
from crafting_system.cli._route import Divergence, Gap
from crafting_system.cli._route_report import _place, route_state_ids


def test_name_states_keeps_the_report_ids_and_numbers_the_others_in_order():
    named = name_states({"a": "S1", "b": "S2"}, ["b", "x", "y", "x"])
    assert named == {"a": "S1", "b": "S2", "x": "R1", "y": "R2"}


def test_the_divergence_on_a_state_the_report_does_not_number_gets_the_next_r_id():
    report = SimpleNamespace(ids={"start": "S1", "shown": "S2"})
    result = SimpleNamespace(gaps=(Gap("off", "no rule"),), divergence=Divergence("member", "Regal Orb", "Exalted Orb"))
    ids = route_state_ids(report, result)
    assert ids["off"] == "R1"  # the gaps keep the numbers they had before the divergence was named
    assert ids["member"] == "R2"
    assert route_state_ids(report, SimpleNamespace(gaps=(), divergence=Divergence("shown", "a", "b")))["shown"] == "S2"


def test_the_place_of_a_policy_state_the_lumped_view_does_not_show_says_so():
    plan = SimpleNamespace(lumped=True, policy={"member": object()})
    report = SimpleNamespace(step_of={}, plan=plan)
    assert _place(report, "member") == "a state of the policy that the report shows by another state of its block"
    assert _place(report, "off") == "a state the policy never reaches"
    assert _place(SimpleNamespace(step_of={}, plan=SimpleNamespace(lumped=False, policy={"member": 1})), "member") == "a state the policy never reaches"

