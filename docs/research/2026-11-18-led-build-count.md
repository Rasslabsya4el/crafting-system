# The cheap bound, step 1: the led exact build counted on two dumps, and a direct status model tried over every offer (research, 2026-11-18)

Ticket #1315. Research, no planner code. It follows `docs/research/2026-11-18-cheap-bound-design.md` (#1310, "the design note" below) and answers the question that note left open in its section 8, step 1: is the "status model" (a coarse lower bound over every offer, which leads the exact build) worth three to four weeks.

Rules read: OR-12, OR-13, OR-38. Nothing here cuts a key, an offer or an outcome (OR-12); every figure says what it is a figure of (OR-13); no claim of a proof is made from a count (OR-38).

Everything counted here ran on the owner's server on 2026-11-18, one process and one thread a run, on the head of PR #1313 (main 37de068f and the design note). The dumps are the design note's: `k-R04.pkl` (R04, 20 offers and the restart, the complete model of the exact bound: 100,773 keys, start value 23,534.09 c) and `k-R24.pkl` (R24, 10 offers and the restart, 60,904 keys, 3,617.64 c). The tools and their outputs are in `research/cheap-bound/` (section 6). **Every figure below is a count that was run. A sentence that is a prediction says "prediction".**

Words, as in the design note. A **key** is the exact bound's summary of an item; the **build** works keys out (finds what every offer does at a key). A **tip** is a key that was found and not worked out. A **lead** is a number given to a tip in place of its true value: it must be at or under the true value. The **coarse key** drops parts of the key; the **status model** is the model on a coarse key, and its value at a tip's coarse key is a lead.

## Short answer

**No: steps 2 to 5 of the design note's plan should not be built as they stand.** Three counts say so.

1. **A led build needs most of the keys unless the lead is nearly exact.** On R24 a lead worth 86% of the true value (the junk counts dropped: 19,964 coarse keys) still makes the build work out 54,866 of 60,895 keys (90%) by the plain rule, and 18,161 (30%) by the best rule tried; a lead worth 42% (the status alone, 196 coarse keys) makes it work out 60,894 (100%) and 40,601 (67%). Only leads at 99.99% or more of the true value bring the count down to the hundreds or low thousands (section 2).
2. **On R04 no small coarse key gives such a lead.** The leads worth 99.99% or more have 29,057 to 73,676 coarse keys, so the "cheap" model is a third to three quarters of the exact one. The lead worth 92% (junk counts as their sum, 64,186 coarse keys) needed 83,347 of 100,771 keys (83%) to come within 1%; the lead worth 8% (junk counts dropped) had moved the start value from 8.2% to 9.0% after 9,741 keys when its run was stopped. **So the line stops on R04, as the design note said it would in this case.**
3. **A status model built directly, with the optimistic stand-in where no argument exists, proves little, and over every offer it was not built at all.** On R04's guide offers it proves 352.39 c, complete, where the merged model of the design note proves 1,932.62 c and the exact bound 23,534.09 c (1.5%); on R24's it stood at 390.16 c when stopped, against 3,128.55 c and 3,617.64 c. Its strength is all in the per-class arguments (the design note's step 4, two to three days each, one of them with no finished argument), not in the model. Over every offer of a target the scratch build ran out of memory at the start key on five of six targets tried: **point 2 of the ticket is not delivered, and R17 still has no figure** (section 4).

What the counts suggest instead, on R04 (section 3): **the kind of a fractured junk mod can leave the key for nothing.** Merged on a key where a fractured junk mod is one value whatever its family type, R04's model has 60,901 keys in place of 100,773 and the same start value to 12 digits (23,534.0922029); with every fractured mod that gives no leaf anything folded, 41,847 keys and the same value. That is an exact build 1.7 to 2.4 times smaller on R04 with no loss, if a direct argument is found for it; it is a merge of a built model here, not a build (#1317). The junk **count** cannot leave: that is where R04's cost is, as the design note found (8% of the value without it).

## 1. What was counted, exactly

`led.py` reads a complete dump and builds nothing. It starts with only the start key worked out. In a round, the model of the keys worked out so far is solved by the planner's own solver (`solve_packed`), each tip being a state whose one action costs its lead and ends (the planner's floor action, `pack_pattern_model`). The cheapest policy is walked from the start, and tips it meets are worked out: their rows are taken from the dump. The count ends when the policy meets no tip. At that moment the start value must equal the complete model's, and it does in every finished run (the largest difference is 4e-13, relative).

