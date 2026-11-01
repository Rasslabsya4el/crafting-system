"""Ticket #175: fit the recombinator's selection exponent alpha from the guide author's sheet.

Usage: python -I fit.py ROWS_JSON OUT_JSON [--boot N] [--sim N] [--seed S]

Model (#90 section 5): on one side the kept mods are drawn one after another without replacement from the pooled
entries, P(next = e) proportional to weight(e)**alpha, and every entry of the picked mod group leaves the pool. The
count of kept mods does not depend on weights (the guide's count table), so each observation is the probability of
the kept set given its size. Standard library only.
"""
import itertools
import json
import math
import random
import sys

GRID = [round(-3.0 + 0.01 * i, 2) for i in range(901)]  # alpha from -3 to 6
CHI2_95 = 3.841458820694124
SPELL_WEIGHTS = [40, 100, 150, 200, 400, 500, 800, 1000, 1500]  # spell damage prefix weights on wands, 3.29.3.3


def set_prob(entries, kept, alpha):
    """Probability that the set `kept` of groups is what k = len(kept) successive draws leave.
    entries: list of (group, weight) with weight > 0."""
    powered = [(g, math.exp(alpha * math.log(w))) for g, w in entries]
    total = 0.0
    for order in itertools.permutations(kept):
        remaining, p = powered, 1.0
        for g in order:
            s_all = sum(w for _, w in remaining)
            s_g = sum(w for gg, w in remaining if gg == g)
            p *= s_g / s_all
            remaining = [(gg, w) for gg, w in remaining if gg != g]
        total += p
    return total


def pool_entries(side, mode, dup, spell=None, weight_key="weight"):
    """(group, weight) list. `dup`: 'own' keeps each copy's own tier weight, 'max' and 'min' give all copies of a
    group the largest or smallest weight among them (open point 3 of #90)."""
    out = []
    for e in side["pool"]:
        if e["kind"] == "nuisance":
            w = spell
        else:
            w = e["weight_low"] if (mode == "low" and e["kind"] == "natural" and "weight_low" in e) else e.get(weight_key) or e["weight"]
        out.append([e["group"], float(w)])
    if dup != "own":
        by = {}
        for g, w in out:
            by.setdefault(g, []).append(w)
        pick = max if dup == "max" else min
        out = [[g, pick(by[g])] for g, _ in out]
    return [tuple(x) for x in out]


def side_loglik_curve(entries, kept, grid):
    return [math.log(max(set_prob(entries, kept, a), 1e-300)) for a in grid]


def profile(curves):
    """Sum of per-side curves -> (mle, lo, hi, curve, max loglik)."""
    n = len(GRID)
    tot = [sum(c[i] for c in curves) for i in range(n)]
    best = max(range(n), key=lambda i: tot[i])
    mx = tot[best]

    def edge(step):
        i = best
        while 0 <= i + step < n and 2 * (mx - tot[i + step]) <= CHI2_95:
            i += step
        j = i + step
        if not (0 <= j < n):
            return None  # the interval runs off the grid
        a, b = 2 * (mx - tot[i]), 2 * (mx - tot[j])
        return GRID[i] + (GRID[j] - GRID[i]) * (CHI2_95 - a) / (b - a)
    return {"mle": GRID[best], "lo": edge(-1), "hi": edge(1), "loglik": mx, "curve": tot}


def lr_stat(prof, alpha):
    return 2 * (prof["loglik"] - prof["curve"][GRID.index(round(alpha, 2))])


def p_chi2_1(x):
    return math.erfc(math.sqrt(max(x, 0) / 2))


def build(sides, mode="central", dup="own", spell=None):
    return [(pool_entries(s, mode, dup, spell), sorted({e["group"] for e in s["kept"]})) for s in sides]


def curves_for(sides, **kw):
    return [side_loglik_curve(ent, kept, GRID) for ent, kept in build(sides, **kw)]


def discord_profile(sides):
    """Spell-damage weight is not recorded: report each fixed value and the profile over the nuisance."""
    per_s = {s: profile(curves_for(sides, spell=s)) for s in SPELL_WEIGHTS}
    n = len(GRID)
    env = [max(per_s[s]["curve"][i] for s in SPELL_WEIGHTS) for i in range(n)]
    best = max(range(n), key=lambda i: env[i])
    fake = {"curve": env, "loglik": env[best], "mle": GRID[best]}
    out = profile([env])  # reuse the edge search on the envelope
    return per_s, out


