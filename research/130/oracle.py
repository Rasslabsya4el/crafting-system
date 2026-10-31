"""Oracles for the variants prototype (ticket #130).

A. 400 random min-max models: the value of the pessimistic model (controller picks an action, nature picks a variant of it,
   every time the state is visited) from `Graph.solve("upper")`, against brute force over every stationary policy and every
   stationary choice of variants; the optimistic model (variants as extra actions) against brute force over policies.
B. the certificate: `certify_upper` returns a checked supersolution `aV` whose value is above the brute-force value, within
   a factor 1 + 1e-9, and the identity T(aV) <= a T(V) - (a - 1) g of ADR-0023 holds for random V and a >= 1 (g the smallest cost).
C. the extremes: on blocks of the real bow pools, a random continuation value V over the blocks; the largest and the smallest
   backup over EVERY member of the block (all ways to put the n slots on distinct families) equal those of the lightest/heaviest members.
"""
import itertools, random
from coarse import *


def random_model(rng):
    n = rng.randint(2, 4)  # non-goal states 0..n-1, goal state n
    table = []
    for s in range(n):
        acts = []
        for a in range(rng.randint(1, 3)):
            variants = []
            for v in range(rng.randint(1, 3)):
                dst = list(range(n + 1))
                w = [rng.random() ** 2 for _ in dst]
                w[n] += 0.3  # every variant reaches the goal with some chance, so every policy is proper
                tot = sum(w)
                variants.append((round(rng.uniform(0.5, 3), 3), {d: x / tot for d, x in zip(dst, w)}))
            costs = {c for c, _ in variants}
            c = variants[0][0]
            variants = [(c, dist) for _, dist in variants]  # one cost per action: the same action costs the same in every variant
            acts.append((rng.random() < 0.85, variants))
        table.append(acts)
    for s in range(n):  # an optimistic model offers an action legal in some member; make sure each state has one legal-everywhere action
        if not any(l for l, _ in table[s]):
            table[s][0] = (True, table[s][0][1])
    return n + 1, [False] * n + [True], table


def policy_value(n, goal, table, policy, choice):
    """Cost of the stationary policy with the stationary variant choice, by a linear solve."""
    P = np.zeros((n, n))
    c = np.zeros(n)
    for s in range(n):
        if goal[s]:
            continue
        cost, dist = table[s][policy[s]][1][choice[s]]
        c[s] = cost
        for d, p in dist.items():
            P[s, d] += p
    A = np.eye(n) - P
    for s in range(n):
        if goal[s]:
            A[s] = 0
            A[s, s] = 1
    return np.linalg.solve(A, c)


def brute(n, goal, table, pessimistic):
    free = [s for s in range(n) if not goal[s]]
    best = np.full(n, np.inf)
    legal_actions = {s: [a for a in range(len(table[s])) if (table[s][a][0] or not pessimistic)] for s in free}
    for policy_t in itertools.product(*[legal_actions[s] for s in free]):
        policy = dict(zip(free, policy_t))
        if pessimistic:
            # nature: every stationary choice of variants; the value of the state is the largest over choices
            worst = np.full(n, -np.inf)
            for choice_t in itertools.product(*[range(len(table[s][policy[s]][1])) for s in free]):
                choice = dict(zip(free, choice_t))
                J = policy_value(n, goal, table, policy, choice)
                worst = np.maximum(worst, J)
            val = worst
        else:
            # optimistic: nature is the controller too, variants are extra actions: the best choice per state
            val = np.full(n, np.inf)
            for choice_t in itertools.product(*[range(len(table[s][policy[s]][1])) for s in free]):
                choice = dict(zip(free, choice_t))
                val = np.minimum(val, policy_value(n, goal, table, policy, choice))
        best = np.minimum(best, val)
    best[[s for s in range(n) if goal[s]]] = 0
    return best


def run_a_b(models=400, seed=130):
    rng = random.Random(seed)
    worst_up = worst_low = worst_cert = 0.0
    gaps = []
    bad_identity = 0
    for m in range(models):
        n, goal, table = random_model(rng)
        # the model has a pessimistic action everywhere (checked in random_model); optimistic offers all actions
        G = Graph.from_tables(n, goal, table)
        Vp = G.solve("upper", tol=1e-14)
        Vo = G.solve("lower", tol=1e-14)
        bp = brute(n, goal, table, True)
        bo = brute(n, goal, table, False)
        worst_up = max(worst_up, float(np.max(np.abs(Vp - bp) / np.maximum(bp, 1e-12))))
        worst_low = max(worst_low, float(np.max(np.abs(Vo - bo) / np.maximum(bo, 1e-12))))
        a, Va, res = G.certify_upper(Vp)
        assert a >= 1.0 and (Va >= bp * (1 - 1e-12)).all(), "certified V below the brute-force value"
        worst_cert = max(worst_cert, float(np.max(Va / np.maximum(bp, 1e-12)) - 1))
        # identity: T(aV) <= a T(V) - (a-1) g for a >= 1 and any positive V (the operator is the pessimistic backup)
        g = float(G.row_cost.min())
        for _ in range(5):
            V = np.abs(np.random.default_rng(rng.randint(0, 10**9)).normal(3, 2, n)) + 0.1
            V[goal] = 0
            aa = 1 + rng.random() * 3
            TaV, _ = G.backup_upper(aa * V)
            TV, _ = G.backup_upper(V)
            free = ~np.asarray(goal)
            if not (TaV[free] <= aa * TV[free] - (aa - 1) * g + 1e-9).all():
                bad_identity += 1
            ab = rng.random()  # and for a <= 1: T(aV) >= a T(V) + (1-a) g
            TbV, _ = G.backup_upper(ab * V)
            if not (TbV[free] >= ab * TV[free] + (1 - ab) * g - 1e-9).all():
                bad_identity += 1
    return dict(models=models, worst_pessimistic_rel=worst_up, worst_optimistic_rel=worst_low,
                worst_certified_over_value=worst_cert, identity_violations=bad_identity)


