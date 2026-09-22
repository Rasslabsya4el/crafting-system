# Current state -- report v2 merged, engine work parked (2026-09-22)

Owner decision 2026-09-22: this project is run by the Claude lead of poe-junkroan-v2; Astra no longer works here.
Report v2 (brief `docs/briefs/2026-09-22-report-ui-v2.md`, branch `lead-report-ui-v2`, a428cb9 + e3e2610) is merged
after the owner's look ("вроде норм"): English, game tooltip card, route rows as ordered actions, a crafting flow
whose steps are ACTIONS (bench crafts titled "Crafting Bench: <recipe>", payments shown under them), one-line steps,
costs per success, evidence split into `evidence.html`. Engine numbers byte-identical (plan.json); 434 tests pass.
Commands: `python -m craftoracle report examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
--output-dir out/reports-v2/helmet` (and `examples/bow_value_table.yaml ... --compare-thresholds 60,100
--output-dir out/reports-v2/bow`).

PARKED (the owner: engine work later, the main build system first). Open engine question for the next engine task:
the protected-prefix routes search `min_elemental in (1, 2)` (`optimizer.py:552`, `605`, `887`; gate
`_preparation_classes` `optimizer.py:823-839`; pick = lowest mean `optimizer.py:742-750`) and the helmet's route 2
picked 2 although the target needs ONE of Fire / Cold / Lightning T1. Accepting >= 1 is a superset of >= 2 with the
same finishing step, so it cannot cost more -- a cost picked 2 as cheaper points at a modelling error. Check before
trusting any protected-prefix number. Also owed: rare/magic affix-count weights and fossil stacking are taken from
Craft of Exile; spot-check them against the wiki.

# Current state — simplify crafting instructions (2026-09-21)

## Owner request and current output

Owner rejected the first three-view prototype: too much prose, vague preparation/state
labels, important rules in tiny subtitles, duplicate before/after items. Technical QA
passed but usability failed. D27 supersedes D25 presentation; do not ask for an A/B/C
choice again. Revised artifact completed: one direct three-step flow, Envy -> bench plus Scour ->
Exalt. Branches say exactly what finishes, passes or repeats. Two item cards are shared
results feeding the next step; no before/after pairs. Costs/evidence stay collapsed.
Contract:docs/specs/2026-09-21-simple-route-flow.md. Q31 is owner readability review.
Artifact:docs/prototypes/route-layouts.html. Worker66a8c4c/9723cef/bab7b7d; lead0e4491d
clarifies minimum2 open prefixes. Lead reviewed whole HTML and verified3 steps,2 cards,
12 slot rows,1 closed disclosure,0 tabs/scripts. Browser links1->2->3->1 pass;390px
no document overflow,0 script errors. Owner readability approval still pending.
No new crafting calculations in this task.

D26: ALL modifier names and stat text remain original English everywhere. Rules
f1cbaf8; prototype6340fbe; production label formatter9b0ab99 (worker285cc34). Lead
ran13 existing focused report tests in under0.1minute. Saved12 helmet/14 bow report
rows refreshed from existing plans/context/evidence; only labels/instructions changed.
Every other route field and saved plan bytes remained identical.

## What works and proof

Calculation baseline02bceff: ordinary PoE3.29 distributions, exact/seeded policy costs,
bounded parameter search, terminal utility and finite template ranking. Last FULL
proof:423 tests passed in0.9minute;12 offline CoE component cases across5 bases,
max relative difference2.08735%. This is historical proof, not a new check of the UI.
Saved reports:out/reports/helmet/index.html and out/reports/bow/index.html. All26 material
totals agree with saved expected costs. Proof:out/evidence-final/proof.json.

Focused presentation check:
`python -m pytest -q tests/test_report.py tests/test_report_template.py`

Full historical reproduction (DO NOT run for this output-only task):
`python -m tools.collect_evidence --output-dir out/evidence-final`
`python -m craftoracle report examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --output-dir out/reports/helmet --evidence-dir out/evidence-final`
`python -m craftoracle report examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --output-dir out/reports/bow --evidence-dir out/evidence-final`

## Facts and limits to preserve

Frozen protected Envy recipe/odds:docs/design/route-layout-proposals.md. Early finish
wins; passing Envy has3 occupied suffixes (Envy ChaosResist6 plus2 elemental T1), at
most1 prefix. Bench729 is a prefix; protected Scour clears all prefixes including it.
Up to3 Exalts check LifeT1 each time; full3 misses reset toEnvy.6.7% is WHOLE-series
success, not per-Orb chance.98.6% is completed-route share ending duringEnvy, not per-use.

C01..C03 are same-helmet COMPONENT checks; C04..C12 other-base engine regressions.
None validates the whole protected route. See docs/validation/coe_cases.md.

Finite template library, not general arbitrary multi-step discovery/global optimum.
100000-state benchmark solver is parked. Prices/bow utility invented; quality supplied;
base0 unpriced. D14/Q16/Q17 pool semantics provisional. Harvest first_only/Q6 sensitivity
explicit. Source gates:recombinationQ21/Q22, AwakenerQ20, unequal-tier ConflictQ11,
veiledQ12, special fossilsQ13, quality/TaintedQ23, special eligibilityQ9/Q18/Q19.

## Next three actions

1. Receive owner readability feedback on the displayed simplified D27 flow.
2. Apply the readable output contract to real reports after owner feedback.
3. Revisit deeper strategy discovery only after the output is readable.

No orchestration skills; all work remains inside crafting. All workers finished and
their committed worktrees removed without force. Temporary preview server stopped.
Preview command:
`python -m http.server 8766 --bind 127.0.0.1 --directory docs/prototypes`
Browser tool blocks local file URLs; owner can open the standalone HTML directly.
Loaded inline preview remains interactive after server stops; refresh needs restart.
Worker ledger:docs/WORKERS.md. Validation:docs/validation/route-layout-prototype.md.
