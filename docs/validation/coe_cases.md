# Twelve real-pool offline Craft of Exile comparisons

Lead acceptance2026-09-21, merge3712602 (worker428b304, correction1b55a94).
All12 cases executed by the lead against frozen independent sources. Maximum absolute
relative difference2.0873505733%; zero cases exceed GOAL2's5% investigation threshold.
Five agree to floating-point precision; seven differ. This is a bounded cross-check,
not proof that every CoE exact-labelled branch or our provisional model is correct.

## Inputs and reproduction

Run from crafting: `python -m tools.coe_validation`. It writes
`out/coe-validation/comparison.json` and `comparison.tsv`. Accepted run:Node v24.11.1,
0.168minute. No network requests, installation, site automation or third-party code
copied into tracked files. The harness extracts complete original declarations at runtime,
executes unchanged arithmetic in bounded Node VM contexts, and stubs UI diagnostics only.
Source-sensitive tests skip clearly if caches are absent; missing sources make the CLI fail.

S3 `sources/raw/coe/package.js` SHA256:
`faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639`.
S4 `sources/raw/coe/poec_data.json` SHA256:
`2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a`.
Sources were cached2026-09-20 and read/executed2026-09-21; see SOURCES.md.

Our pools come from the accepted PoB projection(S24), first matching base-tag weights,
ordinary groups and D14 rules. CoE pools independently use its basemods, ordinary modifier
group1, source-native exclusion groups, positive tiers and level gate. CoE base IDs are
Royal Burgonet52, Simple Robe47, Iron Ring1, Paua Amulet2, Iron Greaves39. Every item is
ilvl86, ordinary, Q9 flags false; no implicit/quality/magnitude condition is scored.
The script checks25 target/existing/forced correspondences by side, level and values;
missing/ambiguous mappings0. Modified level/range fixtures fail explicitly.

Rerolls start with zero explicits and legal rarity. Targets below are AND, exact listed
tiers. Essence C02 forces ChaosResist6 and tests Life9+Fire8. Full suffixes in C03 forbid
further suffixes. Other existing affixes are listed explicitly; their exclusion groups are
removed independently in each source. Relative percent=100*(ours-CoE)/CoE.

## Results

| ID | Base | Action / starting state | Target PoB IDs | Our probability | CoE probability | Relative % |
|---|---|---|---|---:|---:|---:|
| C01 | Royal Burgonet | Chaos / rare | IncreasedLife9, ChaosResist6 | .0003673650969794048 | .0003668380441541475 | +.1436745 |
| C02 | Royal Burgonet | Deafening Envy / rare | IncreasedLife9, FireResist8; forced ChaosResist6 | .0008758259906074872 | .0008579182295252153 | +2.0873506 |
| C03 | Royal Burgonet | Exalted / rare; ChaosResist6, FireResist8, ColdResist8 | IncreasedLife9 | .02546148949713558 | .02546148949713558 | 0 |
| C04 | Simple Robe | Alchemy / normal | LocalIncreasedEnergyShield11 | .03550816560805275 | .03557063531876736 | -.1756216 |
| C05 | Simple Robe | Alteration / magic | LocalIncreasedEnergyShield11, LightningResist8 | .0001408371359360036 | .0001408371359360036 | 0 |
| C06 | Iron Ring | Chaos / rare | ColdResist8, ChaosResist6 | .00010876109551498082 | .0001101634950524083 | -1.2730166 |
| C07 | Iron Ring | Alchemy / normal | ColdResist8 | .024246677570894055 | .02445361336822683 | -.8462381 |
| C08 | Iron Ring | Regal / magic; IncreasedLife7, FireResist8 | ChaosResist6 | .0016909029421711193 | .0016909029421711193 | 0 |
| C09 | Paua Amulet | Chaos / rare | IncreasedLife8, ChaosResist6 | .00010370039891240398 | .0001042588117746307 | -.5356026 |
| C10 | Paua Amulet | Alteration / magic | ColdResist8 | .006330103412534295 | .006330103412534295 | 0 |
| C11 | Iron Greaves | Alchemy / normal | MovementVelocity6 | .05122857786828192 | .05100662496761783 | +.4351452 |
| C12 | Iron Greaves | Regal / magic; MovementVelocity6, FireResist8 | ChaosResist6 | .0030637254901960784 | .0030637254901960784 | 0 |

Envy ID is `Metadata/Items/Currency/CurrencyEssenceEnvy3`; CoE essence1231 forces mod2638,
level81, suffix ChaosResistance,31..35. Its ordinary corresponding modifier is661.
Full JSON preserves all25 checked ranges/levels and each source's groups. Target aliases:
life1775, chaos661, fire1628, cold684, lightning1966, flat energy shield2007, movement2135.
The alias alone is not a tier:1775 here maps to helmet Life9(level64,130..144) or amulet
Life8(level54,115..129). The recorded tier check is essential.

| Cases | Eligible prefix weight, both sources | Eligible suffix weight, both sources | Combined one-draw denominator |
|---|---:|---:|---:|
| C01 | 39275 | 78400 | — |
| C02 | 39275 | 76900 | — |
| C03 | 39275 | 0 (full suffix side) | 39275 |
| C04/C05 | 61000 | 58200 | — |
| C06/C07 | 60250 | 103600 | — |
| C08 | 52250 | 95600 | 147850 |
| C09/C10 | 88600 | 125250 | — |
| C11 | 39000 | 56600 | — |
| C12 | 33000 | 48600 | 81600 |

## What the comparison establishes and leaves open

C01/C02/C04-C07/C09-C11 call original `poec_computeFinalProbsV2`(S3:1021-1198),
with `poec_cAlgoMode="x"`, and its `poec_computePermutationsV2`(1199-1249). Cached
count constants, permutation arrays and helper declarations are loaded directly. Frozen
function offsets are asserted. We do not derive probabilities from rounded attempt labels.
C03/C08/C12 use the unchanged permutation function for one eligible draw; they are
explicitly direct kernel invocations, not a reproduction of the complete UI event path.

Every initial side-pool total agrees, but that does not prove exclusion-family equivalence
or identical later conditional denominators. CoE's final calculation factorizes side
requirement probabilities and count composition; our DP retains joint group state through
all draws. Its count-composition calculation also uses selected group-weight summaries.
See S3:1128-1140,1187-1195 and research/coe-calculator-and-policies.md. These structural
differences identify where further diagnostics belong; this pack does not claim a unique
causal attribution for each small discrepancy. No probability was altered to force agreement.

All three conditional single additions agree, as do the two magic cases. Hand fixtures
through the original JS routine reproduce P(A)=7/12, P(A,C)=5/12 for two distinct-group
draws with weights1/1/2, and P(A)=1/4 for one draw. These do not exhaust overlapping
exclusion-group cases. Q14 remains open for that broader proof; Q16/Q17 remain explicit
pool-semantic limitations. There is no unexplained >5% case in this required pack.

Lead acceptance: clean committed tree; entire initial/correction diff reviewed against the
spec; `python -m pytest -q tests/test_coe_validation.py` gave6 passed in0.009minute;
all12 real cases rerun separately,25 correspondences checked. One correction round fixed
missing correspondence validation, C02 input rarity, side totals and cached permutation
constant loading. Sources remain `reimplemented-from-CoE`; PoB numbers retain their
datamined provenance and supplied-version qualification.
