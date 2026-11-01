import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r25 import r25, all_states
from model import run
w = r25([(500, 2), (1000, 2), (1500, 1)], raw=True)
S = all_states(w)
sub = [(("A",)), ("B",), ("C",), ("A","B"), ("A","C"), ("B","C")]
donors = [s for s in S if s[1] in sub]
sol, proc, acq, secs = run(w, lambda s: [("recomb", d) for d in donors], w.blank())
V = sol.values
b = w.blank()
for t in [(), ("A",), ("A","B"), ("A","B","C")]:
    s = w.state(t)
    print(t, V.get(acq.start(s)))
for d in donors:
    print("acq", d[1], V.get(("in", ("full", d), b)))
st = w.state(("A",))
print("recomb A + B kernel", {k: float(v) for k, v in w.k_recomb(st, w.state(("B",))).items()})
print("recomb AB+AC", {k: float(v) for k, v in w.k_recomb(w.state(("A","B")), w.state(("A","C"))).items()})
print("policy at A:", sol.policy[acq.start(st)].label)
print("policy at blank:", sol.policy[acq.start(b)].label)
print("policy at AB:", sol.policy[acq.start(w.state(("A","B")))].label)
