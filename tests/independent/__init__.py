"""Code that the oracle, the reconciliation checks and their tests share, and that imports nothing of the planner (ticket #419).

Two modules: `ladder`, the natural tier ladder and the base-name rule (#419), and `export`, the loader of the raw repoe-fork
export (#432). Both `tests/oracle/` and `tests/reconcile/` may import exactly those two modules; their independence tests say so.
`test_independent_guard.py` holds this folder to the standard library and `yaml`.
"""
