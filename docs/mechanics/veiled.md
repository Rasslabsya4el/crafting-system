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
mod weights or three independent draws. Do not reuse ordinary weights. Current-game pool
weights, item-level gates and crafted equivalence still need independent review.
Q9 flag matrix; Q12 offer algorithm/weights/signatures. No action implementation.

Recheck2026-09-21: S14's complete encoded matrix has side locks yes/yes and attack/caster
no/no for its historical Veiled orb row. S17 current Wiki has the same side-lock distinction
for Veiled Exalted. Its linked forum S71 was read in full: Guy_GGG discusses Wiki affiliation,
not the mechanic; do not promote the neighbouring player explanations to official evidence.
This confirms the existing documented interaction scope, while offer weights/mappings remain
the next numerical dependency. A supported removal alone is not a complete unveiling policy.

## Frozen CoE offer algorithm reviewed
S3 `poec_simUnveilMod` 2841-2857, read 2026-09-20 (`reimplemented-from-CoE`):
1. Gather existing explicit modgroups and additional mod groups; choose the veiled placeholder
   and its prefix/suffix side. The ordinary PoE1 branch is separate from PoE2 desecration.
2. Use that side's veiled pool; remove existing-group conflicts and `vex != 0` entries. Read
   the candidate's first tier weight. This is CoE's curated offer pool, not directly PoB spawn weights.
3. Request 3 choices, stopping early if the pool is empty. Pick via integer [0,total) with
   half-open cumulative ranges, then remove the chosen entry and every candidate sharing any
   chosen modgroup. Unlike Q2's other sampler, these endpoints are internally consistent.
4. Present the choices; the user's policy selects one (2868-2875). The source filters additional
   mod groups initially, but the compact candidate records do not carry `amg`; do not assume
   that later `amg` checks establish complete pairwise exclusion between offered choices.

Synthetic fixtures under this algorithm: 4 equal-weight independent groups yield a specified
mod in 3 offers with probability 3/4; each unordered offer triple has probability 1/4.
If only 2 compatible groups exist, it returns at most 2 choices rather than duplicating one.
These are source-algorithm arithmetic fixtures; S36's usual three-offer rule does not independently
prove how the live game handles an exhausted offer pool. Q12 retains that edge case and mapping.
