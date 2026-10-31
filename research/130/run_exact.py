from coarse import *
import pickle
d, ab, L = make(float, True)
C = Coarse(L, [])
t = time.time()
G = Graph(C, (NORMAL, ()), NAMES)
print("exact graph: blocks", G.n, "rows", G.nrows, "edges", G.nedges, round(time.time() - t, 1), "s", flush=True)
t = time.time()
V = G.solve_pi("lower", report=True)
eps = G.residual("lower", V)
lo, hi = G.bracket(V, eps)
print("exact V*", V[0], "eps", eps, "bracket", V[0] * lo, V[0] * hi, round(time.time() - t, 1), "s", flush=True)
np.save(".claude/scratch/130/exact_V.npy", V)
