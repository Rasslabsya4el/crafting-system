# The re-solved lead fed by a coarse model built directly: counted on R04 and R24 (research, 2026-11-18)

Ticket #1322. Research, no planner code. It follows `docs/research/2026-11-18-led-build-count.md` (#1315, PR #1318, "the led note" below), whose section 2a counted that the exact bound's build, led by a coarse model **solved again each round** with the rows of the keys already worked out (`worked`), ends in 3,000 of R04's 100,771 keys and 237 of R24's 60,895, but with a coarse model **merged** from the complete exact model, which a real build never has. This note counts the same lead with a coarse model **built directly**.

Rules read: OR-12, OR-13, OR-38. Nothing here cuts a key, an offer or an outcome (OR-12); each figure says what it is a figure of (OR-13); no proof is claimed from a count (OR-38). **Every figure below is a count that was run, on the owner's server on 2026-11-18, one process and one thread a run, with the 1-minute load beside it. A sentence that is a prediction says so.**

## Short answer

ANSWER

## 1. What was counted

The tool is `research/cheap-bound/dled.py` (its docstring states the count; `dled.sh` runs it). It reads the design note's complete dumps `k-R04.pkl` and `k-R24.pkl` (`.claude/scratch/t1310/` on the server), as `led.py` does.

**The same offers on both sides** (ticket, point 3). The direct model is built from the planner's own inputs of the round each dump was made in: the run that made the dump (`benchmark_routes.py ROUTE --net` with the dump's first group, `lead-ROUTE.txt`) is started again and stopped at its call of `pattern_lower_bound`; the abstraction, the start and the priced offers of that call are taken, and the offers kept are the dump's, in the dump's order (asserted: same labels, same costs; and the direct model's start key is asserted equal to the dump's). R04: 20 offers and the restart; R24: 10 and the restart. So the direct model, the exact model and the led build hold the same offers, and the merged-row control is #1318's own runs (same dumps, same offers): R04 3,000 keys, R24 237.

**The direct model** (point 1). The coarse key is `tags,counts` (the bound's key without the ordinary slots' counts and protected tags), the key of #1318's 3,000 and 237. It is built by `sdm.py`'s method (#1315): a coarse key holds representatives, concrete states a kernel produced; an offer is taken at a representative as the bound's builder takes it at a member (the key's refusal, the quality pruning, the lumped twin of an erasing action), its successors pushed to their coarse keys, and the row is the exact pushed kernel where `Pattern.mode_of` is `ANY` at the representative's key or the kernel has one successor, else **angelic** (one certain row to each coarse key the kernel reaches, at the offer's cost). The dump holds no `Pattern.mode_of`; it is recomputed for each (representative, offer) through the same `Pattern` the bound uses. Which offers got which:

| Route | Exact kernel (`ANY` at the representative) | Exact, one successor | Angelic stand-in (mode at the representative) |
|---|---|---|---|
| R04 | Chaos Orb, both essences, Veiled Chaos Orb, Orb of Alteration (110 rows), Alchemy and Transmutation (1 each) | every bench craft, Remove Crafted Mods, Orb of Scouring, part of Annulment and of the Wild Bristle Matron | Exalted Orb, Regal Orb, Augmentation (`extremes`); Annulment, Wild Bristle Matron (`one`); Fracturing Orb, and Chaos, Veiled Chaos, Annulment, Alteration under a lock (`all`) |
| R24 | Deafening Essence of Torment, Veiled Chaos Orb | Pick 1 to 3, the suffix lock, part of Annulment and of the Veiled Chaos Orb | Harvest Add Remove Fire, and Annulment and Veiled Chaos Orb under a lock (`all`); Unveil, Annulment (`one`) |

(Counts of rows per offer and mode are on each run's `DIRECT` line; R04's own-policy build made 41,895 (representative, offer) pairs and 18,683 kernels, R24's 50,131 and 6,495.)

**Coarse keys off the direct model's own policy** (point 4). Three modes:

- `floor`: the direct model is worked out along its **own** cheapest policy from the start until that policy meets no tip of it (sdm.py's order), then held. A coarse key it did not work out is valued at the cheapest offer's price (R04 0.0105 c, R24 0.0000002 c). The exact build is then led by `worked`.
- `demand`: as `floor`, and in each round the coarse keys that the led model's cheapest policy meets unworked, below the exact build's tips, are worked out in the direct model too (their representative, where no kernel gave one, is a member of an exact key holding it, `Pattern.members(key, ANY)`). The coarse keys it ends with are counted.
- `static` (point 2, control): the direct model of `floor`, solved once, its value at a tip's coarse key held fixed (led.py's static lead).

**`worked`** is #1318's (`led.py REFINE=worked`): each round one model is solved: the direct coarse states (their direct rows, plus the dump's rows of every worked-out key they hold), and each worked-out exact key as a state of its own with the dump's rows, whose outcomes go to the exact key where it is worked out and to its coarse state otherwise. The cheapest policy is walked from the start; the tips it meets are worked out by `mass:0.5` (the tips the policy visits most, holding half its visits to tips; #1318's rule for its 3,000 and 237); the run ends when it meets no tip.

**`worked`, pinned (`MAX=1`)**, a variant not in #1318, added because of what the first runs showed (section 3): the coarse states keep their direct rows only, and a worked-out key whose rows are worth less than its coarse state's value is pinned to its coarse state (its value is then its lead). Both are lower bounds of the key, so the larger is too; the pins are set again after each solve until none changes. A build has every input of it.

**The check** (point 5): at every round, the value of every coarse state is compared with the complete model's value at every exact key it holds, and every worked key's own state with its key's value. The lead is above the truth at 0 keys in 0 rounds, in every run (the `lead above the truth` column of each run's log). The final start value of each finished run equals the complete one (largest difference RELDIFF, relative).

## 2. The table

TABLE

## 3. What the table says

SAYS

## 4. The cost of the direct model itself

COST

## 5. What the counts do not show

NOTSHOWN

## 6. The tools

`research/cheap-bound/dled.py`, `dled.sh`; the per-round files (`dled-ROUTE-MODE[-max].tsv`: keys worked out, start value, exact and coarse tips, coarse keys found and worked, keys above the truth, seconds) and the logs stay on the server under `.claude/scratch/t1322/`; `dled-results.txt` holds every run's result line.
