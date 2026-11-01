"""Ticket #271 (d): the Orb of Remembrance on the tab "remembrance data" (2,255 results, one column of counts).

Usage: python -I remembrance.py RAW_DIR OUT_JSON      (needs numpy)

The tab holds only the count after each orb, in the order the author clicked. Whether an orb's result depends on the count
the item had before cannot be read from it directly. What can be read is the order: if the rows are consecutive orbs on
one item (the author rolled a talisman "to 100 with orbs of remembrance"), the previous row is the old count, and the
dependence of a row on the one before it is the dependence of the result on the old count. The sheet does not say the rows
are consecutive orbs on one item, so the tests below speak for that case and stay silent on the other.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parent)]

from sheetpool import read_sheet_csv  # noqa: E402
from stats_util import chi2_sf, normal_sf  # noqa: E402


def phi(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))


def model_probabilities(mu: float, sigma: float, lo_cut: float, hi_cut: float, mode: str) -> np.ndarray:
    """P(result = k) for k = 10..100 of: draw a normal(mu, sigma), redraw while it is outside [lo_cut, hi_cut], then
    report it rounded (mode 'round') or cut down to the whole number (mode 'floor')."""
    ks = np.arange(10, 101)
    if mode == "round":
        a, b = ks - 0.5, ks + 0.5
    else:
        a, b = ks.astype(float), ks + 1.0
    a, b = np.maximum(a, lo_cut), np.minimum(b, hi_cut)
    mass = np.maximum(phi((b - mu) / sigma) - phi((a - mu) / sigma), 0.0)
    return mass / mass.sum()


def main() -> None:
    raw, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    rows = read_sheet_csv(raw / "remem.csv")
    header = list(rows[0].keys())[0]
    x = np.array([float(r[header]) for r in rows if r[header].strip()])
    n = len(x)
    rng = np.random.default_rng(271)
    result: dict = {"results": n, "mean": float(x.mean()), "min": int(x.min()), "max": int(x.max())}

    # --- dependence on the previous row ---
    a, b = x[:-1], x[1:]
    r = float(np.corrcoef(a, b)[0, 1])
    ranks = lambda v: np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(float)  # noqa: E731
    rho = float(np.corrcoef(ranks(a), ranks(b))[0, 1])
    perm = np.array([np.corrcoef(a, rng.permutation(b))[0, 1] for _ in range(5000)])
    slope = float(np.polyfit(a, b, 1)[0])
    resid = b - np.polyval(np.polyfit(a, b, 1), a)
    se_slope = float(resid.std(ddof=2) / (a.std(ddof=1) * math.sqrt(len(a) - 1)))
    cut = [0, 25, 50, 101]
    table = np.zeros((3, 3))
    for u, v in zip(a, b):
        table[np.searchsorted(cut, u, side="right") - 1, np.searchsorted(cut, v, side="right") - 1] += 1
    expected = table.sum(1, keepdims=True) * table.sum(0, keepdims=True) / table.sum()
    chi = float(((table - expected) ** 2 / expected).sum())
    higher = float(np.mean(b > a))
    ties = float(np.mean(b == a))
    result["previous_row"] = {
        "pairs": len(a), "pearson": r, "pearson_permutation_p_two_sided": float((np.abs(perm) >= abs(r)).mean()),
        "pearson_95_half_width": 1.96 / math.sqrt(len(a)), "spearman": rho,
        "slope_of_next_on_previous": slope, "slope_se": se_slope,
        "bins_0_24_25_49_50_100_counts": table.astype(int).tolist(), "chi2_independence": chi, "df": 4, "p": chi2_sf(chi, 4),
        "share_next_higher_than_previous": higher, "share_equal": ties,
        "lag_2_pearson": float(np.corrcoef(x[:-2], x[2:])[0, 1]),
    }
    # mean of the next result after a low and after a high previous result
    low, high = b[a < 25], b[a >= 50]
    result["previous_row"]["mean_next_after_previous_below_25"] = [float(low.mean()), len(low)]
    result["previous_row"]["mean_next_after_previous_50_or_more"] = [float(high.mean()), len(high)]
    result["previous_row"]["difference_of_those_means_z"] = float((high.mean() - low.mean()) / math.sqrt(low.var(ddof=1) / len(low) + high.var(ddof=1) / len(high)))

    # --- the shape: which way of cutting and rounding the normal fits ---
    counts = np.bincount(x.astype(int), minlength=101)[10:101].astype(float)
    variants = {
        "continuous >= 10 and <= 100, rounded": (10.0, 100.0, "round"),
        "continuous >= 10 and < 100.5, rounded (ADR-0043)": (10.0, 100.5, "round"),
        "rounded count between 10 and 100 (continuous 9.5 to 100.5)": (9.5, 100.5, "round"),
        "continuous >= 10 and < 101, cut down": (10.0, 101.0, "floor"),
        "continuous >= 10 and <= 100, cut down": (10.0, 100.0, "floor"),
    }
    shape = {}
    for name, (lo_cut, hi_cut, mode) in variants.items():
        best = (-1e18, None)
        for mu in np.arange(28.0, 42.01, 0.5):
            for sigma in np.arange(20.0, 30.01, 0.5):
                p = model_probabilities(mu, sigma, lo_cut, hi_cut, mode)
                with np.errstate(divide="ignore"):
                    ll = float(np.sum(counts * np.log(np.maximum(p, 1e-300))))
                if ll > best[0]:
                    best = (ll, (float(mu), float(sigma)))
        p35 = model_probabilities(35.0, 25.0, lo_cut, hi_cut, mode)
        ll35 = float(np.sum(counts * np.log(np.maximum(p35, 1e-300))))
        # chi-square on bins of 5 (10-14, ..., 95-100) for N(35, 25)
        edges = list(range(10, 100, 5)) + [101]
        obs_b = [counts[lo - 10: hi - 10].sum() for lo, hi in zip(edges[:-1], edges[1:])]
        exp_b = [p35[lo - 10: hi - 10].sum() * n for lo, hi in zip(edges[:-1], edges[1:])]
        stat = sum((o - e) ** 2 / e for o, e in zip(obs_b, exp_b))
        shape[name] = {
            "best_mu_sigma": best[1], "best_loglik": best[0], "loglik_at_35_25": ll35,
            "mean_of_model_35_25": float((np.arange(10, 101) * p35).sum()),
            "chi2_35_25": stat, "df": len(obs_b) - 1, "p": chi2_sf(stat, len(obs_b) - 1),
            "expected_at_10_and_100": [float(p35[0] * n), float(p35[-1] * n)],
        }
    result["shape"] = shape
    result["observed_at_10_11_99_100"] = [float(counts[0]), float(counts[1]), float(counts[89]), float(counts[90])]
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
