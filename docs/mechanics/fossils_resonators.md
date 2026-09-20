# Fossils and resonators

Status: partial, ordinary weight-transform path reviewed; named fossil data and special outcomes
still need corroboration. Read 2026-09-20. Confidence: `reimplemented-from-CoE`; the metamod
exception is additionally `documented` by S17. Sources: S3 `package.js` line 5 (`fossil`),
`poec_workoutFOMTypes` lines 1500-1508, `poec_getModdedWeight` lines 1559-1570,
`poec_simApplyCraftGO` lines 2328-2338; S17 Wiki Metamod.

## Effect and preconditions

The observed ordinary path rerolls an item as rare with fossil-adjusted weights. The method
metadata requires base `is_fossil`, excludes magic rarity and outcome-affecting metamods.
S17's Essence/Fossil example exempts multimod alone. Full corrupted/mirrored/fractured legality
remains Q9. CoE offers a resonator-size cap from 1 through 4 (`poec_toggleFOResoLimit`, line 1498)
and tracks one resonator of the selected fossil count (`poec_simUpdateSpending`, line 2627).

## Observed weight-transform steps

1. Read each selected fossil's `mod_data` by tag. Zero marks a blocked tag; otherwise divide the
   stored percentage by 100 to get a factor (S3 line 1504). This describes CoE's encoding only.
2. Aggregate positive and negative factors separately. Positive factors add in mode `a` and
   multiply in the alternate mode; negative factors multiply. Mode `a` is the cached default
   (`poec_cFosMode`, line 435), and can be changed. Current-game stacking is still Q13.
3. Hybrid tag entries require all listed tags and bypass the corresponding single-tag factors
   in `poec_getModdedWeight`; a matched block makes effective weight zero.
4. With no block, missing positive/negative factors default to 1 and effective weight is base
   weight times positive factor times negative factor. Opulent has a separate untagged-mod zero
   path. Do not flatten these conditions to one unconditional product per tag.
5. The dispatcher calls a rare reroll with fossil handling, preserving the reroll routine's
   other conditions. Special-fossil cases (including forced essence modifiers and quality)
   branch separately; they are not accepted by the ordinary-weight rule.

## Numeric examples and implementation limits

Synthetic inputs, chosen for arithmetic, not claims about any named fossil:

- Base weight 100, one applicable encoded value 300, negative value 50: factors 3 and 0.5,
  effective weight 150. Matching blocked tag: 0 regardless of those factors.
- Two applicable positive factors 3 and 4: mode `a` gives 700 from base 100; multiplicative mode
  gives 1200. This proves the mode matters; it does not select the game's current rule.
- Base weight 100 with no matched factor and no Opulent untagged override remains 100.

Group conflicts, tier availability and count distributions still come from the pool/reroll
rules. A weight multiplier is not a final success probability. Named multiplier tables must
be sourced per fossil before code can price a fossil policy; no CoE compiled table is copied.

## Open questions

Version condition: S39 official 3.29 Item Changes replaces Fractured Fossil's effect with
fracturing a random modifier and excludes fractured/influenced inputs. The frozen CoE special
path must not be treated as a current 3.29 rule. See patch_3_29.md and Q19; ordinary weight
examples above do not implement this special fossil.

Q3 target patch; Q9 item eligibility; Q13 stacking mode and named fossil multipliers; Q2 literal
RNG issue for special forced-mod draws. Price inputs and rare-input availability belong to the
loadout, not game constants in this sheet. No fossil action has been implemented.
