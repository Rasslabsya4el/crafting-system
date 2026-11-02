# Codebase audit: where the system's meaning silently differs from the game and the owner (ticket #396)

Date: 2026-11-02. Read-only audit of `main` at `86aa0b0`, plus the route pages built on GitHub for all ten benchmark routes.

## Why

On 2026-11-02 the owner opened three route pages (R05, V01, R10) and found faults in minutes. About 31,000 tests had passed on all of them.
- R05 finishes "Life T1 or a resistance T2" with bench crafts.
- V01 shows eight identical Regal steps.
- The R05 buy step prices any ring, not the target's Amethyst Ring.

He asked for a codebase-wide search for the causes, and for fixes per class of fault, not per case.

## Method

Ten read-only sweeps ran in parallel, each from one brief (`2026-11-02-codebase-audit/BRIEF.md`). The brief holds the owner's rules and the definition of a fault: the system's meaning silently differs from the game, from the owner's rules or from its own docs.
- Eight sweeps covered the code by area: targets, actions (two sweeps), state, solving, planning, presentation, and inputs.
- One sweep covered the tests and the process.
- One read all ten benchmark routes as a crafter would. It built the pages on GitHub and checked the numbers with its own Monte Carlo.

Each finding carries its place, evidence, impact, origin (commit, ticket, brief) and the general mistake behind it. The full findings are in `2026-11-02-codebase-audit/*.md`: 174 entries, of which 31 are high impact. The main chat then grouped them, re-counted the main patterns in the code, and traced each class to its root in the code and in the process.

## The owner's rules (the spec this audit measures against)

- An unstated tier is the top tier the item level allows, rolled, not from the bench. A mod forced by an essence or a bench craft is exactly that mod. A bought mod is the tier priced on the trade site.
- A page shows every in-game step and hides none. It shows each player step once, uses one mod format, and never shows the same route twice.
- Trade prices: instant buyout only, mean of the cheapest few, refreshed by the system itself.
- Search like a crafter: detail no later decision reads is not tracked. The answer is exact among realistic routes, with no hard-coded cut-offs, and a cut says what it still guarantees. An interval answer is useless to him.
- All known evidence is modelled up front. An unknown gets the best estimate and an approximate mark. The owner is never asked mid-plan.

These rules were never written down in the repository. That is itself a finding (class 7).

## What the numbers say about the ten routes

The engine's arithmetic holds: an independent Monte Carlo matches R05, R10, R11 and R12. The faults are in what the numbers mean.

| Route | Planner mean | Given-route mean | Verdict |
|---|---|---|---|
| R04 | no page (runner killed after 18 min) | none | unknown |
| R05 | 12.2 c | 135 c | artefact (bench crafts accepted as T1/T2) |
| R08 | 104 c | 1,810 c | unknown: rests on an outlier 0.2 c Prismatic Fossil, not the guide's craft |
| R09 | 75.1 c | 1,300 c | unknown: same outlier |
| R10 | 128 c | 128 c | numbers right; the goal is stricter than the guide ("preferably 70 Life" read as T1: ~46 c at 70) |
| R11 | 1,110 c | 1,110 c | numbers right; the goal is stricter than the guide |
| R12 | 56.6 c | 56.6 c | trustworthy (start mod tier written 3, the data says 7) |
| R13 | 6,310 c | 12,100 c | plausible; Scouring is withheld (−7.5% with it); planned at level 86, not the floor 84 |
| R14 | 5,800 c | never finishes | unknown; the page has 87,272 steps (151 MB), 75% of them the same Restart card |
| V01 | 866 c | none | unclear: 99% of the cost stands on two hand prices; 11 rows for 3 player actions |

## The seven classes

Each class lists its instances (finding ids), its root in the code, and its root in the process. The counts in brackets were re-measured on `main`.

### 1. Values with no source answer game questions (placeholders and defaults)

The type demands a value where the game has none, or where nobody knew the answer. The author fills in a number, and later code reads that number as a fact.

