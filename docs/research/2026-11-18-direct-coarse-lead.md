# The re-solved lead fed by a coarse model built directly: counted on R04 and R24 (research, 2026-11-18)

Ticket #1322. Research, no planner code. It follows `docs/research/2026-11-18-led-build-count.md` (#1315, PR #1318, "the led note" below), whose section 2a counted that the exact bound's build, led by a coarse model **solved again each round** with the rows of the keys already worked out (`worked`), ends in 3,000 of R04's 100,771 keys and 237 of R24's 60,895, but with a coarse model **merged** from the complete exact model, which a real build never has. This note counts the same lead with a coarse model **built directly**.

Rules read: OR-12, OR-13, OR-38. Nothing here cuts a key, an offer or an outcome (OR-12); each figure says what it is a figure of (OR-13); no proof is claimed from a count (OR-38). **Every figure below is a count that was run, on the owner's server on 2026-11-18, one process and one thread a run, with the 1-minute load beside it. A sentence that is a prediction says so.**

## Short answer

**The re-solved lead does not survive a coarse model built directly: the line of #1310's steps 2 to 5 closes in this form.** Counted on both dumps, with the same offers on both sides and the same coarse key as #1318's figures:

1. **R24.** With the merged coarse model the re-solved lead ends in 237 of 60,895 keys; with the coarse model built directly the best of nine variants ends in **37,864 (62.18%)**, #1318's plain `worked` in 43,112 to 44,242 (71% to 73%), and the fixed lead from the same direct rows (the control) in 43,485 (71.41%). Today's build with no lead needs 45,890 under the same rule. The direct model itself is 16,268 to 19,958 coarse keys, so the build and its lead together work out **54,864 to 64,200 keys, 90% to 105% of the blind build's 60,895** (section 4).
2. **R04.** No direct-row run finished. Stopped by hand after 82 to 134 minutes, they had worked out **22,987 to 39,900 keys and stood at 3.7% to 3.9% of the value**, where the merged lead ended in 3,000 keys; at 3,000 keys they stood at 1.5% to 2.2%. The direct model's start value is 1.50% of the exact one in every variant (the merge's: 8.21%), and today's build with no lead stood at 2.3% to 3.6% after as many keys: on R04 the direct lead is worth about as much as none.
3. **Why.** What #1318's 3,000 and 237 rest on is the strength of the merged coarse rows, not the re-solve: the direct rows (exact only where `Pattern.mode_of` is `ANY` or the kernel is certain, the angelic stand-in elsewhere) prove 32.65% of R24's value (53.76% with the `ONE` rows exact) and 1.50% of R04's, against the merge's 86.48% and 8.21%; and with such rows solving again each round gains nothing over a fixed lead. On R04 the stand-ins of the Exalted Orb and the Fracturing Orb hold the direct value at 352.39 c whatever else is changed. **Prediction, not measured:** the line could reopen only with per-class arguments that make those rows near-exact, which the design note priced at two to three days each, one with no finished argument; nothing counted here says they would bring the lead near the merge's.

Lead at or under the true value: checked at every key and every round of every run, 0 keys above it (section 1).

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

**Variants not in #1318**, added because the first runs showed the led value falling from round to round (with merged rows it never falls; with direct rows it does, for three reasons: a worked key's own rows land on coarse keys valued at the floor; a coarse key worked out again at a new representative gains rows, and more rows can only lower a minimum; a coarse key newly worked out sends its rows to coarse keys not yet worked out). Each was asked for by the `checker`; each is checked under the truth like the rest:

- `MAX=1` (pins): a worked key whose rows are worth less than its coarse lead is pinned at its lead (its state's one action leads to its coarse state, or costs the lead), since both are at or under its value **if the coarse lead is** (which here is shown by count only). The pins are set again after each solve, at most 12 solves a round. In `MAX=1` without `RATCHET`, the coarse states keep their direct rows only (the worked members' rows, which `worked` adds to them, can only lower them).
- `RATCHET=1`: the direct model is solved alone each round, and a coarse key's lead is the **largest** value it had in any round so far; the exact part is then solved with its tips at those leads (and pins). Its leads are checked under the truth every round like the others.
- `ONE=exact`: an offer whose mode at the representative is `ONE` (the bound's builder takes it at one member per composition of the junk) gets the representative's exact kernel instead of the angelic stand-in. It is more optimistic in kind than the builder (one representative for a key, where the builder takes several members), and it is checked by count like the rest.

**The check** (point 5): at every round, the value of every coarse state is compared with the complete model's value at every exact key it holds, and every worked key's own state with its key's value. In the runs with a lead that changes (`floor`, `demand`, `RATCHET`) the lead was above the truth at **0 keys in every round of every run**, stopped runs included (the `bad` column of each `.tsv`). In `static` the lead is fixed and was checked once, before the first round: 0 keys. The final start value of every finished run equals the complete one to 3e-13 (relative). This is a check by count on two dumps, not a proof that a direct model built this way is a lower bound elsewhere: a member that no representative covers can reach a coarse key none of them reaches (#1315's caveat of `sdm.py`).

