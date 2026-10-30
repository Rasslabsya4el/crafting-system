"""R12 reconstruction for ticket #10 (Harvest reforges), 2026-10-30.

Usage:  python -I 2026-10-30-harvest-reforges-r12.py <path-to-repoe-3.29.3.3-folder>

Reads mods.json (repoe-fork export of PoE 3.29.3.3) and computes, for the generic
Amulet base (spawn tags: amulet, default) and a given item level:

  * F1 (the guide's formula): weight of +1 Lightning gems / total weight of the pool,
    where the pool is all mods, or all Lightning-tagged mods, or the Lightning-tagged
    mods minus the family of the fractured mod.  These are the numbers the PoE Vault
    guide quotes (0.094%, 1.338%, 2.88%).  They are single-draw weight shares.
  * F2 (exact per-click probability that the finished item contains the mod) under the
    draw model stated in the findings file (candidate rules, not admitted):
        count n in {4,5,6} at 8:3:1; successive weighted draws without replacement from the
        eligible mods; a family already on the item is excluded; max 3 prefixes and 3 suffixes;
        for a tagged reforge the first draw comes from the tagged mods only (H1: proportional to
        weight; H2: uniform over the tagged mods), the remaining n-1 draws from the full pool.
        The fractured mod either counts inside n (F-in) or is extra to n (F-out).
    F2 is exact (Fraction): successive sampling is simulated as an exponential race, which
    turns every probability into a polynomial integral that is evaluated in exact arithmetic.
    A brute-force check on small random pools runs first (self-test).
"""
import json
import random
import sys
from fractions import Fraction
from functools import reduce
from math import gcd

TARGET_ID = "GlobalLightningGemLevel1"
TARGET_FAMILY = "GlobalDamageTypeGemLevel"
SPAWN_TAGS = ("amulet", "default")
N_DIST = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}


def spawn_weight(mod, tags):
    for sw in mod["spawn_weights"]:  # first matching tag decides (wiki, Modifier, Spawn weight tag)
        if sw["tag"] in tags:
            return sw["weight"]
    return 0


def load_pool(mods, ilvl):
    pool = []
    for mid, m in mods.items():
        if m["domain"] != "item" or m["generation_type"] not in ("prefix", "suffix"):
            continue
        if m["required_level"] > ilvl:
            continue
        w = spawn_weight(m, SPAWN_TAGS)
        if w <= 0:
            continue
        assert len(m["groups"]) == 1, mid
        pool.append(dict(id=mid, side=m["generation_type"], w=w, fam=m["groups"][0],
                         lightning="lightning" in m["implicit_tags"], text=m["text"]))
    return pool


def families(pool, blocked=(), only=None):
    """family -> [side, total weight] over mods passing `only`, skipping blocked families."""
    fam = {}
    for m in pool:
        if m["fam"] in blocked or (only and not only(m)):
            continue
        f = fam.setdefault(m["fam"], [m["side"], 0])
        assert f[0] == m["side"]
        f[1] += m["w"]
    return fam


