"""t1360: is swapping two leaves (in the status and in every contribution vector of the key) an exact symmetry of the dump's model?
Classes of keys under the swap group, and how many classes hold keys of different bisimulation blocks (0 = exact on this model)."""
import sys, numpy as np, pickle, re, collections, itertools
r = sys.argv[1]; pairs = [tuple(map(int, p.split("-"))) for p in sys.argv[2:]]
e = np.load(f"e-{r}.npz"); blk = np.load(f"e-{r}-bisim.npy"); P = pickle.load(open(f"e-{r}.npz.parts.pkl", "rb")); parts = P["parts"]; g = e["goal"]; V = e["V"]
pat = re.compile(r"\((?:<Status\.\w+: \d>(?:, )?)+\)")
def apply(p, perm):
    def sw(mo):
        items = re.findall(r"<Status\.\w+: \d>", mo.group(0))
        for a, b in perm:
            if max(a, b) < len(items): items[a], items[b] = items[b], items[a]
        return "(" + ", ".join(items) + ")"
    return tuple(pat.sub(sw, x) for x in p)
group = [c for i in range(len(pairs) + 1) for c in itertools.combinations(pairs, i)]
cls = collections.defaultdict(set); vals = collections.defaultdict(set); n = 0
for k in range(len(blk)):
    if g[k] or parts[k] is None: continue
    c = min(apply(parts[k], perm) for perm in group)
    cls[c].add(int(blk[k])); vals[c].add(round(float(V[k]), 6)); n += 1
print(r, pairs, "keys", n, "classes", len(cls), "classes holding several blocks", sum(len(s) > 1 for s in cls.values()), "classes holding several values", sum(len(s) > 1 for s in vals.values()))
