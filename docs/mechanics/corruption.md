# Vaal Orb and Locus of Corruption

Status: reviewed, partial; ordinary equipment category distribution only. Read 2026-09-20.
Confidence: `documented` S37/S38 and official 3.29 notes S39; `reimplemented-from-CoE` S3.
Maps, gems, jewels and special unique transformations need separate tables, not this rule.

## Effect and preconditions
Corruption changes an eligible item and marks the surviving result corrupted. Locus can also
destroy it. S38 explicitly excludes already corrupted items and lists weapons, armour,
jewellery, quivers and jewels as accepted classes. S37 describes exceptions allowing some
later bench/tainted operations; corrupted is not a universal ban on every later action.
Other mirrored/fractured/special-state checks remain Q9/Q12.

## Category distribution and steps
For ordinary equipment, S37 gives four equally likely Vaal categories: a corruption implicit,
a socket-colour result, a rare reroll with six affixes, or no change except corrupted status.
S38 gives four equally likely Locus categories: two corruption implicits, a socket-colour
result, influenced rare reroll, or destruction. Each category therefore has probability 1/4;
this is not the probability of a particular implicit or affix combination.

1. Check eligibility and select the action's category.
2. Resolve that category using its own pool and state transition. S37 replaces one existing
   implicit randomly if several exist. S38 replaces two randomly if at least three exist.
3. Preserve destroyed as an explicit terminal outcome; mark surviving outcomes corrupted.
4. A socket category can leave a socketless item otherwise unchanged (S37/S38). Keep its
   probability mass, then combine identical resulting states where appropriate (BRIEF 3b).

Since 3.29, Vaal's socket result recolours one random white socket to non-white; Locus recolours
all white sockets to non-white (S39, Gem Socket Changes). The frozen CoE tables still say white
sockets. This is a version discrepancy, Q18; do not implement the old label as a 3.29 rule.
Exact colour probabilities and inputs without white sockets have not been sourced here.

## Metamods, source comparison and limitations
S37/S38 say rare rerolls respect metamods, but their supporting references are player videos/
reports, not a datamined transition. Preserve that evidence limit. Full lock/type interaction
and the influenced-rare pool are not yet independently audited.
S3 `crsim_vaaltbl` / `crsim_locustbl` line 1777 and `poec_simCorrupt` 2805-2818 also select
four categories with a zero-based uniform index. The socket branch mostly returns a label;
it is not a full socket-state simulator. The rare branch forces six affixes, with special
map handling; its altar influence assignment is conditional on `useisinf==1`.
`poec_simRollImplicits` 2819 onward uses weights and excludes groups selected on the preceding
implicit. Full pool, exclusions and weighted RNG need further audit (Q2/Q12/Q16).
These observations do not validate special-item behavior or the complete CoE transition.

## Worked examples
A legal ordinary socketless item, excluding special transformations, has Vaal category mass
1/4 each. Combining the socket and no-change categories yields 1/2 for unchanged properties
plus the corrupted flag; implicit and rare-reroll categories retain 1/4 each (S37).
For Locus, destruction risk is 1/4 and survival probability 3/4 (S38). A policy must report
this irreversible risk separately from expected utility/cost. If a hypothetical desired
implicit-pair event has conditional probability 1/10 within the implicit category, its total
probability is 1/40. The 1/10 is invented arithmetic input, not a game fact.

## Open questions
Q3 target ruleset; Q9 legality; Q12 implicit pools, special cases and detailed transitions;
Q18 pre/post-3.29 socket difference. No corruption engine exists yet.
