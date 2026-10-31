"""A seeded generator of block-structured SSPs for the two-bounds tests (not collected as tests).

`block_ssp(seed)` returns an exact small SSP together with a partition of its states into blocks and
the optimistic and pessimistic block models of ADR-0023, built the way the ADR requires:

* an action type has one block-level kernel (integer weights over blocks and the goal), the same
  for every member of the block that has it (block-invariant);
* a member's version of the type splits each block-level weight `w` into integer weights over the
  members of the target block, in its own way, total exactly `w`, so the member's kernel pushed
  through the block map is the block kernel;
* legality differs by member (a type is legal in a random non-empty subset of the block), and so
  does the cost;
* the optimistic model offers every legal action of every member, pushed through the block map;
  the pessimistic model offers a type only if every member has it, at the largest member cost.

Specs use the format of `ssp_oracles`: `(size, table)`, the goal is `size`, costs are `Fraction`.
"""

import random
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class BlockSpec:
    exact: tuple  # (size, table): the exact SSP
    block_of: tuple  # exact state -> block index (the goal is its own block, `nblocks`)
    members: tuple  # block index -> tuple of exact states
    kernels: dict  # (block, type) -> {target block or goal: weight}
    legal: dict  # (block, type) -> tuple of members that have the type
    costs: dict  # (state, type) -> Fraction
    index_of: dict  # (state, type) -> index of the action in the exact table of the state
    optimistic: tuple  # (nblocks, table) over the blocks
    pessimistic: tuple  # (nblocks, table) over the blocks

    @property
    def nblocks(self):
        return len(self.members)


def block_ssp(seed, *, safe=None, max_states=6):
    """A seeded block-structured SSP; `safe=True` gives every block an always-legal progress type.

    A progress type has a positive weight toward a later block or the goal, so every exact state
    has a proper policy. `safe=None` draws it (most seeds are safe).
    """
    rng = random.Random(seed)
    size = rng.randint(3, max_states)
    nblocks = rng.randint(2, min(4, size))
    if safe is None:
        safe = rng.random() < 0.85
    block_of = [i % nblocks for i in range(size)]
    rng.shuffle(block_of)
    members = tuple(tuple(s for s in range(size) if block_of[s] == b) for b in range(nblocks))
    goal = nblocks

    kernels, legal, costs = {}, {}, {}
    for b in range(nblocks):
        first = 0 if safe else 1
        types = list(range(first, rng.randint(1, 2) + 1))
        for t in types:
            if t == 0:
                targets = rng.sample(range(b + 1, nblocks + 1), k=rng.randint(1, min(2, nblocks - b)))
                kernel = {x: rng.randint(1, 6) for x in targets}
                if rng.random() < 0.5:
                    kernel[rng.randint(0, b)] = rng.randint(1, 6)  # a way back or a self loop
                legal[b, t] = members[b]
            else:
                kernel = {x: rng.randint(1, 6) for x in rng.sample(range(nblocks + 1), k=rng.randint(1, 3))}
                legal[b, t] = tuple(sorted(rng.sample(members[b], k=rng.randint(1, len(members[b])))))
            kernels[b, t] = kernel
            for s in members[b]:
                costs[s, t] = Fraction(rng.randint(1, 20), 4)

    def split(weight, target):
        """Integer weights over the members of `target` (the goal is one member), total `weight`."""
        group = (size,) if target == goal else members[target]
        counts = Counter(rng.choice(group) for _ in range(weight))
        return [(s, w) for s, w in sorted(counts.items())]

    table, index_of = {}, {}
    for s in range(size):
        actions = []
        for (b, t), kernel in kernels.items():
            if b == block_of[s] and s in legal[b, t]:
                outcomes = [pair for target, w in kernel.items() for pair in split(w, target)]
                index_of[s, t] = len(actions)
                actions.append((f"{s}.{t}", costs[s, t], outcomes))
        table[s] = actions

    def block(state):
        return goal if state == size else block_of[state]

    optimistic, pessimistic = {}, {}
    for b in range(nblocks):
        optimistic[b], pessimistic[b] = [], []
        for t in sorted({t for (bb, t) in kernels if bb == b}):
            for s in legal[b, t]:
                pushed = Counter()
                for state, w in table[s][index_of[s, t]][2]:
                    pushed[block(state)] += w
                optimistic[b].append(((b, t, s), costs[s, t], sorted(pushed.items())))
            if len(legal[b, t]) == len(members[b]):
                worst = max(costs[s, t] for s in members[b])
                pessimistic[b].append(((b, t), worst, sorted(kernels[b, t].items())))
    return BlockSpec(
        exact=(size, table),
        block_of=tuple(block_of),
        members=members,
        kernels=kernels,
        legal=legal,
        costs=costs,
        index_of=index_of,
        optimistic=(nblocks, optimistic),
        pessimistic=(nblocks, pessimistic),
    )


def pushed_kernel(spec, state, type_):
    """The exact action `type_` of `state` pushed through the block map, or None if not legal."""
    size, table = spec.exact
    if (state, type_) not in spec.index_of:
        return None
    pushed = Counter()
    for target, w in table[state][spec.index_of[state, type_]][2]:
        pushed[spec.nblocks if target == size else spec.block_of[target]] += w
    return dict(pushed)


def lifted_choice(spec, policy):
    """The exact choice (state -> action index) of a policy on the pessimistic block model."""
    size, _ = spec.exact
    choice = {}
    for state in range(size):
        action = policy.get(spec.block_of[state])
        choice[state] = None if action is None else spec.index_of[state, action.label[1]]
    return choice
