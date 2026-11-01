"""The R25-sized case of ticket #212: three target mods and pairs of feeders stay within the counts ADR-0062 records.

The class world (three target prefixes A, B, C of weight 100, nine junk prefixes in three weight classes, junk told apart by
weight: 63 item states) with the recombinator of ADR-0033 on one side. ADR-0062 measured it on a GitHub runner: with the seed
of isolated feeders, two rounds, 8 acquisition processes, 504 product states, 4,204 actions, 385 of 3,906 (state, donor)
pairs offered, the value 3895.618279569891 at the empty item and the guide's AB + AC route; the product with every donor
offered has 3,969 states and took 814 s. Seconds are not asserted (ADR-0014): they are measured by
`.github/scripts/measure_donors.py` in a heavy run and reported in the pull request. The raw world (299 item states, every
junk mod named) is measured there too; here only its size is counted.
"""

import pytest
from donor_world_support import R25World

from crafting_system.solver import solve_lazily


@pytest.fixture(scope="module")
def world():
    return R25World(raw=False)


@pytest.fixture(scope="module")
def lazy(world):
    return solve_lazily(world.full_model(), world.blank, seed=world.isolated_feeder)


def test_the_world_has_the_sizes_the_adr_names():
    assert len(R25World(raw=False).states()) == 63 and len(R25World(raw=False).donors()) == 62
    assert len(R25World(raw=True).states()) == 299


def test_the_lazy_run_stays_within_the_state_counts_of_the_adr(lazy, world):
    assert lazy.pairs == 63 * 62  # 3,906 (state, donor) pairs of the full model
    assert len(lazy.rounds) <= 2
    assert lazy.rounds[-1].wants <= 8  # the main target and seven donors: the single mods and the pairs, nothing with junk
    assert len(lazy.values) <= 504  # against 3,969 with every donor offered
    assert lazy.offered_pairs <= 441  # the seed offers 7 feeders at 63 states; the ADR's 385 is the same seed minus 8 receivers
    assert lazy.rounds[-1].added == 0


def test_the_value_is_the_one_the_adr_records(lazy):
    assert lazy.value == pytest.approx(3895.618279569891, rel=1e-9)
    assert lazy.error_bound < 1e-8


def test_the_route_is_the_guides_pairs_from_single_mods(lazy, world):
    """The donors the policy uses are made of target mods only, singles and pairs: the AB + AC route."""
    used = {action.label[1] for action in lazy.solution.policy.values() if isinstance(action.label, tuple)}
    assert used and all(set(donor) <= set(world.targets) for donor in used)
    assert {len(donor) for donor in used} <= {1, 2}


def test_a_seed_of_nothing_gives_the_same_value_with_more_wants_on_a_smaller_pool():
    """The seed only saves rounds (ADR-0062 decision 4); at the full size a seed of nothing builds 35 processes and takes minutes."""
    small = R25World(raw=False, junk=((500, 2), (1000, 1)))
    seeded = solve_lazily(small.full_model(), small.blank, seed=small.isolated_feeder)
    bare = solve_lazily(small.full_model(), small.blank)
    assert bare.value == pytest.approx(seeded.value, rel=1e-9)
    assert bare.rounds[-1].wants >= seeded.rounds[-1].wants and len(bare.rounds) >= len(seeded.rounds)
