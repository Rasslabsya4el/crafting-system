# Blessed Orb

Read 2026-09-20. Confidence: `documented` S51; sampler `reimplemented-from-CoE` S3.
Blessed rerolls numerical implicit values while retaining implicit identities. It does not
reroll explicit affixes or replace an implicit with a different mod.

## Preconditions and steps
S51 requires at least one implicit with a nontrivial value range. Items without implicits,
fixed-only implicits and corrupted items are not eligible in the ordinary rule. Synthesised
and eldritch implicits are supported. Additional exceptional modifiable-corrupted states
are not approved by this sheet (Q9).
1. Identify rollable implicit ranges; keep their identities and tiers.
2. Draw replacement values. S51 says the original implicit value cannot recur. Whether that
   excludes each coordinate or only the whole tuple on multi-value items is not established.
3. Keep explicit mods; side-lock metamods concern explicits and do not supply an implicit lock.
   Special implicit-lock properties require independent treatment.

## Numbers, comparison and unknowns
S3 2279 dispatches to poec_simRerollImplicits(false), 2546-2553. Each integer range is drawn
inclusively from low through high; decimal ranges use hundredths. The function does not
exclude the old value, so it conflicts with S51 (Q24).
Synthetic single-value range 10..12, old 10: CoE gives 10/11/12 each 1/3. S51 excludes 10;
it does not independently give probabilities for the other two, so 1/2 each is not accepted
as a game fact without further evidence. A fixed 10..10 implicit has 0 rollable range (S51).
Current-game numerical Blessed outcomes remain unsupported until Q24 is resolved.

Source: S51 https://www.poewiki.net/index.php?title=Blessed_Orb&oldid=1681166, Mechanics;
S3 package.js:2279,2546-2553. Read 2026-09-20.
