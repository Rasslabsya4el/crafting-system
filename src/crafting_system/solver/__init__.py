"""The stochastic shortest path; branching in B3 (ADR-0010, ADR-0011). May import only: data, rules, items, actions, abstraction.

The solver itself is generic: states are any hashable objects, it is pure standard-library Python
and knows nothing of Path of Exile (`tests/test_solver_independence.py` guards that).
"""

from ._bounds import Bounds, solve_bounds
from ._certify import ConvergenceError
from ._minmax import solve_variants
from ._model import Action, Model, Outcome, TabularModel, VariantAction
from ._solve import Solution, solve

__all__ = [
    "Action",
    "Bounds",
    "ConvergenceError",
    "Model",
    "Outcome",
    "Solution",
    "TabularModel",
    "VariantAction",
    "solve",
    "solve_bounds",
    "solve_variants",
]
