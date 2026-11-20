"""t1363, question (b): does a rule read from the key alone name the bisimulation blocks inside the lemma's set F?
Each rule maps a key to a class; a rule is exact on the dump when no class holds keys of two blocks. Counts: classes, classes holding
several blocks, several values (relative 1e-9), and the keys in those mixed classes. python bnames.py ROUTE SPEC"""
import sys, re, pickle, collections, numpy as np
r = sys.argv[1]; e = np.load(f"e-{r}.npz"); P = pickle.load(open(f"e-{r}.npz.parts.pkl", "rb")); parts, fields = P["parts"], P["fields"]
blk = np.load(f"e-{r}-bisim.npy"); F = np.load(sys.argv[2])["free"]; V = e["V"]
fi = {f: i for i, f in enumerate(fields)}
def st(k): return tuple(int(x) for x in re.findall(r": (\d)>", parts[k][fi["status"]]))
def contrib_only(x): return re.sub(r"mod_id='[^']*'", "", re.sub(r"kind='(?!VeiledPrefix|VeiledSuffix|\w*CannotChange)[^']*'", "", x))
rules = {
  "drop status": lambda k, p: p[:fi["status"]] + p[fi["status"] + 1:],
  "drop status, keep which leaves pass": lambda k, p: p[:fi["status"]] + p[fi["status"] + 1:] + (tuple(x == 2 for x in st(k)),),
  "drop status, mod names (contributions kept)": lambda k, p: tuple(contrib_only(x) for i, x in enumerate(p) if i != fi["status"]),
  "drop status, crafted and held mod names": lambda k, p: tuple(contrib_only(x) if fields[i] in ("crafted", "held") else x for i, x in enumerate(p) if i != fi["status"]),
  "drop status and crafted (keep counts)": lambda k, p: tuple(x for i, x in enumerate(p) if fields[i] not in ("status", "crafted")),
  "drop status, crafted, held": lambda k, p: tuple(x for i, x in enumerate(p) if fields[i] not in ("status", "crafted", "held")),
}
ks = [k for k in np.flatnonzero(F) if parts[k] is not None]
print(r, "F keys", len(ks), "blocks in F", len({blk[k] for k in ks}), "values in F", len(np.unique(np.round(V[ks], 6))))
for name, f in rules.items():
    cb = collections.defaultdict(set); cv = collections.defaultdict(set); cn = collections.Counter()
    for k in ks:
        c = f(k, parts[k]); cb[c].add(int(blk[k])); cv[c].add(round(float(V[k]) / float(V[0]), 9)); cn[c] += 1
    mb = [c for c in cb if len(cb[c]) > 1]; mv = [c for c in cv if len(cv[c]) > 1]
    print(f"  {name}: classes {len(cb)}; mixing blocks {len(mb)} ({sum(cn[c] for c in mb)} keys); mixing values {len(mv)} ({sum(cn[c] for c in mv)} keys)")
