# A second, cheap bound over every offer: what the key costs, three candidates counted, one recommended (research, 2026-11-18)

Ticket #1310. A design note, no planner code. It follows `docs/research/2026-11-18-rounds-design.md` (#1276), which named this line "scheme D" and did not propose it.

Rules read: OR-12, OR-13, OR-37, OR-38, OR-39, OR-40, OR-58. Code read on main 37de068f: the docstrings of `abstraction/_pattern.py`, `_relaxed.py`, `planner/_offer_kinds.py`; `PatternKey`, `PatternModel` (`_pattern.py:290`, `:481`); `planner/_pattern_bound.py` (`pack_pattern_model`, `pattern_lower_bound`); `planner/_envelope_plan.py` (`CraftingProblem.lower`, `candidates`, `:175` to `:216`). Not read: the bodies of `_kernel.py` and `_kinds.py` (their roles are taken from the docstring of `_pattern.py`), `_coarse.py` and `_estimate.py` beyond their first lines.

Everything counted here ran on the owner's server on main 37de068f (the targets of #1308, OR-58), 4 worker processes a build under a 16 GB cap; R17 alone ran on the pushed head 30242744 of `claude/t1192b-all-mode-classes` (the member sharing of #1192 part 2, not landed), because main reaches too few of its keys to count. The tools and their outputs are in `research/cheap-bound/` (section 9). The 1-minute load is written beside each build.

Words. An **offer** is one priced action. The **bound** is the planner's proof of what any plan costs at least. The bound of today (the **exact bound**) is a small model of the craft: one state for each **key** (a summary of an item), solved to the end; its **build** is the work of making that model. A **leaf** is one wanted mod of the target. The **status** is the part of the key that says, for each leaf, whether the item has it. **Junk** is a mod the target does not want.

## Short answer

