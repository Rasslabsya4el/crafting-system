# Current state — GOAL 2 active (2026-09-21, 14:56 CEST)

1. Ordinary PoE3.29 is the owner-confirmed target; GOAL2 is incomplete and work continues.
2. Harvest exact/sampler merged527efa7; protected-suffix helmet policy merged55c8191.
3. Harvest Life: p=.07950823245417574; full-prefix failure=.0759283364903187.
4. Its exact mean2703.61 and estimated p90 5987 [5808,6185] include repeated locks and paid restarts.
5. Best helmet remains Envy: mean1927.48, p90 4435, at invented example prices.
6. Metamod matrix has132 cells/33 notes; base projection561 records/548 names, seven classes.
7. Twelve cached-CoE cases accepted3712602;25 correspondences, max relative difference2.08735%, none above5%.
8. Optimizer560f8c2 accepted: protected8357.19→1948.60, Harvest2703.61→1986.20; grids24/8/96/4.
9. Solver b89f775: hand optima8/4/4.75; helmet100000-state limit in0.23022minute, no optimum claimed.
10. Fracture adapter d348533 accepted; next: family policies, complete bow reports, full pytest under one minute.

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
Full main regression at2b1d36a:329 passed in60.62s (1.01minutes); under-minute acceptance
is not yet met. Optimizer correction2 includes reducing repeated expensive test work while
preserving numerical coverage. Full source-tool tests require the ignored local snapshots;
worker focused tests do not require unrelated snapshots. Pytest temp stays in .pytest_tmp.

Source research is now S1-S79. Fifteen owner rows corrected inffcf869; no owner test is
needed. Wiki browser access works through Playwright. Official GGG resolves behavior;
Reddit is retained with version/sample/player-report conditions. Q6 first/all Harvest
filter scope is unresolved: explicit first_only default, all_draws sensitivity. Current
policy has no attack/caster restriction, so that uncertainty does not change its number.

## In progress and bounded backlog

At most two workers. Current:fossil-spam-policy (Terra high, fromc9afb36) and
catalyst-quality-policy (Terra high, CLI handed off after optimizer merge).
Quality core22b6119 has48 lead tests0.036minute; CLI/final report still pending.
Fracture identity accepted d348533:74 lead tests0.074minute; real Envy finish
.06101200110346221/30classes,627 of10000 seeded hits, identity loss0, Divine Life9
value132 retained. Paid fracture policy follows optimizer; Harvest/fossil fracture inputs
remain explicitly unsupported.
Optimizer accepted560f8c2 after two correction rounds and56 lead tests including real
helmet/bow CLI0.954minute. Complete per-threshold search metadata, legal bench audit and
unreachable-stage handling are verified. Final p90/parameter/bow report is part of the
default-plan measurement after family integration. The full-suite runtime target remains
open: routine CLI fixtures will use explicit bounded loadouts, with full default commands
measured separately once; synthetic exhaustive grids retain algorithm/seed coverage.
Conditional attempt kernel accepted0f012a1:10 tests; exact hand means21.5/22,
independent true p90 fixtures44/45/97 with seeded DKW intervals containing each.
Ordinary fossil adapter accepted0de86dd:43 focused tests,18 supported fossils,93 real entries/
84 classes; triple target .00010020977755731918,Life marginal .09844673121656489;
seeded1/1032 of10000,zero blocked/group violations. Policy integration follows optimizer.
Offline validation, Harvest policy and fossil adapter are accepted; clean trees are removed.
Solver acceptedb89f775 as bounded negative research:11 lead tests,1 materialized plus
99999 pending Alchemy states,506055 internal edges and0 complete action rows. Lead rerun
0.23022minute; docs/research/solver-experiment.md records the exact omission/limit scope.
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
- 12:52 CEST — Harvest55c8191 and12-case CoE3712602 accepted;285 tests0.83minute. Attempt kernel/fossil adapter active; optimizer/solver and paid family policy specs ready.
- 13:52 CEST — attempt0f012a1,fossil0de86dd,solverb89f775 accepted; solver100000-state limit0.23022minute. Optimizer correction1 and fracture implementation active; family policies next.
- 14:56 CEST — fracture d348533 and optimizer560f8c2 accepted;56 optimizer lead tests0.954minute. Fossil policy active; catalyst core48 lead tests, CLI active; full-suite runtime work remains.