def all_members(L, pool_kinds, n):
    """Every count vector of the kinds of a pool for n slots on distinct families."""
    kinds = list(pool_kinds)
    caps = [L.info[k]["N"] for k in kinds]
    for h in itertools.product(*[range(c + 1) for c in caps]):
        if sum(h) == n:
            yield {k: x for k, x in zip(kinds, h) if x}


def run_c(trials=300, seed=7):
    rng = random.Random(seed)
    d, ab, L = make(float, True)
    junk = {side: [k for k, v in L.info.items() if v["side"] == side and all(sum(c) == 0 for c, _ in v["classes"])]
            for side in ("prefix", "suffix")}
    goals = [k for k, v in L.info.items() if any(sum(c) for c, _ in v["classes"])]
    worst = 0.0
    checked = 0
    for _ in range(trials):
        # a random pooling: one or two pools per side from random junk kinds
        groups = []
        for side in ("prefix", "suffix"):
            ks = junk[side][:]
            rng.shuffle(ks)
            cut = rng.randint(1, len(ks))
            groups.append(ks[:cut])
            if rng.random() < 0.5 and ks[cut:]:
                groups.append(ks[cut:])
        C = Coarse(L, groups)
        # a random block: rarity rare (or magic for augment), some pooled slots, maybe goal slots
        rarity = rng.choice([MAGIC, RARE])
        cap = CAPS[rarity]
        slots = []
        for name, (side, kinds) in C.pool_info.items():
            room = cap[side] - sum(1 for s in slots if s[0] == side)
            cnt = rng.randint(0, min(room, sum(L.info[k]["N"] for k in kinds)))
            slots += [(side, name, (0, 0, 0))] * cnt
        for gk in goals:
            v = L.info[gk]
            if rng.random() < 0.3 and sum(1 for s in slots if s[0] == v["side"]) < cap[v["side"]]:
                slots.append((v["side"], gk, v["classes"][0][0]))
        block = (rarity, tuple(sorted(slots)))
        if L.is_goal(block):
            continue
        name = "exalt" if rarity == RARE else rng.choice(["augment", "regal"])
        if rarity == RARE and name != "exalt":
            continue
        # all members of the block
        pools = [(nm, C.pool_info[nm]) for nm in C.pool_info]
        counts = Counter(k for _, k, _ in block[1])
        per_pool = [list(all_members(L, kinds, counts.get(nm, 0))) for nm, (side, kinds) in pools]
        rest = tuple(s for s in block[1] if s[1] not in C.pool_info)
        member_dists = []
        for combo in itertools.product(*per_pool):
            exact = list(rest)
            for (nm, (side, kinds)), fill in zip(pools, combo):
                for k, m in fill.items():
                    exact += [(side, k, (0, 0, 0))] * m
            k = L.kernel((rarity, tuple(sorted(exact))), name)
            if k is not None:
                member_dists.append(C.push(k))
        ext, legal_ext = C.variants(block, name)
        if not member_dists:
            assert not ext
            continue
        assert ext, "extremes say illegal but a member can take the action"
        allkeys = set().union(*[d.keys() for d in member_dists + ext])
        # legality: every member can <=> every extreme can
        assert (len(member_dists) == len(list(itertools.product(*per_pool)))) == legal_ext
        for _ in range(8):
            V = {k: rng.random() * 10 for k in allkeys}
            vals_all = [sum(p * V[k] for k, p in d.items()) for d in member_dists]
            vals_ext = [sum(p * V[k] for k, p in d.items()) for d in ext]
            worst = max(worst, abs(max(vals_all) - max(vals_ext)), abs(min(vals_all) - min(vals_ext)))
            checked += 1
    return dict(trials=trials, checks=checked, worst_difference=worst)


if __name__ == "__main__":
    print("A/B", run_a_b(), flush=True)
    print("C", run_c(), flush=True)
