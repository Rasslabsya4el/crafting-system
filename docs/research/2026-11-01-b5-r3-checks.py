"""Checks of research ticket #273 (B5 R3): three small exact comparisons, no network, standard library only.

Run: python -I docs/research/2026-11-01-b5-r3-checks.py

1. Craft of Exile's rules for the strand cut and for Foulborn, as I read them from the public emulator's behaviour
   (written here as arithmetic in my own words, not copied code), against ADR-0040's exact integers.
2. The Orb of Remembrance count: ADR-0043's normal(35, 25) against the model the emulator uses (10 plus a gamma draw
   of shape 2.6 and scale 12.1), on the 2,255 results of the first author's sheet.
3. The destination of an Unravelling on the wand test of ADR-0044 under the three readings: rank multipliers (A),
   cumulative (B) and plain weights of the higher tiers (the emulator's).
"""

# ---------- 2. Remembrance ----------
import math

counts_text = """10:20 11:32 12:31 13:21 14:31 15:36 16:25 17:37 18:32 19:40 20:43 21:45 22:39 23:37 24:32 25:38 26:37 27:43 28:35 29:50 30:43 31:42 32:48 33:30 34:55 35:35 36:46 37:32 38:44 39:51 40:43 41:46 42:48 43:31 44:34 45:41 46:34 47:37 48:32 49:33 50:39 51:40 52:36 53:34 54:27 55:31 56:31 57:24 58:21 59:34 60:23 61:22 62:20 63:28 64:23 65:22 66:21 67:21 68:17 69:19 70:18 71:14 72:15 73:17 74:14 75:11 76:8 77:9 78:9 79:6 80:14 81:7 82:6 83:5 84:8 85:5 86:2 87:8 88:5 89:5 90:5 91:3 92:3 93:3 94:5 95:1 97:2 98:2 100:3"""
obs = {int(a): int(b) for a, b in (x.split(":") for x in counts_text.split())}
N = sum(obs.values())
print("N", N, "mean", sum(k * v for k, v in obs.items()) / N)


def gammap(a, x):
    """regularized lower incomplete gamma P(a, x)"""
    if x <= 0:
        return 0.0
    if x < a + 1:
        s = 1.0 / a
        t = s
        n = a
        for _ in range(2000):
            n += 1
            t *= x / n
            s += t
            if abs(t) < abs(s) * 1e-15:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-15:
            break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, k):
    return 1 - gammap(k / 2, x / 2)


def Phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# Model A (ADR-0043): x ~ N(35,25) accepted if lo <= x < 100.5, result round(x)
def modelA(lo):
    p = {}
    for k in range(10, 101):
        a = max(k - 0.5, lo)
        b = k + 0.5
        p[k] = max(0.0, Phi((b - 35) / 25) - Phi((a - 35) / 25))
    z = sum(p.values())
    return {k: v / z for k, v in p.items()}


# Model C (Craft of Exile beta): t = round(10 + 12.1 * Gamma(2.6)), redraw if t > 100
def modelC(shape=2.6, scale=12.1):
    p = {}
    for k in range(10, 101):
        lo = max(0.0, (k - 0.5 - 10) / scale)
        hi = (k + 0.5 - 10) / scale
        p[k] = gammap(shape, hi) - gammap(shape, lo)
    z = sum(p.values())
    return {k: v / z for k, v in p.items()}


def mean(p):
    return sum(k * v for k, v in p.items())


def chi(p, width=5, label=""):
    bins = []
    k = 10
    while k <= 100:
        hi = min(k + width - 1, 100)
        bins.append((k, hi))
        k += width
    O = [sum(obs.get(j, 0) for j in range(a, b + 1)) for a, b in bins]
    E = [N * sum(p[j] for j in range(a, b + 1)) for a, b in bins]
    # merge tail bins with E < 5
    mo, me = [], []
    co = ce = 0
    for o, e in zip(O, E):
        co += o
        ce += e
        if ce >= 5:
            mo.append(co); me.append(ce); co = ce = 0
    if ce > 0:
        mo[-1] += co; me[-1] += ce
    x2 = sum((o - e) ** 2 / e for o, e in zip(mo, me))
    df = len(mo) - 1
    print(f"{label}: mean {mean(p):.2f}, chi2 {x2:.1f} on {df} df (merged bins {len(mo)}), p {chi2_sf(x2, df):.3f}, "
          f"P(<=14) {sum(p[j] for j in range(10,15)):.4f}, P(>=75) {sum(p[j] for j in range(75,101)):.4f}")
    return mo, me


for lo in (10.0, 9.5):
    chi(modelA(lo), label=f"A normal(35,25) lo={lo}")
chi(modelC(), label="C CoE gamma(2.6)*12.1+10")
# observed
print("observed P(<=14)", sum(obs.get(j, 0) for j in range(10, 15)) / N, "P(>=75)", sum(obs.get(j, 0) for j in range(75, 101)) / N)
# log-likelihood
def ll(p):
    return sum(v * math.log(p[k]) for k, v in obs.items())
