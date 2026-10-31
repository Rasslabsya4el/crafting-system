"""Random walks of the real Abstraction (every family told apart, as the product declares Annulment): at every state the light
model's kernel for every action must equal the real kernel, in exact fractions, up to rare states with six mods."""
import random
from light import *

d, ab, L = make(Fraction, False)
rng = random.Random(int(os.environ.get("SEED", "1")))
WALKS = int(os.environ.get("WALKS", "150"))
s = ab.compress(start(d))
checked = states = 0
depth = Counter()
t = time.time()
seen_states = set()
for w in range(WALKS):
    cs = ab.compress(start(d))
    for step in range(40):
        ls = from_real(cs)
        if ab.is_goal(cs):
            break
        options = []
        for nm in NAMES:
            try:
                real = ab.kernel(cs, ACTS[nm])
            except ActionError:
                real = None
            mine = L.kernel(ls, nm)
            assert (real is None) == (mine is None), (nm, ls)
            if real is None:
                continue
            rl = {from_real(k): v for k, v in real.items()}
            if rl != mine:
                print("MISMATCH", nm, ls)
                for k in set(rl) | set(mine):
                    if rl.get(k) != mine.get(k):
                        print("  ", k, rl.get(k), mine.get(k))
                raise SystemExit(1)
            checked += 1
            options.append((nm, real))
        if ls not in seen_states:
            seen_states.add(ls)
            depth[len(ls[1])] += 1
        # bias the walk towards filling the item: prefer exalt and regal
        weights = [3 if nm in ("exalt", "regal", "augment") else 1 for nm, _ in options]
        nm, real = rng.choices(options, weights)[0]
        ks = list(real)
        cs = rng.choices(ks, [float(real[k]) for k in ks])[0]
    if w % 25 == 24:
        print("walks", w + 1, "states", len(seen_states), "kernels equal", checked, "by mods", dict(sorted(depth.items())), round(time.time() - t, 1), flush=True)
print("OK", checked)
