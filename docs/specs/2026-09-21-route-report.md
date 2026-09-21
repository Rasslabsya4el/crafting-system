# Spec: readable offline Russian route report from real planner output

Worktree `.worktrees/route-report`, branch `w-route-report`. May touch ONLY
src/craftoracle/reporting.py, src/craftoracle/report_assets/, src/craftoracle/cli.py,
tests/test_report.py. Bound75minutes. Terra high. No source/strategy decisions.

Read docs/design/route-report.md fully: it supplies the exact instructions, accounting
formulas, probability semantics and evidence schema. Existing accepted algorithms stay intact.

1. Add `python -m craftoracle report SPEC --loadout LOADOUT --output-dir DIR`
   supporting --threshold or --compare-thresholds and optional --evidence-dir DIR.
   Reuse evaluate_plan; produce index.html and plan.json in DIR. Reject paths outside
   this repository. stdout prints the generated paths. Existing plan/quality flags unchanged.
2. Pure build_report(plan, context, evidence=None) and render_report(report) (or equivalently
   clear small functions). Context includes supplied spec, bench recipes, action count rules,
   source names, generation time/commit. Rendering never computes a fresh crafting probability.
3. All ranked and unavailable rows, readable Russian steps for the supported12-route helmet
   set and bow counterparts, prices/expected counts/cost reconciliation, correctly labelled
   stage probabilities and p90. Account for selected gates, branch costs and exact source rules.
4. Standalone polished HTML, offline search/route selection, table plus detailed steps, compact
   collapsed parameter/source/outcome evidence. Prices marked invented, quality supplied.
   Escape all data safely; no external resources. Tiny embedded JavaScript is allowed.
   Reopen/print works without server. Detail pane must show all route-specific decisions.
5. Evidence display matches the design schema; unavailable/missing/stale evidence explicit.
   Show actual test cases and all12 CoE rows, commands/raw-file links. Keep module-component
   tests distinct from end-to-end game verification. No hardcoded394/test success badge.
6. Meaningful tests on tiny input documents: accounting fixtures in design (Envy1927.479966,
   changed price3854.959932; protected Exalt3.5 count; Magic counts4/4/2/3/2/1), stage-reach
   label, early-stop false, no Exalt whenk0, every row retained, unknown/missing evidence,
   HTML/script injection escaping. CLI wiring test using mocked evaluator, no full grids.

Report commits, focused tests/time, generated fixture path and limitations. Use only ignored
out/ for previews. Lead will supply real end-to-end acceptance and screenshots after merge.
Do not run full pytest or full real plans yourself. Final begins `=== FINAL REPORT ===`.