print("loglik A(10.0)", ll(modelA(10.0)), "A(9.5)", ll(modelA(9.5)), "C", ll(modelC()))
# by coarse deciles
for name, p in (("A", modelA(10.0)), ("C", modelC())):
    print(name, [round(N * sum(p[j] for j in range(a, min(a + 9, 100) + 1)), 1) for a in range(10, 101, 10)])
print("obs", [sum(obs.get(j, 0) for j in range(a, min(a + 9, 100) + 1)) for a in range(10, 101, 10)])


# ---------- 1. cut ----------


def kept_exact(w, s, foul):
    """ADR-0040: K = floor(200 (T-1) / (200 + [s>=1](5s+95) + [foul]*150)) + 1"""
    d = 200 + (5 * s + 95 if s >= 1 else 0) + (150 if foul else 0)
    return (200 * (w - 1)) // d + 1


def kept_coe_strands(w, s):
    """CoE beta, floats as in JS doubles: D = w - (floor(I*(w-1)) + 1), I = 100/(2.5 s + 147.5); kept = w - D"""
    I = 100 / (2.5 * s + 147.5)
    D = w - (math.floor(I * (w - 1)) + 1)
    return w - D


def kept_coe_foul_alone(w):
    """CoE beta: foulBornModifierTierRating = 100; cut = ceil(100*(1-1/(1+100/100)))/100 = 0.5;
    k = floor(w*0.5) removed from the bottom (N+1 = w when every tier up to w is eligible)."""
    t = 1 - 1 / (1 + 100 * (100 / 100) / 100)
    v = math.ceil(100 * t) / 100
    k = math.floor(w * v)
    return w - k


def kept_coe_foul_strands(w, s):
    """CoE beta combined: removed = max(k_rating, D_strand)"""
    t = 1 - 1 / (1 + 1.0)
    v = math.ceil(100 * t) / 100
    k = math.floor(w * v)
    if s > 0:
        I = 100 / (2.5 * s + 147.5)
        D = w - (math.floor(I * (w - 1)) + 1)
    else:
        D = 0
    return w - max(k, D)


print("1) strand cut, CoE (float) vs exact, tiers 1..16, strands 1..100")
bad = []
for w in range(1, 17):
    for s in range(1, 101):
        a, b = kept_exact(w, s, False), kept_coe_strands(w, s)
        if a != b:
            bad.append((w, s, a, b))
print("mismatches:", len(bad), bad[:20])

print("2) Foulborn alone (0 strands): kept tiers per N")
print(" N      :", list(range(1, 16)))
print(" wiki/D175:", [kept_exact(n, 0, True) for n in range(1, 16)])
print(" CoE beta :", [kept_coe_foul_alone(n) for n in range(1, 16)])
diff = [n for n in range(1, 16) if kept_exact(n, 0, True) != kept_coe_foul_alone(n)]
print(" differ at N =", diff)

print("3) Foulborn + strands: additive (post) vs max (CoE) , N = 8, 13; s = 1,11,31,62")
for n in (8, 13):
    for s in (1, 11, 31, 62):
        print(f" N={n} s={s}: additive={kept_exact(n, s, True)}  CoE max-rule={kept_coe_foul_strands(n, s)}  strands only={kept_exact(n, s, False)}")
cnt = 0; tot = 0; ex = []
for n in range(1, 16):
    for s in range(1, 101):
        tot += 1
        a, b = kept_exact(n, s, True), kept_coe_foul_strands(n, s)
        if a != b:
            cnt += 1
            ex.append((n, s, a, b))
print(" cells that differ (N 1..15, s 1..100):", cnt, "of", tot, ex[:8])
# which direction
print(" CoE keeps more in", sum(1 for e in ex if e[3] > e[2]), "cells, fewer in", sum(1 for e in ex if e[3] < e[2]))


# ---------- 3. Unravelling destination on the wand test ----------
print()
print("3) Unravelling wand test: T4 lightning damage to spells; weights T4 800, T3 800, T2 250, T1 60; 257 cases")
obs_pct = {1: 2.72, 2: 16.73, 3: 80.54}
n_cases = 257
higher = {3: 800, 2: 250, 1: 60}  # weights of the tiers above T4
# rank multiplier 1 for the highest tier (T1), 2 for the second (T2), 3 for the third (T3)
readingA = {1: 60 * 1, 2: 250 * 2, 3: 800 * 3}
readingB = {1: 60, 2: 60 + 250, 3: 60 + 250 + 800}  # own weight plus the tiers above it
readingC = {1: 60, 2: 250, 3: 800}
for name, wts in (("A rank multipliers", readingA), ("B cumulative", readingB), ("C plain weights", readingC)):
    z = sum(wts.values())
    exp = {t: wts[t] / z for t in wts}
    x2 = sum((n_cases * obs_pct[t] / 100 - n_cases * exp[t]) ** 2 / (n_cases * exp[t]) for t in wts)
    print(f" {name}: T1/T2/T3 = " + " / ".join(f"{100 * exp[t]:.2f}" for t in (1, 2, 3)) + f" %, chi2 {x2:.2f} on 2 df, p {chi2_sf(x2, 2):.4f}")
