"""B1's offers and kernels are what they were before the implicits, the quality and the offer joined the contract (ticket #142).

"Done when": on the routes R05 and R10 to R13 the offers (labels, resources, left-out reasons) and the kernels of the start
state (every state by its `repr`, with its integer weight) are byte-identical to those of main before the ticket. The
golden file `tests/golden/b1_unchanged_142.json` was written by `b1_unchanged_support.py` run on that code; the policies and
means of R05, R10 and R11 are pinned the same way by `plans_118.json` (`test_prune_bound.py`), and the routes by the
golden pages of the CLI tests. The fingerprints need the cached dump and skip cleanly without it, as in CI.
"""

import json
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from b1_unchanged_support import TARGETS, route_fingerprint

GOLDEN = json.loads((Path(__file__).parent / "golden" / "b1_unchanged_142.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def test_the_golden_file_holds_every_route():
    assert set(GOLDEN) == set(TARGETS)


@pytest.mark.parametrize("stem", TARGETS)
def test_the_offers_and_the_kernels_of_the_route_did_not_move(real, stem):
    found = route_fingerprint(real, stem)
    expected = GOLDEN[stem]

    assert found["offers"] == expected["offers"] and found["offers_sha"] == expected["offers_sha"], "the offers moved"
    assert found["left_out"] == expected["left_out"] and found["left_out_sha"] == expected["left_out_sha"], "the offers left out moved"
    assert found["start"] == expected["start"], "the start state moved (its repr is what a B1 state always read)"
    assert found["kernels"] == expected["kernels"] and found["kernels_sha"] == expected["kernels_sha"], "a kernel moved"
