# Fracturing Orb

Status: reviewed, partial. Read 2026-09-20. Confidence: `documented` for S33 eligibility and
effect; `reimplemented-from-CoE` for uniform selection. No engine implementation.

## Effect and preconditions
A Fracturing Orb locks one explicit modifier on a rare item with at least four explicit
modifiers without rerolling the others (S33 item text and Mechanics). S33 excludes influenced,
synthesised and already fractured items, allows eldritch implicits and Split, and excludes
strongboxes. Its version history says 3.29 removed synthesised from item text but retained the
restriction on existing Standard items. Corrupted/mirrored eligibility remains in Q9.

## Rule steps and probabilities
1. Validate the conditions before selecting an explicit modifier.
2. Select one modifier and mark it fractured, retaining all values and other modifiers.
3. Keep failed-target states: an unwanted fracture is not an unchanged retry (BRIEF 3b).

S3 `poec_simApplyCraftGO` 2280-2281 builds an index list of all existing affixes in PoE 1 and
uses `poec_rand(0,n,true)`: each index gets probability `1/n`. Its veiled-placeholder exclusion
is PoE 2 only. This zero-based call covers every index, unlike the one-based weight draws in
Q2. Wiki's word random alone does not independently prove equal odds; label the formula CoE.

## Interactions and source comparison
S33 says metamods are ignored and imprints cannot undo fracturing. S3 selects from all affixes
without side protection, agreeing on the former. Bench/veiled target eligibility and special
items are not independently audited. Neither item text nor the random-selection branch alone
is the complete legality check.

## Worked examples
Under the scoped CoE rule, a legal four-mod item A/B/C/D has four resulting fractured states,
each probability 1/4. One desired mod gives p=1/4; two acceptable mods p=1/2. Six mods with
one target give p=1/6. These are arithmetic consequences of S3, not game measurements.
A repeat policy must price a replacement base and its preparation after an unwanted fracture.

## Open questions
Q3 target ruleset; Q9 remaining flags; Q12 independent odds and bench/veiled target eligibility.
