# The owner's rules

The document of record for how the owner reads a target, a price, a search and a route page. Builders, the checker and the tests read it; the main chat's memory and the issue comments no longer hold it alone. It was written for ticket [#401](https://github.com/Rasslabsya4el/crafting-system/issues/401), rebuild step 1 of the audit [#396](https://github.com/Rasslabsya4el/crafting-system/issues/396) (`docs/research/2026-11-02-codebase-audit.md`, class 7).

## How to read it

- One rule per entry, numbered `OR-1`, `OR-2`, ... A number is never reused. A rule that is replaced stays, marked **Replaced by**, so an old citation still leads somewhere.
- Each entry has the rule in one sentence, an example and a counter-example from a real route, target or page, and its source with a date. Where no real route shows a case, the entry says so.
- **Where two sources disagree, the later owner decision wins**, and the entry names the one it replaces.
- A rule says what the owner means. It does not say how the code does it. Where the code or a file differs today, that is an open point of the ticket that finds it, not a reason to bend the rule.
- A brief, a PR or a checker verdict cites a rule as `OR-n`.
- Sources named "memory note" are files in the main chat's memory. Their substance is copied here, so nothing outside the repository is needed to read a rule.
- Rules OR-35 to OR-52 are the owner's eighteen decisions of the retro of 2026-11-13, held in the dispatcher chat (his standing chat that starts the ticket chats) and written down in [#900](https://github.com/Rasslabsya4el/crafting-system/issues/900); decision *k* of that ticket is OR-(34 + *k*). Each has a one-line **Reason** as well. They stand in the group they belong to, so the numbers within a group are not in order. "The beta" in them is the website of OR-35 with the methods of OR-37.

## The product

The direction the owner set in the retro of 2026-11-13. An older rule, ADR or map line that disagreed is marked where it stands.

### OR-35. The product is a public website in November 2026

A public website opens in November 2026: the user builds an item as on Craft of Exile (the base, the prefixes, the suffixes and the rest of gear itemisation), picks the crafting methods the run may use and an economy mode, starts the run and gets a route page. The owner earns from ads and subscriptions later; an investor pays for the development.

- **Example.** None yet: no page of the site exists. What exists is the end of such a run, the route page the command writes (`<target>.route.html`, ADR-0015). The list of economy modes (softcore, hardcore and the like) is [#323](https://github.com/Rasslabsya4el/crafting-system/issues/323)'s to settle.
- **Counter-example.** A YAML target file written by hand and a command line as the only way in: v1 as ADR-0015 and the map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1) described it until this date.
- **Reason.** The product is for players and has to pay for itself, and a command line does neither.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 1).
- **Replaces.** "v1 has no HTTP service" of ADR-0015 (amended there) and the destination and the "UI, HTTP service and Docker" out-of-scope line of the map #1 (rewritten). The site, until now a v2 idea on [#325](https://github.com/Rasslabsya4el/crafting-system/issues/325), is the product.

### OR-36. Every generated route is stored and listed, and the same request is answered from the store

Every route the site generates is stored and listed on the site, so that other players take a ready one; an identical request is answered from the store. Reusing stored game maths (the outcomes of actions on a base) for other targets is a wanted optimisation after the beta.

- **Example.** None yet: nothing stores a route today, and no ticket builds the store ([#914](https://github.com/Rasslabsya4el/crafting-system/issues/914)).
- **Counter-example.** A run that plans again a request already answered; a route that exists only as one file on the machine that ran it (ADR-0015, "one file per query, no server").
- **Reason.** A route computed once serves every later player and costs nothing the second time.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 2).
- **Replaces.** "One file per query, no server" of ADR-0015 (amended there).

### OR-37. The beta is B1, B2 and B3 without the recombinator; the rest is "coming soon"; a beta method is never cut for speed

Batches B1, B2 and B3 without the recombinator are the beta, catalysts included. Corruption, Memory Strands, sockets, enchants, Hinekora's Lock and recombinators are shown as "coming soon" and built later; recombinators wait for players' 3.30 data. Methods of the beta are never cut to gain speed: if medium crafts grow past ten minutes as methods are added, the foundation is reviewed instead.

- **Example.** R06's catalysts are in the beta ([#901](https://github.com/Rasslabsya4el/crafting-system/issues/901)). Of B3 the Awakener's Orb and the beast imprints stay, and the recombinator routes R25 to R29 wait. In the batches of ADR-0013 the later methods are corruption (B4), Memory Strands (B5), sockets (B6), enchants (B7) and Hinekora's Lock (B8).
- **Counter-example.** The map's destination until this date, "all eight batches (B1–B8) pass their benchmark routes". For the second half, a method of the beta cut to gain speed, no case is named here.
- **Reason.** The beta has to open in November with every method it offers working end to end, and speed is won in the foundation, not by offering less.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 3).
- **Replaces.** The v1 scope of eight batches (ADR-0013 with [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81); amended there) and the destination of the map #1 (rewritten). Narrows OR-33: its ten minutes are also the mark past which the foundation is reviewed.

### OR-48. In November the player types in what he owns; reading the stash waits for GGG

In November the player may type in what currency and ingredients he owns; reading the stash waits for GGG's approval of the integration.

- **Example.** None yet: the site has no such input. The inputs of a run are [#323](https://github.com/Rasslabsya4el/crafting-system/issues/323)'s, and no ticket builds this one ([#914](https://github.com/Rasslabsya4el/crafting-system/issues/914)).
- **Counter-example.** A site that cannot open, or cannot serve an SSF player, until the stash integration is approved.
- **Reason.** GGG's approval is not in the project's hands and November is; typing it in gives the player the same answer without the integration.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 14).

### OR-52. Patch 3.30 is applied once, at the end of November, with 3.30 week-one prices