- **What is counted.** Keys worked out, of the keys a complete build works out (100,771 on R04, 60,895 on R24: every key but the goals). Every key counts as one; what a key costs in seconds is not in the dumps.
- **"Within 1%".** The first round whose start value is at least 99% of the complete model's. In a real run the planner does not know the complete value; it stops when its bound is within 1% of the plan in hand. So this column is the least a real run could need, not what it would need.
- **The lead.** `exact`: the complete model's own value at the tip (no lead can do better). `floor`: the price of the cheapest offer, which is what a tip is valued at today (`_tip_floor`). Else the value of the model merged on a coarse key, as the design note's `ka.py` merges it (its section 4). Before a lead is used it is compared with the true value at every key: it is above it at 0 keys in every run (the merge lemma of the design note, by count).
- **The rule: which tips are worked out in a round.** `all`: every tip the cheapest policy meets (the plain rule of the textbook method, LAO*). `mass:0.5`: the tips the policy visits most often, the fewest that hold half of all its visits to tips (visits counted over 400 steps from the start). One action of these models can lead to thousands of keys at once (R24: one reroll leads to 24,091), so the rule matters by a factor of three. `mass:0.1` was started on one lead of R04 and is slower still. No rule tried is claimed to be the best one.
- **Not counted:** the cost of building the coarse model itself. The table gives its number of keys beside each lead; a led build pays for those keys too, by a direct build that does not exist (section 4).

## 2. Point 1: the table

`led-summary.md` holds every run; `led-results.txt` the result lines. "Lead's value" is the lead at the start key as a share of the complete model's start value.

### R24 (60,895 keys to work out; complete start value 3,617.64 c)

| Lead | Coarse keys | Lead's value | Rule | Keys worked out until the policy meets no tip | Until within 1% | Until within 10% |
|---|---|---|---|---|---|---|
| the exact value (the least possible) | - | 100% | all | 231 (0.38%) | 1 | 1 |
| the cheapest offer's price (today) | - | 0.0% | all | 60,894 (100.00%) | 60,894 | 60,894 |
| | | | mass:0.5 | 45,890 (75.36%) | 45,113 | 43,731 |
| junk counts as their sum | 53,291 | 100.00% | all | 185 (0.30%) | 1 | 1 |
| junk counts dropped | 19,964 | 86.48% | all | 54,866 (90.10%) | 54,850 | 29,444 |
| | | | mass:0.5 | 18,161 (29.82%) | 17,256 | 6,907 |
| the suffix count only | 25,958 | 86.48% | all | 55,392 (90.96%) | 52,591 | 29,643 |
| | | | mass:0.5 | 18,123 (29.76%) | 16,278 | 6,530 |
| counts and veiled slots dropped | 17,892 | 55.66% | all | 60,455 (99.28%) | 60,455 | 60,455 |
| | | | mass:0.5 | 35,741 (58.69%) | 34,550 | 31,458 |
| counts and crafted slots dropped | 9,982 | 43.70% | all | 60,504 (99.36%) | 60,504 | 60,504 |
| | | | mass:0.5 | 40,326 (66.22%) | 38,678 | 36,734 |
| flags, fractured mods and status | 196 | 42.17% | all | 60,894 (100.00%) | 60,510 | 60,501 |
| | | | mass:0.5 | 40,601 (66.67%) | 39,756 | 35,710 |

### R04 (100,771 keys to work out; complete start value 23,534.09 c)

Four runs did not finish: they were stopped by hand after 17 to 20 minutes each, and the row gives where they stood ("stopped at"). No R04 run with a lead under 99.99% finished. The leads the design note's section 4 lists and this table does not (the suffix or the prefix count only, counts capped at 1 or 2, counts and crafted slots dropped, the status alone: 73% down to 1.8% of the value) were queued behind the unfinished runs and **were not run**.

