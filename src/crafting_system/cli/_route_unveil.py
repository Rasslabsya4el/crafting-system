"""The unveil and its pick as one step of the route page (#1625 point 1).

The planner models an unveil as two actions (ADR-0026): the unveil draws the offer (a chance node) and a pick takes one of its mods (a choice
node, free, the only action an item holding an offer has). A player does both at once: he opens the window, reads the up to three mods and
clicks one. Drawn as the planner holds them, R24's page had an "Unveil" step and a "Pick 1" and a "Pick 3" step for that one action.

`joined_picks` makes the chain the page draws: each state whose every outcome is an item holding an offer moves straight to where the picks
of those items lead, its cost the unveil's plus the mean of the picks' (each a token cost, `FREE_ACTION_SHARE`), and the items holding an
offer leave the chain. The offers and the pick made on each are kept for the step's lines (`Picked`). The chances are those of the plan: the
joined kernel is the product of the two, exactly, in integer weights. A chain where an item holding an offer is reached any other way is
left as it is.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from crafting_system.solver import Action
from crafting_system.solver._packed import BIG_TOTAL

from ._route_flow import Chain, Kernels


@dataclass(frozen=True)
class Picked[S]:
    """One offer an unveil draws: the item holding it, its chance among the unveil's outcomes and the pick the plan makes on it."""

    offered: S
    chance: float
    pick: Action[S]


def _weights(table: Kernels, k: int) -> list[int]:
    lo, hi = int(table.k_ptr[k]), int(table.k_ptr[k + 1])
    if k in table.k_big:
        return list(table.k_big[k])
    if table.k_wt is None:  # a chain of blocks keeps no integer weights: the chances stand for them
        return [Fraction(float(p)).limit_denominator(1 << 40) for p in table.k_prob[lo:hi]]  # type: ignore[misc]
    return [int(w) for w in table.k_wt[lo:hi]]


def joined_picks[S](chain: Chain[S], holds_offer: Callable[[S], bool]) -> tuple[Chain[S], dict[S, tuple[Picked[S], ...]]]:
    """`chain` with each unveil and its pick joined into one move, and, for each state so joined, its offers and their picks."""
    m = chain.m
    if not m:
        return chain, {}
    offer = np.fromiter((bool(holds_offer(state)) for state in chain.states), dtype=bool, count=m)
    if not offer.any():
        return chain, {}
    table = chain.kernels
    has = chain.kernel >= 0
    succ_offer = np.concatenate((offer, np.zeros(len(chain.goals), dtype=bool)))[table.k_succ]  # per edge of each kernel: to an offer
    sizes = table.kernel_sizes()
    kernel_of = np.repeat(np.arange(len(sizes)), sizes)
    any_offer = np.zeros(len(sizes), dtype=bool)
    np.logical_or.at(any_offer, kernel_of, succ_offer)
    all_offer = np.ones(len(sizes), dtype=bool)
    np.logical_and.at(all_offer, kernel_of, succ_offer)
    all_offer &= sizes > 0
    if (any_offer & ~all_offer).any():
        return chain, {}  # an item holding an offer reached otherwise than by the unveil alone
    unveil = has & all_offer[np.where(has, chain.kernel, 0)] & ~offer
    if offer[0] or not unveil.any() or (offer & ~has).any():
        return chain, {}  # the start holds an offer, no unveil, or an item holding an offer has no pick planned
    kept = np.flatnonzero(~offer)
    remap = np.full(m + len(chain.goals), -1, dtype=np.int64)
    remap[kept] = np.arange(len(kept))
    remap[m:] = len(kept) + np.arange(len(chain.goals))
    # the kernels no unveil uses, their states renumbered
    keep_k = ~all_offer
    edges = np.repeat(keep_k, sizes)
    new_id = np.full(len(sizes), -1, dtype=np.int64)
    new_id[keep_k] = np.arange(int(keep_k.sum()))
    k_succ = [remap[table.k_succ[edges]]]
    k_prob = [table.k_prob[edges]]
    k_wt = None if table.k_wt is None else [table.k_wt[edges]]
    k_ptr = list(np.concatenate(([0], np.cumsum(sizes[keep_k]))).astype(np.int64))
    k_big = {int(new_id[k]): weights for k, weights in table.k_big.items() if keep_k[k]}
    cost = chain.cost.copy()
    picks: dict[S, tuple[Picked[S], ...]] = {}
    joined: dict[int, int] = {}  # old kernel of an unveil -> its joined kernel
    kernel = np.where(has, new_id[np.where(has, chain.kernel, 0)], -1)
    for i in np.flatnonzero(unveil).tolist():
        k = int(chain.kernel[i])
        lo, hi = int(table.k_ptr[k]), int(table.k_ptr[k + 1])
        offered = table.k_succ[lo:hi].tolist()
        weights = _weights(table, k)
        total = sum(weights)
        shares = [Fraction(w) / total for w in weights]
        cost[i] = chain.cost[i] + math.fsum(float(share) * chain.cost[o] for share, o in zip(shares, offered, strict=True))
        picks[chain.states[i]] = tuple(Picked(chain.states[o], float(share), chain.action_of(o)) for share, o in zip(shares, offered, strict=True))
        if k not in joined:
            composed: dict[int, Fraction] = {}
            for share, o in zip(shares, offered, strict=True):
                inner = int(chain.kernel[o])
                ilo, ihi = int(table.k_ptr[inner]), int(table.k_ptr[inner + 1])
                inner_w = _weights(table, inner)
                inner_total = sum(inner_w)
                for target, w in zip(table.k_succ[ilo:ihi].tolist(), inner_w, strict=True):
                    composed[int(remap[target])] = composed.get(int(remap[target]), Fraction(0)) + share * Fraction(w) / inner_total
            scale = math.lcm(*(share.denominator for share in composed.values()))
            ints = [int(share * scale) for share in composed.values()]
            whole = sum(ints)
            joined[k] = len(k_ptr) - 1
            k_succ.append(np.array(list(composed), dtype=np.int64))
            k_prob.append(np.array([w / whole for w in ints], dtype=float))
            if k_wt is not None:
                if whole >= BIG_TOTAL:
                    k_big[joined[k]] = tuple(ints)
                    k_wt.append(np.zeros(len(ints), dtype=np.int64))
                else:
                    k_wt.append(np.array(ints, dtype=np.int64))
            k_ptr.append(k_ptr[-1] + len(ints))
        kernel[i] = joined[k]
    kernels = Kernels(
        np.array(k_ptr, dtype=np.int64), np.concatenate(k_succ), None if k_wt is None else np.concatenate(k_wt), np.concatenate(k_prob), k_big
    )
    states = [chain.states[i] for i in kept.tolist()]
    action_of = chain.action_of
    return (
        Chain(states, chain.goals, chain.key[kept], chain.keys, cost[kept], kernel[kept], kernels, lambda i: action_of(int(kept[i]))),
        picks,
    )
