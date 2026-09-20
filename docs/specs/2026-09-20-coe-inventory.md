# Spec: offline mechanical inventory of cached CoE methods

Worktree: `.worktrees/coe-inventory` (branch `w-coe-inventory`). Target: 15 minutes,
split/report a blocker if this needs substantially more. You may touch ONLY
`tools/coe_inventory.py`, `tests/test_coe_inventory.py`, `docs/research/coe-method-inventory.md`.
The lead provides ignored `sources/raw/coe/package.js` inside this worktree.

## Why
The phase-0 lead needs a complete list of action keys, options, and source pointers without
spending research time on repetitive extraction. You extract syntax; the lead alone decides rules,
confidence, current-league availability, and the final action catalogue.

## Requirements
1. Write a standard-library Python offline reader and command:
   `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md`.
   No network, external paths, JavaScript execution, eval, or third-party dependencies.
2. Extract the object assigned to `var poec_cmethods=` using a small string-aware scanner/parser.
   Required supported syntax is objects, arrays, quoted keys/strings, numbers, `!0`/`!1`, null,
   and dotted identifier references such as `poec_constants.constraints.veil_bgroups`.
   Preserve dotted references as explicitly unresolved expressions. Unsupported syntax must raise
   a clear error rather than disappear. Do not parse or execute the rest of the application.
3. Walk all nested `subset` dictionaries. Emit one table row per named method node, including root
   categories; include full key path, name, custom subset marker/subsim, local `required`/`cannot`,
   `nosim` and option IDs/defaults/choice values when present. Record absent flags as absent;
   never infer availability. Do not dump full descriptions or compiled item/mod data.
4. Each row must cite original `package.js` line and a searchable key path. Include source SHA-256,
   extraction command, total nodes, leaf nodes, custom subsets, and option count. Preserve source
   order and produce deterministic output. This is mechanical evidence, not an approved fact sheet.
5. Also list declaration lines for these exact names when present: `poec_simApplyCraftGO`,
   `poec_simRerollItem`, `poec_simRollAffix`, `poec_simRemoveAffix`, `poec_simClearItem`,
   `poec_simRerollValues`, `poec_simRecombinate`, `poec_simCheckHReroll`,
   `poec_computeBestFossils`, `poec_simRollImplicits`, `poec_nsimExecute`,
   `poec_simApplyBenchCraft`. Mark absent names absent; do not invent a call graph.
6. Tests first using tiny synthetic strings authored for this task, not copied CoE data.
   Test counts/path order, strings with braces/escaped quotes, unresolved references/booleans,
   unsupported input, and deterministic rendering. Real-cache extraction must also run, and
   the report must confirm anchors `currency.transmute`, `currency.woke`, `eldritch` exist.
7. Keep this narrowly scoped. No changes to lead docs, source cache, or game engine. Explicit commits.

## Facts this implements
No game rules. Source S3 is the cached CoE application, fetched 2026-09-20.
The following are synthetic parser acceptance numbers, chosen by the lead, not game facts.

## Numbers a test must reproduce
- Input `var poec_cmethods={"currency":{"name":"Currency","subset":{"a":{"name":"A"},"b":{"name":"B","subset":"custom","nosim":!0}}}};`
  gives 3 nodes, 2 leaf nodes, 1 custom subset, in order `currency`, `currency.a`, `currency.b`.
- `!0` -> True, `!1` -> False; a reference `poec_constants.constraints.example` stays unresolved
  and is printed verbatim, not silently converted to a boolean/string-valued game fact.
- Input with a named method containing options `[ {"id":"mode","default":"x","choices":[{"value":"x"},{"value":"y"}]} ]`
  exposes 1 option, 2 choices, and default `x`.
- Unbalanced input and an executable value such as `function(){}` are rejected (2 failures).
- Rendering the same parsed source twice gives byte-identical output (1 comparison).

## Numbers to report
Synthetic node/leaf/custom counts 3/2/1; option/choice counts 1/2; rejected input count 2;
determinism comparisons 1; real-cache nodes/leaves/custom/options and declaration matches;
exact pytest summary and measured duration in minutes. Report source hash, commit IDs,
changed files and any unsupported syntax. No confidence labels or mechanics judgments.

Rules: `docs/WORKER_RULES.md`, AGENTS.md sections 1, 2, 3, 5. Final report starts
`=== FINAL REPORT ===`. Work only in the named worktree, no additional agents.