| Lead | Coarse keys | Lead's value | Rule | Keys worked out until the policy meets no tip | Until within 1% |
|---|---|---|---|---|---|
| the exact value (the least possible) | - | 100% | all | 734 (0.73%) | 1 |
| | | | mass:0.5 | 740 (0.73%) | 1 |
| a fractured junk mod's type folded (`none+fj`, section 3) | 60,901 | 100.00% | mass:0.5 | 674 (0.67%) | 1 |
| every fractured mod that gives no leaf anything folded (`none+fa`) | 41,847 | 100.00% | mass:0.5 | 761 (0.76%) | 1 |
| tags dropped | 73,676 | 99.99% | all | 5,485 (5.44%) | 1 |
| | | | mass:0.5 | 2,030 (2.01%) | 1 |
| tags dropped, `fj` | 42,966 | 99.99% | mass:0.5 | 2,050 (2.03%) | 1 |
| tags dropped, `fa` | 29,057 | 99.99% | mass:0.5 | 2,061 (2.05%) | 1 |
| tags dropped, junk counts as their sum | 64,186 | 92.02% | all | **stopped at** 86,755 (86.1%), start value 99.51%, 14 tips still on the policy | 83,347 (82.7%) |
| | | | mass:0.5 | **stopped at** 21,732 (21.6%), start value 94.10%, 2,440 tips on the policy | not reached |
| tags and junk counts dropped | 28,596 | 8.21% | mass:0.1 | **stopped at** 9,741 (9.7%), start value 8.97% | not reached |
| the cheapest offer's price (today) | - | 0.0% | mass:0.5 | **stopped at** 21,268 (21.1%), start value 2.26% | not reached |

### What the table says

