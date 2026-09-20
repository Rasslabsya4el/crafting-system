# Recombinators

Status: reviewed, partial; contemporary transition probabilities not approved. Read 2026-09-20.
Confidence: `documented` for S41 Wiki mode descriptions; `player-report` for its estimated
unpredictable count table (linked player guide); `reimplemented-from-CoE` for S3 algorithm.
S41 explicitly warns its predictable-mode documentation needs updating. Never collapse the
currency item, predictable device and unpredictable device into one action without Q3.

## Effect and preconditions
S41 describes two magic/rare equipment inputs of the same class. Both are consumed and the
output is a new item, so imprints cannot restore either input. Costs are gold and dust, depending
on inputs; no complete price formula is sourced. Predictable mode selects at least one affix
from each input and exposes a success chance, with no output on failure. Unpredictable mode
always yields an item, with random affix retention. Special-item legality remains Q9/Q12.

## Documented outline, with evidence limits
For unpredictable mode, S41 chooses a base from either input with equal odds, derives item
level, pools prefixes/suffixes, draws their counts, selects which side to fill first with equal
odds, then selects mods with exclusions. The selection-weight formula is explicitly unknown.
Exclusive mods couple the two sides: selecting one excludes others from BOTH pools. Therefore
separate count draws do not imply independent final prefix/suffix outcomes. Base-specific and
fractured-mod eligibility can change the candidate pools; their full matrix is not approved.

S41 item-level formula: min(floor((A+B)/2 + 2), max(A,B)). Examples on the page:
100/1 -> 52; 84/84 -> 84; 84/80 -> 84; 84/79 -> 83.

Estimated unpredictable count table, not datamined exact odds:

| pooled mods on a side | 0 retained | 1 | 2 | 3 |
|---:|---:|---:|---:|---:|
| 1 | 41% | 59% | 0 | 0 |
| 2 | 0 | 66.7% | 33.3% | 0 |
| 3 | 0 | 40% | 50% | 10% |
| 4 | 0 | 10% | 60% | 30% |
| 5 | 0 | 0 | 43% | 57% |
| 6 | 0 | 0 | 30% | 70% |

S41's later worked example instead says 72% for six pooled mods. This internal contradiction
is Q21; do not choose 70 or 72 silently. Constraints may leave fewer mods than a drawn count.

## Frozen CoE algorithm and differences
S3 `poec_simRecombinate` 1888-1925 checks base compatibility, chooses a base with a fair coin,
then sets ilvl to floor((A+B)/2) at 1895, WITHOUT the Wiki's +2. It drops influenced candidates
incompatible with chosen influence, pools both inputs, draws side counts, fills prefixes first
and suffixes second using uniform candidate-index draws, skipping group conflicts.
It rerolls selected values and has a further optional added-mod branch at 1913-1918; that
branch's legacy availability is not established. No predictable success/no-item mode was found
in this function. Do not import this old algorithm as the current device.

S3 `simRecombDistrib` 1886 stores the following weights (sum 10000 per row):
1 pooled -> {0:3334,1:6666}; 2 -> {1:6666,2:3334}; 3 -> {1:3000,2:5000,3:2000};
4 -> {1:1000,2:5500,3:3500}; 5 -> {2:5000,3:5000}; 6 -> {2:3000,3:7000}.
These differ from S41's estimates at pool sizes 1, 3, 4 and 5 (plus rounding at 2).
The table also has 0/7/8 pool entries; special capacities at 1901 need separate ruleset review.
Q22 records ilvl, side ordering, weighting and count differences together.

## Worked arithmetic and policy implications
For inputs 84/80, S41 gives min(84,84)=84; S3's formula gives 82. This is a reproducible
source disagreement, not a probability test. For 84/84 the formulas both give 84.
If a hypothetical predictable attempt succeeds with probability 1/4, the outcome distribution
has item mass 1/4 and destroyed-input/no-item mass 3/4. That probability is invented solely
for the BRIEF 3b risk example; no in-game predictable odds have been sourced.

## Open questions
Q3 version/mode; Q9 item flags; Q12 precise pools and exclusions; Q21 internal Wiki estimate;
Q22 Wiki/CoE algorithm differences. No recombination calculator or policy is implemented.
