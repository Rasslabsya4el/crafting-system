# The rounds of methods: what decides a route, and one design for the scheme (research, 2026-11-18)

Ticket #1276, PR 1 of 2 (this note; no planner code). Question: how does the search reach a plan that needs several kinds of methods together, within the run's time limit, for any target (OR-37: every beta method on any target, no per-route patch, no list of "guide combinations")?

Rules read: OR-12, OR-13, OR-33, OR-37, OR-38, OR-39, OR-40, OR-41. Inputs: the retro audit of 2026-11-18 (the 13 reference routes planned as the site plans them, main 33cd3e5b, with the groups of every route), `planner/_rounds.py`, `_plan.py`, `_offer_kinds.py`, `_offer_floor.py`, `_pattern_bound.py`, `_envelope_plan.py`, `_awakener.py` on main 08bb0cdd, and the issues named below.

Everything measured here ran on the owner's server (24 cores) on main 08bb0cdd, as the site plans (`benchmark_routes.py <route> --net`: the target alone, every beta method, 600 s time limit), 4 worker processes a run, under a 16 GB memory cap. No file of the repo was changed: the probes wrap two functions from outside (which offers are in round 1; how much of the limit the bound's build may take). The 1-minute load of the machine is given next to every timing.

Words used here. An **offer** is one priced action the planner may use (one essence, one bench craft). A **kind** is a family of offers (essences, bench crafts, fossil sets). A **round** is one search over a set of offers. The **bound** is the planner's proof of what any plan must cost at least; the search uses it to tell good items from bad ones. Its **build** is the work of making it, before the search starts; a build is **complete** when it has worked out every case it found, and **stopped** when its time ran out first.

## Short answer

