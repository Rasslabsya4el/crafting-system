# Current state — crafting output layout review (2026-09-21)

## Active owner request

Prepare visual TEMPLATES for approval before production integration. The owner wants
six visible affix slots, action purpose, desired result, event probabilities and explicit
stop/skip/retry transitions. Do not run new crafting calculations, simulations or CoE.
Design:D25 and docs/design/route-layout-proposals.md. Worker spec549ac70:
docs/specs/2026-09-21-route-layout-prototype.md, Terra/high,30minute bound, one isolated
worktree .worktrees/route-layout-prototype. Only docs/prototypes/route-layouts.html is
owned by the worker. Lead owns the recipe interpretation, review and documentation.

Three views of the SAME saved protected Envy helmet route:1 step cards,2 directed
transition map,3 manual execution guide. Recommended final composition:1 plus a compact2.
QuestionQ31 asks the owner to choose after inspecting the concrete output. Currency
artwork and strategy expansion are deferred; no production renderer change is in scope.

## Accepted implementation baseline

Ordinary PoE3.29 distributions, exact/seeded policy costs, bounded parameter search,
terminal utility and ranked finite templates work. Production reports have dark theme,
one decimal,12 helmet routes/14 bow variants, material costs and historical evidence.
Report implementation02bceff; handover docs8d9da78. Last FULL proof at clean02bceff:
423 passing tests,0 failures/errors/skips,0.9minute;12 offline CoE component cases,
maximum relative difference2.08735%. No fresh engine check is claimed during layout work.

Existing saved reports:out/reports/helmet/index.html and out/reports/bow/index.html.
Each folder contains plan.json and copied evidence. All26 material totals reconcile.
Historical proof:out/evidence-final/proof.json. Existing reproduction commands (do not
run them merely for the current layout task):

```powershell
python -m tools.collect_evidence --output-dir out/evidence-final
python -m craftoracle report examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --output-dir out/reports/helmet --evidence-dir out/evidence-final
python -m craftoracle report examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --output-dir out/reports/bow --evidence-dir out/evidence-final
```

## Facts the new layout must preserve

Prototype inputs are the02bceff protected Envy route. Preparation:exactly3 suffixes,
2 desired elemental T1 suffixes and<=1 prefix; finished items stop first. Envy forces
ChaosResist6 on Helmet (PoB Essence.lua:104). Bench729 occupies a prefix. Protected
Scour clears all prefixes, including the bench craft. Up to3 Exalts check lifeT1 after
each; three failed full prefixes return to Envy, not another impossible prefix bench.

Mean1948.6031719508137/p904450.5 at invented prices; immediate Envy success probability
.0025940606844434212, preparation-only.0005495684166343902; series success.06674609236085169.
These are saved values, not new evaluations.6.7% describes the WHOLE Exalt series;
98.6% is the share of completed routes finishing during Envy, not per-use probability.

The owner's other-base CoE concern is valid UX feedback. C01..C03 are helmet component
checks; C04..C12 are engine cases on other bases. None certifies this whole protected
route. The prototype separates route scope, same-base examples and collapsed global
regressions. docs/validation/coe_cases.md holds the exact case scope.

## Remaining boundaries

Finite template library, not a general route discovery engine or proven global optimum.
The benchmark solver reached100000 states before a full Alchemy row and is parked.
Price/bow utility are invented; quality supplied; base0 unpriced. D14/Q16/Q17 pool semantics
remain provisional. Harvest first_only/Q6 sensitivity explicit. Source-dependent gaps:
recombinationQ21/Q22, Awakener conflictQ20, unequal-tier ConflictQ11, veiledQ12, special
fossilsQ13, quality/TaintedQ23, selected special eligibility/replacementQ9/Q18/Q19.

## Next three actions

1. Accept the standalone prototype by full diff, Node syntax and manual browser branches.
2. Present the three actual views and get a concreteQ31 layout choice.
3. Implement only the selected production output contract, then revisit strategy breadth.

All files/worktrees are inside crafting. No orchestration skills. All earlier workers
finished and worktrees removed; only the one layout worker is active. No preview server
is running yet. A temporary localhost preview may be used for browser QA and must stop
before handover. Durable artifact is the standalone HTML; browser file URLs are blocked
by the browser tool. Sources and process ledgers:docs/SOURCES.md,docs/WORKERS.md.
