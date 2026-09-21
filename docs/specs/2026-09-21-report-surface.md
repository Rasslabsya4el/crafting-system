# Spec: final readable offline report template

Worktree .worktrees/report-surface, branch w-report-surface. Terra high, bound35minutes.
Read docs/design/route-report.md in full. The current report worker owns the Python model
and CLI; you own ONLY src/craftoracle/report_assets/template.html and
tests/test_report_template.py. No crafting decisions. No skills or reads outside crafting.

1. Standalone HTML/CSS/JS template with literal placeholders {{REPORT_TITLE}} and
   {{REPORT_DATA}}. Python supplies an escaped title and safe JSON payload (less-than escaped).
   No external resources/network/server requirement. Dark theme, costs/counts/utility/%
   one decimal. Intrinsic ilvl/tier/counts are integers. Probability0.000024282 displays
   <0,1% and approximately1 in41183; full precision stays in JSON/audit. Cost1927.479966
   displays1927,5. Use Russian prose and exact English currency names.
2. Full-width comparison table, then selected route detail, then evidence. Avoid squeezing
   six columns into450px. Readable at1440 and narrow viewport; horizontally scroll tables
   if needed rather than splitting every word. Search retains focus/caret. Row selection
   highlights and opens correct unique key; keyboard and hash work with no Event/string bug.
   Show all12 helmet/all14 bow rows, default cheapest. Link back to comparison.
3. Use the model's instructions verbatim. Show selected threshold; target criteria/any_of
   or readable utility value table from context.target. Target stat_text is exact source text.
   Clear invented-price/utility notice, quality supplied/base cost0 unpriced. Unit once in
   headers. Use exact context.essence_names, fossil_names for readable titles; no ID guessing.
4. Mean versus p90 explanation. Estimated p90 interval/confidence/samplecount/seed separate
   from player cost spread. Stage meanings verbatim. Materials count/unitprice/spend and
   reconciliation state. Route metadata holds Magic success_probability=1/T (when supplied),
   protected early_completion_probability, fracture risk/discard counts. Show those with
   explicit conditioning. Raw audit/assumptions/source and outcome fields collapsed.
5. Evidence from design schema: actualcounts,status,revision/time and stale/dirty flag.
   Searchable testcases grouped by file; failed messages visible. All CoE cases columns:
   id/action/base/targets/ours/coe/relative_difference*100. Cases validate components, not
   complete routes/live game. Never fabricate status; missing evidence explicit. Commands,
   exitcode/durationminutes/loglinks; raw plan.json link and artifacts links. Files copied
   by otherworker. Testlinks can filter component module names; label scope explicitly.
6. Escape every data string inserted asHTML; validate artifact hrefs as relative local
   paths (reject schemes/..). No script execution from values. Lightweight tests for pure
   JS formatting/escaping/filter/selection if practical via installed node (no npm/network).
   Fixtures two duplicateIDs at thresholds60/100 retain two keys; injected </script> markup
   remains text. No fullpytest/planner runs. Generate a preview fixture under ignoredout.

Model: JSON object input/prices/assumptions/routes/unavailable/evidence/context. Eachroute
key,id,name,expected_cost,cost_p90,cost_label,expected_utility,frontier,stopping_threshold,
stages[{name,probability,expected_attempts,meaning}],parameters,decisions,metadata,source,
instructions[],accounting{rows[{currency,count,unit_price,spend}],total,complete,reason}.
Metadata preserves cost_p90_interval,cost_confidence,cost_sample_count,cost_seed,
cost_error_bound and recovery fields. Context generation{commit,generated_at}, target
{criteria[{group,max_tier,text}],any_of[[...]],value_table,threshold,values_note,labels},
essence_names,fossil_names,bench_recipes. Evidence has artifacts paths copied relative to
the report directory. Coordinate any newfield with lead; do not edit otherworker files.

Report commit, focused tests, fixture path and any omitted requirement explicitly.