1. **A bound that looks at the wanted mods one at a time proves almost nothing, on every route.** Counted on the 13 targets with no search (section 3): even granted every favour, it proves 25.75 c on R04 (the guide costs 91,391.74), 20.26 c on R17 (2,573.42), 13.23 c on R24 (4,838.92), 14.26 c on R14 (6,888.46). The cost of these crafts is in holding several mods on the item **together**, and a per-mod figure does not see that. This removes two of the ticket's candidates (the relaxation at the level of the wanted mods alone, and a per-leaf or Lagrangian decomposition) by measurement.
2. **What makes the key count grow is the junk, not the wanted mods.** On R24's complete build (60,904 keys) the status takes 196 values; the rest of the factor of 310 is which junk sits beside the wanted mods, how many, and what the veiled and crafted slots hold (section 2).
3. **The same model on a coarser key still proves a large share.** Merging R24's complete model onto the status alone leaves 196 keys and proves 1,525.56 c, 42% of the exact bound's 3,617.64 c, where the build stopped at its quarter proves 139.73 c on the server and 18.48 c on a GitHub runner (#1276's e11). Keeping the crafted, held and veiled slots and dropping only the junk counts leaves 19,964 keys and proves 3,128.55 c (86%). R04: see section 4 (filled from the run).
4. **Recommendation: build the bound's own model directly on a coarser key (the "status model"), over every offer, before the exact bound.** It is a true lower bound by one lemma (section 5: merging keys of a sound model gives a sound model), it plugs into the search where the exact bound does (`CraftingProblem.lower` and `candidates`, as a maximum with the floors), and it tells which offers a cheapest relaxed plan uses, tools included, which no per-mod rule can (#1276, section 3). The exact bound stays, for the offers the status model names, and proves the answer where it completes.
5. **What is not known, plainly.** No direct build of the status model exists: every figure for it here is a merge of an exact model that had already been built, on the guide's own offers. Whether a direct build over all 4,000 to 11,000 offers of a target is fast, and whether its plan picks the guide's offers out of all of them, is **not verified**; the first PR of the work (section 8) measures exactly that, on the 13-route table, before any planner code depends on it.

## 1. The bounds the planner has today

Two bounds lead the envelope search (`CraftingProblem.lower`, `_envelope_plan.py:175`: the larger of the two at a state).

- **The offers' floors** (`planner/_offer_kinds.py`, `_offer_floor.py`; #1072, #1073, #1074). One number per shape of item: the least cost over chance, over the offers, of landing in "every necessary leaf passes" in one use (Wald's identity; proof in the module's docstring). It is cheap and covers every offer. It is weak for two stated reasons: an offer with no chance bound is "terminal" and cuts the argument at its price (`_offer_kinds.py`, "anything else": the Fracturing Orb, a Harvest add/remove, anything that reads the junk otherwise), and the event is one use. Counted on the 13 targets (the `rho` column of section 3): 0.10 to 4.09 c on every route.
- **The exact bound** (`abstraction/_pattern.py`). One model state per key `(flags, fractured mods, status, item state beyond the mods, crafted slots, count of ordinary mods per side, protected tags of the ordinary mods, veiled slots)` (`PatternKey`, `_pattern.py:290`); in it the exact kernels of the items that have the key. Measured at 99.48% of the exact cost on R04 and 98.10% on R14 (`_pattern.py:9`). It is the thing that does not complete: #1276's probes, #1295, #1297 and #1192 part 2 (the four measurements the ticket quotes).

Between them there is nothing: a state whose key the stopped build did not reach is valued at the floor (`_envelope_plan.py:178`), a few c against thousands.

## 2. Question 1: what makes the key count grow, by part

Tool: `kd.py` stops a route at its first bound's build and dumps the model; `ka.py` counts the keys by part. "Left without it" is the number of distinct keys when that one part is dropped and every other part kept: the smaller it is against the total, the more that part multiplies.

| Route, round 1 | Build | Keys | status | crafted | held (imprints, veiled offer) | fractured | counts | tags | veiled | Left without status | without crafted | without held | without tags (counts go with them) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R24, guide's 9 labels and Alteration | complete in 176 s (load 11 to 8); start value 3,617.64 | 60,904 | 196 | 2 | 200 | 1 | 12 | none in the key | 20 | 3,251 | 36,909 | 6,853 | 19,964 (counts alone: the key holds no tags) |
| R20, guide's 6 labels and Alchemy | stopped at 150 s, 793 of 2,308 keys worked out (load 6 to 11) | 2,308 | 16 | 7 | 1 | 1 | 14 | 153 | 1 | 446 | 872 | 2,308 | 365 (tags alone); 90 (tags and counts) |
| R04 | R04-ROW |
| R17 | R17-ROW |

Read per route:

- **R24.** 196 statuses become 60,904 keys. Dropping the counts of junk per side divides by 3.05; the veiled offer (which three mods the Unveil shows, in `held`) by 8.9 when it is dropped alone; the crafted lock by 1.65. No part alone explains the factor: status, the unveiled offer and the junk counts multiply one another.
- **R20.** The protected tags of the junk (which junk mods carry the attack or the caster tag, counted per side: the key holds them because a "Cannot roll Attack Modifiers" craft is offered) take 153 values and multiply the keys by 6.3 on their own; with the counts, by 25.6. This is a stopped build, so the figures are of the part reached.
- **R04 and R17**: R04-R17-READ

**Which parts a cheaper bound may drop and stay a true lower bound.** Any of them: section 5's lemma holds for every function of the key. What a part costs to drop is strength, and that is measured in section 4, not argued. Two parts have a further price in the *direct* build (section 5): the crafted slots hold the metamods, which decide which side a reroll keeps and which tags a draw may give, and the held part holds the imprints, which a restore reads; a key without them must offer each action at every value of the part it reads. So the first status model keeps flags, fractured mods, status, crafted and held, and drops the junk: counts, tags, and the type of a fractured junk mod.

OR-12 is kept: no count cuts a key, an offer or an outcome. A coarser key merges states; it never drops one.

## 3. Candidates A and B, counted: a bound at the level of the wanted mods

**The candidate (A).** For each necessary leaf `l` that is open at the start, a plan must make `l` pass a first time. If one use of offer `a` makes an open leaf `l` pass with chance at most `p_l(a)` at every state, then, as in the floors' proof, the expected number of uses `x_a` of any plan obeys `sum_a p_l(a) x_a >= 1` for each `l`. So every plan costs at least the value of the small linear program `min sum_a c_a x_a` under those rows, `x >= 0`. **Proof sketch.** For a leaf `l` let `T` be the first time `l` passes. Until `T`, given the history, step `t` makes `l` pass with chance at most `p_l(a_t)`, and `T` is finite almost surely for a plan that reaches the goal, so `E[sum_{t <= T} p_l(a_t)] >= 1` (Wald, as in `_offer_kinds.py`, "THE LOWER BOUND rho"); the uses until `T` are at most all the uses. It survives every tool: an action that removes a mod, locks a side, fractures, imprints or restores makes no leaf pass *for the first time* (a restored snapshot passed it before), so its `p_l` is 0, and a restart's is the chance that the bought item holds the mod. Candidate **B**, a per-leaf or Lagrangian decomposition, is the dual of the same program (one multiplier a leaf), so it proves the same figure.

**The count** (`leaflp.py` on the output of #1276's `seed.py`, run again on main 37de068f; no search; 4 to 34 s a target). The chances are those `seed.py` reads from `reach_bound`, `add_bound` and `declared_add_bound` at the shapes the floors know; they are not yet proofs over every state (a metamod that blocks a tag raises a draw's chance, so a proved `p_l` would be larger and the figure smaller). Two figures: **provable today** counts an offer with no per-leaf bound (4,000 to 7,000 offers a target: `seed.py` gives no chance for a kind the floors call terminal, nor for a fossil set outside the 30 of least declared floor) as chance 1; **ceiling** counts each of those as chance 0, the most this program could ever prove.

| Route | Offers | Floor today (`rho`) | LP, provable today | LP, ceiling | Guide's cost | Ceiling over guide | The LP's offers at the ceiling |
|---|---|---|---|---|---|---|---|
| R12 | 5,960 | 4.09 | 4.09 | 38.23 | 40.93 | 93% | Harvest Reforge Lightning |
| R10 | 4,254 | 3.23 | 4.09 | 5.83 | 38.72 | 15% | an essence, two bench crafts |
| R11 | 5,557 | 1.03 | 4.09 | 4.37 | 617.28 | 0.7% | an essence |
| R05 | 4,895 | 2.37 | 4.09 | 9.28 | 120.56 | 7.7% | two essences |
| R13 | 5,713 | 1.10 | 4.00 | 361.71 | 21,509.67 | 1.7% | Augmentation, the multimod craft, bench crafts |
| R08 | 5,344 | 3.11 | 4.00 | 4.32 | 563.46 | 0.8% | an essence |
| R09 | 5,333 | 2.90 | 4.00 | 4.05 | 353.14 | 1.1% | an essence |
| R04 | 6,220 | 0.79 | 4.00 | 25.75 | 91,391.74 | 0.03% | Transmutation x216, the two guide essences |
| R14 | 10,915 | 0.10 | 4.00 | 14.26 | 6,888.46 | 0.2% | Alchemy, Augmentation, two bench crafts |
| R17 | 7,333 | 3.13 | 4.00 | 20.26 | 2,573.42 | 0.8% | Transmutation x1,934 |
| R20 | 10,878 | 3.73 | 4.09 | 54.75 | not evaluated (#1292) | - | an essence x137, Essence of Horror |
| R06 | 9,330 | 4.00 | 4.00 | 4.42 | not evaluated | - | Transmutation, an essence |
| R24 | 4,253 | 3.66 | 4.09 | 13.23 | 4,838.92 | 0.3% | an essence x53, a pick, the guide's essence |

(The guide's costs are those of #1276's table, evaluated before the targets of #1308 changed; **not re-evaluated here**. The ratios are orders of magnitude, which is all they are used for.)

What the count says:

- **Provable today it is 4.00 to 4.09 c on every route**: one offer with no bound (a beast that adds a mod, a likelihood reforge) covers every row at once.
- **At its ceiling it is under 2% of the guide on every route with more than one wanted mod, R10 (15%) and R05 (8%) apart.** On R17 the cheapest "plan" of this program is 1,934 Orbs of Transmutation: each wanted mod is cheap to hit alone on a magic item, and the program lets the item keep all six. Only R12, whose target is one mod, is bounded well (93%).
- **It ranks no tool.** The offers it uses are rerolls and essences; of R04's 8 guide labels it holds 2, of R17's 14 it holds 1 (`leaflp.txt`). #1276's section 3 found the same for the per-mod seed rule.

So A and B are cheap (seconds, no state at all) and admissible, and as a figure and as a guide to offers they give nothing the floors do not. **Not recommended.** The per-leaf chance bound itself is still worth having for every kind (it is what turns a "terminal" offer into one the floors can raise), but that is #1072 to #1074's line, not a second bound.

## 4. Candidates C and D, counted: the same model on a coarser key

**C: the status model.** The exact bound's model, with a key that holds less. **D: abstraction refinement** is C used as a ladder: the coarse key everywhere, the exact key only where the plan in hand goes.

**The count.** `ka.py` takes a dumped exact model and merges it on a coarser key: a merged key takes every action of every key it holds, each kernel pushed onto the merged keys; it is a goal when one of its keys is. The merged model is solved by the planner's own solver (`pack_pattern_model`, `solve_packed`). By section 5's lemma its start value is a true lower bound, and it is the **most** any bound stated on that coarser key can prove on these offers. It is the ceiling of candidate C, not a run of it: a direct build would not have the exact model to merge. A merged key that holds a key the build did not work out takes that tip's floor, so only a complete build gives a ceiling; R20 and R17 (stopped) are counted by part in section 2 only.

| Route, offers | Key | Keys | Start value | Share of the exact bound | The offers its cheapest plan uses from the start |
|---|---|---|---|---|---|
| R24, 10 and the restart | the exact key | 60,904 | 3,617.64 | 100% | the guide's essence, the lock craft, Veiled Chaos Orb, Unveil, the three picks, Annulment |
| | without the junk counts | 19,964 | 3,128.55 | 86% | the essence, the lock craft, Veiled Chaos Orb, Unveil, the picks |
| | without counts and veiled slots | 17,892 | 2,013.51 | 56% | the essence, Unveil, two picks |
| | without counts and crafted slots | 9,982 | 1,581.00 | 44% | the essence, Veiled Chaos Orb, Unveil, picks, Annulment, Harvest add/remove |
| | flags, fractured mods and status | 196 | 1,525.56 | 42% | the essence, a pick, Annulment, Harvest add/remove |
R04-TABLE

(R24's plan from the complete exact bound costs 3,658.60 c, #1276's e12; its guide 4,838.92 c.)

What the count says:

- **A key of the status alone is 310 times smaller on R24 and still proves 42% of the exact bound**, 115 times the leaf program's ceiling (13.23 c) and 11 times what the stopped exact build proves on the server (139.73 c, e11).
- **Its plan is of the right kind only when the key keeps what the tools act on.** On the status alone the relaxed plan needs no lock and no veiled orb (the merged key lets it keep a prefix through a reroll for free, because some key inside the merged one holds the lock). With the crafted, held and veiled slots kept and only the junk counts dropped, the plan uses the lock craft, the Veiled Chaos Orb, the Unveil and the picks: the guide's methods.
- R04: R04-READ

## 5. The recommended candidate: the status model, and why it is a true lower bound

**The model.** A function `g` of the key (`g` drops parts of it). A state for each value of `g`; at a state `G`, every action of every key `k` with `g(k) = G`, its kernel pushed through `g`; a goal when one of its keys is; the restart leads to `g` of the start key.

**Lemma (merging is sound).** Let `V` be the values of the exact bound's model (`V(key(s)) <= V*(s)`, the exact cost: `_pattern.py`, first paragraphs and each section's "Proved"). Let `W(G) = min over g(k) = G of V(k)`. Then the merged model's value `M` has `M(G) <= W(G)`, so `M(g(key(s))) <= V*(s)`.
*Proof sketch.* Take `G` not a goal and `k` the key of `G` with the least `V`. Its best action `a` in the exact model has `V(k) = c_a + sum_k' P(k') V(k') >= c_a + sum_k' P(k') W(g(k'))`, and the right side is the backup of the merged action `(k, a)` at `W`. So `W >= T(W)` for the merged model's operator `T`. `T` is monotone and every cost is positive, so the merged value is the least fixed point of `T`, reached from 0, and it lies under any `W` with `W >= T(W)` (the argument `_offer_kinds.py` uses for THE SHAPES). At a goal both are 0.
The lemma covers every case the brief names at once, because each is already inside the exact model it merges: restarts (a certain move to the start key), a bought start with random mods (the draw that opens the listing is an action of the start key), imprints (`_pattern.py`, "The imprints": the snapshots are in the key as keys, and stay in `g` as merged keys), metamods (in the crafted slots), removals and the wipe (ordinary actions of each key). **Checked by count, not only argued:** on R24 every merged value above is under the exact one, and merging on the full key returns 3,617.644353959281, the build's own figure.

**The direct build, which is where it can break.** The lemma needs, at a merged key `G` and an action, a set of kernels whose least backup is at most the least over every key in `G` and every member of each, for any values. The exact build gets that by making the members; a direct build must get it from an argument per class of action, as `Pattern.mode_of` does today, with the junk **count** now free as well as the junk's kind. The arguments, and what could break each:

| What the action does | Kernel offered at a merged key | Why it is under every member | What could break it |
|---|---|---|---|
| Erases the mods and reads no junk, no lock held (Chaos, Alteration, an essence, a reforge, the Scouring wipe, the draw of a bought start): today `ANY` | the one exact kernel | the outcome is a function of the flags, fractured mods and crafted slots, all in `g` (ADR-0023) | `g` dropping the crafted slots or the type of a fractured junk mod: the pool then differs inside `G`. So `g` keeps the crafted slots, and a fractured junk mod keeps its family type until a box argument replaces it |
| Adds one drawn mod and keeps the rest (Augmentation, Regal, Exalted, a beast's or Harvest's added mod): today `EXTREMES` | the corners of the box of pool weight the junk takes out, now over every junk count that leaves room | the chance of each successor is linear-fractional in that weight with a positive denominator (`_pattern.py`, `EXTREMES`); a drawn junk mod lands in `G` itself | a full side (refused) is one more corner, not a member to skip; a family on both sides, or a draw by tag or level, breaks the box as today (`ALL` there) |
| Removes one removable slot uniformly (Annulment, the Veiled Exalted Orb's removal, an Eldritch Annulment): today `ONE` | two kernels: no junk, and the most junk the sides hold | each relevant slot goes with chance `1/(r + j)`, a junk slot with `j/(r + j)` back to `G`; the backup is linear-fractional in `j`, so its least is at `j = 0` or the largest `j` | a metamod that protects tagged slots changes which slots count: the protected junk is its own `j'`, a second axis of the same box |
| Adds or removes a named mod with certainty (bench craft, Remove Crafted Mods, a pick, an imprint, a restore, the restart) | the one certain successor | `_pattern.py`, "The certain additions" and "The imprints": the successor key is a function of the key and the action, and of nothing `g` drops but room | room: a craft refused on a full side. The merged key offers it (some member has room unless the relevant slots alone fill the side, which the status and crafted slots say) |
| Fractures one mod uniformly (Fracturing Orb): today `ALL` | corners over the junk count, as a removal | each relevant mod is fractured with chance `1/(r + j)`, a junk one with `j/(r + j)` | needs `g` to send "a fractured junk mod of side s" to one value; the refusal under four mods reads the count, so the corner must be a count the Orb takes |
| Rerolls one side under a lock, or weighs the junk it holds (a reroll with "Prefixes Cannot Be Changed", a likelihood reforge): today `ALL` or `RELAXED` | the choice nodes of `_relaxed`, with the kept side's junk count free | `_relaxed.py`, "Sound": the least backup over the box of class weights is at a corner, by induction on the draws | the number of mods drawn depends on how many the locked side keeps, which is no longer in the key: one walk per kept count, or `ALL`; **this is the class with no finished argument** |
| Anything with no argument yet | the **angelic** kernel: one action per successor the action can reach from some member, at its cost, with certainty | the least of the outcomes is at most their expectation | nothing: it is sound for any action. It is weak (the action behaves as a free choice), and that is where the bound loses strength, visibly |

The last row is what makes the direct build safe to start: a class without a proof is not left out and not guessed, it is offered at its most optimistic, and the bound is lower for it, never higher. Each class that gets its argument raises the figure, and the merge of an exact model (this note's `ka.py`) is the test: **on every route whose exact build completes, the direct status model must be at or under the merged one, key by key.** A direct value above the merged value is a proof that a rule is wrong.

**Cases the brief names.** Restarts: a certain move, in `g` as today. Imprints: `g` keeps the held snapshots as merged keys; a bound made of the item's bound and the snapshot's separately is not one (`_pattern.py`, "The imprints", last lines) and is not proposed. Metamods: in the crafted slots, which `g` keeps. Actions that remove mods: the removal row; the corner `j = 0` is the one a careless rule forgets (with no junk the Annulment always takes a wanted or a crafted slot, which can be the *better* outcome when it frees a slot or lifts a lock). The wipe: an erasing action with a fixed result, first row. A bought start with random mods: the opening draw is an erasing draw of the start's shape, exact, one walk (R20: 133 s for 22 such kernels on main, `handoff-t1192.md`; #1194's store keeps it across rounds). **Not verified:** each row above is a sketch from the arguments already in `_pattern.py`; none was run as code.

## 6. Question 3: how the two bounds work together, and what the page may claim

- **What leads.** The status model is built first, over every offer, growing from the offers of least floor as the exact bound's model does today (`pattern_lower_bound`'s "offers join the model"). The search reads it at `CraftingProblem.lower` and `candidates` as one more term of the maximum: the exact value where the exact model reached the key, else the status model's value of `g(key)`, never below the floor. A state the exact build did not reach is then valued at hundreds or thousands of c in place of the floor's few.
- **What picks the offers.** The offers on the status model's cheapest plan from the start, and those within the plan in hand's cost of it by their own value in the model (the same test the growth of the exact model uses), are the first step of scheme S (#1276, section 5) in place of the per-mod seed that section 3 of #1276 showed does not find the tools. Nothing is cut by this: every other offer still has its step.
- **What proves.** A step of S whose exact bound completes proves its plan within its gap of the cheapest plan of that step's offers, as today. The status model adds one proof of its own: its start value is a lower figure for **every offer it held**. When it held every offer of the target, the answer can say, for the first time, "no plan of any method costs less than X", beside "the cheapest of the methods of the finished steps is Y". The gap between X and Y is stated as it is (OR-13); it will often be wide (42% to 86% on R24), and the page says "proved within N% of the cheapest of these methods; no method at all can cost less than X", never "the cheapest of every method" from the status model alone (OR-38: a claim stays a proof).
- **OR-39.** The first plan can come earlier: a search led by the status model alone, before any exact build, gives an executable plan with its exact mean cost; it is shown, marked "not yet proved the cheapest", and replaced only by a cheaper one.
- **OR-40, OR-37.** No offer and no method is dropped to fit a limit. If the status model's build is itself stopped by the limit, it says so and stands at the offers it held, as the exact build does.
- **A bound learned from stored plans** (the ticket's fifth example) can order the offers before any build and cannot prove anything; it is compatible with all of the above as an ordering of what joins the status model first. Not designed here: the store of #1194 holds draws, not plans.

## 7. Predictions, route by route

Every cell in the last two columns is a **prediction**; none is measured. "Exact build today" is from #1276's probes and the dumps of this note.

| Route | Site today (#1276's table; targets since changed by #1308) | Exact build on the guide's offers | Status model: measured ceiling on the guide's offers | Predicted lead figure over all offers | Predicted effect |
|---|---|---|---|---|---|
| R12, R10, R11, R05, R13, R08, R09 | plans at or under the guide | completes | not counted | under the exact one | none on the cost; a lower figure over every method beside the plan |
| R24 | no plan | complete in 163 to 176 s | 1,525.56 (status) to 3,128.55 (junk counts dropped), exact 3,617.64 | at most those figures (more offers only lower a bound) | a first plan before the exact build ends; the guide's offers in step 1 **if** the plan of the 19,964-key model is also the plan when 4,253 offers are present (not verified) |
| R04 | no plan | R04-PRED |
| R17 | 97,474 c | does not complete (R17-PRED) | not countable: no complete build | unknown | unknown; this route is the test of the direct build |
| R20 | 35 million c | does not complete: exact draws under a lock (#1295) | not countable | unknown | depends on the one class with no finished argument (a reroll under a lock, section 5) |
| R14 | no plan | donors' builds stop at one key of 268 (`handoff-t1192.md`) | not counted | unknown | unknown |
| R06 | not planned (#1232) | - | - | - | none |

## 8. Question 5: the size of the work

In this order; each PR is measured on the 13-route table before the next.

1. **The count over all offers, no planner behaviour changed** (research PR; `research/cheap-bound/`; about 2 days). A status model built directly with the angelic kernel for every class but the certain ones and the erasing rerolls (both already key-level today), from one script, on all 13 targets with every offer. It answers what this note could not: keys and seconds by count, the figure against the guide, and whether the guide's offers are on its cheapest plan. **If the figure collapses (as the leaf program's did) or the guide's tools are absent on R04 and R17, the line stops here** and the notes say so.
2. **The model in `abstraction/`** (one PR: a new `abstraction/_status.py` with `g`, the merged build and the angelic kernel; `_pattern.py` untouched but for an export; tests: the lemma on the hand-worked worlds, "direct at or under merged, key by key" on every fixture whose exact build completes, counted in states). About 3 to 4 days.
3. **The search reads it** (one PR: `planner/_pattern_bound.py` builds it, `_envelope_plan.py` `lower` and `candidates` take the maximum, the answer's limits word section 6's claim; tests through the planner's entry; the 13-route table as the site plans, twice, load beside each timing; the heavy benchmark's record). About 3 days. This is the first PR that can move a route.
4. **The arguments, one class a PR** (additions over the junk count; removals and the Fracturing Orb; a reroll under a lock). Each raises the figure and is tested against the merge. 2 to 3 days each; the third is the hard one and the one R20 waits for.
5. **Step 1 of scheme S from the status model's plan** (with #1276's PR 2).

What can land first and be measured: PR 1 alone, in two days, on the table. Files that the two agents beside this ticket hold (`abstraction/_pattern.py` for #1192, the draw store of PR #1294) are not touched before PR 2, which only reads them.

## 9. The tools

In `research/cheap-bound/`: `kd.py` (dump of a route's first bound's build; round 1 set by `LEAD` as #1276's `tb.py`), `r.sh` (the run: load rule, 16 GB cap), `ka.py` (keys by part; the merged models), `leaflp.py` (the leaf program on `seed.py`'s output; needs scipy, run with `uv run --no-project --with scipy`), the lead files, and the outputs `ka-R24.txt`, `ka-R20.txt`, `ka-R04.txt`, `ka-R17.txt`, `leaflp.txt`. The dumps (`k-*.pkl`, tens to hundreds of MB) and the seed files stay on the server under `.claude/scratch/t1310/`.

## Not done, not verified

- No direct build of the status model exists. Sections 4 and 7 give ceilings from merges of complete exact builds, on the guide's offers only.
- Whether the status model ranks the guide's offers first **among all offers** was not measured on any route. Question 4 of the ticket is answered only in the weaker form "among the offers of the build that was merged".
- R17 has no complete exact build, so it has no merged figure; the ticket asked for R17 and it is not delivered.
- The leaf program's chances are `seed.py`'s, read at the shapes the floors know; a proved bound over every state would be lower still. The guide's costs in section 3 were not re-evaluated on the targets of #1308.
- The table of section 5 is a set of proof sketches. None was run as code, and the row "rerolls one side under a lock" has no finished argument.
- Every timing is one machine under the load written beside it, seen once.
- R14 was not dumped (it is not searched in rounds, so the probe's hook does not reach it).
