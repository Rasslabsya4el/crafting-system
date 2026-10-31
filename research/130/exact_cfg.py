"""exact value of the merged model for the current GOAL / PRICES / action list (env ACTS), by policy iteration."""
from coarse import *
d, ab, L = make(float, True)
names = os.environ.get("ACTS", ",".join(NAMES)).split(",")
C = Coarse(L, [])
t = time.time()
G = Graph(C, (NORMAL, ()), names)
print("exact graph: blocks", G.n, "rows", G.nrows, "edges", G.nedges, round(time.time() - t, 1), "s", flush=True)
t = time.time()
V = G.solve_pi("lower")
eps = G.residual("lower", V)
lo, hi = G.bracket(V, eps)
print("exact V*", V[0], "bracket", V[0] * lo, V[0] * hi, "solve s", round(time.time() - t, 1), flush=True)
