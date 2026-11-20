"""t1363: the value of the lemma's lower model M' (keys of F valued z_ctx, z_X = min(raiser rows of X, c_b + z_Y over moves)),
by value iteration from the dump's V downwards (M' <= V, so V is above its fixed point). python vi.py ROUTE SPEC"""
import sys, numpy as np
e = np.load(f"e-{sys.argv[1]}.npz"); s = np.load(sys.argv[2])
V, goal = e["V"].copy(), e["goal"]; rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
free = s["free"] & ~goal; free[0] = False; ctx = s["ctx"]; nz = int(s["nctx"])
m = len(kptr) - 1; kj = np.repeat(np.arange(m), np.diff(kptr)); ok = ksucc >= 0
for it in range(200000):
    Vs = np.where(ok, V[np.where(ok, ksucc, 0)], 0.0); kv = np.bincount(kj, weights=kprob * Vs, minlength=m)
    nv = np.full(len(V), np.inf); np.minimum.at(nv, rk, np.where(free[rk], np.inf, costs[ro] + kv[rj]))
    z = np.full(nz, np.inf); np.minimum.at(z, s["p_ctx"], costs[s["p_off"]] + kv[s["p_ker"]])
    for _ in range(nz):
        np.minimum.at(z, s["m_from"], s["m_cost"] + z[s["m_to"]])
    nv = np.where(free, z[np.maximum(ctx, 0)], nv); nv = np.where(goal, 0.0, nv)
    d = np.max(np.abs(nv - V)); V = nv
    if it % 500 == 0: print(it, "V'(0)", V[0], "delta", d, flush=True)
    if d < 1e-7 * e["V"][0]: break
print("RESULT", sys.argv[1], sys.argv[2], "iterations", it, "V'(0)", V[0], "V0", e["V"][0], "ratio", V[0] / e["V"][0], "z", np.round(z[:6], 3).tolist())
