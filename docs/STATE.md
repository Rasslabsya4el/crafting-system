# State — 2026-09-21

## Morning summary — GOAL and all three stretch tasks complete

1. Target is ordinary PoE 3.29; owner reconfirmed Q3. Phase 0 and the night goal are complete.
2. The helmet CLI runs from the repository root and prints 9 ranked policies with stages and decisions.
3. Envy target probability: 0.00259406068444; mean cost 1927.48, p90 cost 4435 chaos-equivalent.
4. Protected suffix/life mean 8357.19, p90 18985; with bench131: mean 8359.19, p90 18987.
5. Chaos mean 41183.12, p90 94826.5; Alchemy+Scour mean 41182.12, p90 94825.5.
6. Final `python -m pytest -q`: 248 passed in 0.84 minutes on Python 3.12.4.
7. Validation includes 41 indexed hand answers and independent seeded Monte Carlo on five real pools.
8. Bow thresholds 60/100 produce 12 reachable policies and 3 Pareto points over shared distributions.
9. Divine API: 75/225 real outcomes, event probability 2/15; side locks and seeded sampling tested.
10. Prices/utility are invented inputs; special families remain parked below. No owner answer is needed now.

## Reproduce from crafting/

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
python -m pytest -q
```

Final main test result: `248 passed in 50.30s` (0.84 minutes), implementation at `d332f60`.
The final helmet text command returned 9 policies in about 0.09 minutes. README's runnable
Divine example also passed its 75-outcome assertion. Python 3.12, pytest and NumPy are used;
the local package needs no installation. Planner inputs use committed own projections; full
source-tooling tests also need the ignored snapshots already present in sources/pob/ and
sources/raw/. Isolated worker trees ran focused tests; raw snapshots are not copied into them.

## Numerical evidence and limits

The 9 helmet policies include four essence choices, Alchemy+Scour, Chaos, the fixed magic/
Regal/three-Exalt cycle, protected life and its optional bench finish. Probabilities, attempts,
mean/p90 costs, distributions, steps and assumptions are in JSON. Fixed templates are ranked;
there is no general optimal-policy solver or parent build-system integration.

The magic cycle has exact mean 583612.11 and estimated p90 1345699.5. Its 99% DKW interval
is [1304082.1, 1390479.3], with 50000 samples and seed 20260921. This estimation uncertainty
is distinct from the 90th percentile of total cost. Other listed helmet policies use exact
geometric or convolved quantiles. Mean-budget eligibility and p90-over-budget are separate.

| Bow Pareto policy | Success probability | Mean cost | p90 cost | Conditional utility |
|---|---:|---:|---:|---:|
| Alchemy+Scour, threshold60 | 0.005317197426764 | 187.57 | 431.5 | 62.6361 |
| Magic/Regal/Exalt, threshold60 | 0.007701811732828 | 4056.99 | 9342.4 | 63.5061 |
| Alchemy+Scour, threshold100 | 0.000086404089951 | 11573.03 | 26647.5 | 100 |

These are predictions under the declared model and invented inputs. The real restricted-bow
cache test measures two raw action calculations across two thresholds, one per Alchemy/Chaos.
Constant utility stays exactly constant; strict Pareto comparison keeps identical points.

Divine is a separate value API, not an added CLI strategy. It supports one inclusive integer
range per affix, source-item value order and prefix/suffix locks. Life9/Chaos6 give 75 outcomes,
expected values 137/33 and P(life>=140, chaos>=34)=2/15; adding Fire8 gives 225. Locks leave
5 or 15 outcomes. Exact enumeration stops above 100000 states; direct sampling remains usable.
Fixed numeric, decimal and multiple-range/stat shapes explicitly raise unsupported-shape errors.

## Source and implementation boundaries

D14/GOAL authorize unbiased draws, rare 4/5/6 counts with CoE weights 8/3/1, PoB group and
first-matching-tag weights, and omission of generated tags/multipliers (Q16/Q17). Confidence
and conditions remain visible. Quality is fixed input. Terminal scored classes cannot be
reused for arbitrary transitions requiring lost modifier-group identities. Bench finish uses
a provable known-prefix state. Source corpus remains 62 sources / 20 sheets; no new fact sheets
or broad source re-audit were added during the night implementation.

Parked: Harvest(Q6), fossils(Q13), eldritch(Q11), Awakener(Q20), recombination(Q21/Q22),
fracturing/veiled(Q12), corruption(Q18 plus outcome/eligibility gaps), beasts(Q25), catalysts(Q23).
Source disagreements or incomplete current rules block these families; GOAL excludes them.
The general Q9 eligibility matrix and Q16/Q17 pool semantics remain research dependencies.
Supported ordinary states exclude corrupted/influenced/fractured/synthesised/mirrored/split
items and raise the exact Q9 error. No market prices or PoB damage valuation are inferred.

## Handover and next three actions (outside the completed night goal)

1. The incoming lead reviews provisional D14 against the preserved source questions.
2. Select one broader item/policy slice and settle only the source gates it needs.
3. Wire the reviewed distribution/value/cost contract into the parent project in a separately authorized task.

No active workers or background jobs remain; worker worktrees were removed without force.
Reports are in out/workers/; committed acceptance evidence is in WORKERS.md, specs and tests.
New owner instruction is recorded in AGENTS section6 and D19 (`7748e73`): choose any supported
Terra reasoning per task; use GPT-5.6 Luna for very light tasks and choose its reasoning too.
All worker trees and explicit file operations used this repository; raw snapshots remain ignored.
Current pytest runs use repository-local `.pytest_tmp`. The initial pool acceptance inherited
pytest's default temporary directory before that setting was corrected; no external cleanup
was attempted. Keep the repository-local setting for future test runs.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared, worker launch next.
- 08:18 CEST — item model merged d07a1b5; exact DP in progress; goal/demo incomplete.
- 08:28 CEST — exact DP merged4ee0641; actions/costs running; all downstream specs prepared.
- 09:29 CEST — GOAL1-5 merged,170 tests green; policy/CLI first review corrections in progress; stretch specs ready.
- 10:29 CEST — core,41 known answers and Pareto merged;244 tests green; final bounded Divine worker in progress.
- 10:41 CEST — all core/stretch work accepted;248 tests green; worker-model instruction updated; final handover committed.
