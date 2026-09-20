# State — 2026-09-20

## What works and how to reproduce it
Phase 0 remains in progress. No crafting engine, item model, calculator or ranker exists yet.
The commands below are offline and need the ignored source snapshots listed in SOURCES.

| command / artifact | verified result | acceptance |
|---|---|---|
| `python -m pytest -q` | 48 passed, under one minute | lead ran after both merges |
| `python tools/build_pob_explicit.py` | 4310 literal records, zero skips/errors | b0a19ae |
| `python tools/build_pob_bases.py` | 375 records / 371 names, 5 files (95/29/48/123/80) | 3cb707d |
| `python tools/mod_crosscheck.py` | 54 mods, 5 classes; level/weight/range/side each 54 agreements; 33 matching groups, 21 label differences, 0 missing triples | d440ffd |
| `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md` | 95 nodes / 84 leaves / 13 custom subsets | cd5e976 |

Lead independently matched every projected field in all 375 base records to raw files and
independently checked all 54 comparison rows against raw PoB, CoE and PoEDB. Repeated base
names are source occurrences, not collapsed identities. JSON metadata retains owner-supplied
PoB 2.67.2 / PoE 3.29; upstream revision remains unverified (Q8).
Base output SHA-256: 4d7b1ac6c1c51bd692b622bf0b01e0e7199b66ef37e03762844c29b1a89d75ad.
Cross-check report byte SHA-256 in main: 4a5dd86f014dd3dafb4e3a204d0d5e77e0343a4685a5915f339d6b8bec5adb68.
The report also carries a separately defined canonical self-reference hash. Main uses LF
builder output; worker checkout used CRLF, so regeneration changed only input/output byte
hashes, not any of the 54 comparison results. Rebuild explicit JSON before regenerating report
if a future checkout converts line endings. Byte hashes intentionally describe actual inputs.

## Sources and mechanics
- Twelve CoE files cached once; no new CoE requests in this session. SOURCES has 41 entries.
  Raw third-party files and supplied PoB input remain ignored. No CoE code/data copied to src/data.
- Wiki works in the owner's existing Codex browser after authorization. No cookies exported,
  no challenge bypass. Selected observations are local paraphrases with permanent revision URLs.
- Five families expanded beyond inventory: fracture, veiled, corruption, Awakener, recombinators.
  Sheets retain preconditions, confidence, numerical examples and explicit unknowns. They are
  still partial; existence of a sheet does not mean a complete executable rule.
- S39 official 3.29 notes establish changed corruption socket outcomes and removed/replaced
  synthesis, beast split and Fractured Fossil actions. Q18/Q19 and patch_3_29.md preserve old CoE
  differences. New bench/Talisman actions have gates/costs, not complete algorithms.
- Awakener conflict survivor differs (Q20). Wiki recombinator count table conflicts with its own
  example (70 versus 72 percent, Q21); CoE and Wiki disagree on ilvl, count table and selection
  order/weighting (Q22). No current recombinator odds are approved for implementation.
- CoE per-action execution/routing read at 3365-3399: loop retains changed item; restart restores
  initial snapshot while action counters persist. Simulator snapshot reset is not free in-game
  recovery. Batch/budget/result aggregation and calculator group factorization remain unaudited.
- All 21 sample group discrepancies are separate rows Q16.01-Q16.21. Single PoB group is not
  proven equivalent to all exclusion families; multiplier/generated-tag semantics remain Q17.

## Build-system contract and blockers
BRIEF 3b was read before design and remains mandatory: stage outcome distributions; required
mods OR utility-table/threshold specs; policies with stopping rules; expected utility/cost,
p90 cost, irreversible risk and rare inputs. D7 and docs/design/build_contract.md give invented
hand-computed cases. Do not reduce state to a scalar when future transitions depend on it.

Q3 target patch unanswered; Q6/Q9/Q11/Q12/Q13/Q14/Q16/Q17/Q20-Q22 constrain dependent rules.
Unknown paths must fail explicitly, not guess. Other PoB family builders, complete stat/range
projection and general pool resolver remain unimplemented. These gaps do not block research.

## Worker and process status
Two new bounded worker specs prepared: pob-mod-families (about 30 minutes) and pob-recipes
(about 25 minutes). Longer than 10 minutes is justified by strict literal parsing, malformed-input
tests and deterministic snapshot verification; each command remains short, at most two workers.
Previous workers finished, lead reviewed and ran
branch tests, merged with no-ff, saved reports under out/workers and removed worktrees without
force. Only main checkout remains. WORKERS has acceptance rows. No external directories used.

## Next three actions
1. Pin target patch/mode (Q3), then resolve high-impact conflicts: Harvest retention Q6,
   Awakener survivor Q20 and recombinator probabilities Q21/Q22. Use existing Wiki browser.
2. Source remaining beast, Dominance, influence, synthesis, catalyst/quality and level conditions;
   complete special-action eligibility matrices. Review CoE batch/cost/result aggregation.
3. Specify missing PoB fields/family builders, then a bounded distribution-first exact
   calculator with sourced group assumptions and BRIEF 3b fixtures. Delegate implementation.
