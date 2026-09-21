# GOAL 2 results and limits

This report compares the accepted implementations at the repository's invented example
prices. It is not a market-price estimate or a proof of a globally optimal craft. The
ordinary PoE 3.29 source scope and unresolved questions remain in `../OPEN_QUESTIONS.md`.

## Independent validation and solver experiment

The twelve frozen Craft of Exile comparisons cover helmet, body armour, ring, amulet and
boots, with 25 checked modifier correspondences. The largest relative difference is
2.08735057%; none exceeds 5%. Five cases agree to floating precision. The exact inputs,
source offsets and differences are in `../validation/coe_cases.md` (accepted `3712602`).
The comparison executes the ignored cached files locally and makes no network request.

The bounded solver reproduces the three hand optima 8, 4 and 4.75. The real helmet run
reaches 100,000 states in 0.23022 minute before completing the first Alchemy transition
row: one materialized state, 99,999 pending concrete states and 506,055 internal draw
edges. There is no measured helmet optimum. This is the accepted negative experiment
`b89f775`; its limits and omitted actions are in `solver-experiment.md`.

## Optimized template costs

The finite template grids were accepted in `560f8c2`. Means include preparation,
consumed locks and paid restarts. The fixed recipes remain available through
`policies.evaluate_fixed_policies` for explicit comparisons.

| Helmet route | Fixed mean | Optimized mean | Selected behavior |
|---|---:|---:|---|
| Envy spam | 1927.47996606 | 1927.47996606 | Stop on the complete target |
| Suffix protection and Exalted Orbs | 8357.19392785 | 1948.60317195 | Early complete target; preparation at most one prefix and at least two target elemental suffixes; up to three slams |
| Suffix protection and Harvest Life | 2703.60937955 | 1986.19821628 | Same preparation/early-stop gate; pay another suffix lock for each reforge |

Most of the protected routes' improvement comes from accepting completed Envy preparation
outcomes immediately. Neither route beats direct Envy at these prices. Protected Exalt,
Harvest, Magic and bench grids have 24, 8, 96 and 4 candidates respectively. Optional item
level search keeps caller target IDs and the supplied base price unchanged; it reports an
incomplete search explicitly. These are finite search domains, not all possible policies.

Full default CLI output from fossil worker commit817a040 is preserved locally in
`out/goal2/helmet-before-fracture.json` and `out/goal2/bow-thresholds.json`. All15 fossil
combinations and all96 Magic candidates completed for the helmet and each bow threshold;
there was no work-limit status. Fossil policy accepted2c069fc after48 lead affected tests
and26 final changed tests. Full default command times were0.44minute for the helmet and
0.85minute for the two-threshold bow. The fracture-policy integration is still pending.

Helmet Magic falls from mean583612.105255 to29449.032048; estimated p90 falls from
1345699.5 to67889.5, with final99% DKW interval[65799.2,70159.9]. Its selected gates require
at least one desired modifier after the magic stage and two after Regal, allow three
Exalted Orbs and stop early on completion. Estimated p90 uses50000 samples, seed20260921.
Protected Exalt p90 is4450.5 [4310.5,4600]; Harvest p90 is4590 [4440,4740]. These
brackets describe uncertainty in the p90 estimate, not a player's90% cost interval.

## Fossils and the bow value path

The four-fossil availability input offers Aberrant1, Pristine12, Scorched13 and Serrated14;
all15 nonempty subsets are compared. A selected fossil costs1 and the resonator costs its
socket count, so complete recipes cost2/4/6/8. These are invented price/availability inputs.
The initial Alchemy can finish immediately; all later fossil rerolls include the full
recipe price and require a rare item. Sources/model: `../mechanics/fossils_resonators.md`.

On the helmet, Aberrant1 alone has success probability.0001432502308634093 per fossil
reroll, mean13961.7440676, p9032146.5 and6980.6220338 expected resonators. The overall
best helmet route remains Envy at1927.47996606/4435.

The complete bow result has14 reachable policy/threshold pairs. Its two Pareto points are:

| Stop threshold | Selected recipe | Expected terminal utility | Expected cost | Exact cost p90 |
|---:|---|---:|---:|---:|
| 60 | Scorched13 | 62.71002826 | 162.37512654 | 372.5 |
| 100 | Scorched13 | 100 | 9739.87718828 | 22426.5 |

The corresponding fossil probabilities are.012289507645152398 and.00020533419675207822.
The earlier best Alchemy/Chaos costs were187.56899946 and11573.02621351. The new points
also beat those routes' p90 costs431.5 and26647.5; the threshold60 terminal utility rises
from62.63609988. Every other evaluated pair is dominated. Utility numbers are the invented
bow table from the brief, not a Path of Building damage calculation. The raw stage
distributions are shared between thresholds; terminal distributions retain only outcomes
that satisfy each selected stopping rule.

The paid fracture route and final integrated test runtime remain to be measured.

## Quality finishing

The accepted catalyst API (`14be5e9`) returns distributions of application count, cost and
final quality for ordinary jewellery. At ilvl 86, zero-to-20 same-type quality takes
14.4237235705 applications on average, with p90 16. At supplied price 2 the corresponding
costs are 28.8474471410 and 32. Independent binomial CDF at 16 is 0.9413199321; the seeded
10,000-sample CDF is 0.9345, inside its 0.0194947460 Hoeffding bound. This does not infer
modifier magnitude or damage value. Sources and restrictions: `../mechanics/quality_catalysts.md`.

## Reproduction

```powershell
python -m tools.coe_validation
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
python -m craftoracle quality --base "Paua Amulet" --item-level 86 --catalyst fertile --target-quality 20 --price 2 --json
python -m pytest -q
```

The full-suite under-one-minute target is still pending final integration. Routine CLI
tests use explicitly bounded fossil availability and disable the expensive Magic grid;
small exhaustive fixtures retain optimization and sampled-cost coverage. Full default
commands, including all 15 fossil combinations and the complete Magic grid, are measured
separately for this report. Local raw sources are needed by the source-builder tests.
