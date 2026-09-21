# Spec: sourced ordinary nonhybrid fossil transforms and outcome distributions

Worktree: `.worktrees/ordinary-fossil-distributions` (branch `w-ordinary-fossil-distributions`).
May touch ONLY `src/craftoracle/fossils.py`, `src/craftoracle/actions.py`,
`data/rules/fossils.json`, `tests/test_fossils.py`.

## Why
Owner D21 unblocks CoE's ordinary additive model. Implement facts already interpreted in
docs/mechanics/fossils_resonators.md; unresolved hybrid/special recipes do not block this slice.
No new source research, pricing, loadout or policy changes. Bounded45minute worker task.

## Requirements
1. Encode the sixteen listed ordinary nonhybrid fossil IDs/names/tag factors in OUR small
   rule schema, with source pointers S3 functions/lines and S4 fossil IDs, read2026-09-21,
   confidence reimplemented-from-CoE and D21 default choice. Preserve the Bound/S56
   disagreement in metadata. Do not copy CoE compiled records or code. Unknown IDs and
   known excluded hybrid/special IDs reject with explicit Q13 or Q19 reason.
2. Exact transform uses Fraction arithmetic: per-tag positive sum (default) or product
   (explicit sensitivity); negative factors multiply; then matched positive tags again
   sum/product. Any matching block wins. No match means factor1. Opulent blocks tagless.
   S3 does NOT round;126*.15=18.9. Convert transformed positive pool weights to common
   integer units preserving exact ratios for accepted DrawEntry DP. Report the scale or
   expose rational effective weights for inspection. Never round independently per entry.
3. Inputs are ordinary rare items and a FULL Chaotic resonator of1..4 DISTINCT supported
   fossils. Optional explicit socket_count must equal selected count; duplicate/empty/5
   combinations fail. Normal/magic reject. Reuse Q9 special-item guards. Outcome-affecting
   side/type metamods reject; multimod alone is allowed and rerolled away (S17/S58).
   No fractured, influenced or legacy Alchemical input support in this spec.
4. Provide fossil_distribution(item,data,fossils,labels=None,*,mode="additive",socket_count=None)
   and a direct independent seeded apply_fossils(item,data,fossils,rng,...) -> ItemState.
   A caller-managed immutable prepared sampler plan is allowed; no cache keyed only by
   mutable ActionData identity. Standard rare count weights/caps/groups use accepted rules.
   Preserve internal group identities until final OutcomeClass projection. All old explicits
   reroll in this ordinary slice, source item remains unchanged. Keep all output classes.
5. Extend action_distribution with action="fossil", explicit fossil_ids and fossil_mode
   keywords; reject irrelevant fossil keywords on other actions. Do not change ordinary/
   Harvest semantics. Preserve existing call signatures via optional keywords.
6. Hand tests plus one real helmet distribution and independent direct MC, N10000,
   seed20260921, two-sided Hoeffding delta.001 bound0.019494746035204052. Tests check
   exact mass1, zero blocked weights, preserved input, valid caps/groups, source metadata,
   mutation freshness, default vs sensitivity. Keep focused suite well under a minute.
   Run python -m pytest -q tests/test_fossils.py tests/test_actions.py tests/test_harvest.py.

## Numbers a test must reproduce
Mathematical transforms from the sheet: weight100, factor3 and reduction.5 ->150; block->0;
two positive factors3/4 ->700 additive,1200 multiplicative; no factor->100.
Bound on synthetic minion+aura base100 ->2000 default (S56 alternative1000 remains metadata).
Real PoB LocalAddedFireDamageTwoHand10, bow base weight126, Serrated+Scorched:
2520 additive vs12600 multiplicative. One .15 reduction on126 ->189/10 exactly.
Toy one-draw A fire1,B cold1,C untagged2 distinct groups, Scorched ->A10,B0,C2;
P(A)=5/6,P(C)=1/6. Synthetic rare count1 here is a mathematical fixture, NOT a game count.
Two draws from that toy ->A+C probability1. Opulent on tagless C ->0; wholly empty pool
raises unreachable explicitly. At real Royal Burgonet86, Pristine+Aberrant: measure exact
P(IncreasedLife9 AND ChaosResist6 AND any FireResist8/ColdResist8/LightningResist8), classes,
unscaled/scaled totals, seeded successes/N and bound. Do not invent an expected game number.

## Numbers to report
All hand quantities; real pool totals/chance/classes, MC successes and bound, blocked-weight
violations0; exact source IDs and scale convention; focused tests, commits, files.
Final report begins `=== FINAL REPORT ===`. Future policy will use this accepted adapter.
