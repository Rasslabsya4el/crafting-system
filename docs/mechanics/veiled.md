# Veiled Exalted, Veiled Chaos and unveiling

Status: reviewed, partial; offer probabilities unresolved. Read 2026-09-20.
Confidence: `documented` S34-S36; `datamined` S25; `reimplemented-from-CoE` S3 paths.

## Effects and preconditions
Veiled Exalted Orb removes one random modifier from a rare item, then adds one veiled modifier
(S34). Veiled Chaos Orb reforges a rare item including one veiled modifier (S35). Both exclude
Syndicate signature mods from the possible outcomes. S34 records renaming Veiled Orb to Veiled
Exalted in 3.26; S35 records Veiled Chaos reintroduced separately in 3.26. Chaos is not legacy-only.
S34 disallows Exalted on items with a veiled modifier or its craftable versions. Removal respects
prefix/suffix locks but not cannot-roll attack/caster modifiers. Other flags remain Q9/Q12.

## Observed steps
1. Exalted: validate, remove a permitted mod, recompute open slots, add a veiled placeholder.
   S3 lines 2281-2293 checks existing veiled/unveiled equivalents and errors if none removable.
2. CoE adds to the only side with room, or flips a fair prefix/suffix coin if both have room
   (2290-2292). It does not weight that coin by vacant slots. An old two-veiled path has
   rolled=99 followed by rolled<15: unreachable here, not a sourced 15% current chance.
3. Chaos: S3 2294-2298 rejects retained side-locked/fractured veiled equivalents before rare
   reroll with a forced veil. S35's short description does not independently prove that check.
4. Unveiling presents three random choices and the player picks one (S36). The resulting mod
   does not count as a crafted bench mod. Offer generation and policy choice are separate.

## Data and worked examples
S25 JunMasterAvoidStunAndElementalStatusAilments1 is Prefix, level1, weightKey
[body_armour,default], weightVal[0,0]. Those literal zeros do not establish an impossible unveil:
its offer pool need not use ordinary spawn weights.

CoE fixture: after a permitted removal, free prefix slots=1 and suffix slots=2 gives veil-side
probabilities 1/2 each. Prefix slots=0, suffix slots=1 gives suffix probability 1. Removal and
unveil probabilities remain separate factors. Synthetic policy fixture: an offered set with
utilities 2/7/4 and threshold 6 chooses 7 deterministically; no offer probability is implied.

## Comparison, conditions and gaps
S34 agrees with remove-then-add; S35 with the reforge effect. Three choices do not imply equal
mod weights or three independent draws. Do not reuse ordinary weights. Full `poec_simUnveilMod`
(S3 2841 onward), group blocking, tags, item-level gates and crafted equivalence need review.
Q3 ruleset; Q9 flag matrix; Q12 offer algorithm/weights/signatures. No action implementation.
