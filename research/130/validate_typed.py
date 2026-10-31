"""Family types for the Annulment: the real Abstraction with an Annulment that declares Reads.adding() (its junk told apart
by family type) against the light model with merged kinds; kernels and per-layer state counts."""
from light import *
from dataclasses import dataclass
from crafting_system.actions import AnnulmentOrb
from crafting_system.actions.contract import Reads


@dataclass(frozen=True)
class AnnulTyped(AnnulmentOrb):
    def reads(self, data):
        return Reads.adding()


d = data()
acts = dict(ACTS)
acts["annul"] = AnnulTyped()
ab = Abstraction(d, goal_of(d), BASE, LEVEL, list(acts.values()))
L = Light(d, ab, Fraction, merge="real")
# map the real kind of each family to the merged kind of the light model
pool = build_pool(d, Item.build(d, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, influences=frozenset({Influence.HUNTER})))
kmap = {}
for f in pool:
    rk = ab.kind_of(f.mods[0].mod)
    classes = Counter()
    for pm in f.mods:
        classes[tuple(int(x) for x in ab._drawn_contribution(pm.mod))] += pm.weight
    per_mod = tuple(sorted((tuple(int(x) for x in ab._drawn_contribution(pm.mod)), int(pm.weight)) for pm in f.mods))
    lk = "R|" + f.side.value + "|" + repr(per_mod)
    if kmap.setdefault(rk, lk) != lk: print('CONFLICT', rk, f.family, lk, kmap[rk])
print("real kinds", len(kmap), "light kinds", len(L.info))


def conv(cs):
    r = {Rarity.NORMAL: NORMAL, Rarity.MAGIC: MAGIC, Rarity.RARE: RARE}[cs.flags.rarity]
    return (r, tuple(sorted((s.side.value, kmap[s.kind], tuple(int(x) for x in s.contribution)) for s in cs.slots)))


s0 = ab.compress(start(d))
seen = {s0}
frontier = [s0]
checked = 0
t = time.time()
for layer in range(int(os.environ.get("LAYERS", "3"))):
    nxt = []
    for cs in frontier:
        ls = conv(cs)
        if ab.is_goal(cs):
            continue
        for nm in NAMES:
            try:
                real = ab.kernel(cs, acts[nm])
            except ActionError:
                real = None
            mine = L.kernel(ls, nm)
            assert (real is None) == (mine is None), (nm, ls)
            if real is None:
                continue
            rl = {conv(k): v for k, v in real.items()}
            assert rl == mine, (nm, ls)
            checked += 1
            for k in real:
                if k not in seen:
                    seen.add(k)
                    nxt.append(k)
    frontier = nxt
    print("layer", layer, "states", len(seen), "kernels equal", checked, round(time.time() - t, 1), flush=True)
