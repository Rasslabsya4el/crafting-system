"""Exact state classes of a plan's graph (ticket #312): how many of its states are really different?

    python research/312/exact_classes.py TARGET.yaml [--offers all|twins|start|FILE.json] [--seconds S]
        [--max-rss-mb M] [--max-states N] [--out DIR] [--verify-keys N] [--no-restart]

Walks the exact graph of the plan (the same abstraction, offers and prices as `make_plan`), keeps it as numpy arrays
(one kernel per distinct `Abstraction.kernel_key`, so 530 million edges of R04 are a few hundred thousand kernels),
and runs a partition refinement on it. Two states are in one CLASS when they have the same goal status and the same
set of (cost, successor distribution over classes) pairs: this is lumpability / bisimulation with costs, the
coarsest partition for which the optimal value (and the optimal policy up to the labels) is a function of the class.
Merging a class changes no answer: the mean, the odds, the p50 and the p90 of every policy are the same.

Two partitions are computed:

* `values`: the action set of a state is the set of (cost, distribution over classes) pairs, the dearer of two actions
  with one distribution dropped (never chosen). Labels do not matter: exact for every value and every metric.
* `labels`: the action set is the set of (label, cost, distribution) triples: the policy keeps its labels per class.

Never run on a PC for a real route: the walk is hours of CPU. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import gc
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from crafting_system.abstraction import Abstraction, Goal, integer_weights
from crafting_system.actions import BLOCKING, ActionError
from crafting_system.cli._bound_prune import merge_twins, starting_offers
from crafting_system.cli._offers import RESTART, BuyStartItem, Offer, PricedOffer, offers_for, price_offers, usable_actions
from crafting_system.cli._plan import resolve_start_price
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
BIG = 1 << 62


def rss_mb() -> float:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:  # Windows: only for the quick local tests
        return 0.0


def say(began: float, text: str) -> None:
    print(f"[{time.perf_counter() - began:8.1f}s rss {rss_mb():6,.0f} MB] {text}", flush=True)


# ---- the model: the same offers, abstraction and start as `make_plan` ---------------------------------------------


def build_model(target_path: Path, offers_mode: str, with_restart: bool = True):
    data = load_game_data()
    target = load_target(target_path, data)
    prices = load_price_file(PRICES)
    goal = Goal.from_target(target)
    chosen = offers_for(data, goal, target.base_id, target.start_item, target.actions)
    priced, dropped = price_offers(chosen.offers, prices)
    kept = usable_actions(data, target.start_item, [p.offer.action for p in priced])
    priced = tuple(p for p in priced if p.offer.action in kept)
    price_of_start = resolve_start_price(target, prices, None)
    if price_of_start.chaos > 0 and with_restart:
        bought = price_of_start.name or "start item"
        restart = Offer(RESTART, BuyStartItem(target.start_item), {bought: 1}, shares=False)
        priced = (*priced, PricedOffer(restart, price_of_start.chaos, ((bought, 1, price_of_start.chaos, price_of_start.source),)))
    enabled = [p.offer.action for p in priced if p.offer.action.reads(data).junk]
    holds_metamod = bool(target.start_item.metamods(data) & BLOCKING)
    abstraction = Abstraction(data, goal, target.base_id, target.item_level, enabled, metamods=holds_metamod)
    start = abstraction.compress(target.start_item)
    info = {"offers_total": len(priced), "dropped_unpriced": len(dropped)}
    if offers_mode in ("twins", "start"):
        merged = tuple(merge_twins(data, target.start_item, priced)[0])
        info["after_twins"] = len(merged)
        priced = merged
        if offers_mode == "start":
            priced = tuple(starting_offers(abstraction, start, merged, target.start_item, min_offers=40))
    elif offers_mode.startswith("plan:"):
        # the offers the exact production plan of ANOTHER target ends up using (e.g. R08 from the empty rare), plus the restart and the Alchemy
        from crafting_system.cli import make_plan

        began_plan = time.perf_counter()
        reference = make_plan(data, load_target(Path(offers_mode[5:]), data), prices, budget=None)
        used = {p.label for p in reference.pruned.used} if reference.pruned else {p.label for p in reference.offers}
        priced = tuple(p for p in priced if p.label in used | {RESTART, "Orb of Alchemy"})
        info["reference_plan_mean_remaining"] = reference.mean_remaining
        info["reference_plan_seconds"] = round(time.perf_counter() - began_plan, 1)
        info["reference_plan_offers_used"] = len(used)
    elif offers_mode not in ("all",):
        wanted = json.loads(Path(offers_mode).read_text(encoding="utf-8"))
        labels = set(wanted["labels"]) | {RESTART}
        priced = tuple(p for p in priced if p.label in labels)
        info["named"] = len(wanted["labels"])
    info["offers_used"] = len(priced)
    return data, target, goal, abstraction, start, priced, info


# ---- the walk ------------------------------------------------------------------------------------------------------


class Graph:
    """States by index, and per non-goal state its actions: (offer index, kernel id); a kernel is shared arrays."""

    def __init__(self) -> None:
        self.states: list = []
        self.index: dict = {}
        self.goal: bytearray = bytearray()
        self.expanded = 0
        self.act_ptr = [0]
        self.act_offer: list[int] = []
        self.act_cost: list[float] = []
        self.act_kernel: list[int] = []
        self.k_succ: list[np.ndarray] = []
        self.k_wt: list[np.ndarray] = []
        self.k_big: list[bool] = []
        self.by_key: dict = {}
        self.edges = 0  # transitions counted per (state, offer) as the plain walk counts them
        self.refused: Counter = Counter()

    def intern(self, state, is_goal: bool) -> int:
        found = self.index.get(state)
        if found is None:
            found = len(self.states)
            self.index[state] = found
            self.states.append(state)
            self.goal.append(1 if is_goal else 0)
        return found


def walk(abstraction, start, priced, began, seconds, max_rss, max_states, verify_keys):
    g = Graph()
    g.intern(start, abstraction.is_goal(start))
    start_index = 0
    restart_kernel = None
    last = time.perf_counter()
    reason = "finished"
    verify_pool: list = []
    i = 0
    while i < len(g.states):
        state = g.states[i]
        if not g.goal[i]:
            for oi, p in enumerate(priced):
                action = p.offer.action
                if isinstance(action, BuyStartItem):
                    if state == start:
                        continue
                    if restart_kernel is None:
                        restart_kernel = len(g.k_succ)
                        g.k_succ.append(np.array([start_index], dtype=np.int32))
                        g.k_wt.append(np.array([1], dtype=np.int64))
                        g.k_big.append(False)
                    kid = restart_kernel
                else:
                    try:
                        key = abstraction.kernel_key(state, action)
                    except ActionError:
                        g.refused[p.label] += 1
                        continue
                    kid = g.by_key.get(key)
                    if kid is None:
                        try:
                            weights = integer_weights(abstraction.kernel(state, action))
                        except ActionError:
                            g.refused[p.label] += 1
                            continue
                        succ = np.fromiter((g.intern(s, abstraction.is_goal(s)) for s in weights), dtype=np.int32, count=len(weights))
                        raw = list(weights.values())
                        big = sum(raw) >= BIG
                        wt = np.array(raw, dtype=object if big else np.int64)
                        kid = len(g.k_succ)
                        g.k_succ.append(succ)
                        g.k_wt.append(wt)
                        g.k_big.append(big)
                        g.by_key[key] = kid
                        if verify_keys and len(verify_pool) < 4 * verify_keys and hash(key) % 17 == 0:
                            verify_pool.append((state, action, kid))
                g.act_offer.append(oi)
                g.act_cost.append(p.cost)
                g.act_kernel.append(kid)
                g.edges += len(g.k_succ[kid])
        g.act_ptr.append(len(g.act_offer))
        abstraction._prepared_by.clear()  # the per-state cache of the abstraction is what fills the memory; each pair is asked once
        i += 1
        g.expanded = i
        now = time.perf_counter()
        if now - last >= 30:
            last = now
            say(began, f"found {len(g.states):,} expanded {i:,} kernels {len(g.k_succ):,} edges {g.edges:,}")
        if len(g.states) >= max_states:
            reason = "state limit"
            break
        if rss_mb() >= max_rss:
            reason = "memory limit"
            break
        if now - began >= seconds:
            reason = "time limit"
            break
    # the states found and not expanded (a cut walk) have no actions: pad the pointer
    while len(g.act_ptr) <= len(g.states):
        g.act_ptr.append(len(g.act_offer))
    # check that equal keys really gave equal kernels on a sample
    checked = bad = 0
    for state, action, kid in verify_pool[: 4 * verify_keys]:
        weights = integer_weights(abstraction.kernel(state, action))
        stored = dict(zip((g.states[j] for j in g.k_succ[kid].tolist()), (int(w) for w in g.k_wt[kid].tolist())))
        checked += 1
        if {s: int(w) for s, w in weights.items()} != stored:
            bad += 1
    return g, reason, {"key_checks": checked, "key_mismatches": bad}


# ---- the refinement ------------------------------------------------------------------------------------------------


LAST: dict = {}  # refine's side result: {'converged': bool}


def refine(g: Graph, priced, began, label_mode: bool, max_rounds: int = 500, cut_frontier: bool = True, initial=None, deadline: float = float('inf')):
    """Coarsest partition: same goal status, same set of (cost, distribution over blocks) pairs.

    In a cut walk the states that were found and not expanded stay singleton classes (nothing is known about them);
    the count of classes is then an upper bound of the classes of the whole graph.
    """
    n = len(g.states)
    expanded = g.expanded
    ptr = np.array(g.act_ptr, dtype=np.int64)
    act_offer = np.array(g.act_offer, dtype=np.int32)
    act_kernel = np.array(g.act_kernel, dtype=np.int32)
    costs_a = np.array(g.act_cost, dtype=np.float64)
    labels = [p.label for p in priced]
    goal = np.frombuffer(bytes(g.goal), dtype=np.uint8)
    # block 0 = every goal state; non-goal expanded states in block 1; unexpanded non-goal states: own blocks
    blk = np.zeros(n, dtype=np.int64)
    blk[goal == 0] = 1
    if initial is not None:  # a candidate partition (goal states are still one block): non-goal ids start at 2
        blk[goal == 0] = np.asarray(initial)[goal == 0] + 2
    if expanded < n and cut_frontier:
        extra = np.arange(expanded, n)
        extra = extra[goal[expanded:] == 0]
        blk[extra] = 2 + np.arange(len(extra))
    LAST["converged"] = True
    count = len(np.unique(blk))
    sizes = np.array([len(s) for s in g.k_succ], dtype=np.int64)
    rounds = 0
    history = [count]
    while rounds < max_rounds:
        rounds += 1
        # distribution of every kernel over the current blocks
        dist_id = np.empty(len(g.k_succ), dtype=np.int64)
        seen: dict = {}
        for k, (succ, wt) in enumerate(zip(g.k_succ, g.k_wt)):
            b = blk[succ]
            if len(b) == 1:
                key = (int(b[0]),)
            else:
                order = np.argsort(b, kind="stable")
                bs = b[order]
                ws = wt[order]
                cut = np.flatnonzero(np.concatenate(([True], bs[1:] != bs[:-1])))
                if len(cut) == len(bs):
                    sums = ws
                    ub = bs
                else:
                    ub = bs[cut]
                    sums = np.add.reduceat(ws, cut) if ws.dtype != object else np.array([sum(ws[a:z]) for a, z in zip(cut, [*cut[1:], len(ws)])], dtype=object)
                if len(sums) == 1:
                    key = (int(ub[0]),)
                else:
                    div = math.gcd(*[int(x) for x in sums]) if sums.dtype == object else int(np.gcd.reduce(sums))
                    key = (ub.tobytes(), (sums // div).tobytes() if sums.dtype != object else tuple(int(x) // div for x in sums))
            found = seen.get(key)
            if found is None:
                found = len(seen)
                seen[key] = found
            dist_id[k] = found
        # the signature of every expanded non-goal state
        new_ids: dict = {}
        new_blk = blk.copy()
        for s in range(expanded):
            if goal[s]:
                continue
            a, z = ptr[s], ptr[s + 1]
            if label_mode:
                acts = sorted({(labels[act_offer[t]], float(costs_a[t]), int(dist_id[act_kernel[t]])) for t in range(a, z)})
                sig = (int(blk[s]), tuple(acts))
            else:
                best: dict[int, float] = {}
                for t in range(a, z):
                    d = int(dist_id[act_kernel[t]])
                    c = float(costs_a[t])
                    if d not in best or c < best[d]:
                        best[d] = c
                sig = (int(blk[s]), tuple(sorted(best.items())))
            found = new_ids.get(sig)
            if found is None:
                found = len(new_ids) + 2
                new_ids[sig] = found
            new_blk[s] = found
        # unexpanded non-goal states keep distinct ids above the new ones
        if expanded < n and cut_frontier:
            extra = np.arange(expanded, n)
            extra = extra[goal[expanded:] == 0]
            new_blk[extra] = len(new_ids) + 2 + np.arange(len(extra))
        new_count = len(np.unique(new_blk))
        say(began, f"{'labels' if label_mode else 'values'} round {rounds}: {new_count:,} classes ({len(seen):,} distinct distributions)")
        history.append(new_count)
        blk = new_blk
        if new_count == count:
            LAST["converged"] = True
            break
        count = new_count
        if time.perf_counter() > deadline:
            LAST["converged"] = False
            break
    else:
        LAST["converged"] = False
    return blk, history


# ---- a check on small graphs: the optimal value is constant on a class, and the quotient has the same value -------


def check_values(g: Graph, priced, blk: np.ndarray, start_index: int = 0) -> dict:
    """Solve the whole graph and its quotient with the product solver; the value must be a function of the class."""
    from crafting_system.solver import Action, Outcome, TabularModel, solve

    def actions_of(s: int) -> list:
        found = []
        for t in range(g.act_ptr[s], g.act_ptr[s + 1]):
            p = priced[g.act_offer[t]]
            k = g.act_kernel[t]
            found.append(Action(p.label, p.cost, tuple(Outcome(int(a), int(w)) for a, w in zip(g.k_succ[k], g.k_wt[k]))))
        return found

    goals = [s for s in range(g.expanded) if g.goal[s]]
    table = {s: actions_of(s) for s in range(g.expanded) if not g.goal[s]}
    whole = solve(TabularModel(goals, table), [start_index])
    values = {s: v for s, v in whole.values.items()}
    by_class: dict[int, list[float]] = defaultdict(list)
    for s, v in values.items():
        by_class[int(blk[s])].append(v)
    worst = max((max(v) - min(v)) / max(1.0, abs(max(v))) for v in by_class.values())
    # the quotient: one representative per class, its actions mapped to classes
    rep: dict[int, int] = {}
    for s in range(g.expanded):
        rep.setdefault(int(blk[s]), s)
    qgoals = [b for b, s in rep.items() if g.goal[s]]
    qtable = {}
    for b, s in rep.items():
        if g.goal[s]:
            continue
        acts = []
        for a in actions_of(s):
            merged: dict[int, int] = defaultdict(int)
            for o in a.outcomes:
                merged[int(blk[o.state])] += o.weight
            acts.append(Action(a.label, a.cost, tuple(Outcome(b2, w) for b2, w in merged.items())))
        qtable[b] = acts
    quotient = solve(TabularModel(qgoals, qtable), [int(blk[start_index])])
    return {
        "states_solved": len(values), "classes_with_values": len(by_class), "worst_relative_spread_inside_a_class": worst,
        "start_value_whole": whole.values[start_index], "start_value_quotient": quotient.values[int(blk[start_index])],
    }


# ---- what makes members of one class differ -----------------------------------------------------------------------


def views(state):
    """The parts of a state, each as a hashable view; `explain` counts how often a view varies inside a class."""
    slots = state.slots
    return {
        "flags.rarity": state.flags.rarity,
        "flags.corrupted": state.flags.corrupted,
        "flags.influences": state.flags.influences,
        "fractured (ids and contributions)": state.fractured,
        "fractured (ids only)": tuple(f.mod_id for f in state.fractured),
        "status": state.status,
        "slots (whole multiset)": slots,
        "slots: how many per side": (sum(s.side.value == "prefix" for s in slots), sum(s.side.value == "suffix" for s in slots)),
        "slots: kinds (side, kind, crafted)": tuple(sorted((s.side.value, s.kind, s.crafted) for s in slots)),
        "slots: contributions (side, contribution)": tuple(sorted((s.side.value, tuple(int(c) for c in s.contribution)) for s in slots)),
        "slots: crafted ones": tuple(sorted((s.side.value, s.kind) for s in slots if s.crafted)),
        "slots: ordinary ones (side, kind, contribution)": tuple(
            sorted((s.side.value, s.kind, tuple(int(c) for c in s.contribution)) for s in slots if not s.crafted)
        ),
    }


def explain(g: Graph, blk: np.ndarray, only_expanded: bool = True) -> list[dict]:
    members: dict[int, list[int]] = defaultdict(list)
    limit = g.expanded if only_expanded else len(g.states)
    for s in range(limit):
        members[int(blk[s])].append(s)
    multi = {b: m for b, m in members.items() if len(m) > 1}
    names = list(views(g.states[0]))
    tally = {name: {"classes_varying": 0, "states_in_those_classes": 0, "extra_values": 0} for name in names}
    for b, m in multi.items():
        values = {name: set() for name in names}
        for s in m:
            for name, v in views(g.states[s]).items():
                values[name].add(v)
        for name in names:
            if len(values[name]) > 1:
                tally[name]["classes_varying"] += 1
                tally[name]["states_in_those_classes"] += len(m)
                tally[name]["extra_values"] += len(values[name]) - 1
    return [{"view": name, **tally[name]} for name in names]


def examples(g: Graph, blk: np.ndarray, how_many: int = 5) -> list[dict]:
    """The biggest classes, with a few members shown as text."""
    members: dict[int, list[int]] = defaultdict(list)
    for s in range(g.expanded):
        members[int(blk[s])].append(s)
    biggest = sorted(members.values(), key=len, reverse=True)[:how_many]
    out = []
    for m in biggest:
        out.append({"size": len(m), "goal": bool(g.goal[m[0]]), "sample": [describe(g.states[s]) for s in m[:3]]})
    return out


def describe(state) -> str:
    fractured = [f"{f.mod_id}{[int(c) for c in f.contribution]}" for f in state.fractured]
    slots = [f"{s.side.value[0]}:{s.kind or '-'}{'*' if s.crafted else ''}{[int(c) for c in s.contribution]}" for s in state.slots]
    return f"{state.flags.rarity.value} fractured={fractured} status={[int(x) for x in state.status]} slots={slots}"


def shape_table(g: Graph, blk: np.ndarray) -> list[dict]:
    """States and classes by (rarity, fractured ids): where the states sit."""
    states_by: dict = defaultdict(int)
    classes_by: dict = defaultdict(set)
    for s in range(g.expanded):
        st = g.states[s]
        key = (st.flags.rarity.value, tuple(f.mod_id for f in st.fractured), len(st.slots))
        states_by[key] += 1
        classes_by[key].add(int(blk[s]))
    rows = [{"rarity": k[0], "fractured": list(k[1]), "slots": k[2], "states": states_by[k], "classes": len(classes_by[k])} for k in states_by]
    rows.sort(key=lambda r: -r["states"])
    return rows[:40]


# ---- which fields can be dropped from the state exactly -------------------------------------------------------------


def projection_keys():
    def crafted(st):
        return tuple(sorted((x.side.value, x.kind) for x in st.slots if x.crafted))

    def sides(st):
        return (sum(x.side.value == "prefix" for x in st.slots), sum(x.side.value == "suffix" for x in st.slots))

    return {
        "everything (the state as it is)": lambda st: st,
        "drop all slots": lambda st: (st.flags, st.fractured, st.status),
        "slots -> only the crafted ones": lambda st: (st.flags, st.fractured, st.status, crafted(st)),
        "slots -> how many per side (+ crafted ones)": lambda st: (st.flags, st.fractured, st.status, sides(st), crafted(st)),
        "slots -> (side, contribution): kinds forgotten": lambda st: (st.flags, st.fractured, st.status, tuple(sorted((x.side.value, tuple(int(c) for c in x.contribution), x.crafted) for x in st.slots))),
        "slots -> (side, kind): contributions forgotten": lambda st: (st.flags, st.fractured, st.status, tuple(sorted((x.side.value, x.kind, x.crafted) for x in st.slots))),
        "drop the status of the leaves": lambda st: (st.flags, st.fractured, st.slots),
        "fractured -> ids only": lambda st: (st.flags, tuple(f.mod_id for f in st.fractured), st.status, st.slots),
        "fractured -> dropped": lambda st: (st.flags, st.status, st.slots),
        "drop the flags": lambda st: (st.fractured, st.status, st.slots),
    }


def projection_tests(g: Graph, priced, began, deadline: float) -> list[dict]:
    """For each candidate way of forgetting a field: the number of classes it makes and whether it is already an exact merge.

    A candidate partition is an exact merge when it is stable: one refinement round leaves it as it is. Otherwise one
    round already splits it into more classes (a lower bound of the classes it would need to be exact).
    """
    rows = []
    for name, view in projection_keys().items():
        if time.perf_counter() > deadline:
            rows.append({"candidate": name, "skipped": "out of time"})
            continue
        ids: dict = {}
        init = np.empty(len(g.states), dtype=np.int64)
        for i, st in enumerate(g.states[: g.expanded]):
            init[i] = ids.setdefault(view(st), len(ids))
        goal = np.frombuffer(bytes(g.goal), dtype=np.uint8)
        before = len(np.unique(init[goal == 0]))
        blk, history = refine(g, priced, began, False, max_rounds=1, initial=init)
        rows.append({"candidate": name, "classes_before_a_round": before, "classes_after_one_round": history[-1] - 1, "exact_merge": history[-1] == history[0]})
        say(began, f"candidate {rows[-1]}")
    return rows


# ---- the stages after the classes -----------------------------------------------------------------------------------


def later(g: Graph, priced, blk, args, result: dict, began: float, out_dir, stem: str) -> None:
    """Quotient and its exact solve, rails, lumping of rare outcomes; each result is saved as soon as it is known."""
    import later_stages as L

    def save() -> None:
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{stem}.partial.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    restart_cost = next((p.cost for p in priced if p.label == RESTART), 0.0)
    q, start = L.quotient(g, blk)
    goal_class = next((c for c in range(q.expanded) if q.goal[c]), 0)
    if out_dir is not None:  # the quotient is small: keep it, so that the cut analyses (prune_analysis.py) need no new walk
        import pickle

        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / f"{stem}.quotient.pkl", "wb") as handle:
            plain = {"n": q.expanded, "goal": bytes(q.goal), "act_ptr": q.act_ptr, "act_offer": q.act_offer, "act_cost": q.act_cost, "act_kernel": q.act_kernel, "k_succ": q.k_succ, "k_wt": q.k_wt}
            sizes = np.bincount(np.unique(blk[: g.expanded], return_inverse=True)[1])
            raw = {"states": g.expanded, "actions": len(g.act_offer), "kernels": len(g.k_succ), "edges": g.edges}
            pickle.dump({"graph": plain, "start": start, "goal_class": goal_class, "restart_cost": restart_cost, "labels": [p.label for p in priced], "class_sizes": sizes, "raw": raw}, handle)
    result["quotient"] = {"classes": q.expanded, "actions": len(q.act_offer), "kernels": len(q.k_succ), "edges": q.edges}
    if args.stop_after_quotient:
        say(began, f"quotient {result['quotient']}")
        return
    result["raw_reach"] = {
        "no_change": L.raw_reach(g, 0)["reachable_states"],
        **{f"tau_{tau}": L.raw_reach(g, 0, tau=float(tau))["reachable_states"] for tau in args.taus.split(",") if tau},
        **{f"rail_{c}": L.raw_reach(g, 0, ceiling=float(c))["reachable_states"] for c in args.rails.split(",") if c},
    }
    say(began, f"quotient {result['quotient']}; raw reach {result['raw_reach']}")
    save()

    def value_of(graph, st, label):
        if graph.expanded > args.solve_max_classes:
            return {"value": None, "why": f"{graph.expanded} classes, over the solve limit {args.solve_max_classes}"}
        t0 = time.perf_counter()
        solution, why = L.solve_timed(graph, priced, st, args.solve_seconds)
        out = {"seconds": round(time.perf_counter() - t0, 1), "why": why}
        if solution is not None:
            out["value"] = solution.values[st]
            out["policy_states"] = len(solution.policy)
            out["biggest_uses_in_a_row_in_the_policy"] = L.policy_uses(graph, priced, solution)[:4]
            out["expected_uses_per_run_by_action"] = L.policy_total_uses(solution, st)
        else:
            out["value"] = None
        say(began, f"solve {label}: {out.get('value')} ({why})")
        return out

    result["exact"] = value_of(q, start, "exact quotient")
    save()
    exact = result["exact"].get("value")

    def shrunk(graph, st):
        """The part reachable from the start, then merged again by classes: (classes, graph, start)."""
        keep = L.reachable_mask(graph, st)
        sub, st2 = L.subgraph(graph, keep, st)
        b2, _ = refine(sub, priced, began, label_mode=False)
        q2, s2 = L.quotient(sub, b2, st2)
        return int(keep.sum()), q2, s2

    result["rails"] = {}
    for c in [float(x) for x in args.rails.split(",") if x]:
        r, dropped = L.rail(q, c)
        reach, rq, rs = shrunk(r, start)
        row = {"ceiling": c, "actions_cut": dropped, "classes_reachable": reach, "classes_after_merge": rq.expanded}
        row.update(value_of(rq, rs, f"rail {c:g}"))
        if exact and row.get("value") is not None:
            row["relative_change"] = row["value"] / exact - 1
        result["rails"][f"{c:g}"] = row
        save()
    result["lumping"] = {}
    for tau in [float(x) for x in args.taus.split(",") if x]:
        row = {}
        for mode in ("pess", "opt"):
            lg, info = L.lump(q, tau, mode, start, goal_class, restart_cost)
            reach, lq, ls = shrunk(lg, start)
            part = {**info, "classes_reachable": reach, "classes_after_merge": lq.expanded}
            part.update(value_of(lq, ls, f"lump {tau:g} {mode}"))
            if exact and part.get("value") is not None:
                part["relative_to_exact"] = part["value"] / exact - 1
            row[mode] = part
        result["lumping"][f"{tau:g}"] = row
        save()
    result["projections"] = projection_tests(g, priced, began, began + args.projection_deadline)
    save()
    if args.reference_plan:
        from crafting_system.cli import make_plan

        t0 = time.perf_counter()
        plan = make_plan(g_data_holder["data"], g_data_holder["target"], load_price_file(PRICES), budget=None)
        result["reference_plan"] = {"mean_remaining": plan.mean_remaining, "seconds": round(time.perf_counter() - t0, 1)}
        save()


g_data_holder: dict = {}


# ---- main ---------------------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--offers", default="twins", help="all, twins, start (restart, crafts, best rerolls), or a JSON file {labels: [...]}")
    parser.add_argument("--seconds", type=float, default=2400)
    parser.add_argument("--max-rss-mb", type=float, default=13_000)
    parser.add_argument("--max-states", type=int, default=5_000_000)
    parser.add_argument("--verify-keys", type=int, default=30)
    parser.add_argument("--no-restart", action="store_true")
    parser.add_argument("--projection-deadline", type=float, default=3000, help="seconds from the start after which no more candidate projections are tested")
    parser.add_argument("--refine-seconds", type=float, default=1500)
    parser.add_argument("--no-labels", action="store_true", help="skip the label-aware partition (big graphs)")
    parser.add_argument("--taus", default="1e-3,1e-4,1e-5", help="chance thresholds below which outcomes are lumped")
    parser.add_argument("--rails", default="100000,10000,1000", help="ceilings on the expected uses of an action in a row")
    parser.add_argument("--solve-seconds", type=int, default=1200)
    parser.add_argument("--solve-max-classes", type=int, default=150_000)
    parser.add_argument("--reference-plan", action="store_true", help="also run the production exact plan of the target (small routes only)")
    parser.add_argument("--stop-after-quotient", action="store_true", help="big graphs: keep the quotient file and stop (the rails and the lumping run on the quotient by prune_analysis.py)")
    parser.add_argument("--check-values", action="store_true", help="small graphs only: solve the whole graph and the quotient and compare")
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()
    path = Path(args.target)
    data, target, goal, abstraction, start, priced, info = build_model(path, args.offers, not args.no_restart)
    g_data_holder.update(data=data, target=target)
    say(began, f"model built: {info}; offers: {', '.join(p.label for p in priced[:12])}{' ...' if len(priced) > 12 else ''}")
    g, reason, checks = walk(abstraction, start, priced, began, args.seconds, args.max_rss_mb, args.max_states, args.verify_keys)
    walked = time.perf_counter() - began
    say(began, f"walk {reason}: {len(g.states):,} states found, {g.expanded:,} expanded, {len(g.k_succ):,} kernels, {g.edges:,} edges; {checks}")
    gc.collect()
    result = {
        "target": path.name, "offers_mode": args.offers, **info, "walk_result": reason, "complete": reason == "finished",
        "states_found": len(g.states), "states_expanded": g.expanded, "goal_states": int(sum(g.goal)),
        "kernels": len(g.k_succ), "edges": g.edges, "refused": dict(g.refused), "walk_seconds": round(walked, 1), **checks,
        "walk_rss_mb": round(rss_mb()), "graph_edges_stored": int(sum(len(s) for s in g.k_succ)),
    }
    for mode in ("values",) if args.no_labels else ("values", "labels"):
        t0 = time.perf_counter()
        blk, history = refine(g, priced, began, label_mode=(mode == "labels"), deadline=time.perf_counter() + args.refine_seconds)
        result["converged_" + mode] = LAST["converged"]
        if not LAST["converged"]:
            result["complete"] = False  # the classes counted so far are a lower bound
        classes = len(np.unique(blk[: g.expanded]))
        nongoal = len(np.unique(blk[: g.expanded][np.frombuffer(bytes(g.goal[: g.expanded]), dtype=np.uint8) == 0]))
        result[mode] = {"classes_expanded_states": classes, "non_goal_classes": nongoal, "rounds": len(history) - 1, "history": history, "seconds": round(time.perf_counter() - t0, 1)}
        say(began, f"{mode}: {g.expanded:,} expanded states -> {classes:,} classes ({nongoal:,} non-goal)")
        if mode == "values" and args.check_values and result["complete"]:
            result["check_values"] = check_values(g, priced, blk)
            say(began, f"check: {result['check_values']}")
        if mode == "values":
            result["explain"] = explain(g, blk)
            result["biggest_classes"] = examples(g, blk)
            result["shapes"] = shape_table(g, blk)
            if result["complete"]:
                later(g, priced, blk, args, result, began, out_dir=Path(args.out) if args.out else None, stem=path.stem)
    result["total_seconds"] = round(time.perf_counter() - began, 1)
    result["peak_rss_mb"] = round(rss_mb())
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{path.stem}.{args.offers.replace('/', '_').replace(chr(92), '_').replace(':', '_')[:40]}.classes.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
