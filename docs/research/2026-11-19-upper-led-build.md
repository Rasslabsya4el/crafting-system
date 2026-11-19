# The exact build led from above as well: an incumbent plan beside the lower values, counted on R04 and R24 (research, 2026-11-19)

Ticket #1321. Research, no planner code. It follows `docs/research/2026-11-18-led-build-count.md` (#1315, PR #1318, "the led note") and `docs/research/2026-11-18-direct-coarse-lead.md` (#1322, PR #1324, "the direct note"). Those two counted the exact bound's build led from **below** only: a tip (a key found and not worked out) is valued by a lead at or under its true value, the build works out the tips the cheapest policy meets, and "within 1%" was read against the complete value, which a run does not know. This note counts the same build led from **above** as well, in the manner of bounded RTDP and LAO* with an upper bound: a plan in hand (the incumbent) gives an upper value, the tips are worked out in the order of (visits under the lower policy) x (upper - lower), and the build stops when the lower value at the start is within 1% of the incumbent (OR-39).

Rules read: OR-12 (nothing is cut: the upper value only orders the work and says when the stop is reached), OR-13 (each figure says what it is a figure of), OR-38 (no proof is claimed from a count), OR-39 (the run's 1%). **Every figure below is a count that was run, on the owner's server on 2026-11-19, one process and one thread a run, the 1-minute load beside it. A sentence that is a prediction says so.**

## Short answer

1. **The upper side is cheap; the lower side is the whole cost.** With a perfect lower value at the tips, the incumbent comes within 1% (and so the build stops) after **189 keys on R24 and 387 on R04** (of 60,895 and 100,771). With every lower value a build has (the floor and the direct leads) and with the merged references under the visit and gap weights, the incumbent is within 1% of the complete value before the lower value is, and **the stop falls on the round where the lower value reaches 99% of the complete value**, to the key, in every such run but one (the merged lead under `mass:0.5`, 11 keys later). So, for a given order of work, the led note's "within 1%" column, which it called a floor of the real stop, **is** the stop of an upper-led build on R24 (on R04 no run with such a lead got near either: section 2). Where L is right from the first round (the exact, `tags+sum` and `BEST` references) or under `oracle` weights, the stop waits for the incumbent instead (section 3).
2. **So leading from above does not shrink the build.** To prove 1% at the start key: R24 with today's lower value (the cheapest offer) **45,113 keys (74.08%)**; with the fixed direct coarse lead of #1324 (`ONE=exact`, the stronger of the two fixed direct leads counted; the direct note's best, re-solved, ended in 37,864 with no upper side) **38,631 to 38,885 (63.4% to 63.9%)**, plus the direct model's own 16,268 coarse keys; R04 **not reached**: with the floor and with the direct lead, the runs were stopped at their 50-minute limit after 23,362 and 24,696 keys (23% and 25%) with L at 2.36% and 2.58% of the complete value and **no incumbent at all** (no worked plan with a finite value: U and U_none infinite in every round), so with those leads the upper side never came into play on R04; with the merged reference lead it had an incumbent from 12,393 keys, at 25 times the value. The ticket's rule (weights by the upper-lower gap) is no better than weights by visits alone (R24: 38,885 against 38,631; with the merged lead 17,056 against 17,267), and the best upper value a tip can have (its true value, `oracle`, which no build has) does not change that (section 3).
3. **Upper values at unworked keys.** Two were counted: none (infinite: the incumbent is then a plan that surely meets no tip) and **the restart plus the incumbent's start value** (sound in the dump's model: every non-goal key of both dumps has the restart offer to the start key, R04 3.2 c, R24 50 c, so V(k) <= c_r + V(start) <= c_r + U). The restart stand-in brings the incumbent within 1% sooner (R24 direct lead: 453 keys against 35,446; R04 perfect lead: 387 against 634), but since the stop waits for the lower value, **the stop is the same under both** wherever the lower value is not exact (section 2). **`BEST`'s cousin:** with the least true value inside the coarse key as the lower value (`BEST`, not computable), the upper-led build stops after **458 keys on R04** (814 to the end); no sound quantity counted here or in the two earlier notes comes near it (section 4).

## 1. What was counted

The tool is `research/cheap-bound/uled.py` (its docstring states the count; `uled.sh` runs it; `usum.py` makes the table `uled-summary.md`; `uled-results.txt` holds every result line). It reads the design note's complete dumps `k-R04.pkl` (R04, 20 offers and the restart, 100,771 keys to work out, complete start value 23,534.09 c) and `k-R24.pkl` (R24, 10 offers and the restart, 60,895 keys, 3,617.64 c), on the server under `.claude/scratch/t1310/`. It builds nothing; it works keys out of the dump in the order a led build would.

A round:

