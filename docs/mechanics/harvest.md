# Harvest reforges and add/remove crafts

Read 2026-09-20; updated 2026-09-21 from owner answers. Confidence: `documented` S42 current recipe descriptions and S19 official
3.27 change; `reimplemented-from-CoE` S3 algorithms. Current recipes are distinguished from
the frozen simulator's legacy options. This is a researched partial sheet, not an executable
claim that every modern generation step is known.

## Effects and preconditions
S42 lists rare-item reforges guaranteeing a selected modifier tag, and add-tagged/remove-another
crafts restricted to non-influenced items. These are distinct actions; modern 'augment' is not
an unconditional extra modifier. S42 also lists more/less likely reforges, resistance/damage
conversions and influence randomisation. Retain-prefix/suffix reforges, standalone tagged
annuls and old Harvest synthesis in S3 are not approved as current actions (S42 table, S39).

The current tag table includes Fire/Cold/Lightning/Physical/Life/Defence/Chaos/Attack/Caster/
Speed/Critical and additional Minion/Elemental/Attribute/Mana/Drop reforges using Rancour.
Minion/Elemental/Attribute/Mana availability in the endgame loadout is owner-confirmed
(OWNER_QUESTIONS row 3). Their example price is owner-provisional, equal to the chosen
Sacred-lifeforce add/remove placeholder. Drop is not enabled by that answer.
S3's modern-toggle augment rejects full items and requires a legal tagged addition plus a
removable old modifier (2707-2708,2342-2344). Remaining item flags are Q9.

## Observed CoE reforge steps
1. S3 2341 requests rare reroll (or magic for its special non-rare base path), with selected
   tag, side-lock protection and `igcrca=true`. That last flag is source behavior, not a modern rule.
2. Reroll 2428-2435 retains fractures and protected existing sides, clears the other explicits,
   and rebuilds metamod flags from the survivors.
3. Add one tagged mod first (2448-2451); group/capacity conflicts include retained mods.
   The `hrerollp` legacy path additionally biases later draws; it is not the ordinary current reforge.
4. Draw the ordinary target count, subtract retained/forced counts, fill remaining slots through
   shared weighted selection (2455-2458). See affix_generation.md for count assumptions and Q2.
5. S19 decisively establishes respect for modifier-type restrictions in 3.27. The frozen S3
   ignore flag is not used for the guaranteed draw. Owner row 2 authorizes S14's first-draw-only
   interpretation pending narrower evidence; print that assumption wherever relevant.

## Observed modern-toggle add/remove steps
1. Check non-influence, open space and tagged addition pool (2707-2708).
2. Copy the old item; add one tagged mod while respecting attack/caster blocks (2341-2342).
3. With `crsim_hnerf` enabled, remove one eligible old modifier, excluding the newly added mod
   by ID (2342-2343). Side locks apply; attack/caster restrictions do not protect removals.
4. If no removal is possible, restore the snapshot and fail (2343-2344). This atomic failed
   emulator action is different from a player's policy restart after a successful but bad craft.
5. With the toggle disabled the removal is omitted: that is a legacy simulator variant, not
   the S42 modern recipe. Influence augment exceptions in the code need version classification.

## Metamods, numbers and worked examples
S42 Mechanics independently states: add/remove ignores attack/caster blocks for removal,
respects them for addition, and respects prefix/suffix locks. S17/S19 supply reforge evidence;
Q6 retains uncertainty about current carrier retention and later draws after the 3.27 change.

- S42 Fire reforge costs 50 Wild lifeforce; Life reforge 75 Wild. Fire add/remove costs
  15000 Wild plus 1 Sacred. These are resource quantities read from that revision, not market prices.
