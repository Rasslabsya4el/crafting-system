# State — 2026-09-21

## Morning summary (core works; ordered stretch in progress)

1. Target: ordinary PoE3.29; Q3 confirmed, Phase0 accepted.
2. Helmet command below runs without installation and prints9 real ranked policies.
3. Envy target p=0.00259406068444; expected cost1927.48, p90=4435 chaos-equivalent.
4. Protected suffix/life mean8357.19,p90=18985; optional bench131 mean8359.19,p90=18987.
5. Chaos mean41183.12,p90=94826.5; Alchemy+Scour mean41182.12,p90=94825.5.
6. Magic/Regal/Exalt mean583612.11; estimated p90=1345699.5 with explicit99%DKW interval.
7. Main suite244 passed in0.76minute;41 indexed hand answers and five real-pool MC comparisons included.
8. Bow thresholds60/100 yield12 policies/3 Pareto points; prices/utility are invented inputs.
9. Special families remain parked by GOAL/D14 and question-ID stubs; no new owner answer needed.
10. 41 known answers8ac207c and Pareto242091f accepted; bounded Divine is the final stretch task.

## Reproduce

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --threshold 100 --json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
python -m pytest -q
```

Mandatory text command personally run by lead:exit0,9 policies,0.08minute. CLI focused9 tests
passed0.18minute. Latest combined main suite244 tests passed45.39s (0.76minute) at242091f,
including Pareto/real cache-spy checks and41 indexed known answers. Core cost/probability evidence is
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

Parked families: Harvest(Q6), fossils(Q13), eldritch(Q11), Awakener(Q20), recombination
(Q21/Q22), fracturing/veiled(Q12), corruption(Q18 plus outcome/eligibility gaps), beasts(Q25)
and catalysts(Q23). Reasons are source disagreements or incomplete current rules; the night
goal explicitly excludes them. The broader Q9 eligibility matrix and Q16/Q17 general pools
remain research work after this bounded ordinary prototype, not silent inferred behavior.

Accepted worker trees removed without force. Known-answer worker accepted41 cases,0.06s; no production changes.
Pareto accepted242091f; next worker:Divine20minutes for range/state validation, exact outcomes
and seeded sampling tests. At most2 workers; each command
under10minutes. Pytest uses repository-local .pytest_tmp. No background process is required.

## Next three actions

1. Accept bounded Divine integer rerolls with side locks.
2. Rerun the integrated suite and record final outcome counts.
3. Finish the ten-line handover, commit and close the completed night goal.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared, worker launch next.
- 08:18 CEST — item model merged d07a1b5; exact DP in progress; goal/demo incomplete.
- 08:28 CEST — exact DP merged4ee0641; actions/costs running; all downstream specs prepared.
- 09:29 CEST — GOAL1-5 merged,170 tests green; policy/CLI first review corrections in progress; stretch specs ready.
