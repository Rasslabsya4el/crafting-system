# How many keys any proof within 1% needs, and why: the smallest certificate counted on R24, R04 and R13 (research, 2026-11-20)

Ticket #1360. A design note, no planner code. It follows the three counted lines the ticket names: the cheap bound over every offer (`docs/research/2026-11-18-cheap-bound-design.md`, #1310), the build led by a coarse model (`2026-11-18-led-build-count.md`, #1315; `2026-11-18-direct-coarse-lead.md`, #1322) and the build led from above (`2026-11-19-upper-led-build.md`, #1321). Read too: `2026-11-18-rounds-design.md` (#1276), `2026-11-06-376-junk-aware-bound.md`, `2026-11-06-497-walk-free-bound.md`, issues #1315, #1321, #1322, #1325, #1192, #1304, and the handoffs of #1315, #1321, #1322, #1341, #1352.

Rules read: OR-12 (nothing is dropped for being unlikely: every lemma below is exact, and every count says which keys it leaves out and why their value is known), OR-13, OR-37, OR-38 (no proof is claimed from a count), OR-39 (the 1% stop), OR-40.

**Every figure below is a count that was run** on the owner's server on 2026-11-20, one process and one thread a count (load beside the long ones). A sentence that is a prediction says so. The scripts are in `research/proof-size/` (section 9); the dumps and logs stay under `.claude/scratch/t1360/` and `.claude/scratch/t1310/`.

Words, as in the notes before. A **key** is the exact bound's summary of an item; to **work a key out** is to build every offer's row at it; a **tip** is a key not worked out, valued today at the cheapest offer's price (the **floor**: 0.0105 c on R04, 0.0000002 c on R24). `V` is the value of the complete model of a dump (the bound's own figure); `V0` its value at the start key.

## Short answer