- **The design note's hope was the first row: 231 and 734 keys.** That is what a perfect lead needs (the note counted 197 and 681 keys on the plan itself; the build needs a few more, to see the plan's neighbours are dearer). It is 0.4% and 0.7% of the build.
- **The lead has to be nearly exact for anything like it.** On R24 the lead at 100.00% (53,291 coarse keys) needs 185 keys; the leads at 86% need 30% to 90% of the build; the leads at 42% to 56% need 59% to 100%. There is no middle: between 86% and 100% of the value the count falls from tens of thousands to hundreds, and no coarse key tried lies in between.
- **A led build is better than a blind one, by less than the note hoped.** With today's tip value and the better rule, R24's build needs 75% of its keys; with the 196-key status model as the lead, 67%; with the 19,964-key model, 30%. So on R24 the best case counted is a build 3.4 times smaller, bought with a coarse model of 19,964 keys that would itself have to be built directly, soundly, over the same offers. The sum, 38,125 keys, is 63% of the 60,895.
- **"Within 1%" is no shortcut.** On every lead under 100% the build is within 1% only a few hundred keys before the end (R24, junk counts dropped, mass:0.5: 17,256 of 18,161).
- **On R04 the line stops.** The only leads that end in a few thousand keys are those at 99.99% or more of the value, and their coarse models have 29,057 to 73,676 keys: no cheap bound, the exact model again at a third to three quarters of its size. The lead at 92% (64,186 coarse keys) needed 83,347 keys (83%) to be within 1% under the plain rule; under the better rule it had worked out 21,732 keys and stood at 94.1%, having started at 92.0%. The lead at 8% (the design note's "without tags and counts", the one its recommendation rested on for R04) had gained 0.76 points of the value in 9,741 keys. Where these two runs would have ended is **not known**; that they are far from the 734 keys of a perfect lead is counted.

## 3. What the counts suggest instead, on R04

The question of the brief: is R04's cost really in the junk count, so that the key must be made smaller some other way. Yes to both halves.

- **The count cannot go.** The design note's merge without the junk counts keeps 8.2% of the value, and a lead at 8.2% moves almost nothing here (section 2). With the two counts folded into their sum the lead is at 92%, which is still not enough (section 2), and that coarse model has 64,186 keys.
- **The kind of a fractured junk mod can go, for nothing.** R04's key holds which mod the Fracturing Orb took, and for a junk mod it holds its family type (`~0@attack`, `~4`, ...: 12 types). Two folds were merged (`led.py`):
  - `none+fj`, a fractured junk mod known by its family type is the one value "a fractured junk mod": **60,901 keys, start value 23,534.0922029379 c against the complete model's 23,534.0922029357 c.** Checked key by key as well: in each of the 7,030 merged keys that hold several keys, the exact values of those keys are equal (largest spread 0.0).
  - `none+fa`, every fractured mod that gives no leaf anything is one value (the dump also holds keys whose fractured mod is a bench craft or a veiled mod): **41,847 keys, start value 23,534.0922029384 c.** Not checked key by key.
  - With the protected tags dropped too: 42,966 keys (`tags+fj`) and 29,057 keys (`tags+fa`), both 23,532.68 c (99.99%); inside a merged key the exact values then differ by up to 3e-05.
- **What this is and is not.** It is a merge of a model that had been built, so it shows the value survives; it is not a build on the smaller key. A direct build needs the argument that every action treats two fractured junk mods of different types alike once the rest of the key is known (equal values in every merged key suggest an exact symmetry; they do not prove one). **Prediction, not measured:** R04's exact build on the guide's 21 offers works out 40% fewer keys with the first fold. This is a change to the exact bound's key (#1158's line: a faster exact build), not a second bound. It was counted on R04 alone; R24's key holds no fractured mod. Filed as #1317.
- R24 has the matching fact for the junk counts: as their sum, 53,291 keys of 60,904 and 100.00% of the value (the design note's `kc-R24.txt`). That saves 12%: little.

## 4. Point 2: a direct status model over every offer

**Not delivered as the ticket asks.** The ticket asks for a direct status model over every offer of each of the 13 targets: keys and seconds, its figure against the guide, whether the guide's offers are on its plan, and a figure for R17. What exists is a script, two runs on the guide's offers, and six runs over every offer that did not get past the start key. No target has a figure over every offer; R17 has none.

**The script** (`sdm.py`; its docstring states the build). The coarse key is the bound's key without the junk counts and the protected tags. A coarse key holds representatives (concrete states a kernel produced). An offer is taken at a representative with the abstraction's exact kernel and offered as that kernel where the bound's own rule says one member stands for the key (`Pattern.mode_of` gives `ANY`: an erasing reroll that reads no junk, no lock held) or where it has one successor; everywhere else as the optimistic stand-in of the design note ("angelic": the action may pick its outcome). Keys are worked out where the model's own cheapest policy goes. **It is not a proof:** a member that is no representative could reach a coarse key that no representative reaches. It was not tested key by key against the merged model.

**On the guide's offers** (one process, load 15):

| Route | Offers | Coarse keys found | Worked out | Result | Its figure | The merged model of the design note (the ceiling) | The exact bound | Guide's labels on its plan |
|---|---|---|---|---|---|---|---|---|
| R04 | 8 and the restart | 1,537 | 1,059 | complete in 288 s (the policy meets no tip) | **352.39 c** | 1,932.62 c (on 20 offers and the restart) | 23,534.09 c (same 21) | 5 of 8: both essences, Fracturing Orb, Exalted Orb, the attack-speed craft; not Annulment, not Remove Crafted Mods, not the "Cannot roll Attack" craft |
| R24 | 9 and the restart | 15,356 | 10,727 | stopped by hand at 629 s, 33 tips on the policy | 390.16 c at the stop (a value of the model with every tip free, so at most the complete one) | 3,128.55 c (10 and the restart) | 3,617.64 c | at 150 s: 2 of 9 (Veiled Chaos Orb, Unveil); not read at the stop |

The R04 row's two models are on different offer sets (9 against 21), so "direct at or under merged" is seen at the start key only (352.39 under 1,932.62, and more offers can only lower the merged figure), not key by key.

What these two runs say: with the stand-in in place of the arguments, the direct model proves **1.5% of the exact bound on R04 and at most 11% on R24**, a fifth and an eighth of what the merged model promised. The gap between the direct figure and the merged one is exactly the per-class arguments of the design note's section 5 (additions over the junk count, removals, the Fracturing Orb, a reroll under a lock). The status model is not strong until they are all written.

**Over every offer** (`sdm.sh`, six targets at once, one process each, a 10-minute limit, 20 GB of address space each, load 12 to 15):

| Route | Offers after twins | How far |
|---|---|---|
| R04 | 6,220 | out of memory inside the first 250 offers of the start key |
| R12 | 5,960 | out of memory inside the first 250 offers of the start key |
| R24 | 4,253 | out of memory inside the first 250 offers of the start key |
| R14 | 10,915 | 13 keys worked out, 202 found, start value 0.04 c after 188 s; then out of memory |
| R20 | 10,878 | every offer refused at the unopened listing in 1 s; then out of memory in the listing's draw (`actions/draw.py`, `spread_ends`) |
| R17 | 7,333 | still inside the first 250 offers of the start key after 8 minutes, when stopped by hand |
| R10, R11, R05, R13, R08, R09, R06 | - | not run |

**What this failure is, plainly.** It is a fault of the script's method, not a measurement of the status model. The script asks the abstraction for the exact kernel of every offer at a concrete item; some offer among a target's thousands has an exact kernel too large to hold (the planner's own build never asks for it that way: it shares kernels between members, lumps, and relaxes draws, `abstraction/_pattern.py`). So the count "keys and seconds over every offer" needs a build made with the bound's own machinery (`PatternBuilder` with a coarse key), which is the design note's step 2 (three to four days), not a scratch script. **Which offer blew up was not found.** One thing is counted all the same: the simple route to a direct model over every offer does not work, on five of six targets tried.

## 5. The yes or no, and what it rests on

**Should steps 2 to 5 of the design note's plan be built: no.**

It rests on:

1. Section 2, R24: a lead at 86% of the truth leaves 30% to 90% of the build to do, and the coarse model that gives that lead is a third of the exact one. Counted, two rules, two coarse keys at 86%.
2. Section 2, R04: no coarse key tried is both small and within 1% of the truth; the leads at 92% and at 8% were heading for most of the keys when read. Counted as far as the runs went; the two slow runs were not finished, and the note says where they stood.
3. Section 4: the direct model with the optimistic stand-in is at the level of the offers' floors, so the figures the design note gave for the status model (42% to 86% on R24) are only reached after every per-class argument is written and proved. Counted on R24's guide offers; over every offer the build did not get past the start key on five of the six targets tried (section 4).

What it does not rest on: any timing (none is used as an argument), and any claim about R17, R20 or R14, whose exact builds do not complete and so have no dump to count on.

What stays worth doing from this line, each smaller than the plan it replaces:

- **The kind of a fractured junk mod out of the exact key** (section 3): one argument, one PR on `abstraction/_pattern.py`, measured on R04 against this note's merge (41,847 keys, the same value). Filed as #1317.
- **The exact build worked out along its own cheapest policy instead of blindly**, with today's tip value: R24 needs 75% of its keys that way (section 2, the `floor` row, mass:0.5), so the gain is a quarter at best, and on R04 the count did not finish. Not recommended on these counts; named so that nobody proposes it again without a better rule.

## 6. The tools

In `research/cheap-bound/`, beside the design note's: `led.py` (the led build counted on a dump; its docstring states the count), `led.sh` (one route, one rule, the leads in turn), `ledsum.py` (the table), `sdm.py` and `sdm.sh` (the direct status model of section 4); the outputs `led-summary.md`, `led-results.txt`, `sdm-results.txt`. The per-round files (`led-*.tsv`: keys worked out and start value after each round) and the logs stay on the server under `.claude/scratch/t1315/`.

## Not done, not verified

- **Point 2 of the ticket is not done** (section 4): no direct status model over every offer on any target, no figure for R17, no answer to "are the guide's offers on its plan among all offers". The seven targets not named in section 4's last table were not run at all.
- Four R04 runs of point 1 were stopped unfinished, and six leads of the design note's section 4 were not run on R04 (section 2 says which). The "no" for R04 rests on the runs that finished (leads at 99.99% and above) and on where the unfinished ones stood.
- The rules `all` and `mass:0.5` are two rules, not the best rule. A rule that works out fewer keys may exist; none was looked for beyond `mass:0.1`, which was slower and did not finish.
- Keys are counted as equal. A key's cost in seconds is not in the dumps, so "30% of the keys" is not "30% of the time".
- The counts are on two routes, on the guide's offers (21 and 11), not on a target's thousands of offers. More offers were not counted.
- The fold of section 3 is a merge on one route. No argument for a direct build was written; whether the Fracturing Orb may take a bench craft or a veiled mod in the game (the dump has such keys) was not checked.
- `sdm.py` is not sound by proof and was not tested key by key against a merged model.
- No timing in this note is used as an argument; each is one run under the load written beside it.
- The `checker` had not reviewed this note when it was written (see the PR).
