# State — 2026-09-20

## What works and proof commands
- Phase 0 remains in progress. Twelve CoE files cached once; no new CoE requests this session.
  `docs/SOURCES.md` records 40 sources. Raw CoE/PoEDB/Wiki and supplied PoB files are ignored.
- `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md`
  reproduces 95 nodes / 84 leaves / 13 custom subsets, acceptance cd5e976.
- `python tools/build_pob_explicit.py`: 4310 literal records, no skips/errors, acceptance b0a19ae.
  Eight fields plus source_line; no general tier/range/resolver semantics inferred.
- `python tools/build_pob_bases.py`: 375 literal base records / 371 names over five files,
  counts 95/29/48/123/80, acceptance 3cb707d. Repeated ring names retained by source path/line.
  All seven projected fields independently compared to raw sources by lead; two builds equal.
  Output SHA-256 4d7b1ac6c1c51bd692b622bf0b01e0e7199b66ef37e03762844c29b1a89d75ad.
- Latest lead-run suite on accepted base worker code: `python -m pytest -q`, 34 passed,
  well under one minute. No action engine, calculator, model or ranker is implemented.

## Source and design status
- Wiki browser access restored after restart and the owner's authorization; read the existing
  user tab without exporting cookies. Q5 resolved. Browser observations are paraphrases with
  permanent revision URLs, not a complete HTML cache.
- Fracturing, Veiled Exalted/Chaos, Vaal/Locus and Awakener now have partial sourced rules,
  preconditions and numerical examples. Recombinator remains inventory-only. INDEX exposes
  missing families and remaining limits; partial means scoped specs only, not complete rules.
- Official 3.29 notes S39 establish changed corruption socket outcomes and removed/replaced
  synthesis, beast split and Fractured Fossil actions. Q18/Q19 and patch_3_29.md preserve the
  disagreement with old CoE paths. Newly found bench/Talisman actions need full algorithms.
- Awakener conflicts differ: Wiki describes random discard; CoE keeps receiver and drops donor
  (Q20). General pool semantics remain incomplete: multi-family exclusions Q16 and omitted
  multiplier/generated-tag semantics Q17. Never silently normalize those source differences.
- BRIEF 3b is binding: outcome distributions, required-mod OR utility-table/threshold specs,
  policy stopping rules, expected utility/cost, p90 cost, irreversible risk and rare inputs.
  D7 and docs/design/build_contract.md provide synthetic arithmetic cases. Nothing is reduced
  to a target probability alone before the outcome distribution is available.

## Current work and limits
One worker active: mod-crosscheck (Terra/xhigh), existing isolated worktree, frozen 54-mod
comparison across five item classes. Sources including S27 five base files supplied locally.
Worker reports 54 level/weight/range/side agreements and 21 group-label differences; these are
NOT accepted until lead runs tests and reads the whole diff. Allow up to 10 more minutes for
source-provenance/report finalization; commands are bounded/offline, no background services.
Base worker finished; report saved, clean branch merged, worktree removed without force.

## Open issues and next three actions
Q3 target version is unanswered; owner-supplied PoB 2.67.2 / PoE 3.29 labels are retained but
upstream revision Q8 remains unknown. Q6/Q9/Q11/Q12/Q13/Q14/Q16/Q17/Q20 block dependent
mechanics, not independent source research. Remaining PoB family builders are unimplemented.

1. Accept or return the 54-mod comparison: run branch tests, inspect all rows/pointers, preserve
   each discrepancy in OPEN_QUESTIONS, merge with numbers and record WORKERS.
2. Finish recombinator and remaining action gaps; distinguish 3.29 replacements from frozen CoE
   behavior and investigate Awakener conflict/Harvest/Conflict probability questions.
3. Specify missing PoB fields/builders and a bounded distribution-first exact calculator only
   after its pool/group assumptions are explicitly sourced; keep both BRIEF 3b examples.
