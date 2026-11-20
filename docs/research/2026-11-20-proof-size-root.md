# How many keys any proof within 1% needs, and why: the smallest certificate counted on R24, R04 and R13 (research, 2026-11-20)

Ticket #1360. A design note, no planner code. It follows the three counted lines the ticket names: the cheap bound over every offer (`docs/research/2026-11-18-cheap-bound-design.md`, #1310), the build led by a coarse model (`2026-11-18-led-build-count.md`, #1315; `2026-11-18-direct-coarse-lead.md`, #1322) and the build led from above (`2026-11-19-upper-led-build.md`, #1321). Read too: `2026-11-18-rounds-design.md` (#1276), `2026-11-06-376-junk-aware-bound.md`, `2026-11-06-497-walk-free-bound.md`, issues #1315, #1321, #1322, #1325, #1192, #1304, and the handoffs of #1315, #1321, #1322, #1341, #1352.

Rules read: OR-12 (nothing is dropped for being unlikely: every lemma below is exact, and every count says which keys it leaves out and why their value is known), OR-13, OR-37, OR-38 (no proof is claimed from a count), OR-39 (the 1% stop), OR-40.

**Every figure below is a count that was run** on the owner's server on 2026-11-20, one process and one thread a count (load beside the long ones). A sentence that is a prediction says so. The scripts are in `research/proof-size/` (section 8); the dumps and logs stay under `.claude/scratch/t1360/` and `.claude/scratch/t1310/`.

Words, as in the notes before. A **key** is the exact bound's summary of an item; to **work a key out** is to build every offer's row at it; a **tip** is a key not worked out, valued today at the cheapest offer's price (the **floor**: 0.0105 c on R04, 0.0000002 c on R24). `V` is the value of the complete model of a dump (the bound's own figure); `V0` its value at the start key.

## Short answer

{SHORT}

## 1. What was counted: the smallest certificate, whatever the build does

The three counted lines all asked how many keys a build works out in some **order** before its bound reaches 1%. This note asks the question under all of them: **how few keys can any proof of "every plan costs at least 99% of V0" work out**, whatever the order, the lead or the rule. If that number is already tens of thousands, no order, lead or rule can help, and the form of the bound is the root.

