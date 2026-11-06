# The owner's rules

The document of record for how the owner reads a target, a price, a search and a route page. Builders, the checker and the tests read it; the main chat's memory and the issue comments no longer hold it alone. It was written for ticket [#401](https://github.com/Rasslabsya4el/crafting-system/issues/401), rebuild step 1 of the audit [#396](https://github.com/Rasslabsya4el/crafting-system/issues/396) (`docs/research/2026-11-02-codebase-audit.md`, class 7).

## How to read it

- One rule per entry, numbered `OR-1`, `OR-2`, ... A number is never reused. A rule that is replaced stays, marked **Replaced by**, so an old citation still leads somewhere.
- Each entry has the rule in one sentence, an example and a counter-example from a real route, target or page, and its source with a date. Where no real route shows a case, the entry says so.
- **Where two sources disagree, the later owner decision wins**, and the entry names the one it replaces.
- A rule says what the owner means. It does not say how the code does it. Where the code or a file differs today, that is an open point of the ticket that finds it, not a reason to bend the rule.
- A brief, a PR or a checker verdict cites a rule as `OR-n`.
- Sources named "memory note" are files in the main chat's memory. Their substance is copied here, so nothing outside the repository is needed to read a rule.

## Reading a target

### OR-1. An unstated tier is the top tier the item level allows, rolled

A mod whose tier the guide does not state is the top tier of its ladder that the target's item level allows, rolled on the item, not made at the bench.

