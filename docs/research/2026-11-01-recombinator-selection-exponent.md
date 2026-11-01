# The recombinator's selection exponent, fitted from the guide author's sheet

Research ticket [#175](https://github.com/Rasslabsya4el/crafting-system/issues/175), for the B3 grill ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94)). It narrows the family `P(next = m) ∝ weight(m)^α` that section 5 of the [#90 note](2026-10-31-recombinators-awakener-imprints.md) proposed (on branch `research/recombinators-awakener`) and that ADR-0012 and ADR-0022 leave open. Checked on 2026-11-01 against the pinned repoe-fork export, patch 3.29.3.3. Extract, scripts and the run output are in `research/175/` (see "Reproduce").

## Answer in brief

1. **`α` is about 1: the rule looks weight-proportional.** The Standard gloves tests (the one tab with natural mods of known weight) give `α̂ = 0.92`, 95% profile-likelihood interval **[0.36, 1.56]** (bootstrap over 5,000 resamples of the observations: [0.40, 1.63]), 40 usable observations. Adding the author's wand data, where one weight is not recorded (it has to be assumed), gives `α̂ = 1.23`, interval [0.79, 1.76] at the largest possible weight and up to [0.87, 2.09] at smaller ones.
2. **`α ≤ 0` is excluded, `α = 1` is not.** Equal chance (`α = 0`, Craft of Exile's code) is rejected: likelihood-ratio 11.2 on gloves (p = 0.0008), 39.3 pooled (p = 4e-10). Rare mods favoured (`α < 0`) is further out still. `α = 1` is a good fit (p = 0.79 on gloves, 0.33 pooled). `α > 1` is **not** excluded: the pooled estimate sits above 1 and the upper limits are 1.6 to 2.1, so the family `[0, 1]` of #90 has its upper end in the wrong place: the supported range is about `[0.4, 1.6]`, centred on 1. ADR-0012's reading, that rarer mods are kept at least as often as common ones, is contradicted by the data (as #90 section 5 already said from the qualitative sources).
3. **What it does to the #90 example** (one rare mod, weight 25, in a pool of four prefixes with weights 25, 1000, 1000, 400, count row 4 of the guide): the chance of keeping the rare mod was 55% (`α = 0`) to 3.8% (`α = 1`); at `α̂ = 0.92` it is **4.9%**, at the ends of the gloves interval 25% (`α = 0.36`) and 0.7% (`α = 1.56`), at the ends of the pooled interval 7.4% and 0.4%. The top of the range, 55%, is gone; the bottom drops below 1% if `α` is above 1. The interval is still more than an order of magnitude wide.
4. **What the data cannot say.** They cover weights from 250 to 1500, a ratio of 6 at most; the rare mods of the example (weight 25 to 40) lie ten times further out, so using the power law there is an extrapolation. The sheet does not date its rows (3.25.0, 3.25.1 and Standard are mixed, all before 3.26). The choice of weight for several tiers of one group (#90 open point 3) cannot be tested: no usable observation holds such a pool. The shape check does not prefer another form (section 6).

## 1. Data: what the sheet holds and what was usable

The sheet "3.25 Recomb Diary" (u/Butsicles) has 14 tabs. I read each as CSV (raw extracts kept outside the repo, under `.claude/scratch/175-raw/`; `research/175/rows.json` is the derived extract: one record per combine and side, with the cell text, the resolved game mod, its weight and the reason a side was dropped). One observation is one **side of one combine**: the pooled entries of the two inputs on that side, and the mods that survived. The guide's count table makes the number kept `k` independent of weights, so each observation contributes the probability of the kept set given `k` (all orders of picking, mod-group removal after each pick, a mod on both inputs entering the pool twice).

| Tab | Combines | Sides | Used | Why the others are out |
|---|---|---|---|---|
| Standard recombs on gloves | 41 | 82 | **38** | 17 crafted bench mod in the pool (weight unknown: the export gives crafted mods weight 0) · 14 all weights equal · 8 everything kept · 2 kept mod absent from the pool (rows 9 and 10) · 2 mod in the wrong column (row 37) · 1 one mod group |
| Miscellaneous results (gloves, boots, helmets) | 12 | 24 | **2** | 7 one mod group · 6 all weights equal · 4 empty side · 4 crafted · 1 everything kept |
| Discord data on wands | 40 | 40 (prefix side) | **28** | 12 both mods kept (no choice made); the suffix side of every row is one mod on both items |
| Wands | 6 | | 0 | a crafted spell or cold damage mod in every row |
| Practical use case combines | 34 | | 0 | crafted and exclusive mods (aspect, multimod, Tora's, penetration) in every row; exclusivity rules changed in 3.26 |
| crafted mod combines | 94 | | 0 | tests of crafted-mod weights; bench-crafted mods in every row |
| crafted mod ring combines | 114 | | 0 | header "ALL MODS HERE ARE CRAFTED": crafted against crafted, no natural weight |
| Temple mod transfer | 6 | | 0 | Temple (exclusive) mod in every row |
| Influence blocking chest | 17 | | 0 | breach and influence exclusive mods; the author collects counts only |
| Aggregated Mod data, High mod count combines, Interesting Examples, List of non-exclusive crafted affix mods | | | 0 | counts or notes, no pools |
| Recomb costs | | | 0 | the CSV export is empty |

A side is dropped only for a reason fixed beforehand (a pool I cannot rebuild, a choice that is no choice), never by its outcome. Two readings need saying:

- **Rows with item 2 blank** (the first dozen gloves rows): the pool is item 1's mods alone. The author's own "initial prefixes/suffixes" columns equal item 1's counts, and a final count of 1 from a pool of 6 would be impossible. A side is also dropped when the author's initial or final count disagrees with the cells (none of the used sides is affected).
- **Base type of the gloves** is not recorded. Flat and percentage defence, mana, strength, intelligence, suppression and energy-shield recharge have one ladder per armour type; the central reading takes the largest weight over the types (1000 for most), the sensitivity run the smallest (500 for hybrid bases).

The usable data are therefore two datasets:

- **Gloves and misc ("natural", 40 sides).** All inputs Standard (the tab says so), essence-made chaos resistance on one item in 27 of 30 suffix sides. Weights here are 250 (chaos resistance), 500 (flat damage to attacks, attack speed, mana or life gained per kill), 600 (one accuracy tier), 1000 (most others). The contrast is chiefly chaos resistance (250) against the rest.
- **Wand tab (28 sides).** Rusty's data (Discord message of 2024-08-06, one week before 3.25.1): two items each with one prefix, a "+1 to level of all [element] spell skill gems" mod (weight 250 or 200, recorded per row) and a spell damage mod whose tier is **not recorded**. The spell damage weights on a wand in the export are 40, 150, 500 and 1500 (and 100 to 1000 for the spell-damage-and-mana hybrid), so its weight `s` is a nuisance parameter. The gem mod was kept in 1 of the 28 combines where one mod survived.

## 2. Model and method

On one side, `k` successive draws without replacement from the pooled entries, `P(next = e) ∝ weight(e)^α`, all entries of the picked mod group removed after each pick; the likelihood of an observation is the probability of its kept set summed over the orders of picking. The log-likelihood is computed on a grid of `α` from -3 to 6 in steps of 0.01 (exact enumeration, at most 3 kept of at most 6 pooled). The 95% interval is the profile-likelihood interval (2 × log-likelihood drop ≤ 3.84), checked by a bootstrap that resamples observations. For the wand tab, `s` is either fixed or profiled over the nine weights above. Everything is standard-library Python (`research/175/fit.py`); the bootstrap (5,000 resamples) and the 1,000 simulations of the goodness-of-fit test ran on a GitHub runner with `run.yml`, in about a minute.

## 3. Result: `α` per tab and pooled

| Dataset | Observations | `α̂` | 95% interval (profile) | Bootstrap 2.5% / median / 97.5% |
|---|---|---|---|---|
| Gloves | 38 | 0.95 | [0.38, 1.61] | |
| Misc (gloves, boots, helmets) | 2 | -0.43 | [none, 3.99] | too small to say anything |
| **Gloves + misc** | 40 | **0.92** | **[0.36, 1.56]** | 0.40 / 0.93 / 1.63 |
| Wand tab, `s` = 1500 | 28 | 1.78 | [0.94, 3.37] | 1.15 / 1.79 / 6.0 |
| Wand tab, `s` = 1000 | 28 | 2.29 | [1.21, 4.34] | |
| Wand tab, `s` = 500 | 28 | 4.43 | [2.32, none] | |
| Wand tab, `s` = 150 or less | 28 | negative | | the gem mod would have to be the favoured one |
| **Pooled, `s` = 1500** | 68 | **1.23** | **[0.79, 1.76]** | 0.84 / 1.23 / 1.76 |
| Pooled, `s` = 1000 | 68 | 1.32 | [0.84, 1.88] | |
| Pooled, `s` = 500 | 68 | 1.43 | [0.87, 2.09] | |

The wand tab alone does not fix `α`: with one unknown weight the gem-against-spell contrast only gives `α` as a function of `s`. Pooled with the gloves, `s` is pinned: the gloves fix `α` near 0.9 and then the one gem in 28 needs `s` of 1000 or more; the pooled likelihood prefers `s` = 1500 (log-likelihood -52.8) over 1000 (-53.8), 500 (-57.7) and 200 (-68.3), and rejects 40 to 150 (about -71). 1500 is the largest spell damage weight on a wand in the export, so the pooled interval at `s` = 1500 is conditioned on the edge of what is possible; the rows for lower `s` show how much higher `α` goes.

Tests of fixed values (likelihood ratio, one degree of freedom):

| Dataset | `α = 0` | `α = 1` |
|---|---|---|
| Gloves + misc | 11.2, p = 0.0008 | 0.07, p = 0.79 |
| Wand tab, `s` = 1500 | 30.5, p = 3e-8 | 3.2, p = 0.07 |
| Pooled, `s` = 1500 | 39.3, p = 4e-10 | 0.94, p = 0.33 |
| Gloves + misc, prefix sides only (no chaos resistance, 10 sides) | 1.9, p = 0.17 | 0.03, p = 0.87 |

The 2 × log-likelihood drop on gloves + misc is 18.9 at `α = -0.25`, 54.7 at `α = -1`, 9.8 at `α = 2` and 28.8 at `α = 3`: negative `α` and `α ≥ 2` are both out. The two datasets agree (heterogeneity test, 1 df: 2.36, p = 0.12). The prefix sides give the same direction without chaos resistance, but 10 sides are too few to reject `α = 0` alone.

A model-free reading of the gloves: a weight-250 mod is kept `0.25^α̂ = 0.28` times as often as a weight-1000 mod (range 0.12 to 0.61 over the interval); the player report quoted in #90 (29% against 75%, ratio 0.39) is inside it, and the author's own 7 of 15 (47%) is the one point that sits above it.

## 4. Sensitivity of the gloves + misc estimate (40 sides)

| Change | `α̂` | 95% interval |
|---|---|---|
| central reading | 0.92 | [0.36, 1.56] |
| armour-type groups at their smallest weight | 0.90 | [0.32, 1.55] |
| drop 7 sides with an ambiguous cell reading ("def", "regen") | 0.85 | [0.24, 1.56] |
| prefix sides only (10) | 1.15 | [-0.44, 3.24] |
| suffix sides only (30) | 0.89 | [0.30, 1.57] |
| suffix sides holding chaos resistance (27) | 0.90 | [0.30, 1.60] |

## 5. Duplicate tiers (#90 open point 3)

The pool entries are drawn with their own weights, so a mod held twice (on both inputs) enters twice. The open point is which weight an entry carries when the pool holds two **different tiers** of one group. In the usable data four sides hold two tiers of one group (for instance armour percentage tiers 4 and 3, flat physical damage tiers 3 and 1), but always at equal weight, because on these gloves all tiers of a group weigh the same (only accuracy differs, by one tier); no side holds two tiers at different weights. Giving all copies the largest, the smallest or their own weight therefore changes nothing, to the last digit (0.92, [0.36, 1.56] each time). **The data cannot answer the question.** It matters for groups whose tiers differ in weight (spell damage 40/150/500/1500, damage over time multiplier, elemental damage on wands); every row with such a pool is in a tab that holds crafted or exclusive mods and is out. A test needs a new sample: two tiers of one group on a wand (for instance spell damage at 1500 and at 40) against a third mod, a few dozen combines.

## 6. Goodness of fit and the alternative shape

- **The family describes the data.** A parametric bootstrap of the maximised log-likelihood (1,000 simulated data sets from the fitted model, refitted each time): the observed value is below 42% of them, so there is no sign of misfit. By weight class, mods kept against expected at `α̂ = 0.92`: weight 250: 7 against 6.6 (27 entries); 500: 8 against 8.7 (22); 600: 2 against 1.9 (3); 1000: 53 against 52.8 (84). At `α = 0` the 250-class would be kept 13.7 times and the 1000-class 43.7: the observed 7 and 53 are far from it. In the wand tab at `s` = 1500: the gem mod kept 1 against 0.97 expected (28 entries).
- **The power law itself.** Giving weights 250 and 500 free multipliers against 1000 instead of `(w/1000)^α` (37 sides): fitted multipliers 0.28 and 0.45 against 0.26 and 0.51 from the power law; likelihood-ratio 0.18, p = 0.67. The shape in weight is not rejected.
- **Weight of tier and better** (the shape of PoE 2's predictable formula, here the sum of the weights of tiers 1 to `t` of the mod's group, raised to `β`). On the 40 natural sides: weight only, `α̂ = 0.9`, log-likelihood -47.43; tier-and-better only (`α = 0`), `β̂ = 0.3`, -49.77, worse by 2.3 with the same number of parameters; both, `α̂ = 1.1`, `β̂ = -0.1`, -47.40, no gain over weight alone. The tiers in the data vary from 1 to 12 at equal weight, so this is a real test: tier does not matter once weight is in. It was not run on the wand tab (the gem and spell mods have no tier ladder in the sheet).

## 7. What this means for #94, ADR-0012 and ADR-0022

For the grill to take or leave (not decided here):

1. **Family.** Replace `α` in `[0, 1]` by a range centred on 1. The data support about `[0.4, 1.6]` (gloves + misc interval and bootstrap) or `[0.8, 1.8]` with the wand tab. Weight-proportional (`α = 1`) is a reasonable single "best estimate" and is not rejected anywhere. The interval is statistical (95%), not a guarantee: worst-case planning over it is a choice about risk.
2. **ADR-0012's admission rule is wrong in direction.** It admits the rules under which rarer mods are kept at least as often as common ones; the data reject equal chance, let alone rare-favoured rules. The boundary that is optimistic for rare targets is `α ≈ 0.4`, and `α = 0` should leave the family. ADR-0012's sentence and #90 section 5's "`α = 0` is the boundary" want rewording when #94 closes.
3. **ADR-0022** (a grid of `α`, not two end rules, because extremes can be interior) is untouched by this result; a range `[0.4, 1.6]` needs the same grid.
4. **Use at low weight.** Applying `α` to mods of weight 25 to 50 uses it outside the 250 to 1500 range the sheet covers. If the planner shows chances for such targets it should say they extend a fit that was not measured there.

## 8. Limits

- The chaos resistance in the gloves is essence-made. Its recombinator weight is taken as the natural group's 250, as the author does; the gloves measure `(w_chaos / 1000)^α`, not `α` alone (the prefix sides, without chaos, agree but are weak).
- The wand tab needs the spell damage weight `s` (section 1); the pooled interval depends on it.
- Rows are undated: Standard (gloves), in-league 3.25.0 (the wand tab is the week before 3.25.1, whose note says rarer mods "now have a much higher chance" than before, and the Kingsmarch upgrade of 3.25.0, which the author said tilts toward rare mods, may have been on). The fit describes the mixture before 3.26. The author's 3.26 statements (low weights disadvantaged, weights used as proportional shares) fit it but are not measured.
- 68 observations, and most of the gloves information is one contrast, chaos resistance (250) against mods of 500 to 1000.
- Pools and counts are the author's transcription; the ambiguous cells ("def", "regen") are guesses, shown in section 4 to matter little.
- The count table is assumed independent of weights (the guide says so); if it were not, the fit would absorb part of it.

## Reproduce

```
python -I research/175/build_rows.py RAW_DIR MODS_JSON research/175/rows.json
python -I research/175/fit.py research/175/rows.json research/175/fit_result.json --boot 5000 --sim 1000 --seed 175
```

`RAW_DIR` holds the 14 tabs as `<name>.csv` (`curl -L ".../export?format=csv&gid=<gid>"`, gids in the sheet's HTML); `MODS_JSON` is the pinned `mods.json`. `fit_result.json` is the output of the GitHub run (`run.yml`, branch `claude/eloquent-mahavira-24c2c2`, 1 runner); a local run without `--boot` and `--sim` takes under a minute and gives the same fits.
