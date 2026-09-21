# Spec: preserve original English modifiers in production reports

Worktree `.worktrees/english-mod-labels` (branch `w-english-mod-labels`).
Luna/medium, bound 10 minutes. May touch ONLY `src/craftoracle/reporting.py`
and `src/craftoracle/report_assets/template.html`.

## Why
Owner requires original English modifier names/stat text everywhere. The lead updates
project rules and the prototype worker handles its standalone HTML. This slice fixes
the current production formatter; no layout integration or crafting calculation.

## Requirements
1. Replace localized modifier shorthand in route titles/instructions with English:
   `Фрактура здоровья T1 → Envy` becomes `Fractured Life T1 → Envy` in Python and JS;
   `_life_target_text` uses `Life T1 (<existing English label>)`, fallback `Life T1`.
   Actual complete stat labels must remain unchanged from source context.
2. Inspect both allowed files for other translated modifier names/stat text. Generic
   instructions about suffixes, prefixes, resistance selection may remain Russian.
   Do not translate English source data or invent labels/ranges.
3. No planner, Monte Carlo, CoE, evidence collector, full pytest, network or assets.
   Run existing focused report tests only. No new tests needed for this small label edit.
4. Commit explicit paths. Report hashes, changed text, exact focused test summary and
   any additional translated modifier labels found. Do not edit saved reports: lead
   refreshes those from existing plan/context without recalculation after merge.

## Facts / checkable values
This is D26 presentation only. For context.target.labels.IncreasedLife:1 equal to
`+(130-144) to maximum Life`, expected text is `Life T1 (+(130-144) to maximum Life)`.
Empty context gives `Life T1`. Both route-title mappings produce
`Fractured Life T1 → Envy`. No numeric calculation/output changes allowed.

## Numbers to report
2 title locations and 1 helper changed; focused report tests pass; 0 crafting runs.
Read `docs/WORKER_RULES.md` first; final report starts `=== FINAL REPORT ===`.
