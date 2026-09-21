# Classic recombinators

Reviewed 2026-09-21. Confidence: `documented` for official GGG mode availability (S75)
and Wiki item-level rule (S41); `player-report` for S66-S69 experiments and diagrams;
`reimplemented-from-CoE` for the frozen simulator. Exact current odds remain unsupported.
The selected-mod mode has its own sheet, [recombinators_selected.md](recombinators_selected.md).

## Sources and scope
The source chain matching the owner's description is Butsicles' 3.25 guide (S66, NNN),
his 3.26 follow-up (S67), statistically-typed's Reddit analysis (S68), and its linked
Codeberg guide (S69). Text is cached; diagram descriptions are in
`sources/raw/research/recombinator-diagrams.md`. This is a strong match to the description,
not a claim that the owner has confirmed the exact URL. These are historical player
experiments, not datamined 3.29 probabilities. S66 reports roughly 500-800 experiments.

## Effect, inputs and steps
S41 describes two magic/rare equipment inputs of the same class, consumed to create a new
item. Imprints cannot restore either consumed input. Gold/dust costs depend on inputs;
no complete cost formula is approved. Official 3.26 notes (S75) retain the earlier random
mode without the selected mode's destruction-on-failure outcome. Special legality remains Q9.

The 3.25 model in S66 first chooses a base, then builds prefix/suffix pools, determines
counts and selects modifiers with group and exclusive-mod restrictions. NNN means
**non-native natural modifiers**: modifiers whose natural eligibility depends on the
selected base (for example influence or armour class), not 'nonexclusive' modifiers.
Nonfractured NNN can contribute to a pool's count while being unable to transfer to an
incompatible selected base; fractured candidates count only when their own base is selected.
An exclusive modifier selected on one side excludes exclusive modifiers on both sides.
Not every crafted modifier is exclusive. Individual selection weights remain unknown;
do not replace them with uniform draws merely because the count table is known.

S66's base choice is 50/50. S41's item level is
`min(floor((A+B)/2 + 2), max(A,B))`: 100/1 ->52, 84/80 ->84, 84/79 ->83.
These rules do not establish a complete current eligibility matrix.

## Historical counts and later changes
S66 gives these rounded percentages; preserve the literal measurements rather than
normalizing them into invented exact probabilities.

| Pooled mods on one side | Output0 | Output1 | Output2 | Output3 |
|---:|---:|---:|---:|---:|
| 1 | 41 | 59 | 0 | 0 |
| 2 | 0 | 67 | 33 | 0 |
| 3 | 0 | 39 | 52 | 10 |
| 4 | 0 | 11 | 59 | 31 |
| 5 | 0 | 0 | 43 | 57 |
| 6 | 0 | 0 | 28 | 72 |

Rows3/4 sum to101 because they are rounded empirical estimates. S41 separately lists
70% for pool6 but uses72% in an example (Q21). The S66 table explains the72 figure;
it does not prove that72 is the exact current probability.

S66's 50/50 first-side selection must not be carried forward unqualified. S67 reports
about70 3.26 tests: multiple exclusive modifiers count at most once per side; a side
containing only exclusive modifiers is unlikely to be processed first. One narrated
17-test example gives subcounts1+15=16, so it cannot yield a defensible exact estimate.
S67 says ordinary count behaviour seems similar but needs more tests. Official S75
confirms the3.26 reduction in output count for inputs with many mods unable to roll
naturally (including veil/essence examples); it does not publish an exact count formula.

## What the diagrams establish
S69 explains construction and recycling routes under its stated3.25-count/3.26-exclusive
assumptions. It excludes NNN, selected-mod recombination and gold/dust economics. Its
illustrative35% route joins2p2s with1p3s or3p1s; its49% intermediate-loss figure motivates
recycling. They are rounded derived guide estimates, not independent game constants.
The cached diagram descriptions name each image and explain its surrounding prose;
they do not claim a transcription of every graphical edge probability.

## Frozen CoE comparison
S3 `poec_simRecombinate`,1888-1925, chooses a base, uses `floor((A+B)/2)` at1895,
fills prefixes first, selects candidate indices uniformly with group exclusions, rerolls
values and has an optional added-mod branch1913-1918. Current availability of that branch
is unestablished. For84/80 it gives82, versus84 from S41.
S3 `simRecombDistrib`,1886, uses weights summing10000:
1->{0:3334,1:6666};2->{1:6666,2:3334};3->{1:3000,2:5000,3:2000};
4->{1:1000,2:5500,3:3500};5->{2:5000,3:5000};6->{2:3000,3:7000}.
These disagree with the historical player table as well as the later count change.
No selected-mod success/failure mode appears in this function. Q22 preserves these
differences; the old simulator is not adopted as the current device.

## Remaining gates
Q9 covers special inputs; Q21/Q22 cover current counts, first-side selection, exclusive/NNN
eligibility and individual weights. The requested sources are found and cached; a complete
3.29 transition model is not established. No owner test is requested and no recombination
calculator silently chooses between incompatible historical algorithms.
