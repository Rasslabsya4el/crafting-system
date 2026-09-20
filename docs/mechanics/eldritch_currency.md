# Eldritch currency and Orb of Conflict

Status: partial; current-rule odds and full eligibility unverified. Read 2026-09-20.
Confidence: `documented` for S23 Wiki item text, `reimplemented-from-CoE` for S3 behavior;
Wiki's approximate odds cite a player report and are not an exact transition table.

## Effect and preconditions

S3 has Chaos/Exalted/Annul, Ember/Ichor, and Conflict branches. Its method metadata requires
dominance for Chaos/Exalted/Annul and two eldritch influences for Conflict; the root category
has base-group restrictions and forbids ordinary influence (line 5). Full item flags remain Q9.
S23 Conflict item text requires a non-unique item with both Eldritch implicits; lowering a Lesser
implicit removes it. Wiki Mechanics gives 50% per side at equal tiers, and an approximate
relative-tier adjustment, citing Reddit reference 1. Do not convert that estimate into exact odds.

## Observed CoE steps and conditions

S3 `poec_simParseIAType` line 2114 maps red to Searing Exarch and blue to Eater of Worlds.
`poec_simUpdateDominance` lines 1990-1992 compares internal ranks: **smaller** rank is stronger;
equal ranks leave dominance null. A sole implicit gives its side dominance. Do not reverse this
using the Wiki tier numbering, where T6 is strongest.

- `poec_simApplyCraftGO` lines 2354-2358: Chaos removes unfractured explicits on the dominant
  target side (searing -> prefix; tangled -> suffix), retains the other side/fractures, then
  draws from the count table and clamps additions to the target-side capacity.
- Lines 2359-2362: Exalt adds one on that same target side. Annul's local variable is named
  `keep`, but it is passed as `atype`: `poec_simRemoveAffix` line 2500 preserves the opposite
  side. Thus the observed Annul also targets searing -> prefix, tangled -> suffix. Fractures
  and applicable metamods further restrict eligible removals (2499-2511).
- Lines 2363-2370: Conflict selects a side with `poec_rand(0,2,true)` and changes the two
  implicit tier indices, removing the lowered implicit at its bottom tier.
- Line 2372: lesser/greater/grand/exceptional Ember/Ichor calls use internal ranks 6/5/4/3.
  These internal values are not item levels or Wiki T1..T6 labels.

## Disagreement and examples

CoE's Conflict side selection is an unconditional 50/50 draw, without a relative-tier comparison.
S23 says unequal tiers change the odds. Q11 records both; do not implement the CoE simplification
as current-game probability. At equal tiers, the Wiki gives probability 1/2 for raising a chosen
side. Its worked 5/3 -> 6/2 example is approximately 28%, not an exact calculator fixture.
Lowering Lesser leaves 0 implicits of that influence (S23 item text); upper endpoint behavior
still needs a complete documented table.

## Metamods and unknowns

S17/S14 say Eldritch Chaos ignores side locks; S17 says it respects cannot-roll attack/caster.
See [bench_metamods.md](bench_metamods.md). This does not establish identical behavior for all
Eldritch actions. Q3/Q9/Q11 remain open; no action implementation is authorized by this partial sheet.

## Independent Wiki conditions and examples
S52 Eldritch implicit modifier and S53-S55 currency tooltips, read 2026-09-20:
- Ordinary Ember/Ichor application concerns non-unique helmets, gloves, boots and body armours;
  conventional influence is incompatible. Fractured items can carry these implicits. Amulet
  exceptions exist, but the page explicitly says Embers/Ichors cannot add them to amulets.
- Six named tiers run Lesser, Greater, Grand, Exceptional, Exquisite, Perfect. The first four
  are currency tiers; the last two require Conflict. First application replaces ordinary base
  implicits; the item can then hold one of each eldritch side. S50 separately covers synthesis.
- Higher tier dominates, a sole side dominates, equal tiers have no dominance. S53/S54
  require rare rarity for Chaos/Exalted; S55 Annul permits magic or rare.
- Independent tooltips confirm Exarch -> prefixes and Eater -> suffixes for all three actions.
  Example: Greater Exarch plus Lesser Eater targets prefixes; two Greater implicits cannot
  use a dominance-dependent action. With one legal prefix candidate, successful Exalted
  adds exactly 1 prefix and 0 suffixes; count limits still apply.
- A synthetic Annul candidate set of two removable prefixes under Exarch dominance gives
  intended 1/2 each under S3's equal candidate weights. Wiki establishes the side, not the
  equal-odds distribution; protected/fractured candidates must be excluded first.

S52 still mentions historical splitting/synthesising; S39's 3.29 removal/replacement conditions
override availability claims for those actions (Q19). Ember/Ichor pool weights and all special
base exceptions need a future bounded spec; data definitions alone do not resolve Q9/Q12.

Sources: S3 `sources/raw/coe/package.js` functions/lines above, S17 Wiki Metamod, S23
https://www.poewiki.net/wiki/Orb_of_Conflict (read 2026-09-20 through the existing browser).
