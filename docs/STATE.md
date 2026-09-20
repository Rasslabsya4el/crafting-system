# State — 2026-09-20

## What works and how to reproduce it

- Phase 0 is in progress. Twelve CoE files are cached once in `sources/raw/coe/`; no refresh
  or new CoE download this session. SOURCES records 25 source entries. Raw material and local
  PoB input remain ignored; only our own derived projection is committed.
- Offline method inventory: `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md`.
  It lists 95 nodes, 84 leaves, 13 custom subsets, 2 options; merge `cd5e976`.
- PoB projection: `python tools/build_pob_explicit.py` produces `data/pob_mod_explicit.json`:
  4310 distinct records, zero skips/errors, eight literal fields plus source_line; raw source
  hash and owner-supplied PoB 2.67.2 / PoE 3.29 labels. No tier or eligibility inference.
  Merge `b0a19ae`; two builds byte-identical. Output SHA-256
  `e09344ce07c248bfef894aaf85141b5ec9be87f10da1709527d29e657bb92fb9`.
- Validation: `python -m pytest -q` — 19 passing tests, well under one minute. Lead reran them
  on the final worker branch, reviewed code/tests and independently compared every projected
  field of every generated row to the source. No action engine tests exist yet.

## Design and source status

- BRIEF section 3b was read before engine design and is mandatory: calculators return outcome
  distributions; a spec accepts required mods OR a value table plus threshold; policies include
  stopping rules and report expected utility/cost, p90 cost, irreversible risk and rare inputs.
  D7 and `docs/design/build_contract.md` have two hand-computed threshold/cost examples.
  No item model, calculator, spec loader or ranker is implemented.
- `docs/mechanics/INDEX.md` exposes all requested families and remaining gaps. Detailed partial
  sheets: ordinary currency, affix generation, bench/metamods, essences, fossil weights, eldritch.
  Harvest and Awakener are partial source notes; fracture, veiled, recombination and corruption
  still lack complete algorithms/examples. Existence of a sheet does not mean completion.
- `docs/research/coe-calculator-and-policies.md` distinguishes CoE exact-labelled enumeration
  from extrapolation and describes conditional step routing. Its execution loop and some
  group/factorization behavior still need review. Our contract keeps full outcome distributions.
- Wiki is readable in the user-opened Codex browser. S21 table rechecked: resulting item's
  minimum required level is not an input ilvl gate. S23 Conflict wording disagrees with CoE's
  unconditional 50/50 branch at unequal tiers (Q11); approximate Wiki odds cite a player report.

## Incomplete / blocked assumptions

Q3 target ruleset is unanswered; local snapshot labels are retained as supplied. No current-patch
claim is inferred from the cache date. Q6 Harvest retention, Q9 item eligibility, Q11 Conflict
transition odds, Q12 incomplete families, Q13 fossil stacking/data and Q14 calculator correctness
remain unresolved. Builders for other PoB tables and the 50-mod/5-class CoE+PoEDB comparison
are not done. These gaps do not block source research; dependent engine paths must not guess.

## Active work and next three actions

Worker `pob-explicit-projection` (Terra/xhigh) accepted after one metadata correction. Commits
`a25c58b` / `a15925c`, acceptance merge `b0a19ae`; report and checklist in
`out/workers/pob-explicit-projection.md` (ignored). Prior inventory recovery provenance corrected
in WORKERS. The accepted worktree was removed without force.

Work continues after the checkpoint; phase 0 was not completed. Starting `pob-base-tags`
(Terra/xhigh) in its own worktree: 15-minute allowance for balanced parsing and five-file
provenance checks, commands light and bounded. Lead concurrently sources pool semantics and
prepares the 50-mod / five-class cross-check. Two workers maximum; no services. A second bounded worker `mod-crosscheck` receives a 20-minute allowance for offline comparison/report tests across five HTML caches; no single command should approach ten minutes. Lead has found group-label differences (Q16) and omitted multiplier/generated-tag fields (Q17).

1. Source base-tag/weight precedence and group/tier/range semantics; then specify the next PoB
   builder without claiming the current eight-field projection is a complete resolver.
2. Cross-check at least 50 mods over five item classes against CoE and PoEDB; log discrepancies.
3. Finish high-priority rule gaps and calculator/run-loop notes before a bounded distribution-first
   engine spec; retain all BRIEF 3b tasks, including the invented bow value-table example.
