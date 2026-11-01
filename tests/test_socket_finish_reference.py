"""The socket finish on a four-socket item, solved densely and kept as a fixture (ADR-0058, ticket #230).

An independent oracle for the finish of ADR-0045: every state is one colour per socket and the link groups, every
Chromatic Orb outcome is listed (no tables shared, no reduction), and the optimum is found by policy iteration on
the whole graph. S5's layer 3 (ADR-0045, "the finish value equals the dense value iteration") runs against the same
numbers. The kernels are the formulas of ADR-0047 written out again here, so this file does not import the product.

Item of the fixture: four white, unlinked sockets, item level 84, 20% quality, the three attribute requirements
equal (each colour a third of a coloured socket), Orb of Fusing at 20% quality and Chromatic Orb only, one orb
each at a price of 1.
"""

from fractions import Fraction
from itertools import product

import numpy as np
import pytest

P_COLOURED = Fraction(375, 100000) * (84 - 14) * Fraction(120, 100)  # Siveran's formula, item level 84, quality 20
FUSING_WEIGHTS = {1: 17818, 2: 34818, 3: 26766, 4: 19672, 5: 826, 6: 100}  # 20% quality, sizes 1 to 6


def chromatic(n):
    """Outcome probabilities of one Chromatic Orb on n sockets, colours 0 white, 1 to 3 red, green and blue."""
    out = {}
    for colours in product(range(4), repeat=n):
        p = Fraction(1)
        for c in colours:
            p *= 1 - P_COLOURED if c == 0 else P_COLOURED / 3
        out[colours] = p
    all_white = out.pop((0,) * n)
    for c in (1, 2, 3):  # every socket rolled white: the first socket is made coloured
        first = (c,) + (0,) * (n - 1)
        out[first] += all_white / 3
    return out


def fusing(n):
    """Probability of each tuple of link-group sizes: sizes drawn in turn from the weights cut to what remains."""
    out = {(): Fraction(1)}
    for _ in range(n):
        step = {}
        for sizes, p in out.items():
            remaining = n - sum(sizes)
            if remaining == 0:
                step[sizes] = p
                continue
            total = sum(FUSING_WEIGHTS[s] for s in range(1, remaining + 1))
            for s in range(1, remaining + 1):
                step[sizes + (s,)] = step.get(sizes + (s,), 0) + p * Fraction(FUSING_WEIGHTS[s], total)
        out = step
    return out


def goal(colours, sizes, links, needs):
    start = 0
    for size in sizes:
        group = colours[start:start + size]
        start += size
        if size >= links and all(group.count(c + 1) >= k for c, k in enumerate(needs)):
            return True
    return False


def solve(n, links, needs, allowed=lambda colours, sizes, action: True):
    """Optimal expected orbs from n white, unlinked sockets (policy iteration over every reachable state)."""
    colour_table = {c: float(p) for c, p in chromatic(n).items()}
    fuse_table = {z: float(p) for z, p in fusing(n).items()}
    start = ((0,) * n, (1,) * n)
    index, states, rows = {start: 0}, [start], []
    i = 0
    while i < len(states):
        colours, sizes = states[i]
        row = []
        if goal(colours, sizes, links, needs):
            rows.append(row)
            i += 1
            continue
        offers = []
        if len(sizes) > 1:  # Orb of Fusing is refused when every socket is linked
            offers.append(("fuse", {(colours, s): p for s, p in fuse_table.items()}))
        other = colour_table.get(colours, 0.0)  # a Chromatic Orb never returns the colours the item already has
        offers.append(("chromatic", {(c, sizes): p / (1 - other) for c, p in colour_table.items() if c != colours}))
        for action, dist in offers:
            if not allowed(colours, sizes, action):
                continue
            edges = []
            for state, p in dist.items():
                if state not in index:
                    index[state] = len(states)
                    states.append(state)
                edges.append((index[state], p))
            row.append((action, edges))
        rows.append(row)
        i += 1
    size = len(states)
    done = np.array([not row for row in rows])
    offer_state, offer_edges = [], []  # one entry per (state, action): its state and its (target, probability) edges
    for s, row in enumerate(rows):
        for _, edges in row:
            offer_state.append(s)
            offer_edges.append(edges)
    offer_state = np.array(offer_state)
    counts = np.array([len(e) for e in offer_edges])
    edge_offer = np.repeat(np.arange(len(offer_edges)), counts)
    edge_target = np.array([t for e in offer_edges for t, _ in e])
    edge_p = np.array([p for e in offer_edges for _, p in e])
    first = np.searchsorted(offer_state, np.arange(size))  # the first offer of every state that has any
    live = ~done
    chosen = first.copy()  # start with the first action offered everywhere
    value = np.zeros(size)
    for _ in range(200):  # policy iteration; value iteration is the fixed point it reaches
        a = np.eye(size)
        picked = np.zeros(len(offer_edges), bool)
        picked[chosen[live]] = True
        keep = picked[edge_offer]
        np.add.at(a, (offer_state[edge_offer[keep]], edge_target[keep]), -edge_p[keep])
        b = np.where(live, 1.0, 0.0)
        value = np.linalg.solve(a, b)
        q = 1.0 + np.add.reduceat(edge_p * value[edge_target], np.concatenate([[0], np.cumsum(counts)[:-1]]))
        best = chosen.copy()
        for s in np.flatnonzero(live):
            lo = first[s]
            hi = lo + len(rows[s])
            k = lo + int(np.argmin(q[lo:hi]))
            if q[k] < q[chosen[s]] - 1e-9:
                best[s] = k
        if (best == chosen).all():
            break
        chosen = best
    return float(value[0]), size


@pytest.fixture(scope="module")
def three_linked_red_green_blue():
    return {
        "optimal": solve(4, 3, (1, 1, 1)),
        # links first, then colours: Fusing until a group of three exists, Chromatic Orbs after
        "chain": solve(4, 3, (1, 1, 1), lambda colours, sizes, action: (action == "chromatic") == (max(sizes) >= 3)),
    }


def test_the_dense_graph_is_the_2048_states_of_adr_0045(three_linked_red_green_blue):
    assert three_linked_red_green_blue["optimal"][1] == 4**4 * 2**3


def test_optimal_policy_for_three_linked_red_green_blue_costs_44_6(three_linked_red_green_blue):
    assert three_linked_red_green_blue["optimal"][0] == pytest.approx(44.6, abs=0.05)


def test_links_then_colours_costs_103_0_at_equal_prices(three_linked_red_green_blue):
    assert three_linked_red_green_blue["chain"][0] == pytest.approx(103.0, abs=0.05)


def test_the_two_agree_when_the_group_is_the_whole_item():
    optimal, _ = solve(4, 4, (1, 1, 1))
    chain, _ = solve(4, 4, (1, 1, 1), lambda colours, sizes, action: (action == "chromatic") == (max(sizes) >= 4))
    assert optimal == pytest.approx(chain, rel=1e-9)


def test_the_kernels_sum_to_one_and_all_linked_is_the_fusing_figure_of_adr_0047():
    assert sum(chromatic(4).values()) == 1
    assert sum(fusing(4).values()) == 1
    assert float(fusing(2)[(2,)]) == pytest.approx(0.661, abs=0.0005)
    assert float(fusing(6)[(6,)]) == pytest.approx(0.0010, abs=0.00005)