**A certificate** is a set `S` of keys worked out and a value `W` on them with `W(k) <= c_a + sum_s P_a(s) W(s)` for **every** row `a` at every `k` in `S`, a tip `s` counting at its lead `h(s)`, and `W(start) >= 0.99 V0`. Every such `W` is at most the value of the model with `S` worked out and tips at `h` (which is the build's own soundness argument), so it proves the 1%. A smaller lead can only need a larger `S`.

**The count is a linear program** (`cert.py`). The floor is *consistent*: `h(k) <= c_a + sum P h(s)` at every row, since every price is at least the floor and a goal is worth 0. For a consistent lead, writing `W = h + u` with `u >= 0` and imposing the rows at **every** key loses nothing (at a tip `u = 0` and the row holds by consistency). So

    minimize  sum_k u_k / (V_k - h_k)   subject to   u_k - sum_s P_a(s) u_s <= c_a + sum_s P_a(s) h_s - h_k  (every row),   u_start >= 0.99 V0 - h_start,   0 <= u_k <= V_k - h_k

has an optimum **at most `|S|` for every certificate `S`** (each term is at most 1 on `S` and 0 off it): it is a **lower bound on the size of the smallest certificate**. The keys where its solution (reweighted once to three times) is positive are a certificate themselves: an **upper bound**. The program is solved by HiGHS (scipy 1.16) on the dump's rows, each shared kernel once.

`alpha` leads: `h = max(alpha V, floor)` is consistent for `alpha <= 1` (V is a fixed point), so the same program counts how good a lead at every key must be for a small proof.

The dumps: R24 (`k-R24.pkl`, #1310: 10 offers and the restart, 60,904 keys, `V0` 3,617.64 c), R04 (`k-R04.pkl`: 20 offers and the restart, 100,773 keys, 23,534.09 c), and, new here, R13 ({R13_DUMP}). R14 and R20 have no complete dump (#1310: R20's stops; R14's was never made), and none was made here.

## 2. Question 3: the smallest proof

### Under the present bound (tips at the floor)

| Route | Keys to work out (complete build) | Plan's path | Gap | Smallest certificate: at least (LP) | A certificate found (support) |
|---|---|---|---|---|---|
| R24 | 60,895 | 191 | 1% | **38,368 (63.0%)** | 39,343 |
| R24 | | | 5% | 36,106 (59.3%) | 38,816 |
| R24 | | | 10% | 33,590 (55.2%) | 38,184 |
| R04 | 100,771 | 679 | 1% | {R04_FLOOR} |
| R13 | {R13_N} | {R13_PATH} | 1% | {R13_FLOOR} |

**So the bound's form is the root.** On R24 no proof of 1% under today's tip value can work out fewer than 38,368 keys, whatever leads it, in what order, from below or from above; #1321's upper-led build stopped at 45,113 (floor) and 38,885 (direct lead), #1322's best direct-led build at 37,864: they were already near this floor. Ten times the slack (10%) removes an eighth of it. The 197 keys of the plan are not the size of its proof.

### With a better lead at every tip (`h = alpha V`, R24, 1%)

| Lead at every tip, share of its true value | 0 (floor) | 50% | 80% | 90% | 95% | 98% | 100% |
|---|---|---|---|---|---|---|---|
| Smallest certificate: at least | 38,368 | 28,762 | 15,768 | 8,695 | 4,428 | **328** | 1 |
| A certificate found | 39,343 | 30,491 | 18,713 | 9,851 | 5,810 | 712 | 1 |

This is #1315's "no middle" stated for every build at once: a lead must be worth about 98% of the truth **at every key** before the proof falls to hundreds. #1315 to #1322 counted leads of 1.5% to 86% (direct and merged coarse models); none is near.

### Why: almost every key is a failure, and a failure is worth the start

| Route | Keys | Worth at least `V0` (no better than the start) | of them: worth exactly `V0` + the restart | Rows within 1% of the best row at such keys |
|---|---|---|---|---|
| R24 | 60,895 | **60,727 (99.7%)** | 0 | Annulment, the Veiled Chaos Orb, the picks: nearly every row (`q2-R24.txt`) |
| R04 | 100,771 | **93,566 (92.9%)** | 85,438 | every offer but the locks: e.g. Chaos Orb 116,097 of 116,416 rows, Scouring 100,458 of 100,770 |
| R13 | {R13_N} | {R13_F} | {R13_FR} | {R13_NEAR} |

A key the plan does not want is, nearly always, an item that went wrong: its best move is to start again (R04: the restart at 85,438 keys) or to reroll back to an item like the start (R24: V - V0 is 0, 12.73 or 19.10 c at every such key, the price of one pick, Annulment or essence). Its value is `V0` plus a little, and every row there is within 1% of every other. A certificate must show, at every such key it reaches, that **no** row leads somewhere cheap; with the tips at the floor, a row that reaches a tip with any weight leads somewhere worth nothing, so the proof must reach on, and the reach of an erasing reroll is thousands of keys. That is the whole size of the certificate, on both routes.

**What one fact would remove it.** Give each key with `V >= V0` one row to the start at no cost and no other row, and no work (`FREE=oracle`: the most that any lemma "this key is no better than the start" could give; it reads the truth): the smallest certificate on R24 is then **87 to 94 keys**, on R04 {R04_ORACLE}, on R13 {R13_ORACLE}. The proof is small exactly when the bound knows, without working them out, that the failures are failures.

## 3. Question 1: where the keys come from

**By parts, against the plan's path** (`q1.py`). Each key is put beside the keys of the cheapest plan's path, and classed by the fewest parts in which it differs from one of them:

| Route | Keys | On the path | Differs only in junk (counts, tags) | In slots too (crafted, held, veiled) | In the status too | In a fractured mod |
|---|---|---|---|---|---|---|
| R24, all keys | 60,895 | 191 | **26 (0.04%)** | 12,194 (20.0%) | 48,484 (79.6%) | 0 |
| R24, the certificate of 39,343 | 39,343 | 179 | 26 | 5,272 (13.4%) | 33,866 (86.1%) | 0 |
| R04, all keys | 100,771 | 679 | **202 (0.2%)** | 11,011 (10.9%) | 18,051 (17.9%) | 70,828 (70.3%) |
| R13, all keys | {R13_N} | {R13_PATH} | {R13_Q1} |

So **the keys do not come from junk beside the plan's items.** The ticket's guess (junk count, side, tags) holds for 26 and 202 keys. They come from **other outcomes**: other wanted mods at other tiers (the status), other unveiled offers and crafted slots, and, on R04, a wrong mod fractured (70% of the keys). Each is a draw that went wrong, and section 2 says the proof needs most of them, because it must show each is a failure.

**What an exact merge could remove** (`bisim.py`). The coarsest merge of keys that keeps every row (probabilistic bisimulation, rows compared by price and by their distribution over the merged keys) is the least number of states any exact model of these offers can have. It is counted on the dump, so it reads the rows; it says how far an exact lemma could go, not which lemma.

| Route | Keys | Merged states (bisimulation) | Distinct values | Certificate on the merged model (floor, 1%) | What differs inside a merged state |
|---|---|---|---|---|---|
| R24 | 60,904 | **940** | 28 | at least 774, found 838 | the status in 603 of 780 merged states (leaves 3 and 4 between below and passing, leaves 5 and 6), the held offer in 285, the veiled slots in 267, junk counts and tags in 151 |
| R04 | 100,773 | 51,174 | 389 | {R04_Q} | the status in 31,252 of 31,256 (leaves 3 and 4, below and passing, in 18,536), the fractured mod in 4,306, tags in 409 |
| R13 | {R13_N} | {R13_BISIM} | {R13_VALS} | {R13_QCERT} | |

On R24 the exact model has 65 times more keys than it needs; on R04, 2 times. **Which lemma would give R24's 940 is not found.** One candidate, that leaves 3 and 4 (and 5 and 6) are interchangeable, is counted and is **not** exact: under that swap 137 of R24's classes and 329 of R04's hold keys of different values (`swap.py`).

**Which part the proof truly needs.** Of what multiplies the keys, the proof needs every distinction that changes a value (the 940 and 51,174 merged states), and needs the values of the failures; what it does not need is their **separate working out** when a lemma gives their value (section 2: 87 to 94 keys on R24).

## 4. Question 2: where the offers come from

Counted on the dumps' offers (21, 11 and {R13_OFFERS}); R04's 1,245 offers and R14's 10,907 have **no complete dump** (R04's 1,245-offer model is #1352's: 625,773 keys, about 34 hours at model 6, #1358), so their counts are **not made**.

| Route | Offers | The best row at some key | The best row at a key of the plan's path |
|---|---|---|---|
| R24 | 11 | 9 (not Alteration, which has no row; not the restart) | 8 |
| R04 | 21 | 16 | 11 |
| R13 | {R13_OFFERS} | {R13_ARG} | {R13_ARGP} |

**Exact dominance before the build.** Two offers can be compared without the build only where their rows can: equal kernels (the twins, already lumped, `_offer_kinds.py`), or a kernel that is the other's with mass moved onto keys known to be no cheaper. One such fact is exact and free: **the restart is a row at every key, so `V(k) <= c_r + V0` everywhere, and a ruined key (section 5) is worth exactly `c_r + V0`, the most any key is worth.** So if offer B costs no more than A and, at a context (the flags, fractured mods and crafted slots an erasing offer's outcome depends on, ADR-0023), B's chance of each key that is not ruined is at least A's, then B is never worse than A at any key of that context: A can be left out there, exactly. **Not counted**: it needs the fossil sets' kernels at R04's contexts, which only the 1,245-offer build makes. Beyond this, a dominance between two fossil sets needs an order of keys that every value respects, and none is known: more junk is not always worse (a full side steers a slam), so "fewer junk mods" is no such order.

What the counts do say about offers: at a failure key every row is within 1% of the best (section 2's table), so no rule that leaves an offer out where it is "far from the best" can apply at 1% there. The offers are not where the proof's size comes from; the failures are.

## 5. Question 4: proposals

### Proposal A: the ruined keys are one state, valued without working out (exact)

**The lemma.** A fractured mod is never removed (no action of the game removes one), and a corrupted item takes no further action but those the abstraction lists for it. If a key's permanent mods leave no assignment of the target's necessary leaves to free slots (a fractured mod that gives no leaf takes a slot of a side the target fills; a fractured mod below the leaf's tier takes the leaf's group), then **no plan from it reaches the goal without the restart**, and its value is **exactly `c_r + V(start)`**: any plan from it restarts at some time, at cost at least `c_r`, and then costs at least `V(start)`; restarting at once costs exactly that. Nothing is cut (OR-12): the key keeps its exact value, it is only not worked out. The build values such a key by its restart row alone and offers none of its other rows; a kernel's mass onto ruined keys goes to one state.

**Its size, counted.** R04: every key with a fractured mod that gives no leaf (66,572, 66% of the keys) is worth exactly `V0 + c_r` in the complete model; the keys from which no goal is reachable without the restart in the model's own graph are 82,986 (82%). With those 82,986 keys certified by the lemma, the smallest certificate on R04 is {R04_RUIN}. R24: **0 ruined keys** (its start's fractured mod is wanted, and no offer fractures), so A does nothing there. R13: {R13_RUIN}.

**What it costs.** A test per key found, of the fractured mods against the target's leaves and sides: no row, no kernel, no member. It is cheaper than one offer at one member.

**The first PR.** `abstraction/_pattern.py` (the key's ruin test beside `PatternKey`, one state for every ruined key, its restart row only; the lemma in the module text beside "The imprints") and `planner/_pattern_bound.py` (the ruined state in the packed model); tests: the hand-worked bow with a Fracturing Orb, the model with and without the ruined state equal key by key in value (counted in states), and a ruined key never worked out. Measured end to end on R04 (the 1,245-offer bound of #1352: keys of model 6 before and after, first plan, bound against the plan) and on R24 (which it must not change: 0 ruined keys). **Prediction, not counted:** most of R04's 625,773 keys of model 6 are ruined, as 82% of the 21-offer model's are, since the Fracturing Orb is in both.

### Proposal B: the failures valued by the start (open: the lemma is not found)

The count of section 2 says what is missing on R24: a way to know that a key is no better than the start without working it out. An exact lemma of that kind is a **dominance between keys**: `V(k) >= V(j)` for a key `j` already worked out (the start, or any key whose value the proof holds), proved from the two keys alone. Then the tip `k` takes one row to `j` at no cost, which is sound by the same argument as a lead (the model with that row is under the true one). With the truth as the dominance (`FREE=oracle`) it gives 87 to 94 keys on R24. **No such lemma is known**, and the obvious ones are false: "more junk is no better" fails (a full side steers a slam), "a key with fewer wanted leaves passing is no better" fails (R24's 1,536-key merged states hold keys whose statuses differ at two leaves and have equal values, and swapping those leaves is not exact). A simulation computed on the model would prove it, but it needs the rows of the keys it compares, which is the work it would save.

So B is not proposed for building. It is the open question this note leaves: **a structural dominance of keys that holds on the failures of R24.** Filed as {ISSUE_B}.

### Not proposed, and why each is not one of the three counted lines

- **The cheap bound over every offer (#1310)** is a lead from a coarser key; section 2's `alpha` table shows that any lead under about 98% at every key leaves a proof of thousands to tens of thousands of keys on R24, so no coarse model can be the answer unless it is near exact, which #1310's merged models (8.2% and 86.5%) and #1315's direct ones (1.5% to 54%) are not. Proposal A is not a lead: it gives the ruined keys their exact value.
- **The led build (#1315, #1322)** and **the lead from above (#1321)** choose an order of the work; section 2 bounds every order at once: at least 38,368 keys on R24. Proposal A changes the model (fewer states, exactly), not the order.
- **The exact merge (bisimulation)** is a limit, not a design, until a lemma names the merged keys; #1317 (the type of a fractured junk mod) is one such lemma on R04 (41,847 to 60,901 keys at the same value), and Proposal A subsumes it on R04 (a key with a fractured junk mod is ruined there).

## 6. Question 5: what stays impossible

{IMPOSSIBLE}

## 7. Recommendation

{RECOMMEND}

## 8. The tools

`research/proof-size/`: `kd2.py` (kd.py of #1310 with the lead optional and the first complete bound of at least `MINKEYS` keys dumped), `dump.sh`, `export.py` (a dump into arrays and the complete values by the planner's solver; its start value equals the dump's to the last digit on R24 and R04), `cert.py` (the certificate's program; `FREE=oracle|ruin`; `alpha:` leads; `REWEIGHT`), `sweep.sh`, `bisim.py`, `quot.py` (the merged model, its values equal to the dump's: largest spread 0.0), `blocks.py`, `sdiff.py`, `swap.py`, `q1.py`, `q2.py`, `anaF.py`, `r13.sh`, and the outputs (`*.txt`). The dumps and per-run logs stay on the server under `.claude/scratch/t1360/` and `.claude/scratch/t1310/`.

## Not done, not verified

{NOTDONE}
