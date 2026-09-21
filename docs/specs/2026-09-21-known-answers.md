# Spec: indexed hand-computed known answers

Dispatch only after core GOAL steps 1-6 are merged and green.
Worktree `.worktrees/known-answers`, branch `w-known-answers`.
Allowed `tests/test_known_answers.py`, `docs/research/known-answers.md`.
Budget15 minutes. Production code read-only. Do not duplicate the implementation as an oracle.

## Requirements
1. At least32 separately collected pytest cases with stable KA IDs and a source/derivation
   in each test docstring or parameter description. Small hand calculations, no game-memory
   facts or network. Existing spec/distribution/cost examples are mathematical sources.
2. Implement the following explicit constants as assertions on public APIs. Fractions below
   are hand values, not computed by a second weighted-draw algorithm. One row may provide
   several numbered cases. Use simple fixtures and parameterization, no production changes.
3. Write a compact index mapping KA ID, source/derivation, expected number, test. Do not claim
   PoB data checks or invalid-input checks count as independent probability known answers.

## Numbers / independent arithmetic
Source: hand calculation under affix_generation.md weighted-without-replacement and group
exclusion, authorized unbiased model GOAL Q2. All names/ranges in these examples are synthetic.

| Cases | Fixture / event | Expected |
|---|---|---|
| KA01-03 | A/B/C prefix weights1/1/2, two draws; exact AB,AC,BC | 1/6,5/12,5/12 |
| KA04-06 | Same; contains A, B, C | 7/12,7/12,5/6 |
| KA07-08 | Same; no A; A and not B | 5/12,5/12 |
| KA09-11 | Four distinct equal groups, three draws; contains A; contains A and B; exact ABC | 3/4,1/2,1/4 |
| KA12-14 | GroupX A1hit/A2junk3, groupB2, groupC2; two draws; hit; hit+B; B+C | 5/24,5/48,1/6 |
| KA15-17 | Prefix A1/Suffix B3, caps1/1, count1/2 half each; onlyA; onlyB; AB | 1/8,3/8,1/2 |
| KA18-19 | Same; containsA; E[count] | 5/8,3/2 |
| KA20-22 | Prefix A1/B1, Suffix C1/D1; schedule2 at1/1 then1 at3/3; ABC; ABD; containsA | 1/4,1/4,3/4 |
| KA23-24 | Prefix A1/B3 and suffixC2, caps1/1, two draws; AC; BC | 1/4,3/4 |
| KA25-26 | A/B/C1/1/2, blockA, one draw; B; C | 1/3,2/3 |
| KA27-29 | Outcome utilities0/6/10 with masses1/2,1/3,1/6; E[value]; P>=6; P>=10 | 11/3,1/2,1/6 |
| KA30-33 | Geometric p1/2 price2; E[attempts]; E[cost]; attempts_p90; cost_p90 | 2,4,4,8 |
| KA34-35 | Geometric p1/6 price2; E[cost]; cost_p90 | 12,26 |
| KA36-37 | Two independent p1/2 price1 stages; E[cost]; p90 | 4,7 |
| KA38-39 | p1/2 equal trial prices1/2; E[cost]; p90 | 3,6 |
| KA40-41 | p1/2 price2 reset3 setup7; E[cost]; p90 | 14,24 |

Pair AB in KA01:1/4*1/3+1/4*1/3=1/6. GroupX picked by two draws in KA12 with probability
5/6, then hit is1/4 of its group ->5/24. Side-capped KA23: A-first1/6 plus C-first1/3*1/4
=1/4. Chain KA37: totalattempts CDF6=57/64<.9, CDF7=15/16>=.9. Compound KA39:
CDF5=.8798828125, CDF6=.924072265625. Other fractions follow permutations/symmetry.

Report collected count, focused pytest, indexed IDs and any mismatch. All41 cases are small;
do not reduce count by grouping many assertions into one test and calling them collected cases.