- CoE modern add/remove on a legal 4-mod input has 5 after addition, then 4 after removal.
  The newly added mod has removal probability 0 in that local action (2342's exclusion).
- Synthetic eligible tagged pool A=1, B=3 gives intended addition probabilities 1/4 and 3/4.
  If exactly 2 unprotected old mods can be removed uniformly, a specified add-A/remove-X
  outcome has probability 1/8 under the CoE model. The pool/removal assumptions are stated
  fixture inputs, not claims about any particular game item (S3 shared samplers; Q2).
- A full 3-prefix/3-suffix ordinary item is rejected by S3 augment before the draw. A
  guaranteed tagged addition does not grant a seventh affix slot (2707).

## Accepted ordinary reforge model (2026-09-21)

Side protection is enabled now: S14/S17/S42 and owner row 1 establish that existing protected
affixes survive. The official change S19 specifically addresses type restrictions; it does
not introduce side protection or describe the order in which carrier flags disappear.
Keep the existing ordinary Q9 item boundary until each special-state family is implemented.

For a rare input, retain each existing affix on a protected side. Free slots may still receive
new affixes. Draw one available mod with the selected tag, checking original attack/caster
restrictions, occupied groups and side capacities. Then choose total 4/5/6 with weights 8/3/1,
subtract all retained affixes and the guaranteed mod, and fill the remainder from the ordinary
pool. The first-draw-only model applies no type restriction to subsequent draws. An explicitly
named `all_draws` sensitivity mode applies original type restrictions to every new mod; it
is an alternative hypothesis, not a second accepted game rule. Empty guaranteed pools reject
the action. If both sides are completely protected and no slot is available, reject it.

Weights/groups/ilvl come from PoB; unbiased draws follow D14. Every chosen group is excluded
from subsequent draws. Sampling uses an explicit RNG. Exact evaluation retains group state
until the terminal distribution, including a forced mod's group, even when that mod is junk
under the value table. This preserves BRIEF 3b's distribution/threshold contract.

### Hand examples for the reforge adapter
All weights below are synthetic inputs. Let A(prefix, life, weight1) and B(prefix, life,
weight3) share group L; X(prefix, attack, weight2) and Y(prefix, weight2) have distinct groups.
Keep three concrete suffixes with suffix lock. With count4, A/B final probabilities are
1/4 and 3/4; with count5, AX, AY, BX, BY are 1/8,1/8,3/8,3/8.
With counts4/5/6 at 8/3/1, P(A)=1/4, and total prefix counts1/2/3 are 2/3,1/4,1/12.
For a separate fixture, A(life,attack,weight1), B(life,weight3), X(attack,weight2),
Y(weight2) have four distinct prefix groups, with three retained suffixes including no-attack
and multimod and an original suffix lock prefix. Count5: forced A is excluded; forced B then
adds A/X/Y at 1/5,2/5,2/5 in first-only mode, or Y with probability1 in all-draws mode.

Real Royal Burgonet ilvl86 with three protected ordinary suffixes: eligible life prefix
weight13000 = ten IncreasedLife tiers x1000 plus three LocalBaseArmourAndLife tiers x1000.
The first-draw IncreasedLife9 probability is 1000/13000=1/13. Later draws may also hit Life9
after a hybrid forced mod; the FINAL chance must not be replaced by 1/13.
Source: PoB ModExplicit.lua keys IncreasedLife0..9 and LocalBaseArmourAndLife1..3,
accepted projection and ordinary resolver; checked 2026-09-21.

### Legal protected-half policy boundary
The prepared helmet must have the desired chaos/elemental suffixes, exactly three suffixes,
and space for the prefix lock. Reforge can leave three prefixes; a failed full-prefix result
cannot be locked again. A legal baseline policy restarts the essence preparation on such a
result. A later optimizer may compare an explicitly priced Annul recovery. Do not silently
model all failed outcomes as renewable protected attempts. If p is reforge success, b is
full-prefix failure, A is expected preparation cost, and c is lock+reforge cost, renewal gives
expected total A + (c + b*A)/p. With A=10,c=2,p=1/4,b=1/4 the result is28, not18.
These inputs are hand-chosen arithmetic examples, not game prices or probabilities.

## Comparison and implementation boundary
Source changes are material: legacy toggle, removed recipes, new Rancour options and changed
metamod interactions. Implement only a future bounded spec whose version, item flags,
group rules and draw assumptions are explicit. Q6 no longer blocks ordinary protected reforges;
its unresolved type-filter detail is the declared owner-authorized first-only assumption.
More/less-likely weighting and resistance/damage tier correspondence still need their own
verified tables (Q12). No probability for them is inferred from their names.

Sources: S42 https://www.poewiki.net/index.php?title=Harvest_crafting&oldid=1699145,
Mechanics/current recipe table; S19 official 3.27 notes; S3 package.js functions/lines above.
