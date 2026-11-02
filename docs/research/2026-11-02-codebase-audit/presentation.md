# Audit #396: presentation (what the owner sees: the report and the route page)

Area: `src/crafting_system/cli/` `_report.py`, `_route_view.py`, `_route_html.py`, `_route_flow.py`, `_route_card.py`, `_route_report.py`,
`_route_trade.py`, `_interval.py`, `_start_report.py` (+ `_marking.py`, `_main.py` where they decide what is printed) and every file in `tests/golden/`.
Read-only. Real data: `local/cache/repoe-fork/3.29.3.3`. Scratch snippets live outside the repo (session scratchpad), nothing in the repo changed.

How I read the goldens: I stripped the 16 HTML pages to text (card by card) and read all of them, the V01 text report and JSON, and the interval
text/JSON. Counts below (rows, repeated lines) come from those stripped files or from the golden JSON, not from memory.

Legend: CONFIRMED = I ran it or read it unambiguously; SUSPECTED = reading only.

---

## Findings

### PRES-1: a route "step" is a class of planner states (a bisimulation on exact chances), so one player action is drawn as many rows   [CONFIRMED] [impact: high]
- Where: `_route_flow.py:1-35` (docstring), `:105-230` (`build_flow`, `_refine`: the key is `("action", label, cost)`, then refined until every state of a block has the same exact `Fraction` chance into every block); `_route_view.py:564-575` (`build_section`: one row per flow step); `_report.py:325-368` (the text tree is one line per *state*, `S1..Sn`).
- What it does: two states with the same action are the same step only when their chances into the same steps are equal to the last digit. V01: `Orb of Augmentation` leaves the magic helmet with one of 8 different junk suffixes; each such state has its own Regal chance (0.884% to 0.949% to reach Life T1, because the suffix's family changes the size of the pool), so each becomes its own step. The page has **11 rows for 3 player actions** (buy at the vendor, Augment, Regal ... scrap and restart). 7 of the 11 rows repeat an earlier row's title and item card word for word (my row-duplicate scan of all 16 goldens: V01 7, every other page 0).
- What it should do: owner's rules ("a step is a player step, not a planner state"; "never show the same route twice"; "detail no later decision sees is not tracked at all"). The owner's accepted spec (issue #58 resolution, copied into #78's task): "a step stands for a set of compressed states **only when the policy takes the same action in all of them**; look-alike states that need different actions branch". Different *chances* with the same action were never part of that rule.
- Evidence:
  - V01 golden JSON has 88 policy states. Their (description, action) pairs: 40 "rare ... 2 prefixes, 1 suffix" -> restart, 31 "rare ... 1 prefix, 2 suffixes" -> restart, 8 "magic ... 1 prefix, 1 suffix" -> Regal Orb, 8 "rare ... too weak" -> restart, 1 "magic ... 1 prefix" -> Augmentation: **5 distinct pairs, 3 distinct actions**. The solver solved 786 states for it (`states_solved`).
  - I re-derived the steps from that JSON (`t_partition.py`, scratchpad): the code's rule (exact chances) gives 10 steps (+ the buy row = the 11 rows of the page). Dropping only the chance from the refinement key (action + cost + *which* blocks the transitions reach) gives **3 steps**: Augmentation, Regal Orb, Restart. Grouping by (action, description) gives 4.
  - Page: rows 3 to 10 are all "Regal Orb", Goal "+(130-144) to maximum Life · T1", same item card, differing only in "Chance per use 0.88-0.95%" and "Uses on average" (38.4, 11.4, 6.54, 34.1, 2.13, 8.53, 1.85, 4.27 = 107). Row 2 (Augmentation) says "the item of step 3: 36%, the item of step 6: 32%", and files the other six Regal rows (11%, 6.1%, 2%, 8%, 1.7%, 4%) under **"On failure"** (see PRES-6).
  - The unit test pins the behaviour: `tests/test_cli_route_flow.py:73` `test_look_alike_states_with_the_same_label_but_different_chances_are_two_steps`, `:330` `test_the_steps_are_the_coarsest_grouping`; ADR-0015 line 5 was written as "the same action ... *and* the same chances into the same steps".
- Impact: every page of a policy with a junk-tracking abstraction (bench crafts offered, or vendor/Augmentation starts). R10/R11/R05 (2 to 5 rows) hide it; V01 is the first big policy. The text report has the same fault one level down: 88 `S` states, 79 of them "restart" in three identical descriptions.
- Origin: `a0c7995` (#78, 2026-10-31) "group states by action and exact outcome chances" -> ADR-0015 text; #78's Done-when tested R12 and hand-made 1-3 step policies only; V01 (#331, `ef74f8b`, 2026-11-01) committed the 11-row page as a golden ("its golden (text, JSON and route page) is committed") with no owner look.
- Pattern: a planner-internal equivalence (exact bisimulation) drawn as if it were what the player does.

### PRES-2: the item card after a bench craft shows a different mod from the craft: the canonical id of a class of mods is printed as if it were the mod   [CONFIRMED] [impact: high]
- Where: `_route_card.py:458-460` (`_StateReader.crafted`: `mod_text(self.data.mods[slot.kind])`), `_route_view.py:282-284` (`gains()`: `self._mod(slot.kind) + " · crafted"`), `_report.py:117-122` (`describe_state`, same); the canonical id comes from `abstraction/_kernel.py:1012-1030` (`_canonical_for`: "the smallest id among the mods of the same families, side and domain that give `contribution`").
- What it does: R05's page row 3 is titled "Benchcraft: +(26-40) to maximum Life" and its Goal line and its item card say "+(35-44) to maximum Life · crafted". Run on the real data (`t_canon.py`): the craft is `EinharMasterIncreasedLife2` = +(26-40) (the bench option that exists for rings, 6 Orbs of Transmutation); the slot it makes has kind `DexMasterLifeCrafted1` = +(35-44), the alphabetically smallest of all crafted Life mods. `DexMasterLifeCrafted1` is the add-mod of **no** bench option in `crafting_bench_options.json` (0 of 765). The player is shown a craft that cannot be made.
- What it should do: a state may keep a class; the page must draw what the player has: the mod of the action just taken (the bench action names it: `adds.named`, which the row title already uses) or an honest "a crafted Life mod" with the range of the real craft. Owner rule: one mod format, exact mod/tier.
- Evidence: golden `real_r05.html` rows 3 and 4: title (26-40) vs Goal/card (35-44) (title and card agree for Fire Resistance, (16-20), only because the alphabetically first crafted Fire mod, `DexMasterFireResistanceCrafted1`, happens to roll the same (16-20) as the real `HelenaMasterFireResist1`). The first R05 golden (`9ca2c85`) already had "+(35-44) to maximum Life (crafted)"; it survived all four regenerations.
- Also on the same page: target "Life T1 +(100-114)" is met by a row "+(35-44) ... crafted" and nothing says that a crafted mod fills a "T1" line (that is the seed CRAFTED_TIER fault; the page prints both numbers side by side and does not flag it).
- Impact: any route with a bench craft whose family has several crafted mods (Life, resistances, damage): the card text is the lexicographically first member of the family.
- Origin: #60 (`3c123fc`, `describe_state` takes `data.mods[slot.kind]`) and #78 (`120dc39`). #96 found the same representative problem for **fractured** mods ("R10's fractured Movement Speed read as '5% increased Movement Speed for each nearby Enemy ... essence only' because the compressed state names a representative of the tier class") and fixed `_fractured_row` and `_family_row` only (PR #131 text, "Found on the real pages (1)"); `crafted()` was not touched.
- Pattern: a canonical representative of an equivalence class read as meaning (fixed in two of its three display sites).

### PRES-3: the target card does not show `min_roll` or `not_crafted` (nor `corrupted`/`allow_corrupted`): requirements that decide the cost are invisible   [CONFIRMED] [impact: high]
- Where: `_route_card.py:352-358` (`card_of_target.add`: only `mod_ids`, `min_tier`, item level reach `_leaf_slot`; `Slot(text, "wanted", (), note)`), `:364` (`_properties(..., "", quality)`: corrupted always ""); `_route_view.py:240-247` (`leaf_text`, same data).
- What it does: ran `card_of_target` on a Life leaf with `min_tier=1, min_roll=(50,), not_crafted=True` (`t_target_card.py`): it prints `+(40-54) to maximum Life · T1` and nothing about "roll 50 or more" or "not crafted". Implicit requirements do show their roll (`_wanted_implicit`: "roll 30 or more"), explicit mods do not.
- What it should do: the card is the goal; whatever the goal checks must be on it (owner: "every detail is named", #58 round 1).
- Evidence: examples using them: `not_crafted: true` in r04, r05, r08, r09, r10, r11, r13, r14, v01 (so the V01 and R10/R05 target cards leave out that a crafted Life/Attributes does **not** count), `min_roll` in r03, r06 and `r10-fractured-boots-70-life` ("Life roll 70"; its page would read exactly like the plain R10). The text report does print "(tier 1 or better, not crafted)" (`leaf_labels`), the page does not.
- Impact: 12 of the 14 example targets; the owner reading a page cannot tell that "Life T1" there means "rolled, not bench-crafted", the very distinction PRES-2 and the seed hinge on.
- Origin: `not_crafted`/`min_roll` exist since #19 (`f6861f1`, 2026-10-30); the card (#78, `120dc39`, 10-31) was written against `mod_ids`+`min_tier` only and never extended.
- Pattern: display written against the fields that existed that day and never revisited when the model grew.

### PRES-4: the buy row hides what is searched and what the price is made of   [CONFIRMED] [impact: high]
- Where: `_route_trade.py:74-90` (`_accepts`), `_route_view.py:417-426` (`start_accepts`), `:461-472` (`buy_row`), `:384-391` (`cost_lines`), `:444-459` (`vendor_row`), `_main.py:103-106` (`stale_warning` goes to stderr only).
- What it does:
  1. `_accepts` never prints `spec.base_type` / `spec.category`. R05: card "Amethyst Ring", Accepts "Rare, item level 75 or more, no influence, not corrupted, fractured: +# to all Attributes (at least 13)", and the decoded link in the golden is `category: accessory.ring` with **no** `type` (R10 and R11 do carry `type: Sorcerer Boots / Lion Pelt`). So the price (2.6 c, "mean of the 5 cheapest instant-buyout listings of 10 fetched, 602 on the site" in the price file) is for any ring while the page draws an Amethyst Ring and the planner plans for one (the seed). R12 is the same (Paua Amulet card, `accessory.amulet`), and R12's Accepts says "item level 75 or more" while the card and plan say "item level 84".
  2. `cost_lines` drops the source of every price (`for name, count_, chaos, _ in priced.parts`). R10's essence "1 × Shrieking Essence of Spite 2.13 c" is, in the price fixture, `source: poe.ninja-previous-league`, a median of 5 rows of **Mirage**, `age_days: 99`; it is 110 of R10's 128 c. The page shows no mark. The JSON has `price_source`; the page does not.
  3. V01: the base (2 c) and the gem set (6 c) are `source: hand` ("the refresher does not fetch this line yet, ticket #360"). Mean 866 c = 8 c x 107 vendor attempts, i.e. 99% of the answer rests on those two hand prices; the text report prints `[hand]`, the page prints "2 c" and "6 c". `vendor_row` also says only "2 or more uncorrupted skill gems with the Minion tag ... (the cheapest set)": which gems to buy is not said.
  4. The "price is stale" warning is printed to stderr (`_main.py:103-106`), never on the page; the page says "fetched 2026-10-31" and nothing on age.
- What it should do: owner rules (trade: instant buyout, mean of the cheapest few, prices refresh by the system; "unknowns get the best estimate and an approximate mark"; "stale sources lose"). A price that is a hand number, another league's, or a 99-day-old median must be marked where it is used.
- Evidence: `tests/golden/real_r05.html` (link JSON), `real_r10.html` (Spite 2.13 c), `v01_minion_helmet.html` rows 1 and 11, `tests/fixtures/prices/routes-allflame-2026-10-31.json` (`Shrieking Essence of Spite` entry) and `vendor-v01-2026-11-01.json` (hand notes).
- Impact: every page: the cost numbers have no visible provenance; R05/R12 draw a base that the search does not ask for.
- Origin: buy spec and target start item are two hand-written files (#60 `3c123fc`: "Targets, buy specs and the guides' given routes"); `_accepts` written in #78/#133; price provenance was carried into the JSON (`price_source`) but not into `Line`.
- Pattern: two hand-written descriptions of one start item shown side by side with nothing reconciling them; provenance dropped at the last step.

### PRES-5: item cards of states drop the quality, Eldritch implicits, unveil offer, imprints, enchantment and Memory Strands the state holds   [CONFIRMED by run, real route not run] [impact: medium-high]
- Where: `_route_card.py:558-590` (`card_of_states`: `ItemCard(..., _join_properties(states, level), _implicits(data, base_id), (), sides...)`), `:545-555` (`_join_properties`: rarity, level, influences, corrupted only), `:561-563` (docstring: "A compressed state holds no implicits, quality or offer yet (ticket #69)"), `:293-336` (`card_of_item` returns `enchantments=()` always); `_report.py:103-130` (`describe_state` shows the offer only).
- What it does: `CompressedState` holds `implicits`, `quality`, `offer`, `imprints` (ADR-0027, `abstraction/_state.py:181-188`). Ran the b2 fixture start item (quality Prismatic 12%, Eldritch implicit grade 2) with a target that reads them: `state.quality = Quality(PRISMATIC, 12)`, `state.implicits = (ImplicitSide(grade=2, PASSING), ...)`, and `card_of_states` returns properties `('Rare', 'item level 84')` and implicits `['+(25-35) to Strength']`. The concrete-item card of the same item shows "Prismatic catalyst quality 12%".
- Impact: any plan with a catalyst, an Eldritch currency, an unveil, an imprint or an enchantment: the step is shown, the item card after it does not show what the step did. Target cards show them (so the final card cannot be compared with the goal). Golden `unveil_offer.html` shows it: target "quality 15% or more + Avoid Shock grade 2 or better", bought card quality 12% and the Eldritch implicit, after-card of the only step: neither.
- Origin: #143 (`9885268`, 2026-11-01) added these lines for **concrete** items (start card, target); #142 (`e783a83`, same day) had already put them into the compressed state; nobody connected the two; the docstring is stale.
- Pattern: display not extended when the model grew; stale comment says it cannot.

### PRES-6: a graph drawn as a list; "On failure" means "costs more to finish from"; steps are named "the item of step N"   [CONFIRMED] [impact: medium-high]
- Where: `_route_html.py:117` (a `↓` between every two rows), `_route_flow.py:166-180` (forward/miss by expected cost still to pay, `rank <= limit`), `_route_view.py:331-365` (`chance_lines`, `failure_lines`: the fallback `the item of step N` when no mod difference names the outcome).
- What it does: rows are numbered by breadth-first discovery and joined by `↓`, so rows 3-10 of V01 read as eight Regal Orbs in a row, and the restart (row 11) as the last of eleven steps; the loop is only a text link "→ step 2" in row 11's On failure. "Uses on average" is the total over all restarts (Regal ≈ 38.4), under a title that reads as "use it 38 times on this item" (each item gets one Regal and is scrapped). Augmentation's own outcomes (a different suffix landing) are split into "Chance per use" (36%, 32%) and "On failure" (six outcomes, 33% together) by cost-to-go; the player sees no failure: every outcome is "a magic helmet with a suffix, now Regal". R05's essence step: "the item of step 3: ≈64%, the item of step 4: ≈10%" (2 lines) and V01: "the item of step N" 16 times; the target step's card shows the *joined* item, not what the outcome was.
- What it should do: owner: "branches and failures shown as a player reads them" (a failed Regal = "no Life T1: scrap, buy again"); #58 chose a **flowchart** in round 1.
- Evidence: `v01_minion_helmet.html` rows 2-11; `real_r05.html` row 2; `gap.html`, `branch.html`, `given_route_differs.html`, `restart.html` each have one "the item of step 3" line.
- Origin: #96 (`9ca2c85`) "misses read as On failure by cost" (the checker found a miss shown as progress; the fix classifies by value, not by what happened).
- Pattern: a planner quantity (cost-to-go) used to label what happened to the player.

### PRES-7: "at least 1 of 4" is drawn as four mod lines; the target card has more suffix lines than a ring has suffixes; step Goals list all four   [CONFIRMED] [impact: medium]
- Where: `_route_card.py:342-369` (`card_of_target`: `add()` recurses into `KOfN` and appends one wanted `Slot` per member with the note `at least k of n`; `_fill` (`:289-290`) never caps), `_route_view.py:264-299` (`gains`), `_plan.py:190-213` (`leaf_labels` flattens KOfN, so `Requirements:` lists the members as separate requirements), `_report.py:113-115` (a state "lacks" each member).
- What it does: R05 target card: Prefixes `Life T1 · at least 1 of 4`; Suffixes **five** lines (Attributes, Strength, Fire, Cold, Lightning each in the green "wanted" style) for a ring with 3 suffix slots; step 2's Goal lists Strength, Life, Fire, Cold, Lightning as five goals; the text report would print `Requirements: ...; Life; Fire; Cold; Lightning` (no "one of"). The only trace of the group is a note on each line.
- What it should do: one slot per group ("one of: Life T1 / Fire T2 / Cold T2 / Lightning T2"), on no side more lines than the side holds.
- Evidence: `real_r05.html` target card (8 occurrences of "at least 1 of 4"), step 2 Goal.
- Origin: #78 (`120dc39`) "the members of a k-of-n group carry the note at least k of n" - the note was the whole design; the owner's seed finding (R05).
- Pattern: a structure (k-of-n) flattened for display.

### PRES-8: the card after a step is the join of many states, not an item ("in some", "tier too low", 8 suffix lines)   [CONFIRMED] [impact: medium]
- Where: `_route_card.py:521-543` (`_some`, `_join_rows`), `:558-590` (`card_of_states`), `:420-427` (`wanted(..., BELOW)` -> `+#% to Fire Resistance · tier too low`).
- What it does: R05 row 2 (essence): Prefixes "Life T1 · in some", "+# to maximum Life · tier too low, in some"; Suffixes eight lines (Attributes, Strength, Fire/Cold/Lightning T2 "in some", Fire/Cold/Lightning "tier too low, in some") on a side of 3 slots. `+#` stands for a roll the state does not keep. The same joined card is drawn as the **final** item of the given-route section of R05 (its only forward edge is the goal, whose compressed states include "tier too low" ones).
- What it should do: owner: "a bought item drawn empty / any mod where the player needs to know what is there"; an item card shows an item. A branch (64% craft Life, 10% craft Fire, 6% done) should be a branch, each with its own item.
- Evidence: `real_r05.html`, both sections, row 2; `real_r05` first-round golden `9ca2c85` had the same "in some".
- Origin: #78 `120dc39` (the join) + #96 f52d61b (BELOW rows added).
- Pattern: a set of planner states drawn as one item.

### PRES-9: internals on the owner's page and report   [CONFIRMED] [impact: medium]
- Where / what (each is a line the owner reads):
  1. Claim ids on the goal card and in the text/JSON: `vendor.gem_qualification_is_uncorrupted_skill_gems`, `harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot`, `conflict.odds`, `recombinator_cost.junk_craft_halves_dust_3_26`, ... (`_route_view.py:538-543`, `_marking.py:224-233`); goldens: v01, r12_fixture, r12_fixture_given_route, given_route_differs, approximate_conflict, interval_tiny. ADR-0028 prescribes it ("each with its claim id and reason", also "on the route page").
  2. The *reason* text is the project's provenance prose: **46 of the 117** `approximate_reason` strings in `rules/claims/*.yaml` carry ADR/ticket/issue/grill/"main chat"/"in-game list" references (`sockets.yaml` 14, `memory_strands.yaml` 12, `awakener.yaml` 4, `catalyst.yaml` 4, `foulborn.yaml` 3 ...; a further 8 name "the owner" without a reference), e.g. "applying it to both is the main chat's default" (printed in the interval golden), "the owner chose it (grill B3)", "open point O-06 of research ticket 86", "(in-game list #182)". A page that lists a claim prints that sentence.
  3. `ticket #190` / "(#190)": `UNRESOLVED` (`_report.py:236`) and `_route_view.py:532` "not resolved on the grid (#190)".
  4. `Buy R05 start ring`, `Buy R10 start boots`, `Buy Hand start belt`, `Restart: buy R12 start amulet again`: the row title is the *price-file key* (a benchmark id); page title = the target file name ("r05-strength-ring.yaml") or "Test page".
  5. Text/JSON requirement labels are raw ids: `family IncreasedLife (tier 1 or better, not crafted)`, `family ColdResistance, mod ColdResist1` (`_plan.py:190-213`), V01's `Requirements:` line mixes one English stat text and one family id; states are `S1..Sn` / `R1..` (two numbering schemes: text `S18` vs page "step 11").
  6. `planned:` / `chosen:` in the Start field (the losing option is called "planned"), "Rule axis", "alpha", "grid", "cost rule", "Bracket", "Smallest worst case" (PRES-15), `Run time: ... risk.evaluate 3.0 ms`, "Single-draw weight shares", "States solved", "Blocks solved", "p50/p90/CVaR".
- What it should do: owner: "no internals (claim ids, state ids ...); numbers named in plain words".
- Origin: ADR-0028 (claim id on the page), #143 piece A `4997f19`; the claim reasons were written as provenance notes for the registry (ADR-0004) and then used as page text; #60 for the labels.
- Pattern: project vocabulary leaking into player text.

### PRES-10: "any tier" / "Any tier of the mod counts" stays in 10 of 16 goldens and in the R12 example, against the owner's tier rule   [CONFIRMED] [impact: medium]
- Where: `_route_card.py:243-248` (`_tier_note` returns `any tier`), 10 goldens (approximate_conflict, branch, essence, gap, given_route_differs, interval_tiny, r12_fixture, r12_fixture_given_route, remove_crafted_then_chaos, restart); `examples/targets/r12-lightning-amulet.yaml` ("Every tier of the mod counts, because no minimum tier is given"); `examples/targets/j01-*`, `r13`, `r10-fractured-boots-70-life` have tier-less leaves too.
- What it does: the page says "+#% to Lightning Resistance · any tier". The owner's rule: unstated tier = the top tier the item level allows, "any of 9 tiers is meaningless".
- Also: R12's start item is written `tier: 3` in the target YAML, drawn "T7" on the start card (`r12_fixture.html`: `+(12-17)% to Lightning Resistance · T7 [fractured]`), and "any tier" on the goal and after cards: three statements about one mod, none reconciled (YAML tier is "taken as written" and ignored by the card, which recomputes from data).
- Evidence: `grep -o "any tier"` counts above; `tests/test_cli_routes_real.py` has the right property test (`test_the_tiers_the_target_asks_for_can_appear_at_its_item_level`) but only for R10/R11/R05.
- Origin: #58 round 2 (main chat: "R04 follows the guide: Life of any tier") then the owner's rule of 2026-10-31 (#96 comment); the fixtures predate it and were regenerated (#96, #133, #197) without being re-read.
- Pattern: a golden accepted before a rule existed, never re-judged against it.

### PRES-11: goldens that are not answers, or that contradict themselves, were accepted and re-blessed   [CONFIRMED] [impact: medium]
- 7 of the 16 HTML goldens are hand-made plans (`hand_input`, `toy_plan`, `unveil_plan`: bench_craft, branch, essence, remove_crafted_then_chaos, approximate_conflict, interval_tiny, unveil_offer), 5 are `make_plan` on fixture data (r12 x2, gap, given_route_differs, restart), 4 are real data (real_r05/r10/r11, v01).
- `interval_tiny.html`: the same page says "Mean ≈ 7.14 c (0.024 Divine)" (the belt Chaos-Orb stand-in policy) and "Plan: 62.40 Chaos ... at alpha = 1", "Recombinations: 3.00 expected" (`interval_support.py` header: "the toy plan of the report is the belt plan of `test_cli_approximate_inputs` (its policy is not what is under test)"). The route rows draw one Chaos Orb step and no recombination.
- `unveil_offer.html`: page says goal reached in ≈3.4 Chaos Orbs for 9.4 c, with a target that asks quality 15% and an Eldritch implicit that the one-step policy cannot give (`test_cli_route_golden_b2.py:93`: "The plan is made by hand to show the cards, not to be solved").
- `approximate_conflict.html`: "Orb of Conflict (stand-in)" with cost "1 × Chaos Orb".
- `remove_crafted_then_chaos.html` Accepts: "12% increased Damage" for a *crafted* mod (`start_accepts` drops the crafted mark).
- Regeneration history (git log --follow): real_r05/r10/r11 4 commits each (#96 x3 on 2026-10-31, #163 reprice 11-01; the #163 diff of R05 is only prices); r12_fixture 7 (#78 x2, #96 x2, #133 x2, #197); essence 6; restart 6; branch 5; r12_fixture_given_route 5; gap 4; remove_crafted 4; bench 3; given_route_differs 3; v01 html 2 / txt 3 (the third by `e03e821` "integ: V01 goldens list the kinds #373 adds ... (plan unchanged)") / json 2; interval_tiny 2-3 (#221); approximate_conflict 1; unveil_offer 1. Every route-view change rewrote all of them with `UPDATE_GOLDEN=1`; the PR text says "each diff was read" (PR #131). The only page the owner saw before acceptance was R10 (#96 comments).
- Evidence for "R05 looked right and was not": first golden (`9ca2c85`) planner 27.9 c vs the guide's route 39.5 c; after the owner's tier rule 29.6 c vs 152 c (PR #131 table); now 12.2 c vs 135 c on the same page. The only comparison test is one-sided (PRES-21).

### PRES-12: "one mod format" is not true across the page, and the test that guards it is a whitelist of the variants   [CONFIRMED] [impact: low-medium]
- Where: `_route_card.py` (notes), `tests/test_cli_routes_real.py:205-222` (`NOTE_PARTS = T\d+( or better)?|any tier|crafted|essence only|tier too low|in some|at least \d+ of \d+`).
- What: the same mod appears as (a) `+(13-16) to all Attributes · T1 [fractured]` on a card, (b) `fractured: +# to all Attributes (at least 13)` in Accepts, (c) `+(13-16) ... · T1` on the target; a crafted mod is a note `· crafted` on the target card and a badge `[crafted]` plus purple on step cards (R10, bench_craft: the target line is green); an essence-only mod is a note on leaf rows and a badge elsewhere; ranges appear as `(100-114)`, `#`, a rolled `+25`, `(1-2)` while Accepts says `Regenerate 1 Life per second` for the same mod (bench_craft, branch). The test lists every note variant as legal, and exempts crafted lines from the "has a tier" check (`slot.note or "crafted" in slot.marks`).
- Origin: #96 f52d61b ("one mod-line format"), owner-accepted on R10 only.

### PRES-13: the text report counts the wanted mods again as "other mods"; the report is a list of states   [CONFIRMED] [impact: low-medium]
- Where: `_report.py:123-126`: `junk = [slot for slot in state.slots if not slot.crafted]` includes the slots that give a requirement.
- Evidence (ran, `t_describe.py`): a belt holding a fractured Cold Resistance and one Life mod: description `rare; fractured +#% to Cold Resistance; has family IncreasedLife; ...; other mods: 1 prefix` - the "1 prefix" is the Life mod already named by "has". V01: `S2: magic; has +1 to Level of all Minion Skill Gems; ...; other mods: 1 prefix, 1 suffix` for an item whose only mods are the Minion prefix and the Augmentation suffix; this string is in `description` of every state in the JSON.
- Origin: `3c123fc` (#60).

### PRES-14: for an approximate answer the owner gets no route page, no p90, no `--route`; the switch is a fixed 60 s / 1%   [CONFIRMED structure] [impact: medium]
- Where: `_main.py:104-134` ("Route view not written: it is not built for an approximate answer yet."; `--route` is a `PlanError`), `_marking.py:41,79-81` (`NO_RISK`), `_decide.py:47-48` (`BUDGET_SECONDS = 60.0`, `TOLERANCE = 0.01`), `_report.py:323` ("Blocks solved").
- What: a target whose exact solve is forecast above the budget is answered with "approximate (certified within x% of the exact mean)", the lower/upper bounds, blocks, and a policy over blocks as an `S` tree. The three real goldens are made with `make_plan` (exact, no budget); R05 "plans in about 7 minutes under load (was about 80 s)" (PR #131) so a plain CLI run is not what the golden pins. I did not run the CLI (heavy); the code path is unambiguous.
- Owner rule: "approximate with an interval reads as useless"; "no hard-coded cut-offs".
- Origin: ADR-0023, #127/#128.

### PRES-15: the interval answer is words for a result nobody produces, and it is jargon   [CONFIRMED] [impact: low-medium]
- Where: `_interval.py` (456 lines), `_report.py:77-84` (`with_interval`), `_route_view.py:536-544`.
- What: `build_interval_answer`/`with_interval` are called only from `tests/` (grep over `src/`): the CLI never builds an `IntervalAnswer`; ADR-0028's "As built" says the planner waits for #217. The text it would print is: "the recombinator's mod selection exponent alpha (a mod is kept in proportion to its weight to the power alpha)", "Bracket: the smallest worst case any route can have is ... Chaos", "gap", "cost rule at its low end", "Interval: 59.25 to 64.23 Chaos over the grid", i.e. an interval answer (owner: useless), in terms no player uses. Also the golden contradicts its own page (PRES-11).
- Origin: #221 (`1705ab8`, `9151d1c`).

### PRES-16: donors are invisible to the report and the page   [SUSPECTED, latent] [impact: low now, high when donors are wired]
- Where: `_reach.py:20-36` `policy_states` follows `.outcomes` only, never `.extra_inputs`; `_route_flow.py:121` and `_report.py:160` build from it. `cli/_donors.py` header: "The planner (`make_plan`) does not use this yet ... until the report and the risk run read policies with inputs" - the report side is still unread. `_interval._walk` does follow `extra_inputs`; the page does not.
- Effect once wired: a "Recombine / Awakener" row would be drawn without the rows that build its donor items.

### PRES-17: fixed caps degrade the page silently   [CONFIRMED] [impact: low]
- Where: `_route_flow.py:50-51` `MAX_STEPS = 1500`, `REFINE_WORK = 250_000`; `_reach.py:15` `MAX_TRANSIENT = 400`; `_report.py:42,44` `MAX_TREE_DEPTH = 40`, `MAX_DROPPED_LINES = 300`.
- What: past `REFINE_WORK` every state becomes its own row (no note on the page; PR #131 states this as a valid fallback); past 1500 steps uses/step costs are dropped *with* a goal-card note; past 400 transient states the text report silently omits "reached with chance" (`reach is None`). None says what it still guarantees.

### PRES-18: the guide's route is redrawn where it differs only in a number   [CONFIRMED] [impact: low]
- Where: `_route_view.py:592-672` (`_row_key`, `_same_steps`, `merge_sections`).
- What: R05's given-route section repeats the target card and step 2 (title, Goal, Accepts, Note, the joined item card) of the planner's section; the two rows differ only in the chance lines (5.8% / 94% again vs 5.8% / 64% / 10% / 20%). The owner's rule is "show the guide's route only where it differs"; here the difference is one sentence ("the guide keeps using the essence"). The "Same as the planner" field reads "step 1: the planner's step 1".

### PRES-19: page says the bought item's other mods are unknown ("any mod or empty"); the planner's start state has none   [SUSPECTED] [impact: medium]
- Where: `_route_view.py:428-432` (`start_card`, filler `ANY_OR_EMPTY`), versus the compressed start state: `tests/golden/plans_118.json` first key (R05): `fractured=(AllAttributes4,...), slots=()`.
- What: the planner starts from an item with only the fractured mod (the target's `start_item`), the bought item is a rare with 4+ mods. For R05/R10/R11 the first action is an essence (rerolls everything), so nothing moves; for any plan whose first action does not reroll (Annulment, Exalted, bench craft on the bought item) the page's "unknown" and the plan's "empty" differ, and the page does not say which one the cost assumes.
- Needs: someone with the targets/starts area to confirm; I only read it.

### PRES-20: approximate inputs are on the goal card, not on the steps that read them   [SUSPECTED] [impact: low]
- `_route_view.py:538-543`: the list is built from all actions of the policy (`_marking.approximate_inputs`) and put in one field; interval_tiny lists 11 claims; the reader cannot tell which step or which number each affects.

### PRES-21: tests of the page: what is judged and what is not   [CONFIRMED] [impact: medium]  (see the table below)

---

## Where the page builds steps from states, and what it would take to build them from player actions

- Today: `RouteInput.policy` (state -> solver `Action`) -> `_route_flow.build_flow`: block states by `(action.label, action.cost)` (or "no action, same reason"), refine until every state of a block has the same exact chance into every block (goal counted as one target), solve `N = (I - Q)^-1` on the block chain with numpy (cap 1500 blocks) for uses, reach and cost-to-go -> `_route_view._View.step_row` writes one row per block; forward/miss per edge by cost-to-go (`rank <= limit`); item cards from `_route_card.card_of_states` (join of the states). So the unit of the page is "a class of compressed states that are exactly interchangeable for the solver", which is finer than "what the player does".
- Verified on V01 (JSON golden, no solve): action + cost + *set of reachable blocks* (chances ignored) turns 88 states into 3 steps. The change inside `_refine` is the key (drop `tuple(sorted(into.items()))` chances, keep the support) - small. What it costs elsewhere:
  1. **Numbers.** `_visits` works on the block chain and assumes every state of a block has the same chance row. With the coarser blocks it must be solved on the *state* chain (V01 786 solved / 88 reachable; R05 1,123 reachable) and aggregated: uses(step) = sum of the states' uses; chance of an edge per use = sum(uses_i * p_i) / sum(uses_i) (visit-weighted; totals stay exact: uses x cost still adds to the risk mean, which is the existing `test_the_buy_and_the_step_costs_add_up_to_the_mean_and_the_start_price`); reached = chance that any state of the step is entered. The state-chain solve needs a sparse solve (`reach_probabilities` already refuses above 400 transient states).
  2. **Forward/miss.** Cost-to-go ranks inside one coarse step differ per state; the rule must become "what the player sees": an edge is progress when it adds a wanted mod / reaches a better step in the policy's own order, a setback when it loses one or restarts, and "again" when the player is in the same situation. Outcomes landing in the same coarse step collapse (Augmentation: one outcome "a suffix, now Regal", no "On failure").
  3. **Cards.** `card_of_states` joins the *landing states of the edges*; with coarser steps there are more of them, so PRES-5/7/8 (quality, k-of-n, "in some") must be fixed first, or the cards get more vague, not less.
  4. **Tests.** `test_cli_route_flow.py:73` (different chances = two steps) and `:330` (coarsest grouping) assert the current rule and must be rewritten to the player rule; add a V01-like fixture with the property "no two rows of a page have the same title and card".
- The better fix lives one layer down (owner's rule: "detail no later decision sees is not tracked at all"): the abstraction should not keep the identity of an Augmentation's junk suffix when no later action reads it (solving 786 states for a 3-action plan). That changes the Regal chance from 0.88-0.95% to one number; it is the abstraction area's call.
- A step language already exists in the repo: the given-route rules in `_route.py:1-35` speak in player conditions (`rarity`, `open_prefixes/open_suffixes`, requirement `status` absent/below/passing, `crafted_mods`) and an action. Deriving the planner's policy in the same vocabulary (state classes -> shortest `when:` -> action) would make the planner page and the guide page the same shape, and "show the guide's route only where it differs" a diff of two rule lists instead of `_row_key` text matching.

## What each page test checks

| test / golden | what it really checks | who could have judged it |
|---|---|---|
| `test_the_route_view_page_is_the_golden_file[R05/R10/R11]` (`test_cli_routes_real.py:163`) | byte equality with a file the code itself wrote (`UPDATE_GOLDEN=1`); needs the real cache | owner saw R10 only (10-31); R05/R11: the `checker` and "each diff was read" |
| `test_every_mod_line_of_the_pages_has_the_one_format...` (`:208`) | note text matches a whitelist regex of all existing variants; crafted lines exempt from "has a tier" | nobody: it cannot fail on the faults above |
| `test_the_buy_and_the_step_costs_add_up_to_the_mean_and_the_start_price` | property, independent oracle (`risk.evaluate`) | sound; says nothing about what the rows mean |
| `test_every_reachable_state_is_in_exactly_one_step_and_a_step_has_one_action` | structural | sound, and exactly what permits PRES-1 |
| `test_cli_route_flow.py:73,330` | pins "different chances = different steps" and "coarsest bisimulation" | design lock |
| `test_the_solver_is_no_dearer_than_the_guides_given_route` (`:123`) | `plan.mean <= guide.mean`: one-sided; R05 passes with 12.2 c vs 135 c (11x) | a two-sided "within a factor" or a per-step comparison would have flagged it |
| V01 `test_*` (`test_vendor_benchmark_real.py`) | totals `866.4` / `1348.9` copied from the first run (`abs=0.1`); lines of the text; three goldens | no external oracle exists for V01 |
| `plans_118.json` (`test_prune_bound.py`) | policy label per compressed-state repr and mean of R05 (9.613), R10 (111.33), R11 (1085.96) as main printed them at `147fdad`; 1.9 MB | pins the R05 value that includes bench-crafts-as-T1; a fix will have to re-bless it |
| `unveil_offer`, `interval_tiny`, `approximate_conflict` goldens | cards/blocks drawn from hand-made plans | the plans are declared "not to be solved" in their own docstrings |
| fixture goldens (essence, branch, bench_craft, gap, restart, ...) | wording regressions of the page on toy belts/amulets | read once by a person (`test_cli_route_view.py` header) before the rules of 10-31 |
| not tested anywhere | no repeated rows; every requirement field of the target visible; card text equals a mod the player can get; no side with more lines than slots; price provenance visible | |

## Which other goldens show the same faults

| fault | goldens |
|---|---|
| claim ids | v01 (3), r12_fixture, r12_fixture_given_route, given_route_differs, approximate_conflict, interval_tiny (11) |
| "the item of step N" | v01 (16), real_r05 (2), branch, gap, given_route_differs, restart |
| "any tier" | 10 (list in PRES-10) |
| KOfN as lines, "in some", "tier too low" | real_r05 only (the only KOfN golden) |
| crafted line green in the target, purple in the cards | real_r10, bench_craft |
| crafted text of the class, not of the craft | real_r05 (the only family with several crafted mods in a golden) |
| more mod lines than slots | real_r05 (target 5 suffix lines; row 2 eight) |
| empty/any-or-empty differing between rows of one fixture | bench_craft, remove_crafted_then_chaos, branch (start card "any mod or empty" for slots the next card calls "empty") |
| title vs Goal vs card | real_r05 (Life); interval_tiny (headline vs block) |
| buy spec vs target start item | real_r05 (base), r12_fixture(+given) (base, item level 75 vs 84), bench_craft/branch/essence (`Regenerate 1` vs `(1-2)`) |
| unmarked hand/other-league price | v01 (hand), real_r10 (Mirage, 99 days) |
| repeated rows | v01 (7) |
| quality/implicit/offer missing after a step | unveil_offer |

---

## Patterns seen in this area

1. **A planner-internal object is drawn as if it were something in the game**: an equivalence class of states as a step (PRES-1), a canonical id as a mod (PRES-2), a join of states as an item (PRES-8), cost-to-go as "failure" (PRES-6), a flattened k-of-n as four requirements (PRES-7), a wanted mod as "other mod" (PRES-13).
2. **Display written once against the fields of that day and never extended when the model grew**: `min_roll`/`not_crafted` (since #19) and quality/implicits/offer (since #142) are not on the cards (PRES-3, PRES-5), donors are not followed (PRES-16), a docstring still says the state holds none of it. The same representative bug was fixed in two of its three display sites (PRES-2).
3. **Golden files as the acceptance of correctness**: bulk-regenerated with `UPDATE_GOLDEN=1` on every wording or price change, 7 of 16 from hand-made plans that contradict themselves, a whitelist regex test, only R10 ever shown to the owner (PRES-10, 11, 12, 21).
4. **Two hand-written descriptions of one thing shown side by side with nothing reconciling them**: buy spec vs target start item (base, item level), title vs card, YAML tier vs data tier vs "any tier", the page's "unknown" start vs the plan's empty one (PRES-4, 2, 10, 19).
5. **Project vocabulary leaks into player text**: claim ids, ADR/ticket/grill/"main chat" inside claim reasons, benchmark ids as row titles, S-ids, alpha/bracket/grid (PRES-9, 15).
6. **Provenance dropped at the last step**: the price source, age and "hand" flag exist in the price file and the JSON and never reach the page; approximate inputs are a list on the goal card, not marks on the steps that use them (PRES-4, 20).
7. **Fixed cut-offs and silent fallbacks in the output path**: 60 s / 1% decide whether a page exists at all; step, refine, tree and reach caps degrade the page without a word (PRES-14, 17).
