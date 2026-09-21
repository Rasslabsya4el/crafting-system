# Route report acceptance

Owner request, 2026-09-21: make the computed routes, instructions, costs and probabilities
inspectable, with visible test evidence. Later correction: dark theme, one decimal place.
Design contract: ../design/route-report.md. No new crafting rule is introduced by this UI.

## Reproduction

From the repository root, with the ignored source snapshots present:

```powershell
python -m tools.collect_evidence --output-dir out/evidence
python -m craftoracle report examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --output-dir out/reports/helmet --evidence-dir out/evidence
python -m craftoracle report examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --output-dir out/reports/bow --evidence-dir out/evidence
```

Each report is a standalone index.html plus raw plan.json and copied evidence. Open the
HTML directly in a browser; no server is required. The local preview server used during
lead acceptance is temporary and must be stopped before handover.

## Evidence boundaries

The proof bundle records the executed command, revision, timestamp, exit code, log and
individual pytest cases. It never reuses stale successful artifacts after a failure.
Known-answer mathematical cases are indexed in ../research/known-answers.md; the twelve
offline CoE action comparisons are documented in coe_cases.md. Both remain distinct from
empirical verification of a complete multi-step strategy against the live game.

Expected counts/costs in the report derive from actual selected policy fields. They must
reconcile to the plan's mean with relative1e-9/absolute1e-7 tolerance; the screen rounds
only after that check. Magic stage probabilities describe reach, not success. Estimated
p90 is separate from its99% DKW uncertainty interval. Prices and bow utility are invented
inputs, quality20 is supplied and base cost0 means not priced by this example.

## Acceptance status

Evidence collector accepted5565ea7:16 lead-run focused tests. Synthetic JUnit4 cases with
2 passes/1 failure/1 skip; separate error1; two CoE rows have maximum absolute difference
0.03. Empty/nonfinite/stale artifacts and process startup failure cannot report success.

Report integration, fresh complete proof and real helmet/bow browser acceptance: pending.
