import pickle, sys, collections
from crafting_system.abstraction._pattern import ChoiceNode
for p in sys.argv[1:]:
    d = pickle.load(open(p, "rb"))
    keys, acts, kern = d["keys"], d["actions"], d["kernels"]
    used = set(j for row in acts for _, j in row)
    nnz = sum(len(kern[j][0]) for j in used)
    rows = sum(len(r) for r in acts)
    ch = sum(isinstance(k, ChoiceNode) for k in keys)
    big = sorted((len(kern[j][0]) for j in used), reverse=True)[:5]
    print(p, "keys", len(keys), "choice", ch, "goals", sum(d["goal"]), "rows", rows, "kernels used", len(used), "nnz", nnz, "biggest", big, "offers", len(d["labels"]), d["labels"][-3:], d["costs"][-3:], "cheapest", d["cheapest"])
