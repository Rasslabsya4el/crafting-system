# Awakener's Orb

Status: reviewed, partial; conflict resolution disagrees across sources. Read 2026-09-20.
Confidence: `documented` S40 Wiki Mechanics; `reimplemented-from-CoE` S3/S13.

## Effect and preconditions
The donor is destroyed and its influence transferred to a receiver of the same item class.
Each input must have one influence, different from the other's, and neither can be corrupted
(S40). The receiver becomes rare, retaining its base, item level, sockets, links, quality and
enchantments. One influenced modifier per input is retained except conflicts, and other mods
reroll. Transferred tiers remain, but numerical rolls within those tiers can change.
Metamods are ignored. An imprint can restore the receiver, not the destroyed donor (S40).
Complete mirrored/split/other eligibility remains Q9.

## Scoped rule steps
1. Validate both inputs. A donor is a consumed rare input in a policy (BRIEF 3b).
2. Select influenced modifiers. S40 says random selection if an input has several; it does not
   give an independent probability table.
3. Check shared exclusion families before keeping both selections. S40 says one conflicting
   mod is discarded at random, but also flags uncertainty about non-ModGroup exclusions.
4. Preserve receiver properties, add the second influence, retain selected tiers, reroll values
   and fill remaining affixes from the appropriate pool. Filling/level gates remain partial.

## CoE algorithm and discrepancy
S3 `poec_simAwaken` 1926-1933 checks matching bgroup, one different donor influence and
influenced affixes. It enumerates receiver/donor pairs whose mgrp and id differ, then selects
uniformly using `poec_rand(0,nvcombs.length,true)`. Here mgrp identifies influence membership;
it must not be confused with the separate modgroups exclusion array (Q16).
Dispatch 2299-2301 adds the donor influence and calls rare reroll with the picked pair.
In `poec_simRerollItem` 2443-2446, any shared modgroups entry causes the donor mod m2 to be
omitted while receiver m1 is always retained. Values are rerolled. This deterministic receiver
preference differs from S40's random discard: Q20. Do not turn either into an unqualified
current-game probability without resolving it. CoE also disables receiver ilvl below 68 at
2006; that gate is not independently corroborated by the read Wiki Mechanics paragraph.

## Worked examples
With exactly one influenced mod on each legal input, different IDs and no group conflict, the
retained tier pair is certain under both sources. This does not guarantee a target value roll
or any additional affix. Under the scoped CoE selector, two eligible influenced mods per input
with all four pairs admitted produce four selected pairs, each 1/4. A specific pair is 1/4.
If selected mods conflict, CoE keeps receiver m1 with probability 1; the Wiki describes random
discard without specifying equal odds. The discrepancy is recorded, not averaged away.

## Open questions
Q9 legality and ilvl gate; Q12 full fill/pool behavior; Q16 family semantics; Q20
conflict survivor. No action/calculator implementation is approved for conflicting inputs.
