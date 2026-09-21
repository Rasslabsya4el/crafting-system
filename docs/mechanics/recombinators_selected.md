# Selected-mod recombination in PoE 1

Reviewed2026-09-21. Confidence: `documented` for the PoE1 mode's existence and destructive
failure (S75); `player-report` for formula research (S67,S70,S78). Formula versions and
source games are retained below. Current PoE1 constants and exact odds are unresolved.

## Effect and boundary
Official GGG3.26 notes (S75) introduce selection of modifiers from both inputs, display a
success chance and allow item destruction on failure. The older random mode remains.
Thus 'PoE2 recombinator' is a community nickname for a mode also present in PoE1.
S41 describes at least one selected modifier from each input. A successful result and a
destroyed-input/no-item result are different outcomes in BRIEF3b's distribution contract.
Both input costs are paid on failure; gold/dust costs need a separate sourced price model.

## What applies from which game
S70 is explicitly a **PoE2 patch0.2.0** guide. Its two-selected-mod examples add two
directional contributions, each capped at50%. A contribution depends on the selected
donor modifier's cumulative tier-or-better weight on the candidate recipient base,
the recipient's same-side total weight and a base constant. Examples16.6%=8.3%+8.3%,
8.2%=5.48%+2.72%,55.48%=5.48%+50% describe that historical model. They do not supply
the formula for three or more selected mods. A prose weight example swaps24.9/46.5;
do not copy that inconsistency into executable input.

S67 reports that the selected mode in PoE1 uses the same formula and links spreadsheets.
This is a player claim, not GGG confirmation of identical versioned weights/constants.
Its approximate50.5-51% isolation tip applies to the author's setup; it is not a universal
chance for an arbitrary selected pair. NNN/exclusive incompatibility can invalidate a
directional contribution, so the displayed chance cannot be inferred from counts alone.

The first linked sheet (S78) now identifies itself as **poe2(0.4)recombinator**; the second
(S79) is titled **poe2 weights (OUTDATED0.2)**. This mutable-version drift prevents treating
either as frozen3.26 PoE1 data. S78 was downloaded once as an XLSX into ignored raw storage;
only S79's title/version warning was inspected, not its data.

## Multi-mod formula observed in S78
`R1Backend!I18` describes, for recipient R and donor D with selected counts n_R,n_D,

`u_R = C_R * n_D! / (n_R+n_D-1) * product(w_Dj_on_R / W_R_same_side(j))`.

Here w is cumulative eligible weight of the selected tier or better; W is total eligible
weight on that affix side; C_R is a base-specific constant. Counts are positive because
each input contributes at least one selected mod. Repeat with the inputs reversed.
CellsC14:E15 compute the constant, weight and count factors. Before validity checks the
directional contribution is approximately `min(1,u_R)/2`, but exact spreadsheet rounding
matters: G14 uses

`FLOOR(IF(AND(u>0,u<=0.0001),0.0001,MIN(1,FLOOR(u,0.0001))/2),0.00001)`.

I14/I15 multiply directional contributions by H14/H15 validity gates; I16 floors their
sum to0.0001. Fracture/group validity expressions have not been fully mapped to PoE1.
Neither this rounding nor C_R is approved as a current PoE1 game fact.
The sheet's illustration uses `(4000/55200)*(4000/41000)` ~=0.7069%, boots constant10,
and two donor/three recipient selections: directional chance~=1.767%. A later prose
percentage1.0206% conflicts with that product, although the stated1.76% result agrees.
The reverse contribution is about2.93%, total4.69%. The saved sheet's current sample
ring constant21 is **PoE2 spreadsheet data**, not a PoE1 constant adopted by this project.

## Examples and remaining work
For an explicitly hypothetical displayed chance1/4, the distribution is successful item
mass1/4 and no item mass3/4. This arithmetic is a contract example, not a game prediction.
Q22 retains current PoE1 constants, eligible weight definitions, fracture/exclusive gates,
rounding, success-item details and costs. No current exact selected-mode calculator or
policy is enabled. The requested cross-game research is recorded without asking the
owner to fund experiments.