Patch 3.30 is applied once, at the end of November, with 3.30 week-one prices.

- **Example.** None yet: the data pin is 3.29.3.3 and the tests' prices are OR-44's 3.29 file. The move is one run of the skill `patch-update`.
- **Counter-example.** Moving the data pin or the test prices to 3.30 in the middle of November, while the routes are being fixed against 3.29.
- **Reason.** One move instead of a moving target: the routes are fixed against one patch and one price file, then moved once.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 18).
- **Replaces.** The earlier wording "no 3.30 update until v1 is built and tested" (owner, memory note `stay-on-329.md`; the comment "the owner keeps 3.29 until v1 is built" at `tests/family_bench_support.py:63` repeats it, [#913](https://github.com/Rasslabsya4el/crafting-system/issues/913)): the update now has a date, not a condition.

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
- **Counter-example.** `r10-fractured-boots.yaml` asks Life tier 1 where the guide says "preferably at least 70" (128 c). R11 asks Evasion and Life tier 1 where the guide says "prefixes you are happy with" (1,110 c).
- **A guide's "guarantee".** A guide that says an orb "guarantees" a mod guarantees its family, not its tier: R04's and R14's two Exalted Orbs after "Cannot roll Attack Modifiers" always add one of the two prefix families left, at a random tier. With no tier stated, OR-1 still asks the top tier, and the page shows the chance of each tier (OR-31). Source: owner in the main chat, 2026-11-06 ([#410](https://github.com/Rasslabsya4el/crafting-system/issues/410), point 2).
- **Source.** Owner decisions on #396, point 1, 2026-11-02 (memory note `audit-decisions-2026-11-02.md`).
- **Replaces.** OR-1 where a guide states a number, a tier or a wish. This is the answer to the first open question of the audit.
- **Narrowed by** OR-45 (owner, 2026-11-13) for reference targets: a soft wish of the guide does not make a reference target accept any tier of Life or defences. The two readings of R10 and R11 named above ("at least 70" Life with no tier; "prefixes you are happy with") are replaced by the owner's targets of [#895](https://github.com/Rasslabsya4el/crafting-system/issues/895): R10 Life tier 1 or tier 2, R11 Evasion tier 1 to tier 3 and Life tier 1.

### OR-5. A target never restricts the actions; a user setting may, and the answer shows it

A target states what to end with and what to start from, and every kind of action is offered and pruned by the search; turning a method off is a setting of whoever runs the planner ([#323](https://github.com/Rasslabsya4el/crafting-system/issues/323), the owner's list of user inputs), and the answer shows it (OR-13).

- **Example.** None. No target in `examples/targets/` meets this today: the seven with an `actions:` key (J01, R04, R08, R09, R13, R14, V01) name the allowed kinds, and a target without it gets the silent default of leaving out the opt-in kinds. The rule is the owner's decision, and R05 (no key, yet no Exalted Orb offered) is the nearest case.
- **Counter-example.** `j01-cobalt-life-attack-speed.yaml:23` (`actions: [chaos-orb]`); V01 (`v01-minion-helmet.yaml:44`) lists four orbs "because fewer kinds keep the state space small".
- **Source.** Owner decisions on #396, point 2, 2026-11-02, which says "as the norm" (memory note `audit-decisions-2026-11-02.md`): the silent opt-in default is "a hard contradiction" with the product. The user setting is #323, "turn methods off".
- **Narrowed by** OR-41 (owner, 2026-11-13): the setting starts with every method of the beta on, and the planner offers blocking and filler bench crafts by itself.

### OR-6. A start item is given or bought; how it was acquired is not modelled

A start item is a concrete item that is given or bought; where it came from (a Genesis Tree, for example) is not planned.

- **Example.** R10, R11, R12: a bought item with a fractured mod, priced by OR-7 and OR-8.
- **Counter-example.** A Genesis-born item modelled as an acquisition method. No route does this.
- **Source.** Memory note `snapshot-not-asking.md`, 2026-11-01; ADR-0043.
- **Note.** ADR-0059 admits one exception, the vendor recipe (V01), which ADR-0043 already names.
- **Narrowed by** OR-43 (owner, 2026-11-13): which rarity is bought, and what a bought fractured item holds. Starting over from it is OR-42.

### OR-41. Every method of the beta is offered by default; the planner offers blocking and filler bench crafts itself

Every method of the beta is offered to the planner by default, and the player switches off what he does not want. The planner also offers blocking and filler bench crafts by itself.

- **Example.** None yet ([#886](https://github.com/Rasslabsya4el/crafting-system/issues/886) builds it). The route it must find with nothing named in the target: fill the suffixes with a cheap bench craft, use an Exalted Orb for a guaranteed prefix, remove the craft.
- **Counter-example.** Today most strong methods are off unless a target names them (the Exalted Orb, the Orb of Annulment, the Fracturing Orb, fossils, Harvest add and remove, veiled mods, imprints, beasts), and a bench craft that is not a goal mod is not offered (#886). R05 is planned with no Exalted Orb offered (OR-5).
- **Reason.** The answer is the best route only among what was offered, so a method left off by default is a cheaper route the player never sees.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 7).
- **Narrows.** OR-5: the user setting it names starts with every beta method on.

### OR-42. Starting over costs the cheaper of buying the start item again or wiping the same item

Starting over costs the cheaper of buying the start item again or wiping the same item (an Orb of Scouring, plus an Orb of Transmutation or an Orb of Alchemy when needed); the wipe is a shown step. A fractured mod survives it; a corrupted item cannot be wiped.

- **Example.** None yet: no route page shows a wipe as the way to start over ([#914](https://github.com/Rasslabsya4el/crafting-system/issues/914)).
- **Counter-example.** V01: each of about 107 restarts buys a new helmet where a player scours the old one, and the page says nothing of the old item. R14: the guide's "back to step 1" is priced as buying another start item, 744 Chaos, 48% of the completed route (both [#687](https://github.com/Rasslabsya4el/crafting-system/issues/687)).
- **Reason.** A player wipes the item in his hand when that is cheaper than buying another.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 8).
- **Replaces.** "A restart buys it again" as the only way to start over (`GLOSSARY.md`, **Start item**, marked there). The wipe is a step of OR-16.

### OR-43. A bought base is the cheapest rarity the market sells; a bought fractured item is a Rare with random other mods

Where the guide names no rarity, the start is the cheapest rarity the market sells, and the steps that make it the needed rarity are shown and paid. A bought fractured item is a Rare with random other mods, marked approximate.

- **Example.** None checked against this rule yet; the `crafter` helper asks it of every page it reads (its question 2), and no ticket builds the rule for every bought start ([#914](https://github.com/Rasslabsya4el/crafting-system/issues/914)).
- **Counter-example.** R06 starts from a Normal Hunter belt with no market, while the guide accepts Hunter or Elder at any rarity ([#515](https://github.com/Rasslabsya4el/crafting-system/issues/515)). The bought fractured starts of R03, R05, R10, R11 and R12: the listing holds mods the target does not name, and the planner holds the fractured mod alone ([#656](https://github.com/Rasslabsya4el/crafting-system/issues/656)).
- **Reason.** A player buys what is listed cheapest and pays for making it the rarity he needs, and a fractured item on the market is a Rare with other mods on it.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 9).
- **Narrows.** OR-6 (the start item is still given or bought, and which rarity is bought is now a rule) and OR-17 for a bought fractured item. The mark is OR-23's.

## Prices

### OR-7. A trade price counts instant-buyout listings only, of any age; a marked fallback may stand in

The trade query asks for "Instant Buyout" and never "Instant Buyout and In Person", and sets no listing-age window; where no trade price exists, a poe.ninja row may stand in, and the price is marked as that fallback.

- **Example.** R10's start boots (ticket [#133](https://github.com/Rasslabsya4el/crafting-system/issues/133)): status `securable` and no `indexed` filter; the route page's trade link carries the same filters, so the link shows the listings the price came from. With `price_source` `both` (the default) the planner prices with the trade data and, when it is missing or stale, uses the poe.ninja row marked as a fallback with its reason.
- **Counter-example.** Before #133 the query status defaulted to `available` ("Instant Buyout and In Person"). A price from another league or source shown as a plain number is an unmarked fallback: the V01 page prints "league Allflame, fetched 2026-10-31" for every price whatever its source (audit INPUTS-3, ROUTES-8).
- **Source.** Owner on the R10 page, 2026-10-31 (memory note `owner-route-reading.md`; #133). The fallback: ADR-0061, decision 2 (owner answers of 2026-11-01, [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337)), and the setting `price_source` `ninja`/`trade`/`both` of [#357](https://github.com/Rasslabsya4el/crafting-system/issues/357).
- **Replaces.** The sentence of ADR-0007 (line 7) that the trade query "keeps only listings from the last week by default". Narrowed by the later ADR-0061, decision 2, for the marked fallback.
- **Narrowed by** OR-44 (owner, 2026-11-13) for the tests' prices: the 3.29 week-one file, and a marked hand-set price where the market price is plainly not what a player pays.

### OR-8. A price is the mean of the cheapest few while the market has enough offers

The price is the mean of the cheapest few instant-buyout listings, five by default, while the market has enough of them (the market rule of #355: at least 10 listings, at least 3 usable). When it has fewer, the price is the last one read in this league while the market had enough, marked as an old price with its date; when this league never had one, it is the mean of the listings there are, marked as a thin market. A search with no listings at all falls to OR-7.

- **Example.** A search that finds 5 listings, all priced far above the market by trolls (the end of the Allflame league, 2026-11-08): the page shows the price last read while the search found enough, marked old with its date; with none this league, the mean of the 5, marked thin.
- **Counter-example.** The mean of 5 troll listings shown as a plain price; a thin record dropped silently, so the route is priced from another source with no word of why.
- **Source.** Owner in the main chat, 2026-11-08, answer «в» (this ticket); the cheapest few: memory note `owner-route-reading.md`, 2026-10-31, #133.
- **Replaces.** The unconditional mean of the cheapest five, and for a thin record the "never offered" of #355 (ADR-0061).
- **Narrowed by** OR-44 (owner, 2026-11-13) for the tests' prices: one price per item, low essence tiers from the upgrade recipe.

### OR-9. The system refreshes prices itself

The user never runs a refresh or a data step; the system fetches prices on a schedule, within the trade limiter's budget, as part of a website service.

- **Example.** The scheduled refresher of ADR-0007's amendment ([#337](https://github.com/Rasslabsya4el/crafting-system/issues/337)).
- **Counter-example.** A design option "a trade price list the owner refreshes by command", which he corrected on 2026-11-01. No route shows it.
- **Source.** Memory note `system-self-serves.md`, 2026-11-01.
- **Replaces.** The sentence of ADR-0007 that the trade fetcher "runs only when the owner starts it", already widened by that ADR's amendment.

### OR-44. Tests use the 3.29 week-one price file: one price per item, low essence tiers from the upgrade recipe, a marked hand-set price where the market is not what a player pays

Tests use the 3.29 week-one price file, with one price per item and no ranges. Low essence tiers are priced from the upgrade recipe (three of a tier make one of the next). Where a market price is plainly not what a player pays (an odd fossil, a base with no real listings), a hand-set price is used and marked, and the owner may give the number.

- **Example.** `tests/fixtures/prices/routes-allflame-2026-07-31.json`, league Allflame on its day 7 ([#838](https://github.com/Rasslabsya4el/crafting-system/issues/838)), which the owner looked through and accepted on 2026-11-13. A Shrieking essence at a third of its Deafening one, and so on down ([#885](https://github.com/Rasslabsya4el/crafting-system/issues/885)).
- **Counter-example.** In that file before #885: Muttering Essence of Fear at 87 Chaos, and many Wailing and Weeping essences at 2 to 4 Chaos, above their Deafening tier, because nobody buys them. The hand prices that carry V01's total (the base and the gem set) are not in its price list ([#891](https://github.com/Rasslabsya4el/crafting-system/issues/891)): hand-set, and not marked.
- **Reason.** Tests need prices that do not move and that a player would pay in a league's first week, and a market nobody buys from is not a price.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 10).
- **Narrows.** OR-7 and OR-8 for the tests' prices: the marked hand-set price is a third marked kind, beside OR-7's fallback and OR-8's old or thin price. Replaces the snapshots of later days (2026-10-31, 2026-11-10) as the tests' default. It stands until OR-52's update.

## Search

### OR-10. Detail that no later decision reads is not tracked

The search keeps no detail that a later decision never sees, like a crafter who ignores junk.

- **Example.** R08 and R09: an Orb of Alchemy that only makes the boots rare before a fossil is one state, because the first fossil erases whatever the rare holds. (The step itself is still shown, OR-16.)
- **Counter-example.** V01 has 786 states of which 697 are dead ends that differ only in junk, and 91 remain when merged exactly; R12's reroll-only model keeps 33 states where 2 will do, R10's 425 where 2 will do (audit STATE-4, STATE-6).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

### OR-11. The answer is exact among realistic routes, never an interval

A good answer is exact among realistic routes; "approximate with an interval" reads as useless.

- **Example.** R12 (56.6 c) is an exact mean that an independent Monte Carlo of the audit matched. (R10's 128 c and R11's 1,110 c are exact for their targets as written, but OR-4 calls those targets too strict.)
- **Counter-example.** R04 and R14 at default flags are refused or answered "within a certified 1%" with no route page (audit PLANNING-15).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.
- **Replaces.** The resolution of [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81), question 2 (owner, 2026-10-31): exact when a query fits in about a minute, otherwise an approximate answer marked as such, with an error of at most 1%.
- **Replaced by** OR-32 (owner, 2026-11-13, [#822](https://github.com/Rasslabsya4el/crafting-system/issues/822) question 1), which restores #81's rule: exact when the whole plan fits in about a minute, otherwise a plan proved at most 1% above the cheapest. What stays of OR-11: the answer is a point (the plan and its exact mean), and the proof figure is a certificate beside it, never an answer given as an interval. Since 2026-11-13 the stop is OR-39's: the plan is shown as soon as it exists and the proof stops by itself at a proved 1% gap; what "exact" promises is OR-38.

### OR-12. No hard-coded cut-offs

The planner recognises an unrealistic branch by a general rule, not by a fixed number such as 100,000 uses of one step; the general rule is exact branch-and-bound against an incumbent route, with cuts whose tolerance comes from whether they could change the best route, and a fixed rail is only a stop-and-say-so safety net.

- **Example.** R04 has 177,242 states and 536 million transitions, and R08 with the Alchemy took more than an hour: cut them by the rule, not by a number.
- **Counter-example.** R13's target (`r13-life-resist-belt.yaml:28-35`) names its allowed kinds because a belt rerolled with a Chaos Orb has "more than 43,000 states after four minutes"; the cut is by graph size.
- **Source.** Memory note `realism-rails.md`, 2026-11-01, the owner's correction of the same day.
- **Replaces.** The first reading of that note, "configurable realism rails (100k uses per step)".
- **Narrowed by** OR-32 and OR-33 (owner, 2026-11-13, #822). The stop at a proved 1% (OR-32) is a stated tolerance on the proof of the cheapest plan, written beside the answer (OR-13); it never drops a branch for being unlikely or by a count, and every cut of the search stays exact. The 10-minute net of OR-33 is a stop-and-say-so net in the sense of this rule. Since 2026-11-13 that net is the default of a machine setting (OR-40), and no method of the beta is cut to stay under it (OR-37).

### OR-13. A cut says what it still guarantees

Every cut of the search states what the answer still guarantees.

- **Example.** A target with an `actions:` key prints "the plan is the cheapest among the named ones" in the text report.
- **Counter-example.** The route page of R13 and R14 says "Cheapest policy of the planner" with no word of the kinds left out (audit ROUTES-5, PLANNING-3).
- **Source.** Memory note `realism-rails.md`, 2026-11-01.

### OR-14. Unrealistic and useless branches are cut across the whole route

Pruning works on the route as a whole, not only inside one step.

- **Example.** R14 walks 816,153 item states. Its optimal policy has 87,251 item states, which merge into 65,147 classes reached, or into 14,742 blocks; the guide route has 946 acting item states (1 gap), which merge into 19 blocks. R04 walks 177,242 item states. Its optimal policy has 18,696 item states, which merge into 11,767 classes reached, or into 551 blocks; the guide route has 18,629 acting item states (13 gaps), which merge into 22 blocks. Units: an item state is a `CompressedState`; a class is the exact merge of states with the same future; a block is the exact lumping of the policy chain (`docs/research/2026-11-06-rebuild-6-inventory.md`, section 0).
- **Counter-example.** R14's page of 87,272 steps (151 MB), 65,433 of them the same Restart card, built on `86aa0b0` before the lumped view of #70. A page like that must not exist. Counted on `main` after #70 (heavy run 42243540582, `.github/scripts/page_size.py`, #465): 14,742 steps, 14,743 rows, 17.9 MB, one step per block of the lumped policy. Since #466 it is 12 steps, 13 rows, 0.067 MB (heavy run 42304575904, on `ce5e88b`).
- **Source.** Owner decisions on #396, point 3, 2026-11-02; measurement results on #396, 2026-11-04 (route-level pruning comes before a "minimal state").

### OR-32. Exact when the whole plan fits in about a minute; otherwise proved at most 1% above the cheapest, and said so

When the whole plan fits in about a minute, the plan is proved the cheapest of the offered methods; otherwise the planner stops when its plan is proved to cost at most 1% more than the cheapest, and the answer says so. In both cases the mean shown is the exact mean of the plan shown, and the proof figure ("no way of crafting this item with the offered methods costs less than Y") is a certificate beside that point answer, not an answer given as an interval.

- **Example.** R04 at the 2026-11-10 prices: the plan made from the walk-free bound alone costs 189,226.57 Chaos on average, exactly, and the bound proves that nothing costs less than 188,299.94, 0.49% less; the answer would be that plan, its exact mean and the proof figure, after the bound's build (99 s) and the plan's evaluation (12 s), once #826 and #689 are built (research note `docs/research/2026-11-13-planning-speed.md`, section 3; heavy run 43317321351). Today the whole plan takes 729 s (heavy run 42955861457).
- **Counter-example.** Today's search on the same route: 364 to 510 s and 165,980 item states spent after the plan is already in hand, to prove the last 0.49% (same note and run). A plan shown "within 1%" whose mean is itself an estimate is a counter-example too: the mean is always exact.
- **Source.** Owner in the main chat, 2026-11-13, answer (b) to question 1 of [#822](https://github.com/Rasslabsya4el/crafting-system/issues/822); his rule of [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81), question 2, 2026-10-31.
- **Replaces.** OR-11 ("exact, never an interval"); keeps its point answer. Narrows OR-12.
- **Narrowed by** OR-39 and OR-40 (owner, 2026-11-13). OR-39: the plan is shown as soon as an executable one exists and does not wait for the proof, and the proof stops by itself at a proved 1% gap. As #900's chat reads it (OR-39 says why this is a reading), "about a minute" no longer chooses between two kinds of answer: it is the time a plan aims at (OR-33) and, by OR-40, the default of the machine setting that guards against a hang. What stays of OR-32: the 1% tolerance, the exact mean of the plan shown, and the proof figure as a certificate beside it.

### OR-33. One plan aims at about a minute; a 10-minute net stops it and says so until every method has its bound

A plan aims to be ready in about a minute. Until every method family has its own bound (#822, ticket 4), a net of 10 minutes ends a longer plan with the best plan found, its exact mean and its proved gap, or with "no plan found yet" when none has closed, and says that it stopped (OR-12, OR-13).

- **Example.** R24, whose unveil offer has no bound yet (its walk took 1,838 s, PR #771), would stop at 10 minutes with "stopped after 10 minutes: this plan costs X on average; nothing costs less than Y", or with "stopped after 10 minutes, no plan found yet" if none had closed, as on R08's fossil sets, whose bound alone was not built 16 minutes in (heavy run 43320834722).
- **Counter-example.** R07 killed out of memory after 7 minutes with no answer ([#770](https://github.com/Rasslabsya4el/crafting-system/issues/770)); R25 runs cancelled after about 50 minutes ([#225](https://github.com/Rasslabsya4el/crafting-system/issues/225)).
- **Source.** Owner in the main chat, 2026-11-13, answer to question 2 of #822: (a) one minute as the goal, (b) ten minutes as the net until every method family has its bound.
- **Narrowed by** OR-40 and OR-37 (owner, 2026-11-13). OR-40: the 10 minutes are the default of a machine setting and a guard against a hang, never a figure sized for a GitHub runner and never the normal way a simple or medium craft ends. OR-37: when medium crafts grow past ten minutes as methods are added, the foundation is reviewed; no method of the beta is cut.

### OR-38. "Exact" means the best route under the rules given to the system

The rules given to the system for a method are the absolute: the route must be the best one under those rules, and it is not asked to match the game where the game's odds are unknown. The site need not state an accuracy figure.

- **Example.** The beast influence recipes are modelled as that influence's Exalted Orb and marked unverified (ADR-0013, the B2 amendment): the plan is the cheapest under that rule. The owner on Memory Strands, 2026-11-01 (ADR-0013, the B5 amendment): the system reproduces the evidence gathered, and matching the real game beyond that is not required.
- **Counter-example.** An answer held back because the game's true odds for a method are unknown, or a page line "accurate to N% of the game". No route shows either.
- **Reason.** The game's hidden odds cannot be checked and the rules written down can, so the promise is the one that can be kept.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 4).
- **Note.** OR-23 stands: an input that is an estimate is still marked approximate on the answer. That mark names the input; it is not an accuracy figure for the route.

### OR-39. A plan is shown as soon as an executable one exists; the proof goes on and stops by itself at a proved 1% gap

A plan is shown as soon as an executable one exists; the proof goes on and stops by itself at a proved 1% gap. The shown plan is replaced only by a notably better one, and that threshold is set from measurements. Whether a "keep searching" button exists is decided from measurements.

- **Example.** R04 at the 2026-11-10 prices (OR-32's example): the plan made from the bound alone costs 189,226.57 Chaos on average and nothing costs less than 188,299.94, a gap of 0.49%, so the plan is shown when it exists and the proof has nothing left to do ([#826](https://github.com/Rasslabsya4el/crafting-system/issues/826) builds it).
- **Counter-example.** Today's search on the same route spends 364 to 510 s after the plan is in hand and shows nothing meanwhile (OR-32's counter-example). A page that swaps the route the player is reading for one a fraction of a percent cheaper; none is measured yet.
- **Reason.** A player wants a route he can start on, not to wait for a proof, and not a route that keeps changing under him.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 5).
- **Narrows.** OR-32: the plan no longer waits for its proof, and the proof stops by itself at a proved gap of 1%. The decision does not name OR-32's "about a minute". The reading of the chat that wrote this rule down (#900), not the owner's word: the stop is the 1% gap whatever the time, so the minute no longer chooses between two kinds of answer (a proof that closes completely is the same answer with a gap of 0); it stays the time a plan aims at (OR-33) and the default of the machine setting (OR-40). [#826](https://github.com/Rasslabsya4el/crafting-system/issues/826)'s text still has the minute as that switch (a comment there says so). What OR-32 says of the exact mean of the plan shown, and of the proof figure as a certificate beside it, stands.
- **Open.** No ticket yet measures the threshold of "notably better" or decides the "keep searching" button ([#914](https://github.com/Rasslabsya4el/crafting-system/issues/914)).

### OR-40. A time or memory limit is a setting of the machine and a guard against a hang

A time or memory limit is a setting of the machine, a guard against a hang, never a figure sized for a GitHub runner and never the normal way a simple or medium craft ends.

- **Example.** The planner takes the limits of a run in its settings from whoever calls it (ADR-0018, the amendment of [#880](https://github.com/Rasslabsya4el/crafting-system/issues/880)), and a run that a limit stopped says so in its answer (OR-13).
- **Counter-example.** The generated family benchmark, where 6 targets end at the 10-minute net ([#871](https://github.com/Rasslabsya4el/crafting-system/issues/871)): the net as the way a craft ends. A limit chosen so that a run fits a 16 GB GitHub runner; no place is named here.
- **Reason.** The site runs on its own machine, not on a GitHub runner, and a limit that ends ordinary crafts hides a slow foundation.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 6).
- **Narrows.** OR-32 and OR-33: "about a minute" and the 10-minute net are no longer fixed figures of the product; they stand as the defaults of that setting until measurements change them. This is about the planner's limits only, not the timeouts of heavy runs or the caps of CI. (Both sentences are the dispatcher chat's, written in `CLAUDE.md` on 2026-11-13 and moved here by #900.)

## The answer and the page

### OR-15. Every mod line is in one format

All mod lines on a page share one format, and a mod never shows a different mod's text.

- **Example.** The V01 golden (`tests/golden/v01_minion_helmet.txt`, `.html`): `+(130-144) to maximum Life · T1`, the same shape in every card.
- **Counter-example.** R05's bench step draws `DexMasterLifeCrafted1` "+(35-44)", a mod no bench option adds; "at least 1 of 4" is flattened into four lines with notes (audit PRES-2, PRES-7).
- **Source.** Owner on the R10 page, 2026-10-31 (he had asked before); issue #96, first comment.
- **Narrowed by** OR-47 (owner, 2026-11-13): the format gains the mark of a fractured mod, and an essence's mod carries the essence's tier in place of a tier number.

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
- **Narrowed by** OR-43 (owner, 2026-11-13) for a bought fractured item: it is a Rare with random other mods, and the answer is marked approximate. The wording of the line stays.

### OR-18. One page step is one player step

A page step is the set of states on which the policy takes the same player action, no more and no less: states with different actions branch, and nothing else splits one action into several steps, neither its chance nor a detail the search does not track (their mixture is OR-20).

- **Example.** V01 has 3 player actions (audit PRES-1).
- **Counter-example.** V01's page has 11 rows for those 3, and R14's page had one step per state (14,742 steps counted on `main`, 87,272 before #70) because the "same exact chance" refinement in `cli/_route_flow.py` split one action by chance and, past `REFINE_WORK`, made every state a step (audit PRES-1; counts in OR-14). #466 removed both.
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

### OR-31. A step that can add a wanted mod shows the chance of each tier

When a step can add a mod of a family the target wants, the page shows the chance of each tier of that family (T1, T2, ... and "none"), with the target's tier marked, not only whether the requirement is met.

- **Example.** R04's first Exalted Orb after "Cannot roll Attack Modifiers" adds Maximum Life or Increased Damage with Bow Skills every time (100%), and a top-tier mod of whichever lands 2 times in 15; the step shows the share of every tier of both families.
- **Counter-example.** The R04 benchmark's check of the published odds (`tests/test_cli_r04_r14_real.py:104-111`) gives the first Exalted Orb only two numbers, 100% at any tier and 13% at the top tier, with nothing for the tiers in between.
- **Format.** Runs of tiers with equal chances are joined ("T2 to T10 1.4% each"); the target's tier stays apart. Source: owner in the main chat, 2026-11-06 ([#491](https://github.com/Rasslabsya4el/crafting-system/issues/491)).
- **Source.** Owner in the main chat, 2026-11-06: the system should say "T1 this chance, T2 this chance, and so on".

### OR-34. p50 and p90 to ±10%, added after the route

The p50 and p90 of a plan are given to within ±10% (the half-width of the bracket: the bracket is at most 20% of the figure wide); the route and its exact mean are shown at once, and the percentiles are added when they are done.

- **Example.** R14 at the 2026-11-10 prices: p50 7,319 Chaos, between 6,655 and 7,984 (±9%), after about 6 minutes of percentiles (heavy run 42955861457); the route is on the page before them.
- **Counter-example.** R14's finer step, ±4.8%, which brought the 16 GB runner to 14.9 GB ([#744](https://github.com/Rasslabsya4el/crafting-system/issues/744)); a page held back until the percentiles end.
- **Source.** Owner in the main chat, 2026-11-13, answer (b) to question 3 of [#822](https://github.com/Rasslabsya4el/crafting-system/issues/822), with research into a method whose precision does not degrade on long crafts. That the bracket is printed is the owner's choice on [#709](https://github.com/Rasslabsya4el/crafting-system/issues/709), 2026-11-12.
- **Narrows.** The owner's choice (a) on #709, 2026-11-12, which printed the bracket with no required width: the width is now required, ±10%.

### OR-47. A fractured mod is marked as fractured wherever the item is shown; an essence's mod is shown with the essence's tier

A fractured mod is marked as fractured wherever the item is shown; a mod from an essence is shown with the essence's tier.

- **Example.** None yet ([#895](https://github.com/Rasslabsya4el/crafting-system/issues/895) builds it): R10's Intelligence from the Shrieking Essence of Spite would read as the Shrieking tier's mod.
- **Counter-example.** The R10 and R11 pages the owner read on 2026-11-13 did not show the fracture, and R10's Intelligence from the essence carried "T2" where the owner wants the essence's tier (#895).
- **Reason.** A player reads a fractured mod as the one he cannot lose, and an essence's mod by its essence.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 13).
- **Narrows.** OR-15: the one format of a mod line gains these two marks.

## Evidence

### OR-21. Build on today's snapshot; no fixed ranking of sources

Rules are built on the information that exists now, even where old; GGG notes, the wiki, repoe-fork data, Craft of Exile (pages, data and code) and large-sample player experiments all count, and a source that current data shows out of date loses.

- **Example.** Harvest follows Craft of Exile's implementation where the documentation is incomplete; the 3.25 recombinator guide still stands.
- **Counter-example.** Craft of Exile's 3.29.0.3 essence entries, bench prices and removed Harvest crafts were stale against the 3.29.3.3 data and lost.
- **Source.** Memory note `evidence-ranking.md`, 2026-10-30; ADR-0005.
- **Narrowed by** OR-46 (owner, 2026-11-13): for the outcome of a single action Craft of Exile's emulator is the reference. For everything else this rule stands, and so does its counter-example: where current game data shows the emulator out of date, the stale source loses (the reading of #900's chat; [#915](https://github.com/Rasslabsya4el/crafting-system/issues/915) asks the owner).

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

### OR-49. Game facts the owner gave on 2026-11-13

Eater of Worlds and Searing Exarch influence acts on implicits, and the other influences act on affixes; they do not mix through the Awakener's Orb, and a Hunter's Exalted Orb does not apply to an item with an Eldritch implicit or with Hunter influence. Prime resonators are rare and dear; Chromatic Orbs were made rare in 3.29.

- **Example.** The Prime Chaotic Resonator at 160.7 Chaos and the Chromatic Orb at 1.9 Chaos in the 3.29 week-one file stand as they are ([#885](https://github.com/Rasslabsya4el/crafting-system/issues/885)).
- **Counter-example.** A plan that uses a Hunter's Exalted Orb on boots that hold an Eldritch implicit, or that joins an Eldritch implicit to another item through the Awakener's Orb. No route shows either.
- **Reason.** He knows these from play, and a route that breaks one of them cannot be done in the game.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 15).
- **Note.** These are sources of kind `owner` (OR-21, OR-22). OR-25 is about his opinion on a method of search, not about what he saw in the game.

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
- **Narrowed by** OR-45 (owner, 2026-11-13): he supplies one or two mirror-tier references when asked. He still writes no target, route or test file.

### OR-28. The owner's rules are read by whoever builds and checks

A brief that touches targets, routes, prices or pages names the rules of this file; the checker reviews every change against this file as well as against its ticket; a piece that touches those cites the rules it follows.

- **Example.** `.claude/agents/checker.md` and `CLAUDE.md`, "How work is split", as amended by #401.
- **Counter-example.** Of 37 tickets after 2026-10-31 that touched targets or pages, 2 carried a rule (audit TESTS-6).
- **Source.** The owner's only word is "yes" to "owner rules written in the repo" (#396, point 4, 2026-11-02). That briefs and the checker read the file is the main chat's process from the audit's rebuild proposal 1 and TESTS-6, not an owner statement.

### OR-29. Open points of a PR become issues before it lands

A finding, placeholder or contradiction found in a PR is filed as an issue before the PR lands, not left in the PR's prose.

- **Example.** The list of places that contradict a rule, in the PR of #401.
- **Counter-example.** PR #74 flagged the crafted tier placeholder in its text and no ticket followed; 33 of 153 PRs parked findings in prose (audit TESTS-14).
- **Source.** A process rule of the main chat, from the audit's rebuild proposal 1 and TESTS-14 and ticket #401; not an owner statement.

### OR-30. The rebuild is accepted by rerunning the measurement

After the rebuild, `measure-sim/full` and the bloat step are run again, and their results are what is compared.

- **Example.** The simulation on concrete items matched the computed means on all 10 benchmark routes (max |z| 2.01; `measure-sim.yml`, run 41591954486).
- **Counter-example.** Page goldens accepted by their own regeneration, 43 commits (audit TESTS-5).
- **Source.** A decision of the main chat, posted as a comment on #396 on 2026-11-04 (memory note `measurement-week-results.md`); not an owner statement.

### OR-45. A guide's route is a ceiling, not the truth; a reference target is an item a player would craft

A guide's route is a ceiling, not the truth: the planner may honestly find a cheaper one, and a much cheaper one is reviewed. The guide's cost is its steps priced by our rules at the test prices. A reference target is an item a player would craft: no "any tier" on Life or defences. Guides from 2020, guides whose key step no longer exists, and targets the project invented itself are not references. The owner supplies one or two mirror-tier references when asked.

- **Example.** The owner's targets of 2026-11-13 ([#895](https://github.com/Rasslabsya4el/crafting-system/issues/895)): R10's boots ask Life tier 1 or tier 2, R11's helmet Evasion tier 1 to tier 3 and Life tier 1. R08 and R09 are kept with named tiers, and their "6% of the guide" verdict is measured again ([#901](https://github.com/Rasslabsya4el/crafting-system/issues/901)): a much cheaper route, reviewed.
- **Counter-example.** R10 and R11 with Life at any tier: "nobody buys or crafts boots with tier 10 Life" (the owner, #895). R15 and R18, guides from 2020; R07, whose guide rests on the old Veiled Chaos Orb; V01 and J01, targets the project invented (#901).
- **Reason.** A verdict against a guide means something only when the target is an item players make and the guide can still be followed.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 11).
- **Narrows.** OR-4 for reference targets: a guide's soft wish does not make a reference target accept any tier of Life or defences (the R10 and R11 readings in OR-4's entry are replaced by the targets of #895). OR-27: agents still find the references, and the mirror-tier ones come from the owner when asked. The benchmark list R01 to R30 of ADR-0013 (amended there).

### OR-46. Every changed route page is read by the `crafter` helper as a player; the owner gets a short digest; the emulator is the reference for one action

Every changed route page is read by the `crafter` helper as a player before it lands. The owner gets a short digest at checkpoints (the target, the cost against the guide, the crafter's verdict) and full pages only where the crafter doubts or the cost is far from the guide. Craft of Exile's emulator is the reference for the outcome of a single action, as Path of Building is for builds.

- **Example.** `.claude/agents/crafter.md` and `CLAUDE.md`, "How work is split" ([#888](https://github.com/Rasslabsya4el/crafting-system/issues/888)). Seven emulator cases of 12,000 uses each agreed with the planner's chance of one use of the Exalted Orb on J01 and V01 (`docs/research/2026-11-13-637-exalt-key.md`, [#637](https://github.com/Rasslabsya4el/crafting-system/issues/637); skill `coe-emulator-check`).
- **Counter-example.** Before #888 no one read a page as a player before it landed. The helper's trial run found on R11's recorded page that a helmet with three full suffixes counts as finished, while the guide rolls until an open suffix ([#890](https://github.com/Rasslabsya4el/crafting-system/issues/890)).
- **Reason.** Tests do not see what a player would call wrong, and the owner does not read every page himself.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 12).
- **Narrows.** OR-21 (and ADR-0005, amended there): for the outcome of a single action the emulator is the reference, where OR-21 names no ranking of sources. The decision does not say what happens where current game data shows the emulator out of date, the case of OR-21's counter-example. The reading of the chat that wrote this rule down (#900), not the owner's word: there OR-21 still stands, the stale source loses, and the disagreement is filed as an issue; the question is put to the owner in [#915](https://github.com/Rasslabsya4el/crafting-system/issues/915). OR-24 is unchanged: a doubtful mechanic goes beside the emulator first.
- **Replaces.** The sentence of `CLAUDE.md` that the dispatcher chat shows the owner every benchmark page at each checkpoint (changed there).

### OR-50. The architecture, the language and the maths are the dispatcher chat's call

The owner is not a developer or a mathematician and leaves the architecture, the language and the maths to the dispatcher chat, including a rewrite of the core in a compiled language if measurements support it; he must be told each such decision in product terms. The frame must be easy to copy and rework for Path of Exile 2.

- **Example.** Planning moved into a module of its own with one entry ([#880](https://github.com/Rasslabsya4el/crafting-system/issues/880), ADR-0018's amendment). A compiled kernel generator is measured against today's Python before anything is rewritten ([#881](https://github.com/Rasslabsya4el/crafting-system/issues/881)).
- **Counter-example.** A question to the owner about which search or which language to use. No real case is recorded here.
- **Reason.** He decides what the product does and what he pays for it; how it is built is decided by whoever can measure it (OR-25).
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 16).
- **Note.** The ADRs on the language and the modules (ADR-0010, ADR-0016, ADR-0018) stand until the dispatcher chat changes one by an ADR; this rule says whose decision that is. Path of Exile 2 itself stays outside the beta (the map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1), "Out of scope").

### OR-51. Every chat and helper runs on Fable 5.2 until the owner says to go back

**Ended 2026-11-14** (owner in the dispatcher chat: the Fable allowance ran out; back to Opus 5.5). The rule of 2026-11-10 applies again: every chat on Opus 5.5 with effort medium, the helpers on their own models (`CLAUDE.md`, "How work is split").

Every chat and helper runs on Fable 5.2 until he says to go back to the earlier rule.

- **Example.** A chat passes `model: "fable"` when it starts `finder`, `checker` or `crafter`, whatever their own files say (`CLAUDE.md`, "How work is split").
- **Counter-example.** A helper started with no model named, which runs on the model of its own file (Haiku 5.5 or Sonnet 5.5).
- **Reason.** It is temporary: his Fable allowance.
- **Source.** Owner in the dispatcher chat, the retro of 2026-11-13 ([#900](https://github.com/Rasslabsya4el/crafting-system/issues/900), decision 17).
- **Replaces, for now.** The rule of 2026-11-10 it returns to: every chat on Opus 5.5 with effort medium, the helpers on their own models (`CLAUDE.md` keeps its text).

## Left out on purpose

- **The pannable board** (decision 6 of #396) is a v2 idea on the map ([#325](https://github.com/Rasslabsya4el/crafting-system/issues/325)), not a rule of reading; nothing is taken into work until the owner says so. The website itself is no longer on that list: it is the product (OR-35).
- **Rules the audit proposes but the owner did not state**, such as "a start price is required" and "done means reachable", are not here.
