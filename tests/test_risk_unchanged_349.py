"""Plans without a free action keep the risk output they had on main (ticket #349, golden test).

The free-action grid of #349 is taken only when the caller names a free cost and the policy holds an action of that cost. Everything else, the
ordinary grid, the coarse grid, the policies with inputs and the ones that can fail, must give the same reports digit for digit as before it:
`tests/golden/risk_unchanged_349.json` holds their `repr`, made on main by `tests/risk_unchanged_support.py`.
"""

import json

from risk_unchanged_support import GOLDEN, snapshot


def test_the_risk_reports_of_policies_without_a_free_action_are_the_ones_main_gave():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    found = snapshot()

    assert sorted(found) == sorted(expected)
    for name in sorted(expected):
        assert found[name] == expected[name], name
