# Fossils and resonators

Status: ordinary weight-transform model including the two sourced hybrid-tag fossils accepted under D21; special outcomes
remain partial. Read 2026-09-20, rechecked2026-09-21. Confidence: `reimplemented-from-CoE`; the metamod
exception is additionally `documented` by S17. Sources: S3 `package.js` line 5 (`fossil`),
`poec_workoutFOMTypes` lines 1500-1508, `poec_getModdedWeight` lines 1559-1570,
`poec_simApplyCraftGO` lines 2328-2338; S17 Wiki Metamod.

Ordinary adapter accepted0de86dd; bounded Alchemy-then-Chaotic policy accepted2c069fc.
The policy compares every nonempty subset of up to four caller-available fossils, prices
the whole resonator recipe, and retains both raw and conditional terminal distributions.
This availability limit and the example prices are prototype inputs (D22), not game facts.
Policy derivation and hand cases: docs/design/family-policies.md; measured helmet/bow
comparisons: docs/research/goal2-results.md.

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
   (`poec_cFosMode`, line 435), and can be changed. D21 selects this default for the prototype,
   with multiplicative sensitivity retained; Q13 preserves its evidence limits.
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
  gives1200. D21 selects700 as the CoE-derived default, not a datamined game assertion.
- Base weight 100 with no matched factor and no Opulent untagged override remains 100.

Group conflicts, tier availability and count distributions still come from the pool/reroll
rules. A weight multiplier is not a final success probability. Named multiplier tables must
be sourced per fossil before code can price a fossil policy; no CoE compiled table is copied.

## Open questions

Version condition: S39 official 3.29 Item Changes replaces Fractured Fossil's effect with
fracturing a random modifier and excludes fractured/influenced inputs. The frozen CoE special
path must not be treated as a current 3.29 rule. See patch_3_29.md and Q19; ordinary weight
examples above do not implement this special fossil.

Q9 special-item eligibility; Q13 evidence conflicts and special fossil factors; Q2 literal
RNG issue for special forced-mod draws. Price inputs and rare-input availability belong to the
loadout, not game constants in this sheet. Ordinary adapter accepted0de86dd2026-09-21:
18 supported fossils with exact rational transforms and seeded independent sampling;
special recipes remain unsupported. Planner combination policy is a separate next step.


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

S56's interpretation applies a fossil once even if multiple tags match: a base-weight100
Minion/Aura mod becomes1000 under Bound. Cached CoE instead adds matching positive tag
factors and gives2000 in its default mode. This is Q13.01, not a silent agreement.
S56 calls these numbers community interpretation; D21 selects the observed CoE default
over this player interpretation, with both results preserved for review.
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

S56 corroborates the nature of the Q13 dispute; D21 chooses the implementation default.
All special recipes
still require current patch/eligibility evidence, especially the S39 Fractured Fossil replacement.


## Ordinary-mode resonator gate clarified
S58 https://www.poewiki.net/index.php?title=Resonator&oldid=1675208, Mechanics/List/Ruthless,
read 2026-09-20 (`documented`): ordinary-mode obtainable Chaotic resonators reforge rare
items. Alchemical resonators target normal items and are now obtained in Ruthless; existing
legacy ones still work. Thus frozen CoE's broad non-magic gate is not sufficient for the confirmed
ordinary 3.29 loadout. Normal-item fossil starts require an explicitly available legacy input,
not an assumed current Alchemical resonator. Record the source-local difference as Q30.

The resonator must be full; no duplicate fossil type is allowed within it. A blocked modifier
tag overrides a more-weight effect, and all socketed fossils contribute their use restrictions.
Example: a Fire-tag candidate remains weight 0 when Frigid blocks Fire, even if another fossil
boosts Fire (S58 precedence, S56 tag interpretation). A 2-slot resonator with only 1 fossil is
not usable. Completed sockets lock in the fossils; this preparation can consume rare inputs
before the random item outcome, so a later policy must count the complete resonator recipe.

