# Orb of Dominance and elevated modifiers

Read 2026-09-20. Confidence: `documented` S43; selection odds `reimplemented-from-CoE` S3.
The action removes one influenced explicit and upgrades another. Eldritch implicits use
Orb of Conflict instead; the similar names do not imply shared mechanics.

## Preconditions
S43 permits magic/rare Body Armour, Boots, Gloves and Helmets with at least two influenced
modifiers. Both single and dual conventional influences work. Legacy or protected modifiers
are unaffected; no minimum item level is required to elevate a highest-tier modifier.
Full mirrored/corrupted exception handling remains Q9. An available source row is not proof
that a particular elevated transformation exists in the accepted data projection (Q12).

## Rule steps
1. Find eligible conventional influenced explicits, excluding modifiers protected by side locks.
   S3 2302-2303 implements this side filtering; S43 independently describes protection.
2. S3 2304 selects one eligible removal index uniformly, then one different eligible upgrade
   index uniformly. S43 says random selection but does not independently prove equal odds.
3. Upgrade one tier; highest ordinary tier becomes elevated. Selecting an already elevated
   modifier rerolls its values (S43 tooltip; S3 2304). Remove the other selected modifier.
4. S3 reads the elevated mapping from `maeven.bmods`/`maeven.ind`, not an inferred tier name.
   Our PoB projection does not yet provide a verified complete elevated mapping.

## Numbers and examples
For N eligible mods under the CoE algorithm, each ordered remove/upgrade pair has probability
1/[N(N-1)]. N=2 gives two outcomes, each 1/2. N=3 gives six outcomes, each 1/6; one specified
mod is upgraded with probability 1/3. These are mathematical consequences of S3's two draws,
not additional datamined drop weights. The source uses half-open index draws here, avoiding Q2.
S43's tier example: T3 becomes T2; T1 becomes elevated; elevated stays elevated with rerolled values.
An item with only one eligible modifier after locks fails S3's N>=2 test (2304-2305).

## Metamods, comparison and open questions
Side locks protect against both selected operations. Attack/caster removal restrictions are
not tested by S3's local selection loop; do not infer them from Annulment. S43 identifies legacy
mods as protected, whereas this local CoE loop only checks influence group and side locks.
The required legacy filter and full elevated mapping remain Q12; eligibility remains Q9.
No current-game equality claim beyond the documented tier transformation is approved.

Sources: S43 https://www.poewiki.net/index.php?title=Orb_of_Dominance&oldid=1699839,
Mechanics and tooltip; S3 package.js `poec_simApplyCraftGO`:2302-2305.
