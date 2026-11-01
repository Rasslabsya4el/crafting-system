"""Ticket #271 (c): the Orb of Unravelling on the sheet's tab "Unravelling data" (36,598 mods on 9,373 orbs).

Usage (repository root, Python 3.12 or later, pinned game data in CACHE_DIR):
    python research/271/unravel.py RAW_DIR CACHE_DIR OUT_JSON

One row of the tab is one mod of one orb. The tab holds about two million lines of text because each row carries the item
text before and after. Questions: the shape of the chance that a mod rises, with `x = s * W_up / (2 * W_side)` taken from
our data (ADR-0044) and from the author's own columns, and which reading of the destination tier (rank multipliers,
cumulative, weights only) predicts the tier the mod went to.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parent)]

from crafting_system.data.load import load_game_data  # noqa: E402
from crafting_system.items import Item, Rarity  # noqa: E402
from sheetpool import game_pool  # noqa: E402
from stats_util import chi2_sf  # noqa: E402


def load_rows(path: Path):
    text = Path(path).read_bytes().decode("utf-8", errors="replace")
    keep = ("strands", "item_level", "mod_family", "mod_before_id", "mod_after_id", "tier_before", "tier_after",
            "tiers_upgraded", "item_class", "base_name", "upgrade_chance", "total_prefix_weight", "total_suffix_weight",
            "upgrade_candidate_weights", "mod_count")
    return [{k: r[k] for k in keep} for r in csv.DictReader(io.StringIO(text, newline=""))]


class Pools:
    """The pool of a base at an item level, grouped by mod type and side, with the totals of each side."""

    def __init__(self, data):
        self.data = data
        self.bases = defaultdict(list)
        for b in data.base_items.values():
            if b.domain == "item":
                self.bases[b.name].append(b)
        self.cache = {}

    def get(self, base_name, level):
        key = (base_name, level)
        if key not in self.cache:
            base = self.bases[base_name][0]
            cands = game_pool(self.data, Item(base_id=base.id, item_level=level, rarity=Rarity.RARE))
            groups = defaultdict(list)
            totals = {"prefix": 0.0, "suffix": 0.0}
            for c in cands:
                groups[(c.mod.type, c.side.value)].append(c)
                totals[c.side.value] += float(c.weight)
            for g in groups.values():
                g.sort(key=lambda c: -c.mod.required_level)
            self.cache[key] = (groups, totals)
        return self.cache[key]


def keep_count(tiers: int, strands: int) -> int:
    return 200 * (tiers - 1) // (200 + (5 * strands + 95 if strands >= 1 else 0)) + 1


def loglik_chance(p: np.ndarray, up: np.ndarray) -> float:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(np.sum(np.where(up, np.log(p), np.log1p(-p))))


def golden(f, lo, hi, steps=60):
    """Maximise a one-parameter function on [lo, hi] (golden section)."""
    phi = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(steps):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = f(d)
    x = (a + b) / 2
    return x, f(x)


def binned(x, up, edges):
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (x >= lo) & (x < hi)
        n = int(sel.sum())
        if n:
            out.append({"x_from": lo, "x_to": hi, "mods": n, "observed_rate": float(up[sel].mean()),
                        "predicted_mean_if_p_is_x": float(np.minimum(x[sel], 1).mean())})
    return out


def main() -> None:
    raw, cache, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    data = load_game_data(cache_dir=cache)
    pools = Pools(data)
    rows = load_rows(raw / "unravel.csv")
    n = len(rows)
    s = np.zeros(n)
    w_up = np.zeros(n)
    w_side = np.zeros(n)
    their_up = np.zeros(n)
    their_side = np.zeros(n)
    their_p = np.zeros(n)
    up = np.zeros(n, dtype=bool)
    mod_count = np.zeros(n, dtype=int)
    is_wand = np.zeros(n, dtype=bool)
    dest = []  # (row index, candidate weights top to bottom, index of the destination among them, T, K, dest index in whole table)
    left_out = Counter()
    for i, r in enumerate(rows):
        mb, ma = data.mods[r["mod_before_id"]], data.mods[r["mod_after_id"]]
        groups, totals = pools.get(r["base_name"], int(r["item_level"]))
        side = mb.generation_type.value if hasattr(mb.generation_type, "value") else str(mb.generation_type)
        group = groups[(mb.type, side)]
        above = [c for c in group if c.mod.required_level > mb.required_level]
        s[i] = int(r["strands"])
        w_up[i] = float(sum(c.weight for c in above))
        w_side[i] = totals[side]
        their_up[i] = float(r["upgrade_candidate_weights"])
        their_side[i] = float(r["total_prefix_weight" if side == "prefix" else "total_suffix_weight"])
        their_p[i] = float(r["upgrade_chance"])
        up[i] = int(r["tiers_upgraded"]) > 0
        mod_count[i] = int(r["mod_count"])
        is_wand[i] = r["item_class"] == "Wands"
        if up[i]:
            ids = [c.mod.id for c in above]
            if ma.id in ids:
                index_in_table = [c.mod.id for c in group].index(ma.id)
                dest.append((i, [float(c.weight) for c in above], ids.index(ma.id), len(group), int(s[i]), index_in_table))
            else:
                left_out["upgraded to a mod outside the tiers above in our pool"] += 1
    x = s * w_up / (2 * w_side)
    x_their = s * their_up / (2 * their_side)
    result: dict = {"game_data_version": data.version, "rows": n, "orbs_in_the_post": 9373, "left_out": dict(left_out)}
    result["our_weights_equal_the_authors"] = {
        "W_up_equal": int(np.sum(np.isclose(w_up, their_up))), "W_up_differ": int(np.sum(~np.isclose(w_up, their_up))),
        "W_side_equal": int(np.sum(np.isclose(w_side, their_side))), "W_side_differ": int(np.sum(~np.isclose(w_side, their_side))),
        "W_side_differ_on_wands": int(np.sum(~np.isclose(w_side, their_side) & is_wand)),
        "W_side_differ_on_other_bases": int(np.sum(~np.isclose(w_side, their_side) & ~is_wand)),
        "author_chance_equals_his_formula": int(np.sum(np.isclose(np.minimum(x_their, 1), their_p))),
    }

    # --- the breakpoint ---
    for name, xx in (("ours", x), ("authors", x_their)):
        guaranteed = xx >= 1
        failed_below = up[(xx < 1) & (xx > 0)]
        result[f"breakpoint_{name}"] = {
            "mods_with_x_at_least_1": int(guaranteed.sum()),
            "of_them_not_raised": int((~up[guaranteed]).sum()),
            "mods_with_x_0": int((xx == 0).sum()),
            "of_them_raised": int(up[xx == 0].sum()),
            "largest_x_below_1_of_a_mod_not_raised": float(xx[(~up) & (xx < 1) & (xx > 0)].max()),
            "mods_not_raised_with_x_over_0.95": int(((~up) & (xx >= 0.95) & (xx < 1)).sum()),
            "mods_with_x_over_0.95_below_1": int(((xx >= 0.95) & (xx < 1)).sum()),
        }

    # --- the curve below the breakpoint ---
    live = (x > 0) & (x < 1)
    edges = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    result["calibration_ours"] = binned(x[live], up[live], edges)
    result["calibration_authors"] = binned(x_their[(x_their > 0) & (x_their < 1)], up[(x_their > 0) & (x_their < 1)], edges)

    def ll_model(p, mask=None):
        return loglik_chance(p if mask is None else p[mask], up if mask is None else up[mask])

    fits = {}
    for name, xx in (("ours", x), ("authors", x_their)):
        base = ll_model(np.minimum(xx, 1))
        a_hat, ll_a = golden(lambda a: ll_model(np.minimum(a * xx, 1)), 0.5, 2.0)
        k_hat, ll_k = golden(lambda k: ll_model(1 - (1 - np.minimum(xx, 1)) ** k), 0.3, 3.0)
        # a * x^b, capped at 1
        best = (-1e18, None)
        for b in np.arange(0.7, 1.31, 0.02):
            a_b, ll_b = golden(lambda a: ll_model(np.minimum(a * np.maximum(xx, 1e-12) ** b, 1)), 0.3, 3.0, steps=40)
            if ll_b > best[0]:
                best = (ll_b, (float(a_b), float(b)))
        # the guarantee at x >= 1 is kept in the first two; the empirical ceiling is the binned rate in 40 bins of x
        qs = np.quantile(xx[(xx > 0) & (xx < 1)], np.linspace(0, 1, 41))
        ll_bins = 0.0
        for lo, hi in zip(qs[:-1], qs[1:]):
            sel = (xx >= lo) & (xx < hi) & (xx > 0)
            if sel.sum():
                rate = np.clip(up[sel].mean(), 1e-9, 1 - 1e-9)
                ll_bins += float(np.sum(np.where(up[sel], np.log(rate), np.log1p(-rate))))
        fits[name] = {
            "loglik_p_equals_min(1,x)": base,
            "a_hat_for_min(1,a*x)": a_hat, "loglik_a": ll_a,
            "k_hat_for_1-(1-x)^k": k_hat, "loglik_k": ll_k,
            "a_b_hat_for_min(1,a*x^b)": best[1], "loglik_ab": best[0],
            "loglik_of_40_free_bins_on_0<x<1_plus_guarantee": ll_bins + 0.0,
        }
        # standard error of a by the curvature at the maximum
        h = 0.005
        f0, fp_, fm = [ll_model(np.minimum((a_hat + d) * xx, 1)) for d in (0, h, -h)]
        fits[name]["a_hat_se"] = float(1 / math.sqrt(max(-(fp_ - 2 * f0 + fm) / h**2, 1e-12)))
    result["chance_fits"] = fits
    # the same on the bases other than wands (the author's wand columns lack the 0.5 weight of attack mods)
    sel = ~is_wand
    sub = {}
    for name, xx in (("ours", x), ("authors", x_their)):
        a_hat, ll_a = golden(lambda a: loglik_chance(np.minimum(a * xx[sel], 1), up[sel]), 0.5, 2.0)
        sub[name] = {"mods": int(sel.sum()), "loglik_min(1,x)": loglik_chance(np.minimum(xx[sel], 1), up[sel]), "a_hat": a_hat, "loglik_a": ll_a}
    result["chance_fits_without_wands"] = sub
    # does the number of mods on the item matter?
    by_count = {}
    for k in sorted(set(mod_count.tolist())):
        m = live & (mod_count == k)
        if m.sum() >= 50:
            by_count[str(k)] = {"mods": int(m.sum()), "observed_rate": float(up[m].mean()), "predicted_mean": float(np.minimum(x[m], 1).mean())}
    result["by_mods_on_the_item"] = by_count
    # strands as a separate input: p = min(1, a * s^b * r^c) with r = W_up / (2 W_side)
    r_ratio = w_up / (2 * w_side)

    def ll3(a, b, c):
        with np.errstate(divide="ignore"):
            p = np.minimum(a * np.maximum(s, 1e-12) ** b * np.maximum(r_ratio, 1e-12) ** c, 1.0)
        p = np.where(r_ratio == 0, 0.0, p)
        return loglik_chance(p, up)

    point = np.array([1.0, 1.0, 1.0])
    step = np.array([0.05, 0.05, 0.05])
    best = ll3(*point)
    for _ in range(40):
        improved = False
        for k in range(3):
            for d in (step[k], -step[k]):
                trial = point.copy()
                trial[k] += d
                v = ll3(*trial)
                if v > best + 1e-9:
                    best, point, improved = v, trial, True
        if not improved:
            step = step / 2
            if step.max() < 1e-4:
                break
    hess = np.zeros((3, 3))
    h = 0.01
    for i in range(3):
        for j in range(3):
            def at(di, dj):
                t = point.copy()
                t[i] += di
                t[j] += dj
                return ll3(*t)
            hess[i, j] = (at(h, h) - at(h, -h) - at(-h, h) + at(-h, -h)) / (4 * h * h)
    try:
        se = np.sqrt(np.diag(np.linalg.inv(-hess)))
    except np.linalg.LinAlgError:
        se = np.full(3, float("nan"))
    result["strands_and_weights_as_separate_inputs"] = {
        "a_b_c": point.tolist(), "standard_errors": se.tolist(), "loglik": best, "loglik_at_1_1_1": ll3(1.0, 1.0, 1.0),
        "meaning": "p = min(1, a * s^b * (W_up / (2 W_side))^c)",
    }

    # --- the destination ---
    informative = 0
    totals = {k: 0.0 for k in ("A_rank_multipliers", "B_cumulative", "C_weights_only", "D_uniform")}
    alpha_grid = [-0.5, 0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    alpha = {str(a): 0.0 for a in alpha_grid}
    dest_cut_outside = 0
    pa_obs, pb_obs, pc_obs = [], [], []
    for i, weights, j, total_tiers, strands, index_in_table in dest:
        w = np.array(weights)
        m = len(w)
        ranks = np.arange(1, m + 1, dtype=float)
        if len(set(weights)) > 1:
            informative += 1
            va, vb, vc = w * ranks, np.cumsum(w), w
            pa_obs.append(va[j] / va.sum())
            pb_obs.append(vb[j] / vb.sum())
            pc_obs.append(vc[j] / vc.sum())
        schemes = {
            "A_rank_multipliers": w * ranks,
            "B_cumulative": np.cumsum(w),
            "C_weights_only": w,
            "D_uniform": np.ones(m),
        }
        for k, v in schemes.items():
            totals[k] += math.log(v[j] / v.sum())
        for a in alpha_grid:
            v = w * ranks**a
            alpha[str(a)] += math.log(v[j] / v.sum())
        keep = keep_count(total_tiers, strands)
        if index_in_table >= keep:
            dest_cut_outside += 1
    result["destination"] = {
        "raised_mods_used": len(dest),
        "mods_with_unequal_candidate_weights": informative,
        "loglik": totals,
        "loglik_rank_multiplier_power": alpha,
        "destinations_outside_the_tiers_the_strand_cut_would_keep": dest_cut_outside,
    }
    # A against B on the mods whose candidate tiers differ in weight (on equal weights the two readings are the same)
    pa, pb = np.array(pa_obs), np.array(pb_obs)
    d = np.log(pb) - np.log(pa)
    mix = lambda t: float(np.log((1 - t) * pa + t * pb).sum())  # noqa: E731
    t_hat, ll_t = golden(mix, 0.0, 1.0)
    def edge(direction):
        t = t_hat
        while 0 <= t + direction * 0.005 <= 1 and ll_t - mix(t + direction * 0.005) <= 1.92:
            t += direction * 0.005
        return t
    result["destination_A_vs_B"] = {
        "mods_with_unequal_weights": len(pa),
        "loglik_B_minus_A": float(d.sum()), "se": float(d.std(ddof=1) * math.sqrt(len(d))),
        "z": float(d.sum() / (d.std(ddof=1) * math.sqrt(len(d)))),
        "mixture_weight_on_B_hat": t_hat, "mixture_95_interval": [edge(-1), edge(1)],
        "loglik_C_weights_only_minus_A": float(np.log(np.array(pc_obs)).sum() - np.log(pa).sum()),
    }
    # which reading can the data reject? replay the same mods under each reading (parametric bootstrap on the distinct
    # candidate-weight lists, 4,000 replays) and see how often a replay gives a log-likelihood difference B - A as far
    # from its own expectation as the observed one
    unique = defaultdict(lambda: np.zeros(0, dtype=int))
    for _, weights, j, _, _, _ in dest:
        if len(set(weights)) > 1:
            key = tuple(weights)
            if key not in unique or len(unique[key]) == 0:
                unique[key] = np.zeros(len(weights), dtype=int)
            unique[key][j] += 1
    keys = list(unique)
    pa_k = [np.array(k) * np.arange(1, len(k) + 1) for k in keys]
    pa_k = [v / v.sum() for v in pa_k]
    pb_k = [np.cumsum(np.array(k)) for k in keys]
    pb_k = [v / v.sum() for v in pb_k]
    delta_k = [np.log(b) - np.log(a) for a, b in zip(pa_k, pb_k)]
    counts_k = [unique[k] for k in keys]
    observed_delta = float(sum((c * dk).sum() for c, dk in zip(counts_k, delta_k)))
    rng = np.random.default_rng(271)
    replay = {}
    for name, probs in (("under_A", pa_k), ("under_B", pb_k)):
        sims = np.zeros(4000)
        for rep in range(4000):
            sims[rep] = sum((rng.multinomial(int(c.sum()), p) * dk).sum() for c, p, dk in zip(counts_k, probs, delta_k))
        replay[name] = {"mean": float(sims.mean()), "sd": float(sims.std()),
                        "share_of_replays_as_favourable_to_B_as_observed": float((sims >= observed_delta).mean()),
                        "share_of_replays_as_favourable_to_A_as_observed": float((sims <= observed_delta).mean())}
    result["destination_replay"] = {"distinct_weight_lists": len(keys), "observed_loglik_B_minus_A": observed_delta, **replay}
    # per-tier-count check of A: observed destination shares against A for the mods with equal weights
    groups = defaultdict(list)
    for i, weights, j, total_tiers, strands, idx in dest:
        if len(set(weights)) == 1:
            groups[len(weights)].append(j)
    chi_rows = {}
    for m, js in groups.items():
        if m < 2 or len(js) < 50:
            continue
        obs = np.bincount(js, minlength=m).astype(float)
        exp = np.arange(1, m + 1, dtype=float)
        exp = exp / exp.sum() * len(js)
        stat = float(((obs - exp) ** 2 / exp).sum())
        chi_rows[str(m)] = {"raised_mods": len(js), "chi2_rank_multipliers": stat, "df": m - 1, "p": chi2_sf(stat, m - 1)}
    result["destination_equal_weights_chi_square"] = chi_rows
    # the wand test of the post, again: T4 lightning damage to spells on wands (800, 800, 250, 60)
    wand = []
    for i, weights, j, total_tiers, strands, idx in dest:
        r = rows[i]
        if r["item_class"] == "Wands" and weights == [60.0, 250.0, 800.0] and total_tiers >= 3:
            wand.append(j)
    if wand:
        counts = np.bincount(wand, minlength=3)
        w = np.array([60.0, 250.0, 800.0])
        pa = w * np.arange(1, 4)
        pa = pa / pa.sum()
        pb = np.cumsum(w) / np.cumsum(w).sum()
        result["destination_wand_case"] = {
            "raised_mods": len(wand), "counts_final_T1_T2_T3": counts.tolist(),
            "A_predicted": (pa * len(wand)).round(2).tolist(), "B_predicted": (pb * len(wand)).round(2).tolist(),
            "chi2_A": float(((counts - pa * len(wand)) ** 2 / (pa * len(wand))).sum()),
            "chi2_B": float(((counts - pb * len(wand)) ** 2 / (pb * len(wand))).sum()),
        }
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
