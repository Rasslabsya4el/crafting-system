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


## Named multiplier evidence and special branches
S56 https://www.poewiki.net/index.php?title=Fossil&oldid=1702302, Mechanics, read 2026-09-20,
explicitly calls its multiplier table a community interpretation of DelveCraftingModifiers.dat
and says additive versus multiplicative stacking is disputed. Confidence for those numerical
multipliers is `player-report` (Wiki-reported community interpretation), not independently
`datamined`. The following entries can support source-labelled experiments, not exact game odds:

| fossil | more | fewer / blocked |
|---|---|---|
| Serrated | Attack x10 | Caster x0.15 |
| Aetheric | Caster x10 | Attack x0.15 |
| Scorched / Frigid | Fire / Cold x10 | Cold / Fire blocked respectively |
| Metallic / Jagged / Aberrant | Lightning / Physical / Chaos x10 | Physical / Chaos / Lightning blocked respectively |
| Pristine / Dense | Life / Defence x10 | Defence / Life blocked respectively |
| Lucent / Shuddering | Mana / Speed x10 | Speed / Mana blocked respectively |
| Deft / Fundamental | Critical / Attribute x10 | Attribute / Critical blocked respectively |
| Bound | Minion OR Aura OR Curse x10 | no blocker listed |
| Faceted | Gem x10 | no blocker listed |
| Opulent | Drop x10 | tagless blocked |
| Prismatic | Elemental OR Fire OR Cold OR Lightning x6 | (Physical AND Ailment) OR (Chaos AND Ailment) blocked |
| Corroded | (Physical AND Ailment) OR (Chaos AND Ailment) x10 | Elemental OR Fire OR Cold OR Lightning blocked |

A fossil affects a mod once even if multiple of its tags match (S56). Thus a base-weight-100
mod matching both Minion and Aura becomes 1000 under the single Bound interpretation, not
10000. Multiple distinct fossils remain the disputed Q13, not repeated independent tag products.
S56 reports Sanctified factor 1 + .01*(required mod level - 40); a level-80 fixture gives 1.4.
This is a reported formula, not a new mod-level gate. Tangled uses a random boosted tag x30
and a different blocked tag; overlapping-other-fossil restrictions are marked unconfirmed.

S3 special branches read independently:
- Glyphic (2328-2334): build base-compatible corrupted-essence candidates, exclude fractured
  group conflicts, assign each base weight 1000 and transform via fossil weights, then choose
  one forced essence modifier before rare reroll. Empty pool errors; weighted RNG has Q2.
- Perfect (2336): integer quality from 15 through 30 inclusive: 16 possible values, 1/16 each
  in this source algorithm. This is not proof of current availability or its full game distribution.
- Gilded (2336-2337): append its vendor-value implicit only if absent; no duplicate append.
- Hollow (2452): force an Abyss-socket suffix before filling remaining affixes, occupying 1 suffix.
- S56 says weights do not affect Bloodstained corrupted-implicit outcomes or Fractured Fossil
  fracture selection. Their exact transition distributions remain Q12, not ordinary weight draws.

S56 corroborates the nature of the Q13 dispute; it does not resolve it. All special recipes
still require current patch/eligibility evidence, especially the S39 Fractured Fossil replacement.
