# State — 2026-09-20

## Current milestone and target

Phase 0 knowledge harvest is complete against the BRIEF exit criteria (acceptance 68dd82d;
checklist in `docs/research/phase0-coverage.md`). Target: ordinary PoE 3.29, explicitly
confirmed by the owner (Q3/D11). No crafting engine, item model, calculator or ranker exists yet.
Completion means reviewed source material and selected data, not resolved odds for every action.

## What works and how to reproduce it

Run in crafting/. Commands are offline; snapshot tests require the ignored local inputs in SOURCES.

| command / artifact | verified result | acceptance |
|---|---|---|
| `python -m pytest -q` | 78 passed, under one minute, no skips in this checkout | lead ran combined main after both merges |
| `python tools/build_pob_mod_families.py` | 10555 records: Explicit 4310 / Veiled 258 / Eldritch 4086 / Corrupted 371 / Delve 186 / Synthesis 1344; zero skips/errors | 375528a |
| `python tools/build_pob_recipes.py` | 732 bench rows, 105 essence rows, 2310 class mappings / 622 distinct referenced mod IDs, none missing | 8d49e8f |
| `python tools/build_pob_explicit.py` | initial narrow projection, 4310 records, zero skips/errors | b0a19ae |
| `python tools/build_pob_bases.py` | 375 source occurrences / 371 names, 5 files (95/29/48/123/80) | 3cb707d |
| `python tools/mod_crosscheck.py` | 54 mods / 5 classes; 54 agreements each for level, weight, range and side; group labels 33 equal / 21 different; missing triples 0 | d440ffd |
| `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md` | 95 nodes / 84 leaves / 13 custom subsets | cd5e976 |

The lead independently matched every projected field of all 10555 family records, all 837
recipe records and all 375 base occurrences to the raw sources, and checked every raw-source
row of the 54-mod comparison. Builders preserve source hashes, order and lines. Repeated base
names are occurrences, not collapsed identities. Source version is owner-supplied PoB 2.67.2 /
PoE 3.29; upstream revision remains unverified (Q8).

Full family data retains literal stat strings, ordered weights, optional tags/multipliers and
six fractional statOrder values. It does not infer game stat IDs, tiers or group equivalence.
The initial explicit JSON remains for the existing cross-check consumer (D12).

Reproducible UTF-8 LF output SHA-256 values:

- Family: a37bd981e34e1d43cbb12c1b7009ab86cc63fa357bdaba41ad20d8d2ba39aee4.
- Bench: ed9666c32a65744efe0428ccf5876d20b2523e3efdc7ffc3db3aae8a4251c4b5.
- Essence: 280dc5026636cd7551337ad49b8e5abda082edbf99aae9f1fd3f9004cf9503c3.
- Bases: 4d7b1ac6c1c51bd692b622bf0b01e0e7199b66ef37e03762844c29b1a89d75ad.

The cross-check byte hash in main is 4a5dd86f014dd3dafb4e3a204d0d5e77e0343a4685a5915f339d6b8bec5adb68.
It also carries a separate canonical self-reference hash. Git may convert checkout line endings;
regenerate explicit JSON before regenerating that report. Byte hashes describe actual bytes.

## Sources and mechanics

- 12 public CoE files cached once; this session read only their frozen copies. 62 source rows
  and 20 fact sheets plus INDEX. Raw third-party material and supplied PoB inputs remain ignored;
  no CoE code or compiled data copied into src/data.
- Wiki works through the owner's existing authorized Codex browser. Selected paraphrases and
  permanent revision URLs are cached locally; these are not full-page captures. No cookies exported.
- All required BRIEF action families have source-qualified preconditions, steps, numerical
  examples, confidence labels and open questions. Additional sheets cover beasts, Dominance,
  influence orbs, Blessed, synthesis and quality. Optional catalogue families remain backlog.
- Official 3.29 changes take precedence over old frozen actions: changed corruption sockets,
  synthesis availability, beast split replacements and Fractured Fossil (Q18/Q19). Ordinary
  resonators require rare inputs; legacy/Ruthless Alchemical inputs are separately scoped (Q30).
- CoE calculator exact/extrapolated branches and simulator routing, reset, batch, success,
  resource and cost aggregation are reviewed. Its displayed mean rounds quantities up, and its
  cheapest/costliest sort is by action count, not price (Q28); neither defines our future metrics.
- S7 contains 52 guide references (37 video / 15 written), not guide bodies. Linked contents
  were not claimed as read. CoE inventory entries are not proof of current availability.

## What remains unsupported

Source conflicts remain explicit: Harvest retention Q6; Conflict odds Q11; special eligibility
Q9/Q12; fossil stacking Q13; CoE exactness on overlapping groups Q14; canonical groups and
multiplier/generated-tag semantics Q16/Q17; Awakener conflict survivor Q20; recombinator
counts/algorithm Q21/Q22; current quality increments/rounding Q23; Blessed exclusion Q24;
beast exchange details Q25. Other questions and overview discrepancies remain in OPEN_QUESTIONS.

Extraction is complete for the selected Phase 0 tables, but numeric stat/range interpretation,
complete base identity, other item classes and a general pool resolver are future work. A rule
with an unsourced dependency must raise NotImplementedError with its question ID when reached;
source uncertainty is not permission to guess or advertise an exact full-game calculator.

## Mandatory next-stage contract

BRIEF 3b, D7 and `docs/design/build_contract.md`: return stage outcome distributions, accept
required mods OR a utility table with threshold, retain states needed by later decisions, and
evaluate policies with stopping rules. Report expected utility/cost, p90 cost, irreversible
risk and rare inputs. CoE success-only frequencies or rounded display costs are insufficient.

## Worker and process status

Both new workers completed. The lead reviewed full diffs, requested parser corrections, ran
each final branch suite, checked all specified numbers, merged with no-ff and saved reports in
out/workers. WORKERS has both acceptance rows. All worker worktrees were removed without force;
only main remains. No worker jobs or background processes were left running. No external
filesystem paths were used. Implementation stays delegated under a bounded spec, at most two
workers. The completed 25/30-minute budgets covered literal parsing and malformed-input checks;
no individual command approached ten minutes.

## Next three actions

1. Design a bounded Phase 1 item/outcome representation and exact draw contract using BRIEF 3b
   and the existing synthetic fixtures; specify preserved state and unsupported source branches.
2. Resolve Q16/Q17 for the first concrete item-class pool, then write a sourced resolver spec.
   Until then, use explicitly synthetic pools only; do not claim real-item probabilities.
3. Delegate exact distributions and spam-policy costs with hand-computed acceptance numbers,
   followed by a seeded Monte Carlo check. Keep optional catalogue work and unresolved special
   actions visible in TASKS, outside the first executable slice.

## Night log
- 00:05 — read GOAL and repository rules; item-model pool spec written, worker launch next.
