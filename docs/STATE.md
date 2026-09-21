# Current state — GOAL 2 final acceptance (2026-09-21, 15:53 CEST)

1. Target: ordinary PoE3.29, confirmed by owner; GOAL2 implementation is merged, final runtime check remains.
2. Twelve offline CoE cases/25 correspondences: maximum relative difference2.08735%, none above5% (3712602).
3. Protected Exalt mean8357.19393 ->1948.60317; Harvest2703.60938 ->1986.19822 (560f8c2).
4. Magic helmet mean583612.10526 ->29449.03205; selected gates1/2, three slams, early stop.
5. Best helmet remains Envy: exact mean1927.47997/p904435 at invented example prices.
6. Fossils2c069fc: all15 recipes; bow60/100 Scorched frontier means162.37513/9739.87719, p90372.5/22426.5.
7. Fracture000e8d9: paid replacements, mean4227.73669, estimated p908744 [8500,9353.5];12 helmet routes.
8. Catalyst14be5e9: mean14.42372 applications/p9016; supplied price2 gives28.84745/32.
9. Solver b89f775: hand optima8/4/4.75; helmet100000-state limit in0.23022minute, no optimum claimed.
10. Final394 tests pass in1.036minute; one tiny cache regression fixture is being bounded to meet the one-minute limit.

## Working commands

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
python -m craftoracle quality --base "Paua Amulet" --item-level 86 --catalyst fertile --target-quality 20 --price 2 --json
python -m tools.coe_validation
python -m pytest -q
```

Complete default CLI measurements: final helmet0.51minute, bow60/100 0.85minute.
Every offered15-fossil and96-Magic candidate completes; no work-limit result. Full local
JSON: out/goal2/helmet-final.json and out/goal2/bow-thresholds.json. Accepted results,
parameters, uncertainty and before/after costs: docs/research/goal2-results.md.

Lead acceptance: fossil48 affected tests plus26 changed tests; fracture47 affected tests
plus17 final input tests. Full main after fossils373 passed in0.863minute; after fracture
394 passed in1.036minute. Source-builder tests need the ignored local PoB/CoE snapshots.
All pytest temporary files stay in .pytest_tmp. No raw third-party files are committed.

## Active work and next three actions

Only bound-cache-regression is active: Luna medium, five-minute spec, own worktree.
It changes one test fixture only: same production cache path, hand probabilities1/2 ->1,
means2.5 ->1.5; real helmet and full-plan coverage stay intact (D23). Main production code
is accepted. All fossil/fracture implementation worktrees were removed without force.
No long-running CPU job or background service is left behind; worker tests remain bounded.

1. Accept the tiny fixture change by whole diff, its numbers and lead tests; merge explicitly.
2. Run the full main suite once after that change; record measured time and final status.
3. Finish STATE/TASKS/worker ledger/report, explicit-path commit, and report GOAL2 completion.

## Sources and remaining limits

S1-S79 and15 owner rows are recorded; no unanswered question needs an owner test today.
Wiki rechecked15:17CEST through Playwright extension: Vaal Orb article loaded. The separate
Codex browser API's apikey failure is not a research blocker. Official GGG statements decide
behavior they address; Reddit/player reports retain date, version and sample conditions.

Q6 first/all Harvest type filtering remains open: explicit first_only default, all_draws
sensitivity. The accepted protected Life route has no type blocker. Ordinary CoE additive
fossils, uniform fracture and fractional catalyst gains are implemented. Other answers
resolved eligibility/research scope, not these remaining executable numeric/model gates:
recombination and selected-mode odds(Q21/Q22), Awakener conflicting survivor(Q20), unequal-
tier Conflict probabilities(Q11), veiled offers(Q12), special fossils(Q13), quality magnitude/
Tainted(Q23), and remaining special-state/replacement-action gaps(Q9/Q18/Q19).

Price and bow utility tables are invented inputs. D14/Q16/Q17 pool semantics remain
provisional. Template search is finite, not a global optimum. OutcomeClass is a terminal
projection; transitions needing lost modifier-group identity cannot reuse it. Fracture-Life
policy is only the documented Royal Burgonet86 target; catalyst policy finishes supplied
ordinary jewellery. Broader policy/eligibility work remains explicitly in TASKS.

AGENTS/D19 allow lead-selected Terra reasoning and Luna for very light tasks. No
orchestration skills used. All reads/writes/worktrees stay inside crafting. Acceptance
ledger:docs/WORKERS.md; detailed local reports:out/workers.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared.
- 08:18 CEST — item model merged d07a1b5; goal/demo incomplete.
- 08:28 CEST — exact DP4ee0641; actions/costs running.
- 09:29 CEST — core170 tests green; policy/CLI corrections active.
- 10:29 CEST — core/known answers/Pareto merged;244 tests; Divine active.
- 10:41 CEST — GOAL1 complete;248 tests0.84minute.
- 11:52 CEST — matrix132cells/bases561 merged; Harvest/CoE validation active.
- 12:52 CEST — Harvest55c8191/CoE3712602 accepted;285 tests0.83minute.
- 13:52 CEST — kernel0f012a1/fossil0de86dd/solverb89f775 accepted; optimizer/fracture active.
- 14:56 CEST — fracture d348533/optimizer560f8c2 accepted; family policies active.
- 15:53 CEST — all family policies merged;394 tests green but1.036minute; one bounded cache fixture in progress.
