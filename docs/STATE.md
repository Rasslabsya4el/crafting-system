# State — 2026-09-21

## Morning summary (core works; ordered stretch in progress)

1. Target: ordinary PoE3.29; Q3 confirmed, Phase0 accepted.
2. Helmet command below runs without installation and prints9 real ranked policies.
3. Envy target p=0.00259406068444; expected cost1927.48, p90=4435 chaos-equivalent.
4. Protected suffix/life mean8357.19,p90=18985; optional bench131 mean8359.19,p90=18987.
5. Chaos mean41183.12,p90=94826.5; Alchemy+Scour mean41182.12,p90=94825.5.
6. Magic/Regal/Exalt mean583612.11; estimated p90=1345699.5 with explicit99%DKW interval.
7. Main suite187 passed in0.71minute; hand exact cases and five real-pool MC comparisons included.
8. Bow value-table threshold100 produces6 reachable policies; prices/utility are invented inputs.
9. Special families remain parked by GOAL/D14 and question-ID stubs; no new owner answer needed.
10. Continue ordered stretch:41 known answers, Pareto/two bow thresholds, bounded Divine; do not stop yet.

## Reproduce

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --threshold 100 --json
python -m pytest -q
```

Mandatory text command personally run by lead:exit0,9 policies,0.08minute. CLI focused9 tests
passed0.18minute. Main187 tests passed42.82s (0.71minute) atd344054; final0acb192 adds only
subprocess error-test coverage, personally checked1 test. Core cost/probability evidence is
in policy-evaluation spec and out/workers reports. All5 acceptance probabilities passed.

## Boundaries and current work

Exact under declared provisional rules, not externally measured game odds: rare4/5/6 weights
8/3/1 from CoE, PoB group/first-tag weights, no generated tags or multipliers (Q16/Q17).
Quality is fixed input. Prices are invented, no trade lookup. Terminal scored classes cannot
be reused for arbitrary transitions needing lost group identities. Bench finish uses a proved
known-prefix state. Source confidence and parked contradictions remain in the existing62-source/
20-sheet corpus; no new fact sheets or research expansion tonight.

MC cost fallback applies only to the expensive fixed magic cycle:50000 samples,seed20260921,
p90 interval[1304082.1,1390479.3] at99%DKW. This uncertainty interval differs from cost p90.
Other listed policies have exact geometric/convolved p90. Policies are fixed templates, not
an optimal-policy search. Budget flags use mean cost and separately expose p90 over budget.

Accepted worker trees removed without force. Next worker:known-answers,15minute budget,
followed by frontier20minutes and Divine20minutes in order. At most2 workers; each command
under10minutes. Pytest uses repository-local .pytest_tmp. No background process is required.

## Next three actions

1. Accept41 indexed hand-computed cases, then read GOAL and merge.
2. Implement Pareto comparison for thresholds60/100 over shared bow distributions.
3. Implement bounded Divine integer rerolls; rerun integrated suite, finish handover and commit.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared, worker launch next.
- 08:18 CEST — item model merged d07a1b5; exact DP in progress; goal/demo incomplete.
- 08:28 CEST — exact DP merged4ee0641; actions/costs running; all downstream specs prepared.
- 09:29 CEST — GOAL1-5 merged,170 tests green; policy/CLI first review corrections in progress; stretch specs ready.
