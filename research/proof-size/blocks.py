"""t1360: which key parts vary inside a bisimulation block (bisim.py's), and how many keys the block count saves per part.
python blocks.py e-ROUTE.npz"""
import sys, pickle, collections, numpy as np
e = np.load(sys.argv[1]); blk = np.load(sys.argv[1].replace(".npz", "-bisim.npy")); P = pickle.load(open(sys.argv[1] + ".parts.pkl", "rb"))
fields, parts = P["fields"], P["parts"]
goal = e["goal"]
by = collections.defaultdict(list)
for k, b in enumerate(blk):
    if not goal[k] and parts[k] is not None:
        by[b].append(k)
multi = [ks for ks in by.values() if len(ks) > 1]
print(f"blocks {len(by)} (with several keys {len(multi)}), keys in them {sum(map(len, multi))}")
for i, f in enumerate(fields):
    varies = sum(1 for ks in multi if len({parts[k][i] for k in ks}) > 1)
    print(f"  {f}: varies in {varies} blocks")
# keys left if each part alone were dropped vs blocks: a part is 'unread' when merging on it never crosses blocks
for i, f in enumerate(fields):
    g = collections.defaultdict(set)
    for k, p in enumerate(parts):
        if p is not None and not goal[k]:
            g[p[:i] + p[i + 1:]].add(blk[k])
    cross = sum(1 for s in g.values() if len(s) > 1)
    print(f"  drop {f}: coarse keys {len(g)}, of which mixing several blocks {cross}")
sz = sorted(map(len, by.values()), reverse=True)
print("largest blocks", sz[:10], "singletons", sum(1 for s in sz if s == 1))
