# Current state — GOAL 2 active (2026-09-21, 12:41 CEST)

1. Ordinary PoE3.29 is the owner-confirmed target; GOAL2 is incomplete and work continues.
2. Harvest exact/sampler merged527efa7; protected-suffix helmet policy merged55c8191.
3. Harvest Life: p=.07950823245417574; full-prefix failure=.0759283364903187.
4. Its exact mean2703.61 and estimated p90 5987 [5808,6185] include repeated locks and paid restarts.
5. Best helmet remains Envy: mean1927.48, p90 4435, at invented example prices.
6. Metamod matrix has132 cells/33 notes; base projection561 records/548 names, seven classes.
7. Twelve cached-CoE cases reproduced; largest relative difference2.08735%; final correction acceptance in progress.
8. Optimizer pending: protected k1 baseline8357.19; legal fixed k2 measurement4693.13, k3 paid-reset4787.90.
9. General solver pending: no state-count/runtime/optimum result exists yet; bow recheck follows optimizer.
10. Next: accept12-case report; accept attempt kernel and optimize templates; run bounded solver/family policies.

## Working commands and evidence

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
python -m tools.coe_validation
python -m pytest -q
```

Latest focused lead acceptance:39 Harvest/policy/input/CLI tests passed in0.54minute
on55c8191. Accepted Harvest adapter:26 tests, exact Life9=.07950823245417578,
820/10000 seeded samples within Hoeffding .019494746, zero suffix violations.
No new full-suite result is claimed yet: previous accepted full baseline248 tests in
0.84minute atd332f60. Full source-tool tests require the ignored local snapshots;
worker focused tests do not require unrelated snapshots. Pytest temp stays in .pytest_tmp.

Source research is now S1-S79. Fifteen owner rows corrected inffcf869; no owner test is
needed. Wiki browser access works through Playwright. Official GGG resolves behavior;
Reddit is retained with version/sample/player-report conditions. Q6 first/all Harvest
filter scope is unresolved: explicit first_only default, all_draws sensitivity. Current
policy has no attack/caster restriction, so that uncertainty does not change its number.

## In progress and bounded backlog

At most two workers. Current:policy-attempt-kernel; offline-coe-validation has returned
correction1 for acceptance. Ordinary fossil adapter is next available independent slice.
Specs ready:template optimizer, bounded solver, ordinary fossils, concrete fracture identity,
and catalyst quality finishing. New family policy specs follow their accepted adapters.
No background CPU job or unbounded wait is left. Worker scope at most90minutes; individual
CPU jobs at most10minutes. Solver experiment caps graph building and solution at2minutes
each,100000 states/2000000 edges; negative measured findings are acceptable per GOAL2.

Resolved for implementation: rare counts8/3/1, multimod2Divine, normal/rare Screaming+
essences (magic never), protected Harvest, ordinary CoE additive fossils including two
hybrid definitions, ordinary uniform fracture model, catalyst fractional quality gains.
Still explicitly gated: current exact recombination/selected-mode odds(Q21/Q22), Awakener
conflict survivor(Q20), Conflict exact unequal-tier table(Q11), veiled offers(Q12), special
fossils(Q13), unsupported quality magnitude/Tainted(Q23), other special-state/action gaps.
These gates do not excuse stopping the answered ordinary family implementations.

Price and utility tables are invented inputs, not market/game facts. D14/Q16/Q17 pool
semantics remain explicitly provisional. Terminal scored classes cannot be reused for
arbitrary future transitions that require lost modifier-group identity. The general solver
must retain that identity or demonstrate an exact equivalent grouping.

## Accepted baseline retained for comparison

GOAL1 complete:41 indexed hand answers; bounded Divine75/225 outcomes and event2/15;
bow60/100 previously12 reachable policies/3 frontier points. Fixed magic route mean583612.11,
estimated p90 1345699.5 [1304082.1,1390479.3],50000 samples,seed20260921. These are baseline
measurements, not claims about the forthcoming optimized policies. Reports live in
out/workers; committed acceptance ledger is docs/WORKERS.md. All worker worktrees and data
operations remain inside crafting; third-party snapshots remain ignored. AGENTS/D19 allow
lead-selected Terra reasoning, or Luna for very light tasks. No orchestration skills used.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared, worker launch next.
- 08:18 CEST — item model merged d07a1b5; exact DP in progress; goal/demo incomplete.
- 08:28 CEST — exact DP merged4ee0641; actions/costs running; all downstream specs prepared.
- 09:29 CEST — GOAL1-5 merged,170 tests green; policy/CLI first review corrections in progress; stretch specs ready.
- 10:29 CEST — core,41 known answers and Pareto merged;244 tests green; final bounded Divine worker in progress.
- 10:41 CEST — all core/stretch work accepted;248 tests green; worker-model instruction updated; final handover committed.
- 11:52 CEST — matrix132cells and bases561 merged; Harvest correction1 and offline12-case validation in progress; optimiser/solver pending.