- **Lower model.** The worked-out keys with their rows; each tip a state whose one action costs its lead and ends (led.py's). Solved by the planner's solver (`solve_packed`). L is its start value.
- **Incumbent, restart upper.** The same worked keys; each tip's one action is the restart (cost c_r, to the start key). Solved, its start value U is the best plan that uses only worked rows and restarts whenever it meets a tip: the value of a real policy of the dump's model, so U >= V(start) (checked every round). A tip's upper value is then c_r + U.
- **Incumbent, no upper at tips.** The worked keys from which some plan reaches a goal with probability 1 and never meets a tip (computed exactly: the greatest set closed under such actions, then those that reach a goal inside it); U_none is its value at the start, infinite while the start is not in it.
- **The lower policy** (cheapest in the lower model) is walked from the start; its tips and their expected visits over 400 steps are counted (led.py's).
- **Stop** (OR-39): the first round with L >= 0.99 U, for each incumbent. The run goes on to led.py's end (no tip on the lower policy), so both stops and the end are read from one run.
- **Rule**: which of the policy's tips are worked out. `gap:0.5`, the ticket's: the tips with the largest visits x (c_r + U - lead), the fewest that hold half of that sum (while U is still infinite, every gap is infinite and the tips are weighed by visits alone). `mass:0.5`: by visits alone (led.py's; the rule of the led note's and the direct note's figures). `all`: every tip. Weights `oracle`: visits x (V(tip) - lead), the best upper value a tip can have; it reads the truth.

**Lower values at unworked keys** (the leads). Honest, a build has them: `floor`, the cheapest offer's price (what a tip is valued at today, `_tip_floor`); `direct`, the fixed lead of the direct coarse model of #1324 (`dled.py` mode `static`, saved per key with the new env `SAVELEAD`), plain (1.50% of R04's start value, 32.65% of R24's) and with `ONE=exact` (1.50% and 53.76%). References a build does not have: `exact` (the complete value), the merged coarse models of the led note (`tags,counts`, 86.48% on R24 and 8.21% on R04; `tags,counts,crafted,held,veiled`; `tags+sum`), and `BEST`. Every lead is checked to be at or under the complete value at every key before it is used: 0 keys above it in every run.

The direct lead is the **fixed** one (`static`). The direct note counted that solving it again each round gains at most 9 points on R24 and nothing on R04; the re-solved direct lead was not combined with the upper side here.

## 2. The table

"Stop" is the stop L >= 0.99 U with the restart upper (in brackets: with no upper at tips, where it differs). "L at 99%" is the first round whose L is at least 99% of the complete value, the led note's "within 1%". "U at 101%" is the first round whose incumbent is within 1% above the complete value (restart upper; no upper at tips). Keys are exact keys worked out. One process, one thread.

### R24 (60,895 keys; complete start value 3,617.64 c)

| Lower value at tips | Its start value | Rule | Stop | L at 99% | U at 101% | End (no tip on the lower policy) | Seconds (load) |
|---|---|---|---|---|---|---|---|
| exact (reference) | 100% | gap:0.5 | **189** (228) | 1 | 189 (228) | 231 | 4 (6.5) |
| junk counts as their sum, merged (reference) | 100.00% | gap:0.5 | 185 (195) | 1 | 185 (195) | 195 | 2 (6.3) |
| junk counts and tags dropped, merged (reference) | 86.48% | gap:0.5 | 17,056 | 17,056 | 11,931 (15,790) | 19,539 | 187 (6.3) |
| | | mass:0.5 | 17,267 | 17,256 | 17,267 (17,267) | 18,161 | 191 (7.0) |
| | | all | 54,850 | 54,850 | 29,703 (29,783) | 54,866 | 90 (7.6) |
| | | oracle weights (#1318's `oracle:0.5`, same weights, no incumbent read) | - | 16,306 | - | 18,727 | - |
| flags, fractured mods and status, merged (reference) | 42.17% | gap:0.5 | 39,744 | 39,744 | 28,513 (33,989) | 40,864 | 248 (6.3) |
| **the cheapest offer (today)** | 0.00% | gap:0.5 (= mass:0.5) | **45,113 (74.08%)** | 45,113 | 35,430 (35,430) | 45,890 | 230 (6.8) |
| | | oracle weights | 46,528 | 45,541 | 46,528 (46,528) | 46,528 | 252 (8.0) |
| **direct, `ONE=exact`, fixed (#1324)** | 53.76% | gap:0.5 | **38,885 (63.86%)** | 38,885 | 453 (35,446) | 39,758 | 379 (6.9) |
| | | mass:0.5 | 38,631 (63.44%) | 38,631 | 428 (645) | 39,439 | 380 (7.4) |
| | | all | 60,867 | 60,867 | 892 (30,570) | 60,867 | 163 (7.1) |
| | | oracle weights | 38,331 | 37,336 | 38,331 (38,331) | 38,331 | 319 (8.0) |
| direct, plain, fixed (#1324) | 32.65% | gap:0.5 | 42,797 (70.28%) | 42,797 | 15,534 (32,522) | 43,593 | 349 (7.6) |

### R04 (100,771 keys; complete start value 23,534.09 c)

Every R04 run with a lead under 100% was stopped at its 50-minute limit (`LIMIT=3000`, one process each, load 6 to 8 during, 4.9 to 7.0 at the end); the row gives where it stood. On R04 the rule `gap:0.5` was the visit rule in every round of the floor and direct runs (the incumbent was never finite) and up to 12,393 keys in the merged run.

| Lower value at tips | Its start value | Rule | Stop | L at 99% | U at 101% | End (no tip on the lower policy) | Seconds (load) |
|---|---|---|---|---|---|---|---|
| exact (reference) | 100% | gap:0.5 | **387** (634) | 1 | 387 (634) | 740 | 22 (7.4) |
| junk counts and tags dropped, `BEST` (reference; not a lower bound a build has) | 100% | gap:0.5 | 458 (698) | 1 | 458 (698) | 814 | 36 (7.5) |
| junk counts and tags dropped, merged (reference) | 8.21% | gap:0.5 | **stopped at** 20,671 keys (20.5%): L 9.88%, U 590,236.79 c (25 times V; first finite after 12,393 keys), L/U 0.39% | not reached | not reached | - | 3,003 (6.3) |
| **the cheapest offer (today)** | 0.00% | gap:0.5 (= mass:0.5) | **stopped at** 23,362 keys (23.2%): L 2.36%, U infinite | not reached | not reached | - | 3,001 (4.9) |
| **direct, `ONE=exact`, fixed (#1324)** | 1.50% | gap:0.5 | **stopped at** 24,696 keys (24.5%): L 2.58%, U infinite | not reached | not reached | - | 3,005 (7.0) |

At equal keys these stand where the lower-led runs stood: #1318's merged run (`mass:0.5`, `led2-R04-tags_counts-mass-0.5.tsv`) was at 9.88% after 20,703 keys; its floor run at 2.36% after 23,362; #1324's fixed direct lead (`dled-R04-static.tsv`, plain rows) at 2.69% after 24,750. That last pair compares two different leads (plain and `ONE=exact` rows), which have the same start value on R04 (352.39 c) and may differ elsewhere; no lower-led run of the `ONE=exact` lead on R04 exists.

## 3. What the table says

- **The incumbent is not what is missing.** On R24, with the direct lead, a plan within 1% of the complete value is in hand after 428 to 892 keys; the lower value reaches 99% only after 38,631 to 60,867. With today's floor, after 35,430 against 45,113. In every run with a lead a build has, and with the merged leads under visit or gap weights, the stop falls on the round where L reaches 99% of the complete value (one exception: the merged lead under `mass:0.5`, where the incumbent arrives 11 keys after L, 17,267 against 17,256). Where L is right from the start (exact, `tags+sum`, `BEST`) or under `oracle` weights, the stop waits for the incumbent (185 to 458 keys; and 46,528 and 38,331 under `oracle`, 987 and 995 keys after L). Since U >= V always, no upper value can make the stop come before L reaches 99% of V **for a given order of the work**: the "within 1%" figures of the led note and the direct note are a floor of the stop of an upper-led build that works the keys in the same order, and on R24 they are its stop. On R04 the floor and direct runs never had an incumbent in 23,362 to 24,696 keys, and the merged one had one at 25 times the value: there the upper side is not even started when the lower side is at 2% to 10%. Another order moves both (the `oracle` rows).
- **The ticket's rule is no lever.** Weighing the tips by the gap instead of visits moves the R24 stops by -211 and +254 keys, -0.35 and +0.42 points of the 60,895 (merged: 17,056 against 17,267; direct: 38,885 against 38,631). While the incumbent is still infinite the gap rule is the visit rule: on R24 the restart incumbent is first finite after 19,177 keys (floor), 231 (direct `ONE=exact`), 270 (direct plain), 9,763 (merged `tags,counts`) and 21,918 (merged 42.17%); on R04 after 12,393 (merged `tags,counts`) and never in the floor and direct runs. With the floor lead the two rules are the same rule (every tip has the same gap per visit). With the true value of each tip as its upper value (`oracle` weights, which read the truth; one order, not a bound on every order) L reaches 99% at 45,541 keys with the floor lead (428 later than under `gap:0.5`) and at 37,336 with the direct lead (1,549 sooner), but the incumbent is then built last (its U is first within 1% at the end of the build), and the stop moves to the end (floor 46,528, direct 38,331). **Prediction, not counted:** a sharper upper stand-in than the restart would move the stop by a few points either way, as `oracle` does; it cannot bring it under the round where L reaches 99% in its own order.
- **What the upper side costs by itself.** With the perfect lead, 189 keys on R24 and 387 on R04 prove 1% with the restart upper, 228 and 634 with none; the build to "no tip" needs 231 and 740. That is the least an upper-led build can need on these dumps; any real lead adds the keys its lower side needs.

## 4. `BEST`'s cousin: is there a sound quantity near it?

The led note found that the least true value inside a coarse key (`BEST`) ends the lower-led build in 804 to 874 keys on R04, and that it is no lower bound a build can compute (it reads the complete values; the fewest-junk member that holds it in 98.6% of the coarse keys is not a lower bound: 889 keys below it, by up to 0.02%). Here, led from above too, `BEST` (28,596 coarse keys) stops after **458 keys** (814 to the end): near the perfect lead's 387.

Sound quantities counted against it, in this note and the two before it:

| Lower value (a build has the first two; the last two need the complete model) | R04 at the start | R04 keys until L reaches 99% of the value (`BEST`: 1; its upper-led stop: 458) |
|---|---|---|
| the cheapest offer (today) | 0.0% | not reached: 2.36% after 23,362 keys (this note, stopped); 4.09% after 44,341 (led note, stopped) |
| the direct coarse model of #1324, fixed or re-solved | 1.50% | not reached: 2.58% after 24,696 keys (this note, fixed, stopped); 3.66% to 4.01% after 22,987 to 43,097 (direct note, stopped) |
| the merged coarse model, fixed (led note; needs the complete model, so not a build's either) | 8.21% | not reached: 12.54% after 48,910 keys (stopped) |
| the merged coarse model, re-solved with worked rows (`worked`, led note; needs the complete model) | 8.21% | 2,257 |

**No sound quantity counted comes near it.** On the same column `BEST` needs 1 key and the perfect lead's upper-led stop needs 387; the nearest counted (`worked`, 2,257 keys until L is at 99%, so at least that many to its stop) uses coarse rows merged from the complete model, which no build has; with rows built directly the same method gains nothing (the direct note). **Prediction, not counted:** a sound quantity near `BEST` needs a sound argument that the fewest-junk member of a coarse key is (nearly) its cheapest, with a stated slack (the dumps show it is false by up to 0.02% on 889 R04 keys), and the value of that member is the exact problem again (its members reach every key, `ledreach.py`). Nothing counted shows such an argument exists.

## 5. What the count does not show

- **The incumbent here is a plan of the bound's model, not the search's plan in the game.** The planner's stop compares its bound with the plan in hand of the search, whose cost is at least the model's value. So, for the same order of the work, its stop comes no earlier than this note's, and only if its plan is within 1% of the model's value: these counts are a floor of the planner's stop in that order, not its stop.
- **One upper stand-in at tips.** The restart plus the incumbent; the guide's route from a key (the ticket's other example) is not in the dumps. The `oracle` weights show one order a sharper stand-in could give, not a bound on all of them; in any order the stop cannot come before L reaches 99%.
- **The direct lead is the fixed one.** Its re-solved forms (the direct note's `RATCHET`, `MAX`, `demand`) were not combined with the upper side. **Prediction:** they would move the stop as they moved "within 1%" there (on R24 by at most a few points), since the stop is set by L.
- **Two dumps, the guide's offers** (21 and 11), not a target's thousands. No figure for R17, R20, R14.
- **Keys counted as equal**; three solves a round in the tool (lower and two incumbents) are this script's cost, not a build's.
- **Rules:** `gap:0.5`, `mass:0.5`, `all`, and `oracle` weights; bounded RTDP's sampled trajectories were not simulated (the rules here work out the tips of the whole lower policy by weight, which is the deterministic form of the same choice).
- **Where the R04 runs would end.** All three R04 runs with a lead under 100% were stopped at 50 minutes; where they end, and where their incumbent would first be finite (floor, direct) is not counted. That they need far more than the 387 keys of the perfect lead is counted. Filed as #1326 (with a plan in hand early, e.g. the guide's route); the other points of this section as #1327; a lower value that reaches 99% far sooner on R24 is #1310's line.

## 6. The tools

`research/cheap-bound/uled.py`, `uled.sh`, `usum.py`; `uled-summary.md` (the table of every run), `uled-results.txt` (every result line). `dled.py` takes a new env `SAVELEAD=PATH` in mode `static`: it saves the fixed direct lead of every exact key and stops before the led build. The per-round files (`u-ROUTE-LEAD-RULE-WEIGHTS.tsv`: keys worked out, L, both incumbents, the policy's gap, its tips and their visits) and the logs stay on the server under `.claude/scratch/t1321/`.