- **Under today's bound (a key not worked out valued at the floor), a proof within 1% needs tens of thousands of keys, in whatever order the build works.** A certificate of "every plan costs at least 99% of the bound's value" must work out at least **38,368 of R24's 60,895 keys (63%)**, at least **46,518 of R04's 100,771 keys** (46%; read from its exact merge, where it is 91% of the 51,174 states, section 1), and on R13 at least 1,078 keys (the 1,135-state merge needs 95% of its states; R13's own keys were not counted to the end). These bound every certificate with tips at the floor, so no order of the work, from below or from above, can go under them (section 2); a lead changes the tip value and is counted apart (next point). **The root is the bound's form**: a key not worked out is valued at the cheapest price (the floor), and nearly every key is a draw that went wrong, worth the start's value plus a little (99.7% of R24's keys, 92.9% of R04's, 98.8% of R13's at the reset); with tips at the floor the proof must work each one out to show it is no better.
- **How strong a lead must be.** With every key not worked out valued at a share of its true value, R24's smallest proof is 28,762 keys at 50%, 15,768 at 80%, **8,695 at 90%, 4,428 at 95%, 328 at 98%** (lower bounds; certificates found 30,491, 18,713, 9,851, 5,810, 712). A lead of one share at every key must be worth about 98% of the truth to bring the proof to hundreds. A lead that is near exact only at the failures can do it with less elsewhere: #1315's merged lead re-solved with the worked keys' rows proved R24 in 237 keys, but its merged rows are built over every member, which is the work the build cannot afford (#1322: 54,000 to 64,000 keys built directly).
- **What one fact would do.** If the bound knew, without working a key out, that it is no better than the start (or than the item after an erasing reroll), the proof would be 87 to 94 keys on R24, 328 to 380 on R13, 6,072 to 6,488 on R04. No exact lemma for that is known (#1363).
- **Proposal A (exact):** on R04, the keys that cannot reach the goal without the restart (82,986 of 100,771) given their exact value without working out: the smallest proof falls from at least 46,518 keys to **16,056 to 17,203 keys**. The lemma's own test names 66,572 of the 82,986, so with it alone the figure is larger and not counted. On R24 and R13 it does nothing (no such key). Filed as #1367.
- **So today the only known road to a 1% proof is the complete build made cheap and parallel** (#1335 to #1358, #1340), with Proposal A on R04 beside it (section 7).

## 1. What was counted: the smallest certificate, whatever the build does

The three counted lines all asked how many keys a build works out in some **order** before its bound reaches 1%. This note asks the question under all of them: **how few keys can any proof of "every plan costs at least 99% of V0" work out**, whatever the order, the lead or the rule. If that number is already tens of thousands, no order, lead or rule can help, and the form of the bound is the root.

**A certificate** is a set `S` of keys worked out and a value `W` on them with `W(k) <= c_a + sum_s P_a(s) W(s)` for **every** row `a` at every `k` in `S`, a tip `s` counting at its lead `h(s)`, and `W(start) >= 0.99 V0`. Every such `W` is at most the value of the model with `S` worked out and tips at `h` (which is the build's own soundness argument), so it proves the 1%. A smaller lead can only need a larger `S`.

**The count is a linear program** (`cert.py`). The floor is *consistent*: `h(k) <= c_a + sum P h(s)` at every row, since every price is at least the floor and a goal is worth 0. For a consistent lead, writing `W = h + u` with `u >= 0` and imposing the rows at **every** key loses nothing (at a tip `u = 0` and the row holds by consistency). So

    minimize  sum_k u_k / (V_k - h_k)   subject to   u_k - sum_s P_a(s) u_s <= c_a + sum_s P_a(s) h_s - h_k  (every row),   u_start >= 0.99 V0 - h_start,   0 <= u_k <= V_k - h_k

has an optimum **at most `|S|` for every certificate `S`** (each term is at most 1 on `S` and 0 off it): it is a **lower bound on the size of the smallest certificate**. (A certificate's `W` can be taken at least `h`, since `max(W, h)` keeps every row by consistency, and at most `V`, since `W` is under the model's value; so it is a point of the program.)

**A key certificate is never smaller than a certificate of the exact merge.** If `S` and `W` are a certificate of the keys, give each merged state `B` that meets `S` the value `max` of `W` over `B ∩ S`, and every other state the floor. At the key `k` where the maximum is reached, `W(k) <= c_a + sum_s P_a(s) W(s) <= c_a + sum_B' P_a(B') W'(B')` for every row, and the merged state has the same rows by price and by their mass on the merged states (that is what the merge keeps); so `W'` is a certificate of the merged model with at most `|S|` states worked out. So the merged program's lower bound is a lower bound for the keys too. It is used below where the program on the keys did not end (R04, R13). The keys where its solution (reweighted once to three times) is positive are a certificate themselves: an **upper bound**. The program is solved by HiGHS (scipy 1.16) on the dump's rows, each shared kernel once.

`alpha` leads: `h = max(alpha V, floor)` is consistent for `alpha <= 1` (V is a fixed point), so the same program counts how good a lead at every key must be for a small proof.

The dumps: R24 (`k-R24.pkl`, #1310: 10 offers and the restart, 60,904 keys, `V0` 3,617.64 c), R04 (`k-R04.pkl`: 20 offers and the restart, 100,773 keys, 23,534.09 c), and, new here, R13 (`k-R13.pkl`, dumped here by `kd2.py`: the first complete bound of R13's natural run with at least 1,000 keys, 72 offers with the restart, 78,654 keys, 156,935 kernels, `V0` 28,164.02 c, built in 1,167 s at load 4 to 10; its kernels are the approximate ones of the run, error 3.2e-7, the missing mass going to the sink). R14 and R20 have no complete dump (#1310: R20's stops; R14's was never made), and none was made here.

## 2. Question 3: the smallest proof

### Under the present bound (tips at the floor)

| Route | Keys to work out (complete build) | Plan's path | Gap | Smallest certificate: at least (LP) | A certificate found (support) |
|---|---|---|---|---|---|
| R24 | 60,895 | 191 | 1% | **38,368 (63.0%)** | 39,343 |
| R24 | | | 5% | 36,106 (59.3%) | 38,816 |
| R24 | | | 10% | 33,590 (55.2%) | 38,184 |
| R04 | 100,771 | 679 | 1% | **at least 46,518 (46%)**, read from its merge; on its keys directly not obtained (the program did not end: simplex 90 to 100 min, interior point over 2 h 10 min, one process at load 7 to 9); on R04's exact merge: **at least 46,518 of 51,174 states (91%), found 49,624** | |
| R13 | 78,651 | 442 | 1% | at least 1,078, read from its merge; on its keys directly not obtained (the program did not end: simplex 90 to 100 min, interior point over 2 h 10 min, one process at load 7 to 9); on R13's exact merge: at least 1,078 of 1,135 states, found 1,105 | |

**So the bound's form is the root.** On R24 no proof of 1% with tips at the floor can work out fewer than 38,368 keys, in whatever order, from below or from above; #1321's upper-led build stopped at 45,113 with the floor. Builds with another tip value are not bound by this figure, and the counted ones are not far from it: #1321's direct lead 38,885, #1322's best direct-led build 37,864. Ten times the slack (10%) removes an eighth of it. The 197 keys of the plan are not the size of its proof.

### With a better lead at every tip (`h = alpha V`, R24, 1%)

| Lead at every tip, share of its true value | 0 (floor) | 50% | 80% | 90% | 95% | 98% | 100% |
|---|---|---|---|---|---|---|---|
| Smallest certificate: at least | 38,368 | 28,762 | 15,768 | 8,695 | 4,428 | **328** | 1 |
| A certificate found | 39,343 | 30,491 | 18,713 | 9,851 | 5,810 | 712 | 1 |

This is #1315's "no middle" stated for every build at once: a lead must be worth about 98% of the truth **at every key** before the proof falls to hundreds. #1315 to #1322 counted leads of 1.5% to 86% (direct and merged coarse models); none is near.

### Why: almost every key is a failure, and a failure is worth the start

| Route | Keys | Worth at least `V0` (no better than the start) | of them: worth exactly `V0` + the restart | Rows within 1% of the best row at such keys |
|---|---|---|---|---|
| R24 | 60,895 | **60,727 (99.7%)** | 0 | Annulment, the Veiled Chaos Orb, the picks: nearly every row (`out/q2-R24.log`) |
| R04 | 100,771 | **93,566 (92.9%)** | 85,438 | every offer but the locks: e.g. Chaos Orb 116,097 of 116,416 rows, Scouring 100,458 of 100,770 |
| R13 | 78,651 | 1 (the start: a bought listing, its price sunk, so every other key is a little cheaper); **77,719 (98.8%)** at or above the reset value, not counting the start and the anchor key itself, (28,163.95 c, the most common value) | 0; Harvest Reforge Fire is the best row at 77,514 | Harvest Reforge Fire within 1% at 77,514 of 78,440 rows, Scouring at 77,720 of 78,649, Annulment at 78,353 of 78,647 (`out/q2-R13.log`) |

A key the plan does not want is, nearly always, an item that went wrong: its best move is to start again (R04: the restart at 85,438 keys) or to reroll back to an item like the start (R24: V - V0 is 0, 12.73 or 19.10 c at every such key, the price of one pick, Annulment or essence). Its value is `V0` plus a little, and every row there is within 1% of every other. A certificate must show, at every such key it reaches, that **no** row leads somewhere cheap; with the tips at the floor, a row that reaches a tip with any weight leads somewhere worth nothing, so the proof must reach on, and the reach of an erasing reroll is thousands of keys. That is the whole size of the certificate, on both routes.

**What one fact would remove it.** Give each key with `V >= V0` one row to the start at no cost and no other row, and no work (`FREE=oracle`: the most that any lemma "this key is no better than the start" could give; it reads the truth): the smallest certificate on R24 is then **87 to 94 keys**, on R04 **6,072 to 6,488 keys** (R04 has 7,205 keys worth less than the start, and a proof must still work those out), on R13 **328 to 380 keys** (R13's start is a bought listing, so the free row goes to the key of the most common value, the item after an erasing reroll: `FREE=mode`, 77,719 free keys). The proof is small exactly when the bound knows, without working them out, that the failures are failures.

## 3. Question 1: where the keys come from

**By parts, against the plan's path** (`q1.py`). Each key is put beside the keys of the cheapest plan's path, and classed by the fewest parts in which it differs from one of them:

| Route | Keys | On the path | Differs only in junk (counts, tags) | In slots too (crafted, held, veiled) | In the status too | In a fractured mod |
|---|---|---|---|---|---|---|
| R24, all keys | 60,895 | 191 | **26 (0.04%)** | 12,194 (20.0%) | 48,484 (79.6%) | 0 |
| R24, the certificate of 39,343 | 39,343 | 179 | 26 | 5,272 (13.4%) | 33,866 (86.1%) | 0 |
| R04, all keys | 100,771 | 679 | **202 (0.2%)** | 11,011 (10.9%) | 18,051 (17.9%) | 70,828 (70.3%) |
| R13, all keys | 78,651 | 442 | **34 (0.04%)** | 15,904 (20.2%) | 26,266 (33.4%) | 36,005 (45.8%, a fractured mod or the flags) |

So **the keys do not come from junk beside the plan's items.** The ticket's guess (junk count, side, tags) holds for 26 and 202 keys. They come from **other outcomes**: other wanted mods at other tiers (the status), other unveiled offers and crafted slots, and, on R04, a wrong mod fractured (70% of the keys). Each is a draw that went wrong, and section 2 says the proof needs most of them, because it must show each is a failure.

**What an exact merge could remove** (`bisim.py`). The coarsest merge of keys that keeps every row (probabilistic bisimulation, rows compared by price and by their distribution over the merged keys) is the least number of states any exact model of these offers can have. It is counted on the dump, so it reads the rows; it says how far an exact lemma could go, not which lemma.

| Route | Keys | Merged states (bisimulation) | Distinct values | Certificate on the merged model (floor, 1%) | What differs inside a merged state |
|---|---|---|---|---|---|
| R24 | 60,904 | **940** | 28 | at least 774, found 838 | the status in 603 of 780 merged states (leaves 3 and 4 between below and passing, leaves 5 and 6), the held offer in 285, the veiled slots in 267, junk counts and tags in 151 |
| R04 | 100,773 | 51,174 | 389 | at least 46,518, found 49,624 | the status in 31,252 of 31,256 (leaves 3 and 4, below and passing, in 18,536), the fractured mod in 4,306, tags in 409 |
| R13 | 78,654 | **1,135** | 24 | at least 1,078, found 1,105 | not counted |

On R24 the exact model has 65 times more keys than it needs; on R04, 2 times. **Which lemma would give R24's 940 is not found.** One candidate, that leaves 3 and 4 (and 5 and 6) are interchangeable, is counted and is **not** exact: under that swap 137 of R24's classes and 329 of R04's hold keys of different values (`swap.py`).

**Which part the proof truly needs.** Of what multiplies the keys, the proof needs every distinction that changes a value (the 940 and 51,174 merged states), and needs the values of the failures; what it does not need is their **separate working out** when a lemma gives their value (section 2: 87 to 94 keys on R24).

## 4. Question 2: where the offers come from

Counted on the dumps' offers (21, 11 and 72); R04's 1,245 offers and R14's 10,907 have **no complete dump** (R04's 1,245-offer model is #1352's: 625,773 keys at model 6; it stops on the 12 GB net at model 24, #1366), so their counts are **not made**.

| Route | Offers | The best row at some key | The best row at a key of the plan's path |
|---|---|---|---|
| R24 | 11 | 9 (not Alteration, which has no row; not the restart) | 8 |
| R04 | 21 | 16 | 11 |
| R13 | 72 | 9 (Harvest Reforge Fire at 77,514 keys; Remove Crafted Mods 795; Scouring 206; Annulment 122; three bench crafts; Alchemy; the listing) | 8 |

**Exact dominance before the build.** Two offers can be compared without the build only where their rows can: equal kernels (the twins, already lumped, `_offer_kinds.py`), or a kernel that is the other's with mass moved onto keys known to be no cheaper. One such fact is exact and free: **the restart is a row at every key, so `V(k) <= c_r + V0` everywhere, and a ruined key (section 5) is worth exactly `c_r + V0`, the most any key is worth.** So if offer B costs no more than A and, at a context (the flags, fractured mods and crafted slots an erasing offer's outcome depends on, ADR-0023), B's chance of each key that is not ruined is at least A's, then B is never worse than A at any key of that context: A can be left out there, exactly. **Not counted**: it needs the fossil sets' kernels at R04's contexts, which only the 1,245-offer build makes. Beyond this, a dominance between two fossil sets needs an order of keys that every value respects, and none is known: more junk is not always worse (a full side steers a slam), so "fewer junk mods" is no such order.

What the counts do say about offers: at a failure key every row is within 1% of the best (section 2's table), so no rule that leaves an offer out where it is "far from the best" can apply at 1% there. The offers are not where the proof's size comes from; the failures are.

## 5. Question 4: proposals

### Proposal A: the ruined keys are one state, valued without working out (exact)

**The lemma.** A fractured mod is never removed (no action of the game removes one), and a corrupted item takes no further action but those the abstraction lists for it. If a key's permanent mods leave no assignment of the target's necessary leaves to free slots (a fractured mod that gives no leaf takes a slot of a side the target fills; a fractured mod below the leaf's tier takes the leaf's group), for **every** set of leaves that satisfies the target (a target with alternative leaves is ruined only when each alternative is blocked), then **no plan from it reaches the goal without a row that replaces the item** (the restart, or any other row that starts from a new base, each counted at its own price), and its value is **exactly the cheapest such row's price plus the value of the item it starts from** (in the dumps the restart is the only such row, so `c_r + V(start)`): any plan from it takes one such row at some time, paying at least that and then at least the new item's value; taking it at once costs exactly that. Nothing is cut (OR-12): the key keeps its exact value, it is only not worked out. The build values such a key by its restart row alone and offers none of its other rows; a kernel's mass onto ruined keys goes to one state.

**Its size, counted.** R04: every key with a fractured mod that gives no leaf (66,572, 66% of the keys; counted by the first agent of this ticket in a command whose script was not kept, so this figure is not reproduced by the tools of section 9) is worth exactly `V0 + c_r` in the complete model; the keys from which no goal is reachable without the restart in the model's own graph are 82,986 (82%). With those 82,986 keys given their value by the restart row alone, the smallest certificate on R04 is **at least 16,056 keys, found 17,203** (`out/i-R04-ruin.log`, HiGHS interior point, 1,282 s); without A at least 46,518 (read from R04's exact merge, section 1; the program on the keys themselves did not end). The lemma's own test (a fractured mod that gives no leaf) finds 66,572 of them; the other 16,414 are dead in the model's graph for other reasons (a fractured mod of a wrong tier, a full side), and whether the lemma's test reaches them is not counted. A certificate with fewer keys valued free can only be larger, so with the lemma's 66,572 the figure is at least the one above. R24: **0 ruined keys** (its start's fractured mod is wanted, and no offer fractures), so A does nothing there. R13: **0 ruined keys** (no offer of its dump fractures), so A does nothing there.

**What it costs.** A test per key found, of the fractured mods against the target's leaves and sides: no row, no kernel, no member. It is cheaper than one offer at one member.

**The first PR.** `abstraction/_pattern.py` (the key's ruin test beside `PatternKey`, one state for every ruined key, its restart row only; the lemma in the module text beside "The imprints") and `planner/_pattern_bound.py` (the ruined state in the packed model); tests: the hand-worked bow with a Fracturing Orb, the model with and without the ruined state equal key by key in value (counted in states), and a ruined key never worked out. Measured end to end on R04 (the 1,245-offer bound of #1352: keys of model 6 before and after, first plan, bound against the plan) and on R24 (which it must not change: 0 ruined keys). **Prediction, not counted:** most of R04's 625,773 keys of model 6 are ruined, as 82% of the 21-offer model's are, since the Fracturing Orb is in both.

### Proposal B: the failures valued by the start (open: the lemma is not found)

The count of section 2 says what is missing on R24: a way to know that a key is no better than the start without working it out. An exact lemma of that kind is a **dominance between keys**: `V(k) >= V(j)` for a key `j` already worked out (the start, or any key whose value the proof holds), proved from the two keys alone. Then the tip `k` takes one row to `j` at no cost, which is sound by the same argument as a lead (the model with that row is under the true one). With the truth as the dominance (`FREE=oracle`) it gives 87 to 94 keys on R24. **No such lemma is known**, and the obvious ones are false or unproved: "more junk is no better" fails (a full side steers a slam); "a key with fewer wanted leaves passing is no better" is not proved, and its nearest exact form, swapping leaves 3 and 4 (and 5 and 6), is false (137 classes of R24 with keys of different values). A simulation computed on the model would prove it, but it needs the rows of the keys it compares, which is the work it would save.

So B is not proposed for building. It is the open question this note leaves: **a structural dominance of keys that holds on the failures of R24.** Filed as #1363 (research, no planner code).

### Not proposed, and why each is not one of the three counted lines

- **The cheap bound over every offer (#1310)** is a lead from a coarser key; section 2's `alpha` table shows that any lead under about 98% at every key leaves a proof of thousands to tens of thousands of keys on R24, so no coarse model can be the answer unless it is near exact, which #1310's merged models (8.2% and 86.5%) and #1315's direct ones (1.5% to 54%) are not. Proposal A is not a lead: it gives the ruined keys their exact value.
- **The led build (#1315, #1322)** and **the lead from above (#1321)** choose an order of the work; section 2 bounds every order at once: at least 38,368 keys on R24. Proposal A changes the model (fewer states, exactly), not the order.
- **The exact merge (bisimulation)** is a limit, not a design, until a lemma names the merged keys; #1317 (the type of a fractured junk mod) is one such lemma on R04 (41,847 to 60,901 keys at the same value), and Proposal A subsumes it on R04 (a key with a fractured junk mod is ruined there).

## 6. Question 5: what stays impossible

**Impossible under today's bound: a proof of hundreds of keys.** On R24 every exact 1% proof with tips at the floor works out at least 38,368 keys (63% of the complete model), at 10% still 33,590; on R04 at least 46,518 keys and on R13 at least 1,078 (both read from their exact merges, section 1). No order of the work can go under these, since they are counts over every certificate with tips at the floor; a lead changes the bound and needs, as one share at every key, about 98% of the truth (section 2).

**Not shown impossible, not shown possible: a proof within the server's memory.** R04's model 6 of 625,773 keys holds 7.6 GB (#1341) and now passes in 2 minutes (#1358), but round 1's bound then grows to model 23 (625,870 keys, 1,309 of 6,164 offers, binding offers asked at up to 203,928 keys) and stops on the 12 GB net at model 24, its first plan's chain cut at 12.3 GB (#1366). R13's 78,654-key bound holds 3 to 5 GB (#1332). R24's bound has not ended (#1329). So R04's wall is now memory at 12 GB; whether more of the server's 60 GB, or Proposal A's smaller model, lets it end is not measured. R14 and R17 have no complete bound or dump, so nothing about them is counted here; for them neither "possible" nor "impossible" is shown.


## 7. What this means for the work (for the dispatcher and the owner)

**(a) Is the complete build, made cheap and parallel, the only known road to a 1% proof today? Yes.** Section 2 bounds every order of the work at once: with tips at the floor any 1% proof works out at least 38,368 of R24's 60,895 keys, 46,518 of R04's 100,771, and 1,078 of R13's (R13's figure read from its merge, whose 1,135 states it nearly fills). A lead of one share at every key must be worth 98% of the truth before the proof falls to hundreds; the leads counted are worth 1.5% to 86% (#1310, #1315, #1322), and the one near-exact lead counted (#1315's re-solved merged lead, 237 keys on R24) needs merged rows built over every member, which is again the complete work. Proposal A shrinks R04 only. So a proof today means building nearly the whole bound, and the line of #1335 to #1358 (memory, shared kernels, the fossil outcomes, the cores of #1340) is the critical path, not a detour. Its cost, from the measurements of #1325, #1329, #1341, #1352 and #1358 (none rebuilt here):

| Route | Offers of the default methods | The bound as far as it was built | Offers at a key | Time measured (server, load 2 to 7) | Proof within 1% |
|---|---|---|---|---|---|
| R04 | about 6,100 (1,245 join round 1's bound) | round 1, model 6: **625,773 keys, 1,439,271 kernels**, 7.6 GB (#1341) | about 73 at most keys; 1,245 at 36 keys (#1358) | models 1 to 5 about 80 minutes (#1341); model 6's pass 2 minutes after #1358, models 7 to 23 21 minutes (#1366) | not reached: round 1's bound stops on the 12 GB net at model 24 (625,870 keys, 1,309 offers) and its first plan is cut at 12.3 GB (#1366) |
| R24 | 4,105 (2,831 join) | model 52 after #1325: 21,483 keys and still growing past 50 minutes; 7 offers built at 21,444 keys in one round, about 9 ms a key and offer (#1329) | 21 in the start's class at most keys; 2,831 at the 39 keys that need them (#1325) | stopped by hand at 50 minutes, bound not ended | not reached: no plan |
| R13 | 172 to 190 in its later rounds' bounds (#1332, #1338) | first complete bound: **78,654 keys, 156,935 kernels, 72 offers**, 1,167 s (this note's dump); later: the 190-offer bound of 44,637 keys and the 172-offer bound of 78,654 keys (#1332, #1338) | 72, then up to 190 | first bound 14 to 22 minutes; runs of 120 and 189 minutes spent 46 to 61% of their time in the bound's build and 31 to 37% in the search (#1340) | a plan of 28,206.73 c; a proof within 1% over every offer not shown |

In keys times offers: R04 is about 46 million key-offer pairs if every key of model 6 holds the 73 offers that model 6's pass gives (a prediction from #1358's count, not a measurement), R13's first bound 5.7 million (78,654 keys by 72 offers), R24 not known because its bound has not ended. These are what a complete proof costs on today's bound; the counts of section 2 say no proof of the same bound can cost less than about two thirds of them.

**(b) What Proposal A saves.** On R04: the smallest certificate falls to at least 16,056 keys (one found of 17,203) (16% of its keys, against at least 46,518 without A), because 82,986 of its 100,771 keys need no working out. In the complete 1,245-offer model of round 1 (625,773 keys) the share of ruined keys is not counted; if it is near the 82% of the 21-offer dump (a prediction), model 6 would shrink about five times. On R24 and R13 it does nothing: neither dump has a ruined key (R24's fractured mod is wanted, R13's offers fracture nothing).

**(c) What a new bound would need for hundreds of keys to be enough.** One of two things, each counted on R24: a value at every key not worked out that is at least 98% of its true value (328 keys at 98%, 4,428 at 95%, 8,695 at 90%), or a proof, from the key alone, that it is no better than the start or than the item after an erasing reroll (87 to 94 keys on R24, 328 to 380 on R13, 6,072 to 6,488 on R04). What counted suggests such a bound may exist: the exact merge of R24's 60,904 keys has only 940 states and 28 distinct values, R13's 78,654 keys 1,135 states and 24 values, and 98.8% of R13's keys sit at one value (the reset); a rule that names those states before the build would also make the complete build itself 940 and 1,135 states. What counts against: the obvious rules are false (leaves 3 and 4 swapped is not exact, more junk is not always worse), and on R04 the merge keeps 51,174 states. So it is suggested, not shown; #1363 looks for it.

## 8. Recommendation

1. **Keep the complete build cheap and parallel as the critical path** (#1340 the cores, #1358 R04's model 6, #1329 R24's growth). It is the only known road to a 1% proof on R24 and R13, and section 2 shows no build order or lead of today's bound avoids it.
2. **Build Proposal A first, on R04**: #1367. It is exact (OR-12), cheap (a test of fractured mods against the target, no row), and cuts R04's smallest proof to 16,056 to 17,203 keys (16% of its keys, against at least 46,518 without A). It does nothing on R24 and R13, and its PR must show they are unchanged.
3. **Research the missing lemma** (#1363): a structural "no better than the start" between keys. It is the only counted way to proofs of hundreds of keys (87 to 94 on R24); nothing counted says it exists, but the exact merges (940 states on R24, 1,135 on R13, two dozen values each) suggest the structure is there.
4. Not recommended: any further lead or order of the build (#1310, #1315, #1321, #1322 lines). Section 2 bounds them all.

## 9. The tools

`research/proof-size/`: `kd2.py` (kd.py of #1310 with the lead optional and the first complete bound of at least `MINKEYS` keys dumped), `dump.sh`, `export.py` (a dump into arrays and the complete values by the planner's solver; its start value equals the dump's to the last digit on R24 and R04), `cert.py` (the certificate's program; `FREE=oracle|ruin`; `alpha:` leads; `REWEIGHT`), `sweep.sh`, `bisim.py`, `quot.py` (the merged model, its values equal to the dump's: largest spread 0.0), `blocks.py`, `sdiff.py`, `swap.py`, `q1.py`, `q2.py`, `anaF.py`, `r13.sh`, and the outputs (`out/*.log`). The dumps and per-run logs stay on the server under `.claude/scratch/t1360/` and `.claude/scratch/t1310/`.

## Not done, not verified

- Filed as #1368: R14, R17 and R20: no complete dump, no count (R20's dump stops, #1310; R14's was never made). R04's 1,245 offers and R14's 10,907 are not counted (section 4): their dumps would need the complete 1,245-offer build.
- The exact dominance between offers of section 4 is stated, not counted (#1368).
- The certificates "found" are the supports of the program's solutions, certificates up to the solver's tolerance (1e-7 of a key's span); none was solved again exactly on its keys.
- Proposal A's lemma test (66,572 keys on R04) is narrower than the graph count used for its certificate (82,986); its certificate with the lemma's keys alone is not counted. Its size on R04's complete 625,773-key model is a prediction.
- The cost of a complete proof in section 7 is read from earlier handoffs, not measured again; R04's 46 million key-offer pairs is a prediction.
- R13's dump has approximate kernels (error 3.2e-7, the missing mass to the sink), as the run's own bound has.
- The floor certificate on R04's and R13's own keys (not merged): not obtained. Simplex did not end in 90 to 100 minutes, interior point not in 2 h 10 min (left running to their 4 h cap, logs `.claude/scratch/t1360/i-R04-floor.log`, `i-R13-floor.log`). Their merged models are counted instead, and section 1 shows a certificate of the keys is never smaller than one of the merged states, so the merged lower bounds hold for the keys; the upper side (a certificate of the keys found) is not known for R04 and R13 without A.