The runs were made on this branch's tree (#1318's head 610d44e6 and the commits of this ticket); the dumps were made on 37de068f. That the two trees build the same model on these offers is shown by the asserts above (same offers, same start key), by the direct model on R24 finding exactly the 19,964 coarse keys of #1318's merge, and by the check (0 keys above the truth, the final values equal).

## 2. The table

"Keys" are exact keys worked out (of 60,895 on R24, 100,771 on R04: every key but the goals), "until no tip" is the end of the count (the start value is then the complete one), "within 1%" the first round at 99% of the complete start value. "Direct model" gives the coarse keys it found and worked out (at the end of the run), its start value (the direct model alone, built along its own policy, as a share of the exact start value) and its seconds. All rule `mass:0.5`, one process and one thread.

### R24 (60,895 keys; complete start value 3,617.64 c)

| Lead | Direct model: coarse keys found / worked out | Its start value | Keys worked out until no tip | Until within 1% | Seconds of the run (load) |
|---|---|---|---|---|---|
| merged coarse model, `worked` (#1318, the control) | 19,964 (merged from the complete model) | 86.48% | **237 (0.39%)** | 205 | 47 (18-21) |
| direct, `static` (fixed lead) | 16,238 / 16,220 | 32.65% | 43,485 (71.41%) | 42,715 | 473 (7.0) |
| direct, `worked`, `floor` | 16,238 / 16,220 | 32.65% | 43,112 (70.80%) | 42,240 | 819 (6.7) |
| direct, `worked`, `demand` | 19,964 / 19,958 | 32.65% | 44,242 (72.65%) | 43,688 | 853 (6.8) |
| direct, `worked`, `floor`, `MAX` | 16,238 / 16,220 | 32.65% | 42,225 (69.34%) | 41,421 | 802 (7.0) |
| direct, `worked`, `demand`, `MAX` | 19,964 / 19,958 | 32.65% | 46,165 (75.81%) | 45,328 | 789 (7.0) |
| direct, `RATCHET`, `floor`, `MAX` | 16,238 / 16,220 | 32.65% | 43,784 (71.90%) | 42,875 | 638 (10.0) |
| direct, `RATCHET`, `demand`, `MAX` | 19,964 / 19,958 | 32.65% | 42,298 (69.46%) | 41,515 | 730 (10.1) |
| direct, `RATCHET`, `floor`, `MAX`, `ONE=exact` | 16,274 / 16,268 | 53.76% | 38,596 (63.38%) | 37,673 | 421 (9.8) |
| direct, `RATCHET`, `demand`, `MAX`, `ONE=exact` | 19,964 / 19,958 | 53.76% | **37,864 (62.18%)** | 37,023 | 492 (10.0) |
| today's floor (#1318, `floor`, mass:0.5) | - | 0.0% | 45,890 (75.36%) | 45,113 | - |

(In the `floor`, `static` and floor-`RATCHET` rows the direct model's coarse keys are those of its own build, from its `DIRECT` line; the result lines print 19,961, which adds the coarse keys the exact build's tips named and the direct model never worked out: they stay at the floor. In the `demand` rows the direct model ends with 19,958 coarse keys worked out of the 19,964 of #1318's merge: the whole coarse model.)

### R04 (100,771 keys; complete start value 23,534.09 c)

No R04 run with direct rows finished. Each was stopped by hand at 23:00 (load 10), after 85 to 135 minutes, when every one had worked out more than 7 times the merged count's 3,000 keys at under 4% of the value; the row gives where it stood (keys worked out; the start value as a share of the complete one; and, for comparison at equal keys, the same share when the run had worked out 3,000 keys). The lead was above the truth at 0 keys in every round of every run.

| Lead | Direct model: coarse keys found / worked out (at the stop) | Its start value | Stopped at (minutes) | Share at the stop | Share at 3,000 keys | Within 1% |
|---|---|---|---|---|---|---|
| merged coarse model, `worked` (#1318, the control) | 28,596 (merged) | 8.21% | **ended: 3,000 keys (2.98%)** (34 min) | 100% | 100% | 2,257 |
| direct, `worked`, `demand` | 22,074 / 16,205 | 1.50% | 25,064 keys (24.9%) (120) | 3.79% | 2.18% | not reached |
| direct, `worked`, `demand`, `MAX` | 22,668 / 16,682 | 1.50% | 25,529 keys (25.3%) (134) | 3.85% | 2.21% | not reached |
| direct, `RATCHET`, `demand`, `MAX`, `ONE=exact` | 20,330 / 14,787 | 1.50% | 22,987 keys (22.8%) (82) | 3.66% | 2.19% | not reached |
| direct, `RATCHET`, `floor`, `MAX`, `ONE=exact` | 5,549 / 1,972 (held) | 1.50% | 39,900 keys (39.6%) (82) | 3.67% | 1.52% | not reached |
| direct, `static` (fixed lead) | R04STATIC |
| today's floor (#1318, `floor`, mass:0.5; no coarse model) | - | 0.0% | stopped at 44,341 keys (44.0%) | 4.09% | 1.37% | not reached |

At equal keys today's floor (no lead at all) stood at 2.34% after 23,004 keys and 3.59% after 39,929 (#1318's `led-R04-floor-mass-0.5.tsv`), against 3.66% and 3.67% here: on R04 the direct lead is worth about as much as no lead.

## 3. What the table says

- **R24: the direct rows lose almost all of the merge's gain.** With the merged coarse model the re-solved lead ends in 237 keys; with the coarse model built directly, on the same coarse key, the same offers and the same rule, the best variant counted ends in 37,864 keys (62.18%), the plain `worked` of #1318 in 43,112 to 44,242 (70.80% to 72.65%), and the fixed lead from the same direct rows in 43,485 (71.41%). Today's tip value (the cheapest offer, no coarse model at all) needs 45,890 under the same rule (#1318). So the direct model, re-solved or not, saves 3% to 13% of the keys against having no lead, where the merged one saved 99.6%.
- **Re-solving does not help with direct rows.** On R24 every `worked` variant without `ONE=exact` is within 4.4 points of the fixed lead (69.34% to 75.81% against 71.41%); only the variants that keep a lead from falling (`RATCHET`) or give it stronger rows (`ONE=exact`) move it, and then by 9 points. With merged rows re-solving was the whole gain (#1318: fixed 29.82%, re-solved 0.39%); with direct rows there is nothing for it to recover, because what the direct rows lose is not in what the build later learns of the worked keys but in the coarse rows themselves.
- **Where the strength goes.** The direct model's own start value is 32.65% of the exact one on R24 (53.76% with `ONE=exact`), against the merge's 86.48% on the same coarse key; on R04 it is 1.50% in every variant (the merge's: 8.21%). On R04 the start value does not move with `ONE=exact`: what holds it at 352.39 c is the angelic stand-in of the Exalted Orb (`extremes`) and of the Fracturing Orb (`all`), the per-class arguments of the design note's section 5 that do not exist.
- **The lead falls as the direct model learns.** With direct rows the led start value is not monotone: on R24 `demand` it goes from 32.65% at round 5 to 10.48% at round 39 before it climbs (`floor`: 20.73% at round 50; even `static`, 21.42% at round 56, where a worked key's own rows land on coarse keys below its lead), as coarse keys are worked out again at new representatives (more rows, a lower minimum) and as newly worked coarse keys send rows to keys not yet worked out. So the direct model's 32.65% at the start is in part the optimism of a model that has seen few members. With `MAX` and `RATCHET` the start value never falls below the first round's; that changes the count by -2.6 to +6.4 points (`floor`: 69.34% to 71.90%; `demand`: 75.81% to 69.46%), not by an order.

- **R04: the direct rows do not lead the build at all.** The direct model's start value is 1.50% of the exact one in every variant (352.39 c, the figure `sdm.py` found on the guide's 8 offers in #1315), and the led build with it stood at 3.7% to 3.9% of the value after 23,000 to 40,000 keys, where the merged model ended in 3,000 and today's tip value, with no coarse model, stood at 2.3% to 3.6% after as many keys. Where the runs would have ended is not known; that they need far more than a few thousand keys is counted (7 to 13 times the merged count, under 4% of the value).

## 4. The cost of the direct model itself

The ticket asks for the cost of building the coarse model beside the exact keys the led build works out, and the sum against today's blind build on the same offers.

| Route | Variant | Direct model: coarse keys worked out | Its kernels and rows (seconds) | Its build along its own policy (seconds, load) | Peak memory of the run | Exact keys worked out | Sum of keys | Blind build on the same offers |
|---|---|---|---|---|---|---|---|---|
| R24 | best counted (`RATCHET`, `demand`, `MAX`, `ONE=exact`) | 19,958 | 30 s | 147 s (9.9) | 1.45 GB | 37,864 | **57,822 (95%)** | 60,895 |
| R24 | `RATCHET`, `floor`, `MAX`, `ONE=exact` | 16,268 | 17 s | 137 s (7.1) | 1.06 GB | 38,596 | **54,864 (90%)** | 60,895 |
| R24 | plain `worked`, `floor` (the ticket's count 1) | 16,220 | 9 s | 347 s (7.0) | 1.00 GB | 43,112 | 59,332 (97%) | 60,895 |
| R24 | plain `worked`, `demand` | 19,958 | 23 s | 350 s (7.0) | 1.56 GB | 44,242 | 64,200 (105%) | 60,895 |
| R04 | `RATCHET`, `demand`, `MAX`, `ONE=exact` (at the stop) | 14,787 | not written (stopped) | 133 s (9.9) | 0.97 GB at the direct build; the led part was stopped before its peak was written | 22,987 (stopped, 3.66%) | more than 37,774 | 100,771 |
| R04 | `RATCHET`, `floor`, `MAX`, `ONE=exact` (at the stop) | 1,972 | 7 s | 133 s (9.9) | as above | 39,900 (stopped, 3.67%) | more than 41,872 | 100,771 |

What the seconds are: of a direct build's 133 to 388 s, 7 to 18 s are kernels and rows and the rest is the 187 to 443 solves of the model along its own policy (one solve a round, as `sdm.py` does it). A real build would not solve after each key; the count of coarse keys is the figure that carries over, the seconds are this script's. A coarse key here costs about as much to work out as an exact key (it is worked out at one to a few representatives, each with every offer), so the keys may be added as they are; that is a reading of the counts, not a timing of both on one footing.

## 5. What the counts do not show

- **No other coarse key was counted with direct rows.** The coarse key is `tags,counts` alone, the one of #1318's 3,000 and 237. A finer coarse key (less merged) has stronger direct rows but more coarse keys; #1318's merge on R04 at 99.99% needed 29,057 to 73,676 coarse keys.
- **The per-class arguments of the design note's section 5 were not written.** The direct rows here are `sdm.py`'s: exact where `Pattern.mode_of` is `ANY` or the kernel is certain (and `ONE` in the `ONE=exact` rows), angelic elsewhere. With those arguments the direct rows would be stronger; how much stronger is not counted. **Prediction, not measured:** on R04 the Exalted Orb and the Fracturing Orb hold the direct value at 1.5%, so an argument for those two is where any gain would come from first.
- **No proof.** The direct model is a lower bound here by count (0 keys above the truth, every round, two dumps), not by argument (OR-38).
- **Two dumps, the guide's offers (21 and 11).** Not a target's thousands of offers; not R17, R20, R14, whose exact builds do not complete.
- **One rule.** All runs use `mass:0.5`, #1318's rule for its 237 and 3,000. Other rules were not counted with direct rows.
- **The ratchet and the pins are this note's additions**, each sound given a sound coarse lead; other ways of combining a key's rows with its lead (a value iteration with the maximum at every state) were not counted.
- **Keys are counted as equal**, coarse and exact; the seconds of a real build per key are not in these counts.
- **Where the R04 runs would have ended.** All four were stopped by hand at 23:00 (section 2); the R04 `floor` and `static` runs of the plain variant were stopped before their led part to free their processes for the variants, and the `MAX`-only `floor` run on R04 was not run.

## 6. The tools

`research/cheap-bound/dled.py`, `dled.sh`; `dled-results.txt` (every run's `DIRECT` and `RESULT` lines, and the last per-round row of the stopped runs). The per-round files (`dled-ROUTE-MODE[-max].tsv`: keys worked out, start value, exact and coarse tips, coarse keys found and worked, keys above the truth, seconds) and the logs stay on the server under `.claude/scratch/t1322/` (an earlier set, made before a fault of `dled.py` was fixed, is in its `old-pendfloor/` and is not used: it gave a coarse key that was worked out the floor as soon as a new representative of it waited, and its leads collapsed).
