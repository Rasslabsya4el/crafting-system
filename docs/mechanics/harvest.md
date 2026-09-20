# Harvest reforges and add/remove crafts

Read 2026-09-20. Confidence: `documented` S42 current recipe descriptions and S19 official
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
Availability within the target loadout is Q26; their existence does not establish equal weights.
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
5. S19 says modern reforges respect modifier-type restrictions. Frozen S3 passes ignore-type-
   restriction to both forced and later draws. Do not silently use S3 for post-3.27 metamod cases.

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

## Comparison and implementation boundary
Source changes are material: legacy toggle, removed recipes, new Rancour options and changed
metamod interactions. Implement only a future bounded spec whose version, item flags,
group rules and draw assumptions are explicit; otherwise raise unsourced Q6/Q9/Q26.
More/less-likely weighting and resistance/damage tier correspondence still need their own
verified tables (Q12). No probability for them is inferred from their names.

Sources: S42 https://www.poewiki.net/index.php?title=Harvest_crafting&oldid=1699145,
Mechanics/current recipe table; S19 official 3.27 notes; S3 package.js functions/lines above.