# ---------------------------------------------------------------- exact race
def race_states(fam, target, cap_p, cap_s):
    """Return (g, K_T, states): states[(a,b)] is a polynomial in x (list of int coefficients)
    for P(a prefix / b suffix families, each count capped at its cap, arrived before the target)."""
    ws = [v[1] for v in fam.values()]
    g = reduce(gcd, ws)
    K = {f: v[1] // g for f, v in fam.items()}
    D = sum(k for f, k in K.items() if f != target)
    states = {(0, 0): [1] + [0] * D}
    for f, (side, _) in fam.items():
        if f == target:
            continue
        k = K[f]
        new = {}
        for (a, b), poly in states.items():
            shifted = [0] * k + poly[:D + 1 - k]  # not arrived yet: x^k * poly
            na = new.setdefault((a, b), [0] * (D + 1))
            for i, c in enumerate(shifted):
                if c:
                    na[i] += c
            # arrived: (1 - x^k) * poly
            if side == "prefix":
                a2, b2 = min(cap_p, a + 1), b
            else:
                a2, b2 = a, min(cap_s, b + 1)
            nb = new.setdefault((a2, b2), [0] * (D + 1))
            for i, c in enumerate(poly):
                if c:
                    nb[i] += c
            for i, c in enumerate(shifted):
                if c:
                    nb[i] -= c
        states = new
    return g, K[target], states


def prob_family_drawn(states, KT, side, cap_p, cap_s, picks):
    """P(target family is drawn within `picks` successive draws)."""
    if picks <= 0:
        return Fraction(0)
    acc = {}
    for (a, b), poly in states.items():
        if side == "prefix":
            ok = a < cap_p and a + b < picks
        else:
            ok = b < cap_s and a + b < picks
        if ok:
            for m, c in enumerate(poly):
                if c:
                    acc[m] = acc.get(m, 0) + c
    return sum(Fraction(c * KT, m + KT) for m, c in acc.items())


def p_family(fam, target, p0, s0, picks):
    cap_p, cap_s = 3 - p0, 3 - s0
    side = fam[target][0]
    _, KT, st = race_states(fam, target, cap_p, cap_s)
    return prob_family_drawn(st, KT, side, cap_p, cap_s, picks)


# ---------------------------------------------------------------- brute force (self-test)
def brute(fam_list, target, p0, s0, picks):
    """fam_list: list of (name, side, weight). Exact recursion over draw sequences."""
    def rec(avail, p, s, left):
        if left == 0:
            return Fraction(0)
        elig = [f for f in avail if (f[1] == "prefix" and p < 3) or (f[1] == "suffix" and s < 3)]
        tot = sum(f[2] for f in elig)
        if tot == 0:
            return Fraction(0)
        res = Fraction(0)
        for f in elig:
            pr = Fraction(f[2], tot)
            if f[0] == target:
                res += pr
            else:
                rest = [x for x in avail if x[0] != f[0]]
                res += pr * rec(rest, p + (f[1] == "prefix"), s + (f[1] == "suffix"), left - 1)
        return res
    return rec(fam_list, p0, s0, picks)


def self_test():
    rnd = random.Random(7)
    for _ in range(40):
        nf = rnd.randint(3, 7)
        fl = [("f%d" % i, rnd.choice(["prefix", "suffix"]), rnd.choice([1, 2, 3, 5, 10]) * 50) for i in range(nf)]
        t = fl[0][0]
        p0, s0 = rnd.randint(0, 2), rnd.randint(0, 2)
        picks = rnd.randint(1, 5)
        fam = {n: [sd, w] for n, sd, w in fl}
        assert p_family(fam, t, p0, s0, picks) == brute(fl, t, p0, s0, picks), (fl, p0, s0, picks)
    print("self-test ok: exact race == brute-force enumeration on 40 random small pools")


# ---------------------------------------------------------------- scenarios
def pct(x, nd=4):
    return "%.*f%%" % (nd, float(x) * 100)


def run(mods, ilvl):
    pool = load_pool(mods, ilvl)
    tgt = next(m for m in pool if m["id"] == TARGET_ID)
    wT = tgt["w"]
    full = families(pool)
    famW = full[TARGET_FAMILY][1]
    pin_in_family = Fraction(wT, famW)  # which member of the gem-level family, once the family is drawn
    tot = sum(m["w"] for m in pool)
    tagged = sum(m["w"] for m in pool if m["lightning"])
    res_w = sum(m["w"] for m in pool if m["fam"] == "LightningResistance")
    print("=== amulet ilvl %d: %d mods, %d families, total weight %d; Lightning-tagged: %d mods, weight %d" % (
        ilvl, len(pool), len(full), tot, sum(1 for m in pool if m["lightning"]), tagged))
    print("F1 Chaos          = %d/%d = %s" % (wT, tot, pct(Fraction(wT, tot), 5)))
    print("F1 Reforge Ltn    = %d/%d = %s" % (wT, tagged, pct(Fraction(wT, tagged), 5)))
    print("F1 fractured LRes = %d/%d = %s   (LightningResistance family weight %d)" % (
        wT, tagged - res_w, pct(Fraction(wT, tagged - res_w), 5), res_w))

    def chaos(blocked, p0, s0, extra_fixed):
        fam = families(pool, blocked)
        out = Fraction(0)
        cap_p, cap_s = 3 - p0, 3 - s0
        _, KT, st = race_states(fam, TARGET_FAMILY, cap_p, cap_s)
        for n, pn in N_DIST.items():
            out += pn * prob_family_drawn(st, KT, "prefix", cap_p, cap_s, n - extra_fixed) * pin_in_family
        return out

    def tagged_reforge(blocked, p0, s0, extra_fixed, uniform=False):
        """Forced draw: weight-proportional over tagged mods (candidate H1) or uniform over them (H2)."""
        fam_all = families(pool, blocked)
        tagged_mods = [m for m in pool if m["lightning"] and m["fam"] not in blocked]
        if uniform:
            fam_tag = {}
            for m in tagged_mods:
                f = fam_tag.setdefault(m["fam"], [m["side"], 0])
                f[1] += 1
            tag_total, w_target = len(tagged_mods), 1
        else:
            fam_tag = families(pool, blocked, only=lambda m: m["lightning"])
            tag_total, w_target = sum(v[1] for v in fam_tag.values()), wT
        out = Fraction(0)
        for n, pn in N_DIST.items():  # forced draw is the target itself
            out += pn * Fraction(w_target, tag_total)
        for f, (side, wf) in fam_tag.items():  # forced draw is another tagged family f
            if f == TARGET_FAMILY:
                continue
            pf = Fraction(wf, tag_total)
            pp, ss = p0 + (side == "prefix"), s0 + (side == "suffix")
            fam = {k: v for k, v in fam_all.items() if k != f}
            cap_p, cap_s = 3 - pp, 3 - ss
            _, KT, st = race_states(fam, TARGET_FAMILY, cap_p, cap_s)
            for n, pn in N_DIST.items():
                picks = n - extra_fixed - 1
                out += pn * pf * prob_family_drawn(st, KT, "prefix", cap_p, cap_s, picks) * pin_in_family
        return out

    print("F2 Chaos, no fractured                : %s" % pct(chaos((), 0, 0, 0)))
    print("F2 Reforge Lightning, no fractured    : %s" % pct(tagged_reforge((), 0, 0, 0)))
    for label, extra in (("fractured mod counts inside n", 1), ("fractured mod is extra to n  ", 0)):
        rf = tagged_reforge(("LightningResistance",), 0, 1, extra)
        cf = chaos(("LightningResistance",), 0, 1, extra)
        print("F2 Reforge Lightning, fractured LRes, %s: %s   (Chaos on same item: %s)" % (label, pct(rf), pct(cf)))
    print("F2 under H2 (uniform forced pick): no fractured %s ; fractured-in %s ; fractured-out %s" % (
        pct(tagged_reforge((), 0, 0, 0, True)),
        pct(tagged_reforge(("LightningResistance",), 0, 1, 1, True)),
        pct(tagged_reforge(("LightningResistance",), 0, 1, 0, True))))


if __name__ == "__main__":
    base = sys.argv[1]
    self_test()
    with open(base + "/mods.json", encoding="utf-8") as fh:
        mods = json.load(fh)
    for ilvl in (84, 85, 86):
        run(mods, ilvl)
    print("guide: 200/213850 = %s ; 200/14950 = %s ; 200/6950 = %s" % (
        pct(Fraction(200, 213850), 5), pct(Fraction(200, 14950), 5), pct(Fraction(200, 6950), 5)))
