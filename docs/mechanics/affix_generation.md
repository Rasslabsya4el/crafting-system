# Affix generation and reroll counts

Status: reviewed CoE behavior; independent game confirmation incomplete. Read 2026-09-20.
Confidence: `reimplemented-from-CoE`; PoB example fields are `datamined`.
Sources: S3 `poec_simRerollItem`, `poec_simRollAffix`, `poec_simGetBlockData`,
`poec_simBuildMods`, `poec_rand` (line 992), `numOfAffixes` (line 993); S10.

## Effect and preconditions
The reroll routine preserves the permitted existing mods, inserts any forced mods, chooses a
target explicit count, and fills remaining slots by weighted draws. This sheet covers the ordinary
PoE 1 path; the base's caps and eligible pool must already have been resolved. It is not a claim
that every item uses three prefixes and three suffixes.

## Exact observed steps
1. `poec_simRerollItem` updates rarity and captures the corresponding caps.
2. Unless `remfrac` is set, it preserves fractures, the requested `keepside`, and side-locked
   affixes when `metaprot` is true. It reconstructs metamod flags from retained mods.
3. It inserts supplied forced mods, veiled placeholders, Awakener selections or a forced tagged
   roll when their respective parameters apply. These consume the target count.
4. Without an explicit count or graveyard override, it uses
   `numOfAffixes[(prefix_cap + suffix_cap)/2]` and a random real value in [0,1).
5. It asks `poec_simRollAffix` for target count minus already retained/forced count. That function
   combines currently open prefix/suffix pools; it does not first flip a fair prefix/suffix coin.
6. Between draws it removes conflicting groups and closed sides and recomputes total weight.
   `poec_simGetBlockData` also reads additional mod groups and tag blocks. A full pool resolver
   audit remains pending; do not reduce all exclusions to the displayed text of a modifier.

## Numbers and their source
All rows below are S3 `numOfAffixes`, not datamined probabilities. Probabilities are interval
widths; source intervals share endpoints and the loop can overwrite an earlier match at equality.

| cap-sum / 2 | target count -> probability |
|---|---|
| 3 | 4 -> 2/3; 5 -> 1/4; 6 -> 1/12 (decimal intervals in source) |
| 2.5 | 4 -> 2/3; 5 -> 1/3 |
| 2 | 3 -> 0.65; 4 -> 0.35 |
| 1.5 | 3 -> 1 |
| 1 | 1 -> 1/2; 2 -> 1/2 |

PoB S10 `Strength1`: level 1, 13 ordered weight keys, 13 weights summing to 8333, default
weight 0. This is an input-data example, **not** the total weight of any particular item's pool.

## Conditions, metamods and exceptions
`poec_getMagicOverrideMaxAff` and named special bases override ordinary limits;
Simplex/Focused handling also overrides target count. Graveyard and forced-count paths bypass
the table. Retained fractured/locked mods consume slots. Pool exhaustion can prevent filling
the requested number; the count table alone does not guarantee the final count.
`meta && !igcrca` controls attack/caster tag filtering in `poec_simRollAffix`.

## Reference discrepancy
Q2: `poec_rand(1,total,true)` excludes `total`, but weighted intervals include it.
For two entries of weight 1 each, the call returns only 1 and the second entry is unreachable.
The routine's recorded chance `weight/total` therefore differs from its literal sampling.
Our future engine must use unbiased draws; no source code has been transplanted.

## Worked examples for future tests
- Ordinary six-slot reroll without protected mods: expected target count is
  `4*(2/3)+5*(1/4)+6*(1/12)=53/12`. S3 table, arithmetic derivation.
- Ordinary two-slot magic reroll: expected target count `1*(1/2)+2*(1/2)=3/2`.
- Synthetic independent eligible entries A/B/C with weights 1/1/2, no group conflicts,
  two draws without replacement: intended `P(A appears)=1-(1/4*2/3+2/4*1/2)=7/12`.
  This is a hand-computed acceptance example, not a game pool and not a measurement from CoE.

## Open questions
Q2 (sampling discrepancy), Q4 (count corroboration), Q8 (PoB revision).
Action implementation and rule tests have not started; these examples become worker specs first.