def shape_fit(sides, mode="central"):
    """P proportional to weight**alpha * tier_and_better**beta on a coarse grid; returns max loglik by model."""
    data = []
    for s in sides:
        ent = []
        for e in s["pool"]:
            w = e["weight_low"] if mode == "low" and "weight_low" in e else e["weight"]
            ent.append((e["group"], float(w), float(e["weight_cum"])))
        data.append((ent, sorted({e["group"] for e in s["kept"]})))

    def ll(a, b):
        t = 0.0
        for ent, kept in data:
            t += math.log(max(set_prob([(g, math.exp(a * math.log(w) + b * math.log(c))) for g, w, c in ent], kept, 1.0), 1e-300))
        return t
    best = {}
    ag = [round(-1 + 0.1 * i, 1) for i in range(0, 41)]
    bg = [round(-1 + 0.1 * i, 1) for i in range(0, 31)]
    grid2 = {(a, b): ll(a, b) for a in ag for b in bg}
    best["alpha_only"] = max((v, a) for (a, b), v in grid2.items() if b == 0.0)
    best["beta_only"] = max((v, b) for (a, b), v in grid2.items() if a == 0.0)
    best["both"] = max((v, a, b) for (a, b), v in grid2.items())
    return best


def class_free_fit(sides):
    """Shape check: give the weight classes 250 and 500 free multipliers against 1000 instead of the power law
    (250/1000)**alpha. Same sides for both fits: those whose weights are all 250, 500 or 1000."""
    use = [s for s in sides if all(e["weight"] in (250, 500, 1000) for e in s["pool"])]
    data = [([(e["group"], e["weight"]) for e in s["pool"]], sorted({e["group"] for e in s["kept"]})) for s in use]
    power = profile([side_loglik_curve(ent, kept, GRID) for ent, kept in data])
    axis = [math.exp(math.log(0.02) + (math.log(2.0) - math.log(0.02)) * i / 40) for i in range(41)]
    best = (-1e300, None, None)
    for t250 in axis:
        for t500 in axis:
            tot = 0.0
            for ent, kept in data:
                ent2 = [(g, {250: t250, 500: t500, 1000: 1.0}[w]) for g, w in ent]
                tot += math.log(max(set_prob(ent2, kept, 1.0), 1e-300))
            if tot > best[0]:
                best = (tot, t250, t500)
    lr = 2 * (best[0] - power["loglik"])
    return {"sides": len(use), "power_law_loglik": round(power["loglik"], 3), "power_law_alpha": power["mle"],
            "free_loglik": round(best[0], 3), "free_mult_250": round(best[1], 3), "free_mult_500": round(best[2], 3),
            "power_law_mult_250": round(0.25 ** power["mle"], 3), "power_law_mult_500": round(0.5 ** power["mle"], 3),
            "LR_free_vs_power": round(lr, 3), "p_value_1df": p_chi2_1(lr)}


def inclusion(entries, k, alpha):
    """P(group kept) for each group in a pool when k are kept."""
    groups = sorted({g for g, _ in entries})
    probs = {g: 0.0 for g in groups}
    for subset in itertools.combinations(groups, k):
        p = set_prob(entries, list(subset), alpha)
        for g in subset:
            probs[g] += p
    return probs


def calibration(sides, alpha, **kw):
    """Observed against expected number of kept mods, by weight class of the entry."""
    cells = {}
    for (ent, kept), side in zip(build(sides, **kw), sides):
        probs = inclusion(ent, len(kept), alpha)
        wmax = {}
        for g, w in ent:
            wmax[g] = max(wmax.get(g, 0), w)
        for g, p in probs.items():
            key = int(wmax[g])
            c = cells.setdefault(key, [0, 0.0, 0.0])
            c[0] += 1
            c[1] += p
            c[2] += 1 if g in kept else 0
    return {k: {"entries": v[0], "expected_kept": round(v[1], 2), "observed_kept": int(v[2])} for k, v in sorted(cells.items())}


def sample_kept(entries, k, alpha, rng):
    remaining = [(g, math.exp(alpha * math.log(w))) for g, w in entries]
    kept = []
    for _ in range(k):
        r = rng.random() * sum(w for _, w in remaining)
        acc = 0.0
        for g, w in remaining:
            acc += w
            if r <= acc:
                kept.append(g)
                break
        remaining = [(gg, w) for gg, w in remaining if gg != kept[-1]]
    return sorted(kept)


COARSE = [round(-2 + 0.1 * i, 1) for i in range(0, 61)]


def fit_coarse(data):
    best, arg = -1e300, None
    for a in COARSE:
        t = sum(math.log(max(set_prob(ent, kept, a), 1e-300)) for ent, kept in data)
        if t > best:
            best, arg = t, a
    return best, arg


def gof_sim(data, alpha_hat, n_sim, rng):
    """Parametric bootstrap of the maximised log-likelihood: a model that does not describe the data gives an
    observed value below almost all simulated ones. Also the per-side loglik sum at alpha_hat, for reference."""
    obs, _ = fit_coarse(data)
    sims = []
    for _ in range(n_sim):
        sim = [(ent, sample_kept(ent, len(kept), alpha_hat, rng)) for ent, kept in data]
        sims.append(fit_coarse(sim)[0])
    p_low = sum(1 for x in sims if x <= obs) / n_sim
    return {"observed_max_loglik": round(obs, 3), "sim_mean": round(sum(sims) / n_sim, 3), "p_low": p_low, "n_sim": n_sim}