1. **What decides a route is whether the bound's build completes, not which kinds sit in which round.** On R04 the same methods give a plan of 32,192.94 c in 48 s when round 1 holds the guide's 7 offers (build complete in 42 s; seen twice, to the cent), and a first plan of 898,973,434,471 c when round 1 holds those 7 and 12 more single offers (build stopped at 150 s with 5,397 of 24,286 cases done). With a complete bound the search needs about 3 s. With a stopped one it is blind: its starting figure is 0.01 to 160 c against true costs of thousands, its first plan is absurd, and the rounds after it get shares too short for any build.
2. **On four of the five failing routes the build does not complete in its time even on the guide's own offers.** Round 1 = the guide's labels, nothing else of weight, and the build stopped at the quarter of the limit it is allowed (150 s): R17 (11 offers) 176 of 1,081 cases done; R20 (7 offers) 378 of 1,751; R24 (10 offers) 55,363 of 60,494; R14 (13 offers, a run of 2026-11-17) stopped in growth at 152 s. Only R04 completes (42 s). Allowed three quarters of the limit, R24's build completes in 163 s and its plan is 3,658.60 c, below the guide's 4,838.92 (seen twice); R17's is a third done at 447 s (plan 44,910.65 c against 2,573.42), R20's meets a fault of the planner (#1290), and so R24's gate is the quarter rule, the others' is the cost of the build itself: open issue #1158 with #1192, #1193 and #1194. This is the "second cause" the ticket asks to trace on R14 and R24, and it is the first cause on R17 and R20 as well. No arrangement of rounds, groups, seeds or time shares brings R17, R20 or R14 to its guide's cost today.
3. **No rule that picks round 1 without a search found the guide's methods.** The rule the previous direction named (for each wanted mod, the offers of least cost over chance of giving it) was tested by count on all 13 targets, with no search: it holds every "provider" of the guide on 3 of 13 routes (4 with five offers a mod), and on every failing route 3 to 7 of the guide's labels are tools that give no wanted mod at all (Orb of Annulment, the metamod crafts, the Fracturing Orb, the imprint, Harvest add/remove), which no such rule can rank. Taking every tool gives 44 to 96 offers, and 19 already break R04's bound.
4. **Recommendation, in this order.** (a) First the build: #1193, #1192, #1194 under #1158, with a new acceptance that these probes define (section 7): on each failing route, round 1 = the guide's offers must build a complete bound inside its share. (b) Then PR 2 of this ticket: the rounds as a few nested steps, each accepted only when its bound completes (section 5), with the Awakener's Orb inside the same scheme and an answer that claims only what the completed steps prove. PR 2 before (a) can move one route at most (R04) and risks the seven good ones for it; I do not recommend that order.
5. **What PR 2 is predicted to give** (section 6): after (a), R04 about 32,200 c (guide 91,392), R24 about 3,660 c (guide 4,839), R17 about 2,500 c (the plan a run with no limit found on 2026-11-17), R20 and R14 not predictable before their builds complete. Before (a): R04 and R24 uncertain (their plans are measured only on the guide's exact offers, and a step of S holds more), the other three unchanged.
6. **The size of what (a) must reach, said plainly.** Today a build completes on 7 offers (R04) and 10 (R24) and not on 19. A step of S that holds a guide's methods holds 20 to 60 offers, because nothing but a search can tell which few tools pay. If the build cannot be made to complete on sets of that size, S will accept only its first steps on the hard routes and say so; the way past that is a bound of another kind (scheme D, section 4), not another arrangement of rounds.

## 1. What is wrong, checked again

The audit's findings were read against the code of main 08bb0cdd and hold:

- A round is the base plus one group (`_rounds.py:332`); a group is one kind and the model features it adds (`round_groups`, `_rounds.py:155`), so every route has 26 to 36 rounds.
- Before the first plan a round has all the time left (`_rounds.py:344`: `searches = rest if best is not None else 1`). After it, each round has the time left divided by the rounds left (`search_net`, `_plan.py:587`).
- What joins the base: round 1, a round that closed or was refused, and the round that made the first plan (`_rounds.py:400` to `405`). A round its time stopped does not.
- A target that is offered an Awakener's Orb is not searched in rounds (`rounds_apply`, `_plan.py:1134`); each donor and then the target get an equal share of the time (`_awakener.py:156`, `search_net(clock, searches)` with the searches left).
- The bound's build before a first plan may take a quarter of its search's time (`SEARCH_PER_BUILD = 3.0`, `_envelope_plan.py:261`): 150 s of 600.

One claim of the audit does not hold as it was written. "With the guide's methods in round 1 and the same net, R17 plans at 2,507 c": that plan came from a run with no time limit (the checkpoint of 2026-11-17, whose target file still named the guide's actions). Under the 600 s limit the same round 1 gives 148,733,212.72 c (probe e8 below).

## 2. The probes

Each row is one run of one route as the site plans it, with round 1 set from outside. "Cases" are the bound's keys: found, and of those worked out (expanded). A build is complete when both are equal.

| Probe | Route | Round 1 holds | Bound's build | First plan and answer | Load |
|---|---|---|---|---|---|
| e6 | R04 | the guide's 6 labels and Alchemy: 7 offers | **complete** in 43 s: 13,060 cases, starting figure 32,075.10 | 32,192.94 c at 48 s, proved at least 32,075.23 (gap 0.37%) | 3.5 |
| e7 | R04 | the same (repeat) | **complete** in 42 s: 13,060 cases, 32,075.10 | 32,192.94 c at 47 s; answer 32,196.14 c with the start item | 3.3 |
| e10 | R04 | those 7 and every other single-offer kind that adds no imprint and no veiled mod (the other currency orbs, Remove Crafted Mods, the Matron, the three other metamod crafts): 19 offers | stopped at 150 s: 24,286 cases, 5,397 done, starting figure 0.39 | 898,973,434,471 c | 1.3 |
| e5 | R04 | e10's and the imprint, restore, veiled orbs, unveil and picks, three corrupted essences: 30 offers | stopped at 150 s: 42,731 cases, 3,438 done, 0.38 | 898,973,434,504 c | 3.5 |
| e1 | R04 | the guide's kinds whole (every essence, the four corrupted ones, the metamod crafts): 117 offers | first model (14 offers) complete in 2.2 s at 6.80, its growth by 98 offers stopped at 150 s | 898,973,434,456 c; the run ends with an error | 4 to 11 |
| e2 | R04 | every kind but fossil sets: 231 offers | stopped at 150 s with 23 cases done | killed at the 16 GB cap | 4 to 11 |
| e4 | R04 | every offer in one search (6,210 after twins) | stopped at 150 s with 23 cases done | killed at the 16 GB cap | 4 to 11 |
| e8 | R17 | the guide's 10 labels and Alchemy: 11 offers | stopped at 150 s: 1,081 cases, 176 done, 0.0105 | 148,733,212.72 c (answer 148,733,745.72 c); guide 2,573.42 | 3.3 |
| e9 | R20 | the guide's 6 labels and Alchemy: 7 offers | stopped at 150 s: 1,751 cases, 378 done, 13.24 | no plan in 637 s | 2.9 |
| e11 | R24 | the guide's 9 labels and Alteration: 10 offers | stopped at 150 s: 60,494 cases, 55,363 done (92%), 139.73 | 8,248.20 c; guide 4,838.92 | 1.3 |
| e3 | R24 | the guide's kinds whole: 84 offers | growth stopped at 150 s (33 of 85 offers in), 160.56 | 1,684,956 c first, 69,482.96 c later | 4 to 11 |

The same round 1, with the build before a first plan allowed about three quarters of the limit instead of a quarter (447 s of 600):

| Probe | Route | Round 1 holds | Bound's build | First plan and answer | Load |
|---|---|---|---|---|---|
| e12, e16 | R24 | e11's 10 offers | **complete** in 163 s and 165 s: 60,904 cases, starting figure 3,617.64 | 3,658.60 c, proved at least 3,629.58 (gap 0.8%), in both runs; guide 4,838.92 | 2.5 and 6.3 |
| e14 | R04 | e10's 19 offers | stopped at 447 s: 33,348 cases, 9,756 done, 13.12 | 898,973,434,471 c; the run ends with an error | 2.5 |
| e15 | R17 | e8's 11 offers | stopped at 447 s: 2,273 cases, 656 done, 0.38 | 44,910.65 c (answer 45,443.65 c); guide 2,573.42 | 2.2 |
| e13 | R20 | e9's 7 offers | a fault of the planner at 404 s, 440 of 1,751 cases done (filed: #1290) | no plan | 2.2 |

(The load is the 1-minute figure when a run started; e12 to e15 ran together, four to six probes of 4 processes at once, so their timings were taken under a load near 6 of their own making.)

R14 was not probed again (it is not searched in rounds, so the probe's hook does not reach it). Its guided run of 2026-11-17 on a GitHub runner (the guide's 13 offers) shows the same thing: the build stopped in growth at 152 s with a starting figure of 0.108, the search's figure crawled from 0.108 to 0.39 over 22 search rounds, and the plan was 696,689.73 c against the guide's 6,888.46.

What the probes say:

- **A complete bound gives a sane plan at once.** e6 and e7: 42 s of build, then 3 to 5 s of search, and the plan is proved within 0.37% of the cheapest of its offers.
- **A stopped bound gives an absurd first plan**, whatever offers are present. e10 holds every offer of e6 and still plans 9e11 c.
- **Completeness falls steeply with the offers in the round.** From 7 to 19 offers on R04 the cases found double and the speed falls from about 310 cases a second to 36. The 12 added offers are single currency orbs and metamod crafts, the ones any "safe first tier" would hold.
- **How close the build came matters.** R24 at 92% plans 8,248 c (1.7 times the guide) and at 100% plans 3,658.60 c (0.76 times); R17 at 16% plans 148 million and at about 29% plans 44,911 c.
- One search over everything, and everything but the fossil sets, do not fit 16 GB.

## 3. A seed chosen without a search: the counted test

The direction handed to this note was: choose round 1 per offer, with no search, from what actions declare: for each wanted mod its best "providers" by cost over chance, and what they depend on. The test (`seed.py` and `seedreport.py`, kept with the probe logs; one process, 4 to 44 s a target, no search): for each of the 13 reference targets, take the offers the planner would search, and for every wanted mod not on the start item (a "leaf" of the goal: the necessary ones and the members of a k-of-n) compute each offer's chance of giving that mod in one use, from the same pool bounds the planner's floors use (`reach_bound`, `add_bound`; a bench craft or a veiled pick that names the mod counts 1). Rule P(K): for each such mod, the K offers of least cost over chance. For fossil sets the chance was computed only for the 30 sets of least declared floor and the guide's own.

A guide's label is a **provider** when it has a chance on some wanted mod, and a **tool** when it has none.

| Route | Wanted mods open | P(1) size | P(5) size | Guide's providers inside P(1) / P(5) | Guide's providers outside P(5), with their rank | Guide's tools (no rule P finds them) | Every tool offered |
|---|---|---|---|---|---|---|---|
| R12 | 1 | 1 | 5 | 0 of 1 / 1 of 1 | - | - | 44 |
| R10 | 3 | 3 | 10 | 2 of 2 / 2 of 2 | - | - | 62 |
| R11 | 4 | 3 | 7 | 1 of 1 / 1 of 1 | - | - | 62 |
| R05 | 2 | 2 | 6 | 1 of 1 / 1 of 1 | - | - | 45 |
| R13 | 5 | 2 | 12 | 1 of 3 / 1 of 3 | Regal Orb 17, Orb of Alteration 21 | - | 85 |
| R08 | 3 | 2 | 8 | 1 of 2 / 1 of 2 | the fossil set 77 | - | 96 |
| R09 | 3 | 3 | 11 | 1 of 2 / 1 of 2 | the fossil set 67 | - | 79 |
| R04 | 5 | 3 | 12 | 2 of 3 / 2 of 3 | Exalted Orb 25 | Annulment, Remove Crafted Mods, metamod craft, Fracturing Orb | 84 |
| R14 | 5 | 4 | 15 | 2 of 5 / 4 of 5 | Orb of Alteration 20 | Annulment, Remove Crafted Mods, multimod craft, metamod craft | 55 |
| R17 | 2 | 1 | 5 | 1 of 3 / 1 of 3 | Regal Orb 18, Orb of Alteration 35 | Annulment, multimod craft, two metamod crafts, imprint, restore, Harvest add/remove | 85 |
| R20 | 4 | 2 | 12 | 1 of 3 / 1 of 3 | Harvest Reforge Fire 16, Harvest Reforge Influence 115 | Annulment, metamod craft, the Matron | 73 |
| R06 | 7 | 3 | 13 | 1 of 2 / 1 of 2 | Exalted Orb 67 | Annulment | 66 |
| R24 | 6 | 6 | 15 | 2 of 5 / 4 of 5 | Veiled Chaos Orb 86 | Annulment, metamod craft, Unveil, Harvest add/remove | 59 |

("Every tool offered" leaves out the fossil sets and the 40 to 67 bench crafts that name a mod the target does not want. R06 was read with a stand-in start price of 1 c, as the audit did.)

What the count says, plainly:

- **The rule holds all of the guide's labels on 3 of 13 routes with one offer a mod (R10, R11, R05) and on 4 with five (R12).** These are routes that already plan at or below their guide.
- **On none of the five failing routes, nor on R06, does it hold the guide's labels, at any K up to 5.** Two reasons. The guide's generic rerolls and additions (Alteration, Regal, Exalted, a Harvest reforge, a fossil set) are far down the list of a single mod (rank 16 to 115), because their worth is in what they do to several mods at once or after another step. And 1 to 7 labels a route are tools with no chance on any wanted mod: a rule that ranks by chance has nothing to rank them by.
- **The tools cannot be taken all together.** They are 44 to 96 offers a route. e10 took 12 of them beside R04's guide and the bound no longer completed.
- The multimod craft ("Can have up to 3 Crafted Modifiers") declares nothing that tells it from a bench craft whose mod the target does not want.

So the seed rule of that direction fails its own test. A seed is still worth having as step 1 of the scheme (it is small, 2 to 8 offers with two a mod, and it is where the plan a player would start from lives on the simple routes), but it does not find what the failing routes need. Nothing search-free that I could state does: which tools pay is exactly what the search is for.

## 4. The schemes compared

Each scheme with what it costs, what was measured, and what it predicts for the five failing routes. "Unchanged" means: as on main today (R04, R24, R14 no plan; R17 97,474 c; R20 35.06 million c).

**A. Keep one kind a round; give a no-plan round a time share; let a stopped round join the base or run again (the line of #1268 and #1273).** Cost: small. It cannot work: with 26 to 36 rounds in 600 s a share is about 20 s, and the one round known to work (e6) needs 45 s for 7 offers; and once stopped rounds join, the base is e1 or e2, whose bound does not complete. Prediction: all five unchanged.

**B. Regroup the kinds: the guide's kinds together, or everything of the simplest model first, or everything but the fossil sets.** Measured: e1 (117 offers), e2 (231), e3 (R24, 84), e5 (30), e10 (19). None builds a complete bound on R04; e3 leaves R24 at 69,483 c. Prediction: all five unchanged. Whole kinds are too many offers, and so is a first tier of single offers.

**C. One search over every offer.** Measured (e4): 23 cases done in 150 s, killed at 16 GB. It needs a floor per method strong enough that the build never touches most offers (#1072, #1073, #1074); that is the long road OR-37 already points at, not this ticket. Prediction: no plan on any of the five today.

**E. A seed chosen without a search, then growth (the direction handed over).** Measured in section 3: the seed misses the guide's methods on all five. Growth "one dependency-closed set of tools at a time" then meets the same wall as B: R04's guide needs the Fracturing Orb, a metamod craft, the Annulment and the Exalted Orb at once, and the union of their families is e10. Prediction before the build is cheaper: R04 a plan of its completed steps, most likely without the metamod craft and far above 32,193 c (not measured: the probe can only set round 1); the other four unchanged.

**S. Few nested steps, each accepted only when its bound completes (recommended for PR 2, section 5).** It is E's growth without the claim that the seed finds the route: step 1 is the seed, each later step adds one family of offers to everything accepted so far, a step whose build does not complete inside its slice is undone and its family listed as not finished, and the answer claims the cheapest of the completed steps' methods. Cost: a rewrite of `_rounds.widen` and of the grouping, about the size of the code it replaces; no new proof (each step is one search with its own complete bound, as a round is today). Prediction: section 6. Its worth today is in what it stops doing wrong (no round eats the limit, no absurd plan from a stopped bound is called a plan of every method, no 30 shares of 9 to 27 s); its worth on the failing routes comes when their builds complete.

**D. A second, cheaper bound over every offer (a relaxed model at the level of the wanted mods), which would both pick the offers and prove a floor for all of them.** Best in theory: it is the only scheme here that could prove a plan against all 11,000 offers. It needs an optimistic model for about 30 kinds with a proof each; the present bound already is such a relaxation and is the thing that does not complete. Weeks of work and its own design note. Named as the long line, not proposed here.

**F. More of the limit for the build before the first plan.** Not a scheme of rounds, a setting inside any of them: today the build stops at a quarter (150 s) "to leave the rest for the search", and the measured search after a complete bound is 3 to 5 s (e6, e7). Measured (the second table of section 2): R24's build on its guide's 10 offers needs 163 s, 13 s past the quarter, and then the plan is 3,658.60 c, below the guide, seen twice. On R04's 19 offers and R17's 11 the build is a third done at 447 s, and on R20 it meets a fault (#1290). So the quarter is wrong whenever a build is about to complete, and it is the whole of R24's "second cause" on this machine; it is not what stops R04, R17 or R20. In scheme S a step's build may take the step's whole slice, since nothing but a complete bound is accepted. Prediction alone (round 1 still by kinds): all five unchanged, because on main no round holds R24's ten offers together.

## 5. The recommended scheme, and the ticket's questions

**The steps.** The offers are split once, from what their actions declare (the reads and adds the floors already use; no kind is named, no guide list exists):

1. *The seed.* For every wanted mod not on the start item, the two offers of least cost over chance of giving it, and the restart. Counted on the 13 targets: 2 to 8 offers.
2. *The rest, in families.* The offers that add to an item without erasing it and the moves between rarities (Augmentation, Regal, Exalted, Transmutation, Alchemy, Scouring); the removals (Annulment, Remove Crafted Mods); the offers that fracture; the metamod crafts and the Matron; the imprint and its restore; the veiled orbs with Unveil and the picks; then each bulk kind whole (the other essences, the other bench crafts, the Harvest crafts, the beasts, the fossil sets last). A family is closed under what its members need (a restore joins with its imprint, a pick with the Unveil and a veiled orb). At most 12 steps a route, against 26 to 36 rounds today.
3. *Order.* The order of that list: fixed by what the families declare (those that add least to the model first, the bulk kinds after the tools, the fossil sets last), the same for every target, so a step's place can be said before a run. Numbered here: 1 the seed, 2 additions and moves, 3 removals, 4 fracture, 5 metamods, 6 imprint, 7 veiled, 8 Harvest, 9 beasts, 10 the other essences, 11 the other bench crafts, 12 fossil sets (a target that is not offered a family has no step for it).

**A step** is the offers accepted so far plus one family: the bound is built for them; if the build completes inside the step's slice, the search runs and the family is accepted (it stays for every later step, whether it made the plan cheaper or not, unless its step proved it cannot: then it is set aside as today); if the build does not complete, the step is undone, the model of the last accepted step stands, and the family is listed in the answer as not finished.

The ticket's questions:

- **Which step first holds each guide's kinds together, and when it runs.** The step of the last family the guide uses, since every accepted earlier family is still there: step 5 on R04, 8 on R20 and R24, 11 on R17 and R14 (their multimod craft sits among the other bench crafts), of 12 (table in section 6). Today it is round 27 to 30 of 30, reached only if every round before it closed. When it runs depends on the slices: a step that completes in seconds, as small ones do (builds of 1 to 2 s on today's early rounds), gives its unused time to the later ones; if every step used its whole slice of a twelfth of 600 s, step 8 would start at 350 s. That is late, and it is why the build's cost comes first (section 7): the scheme has room for a few steps of 40 to 160 s, not for twelve.
- **What bounds the time of a round before the first plan.** Its slice: the time left divided by the steps left, never all the time left. A step that makes no plan inside its slice gives way like any other. `_rounds.py:344` goes.
- **What a step stopped by its slice leaves to the later ones.** Its family, set aside and named, and nothing else: the accepted offers and the model of the last complete step stand. If time is left after the last step, the set-aside families are tried again in the same order with what is left (one pass, no loop).
- **What happens after an absurd first plan.** A plan from a complete bound is not absurd: it is the true cheapest of its step's offers within the gap, and it is shown at once (OR-39), with the claim of section 8. A plan a stopped search holds over a stopped bound is the absurd case (898,973,434,471 c): under S such a step is undone, so its plan is shown only if no accepted step has one, and then it is said to be unproved. Later steps keep their full slices; the share no longer shrinks to 9 to 27 s because there are a third as many steps.
- **How R14 (Awakener's Orb) enters.** The Awakener's Orbs are one family. Their step comes after the metamods (an orb reads a second item, which adds to the model as the imprint does). Their donors are planned when that family's step comes, inside that step's slice, each donor by the same steps on its share of it; a donor whose plan does not complete leaves its orb out with the limit it has today (`no_donor_limit`). The target is searched in steps like any other target from the start, so its other methods are tried whether or not the donors finish. `rounds_apply` no longer returns False for an Awakener's Orb, and the donors no longer take eight ninths of the limit before the target's first search.

**What is dropped of the current scheme.** Groups of one kind ordered by features (`round_groups`' sort). "All the time left" before the first plan (`_rounds.py:344`). `Share` giving way after one search round on a plan from a stopped bound. Shares of the time over 30 rounds. The floors-order pass as a stage of its own after the first plan (255 s on R20, #1241): the order is fixed by the families. The rule that a target with an Awakener's Orb is one search (`_plan.py:1141`). Kept: the envelope search itself, the bound and its rollback to the last complete model, the price cut against the plan in hand, set-aside of a family proved unable to beat the plan, the records the answer is written from.

## 6. Predictions, route by route

"Step" is the first step of S that holds every label of the guide (of 12, numbered as in section 5). "Today's gate" is what the probes measured on the guide's own offers. Costs in chaos; the seven good routes' costs are the audit's fresh run.

| Route | Today (site, 600 s) | Guide | Step | Today's gate on the guide's offers | S before the build is cheaper | S after it |
|---|---|---|---|---|---|---|
| R12 | 40.93 | 40.93 | 8 (its Harvest reforge is third on its mod; 1 with three offers a mod) | none (plans today) | 40.93 expected | same |
| R10 | 38.72 | 38.72 | 1 | none | 38.72 expected | same |
| R11 | 188.03 | 617.28 | 2 (Exalted joins) | none | 188.03 expected | same |
| R05 | 92.77 | 120.56 | 1 | none | 92.77 expected | same |
| R13 | 6,533.66 | 21,509.67 | 2 | none | no dearer expected; not measured | same |
| R08 | 59.22 | 563.46 | 12 (fossil sets) | none | 59.22 expected if its plan needs no fossil set; not measured | same |
| R09 | 19.31 | 353.14 | 12 (fossil sets) | none | as R08 | same |
| R04 | no plan | 91,391.74 | 5 (additions, removals, fracture, metamod) | complete on 7 offers in 42 s; on 19 stopped at 150 s and at 447 s | a plan of its completed steps, most likely not the guide's kind of plan; not measured | about 32,200 (e6, e7) |
| R17 | 97,474.31 | 2,573.42 | 11 (imprint 6, Harvest add/remove 8, multimod craft 11) | stopped: 176 of 1,081 cases at 150 s, 656 of 2,273 at 447 s | unchanged in kind (a plan of essences and currency) | about 2,500 (the plan of 2026-11-17 with no limit) |
| R20 | 35,058,370.95 | not evaluated | 8 (metamod 5, Harvest 8) | stopped: 378 of 1,751 at 150 s; a fault at 404 s (#1290) | unchanged in kind | not predictable: no run has finished its bound |
| R24 | no plan | 4,838.92 | 8 (metamod 5, veiled 7, Harvest add/remove 8) | stopped at 92% at 150 s (8,248.20 c); complete in 163 s when allowed (3,658.60 c) | a plan of its completed steps (today none exists); not measured | about 3,660 (e12, e16) |
| R14 | no plan | 6,888.46 | 11 (metamod 5, multimod craft 11); the orbs are a step of their own | stopped in growth at 152 s (run of 2026-11-17) | searched in steps; a plan of its completed steps; not measured | not predictable |
| R06 | not planned (#1232, #483) | not evaluated | 3 | not probed | not planned until it has a start price | not predictable |

What is and is not measured in this table: the "today" and "guide" columns and every "gate" are measurements. Every cell under S is a prediction: the probes can set round 1 only, so no run of S exists. The seven good routes are expected to keep their cost because the offers their plans use are in the seed or an early family; whether each does is the first thing PR 2's table shows, and "no route of the seven is dearer" is in its Done-when.

## 7. The second cause on R14 and R24, and the order of the work

The ticket asks to trace why R14 and R24 stay 15 to 100 times above the guide even with the guide's kinds in round 1. It is not unknown: on both, the bound's build does not complete in its quarter of the limit on the guide's own 10 to 13 offers, so the search is led by a figure far below the truth. R24: e11 above (and on a 4-core GitHub runner on 2026-11-17: 35,114 cases, 8,337 done, starting figure 18.48, first plan 1.68 million c, and none of the 23 builds of the run complete); allowed to finish, its build takes 163 s on the server and the plan is 3,658.60 c (e12, e16), so on R24 the cause is fully traced. R14: build stopped in growth at 152 s, starting figure 0.108; not probed further here. R17 and R20 are the same as R14 (e8, e9, e15, e13). This is #1158, whose three children name where the build's time goes: thousands of members a case under an action that reads everything (#1192: R20's beast swap, R14's donors), bench-craft pairs asked again at every member (#1193), and the same exact draws made again by every round (#1194). A comment on #1158 carries these facts. No new issue is needed.

**#1276 does not fix it.** The rounds decide which offers a search holds; these builds do not complete on the smallest set of offers that holds the guide's route.

**Order.** First #1193, #1192, #1194 (in the order #1158 gives them), accepted by a check this note adds to #1158: with round 1 set to the guide's labels (the probe tool does it without a code change), the bound's build completes inside its share on R17 (11 offers), R20 (7, and without the fault of #1290), on R14's target with the guide's 13, and on R04's 19 offers of e10 (R24's 10 complete already, in 163 s). The sets S will really hold are larger (20 to 60 offers at the step of the guide's last family), so that check is the least the builds must reach, not the end. Then PR 2. Reasons: S is gated on complete builds, so before them it has almost nothing to accept on four routes; its acceptance table could then only say "second cause #1158" on four of five rows; and a rewrite of the rounds risks the seven good routes for one uncertain route. If the dispatcher wants PR 2 first all the same, it is safe to build (nothing in it depends on the build's speed), and its table must then be read against the "before" column of section 6.

## 8. What the answer may claim (OR-38, OR-39, OR-40, OR-13)

- **OR-38 (the best route under the rules given).** A step's search with a complete bound proves its plan within the stated gap of the cheapest plan of that step's offers. That is all a run proves. The answer says: "the cheapest of the methods of the steps that finished, within X%", lists those methods, and lists every family set aside or not tried with the lowest cost its floor allows ("a plan that uses these was not ruled out and may cost less"), as `rounds_limits` does today. "Within 1% of the cheapest of every method" is said only when the last step held every offer and completed. Never again one step's gap on the whole plan (#1182, #1186).
- **OR-39 (a plan is shown as soon as one exists).** The first accepted step that has a plan shows it; a later step replaces it only by a cheaper one. A plan from a step whose bound did not complete is shown only when nothing better exists, and is marked unproved (its cost is exact, its optimality is not claimed even among its own offers).
- **OR-40 (the limit is a setting of the machine).** The slices are shares of the run's own limit, whatever it is; the floor of a slice is a share of the limit too, not a number of seconds. No family is dropped to stay under the limit: one that did not fit is named (OR-13, OR-37). On a faster machine or a longer limit more steps complete and the same code gives the wider proof.
- **OR-12.** No count of offers and no named kind cuts anything: K = 2 in the seed decides only what is searched first, every offer has its step, and "accepted only when the bound completes" is the bound's own stop-and-say-so net.
- **Proof obligations of PR 2.** (1) A step's plan is proved only against its own offers: by construction, as a round today. (2) Undoing a step leaves no trace in the next one's bound: the bound is built per step from the accepted offers (the rollback to the last complete model exists inside one build; across steps nothing is shared but the plan in hand as an upper figure, which is sound for any set of offers that holds its offers). (3) The price cut against the plan in hand stays sound when the offers grow (it is today). (4) A donor planned inside the orb's step gives the orb a price that is the donor plan's cost, an upper figure; the orb's floor must use the donor's lower figure, as `whole_lower` does today.

## 9. Tickets

Read from their titles, the audit and #1158's comments; PR 2's author reads each before closing it.

- **Replaced by PR 2** (their subject is a part of the scheme that goes): #1268 (should round 8 get R04's time), #1273 (a stopped round never joins the base), #1241 (the floors-order pass takes 228 s), #1275 (that pass has no net on a group's setup), #1167 (R08 and R09: the bench round gets 0 s), the rounds part of #1260 (R17: the essence round sorts 13th and starves; its crash in the risk step "the start state cannot finish" is a separate fault and keeps a ticket), the "no-plan round is still carried" half of #1097 (its foresight half stays), and the "rounds" Done-when of #1069.
- **Answered by this note, closed by the builds** (their cause is the bound's build on the guide's own offers; they close when the 13-route table shows the route): #1182 (R17), #1186 (R20), #1142 (R04, R14, R20, R24 no plan).
- **Kept, and first in the order:** #1158 with #1193, #1192, #1194, and #1290 (filed by this note: R20's build meets a fault at 404 s).
- **Kept:** #1072, #1073, #1074 (floors per method: the road to one search), #1267 and #1232 (R06), #914.

## 10. Plan for PR 2

Through the planner module and the one envelope search; nothing under `cli/`.

1. `planner/_offer_kinds.py`: `leaf_chances(...)`, each offer's chance on each open wanted mod from `reach_bound`, `add_bound`, `declared_add_bound` and `finishes` (what `seed.py` does from outside, with the fossil sets read from their class's declared bounds, `declared_pbars`); and `families(...)`, the split of section 5 from `Reads` and `Adds`. No action class imported.
2. `planner/_rounds.py`: `round_groups` gives the seed and the families; `widen` becomes the steps (slice = time left over steps left with a floor that is a share of the limit; accept or undo by the build's completeness, which `EnvelopeInfo` already reports as `bound_stopped`; one second pass over set-aside families when time is left); `Share`'s special case before the first plan and the floors-order pass after it go; `rounds_limits` words the claim of section 8.
3. `planner/_plan.py`: `offer_groups` and `widened_plan` follow; `rounds_apply` stops refusing a target with an Awakener's Orb; `search_net` loses the "all the time left" case.
4. `planner/_awakener.py`: `solve_donors` is called from the orb family's step with that step's slice.
5. Tests, through the planner's entry, counted in states (`Budget.in_states`), no clock read: a hand-built target whose cheapest plan needs two tools from two families together (neither pays alone) is found at the step of the second; a family whose build cannot complete in its states share is undone and named, and the plan and its claim are those of the last accepted step; the answer never says "of every method" when a family was set aside; a target with an Awakener's Orb is searched in steps and its orb left out with its limit when the donor does not complete; the seed of each of the 13 reference targets is counted (size, and the offers of today's plans of the seven good routes inside the seed or an early family) with no search. Modules that plan a real route in CI set `CLASSIC_OFFERS = True`.
6. Acceptance: the 13-route table as the site plans (`benchmark_routes.py ... --net`) on the server, two runs, load written beside the timings: no route of the seven is dearer; R04, R17, R20, R24 no dearer than twice the guide, or per route the measured gate and its issue; R14 searched in steps. Then the heavy benchmark's record (this ticket owns it until it lands).

## Not done, not verified

- No run of scheme S exists; section 6's S columns are predictions.
- R20's and R06's guide costs are still not evaluated by any run.
- R14 was not probed on the server.
- The seed test read fossil sets only through the 30 of least declared floor and the guide's own; a fossil set's rank on a wanted mod (67, 77) is among those.
- The families of section 5 were counted from the offers' declarations in the seed test's output, not built as code; the multimod craft has no declaration that sets it apart from other bench crafts, so it would join with "the other bench crafts" unless PR 2 finds one.
- Every timing is one machine under a load of 1 to 11 (about 6 while four to six probes ran together); R04's 7-offer run was seen twice with the same plan to the cent.