## Owner follow-up: type, overlap and adopted numbers (2026-09-21)
S58 recheck and S72 tooltips resolve owner row6: Primitive/Potent/Powerful/Prime **Chaotic**
resonators all target rare items, with1/2/3/4 sockets respectively. **Alchemical** targets
normal items; current acquisition is Ruthless, or an explicitly allowed legacy input.
Rarity depends on type, not socket count. No owner test is needed.

Two different fossils can affect the same MOD through different tags. PoB
`ModExplicit.lua:447`, `LocalAddedFireDamageTwoHand10`, has bow weight126 and tags including
fire and attack. S4 fossils13(Scorched) and14(Serrated) respectively encode fire1000 and
attack1000; neither of their cold/caster restrictions matches this mod. Default S3 mode
adds10+10: effective weight2520. Multiplicative sensitivity gives12600. These are weights,
not hit probabilities. Duplicate fossil types in one resonator remain forbidden.

Read S4 `fossils.seq[].mod_data` with S3's percentage decoding; the ordinary nonhybrid
table below is an independently described set of facts, not a copied compiled table.

| CoE fossil ID/name | Positive tag factor | Reduced/blocked tag |
|---|---|---|
| 1 Aberrant | chaos10 | lightning0 |
| 2 Aetheric | caster10 | attack0.15 |
| 3 Bound | minion10,aura10,curse10 | none |
| 22 Deft | critical10 | attribute0 |
| 5 Dense | defences10 | life0 |
| 6 Faceted | gem10 | none |
| 7 Frigid | cold10 | fire0 |
| 21 Fundamental | attribute10 | critical0 |
| 8 Jagged | physical10 | chaos0 |
| 9 Lucent | mana10 | speed0 |
| 10 Metallic | lightning10 | physical0 |
| 23 Opulent | drop10 | tagless0 (special matching rule) |
| 12 Pristine | life10 | defences0 |
| 13 Scorched | fire10 | cold0 |
| 14 Serrated | attack10 | caster0.15 |
| 15 Shuddering | speed10 | mana0 |

S4 Prismatic11 boosts **elemental only** by6, unlike S56's broader OR description; it
blocks physical+ailment and chaos+ailment conjunctions. Corroded4 boosts those conjunctions
by10 and blocks elemental/fire/cold/lightning. The literal hybrid branch's absent negative
entry defaults to1 through JavaScript's null/undefined check; the offline trace below
confirms this for these source records. These two hybrid recipes are also accepted.
Glyphic20,Hollow18,Sanctified19 have separate rules, not an empty ordinary transform.
Ordinary combinations can now be implemented with explicit CoE confidence and
real pool tests; unresolved specials do not block them.

S3 `poec_getModdedWeight`,1559-1570, returns the multiplication result without integer
rounding. Example126*0.15=18.9, not18 or19. Our integer DP can preserve this rational
probability law by scaling ALL transformed pool weights by one common denominator and
then reducing their common gcd. This is mathematical representation, not game rounding.

## Offline hybrid trace (2026-09-21)
The lead executed unchanged S3 `poec_workoutFOMTypes`1500-1508 and
`poec_getModdedWeight`1559-1570 against S4 in a local Node VM, with base weight100.
Only JSON parsing/iteration helpers were supplied; no source arithmetic was rewritten.

| Fossils | Mod tags | Effective weight |
|---|---|---:|
| Corroded4 | physical,ailment | 1000 |
| Corroded4 | physical | 100 |
| Prismatic11,Jagged8 | physical,ailment | 0 |
| Corroded4,Jagged8 | physical,ailment | 1000 |
| Corroded4,Serrated14 | physical,ailment,attack | 2000 |
| Prismatic11,Scorched13 | elemental,fire | 1600 |

A matching conjunction bypasses positive AND negative factors of its constituent single
tags; single-tag blocks still win. Thus Corroded+Jagged is1000, not2000, for physical
ailment: the hybrid's physical component suppresses the extra single physical boost.
An unrelated attack boost still adds. This narrows Q13 to historical confidence/conflicts
and genuinely special recipes; lack of datamined corroboration does not block CoE-derived use.