def bootstrap(per_side_curves, n_boot, rng):
    n, m = len(per_side_curves), len(GRID)
    ests = []
    for _ in range(n_boot):
        tot = [0.0] * m
        for _ in range(n):
            c = per_side_curves[rng.randrange(n)]
            for i in range(m):
                tot[i] += c[i]
        ests.append(GRID[max(range(m), key=lambda i: tot[i])])
    ests.sort()
    return {"n_boot": n_boot, "q025": ests[int(0.025 * n_boot)], "median": ests[n_boot // 2], "q975": ests[int(0.975 * n_boot) - 1]}


def rare_target_example(alpha):
    """The #90 section 5 example: a pool of four prefixes with weights 25, 1000, 1000, 400 and the guide's count
    row 4 (10/60/30); the chance that the rare mod is kept."""
    ent = [("rare", 25.0), ("c1", 1000.0), ("c2", 1000.0), ("c3", 400.0)]
    counts = {1: 0.10, 2: 0.60, 3: 0.30}
    return sum(pk * inclusion(ent, k, alpha)["rare"] for k, pk in counts.items())


def summarize(prof):
    return {k: prof[k] for k in ("mle", "lo", "hi", "loglik")}


def main(rows_json, out_json, n_boot, n_sim, seed):
    rng = random.Random(seed)
    sides = [s for s in json.load(open(rows_json, encoding="utf-8"))["sides"] if not s["drop_reason"]]
    tabs = {"gloves": [s for s in sides if s["tab"] == "gloves"], "misc": [s for s in sides if s["tab"] == "misc"],
            "discord_wands": [s for s in sides if s["tab"] == "discord_wands"]}
    natural = tabs["gloves"] + tabs["misc"]
    res = {"counts": {k: len(v) for k, v in tabs.items()}}

    # per tab and pooled (central choices)
    out = {}
    for name, grp in (("gloves", tabs["gloves"]), ("misc", tabs["misc"]), ("gloves+misc", natural)):
        out[name] = summarize(profile(curves_for(grp)))
    per_s, env = discord_profile(tabs["discord_wands"])
    out["discord_wands (spell weight profiled)"] = summarize(env)
    out["discord_wands by fixed spell weight"] = {str(s): summarize(p) for s, p in per_s.items()}
    # pooled: natural curves + discord envelope over s
    nat_curves = curves_for(natural)
    pooled_by_s = {}
    for s in SPELL_WEIGHTS:
        pooled_by_s[s] = profile(nat_curves + curves_for(tabs["discord_wands"], spell=s))
    m = len(GRID)
    penv = [max(pooled_by_s[s]["curve"][i] for s in SPELL_WEIGHTS) for i in range(m)]
    out["pooled (spell weight profiled)"] = summarize(profile([penv]))
    out["pooled by fixed spell weight"] = {str(s): summarize(p) for s, p in pooled_by_s.items()}
    res["fits"] = out

    # tests against alpha = 0 and alpha = 1
    tests = {}
    for name, prof in (("gloves+misc", profile(nat_curves)), ("discord (s=1500)", per_s[1500]), ("pooled (s=1500)", pooled_by_s[1500])):
        tests[name] = {"LR_vs_alpha0": round(lr_stat(prof, 0.0), 3), "p_alpha0": p_chi2_1(lr_stat(prof, 0.0)),
                       "LR_vs_alpha1": round(lr_stat(prof, 1.0), 3), "p_alpha1": p_chi2_1(lr_stat(prof, 1.0))}
    # sides without chaos resistance do not depend on the weight assumed for an essence-made chaos mod
    pre = [s for s in natural if s["side"] == "prefix"]
    pp = profile(curves_for(pre))
    tests["gloves+misc prefix sides only (no chaos)"] = {
        "sides": len(pre), "mle": pp["mle"], "LR_vs_alpha0": round(lr_stat(pp, 0.0), 3), "p_alpha0": p_chi2_1(lr_stat(pp, 0.0)),
        "LR_vs_alpha1": round(lr_stat(pp, 1.0), 3), "p_alpha1": p_chi2_1(lr_stat(pp, 1.0))}
    het = 2 * (profile(nat_curves)["loglik"] + per_s[1500]["loglik"] - pooled_by_s[1500]["loglik"])
    tests["heterogeneity gloves+misc vs wand tab (s=1500), 1 df"] = {"LR": round(het, 3), "p": p_chi2_1(het)}
    res["tests"] = tests

    # sensitivity of the central pooled estimate (gloves+misc only, so no nuisance)
    sens = {}
    for label, kw, subset in (
            ("central", {}, natural),
            ("typed groups at their smallest weight", {"mode": "low"}, natural),
            ("duplicate tiers: largest weight for all copies", {"dup": "max"}, natural),
            ("duplicate tiers: smallest weight for all copies", {"dup": "min"}, natural),
            ("drop ambiguous cell readings", {}, [s for s in natural if not any(e.get("ambiguous") for e in s["pool"])]),
            ("prefix sides only", {}, [s for s in natural if s["side"] == "prefix"]),
            ("suffix sides only", {}, [s for s in natural if s["side"] == "suffix"]),
            ("suffix sides with chaos resistance", {}, [s for s in natural if s["side"] == "suffix" and any(e["group"] == "ChaosResistance" for e in s["pool"])])):
        if subset:
            sens[label] = {**summarize(profile(curves_for(subset, **kw))), "sides": len(subset)}
    res["sensitivity_gloves_misc"] = sens
    # how many sides hold several tiers of one group with different weights
    several = 0
    for s in natural:
        by = {}
        for e in s["pool"]:
            by.setdefault(e["group"], set()).add(e["weight"])
        if any(len(v) > 1 for v in by.values()):
            several += 1
    res["sides_with_unequal_duplicate_tiers"] = several
    res["sides_with_any_duplicate_group"] = sum(1 for s in natural if len({e["group"] for e in s["pool"]}) < len(s["pool"]))

    # goodness of fit
    a_hat = out["gloves+misc"]["mle"]
    data = build(natural)
    gof = {"gloves+misc": gof_sim(data, a_hat, n_sim, rng) if n_sim else None,
           "calibration_at_mle": calibration(natural, a_hat),
           "calibration_at_alpha0": calibration(natural, 0.0), "calibration_at_alpha1": calibration(natural, 1.0)}
    sp = out["pooled (spell weight profiled)"]
    best_s = max(SPELL_WEIGHTS, key=lambda s: pooled_by_s[s]["loglik"])
    gof["discord_calibration_s1500"] = calibration(tabs["discord_wands"], per_s[1500]["mle"], spell=1500)
    gof["shape_fit_gloves_misc"] = {k: list(v) for k, v in shape_fit(natural).items()}
    gof["weight_class_free_fit"] = class_free_fit(natural)
    res["goodness_of_fit"] = gof

    # bootstrap over sides
    if n_boot:
        disc_curves = curves_for(tabs["discord_wands"], spell=1500)
        res["bootstrap"] = {"gloves+misc": bootstrap(nat_curves, n_boot, rng),
                            "discord (s=1500)": bootstrap(disc_curves, n_boot, rng),
                            "pooled (s=1500)": bootstrap(nat_curves + disc_curves, n_boot, rng)}

    # what the fitted alpha does to the #90 example
    ex = {}
    for label, a in (("alpha=0", 0.0), ("alpha=1", 1.0), ("gloves+misc mle", out["gloves+misc"]["mle"]),
                     ("gloves+misc lo", out["gloves+misc"]["lo"]), ("gloves+misc hi", out["gloves+misc"]["hi"]),
                     ("pooled mle", sp["mle"]), ("pooled lo", sp["lo"]), ("pooled hi", sp["hi"])):
        if a is not None:
            ex[label] = {"alpha": a, "p_rare_kept": round(rare_target_example(a), 4)}
    res["rare_target_example"] = ex
    g = out["gloves+misc"]
    res["chaos_retention_ratio"] = {"definition": "(250/1000)**alpha: how often a weight-250 mod is kept relative to a weight-1000 mod",
                                    "mle": round(0.25 ** g["mle"], 3), "at_alpha_lo": round(0.25 ** g["lo"], 3),
                                    "at_alpha_hi": round(0.25 ** g["hi"], 3)}
    res["pooled_best_spell_weight"] = best_s
    # twice the log-likelihood drop from the maximum, every 0.25 in alpha, for plotting or reading off intervals
    def coarse(prof):
        return {str(a): round(2 * (prof["loglik"] - prof["curve"][GRID.index(a)]), 2) for a in GRID if round(a * 4) == a * 4}
    res["deviance_curves"] = {"gloves+misc": coarse(profile(nat_curves)),
                              "discord (s=1500)": coarse(per_s[1500]), "pooled (s=1500)": coarse(pooled_by_s[1500])}
    json.dump(res, open(out_json, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: res[k] for k in ("counts", "fits", "tests")}, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--boot": 0, "--sim": 0, "--seed": 175}
    pos = []
    i = 0
    while i < len(args):
        if args[i] in opt:
            opt[args[i]] = int(args[i + 1])
            i += 2
        else:
            pos.append(args[i])
            i += 1
    main(pos[0], pos[1], opt["--boot"], opt["--sim"], opt["--seed"])
