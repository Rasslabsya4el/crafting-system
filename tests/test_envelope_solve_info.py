"""#1468: what a solve puts into its `info` is added into the search's `SearchStats.solve_info` by the kind of each value, never by its name.

A solve whose evaluation was taken at the limit of its method sets `info["linear_limit"]` to a record (states, residual, amplification, why,
`solver/_packed_solve.evaluate_policy`); the search summed every value as a number and died there with a TypeError (int + dict), losing the plan of
a long run (the R17 hand test, H17 of board #1434). The record is kept as the count of the solves that held it with the worst of each figure, and the
run's progress says it.
"""

import math

from envelope_support import ExplicitProblem, dense_optimum, random_graph

from crafting_system.planner import _envelope as envelope
from crafting_system.planner._envelope import Search


def test_a_solve_taken_at_its_linear_limit_does_not_end_the_search_and_its_record_reaches_the_report(monkeypatch):
    graph = random_graph(3, 40)
    value, _ = dense_optimum(graph)
    real = envelope.solve_graph
    residuals = []

    def at_its_limit(*args, info, **kwargs):  # the real solve, then the record `evaluate_policy` writes when it keeps an iterate at its limit
        core = real(*args, info=info, **kwargs)
        residuals.append(10.0 ** -(9 + len(residuals) % 3))
        info["linear_limit"] = {"states": 100 + len(residuals), "residual": residuals[-1], "amplification": 2.5e5, "why": "needs 123 cells", "rows": 900, "cells": 5e9, "allowed": 2.5e8}
        return core

    monkeypatch.setattr(envelope, "solve_graph", at_its_limit)
    said = []
    result = Search(ExplicitProblem(graph, value, 0.5), progress=said.append).run()

    record = result.stats.solve_info["linear_limit"]
    rounds = result.stats.rounds
    assert rounds >= 1 and record["solves"] == rounds  # the lower solves of the rounds (the upper solves have their own info)
    assert record["residual"] in residuals and record["states"] >= 101  # a figure a solve said (the worst of them: `test_each_kind_of_value_is_added_by_its_rule`)
    assert record["amplification"] == 2.5e5 and record["why"] == "needs 123 cells"
    assert any(text.strip().startswith(f"linear_limit in {rounds:,} solves: worst ") and "residual" in text and "amplification 2.5e+05" in text for text in said)
    assert result.exact and math.isfinite(result.lower)  # the search ended as it would have, with its plan


def test_each_kind_of_value_is_added_by_its_rule():
    from crafting_system.planner._envelope import add_solve_info, solve_info_records  # (here, so the test above fails on main with its TypeError, not on the import)

    totals = {}
    add_solve_info(totals, {"matvecs": 3, "seconds": 0.5, "warm": "kept", "skipped": None, "linear_limit": {"states": 5, "residual": 1e-9, "why": "a"}, "cut": (1, 2)})
    add_solve_info(totals, {"matvecs": 4, "seconds": 0.25, "warm": "kept", "skipped": 2, "linear_limit": {"states": 3, "residual": 4e-9, "why": "b"}, "cut": [3]})

    assert totals["matvecs"] == 7 and totals["seconds"] == 0.75 and totals["warm_kept"] == 2 and totals["skipped"] == 2
    assert totals["linear_limit"] == {"solves": 2, "states": 5, "residual": 4e-9, "why": "b"}  # the worst figures, the last words
    assert totals["cut"] == 2  # a value of no other kind is counted
    assert solve_info_records(totals) == ["linear_limit in 2 solves: worst states 5, residual 4e-09; last why: b"]