- **Example.** R05 (`examples/targets/r05-strength-ring.yaml`, item level 75): the guide says only "Maximum Life or Resistances", so the target asks Life tier 1, +(100-114), and each resistance tier 2, +(42-45)%, because their tier 1 needs item level 84.
- **Counter-example.** The same file counts a bench craft as "tier 1 of what it crafts whatever its range" (line 26), so a crafted +(26-40) Life meets "Life T1"; R05's mean came out at 12.2 c against the guide route's 135 c. R12 (`r12-lightning-amulet.yaml:28`) writes "every tier of the mod counts, because no minimum tier is given".
- **Source.** Owner on the R10 page, 2026-10-31 (memory note `owner-route-reading.md`; issue [#96](https://github.com/Rasslabsya4el/crafting-system/issues/96), first comment). Audit #396, "The owner's rules".
- **Replaces.** The default of ADR-0008 ("any tier, any source"), written on 2026-10-30. Narrowed by OR-4.

### OR-2. A mod forced by an essence or a bench craft is exactly that mod

When the route's essence or bench craft forces a mod, the target asks for exactly that mod and tier, not "any of N tiers".

- **Example.** R10 (`r10-fractured-boots.yaml`): the Shrieking Essence of Spite gives `Intelligence8`, tier 2 on boots, +(43-50); the bench craft gives `EinharMasterAvoidElementalAilments1`, (16-20)%. Both are asked with `mod:`, so no other tier of the family counts.
- **Counter-example.** R13's "a crafted damage modifier" is read as any tier of two families, so the planner buys the cheapest craft, (24-32)% for 0.109 c, while the given route buys (15-17)% for 9.16 c: one target, two readings (audit ROUTES-3).
- **Source.** Memory note `owner-route-reading.md`, 2026-10-31; issue #96, first comment, 2026-10-31.

### OR-3. A mod of a bought start item is the tier the trade price was taken for

The start item's own mods are the tier priced on the trade site, and the target, the buy spec and the price agree on it.

- **Example.** R11 (`r11-reservation-helmet.yaml`): the fractured Chaos Resistance is tier 1, +(31-35)%, and the buy spec prices that tier. R10: the fractured `MovementVelocity5`, 30%, tier 2, is the cheapest tier the spec prices.
- **Counter-example.** R12's start amulet is written as `LightningResist2`, tier 3, `[14]` (`r12-lightning-amulet.yaml:48-49`), while the game data has that mod at tier 7 and the buy spec (`examples/buy/r12-start-amulet.yaml:10-12`) names no minimum for the fractured resistance.
- **Source.** Memory note `owner-route-reading.md`, 2026-10-31; issue #96, first comment, 2026-10-31.

### OR-4. The guide's own wording wins

When a guide gives a tier, a number or a soft wish, the target takes the guide's words; the top tier of OR-1 applies only where the guide states no tier.

- **Example.** `r10-fractured-boots-70-life.yaml` reads the guide's "preferably at least 70" Life as a roll of at least 70 with no tier (about 46 c at 70). R14 asks `IncreasedAttackSpeed` `min_tier: 1` because the guide says "T1 Attack Speed"; R13 asks tier 1 Life because the guide says "tier-1 life".
- **Counter-example.** `r10-fractured-boots.yaml` asks Life tier 1 where the guide says "preferably at least 70" (128 c). R11 asks Evasion and Life tier 1 where the guide says "prefixes you are happy with" (1,110 c). R04 and R14: the guide's two Exalted Orbs "guarantee" Life and the damage mod, 100%; at the target's top tiers the same orbs are 13% and 20% (R04) and 55% and 10% (R14).
- **Source.** Owner decisions on #396, point 1, 2026-11-02 (memory note `audit-decisions-2026-11-02.md`).
- **Replaces.** OR-1 where a guide states a number, a tier or a wish. This is the answer to the first open question of the audit.

### OR-5. A target never says which actions are allowed

A target states what to end with and what to start from; every kind of action is offered and pruning decides.

- **Example.** None. No target in `examples/targets/` meets this today: the seven with an `actions:` key (J01, R04, R08, R09, R13, R14, V01) name the allowed kinds, and a target without it gets the silent default of leaving out the opt-in kinds. The rule is the owner's decision, and R05 (no key, yet no Exalted Orb offered) is the nearest case.
- **Counter-example.** `j01-cobalt-life-attack-speed.yaml:23` (`actions: [chaos-orb]`); V01 (`v01-minion-helmet.yaml:44`) lists four orbs "because fewer kinds keep the state space small".
- **Source.** Owner decisions on #396, point 2, 2026-11-02 (memory note `audit-decisions-2026-11-02.md`): the silent opt-in default is "a hard contradiction" with the product.

### OR-6. A start item is given or bought; how it was acquired is not modelled

A start item is a concrete item that is given or bought; where it came from (a Genesis Tree, for example) is not planned.

- **Example.** R10, R11, R12: a bought item with a fractured mod, priced by OR-7 and OR-8.
- **Counter-example.** A Genesis-born item modelled as an acquisition method. No route does this.
- **Source.** Memory note `snapshot-not-asking.md`, 2026-11-01; ADR-0043.
- **Note.** ADR-0059 admits one exception, the vendor recipe (V01), which ADR-0043 already names.

## Prices

### OR-7. A trade price counts instant-buyout listings only, of any age

The trade query asks for "Instant Buyout" and never "Instant Buyout and In Person", and sets no listing-age window.

- **Example.** R10's start boots (ticket [#133](https://github.com/Rasslabsya4el/crafting-system/issues/133)): status `securable` and no `indexed` filter; the route page's trade link carries the same filters, so the link shows the listings the price came from.
- **Counter-example.** R04's start quiver is priced at 9 c from a poe.ninja line while trade shows 130 c (audit ROUTES-7). A poe.ninja row proves no instant-buyout listing.
- **Source.** Owner on the R10 page, 2026-10-31 (memory note `owner-route-reading.md`; #133).

### OR-8. A price is the mean of the cheapest few

The price is the mean of the cheapest few instant-buyout listings, five by default.

- **Example.** R10's start boots: "mean of the 5 cheapest instant-buyout listings" (#133; ADR-0061, decision 3).
- **Counter-example.** The median of the cheapest, which `trade_pricing.py` computed before #133.
- **Source.** Memory note `owner-route-reading.md`, 2026-10-31; #133.

### OR-9. The system refreshes prices itself

The user never runs a refresh or a data step; the system fetches prices on a schedule, within the trade limiter's budget, as part of a website service.

- **Example.** The scheduled refresher of ADR-0007's amendment ([#337](https://github.com/Rasslabsya4el/crafting-system/issues/337)).
- **Counter-example.** A design option "a trade price list the owner refreshes by command", which he corrected on 2026-11-01. No route shows it.
- **Source.** Memory note `system-self-serves.md`, 2026-11-01.
- **Replaces.** The sentence of ADR-0007 that the trade fetcher "runs only when the owner starts it", already widened by that ADR's amendment.

## Search

### OR-10. Detail that no later decision reads is not tracked

The search keeps no detail that a later decision never sees, like a crafter who ignores junk.

- **Example.** R08 and R09: an Orb of Alchemy that only makes the boots rare before a fossil is one state, because the first fossil erases whatever the rare holds. (The step itself is still shown, OR-16.)
- **Counter-example.** V01 has 786 states of which 697 are dead ends that differ only in junk, and 91 remain when merged exactly; R12's reroll-only model keeps 33 states where 2 will do, R10's 425 where 2 will do (audit STATE-4, STATE-6).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

### OR-11. The answer is exact among realistic routes, never an interval

A good answer is exact among realistic routes; "approximate with an interval" reads as useless.

- **Example.** R10 (128 c), R11 (1,110 c) and R12 (56.6 c) are exact means that an independent Monte Carlo of the audit matched.
- **Counter-example.** R04 and R14 at default flags are refused or answered "within a certified 1%" with no route page (audit PLANNING-15).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

### OR-12. No hard-coded cut-offs

The planner recognises an unrealistic branch by a general rule, not by a fixed number such as 100,000 uses of one step; the general rule is exact branch-and-bound against an incumbent route, with cuts whose tolerance comes from whether they could change the best route, and a fixed rail is only a stop-and-say-so safety net.

- **Example.** R04 has 177,242 states and 536 million transitions, and R08 with the Alchemy took more than an hour: cut them by the rule, not by a number.
- **Counter-example.** R13's target (`r13-life-resist-belt.yaml:28-35`) names its allowed kinds because a belt rerolled with a Chaos Orb has "more than 43,000 states after four minutes"; the cut is by graph size.
- **Source.** Memory note `realism-rails.md`, 2026-11-01, the owner's correction of the same day.
- **Replaces.** The first reading of that note, "configurable realism rails (100k uses per step)".

### OR-13. A cut says what it still guarantees

Every cut of the search states what the answer still guarantees.

- **Example.** A target with an `actions:` key prints "the plan is the cheapest among the named ones" in the text report.
- **Counter-example.** The route page of R13 and R14 says "Cheapest policy of the planner" with no word of the kinds left out (audit ROUTES-5, PLANNING-3).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

### OR-14. Unrealistic and useless branches are cut across the whole route

Pruning works on the route as a whole, not only inside one step.

- **Example.** R14 walks 816,153 states, its optimal policy reaches 65,147 of them and the guide route 946; R04 walks 177,242 and the guide route reaches 22.
- **Counter-example.** R14's page of 87,272 steps (151 MB), 65,433 of them the same Restart card. A page like that must not exist.
- **Source.** Owner decisions on #396, point 3, 2026-11-02; measurement results on #396, 2026-11-04 (route-level pruning comes before a "minimal state").

## The answer and the page

### OR-15. Every mod line is in one format

All mod lines on a page share one format, and a mod never shows a different mod's text.

- **Example.** The V01 golden (`tests/golden/v01_minion_helmet.txt`, `.html`): `+(130-144) to maximum Life · T1`, the same shape in every card.
- **Counter-example.** R05's bench step draws `DexMasterLifeCrafted1` "+(35-44)", a mod no bench option adds; "at least 1 of 4" is flattened into four lines with notes (audit PRES-2, PRES-7).
- **Source.** Owner on the R10 page, 2026-10-31 (he had asked before); issue #96, first comment.

### OR-16. Every in-game step is shown; none is hidden

A page shows each step a player does in the game.

- **Example.** The accepted R10 page notes that an essence of level 5 or higher reforges a rare without a Scouring Orb.
- **Counter-example.** R08 and R09 draw the bought Normal boots and then a "Rare" card with no mod; the Alchemy between them appears nowhere on the page (audit ROUTES-4). R05's 20% catalyst is left out with no mark on the page.
- **Source.** Memory note `owner-route-reading.md`, 2026-10-31; issue #96, first comment.

### OR-17. The bought item's other mods are shown as "any mod or empty"

A bought item is never drawn empty; its mods other than the wanted one read "any mod or empty".

- **Example.** The accepted R10 page (2026-10-31): the bought boots show the fractured Movement Speed and "any mod or empty" for the rest.
- **Counter-example.** The R10 page the owner rejected on 2026-10-31 drew the bought item empty.
- **Source.** Issue #96, first comment (asked) and second comment (accepted), both 2026-10-31.

### OR-18. A page step is a player step

A step stands for a set of states only when the policy takes the same action in all of them; look-alike states that need different actions branch.

- **Example.** V01 has 3 player actions (audit PRES-1).
- **Counter-example.** V01's page has 11 rows for those 3, and R14's 87,272 steps come from the "same exact chance" refinement added later (audit PRES-1).
- **Source.** Issue [#58](https://github.com/Rasslabsya4el/crafting-system/issues/58), the "Exact states: the general rule" comment, 2026-10-31; memory note `audit-decisions-2026-11-02.md`.

### OR-19. The same route is never shown twice

A page shows the guide's route once when it equals the plan's, and only the steps that differ otherwise.

- **Example.** R10 and R11: "Same as the given route".
- **Counter-example.** Showing the route twice was one of the faults the owner named on the R10 page of 2026-10-31.
- **Source.** Issue #96, first comment, 2026-10-31.

### OR-20. A fully known mechanic is never shown as a range

When all mechanics of a case are known, the page shows one exact chance; states that take the same action merge for display into the mixture of their chances.

- **Example.** V01: the eight Regal states take the same action, so "Augmentation, then Regal" has one chance, the mixture of the eight.
- **Counter-example.** The same page shows eight Regal rows between ≈0.88% and ≈0.95% (`tests/golden/v01_minion_helmet.txt:408,453`). That spread was a display artefact, not an uncertainty.
- **Source.** Owner decisions on #396, point 5, 2026-11-02. A display merge of this kind is exact and needs no bound.

## Evidence

### OR-21. Build on today's snapshot; no fixed ranking of sources

Rules are built on the information that exists now, even where old; GGG notes, the wiki, repoe-fork data, Craft of Exile (pages, data and code) and large-sample player experiments all count, and a source that current data shows out of date loses.

- **Example.** Harvest follows Craft of Exile's implementation where the documentation is incomplete; the 3.25 recombinator guide still stands.
- **Counter-example.** Craft of Exile's 3.29.0.3 essence entries, bench prices and removed Harvest crafts were stale against the 3.29.3.3 data and lost.
- **Source.** Memory note `evidence-ranking.md`, 2026-10-30; ADR-0005.

### OR-22. Every rule carries its source, URL, quote and date

A mechanic's rule in the registry names where it came from.

- **Example.** A Craft of Exile claim cites the page or code line, its data version and the date checked.
- **Counter-example.** 25 claims are verified at 3.29.0.3 against the 3.29.3.3 pin (audit ACT1-14).
- **Source.** Memory note `evidence-ranking.md`, 2026-10-30; ADR-0004, ADR-0005.

### OR-23. All known evidence is modelled up front; an unknown gets the best estimate, marked approximate

The system models everything known now. For an unknown it uses the best estimate from the evidence and marks the result approximate.

- **Example.** V01's vendor-recipe claims are listed on the page as "Approximate inputs".
- **Counter-example.** 15 claims say "APPROXIMATE" or "UNVERIFIED" in their text with no `approximate: true`; an action with an unpriced resource is dropped instead of estimated (audit INPUTS-15, PLANNING-4).
- **Source.** Memory note `snapshot-not-asking.md`, 2026-11-01.

### OR-24. The owner is never asked mid-plan

The planner never stops a route to ask the owner for a check in the game; a doubtful mechanic is checked in the Craft of Exile emulator first, and goes on the owner's in-game list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)) only when the emulator cannot check it or contradicts other trusted sources.

- **Example.** A mechanic in doubt is put beside the emulator before any question to him (skill `coe-emulator-check`).
- **Counter-example.** A design that says "measure later if a route depends on it". No route shows it.
- **Source.** Memory note `snapshot-not-asking.md`, 2026-11-01. The owner: «не будет такого что она просит меня что то проверить в игре» ("there will not be a case where it asks me to check something in the game").
- **Replaces.** The part of `evidence-ranking.md` (2026-10-30) and ADR-0005 that sends a quick-to-check conflict to the owner as a short in-game check; that route is now the last, not the first.

### OR-25. The owner's opinion on a method is not a source of truth

He says he is no combinatorics expert: where the method is unsure, research it, and say what each cut still guarantees.

- **Example.** His 100,000-uses rail was corrected the same day to a general rule (OR-12).
- **Counter-example.** None in a route.
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

## Process

### OR-26. A defect is traced to its root; no per-case patches

On any defect, trace each symptom to its origin, group by root cause, and fix the root: a rule, a single source of truth, an independent check, or a rebuild. Say for each root which other routes or features it touches.

- **Example.** The audit #396 grouped the R05, V01 and R10 faults into seven classes.
- **Counter-example.** A list of one-line fixes for the R05, V01 and R10 pages.
- **Source.** Memory note `roots-not-patches.md`, 2026-11-02.

### OR-27. The owner writes no target or route; agents find and test them

Agents find benchmark routes (guides, Craft of Exile, research) and write the target, the route and the test; the owner is asked only for taste, money, time and risk.

- **Example.** The benchmark targets in `examples/targets/` are written by agents from guides: the headers cite PoE Vault, Reddit and `docs/research/2026-10-30-5-reference-routes.md`.
- **Counter-example.** None in the repository.
- **Source.** Memory note `owner-not-a-crafter.md`, 2026-10-31.

### OR-28. The owner's rules are read by whoever builds and checks

A brief that touches targets, routes, prices or pages names the rules of this file; the checker reviews every change against this file as well as against its ticket; a piece that touches those cites the rules it follows.

- **Example.** `.claude/agents/checker.md` and `CLAUDE.md`, "How work is split", as amended by #401.
- **Counter-example.** Of 37 tickets after 2026-10-31 that touched targets or pages, 2 carried a rule (audit TESTS-6).
- **Source.** Owner decisions on #396, point 4, 2026-11-02 ("Owner rules written in the repo: yes"); audit rebuild proposal 1.

### OR-29. Open points of a PR become issues before it lands

A finding, placeholder or contradiction found in a PR is filed as an issue before the PR lands, not left in the PR's prose.

- **Example.** The list of places that contradict a rule, in the PR of #401.
- **Counter-example.** PR #74 flagged the crafted tier placeholder in its text and no ticket followed; 33 of 153 PRs parked findings in prose (audit TESTS-14).
- **Source.** Audit rebuild proposal 1 and TESTS-14; ticket #401.

### OR-30. The rebuild is accepted by rerunning the measurement

After the rebuild, `measure-sim/full` and the bloat step are run again, and their results are what is compared.

- **Example.** The simulation on concrete items matched the computed means on all 10 benchmark routes (max |z| 2.01; `measure-sim.yml`, run 41591954486).
- **Counter-example.** Page goldens accepted by their own regeneration, 43 commits (audit TESTS-5).
- **Source.** Comment on #396, 2026-11-04 (memory note `measurement-week-results.md`).

## Left out on purpose

- **The pannable board** (decision 6 of #396) is a v2 idea on the map ([#325](https://github.com/Rasslabsya4el/crafting-system/issues/325)), not a rule of reading; nothing is taken into work until the owner says so.
- **Rules the audit proposes but the owner did not state**, such as "a start price is required" and "done means reachable", are not here.
