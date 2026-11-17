"""The guard of `two_runs_support` (#1136): a comparison of two runs, or a golden, whose answer names a round's measured seconds fails at once."""

import pytest
from two_runs_support import masked, without_timings

ON_THE_CLOCK = "round 1 (chaos-orb; 1 actions offered, 0 s): finished, its best plan costs 29.13 Chaos"
IN_STATES = "round 1 (chaos-orb; 1 actions offered, 2 states): finished, its best plan costs 29.13 Chaos"


def test_a_text_or_a_document_counted_in_states_passes_without_its_measured_times():
    assert masked(f"Run time: working out the plan took 12 ms\n{IN_STATES}\n") == f"Run time: <measured>\n{IN_STATES}\n"
    assert without_timings({"limits": [IN_STATES], "timings_seconds": {"solve": 0.4}}) == {"limits": [IN_STATES]}


@pytest.mark.parametrize("seconds", ["0 s", "1 s", "1,204 s"])
def test_a_round_that_names_its_seconds_fails_the_text_and_the_document(seconds):
    line = ON_THE_CLOCK.replace("0 s", seconds)
    with pytest.raises(AssertionError, match="counted in states"):
        masked(line)
    with pytest.raises(AssertionError, match="counted in states"):
        without_timings({"limits": [line]})
