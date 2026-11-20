"""t1360: inside each bisimulation block, which leaves' status differ and between which values; and per block the optimal row's offer."""
import sys, pickle, collections, re, numpy as np
e = np.load(sys.argv[1]); blk = np.load(sys.argv[1].replace(".npz", "-bisim.npy")); P = pickle.load(open(sys.argv[1] + ".parts.pkl", "rb"))
parts, fields = P["parts"], P["fields"]; si = fields.index("status"); goal = e["goal"]
def st(k): return tuple(int(x) for x in re.findall(r": (\d)>", parts[k][si]))
by = collections.defaultdict(list)
for k in range(len(blk)):
    if not goal[k]: by[blk[k]].append(k)
pairs = collections.Counter(); nleaf = collections.Counter()
for ks in by.values():
    S = {st(k) for k in ks}
    if len(S) < 2: continue
    S = list(S)
    for i in range(len(S[0])):
        vals = frozenset(s[i] for s in S)
        if len(vals) > 1: pairs[(i, tuple(sorted(vals)))] += 1
    nleaf[len(S)] += 1
print(sys.argv[1], "leaf index, status values that share a block (0 absent, 1 below, 2 passing): blocks", pairs.most_common(12))
print(" statuses per block:", sorted(nleaf.items())[:12])
