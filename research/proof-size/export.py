"""t1360: a complete dump of kd.py -> plain arrays (npz) + key parts (pickle of tuples of str), and the complete values V by the planner's solver.
python export.py DUMP.pkl OUT.npz"""
import math, pickle, sys
from types import SimpleNamespace
import numpy as np
from crafting_system.abstraction._pattern import CHOICE, ChoiceNode, PatternModel, PatternStats
from crafting_system.planner import _pattern_bound as pb
from crafting_system.solver import solve_packed
d = pickle.load(open(sys.argv[1], "rb"))
keys, goal, acts, kern, exp = d["keys"], d["goal"], d["actions"], d["kernels"], d["expanded"]
n = len(keys)
offers = [SimpleNamespace(cost=c) for c in d["costs"]]
model = PatternModel(keys, goal, acts, kern, PatternStats(), {}, exp, None)
sol = solve_packed(pb.pack_pattern_model(model, offers, None), progress=None, refuse_above=math.inf)
V = np.asarray(sol.value[:n], dtype=float)
used = sorted(set(j for r in acts for _, j in r)); jid = {j: i for i, j in enumerate(used)}
kptr = [0]; ksucc = []; kprob = []
for j in used:
    s, w = kern[j]; t = sum(w)
    ksucc += [x if x >= 0 else -1 for x in s]; kprob += [x / t for x in w]; kptr.append(len(ksucc))
rk, ro, rj = [], [], []
for k, r in enumerate(acts):
    for o, j in r:
        rk.append(k); ro.append(o); rj.append(jid[j])
choice = np.array([isinstance(k, ChoiceNode) for k in keys])
np.savez_compressed(sys.argv[2], V=V, goal=np.array(goal), choice=choice, expanded=np.array(exp), rk=np.array(rk), ro=np.array(ro), rj=np.array(rj),
    kptr=np.array(kptr), ksucc=np.array(ksucc), kprob=np.array(kprob), costs=np.array(d["costs"]), cheapest=d["cheapest"], start_value=d["start_value"],
    choice_cost=pb.FLOOR_COST if hasattr(pb, "FLOOR_COST") else 0.0)
parts = [None if isinstance(k, ChoiceNode) else tuple(repr(getattr(k, f)) for f in k._fields) for k in keys]
pickle.dump({"fields": keys[0]._fields, "parts": parts, "labels": d["labels"], "choice_parent": [getattr(k, "__dict__", None) and None for k in keys]}, open(sys.argv[2] + ".parts.pkl", "wb"))
print("exported", sys.argv[1], "n", n, "rows", len(rk), "kernels", len(used), "V0", V[0], "dump V0", d["start_value"], "labels", d["labels"])
