"""The stochastic shortest path; branching in B3 (ADR-0010, ADR-0011). May import only: data, rules, items, actions, abstraction.

The solver itself is generic: states are any hashable objects and it knows nothing of Path of Exile
(`tests/test_solver_independence.py` guards that). It is pure standard-library Python except the packed solve
(`_packed*.py`, ticket #374), which uses numpy (ADR-0063).
"""

from ._acquire import MAIN, Acquisition, Need
from ._bounds import Bounds, solve_bounds
from ._certify import ConvergenceError
from ._minmax import solve_variants
from ._model import Action, Model, Outcome, Peek, TabularModel, VariantAction
from ._packed import PackedBuilder, PackedGraph, PackedModel, pack_model
from ._packed_model import solve_packed_model
from ._packed_solve import PackedSolution, certify, policy_reach, solve_packed
from ._peek import ExpandedModel, PeekNode, PeekSolution, Reaction, peek_backup, solve_peek
from ._solve import Solution, solve
from ._tail import NoPolicyError, TailCut, solve_tail_cut

__all__ = [
    "Acquisition",
    "Action",
    "Bounds",
    "ConvergenceError",
    "ExpandedModel",
    "MAIN",
    "Model",
    "Need",
    "NoPolicyError",
    "PackedBuilder",
    "PackedGraph",
    "PackedModel",
    "PackedSolution",
    "Outcome",
    "Peek",
    "PeekNode",
    "PeekSolution",
    "Reaction",
    "Solution",
    "TabularModel",
    "TailCut",
    "VariantAction",
    "certify",
    "pack_model",
    "peek_backup",
    "policy_reach",
    "solve",
    "solve_packed",
    "solve_packed_model",
    "solve_bounds",
    "solve_peek",
    "solve_tail_cut",
    "solve_variants",
]
