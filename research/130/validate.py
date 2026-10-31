"""Compare Light's kernels with the real Abstraction's on every state of the first two layers."""
from light import *

d, ab, L = make(Fraction)
print({k: (v["side"], v["N"], v["W"], v["names"][:3]) for k, v in L.info.items()})
s0 = ab.compress(start(d))
seen = {s0}
frontier = [s0]
checked = 0
mismatch = 0
t = time.time()
LAYERS = int(os.environ.get("LAYERS", "2"))
for layer in range(LAYERS):
    nxt = []
    for cs in frontier:
        ls = from_real(cs)
        if L.is_goal(ls) != ab.is_goal(cs):
            raise SystemExit("goal mismatch")
        if ab.is_goal(cs):
            continue
        for nm in NAMES:
            try:
                real = ab.kernel(cs, ACTS[nm])
            except ActionError:
                real = None
            mine = L.kernel(ls, nm)
            if (real is None) != (mine is None):
                print("REFUSAL MISMATCH", nm, ls)
                mismatch += 1
                continue
            if real is None:
                continue
            real_l = {from_real(k): v for k, v in real.items()}
            if real_l != mine:
                print("KERNEL MISMATCH", nm, ls)
                for k in set(real_l) | set(mine):
                    if real_l.get(k) != mine.get(k):
                        print(k, real_l.get(k), mine.get(k))
                raise SystemExit(1)
            checked += 1
            for k in real:
                if k not in seen:
                    seen.add(k)
                    nxt.append(k)
    frontier = nxt
    print("layer", layer, len(seen), checked, round(time.time() - t, 1), flush=True)
print("OK", checked, "kernels equal; refusal mismatches", mismatch)
