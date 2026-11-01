"""The lift of a solved policy to concrete items (ADR-0023, ticket #128): what `--verify` runs.

An exact plan's policy is keyed by compressed states, so a concrete item is compressed and the table gives its
action. An approximate plan's policy is keyed by blocks, so the item goes one step further. A table may also
hold exact states (a level can keep some states exact, as the tail cut does), so the exact state is looked up
first and only a state without an entry is mapped to its block.
"""

from collections.abc import Mapping

from crafting_system.abstraction import CompressedState
from crafting_system.items import Item
from crafting_system.simulator import Policy, Step

from ._plan import Plan


def lift(plan: Plan, steps: Mapping[CompressedState, Step]) -> Policy:
    """The simulator's policy for `plan`: concrete item -> compress -> (block) -> policy table -> `Step`.

    This is the lift of ADR-0023. `steps` maps the keys of `plan.policy` (states of an exact plan, blocks of an
    approximate one) to the step each stands for. For an approximate plan the item is compressed to its exact
    state, looked up there first, and else mapped to its block by `plan.approximation.coarsening.coarsen`
    and looked up there. A key with no step stops the run (None).

    It is sound because the actions on the ladder are block-invariant: every member of a block has the same
    legal actions, so the pessimistic policy's action for a block is legal on every item of it. The lift reads the
    coarsening of the approximation and nothing about the level that built it.
    """
    abstraction = plan.abstraction
    if plan.approximation is None:
        return lambda item: steps.get(abstraction.compress(item))
    coarsen = plan.approximation.coarsening.coarsen

    def policy(item: Item) -> Step | None:
        state = abstraction.compress(item)
        step = steps.get(state)
        return step if step is not None else steps.get(coarsen(state))

    return policy
