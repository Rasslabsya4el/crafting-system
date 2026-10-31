"""Merging the families that have the same side and the same total weight per goal contribution is exact (lumpable):
for random states of the model that tells every family apart, the kernel pushed through the merge equals the merged model's kernel."""
import random
from light import *

d, ab, L0 = make(Fraction, False)
_, _, L1 = make(Fraction, True)
fmap = {}
pool = build_pool(d, Item.build(d, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, influences=frozenset({Influence.HUNTER})))
for f in pool:
    k0 = ab.kind_of(f.mods[0].mod)
    classes = Counter()
    for pm in f.mods:
        classes[tuple(int(x) for x in ab._drawn_contribution(pm.mod))] += int(pm.weight)
    fmap[k0] = "T|" + f.side.value + "|" + repr(tuple(sorted(classes.items())))
assert set(fmap.values()) == set(L1.info), (set(fmap.values()) ^ set(L1.info))


def f_state(s):
    r, slots = s
    return (r, tuple(sorted((a, fmap[k], c) for a, k, c in slots)))


def push(k):
    out = defaultdict(Fraction)
    for s, p in k.items():
        out[f_state(s)] += p
    return dict(out)


rng = random.Random(3)
checked = 0
for walk in range(int(os.environ.get("WALKS", "400"))):
    s = (NORMAL, ())
    for step in range(30):
        if L0.is_goal(s):
            break
        options = []
        for nm in NAMES:
            k0 = L0.kernel(s, nm)
            k1 = L1.kernel(f_state(s), nm)
            assert (k0 is None) == (k1 is None), (nm, s)
            if k0 is None:
                continue
            assert push(k0) == k1, (nm, s)
            checked += 1
            options.append(k0)
        k = rng.choices(options, [3 if len(o) > 5 else 1 for o in options])[0]
        s = rng.choices(list(k), [float(v) for v in k.values()])[0]
print("lumpable on", checked, "kernels")
