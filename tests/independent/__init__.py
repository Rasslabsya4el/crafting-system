"""Code that the oracle, the reconciliation checks and their tests share, and that imports nothing of the planner (ticket #419).

One module today, `ladder`: the natural tier ladder and the base-name rule. Both `tests/oracle/` and `tests/reconcile/` may import
exactly that module; their independence tests say so. `test_independent_guard.py` holds this folder to the standard library and `yaml`.
"""
