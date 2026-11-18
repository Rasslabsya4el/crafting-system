"""#1315: which key of a coarse key holds the least complete value?    python ledmin.py DUMP.pkl [PARTS,DROPPED]   (default tags,counts)

led.py with BEST=1 shows that the least complete value inside a coarse key is a lead that ends the count in under 1% of the keys. This asks
whether that least value sits at a member one can name without the complete model: the member with the fewest junk mods (least sum of the
two counts). A count on a complete dump; no argument."""
import math, pickle, sys
from collections import defaultdict
from types import SimpleNamespace
import numpy as np
from crafting_system.abstraction._pattern import PatternModel, PatternStats
from crafting_system.planner import _pattern_bound as pb
from crafting_system.solver import solve_packed

d = pickle.load(open(sys.argv[1], "rb"))
drop = tuple((sys.argv[2] if len(sys.argv) > 2 else "tags,counts").split(","))
keys, goal = d["keys"], d["goal"]
model = PatternModel(keys, goal, d["actions"], d["kernels"], PatternStats(), {}, d["expanded"], None)
V = np.asarray(solve_packed(pb.pack_pattern_model(model, [SimpleNamespace(cost=c) for c in d["costs"]], None), progress=None, refuse_above=math.inf).value[: len(keys)], dtype=float)
groups = defaultdict(list)
for i, k in enumerate(keys):
    if not goal[i]:
        groups[k._replace(**{f: None for f in drop})].append(i)
several = [g for g in groups.values() if len(g) > 1]
at_least, keys_above, keys_in, worst = 0, 0, 0, 0.0
for g in several:
    lo = min(V[i] for i in g)
    fewest = min(sum(keys[i].counts) for i in g)
    best_of_fewest = min(V[i] for i in g if sum(keys[i].counts) == fewest)
    at_least += best_of_fewest <= lo * (1 + 1e-9) + 1e-12
    worst = max(worst, (best_of_fewest - lo) / max(best_of_fewest, 1e-300))
    for i in g:  # is the value never lower with more junk? compared with the best member of the fewest junk
        keys_in += 1
        keys_above += V[i] >= best_of_fewest * (1 - 1e-9) - 1e-12
print(f"RESULT {sys.argv[1].split('/')[-1]} dropped {','.join(drop)}: coarse keys {len(groups)}, of them {len(several)} hold several keys; the least complete value is at a member with the fewest junk mods in "
      f"{at_least} of them ({100 * at_least / max(len(several), 1):.2f}%); keys whose value is at least that member's: {keys_above} of {keys_in} ({100 * keys_above / max(keys_in, 1):.2f}%); "
      f"where it is not, the fewest-junk member is above the least value by at most {100 * worst:.2f}%")