- **"No tier" read as tier 1** [14 sites in `src`, 25 in `tests`, 4 separate constants: `bench.py:57`, `beasts.py:59`, `influence.py:114`, `floor.py:57`].
  - Bench crafts, essence-only mods (1,322 of 2,200 forced mods have no tier, 614 are weaker than T1), veiled picks, beast aspects, Elevated mods and Awakener donor mods: TARGETS-1, STATE-1, ACT1-1/2/3, ACT2-4/13, PLANNING-16.
  - It came in with the first compressed state (#24, `55f8109`), before crafted mods existed. #56 then wrote `CRAFTED_TIER = 1 # Item needs one, from 1`.
- **"Lowest roll" stands for a roll** in simulated results (Embers, Conflict, Pick): ACT1-6, ACT2-12.
- **A price of 0, or no `start_price`, means "free" and also "cannot be bought again".** This switches restart off; V01 gives 186 c at 0.01 c and "no policy" at 0. See PLANNING-13, SOLVER-7, TARGETS-8, INPUTS-8.
- **An "empty rare" start item that does not exist in the game**, with the Alchemy folded into the price: TARGETS-9, PLANNING-9, INPUTS-5. **The epsilon "free" cost** is recognised later by its value: SOLVER-11.
- **Defaults that decide game questions with no mark:**
  - the requirement default "any tier, any source" (ADR-0008, written before the owner's rule): TARGETS-2;
  - beast level 83, a rare beast at 1 c: ACT2-2;
  - the recombinator cost constant, with a default Gold price that is 90% of it: ACT2-8;
  - previous-league prices copied unscaled: INPUTS-10;
  - one white socket assumed: ACT2-20.
- **Weak evidence admitted as exact** [15 claims say "APPROXIMATE", "UNVERIFIED" or "not rechecked" in their text with no `approximate: true`]: ACT1-7, ACT1-9, ACT2-6/7, INPUTS-15. In addition, 25 claims are verified at 3.29.0.3 against the 3.29.3.3 pin: ACT1-14.

*Code root:* the item and mod model cannot say "not applicable" or "unknown". `ExplicitMod.tier` is an int ≥ 1, values are required, and a price is a float. The model also has no mod origin (STATE-10), so the question "is this the natural T1?" has no place to live.

*Process root:* PR #74 flagged the crafted tier placeholder in its prose, and no ticket followed (TESTS-14).

### 2. One fact written by hand in several places, with nothing reconciling them

- **The start item is described twice:** the target's `base`/`item_level`/`start_item`, and the buy spec. They disagree on R05, R09, R12, R14 and R04 (INPUTS-1/6, PLANNING-10, ROUTES-7, TESTS-7). The "reconciliation" test replays the same recorded search (TESTS-7).
- **Start-mod tiers and values are typed by hand** where the data knows them; R12 says T3 for a T7 mod, and a test pins the wrong number: TARGETS-5, INPUTS-9, PLANNING-11, ROUTES-10.
- **One price key per base name**, while several bases share a name; the target side uses an id: INPUTS-6.
- **The tier constant is copied four times;** the "lowest value" helper is written in six places: ACT2-19, STATE-13.
- **Docs and code disagree:**
  - the bench item-level gate is documented and not enforced, and the floor still applies it: TARGETS-7, ACT1-11, INPUTS-11;
  - ADR-0007 still describes a one-week trade filter: INPUTS-17;
  - ADR-0061 and the glossary say the level is a floor the planner uses: PLANNING-8, ROUTES-13;
  - the glossary gives mods an origin the type lacks: STATE-10;
  - the recombinator table is not reproduced by its own counts: ACT2-9.
- **The owner's tier rule lives as comments in 14 target files,** and they contradict each other: R12 says "top tier" on line 16 and "every tier counts" on line 28 (TARGETS-2).

*Code root:* derived facts are typed instead of derived. There is no single description of the start item from which the buy query, the price key and the planned item all follow.

*Process root:* each ticket wrote its own file for the slice it needed (#26 R12, #60 R05/R10/R11, #63, #70). No check compares the files.

### 3. Built, but not wired: capabilities no plan can reach, settings nothing reads

- **30 action kinds are `planner=False`.** No plan can use:
  - Eldritch orbs, Embers and Ichors, the Blessed Orb and catalysts, because targets with implicits or quality are refused;
  - the Awakener's Orb and the recombinator, because there is no two-input action in planning;
  - Imprint, Dominance, influenced Exalted, sockets, the Lock, Foulborn orbs and strands.

  The Vaal Orb and Bloodstained are planner kinds that no useful plan can use (ACT2-1). See also ACT2-11.
- **Alchemy and Scouring are withheld for graph size, with a stale reason:** ACT1-4, PLANNING-2.
- **Settings accepted and documented that nothing reads:** `price_source`, `price_gap_percent`, `--price-source`, `max_imprints`, `recombinator_junk_craft`, `memory_strands` (PLANNING-6/7).
- **The market rule** (instant buyout, age, sample size) is a tested module that the planner never calls: INPUTS-2.
- **The item-level floor** is built, and no code calls it: TARGETS-3, PLANNING-8, ROUTES-13.

*Code root:* the planner entry (`make_plan`, `offers_for`, `allow_inputs=False`) is a separate gate that each mechanic ticket left closed.

*Process root:* tickets were cut by layer: mechanic, then state, then "planner later". "Done when" tests the piece in isolation, and nothing measures "a benchmark route uses it". The map's integration tickets (#159, #223, #231, #277, #296–#298, #351/#354/#359) stand at the end of the chains, so each closed ticket looked like progress that no plan could see.

### 4. Silent limits: a restriction applied, with the reason absent or stated where nobody reads it

- **A target with no `actions:` key is planned without the opt-in kinds and the metamods,** and nothing says so. Only the explicit case prints a "left out" line: PLANNING-1.
- **The route page never shows what was left out:** the actions list, unpriced drops, pruning and the plan note. They go to the text report and JSON only; R12's page has none of its 19 drops (PLANNING-3, ROUTES-5).
- **An action with an unpriced resource is dropped, not estimated and marked:** PLANNING-4.
- **A model gap is reported as a game refusal:** `OutOfScopeError` is caught as "the game refuses it" at eight sites and in the report text (SOLVER-8, PLANNING-5).
- **Several limits share one message or a stale one:**
  - the p90 cut, the memory limit and donors in a cycle all give the message "not resolved on the grid (#190)" (SOLVER-6);
  - R04 and R14 are refused at default flags with a stale "cannot be solved" text (SOLVER-3, ROUTES-11).
- **The approximate status is written in prose,** not in the field the report reads (15 claims; ACT1-7, INPUTS-15).
- **Steps the guide or the game has are left off the page** with no mark: the hidden Alchemy, the catalysts, R11's finishing craft (ROUTES-4).

*Code root:* limits are recorded where they are raised (exceptions, `plan.note`, text lines), not carried as data with the answer. One exception family covers both "the game says no" and "the model cannot say". The page was built from the policy alone.

*Process root:* the page tickets (#78, #96) were judged on R10 alone; the "report, route page and given routes" ticket (#298) is still open.

### 5. Planner internals shown as the game: in the state and on the page

- **The state keeps detail no decision reads:**
  - 697 of V01's 786 states are dead ends that differ only in junk; 91 states remain when merged exactly (STATE-4);
  - reroll-only models keep a status the next reroll erases: R12 33→2, R10 425→2 (STATE-6);
  - V01's eight Regal states are the junk suffix's family type, and merging them is approximate, at goal chances 0.88%–0.95% (STATE-5, ACT1-15).
- **The solver computes the exact equivalence classes and the page discards them:** V01 has 248 states in 30 classes (SOLVER-2).
- **A page "step" is a class of states with exactly equal chances:**
  - V01 shows 11 rows for 3 player actions;
  - R14 shows 87,272 steps (151 MB);
  - the owner's spec said "same action", and the "same chance" rule was added in `_route_flow.py` and pinned by a test.

  See PRES-1, ROUTES-15.
- **A class representative is printed as the object.** R05's bench step "+(26-40) Life" draws `DexMasterLifeCrafted1` "+(35-44)", a mod no bench option adds; #96 fixed this for fractured mods only (PRES-2, ROUTES-1). R13's damage leaf is drawn as a mod a belt cannot hold (TARGETS-6).
- **A join of states is drawn as one item** ("in some", "tier too low", 8 suffix lines): PRES-8. **A cost-to-go is labelled "On failure":** PRES-6. **"At least 1 of 4" is flattened into four mod lines:** PRES-7.
- **Displays were not extended when the model grew:**
  - the target card hides `min_roll`, `not_crafted` and `corrupted` (PRES-3, TARGETS-6);
  - the cards after a step drop quality, implicits, enchantment, imprints and strands (PRES-5).
- **Project vocabulary reaches the player:**
  - claim ids, ADR and ticket references, and "the main chat" (46 of 117 approximate reasons): PRES-9, ROUTES-12;
  - internal price keys as titles: INPUTS-7;
  - mod ids in labels: ACT1-5/12.
- **The provenance of a price is dropped at the page:** a 99-day-old Mirage price and hand prices all appear under "league Allflame, fetched 2026-10-31" (INPUTS-3, ROUTES-8, PRES-4).

*Code root:* there is no model of a route as a player sees it, meaning actions, branches and what the item is at each point. The page is a rendering of the policy table over states. The state's granularity was chosen for exactness (ADR-0009: "exact, therefore tracked"), never for what a later decision reads. Liveness and minimality were never asked (TESTS-8).

*Process root:* the owner's "crafter-like search, untracked detail" (2026-11-01) reached a research ticket (#312), but no build ticket. Page goldens were accepted by regeneration.

### 6. The checks compare the system with itself

- **Layer-1 oracles share the code under test:** `compress`, `build_pool` and the tier default (STATE-2). The contract suite compares each action with its own `outcomes`, on three members per kind, on amulet fixtures, with a goal that has no tier (ACT1-10).
- **`--verify` is independent in code but shares the meaning:** the actions, the tier tables, `Target.is_met_by` and the prices (SOLVER-1, TESTS-9). The auditor reproduced it: a bench craft met "Life T1", and `--verify` reported that it agrees.
- **"Solver mean ≤ given route mean" can only pass when the model is wrong.**
  - It is one-sided, and the given route is a restriction of the planner's own search, so it passes by construction.
  - It is vacuous for R04 and R14, whose given routes never finish.
  - R05's ratio fell 0.71 → 0.19 → 0.09 over three PRs without a comment.

  See PLANNING-12, ROUTES-2, TESTS-4.
- **The golden pages are accepted by their own regeneration:** 43 commits, single-line HTML sections of up to 15 KB, and only R10 was ever shown to the owner (TESTS-5, TESTS-13, PRES-10/11).
- **The two tests written to guard the owner's rules cannot fail on the headline fault.** One passes at any `min_tier`; the other whitelists the current variants (TESTS-3, PRES-12).
- **The one independent mechanics oracle, Craft of Exile, is skipped in CI and stale,** with a +2% essence gap accepted under a 5% threshold (TESTS-10).
- **The test mass is where exact oracles are cheap, not where the risk is.** 50.7% of tests check solver maths on random graphs, and about 0.56% plan a real route. The joints game → claim, guide → target, target → goal, buy spec → start and plan → page have no oracle (TESTS-1).

*Code root:* there is no independent oracle layer. Every expected value is computed by, or copied from, the code it checks.

*Process root:* the oracle is written by the implementer in the same ticket, and reviewed by the same model family against the same ticket text (TESTS-17).

### 7. The owner's rules live where the builders do not read them

- **The rules are not in the repository.** They exist in the main chat's memory, one comment on #96, and comments in target files. ADR-0008 still states the opposite default, and the tests follow the ADR (TESTS-6, TESTS-15).
- **Briefs and the checker carry the ticket text only.** Of 37 tickets after 2026-10-31 that touched targets or pages, 2 carried the rule (TESTS-6).
- **Findings are parked in PR prose:** 33 of 153 PRs, PR #74's placeholder note among them (TESTS-14).
- **A rule was applied past the cases it was made for, with no mark.** "Top tier" was applied where the guide states a number or a soft wish: R10 "preferably 70 Life", R11 "you are happy with", and R04/R14 exalts turned from 100% into 13%/20% and 55%/10% (ROUTES-3, PLANNING-14).

*Root:* process. The definition of "right" has a single holder, the main chat, and no file the builders, the checker or the tests read.

## How the classes connect

Class 7 is upstream of the rest.
- With no written spec, there is no independent oracle (class 6).
- With no oracle, placeholders (class 1), duplicated facts (class 2), silent limits (class 4) and internals on the page (class 5) all pass.
- Class 3 has its own process root: the cut by layer, with "done" meaning "the piece works alone".

## Rebuild proposal, per root

The order matters. First the spec and an oracle that fails on today's code, then the rebuilds, which that oracle then shows working.

1. **The owner's rules as a document of record** (class 7).
   - Write `docs/owner-rules.md`, one rule per line with an example and a counter-example. Amend ADR-0008 and the glossary to match.
   - Briefs, the checker and target files cite it. The checker reviews against it, not only against the ticket.
   - Open points in a PR become issues before the PR lands.
2. **An independent oracle layer** (class 6). New code that imports nothing from the planner's reading:
   - an owner-rules check of every route's goal states and of every page;
   - a two-sided plausibility check against the guides' published odds and costs;
   - recorded Craft of Exile frequencies for the core mechanics, run in CI;
   - a reconciliation check for every fact that remains in two places.

   Golden changes show a readable before/after for review. Today's faults become failing tests first.
3. **Mod origin and "no value" in the item model** (class 1).
   - A mod carries its origin: rolled, crafted, essence-forced, fractured, veiled or Elevated. A requirement is judged on the natural ladder by its values, so a bench Life 35-44 is not T1.
   - Remove every default tier, every invented start item, and the "price 0 = free = no restart" coupling. A start price is required.
   - Claims carry `approximate` as a field, checked against their text.
4. **One description per fact** (class 2).
   - The target is the only description of the start item. The trade query, the price key (by base id) and the planned item derive from it.
   - Start-mod tiers derive from the data.
   - Docs that state behaviour are checked by a test, or removed.
5. **An answer envelope** (class 4).
   - Every answer carries its limits as data: kinds left out and why, unpriced items, model gaps (a separate error type from game refusals), cuts with their guarantee, and price provenance.
   - The page and the report must render all of it.
6. **Minimal state and a route model** (class 5).
   - Merge exactly the states no later decision distinguishes. The packed solver already computes the classes (#312, SOLVER-2, STATE-4/6).
   - Build a route model of player actions with named branches from the minimised policy, and render the page from it in player words.
   - Any further merge that is not exact needs the owner's word (question below) and states its guarantee.
7. **Done means reachable** (class 3).
   - A mechanic ticket is done when a benchmark route can use it end to end. A reachability report lists which kinds every plan can reach and why not.
   - Re-cut the map so that each mechanic carries its own planner-entry slice.

## What this touches

- **Chain B (#70 and onward)** compares planner and guide numbers. Those comparisons mean nothing until classes 1, 2 and 6 are rebuilt, so the chain stays paused.
- **The state work just landed** (#152, #155, #158; #214, #217 in flight) is sound in its own terms. It shares class 1 (Elevated tier 1, donor tier 1) and class 3 (unreachable until the planner entry opens).
- **Every golden page and every benchmark number** will change after the rebuild of classes 1, 2 and 5.

## Questions only the owner can answer

- **Soft wishes in a guide.** When a guide gives a number or a soft wish ("preferably at least 70 Life", "you are happy with"), does the target take the guide's words or the top tier?
- **Non-exact merges.** Do we merge states whose effect on the answer is small but not zero (V01's 0.88%–0.95%), if the page states the bound?
