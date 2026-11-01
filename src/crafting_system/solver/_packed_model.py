"""The packed solve for a generic `Model`: the same answer as `solve`, held in arrays (ticket #374).

`solve_packed_model` walks the model into a packed graph (`pack_model`), merges it exactly, solves and certifies it
(`solve_packed`), and returns the `Solution` the object solver would: the value of every reachable state and the
policy as the model's own `Action` objects. It takes plain actions only (no `extra_inputs`, no `VariantAction`, no
`Peek`); those stay with `solve`, `solve_variants` and `solve_peek`.
"""

from collections.abc import Callable, Iterable

from ._packed import pack_model
from ._packed_solve import DENSE_LIMIT, solve_packed
from ._solve import Solution
from ._model import Model


def solve_packed_model[S](
    model: Model[S],
    starts: Iterable[S],
    *,
    tolerance: float = 1e-10,
    dense_limit: int = DENSE_LIMIT,
    merge: bool = True,
    progress: Callable[[str], None] | None = None,
) -> Solution[S]:
    """Minimise the mean cost to a goal from every state reachable from `starts`, on packed arrays."""
    packed = pack_model(model, starts)
    solved = solve_packed(packed.graph, tolerance=tolerance, dense_limit=dense_limit, merge=merge, progress=progress)
    states = packed.states
    values = solved.value.tolist()
    actions = solved.action.tolist()
    return Solution(
        values={state: values[i] for i, state in enumerate(states)},
        policy={states[i]: packed.actions[a] for i, a in enumerate(actions) if a >= 0},
        error_bound=solved.error_bound,
    )
