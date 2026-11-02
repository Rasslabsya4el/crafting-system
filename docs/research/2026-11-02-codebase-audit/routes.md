# Audit area ROUTES: the ten benchmark routes, read as a Path of Exile crafter would (ticket #396)

Auditor: routes reviewer. Read-only on the repo; pages built on GitHub (branch `scratch/route-pages-1102`, script
`.github/scripts/route_pages.py`), downloaded to `.claude/scratch/audit/pages/` (run 41423936987 for R05, R08, R09, R10, R11, R12, R13,
V01; run 41424744960 for R04, which was killed after 18 min 17 s; run 41424775927 for R14, solved in 1,249 s, a 151 MB page). Prices are `tests/fixtures/prices/routes-allflame-2026-10-31.json`
(the same file the tests use). Game data: repoe-fork 3.29.3.3 in `local/cache/`.

## Per-route table

| route | planner mean | guide / given-route mean | verdict | main faults (finding ids) |
|---|---|---|---|---|
| R04 quiver | no page: the GitHub runner was killed after 18 min (ROUTES-11); ADR-0063's research script gives 69,716 c (187 Divine) | none | unknown | goal reads the guide's "100%" exalts as 13% and 20% (ROUTES-3); a guide-level craft is about 2,500 c by my rough estimate; price 9 c of a poe.ninja line against 130 c on trade (ROUTES-7) |
| R05 ring | 12.2 c (p90 17.9) | 135 c | artefact | bench craft counts as T1/T2 (seed); crafted mod drawn is not the one costed (ROUTES-1); 135 c is itself an artefact (ROUTES-2); buy any ring (seed); 20 catalysts silently dropped (ROUTES-4) |
| R08 ES boots | 104 c (p90 194) | 1,810 c | unknown: plausible, but not the guide's craft | route uses a 0.2 c Prismatic Fossil as a plain reroll, not Dense + Shuddering (ROUTES-6); Alchemy hidden and a white base bought (ROUTES-4); restricted action list not shown (ROUTES-5); 1,810 c is an artefact (ROUTES-2) |
| R09 life boots | 75.1 c (p90 160) | 1,300 c | unknown: plausible, but not the guide's craft | same as R08 |
| R10 boots | 128 c (p90 271) | 128 c (same route) | numbers trustworthy; goal stricter than the guide | Life T1 where the guide says "preferably at least 70": the same boots cost about 46 c (ROUTES-3); essence price is from an older league (ROUTES-8) |
| R11 helmet | 1,110 c (p90 2,520) | 1,110 c (same route) | numbers trustworthy; goal far stricter than the guide | T1 Evasion% and T1 Life where the guide says "you are happy with" (ROUTES-3); the guide's finishing craft and implicits dropped without a mark (ROUTES-4) |
| R12 amulet | 56.6 c (p90 128) | 56.6 c (same route) | trustworthy | start-item tier written as 3, data says T7 (ROUTES-10); an approximate mark that cannot apply (ROUTES-12) |
| R13 belt | 6,310 c (p90 14,600) | 12,100 c | plausible; the guide number is an artefact | crafted mod drawn is not the one costed (ROUTES-1); rebuys a 10 c belt where a 0.37 c Scouring does the same, action list not shown (ROUTES-5); ADR-0061 says level 84 costs 5,492 c, the page plans 86 (ROUTES-13) |
| R14 bow | 5,800 c (p90 not resolved); page of 87,272 steps, 151 MB (ROUTES-15) | never finishes: the guide's rules leave gaps | unknown: mean agrees with ADR-0063 (5,786 c) but nobody can read the page | 65,433 of the steps are the same "Restart" card, 251 are Alteration cards (the V01 seed at scale, ROUTES-15); goal reads the guide's "100%" exalts as 55% and 10% (ROUTES-3); buy spec accepts magic and rare bows (ROUTES-7); stale "cannot be solved" text (ROUTES-11) |
| V01 helmet | 866 c (p90 1,980) | no guide | artefact-ish / unknown | eight Regal steps (seed); 106 restarts at 8 c are 850 of the 866 c; only 4 orbs allowed and the page does not say (ROUTES-5); hand prices shown as Allflame prices (ROUTES-8); claim ids on the page (seed) |

### How the numbers were checked

For R05, R09, R10, R11, R12 I wrote an independent Monte Carlo from the raw `mods.json` / `fossils.json`
(pool by spawn tags and item level, family exclusion, 4/5/6 mods at 8:3:1 counting the fractured and essence mods, side limits) and compared the
"Chance per use" of each page. The engine's arithmetic holds everywhere I could test it; the faults below are about meaning, not arithmetic.

| quantity | page | independent Monte Carlo |
|---|---|---|
| R05 essence success (Life T1 or a T2 resistance) | 5.8% | 5.80% |
| R10 essence success (Life T1 and an open suffix) | 1.9% | 1.90% |
| R11 essence success (Evasion% T1 and Life T1) | 0.092% | 0.096% |
| R12 Harvest Reforge Lightning, +1 Lightning gems | 3.2% (the guide publishes the first-draw share 200/6950 = 2.88%) | 3.21% |
| R09 Prismatic: target / step-3 item | 0.077% / 2.3% | 0.068% / 2.2% |
| R09 Pristine + Shuddering: target / step-3 item | 1.6% / 1.1% | 1.4% / 0.9% (15-20% lower with the engine's tag rule, `implicit_tags` only; unexplained, my model may be incomplete) |

## Findings

### ROUTES-1: A crafted slot is drawn as a different mod than the one the step crafts; a goal leaf is drawn as a mod the item cannot have   [CONFIRMED] [impact: high]
- Where: `src/crafting_system/cli/_route_card.py:458-460` (`crafted()` prints `self.data.mods[slot.kind]`, the state's class representative, not the bench option the step used); the goal text of a family leaf (`_route_card.py` around 440-455, `_family_row`); pages `R05-r05-strength-ring.route.html` steps 3-4 and `R13-r13-life-resist-belt.route.html` goal card, steps 6 and 8.
- What it does: R05 step 3 is headed "Benchcraft: +(26-40) to maximum Life" and costs "6 x Orb of Transmutation" (mod `EinharMasterIncreasedLife2`), but its Goal row and the finished ring read "+(35-44) to maximum Life crafted", which is `StrMasterLifeCrafted1`, a mod no bench option adds (`crafting_bench_options.json` offers (15-25), (26-40) and (41-55) Life on a ring). R13, planner step 8: header "(24-32)% increased Elemental Damage with Attack Skills" (`EinharMasterWeaponElementalDamage2`), finished belt "(8-22)% increased Elemental Damage with Attack Skills crafted" (`DexMasterWeaponElementalDamageCrafted`, not a bench option). R13, given route step 6: header "(15-17)% increased Damage" (`JunMaster2AllDamage3`, 4 Exalted Orbs), finished belt "(9-11)% increased Damage crafted" (`JunMaster2AllDamage1`, not a bench option). The R13 goal card says "(11-15)% increased Damage . at least 1 of 2": that is `AllDamageInfluence1`, a prefix that spawns only with the `belt_adjudicator` tag, so a plain Leather Belt can never have it; the target file itself says the bench offers (12-14) and (15-17).
- What it should do: show exactly the mod the craft adds, with its range (owner: "a mod forced by an essence or bench craft is exactly that mod/tier"; "show every in-game step"), and name for a goal leaf only mods the item can carry. A player who reads "(35-44) Life" and goes to the bench finds no such option.
- Evidence: page text above; a python pass over `crafting_bench_options.json`: `StrMasterLifeCrafted1`, `JunMaster2AllDamage1` and `DexMasterWeaponElementalDamageCrafted` are in no option, while `EinharMasterIncreasedLife2`, `JunMaster2AllDamage3` and `EinharMasterWeaponElementalDamage2` are. R08, R09 and R10 crafts read right only because one mod stands for the class there. The committed golden `tests/golden/real_r05.html` already carries the "(35-44)" line, so a golden pinned it.
- Impact: every route with a bench craft whose class holds several mods: R05, R13 (and any later one). The mean is not changed (the right mod is costed); the picture is.
- Origin: #78 (120dc39, 2026-10-31, item cards of the route view), reviewed in #96 (f52d61b) on R10, R11, R05; the compressed state names a crafted mod by its canonical mod id (`src/crafting_system/abstraction/_state.py:56-68`), one id for every crafted mod with the same effect on the goal (ADR-0009), and the card reads that id back as if it were the mod.
- Pattern: a representative of an equivalence class printed as if it were the object.

### ROUTES-2: The pass rule "solver is no dearer than the guide" can never fail, and the "guide" means it is compared with are artefacts of the given-route files   [CONFIRMED] [impact: high]
- Where: `tests/test_cli_routes_real.py:131` (`assert plan.risk.mean.value <= result.risk.mean.value * (1 + 1e-9)`), `src/crafting_system/cli/_benchmark.py:525-531` (`_not_dearer`), ADR-0013 pass rule ("at equal prices the solver's route costs no more than the guide's"), `examples/routes/*.yaml`.
- What it does: the given route is a fixed policy evaluated in the planner's own model, stopping only at the target's goal, and every action it uses is offered to the planner, which minimises over a superset. So "solver <= guide" holds whatever the target says; the R05 run with 12 c against 135 c passed it. The guide's mean is whatever the YAML's rules make it, and those rules are stricter or poorer than the guide's text:
  - R05 135 c: the rule `rare -> Deafening Essence of Rage` runs until T1 Life or a T2 resistance is rolled (5.8% per use, 17.3 uses x 7.64 c). The guide says "until the other modifiers are useful ones, such as Maximum Life or Resistances", then the bench on an open modifier.
  - R08 1,810 c and R09 1,300 c: the rule `rare -> Dense + Shuddering` runs again whenever Movement Speed is present at any tier but 35%; the guide says "desirable Movement Speed".
  - R14: the given route as written leaves gaps (a state no rule matches), so the page says "never finishes: the route has gaps, success chance < 0.001%"; there is no guide mean to compare with at all (the completed `-restart.yaml` variant adds a rule "buy the start item again" that the guide does not contain).
  - R13 12,100 c: no Orb of Augmentation in the rules (116,000 Alterations); the planner's 6,310 c uses Augmentation (57,800 Alterations), which the guide's "Alt spam for T1 life and a resist" implies.
- What it should do: compare against what the guide fixes (its stated odds, which the benchmark does check, and costs where it states them), and mark a guide mean built from a YAML as the YAML's, with the YAML's stop rule printed.
- Evidence: the "Given route" sections of the pages (135 c, 1,810 c, 1,300 c, 12,100 c); `examples/routes/r05-strength-ring.yaml` (one rule), `r08-energy-shield-boots.yaml`, `r13-life-resist-belt.yaml` (no Augmentation).
- Impact: the "given route" half of every page and `benchmark.json` `solver_not_dearer`; the benchmark verdict in the README.
- Origin: ADR-0013 (grill round 1 Q7: "Guides state no cost, so the guide's cost is its given route"); #60 (3c123fc, 2026-10-31) wrote the first given routes and the assertion.
- Pattern: an oracle whose expected value follows from the code under test (the optimum compared with a restriction of itself).

### ROUTES-3: The owner's "unstated tier is the top tier" is applied where the guide states a number or a soft wish, so the targets are far harder than the guides' crafts and the page does not say so   [CONFIRMED] [impact: high]
- Where: `examples/targets/r04-penetrating-quiver.yaml` (`min_tier: 1` Life, `min_tier: 2` Bow Skills damage), `r14-hunter-bow.yaml` (`PoisonDamagePrefixInfluence4`), `r10-fractured-boots.yaml` (Life `min_tier: 1`), `r11-reservation-helmet.yaml` (Evasion% T1 and Life T1), `r08`/`r09` (35% Movement Speed rolled or crafted), `src/crafting_system/cli/_benchmark.py:178-196,219-233`, `tests/test_cli_r04_r14_real.py` rows.
- What it does: R04 step 8 of the guide: two Exalted Orbs "guarantee" Maximum Life and Increased Damage with Bow Skills (probability 1.0 in the research note). At the target's tiers the benchmark's own table computes 13% (2 in 15) and 20% (1 in 5): the last two orbs are about 38 times harder than the guide's. ADR-0063 reports the planner's value for this target as 69,716 chaos (187 Divine); a back-of-envelope guide-level craft (4 attempts of quiver 9 c + Insanity 45.5 c + annuls about 40 c + Fracturing Orb 260 c, then about 90 Deafening Rage essences at 7.64 c, then 1 Divine for the metamod, exalts certain) is about 2,500 c (rough, my arithmetic), a factor of about 28. R14: 100% against 55% and 10%, planner 5,800 c. R10: the guide says "+# to maximum Life, preferably at least 70", the target asks T1 (115-129). My Monte Carlo of the same essence reroll with Life of at least 70 (tiers 5 to 8, every roll of them is 70 or more) gives 7.65% per use against 1.90% for T1, a mean of about 17 + 13.1 x 2.13 + 1 = 46 c against the page's 128 c; the target for it exists (`examples/targets/r10-fractured-boots-70-life.yaml`, #71) but is not the benchmarked one. R11: the guide says "until Evasion/Life prefixes you are happy with"; the target asks Evasion% T1 and Life T1 (0.092% per use, 1,090 uses, 1,110 c, 3 Divine), which no crafter would spam. R13: "a crafted damage modifier" is read as any tier of two families, so the planner buys the cheapest craft ((24-32)% for 0.109 c) and the given route buys (15-17)% for 9.16 c: one target, two readings of the same words.
- What it should do: the owner's rule is about a tier nobody states. Where the source states odds or "at least N", the target must follow the source, or the page must say "stricter than the guide: the guide's own goal would cost X" (owner: cuts must say what they still guarantee).
- Evidence: `tests/test_cli_r04_r14_real.py:104-118` pins the rows ("100%", "13%", False) and ("100%", "20%", False) for R04 and ("100%", "55%", False), ("100%", "10%", False) for R14; `bootsim70.py` result 0.0765 against `bootsim.py` 0.0190 on the same pool.
- Impact: R04 and R14 (cannot be read at all, ROUTES-11), R10 (2.8x), R11, R08, R09; and every comparison with the guide (ROUTES-2).
- Origin: owner's tier rule, written into the targets in #96 (f52d61b, 2026-10-31); target files re-pinned in #352 (544981a, 2026-11-01); the "13%" rows in #70.
- Pattern: a rule of the owner generalised past the cases it was made for, with no mark where the result is stricter than the source.

### ROUTES-4: Guide steps and game steps that the page leaves out, unmarked   [CONFIRMED] [impact: medium]
- Where: `examples/targets/r08-energy-shield-boots.yaml:36-45` and `r09-life-boots.yaml:31-40` (start item comment and block), `examples/targets/r05-strength-ring.yaml` (catalysts), `r11-reservation-helmet.yaml`, `r04-penetrating-quiver.yaml`.
- What it does:
  - R08 and R09: the buy card says "Accepts Normal, item level 86 or more" and the next card draws "Rare, item level 86" with no mod. Fossils work on a rare item only (claim `fossils.resonator_rare_only`), so an Orb of Alchemy sits between the two cards. It is not a step (the word Alchemy appears nowhere in the page); its 0.027 c is added to the start price (price file note). The target says a real Alchemy gives 4 to 6 random mods and "a plan of it did not finish in 60 minutes (run 41292010467)", so it was left out to make the solve finish.
  - A rare start is not considered: a rare item of ilvl 86 with any mods is as good as a white one for a fossil route, because the first fossil erases whatever it holds, and it needs no Alchemy. Its trade price was not looked up (SUSPECTED that it is lower); the white Sorcerer Boots costs 29.8 c of R08's 104 c (22 listings), the white Two-Toned 5.0 c.
  - R05: the guide's goal includes "20% Intrinsic Catalyst quality" and its step 3 applies 20 Intrinsic Catalysts. The target says "left out, it is B2"; ADR-0013's B2 amendment says "R05 gains its catalyst line", ADR-0029 has the finish cost, ticket #159 is open. Nothing on the page says the quality is missing.
  - R11: the guide's step 2 ("finish with a crafted Resistance or Attribute") and its two Eldritch implicits are in the target file's comments only. R04: the guide's step 9 (remove the metamod, craft a suffix) likewise.
- What it should do: a step the game needs is a step on the page (owner: "show every in-game step; never hide one (a bought item drawn 'empty', ...)"), and a guide step the target does not cover is listed as "not planned" on the page.
- Evidence: page R08 steps 1-2; `grep -c -i alchemy` over the R08 and R09 pages gives 0; `grep -i catalyst` over the R05 page gives nothing.
- Impact: R08, R09 (hidden step, costed inside the start price), R05, R11, R04 (silent narrowing of the guide).
- Origin: #63 (60013ba, R08/R09); #60 (R05, R11); ADR-0013 B2 amendment versus the target comment.
- Pattern: a solve-time shortcut or scope cut shown as if it were the game.

### ROUTES-5: The route page never says which actions the planner was allowed; "Cheapest policy of the planner" is the cheapest among four to six kinds   [CONFIRMED] [impact: medium]
- Where: `actions:` in `examples/targets/r04, r08, r09, r13, r14, v01`; the text report prints "Not offered, N actions: reason" (`src/crafting_system/cli/_report.py:322`) but `_route_view.py` never reads `plan.left_out`; none of the eight pages contains "left out" or "not offered".
- What it does: R13 allows `[transmutation, alteration, augmentation, regal, bench-craft, remove-crafted-mods]`, so Orb of Scouring (0.37 c) is out and each of the 49.3 restarts rebuys a 10 c belt (493 c of 6,310 c, 7.8%); with Scouring the restart costs 0.37 c and the mean is about 5,840 c. R08 and R09 allow `[fossil-set, bench-craft]`, no Chaos Orb (1 c, no resonator), which is why a 1.59 c Prismatic Fossil use is the plain reroll (ROUTES-6). V01 allows four orbs ("Fewer kinds keep the state space small, so the benchmark solves in seconds"): no Annulment, Exalted or Chaos Orb.
- What it should do: "among these actions: ..." next to the mean, and the cut named with what it still guarantees (owner: "cuts must say what they still guarantee").
- Evidence: page texts; price file (`Orb of Scouring` 0.3668, `Chaos Orb` 1.0); target comments (R13: "more than 43,000 states after four minutes ... the pruning of ticket #118").
- Impact: R13, R08, R09, V01, R04, R14 (all means are bounds from above).
- Origin: target comments of #66 (R13), #63 (R08/R09), #331 (V01); the route view of #96 draws the policy only.
- Pattern: a search restricted for solve time presented as the optimum.

### ROUTES-6: On R08 and R09 the planner's route is not the guide's, and it exists because of two outlier prices   [CONFIRMED route, SUSPECTED prices] [impact: medium]
- Where: page R08/R09 step 2; `tests/fixtures/prices/routes-allflame-2026-10-31.json` (`Prismatic Fossil` 0.2, `Primitive Chaotic Resonator` 1.39, `Potent Chaotic Resonator` 1.39).
- What it does: R08's title is "Dense + Shuddering Energy Shield boots", the planner's step 2 is "Fossils Prismatic Fossil" (one Primitive Chaotic Resonator 1.39 c + one fossil 0.2 c). Prismatic only adds Elemental weight and removes Physical and Chaos ailment mods; it does nothing for Energy Shield or Life, so it is a plain reroll at 1.59 c. The guide's pair gives 0.96% target plus 1.3% "step-3 item" (2.26%) at 39.8 c a use; Prismatic gives 0.068% plus 2.2% (2.27%) at 1.59 c. The pair buys nothing here because Shuddering fills a prefix with a lower-tier Movement Speed that blocks the bench craft, and the target accepts no lower tier (ROUTES-3). So 104 c against 1,810 c is the right ratio for this target. But Prismatic costs 0.2 c where the next-cheapest fossil is Bloodstained at 4.0 c, and a 1-socket and a 2-socket resonator share one price. At a 4 c Prismatic the R08 mean would be about (1.39+4) x 44 + 30 + 4 = 271 c and R09's about 235 c, instead of 104 c and 75 c.
- What it should do: a price that decides the identity of the route is shown with its source and checked; the page explains why a fossil with no bearing on the goal is used.
- Evidence: page numbers above; price file lines; `fossils.json` `Prismatic Fossil` (`positive_mod_weights: elemental 600`, `negative_mod_weights: bleed 0, poison 0`). The independent Monte Carlo reproduces the chances (table at the top), so only the price is in doubt.
- Impact: R08 (104 c) and R09 (75.1 c) rest on it.
- Origin: #63 (60013ba) merged `routes-allflame-fossils-2026-11-01.json` into the one fixture.
- Pattern: an outlier input decides the shape of the answer without a mark.

### ROUTES-7: The buy spec and the target describe the start item twice, and they differ   [CONFIRMED for R05, R09, R12, R04; SUSPECTED for the R14 price] [impact: medium]
- Where: `examples/buy/*.yaml` against `examples/targets/*.yaml`; prices in the fixture.
- What it does:
  - R05: target `Amethyst Ring` (chaos-resistance implicit); the spec has no base; price 2.6 c is for any ring with a fractured All Attributes of 13 or more (602 listings) (seed).
  - R12: target Paua Amulet, item level 84, fractured Lightning Resistance `tier: 3, values [14]`; spec: any amulet, item level 75 or more, any fractured Lightning Resistance. The price 1.0 c is the mean of the five cheapest of 909, the site's floor. The page shows the start as "+(12-17)% Lightning Resistance . T7".
  - R14: the target starts from a Normal Hunter Thicket Bow; the spec's `rarity: nonunique` accepts magic and rare bows too, and the price (13 c) is the mean of the five cheapest of 164 such listings, probably magic or rare ones. Scouring is not in R14's action list, so a rare listing cannot become the planner's start item.
  - R09: target `BootsAtlas1` (Evasion and Energy Shield); the spec `base_type: Two-Toned Boots` matches all three Two-Toned bases (5.03 c).
  - R04: the target plans item level 81; the committed price (9 c) is a poe.ninja line of item level 85 (43 observations) because the trade search "found 3 listings (mean 130 Chaos)" (comment in `examples/buy/r04-start-quiver.yaml`). The owner's rule is trade, instant buyout, mean of the cheapest few; ADR-0061 allows the poe.ninja row only when the trade market is thin and says the page must say so. R04 restarts the quiver about four times (Fracturing Orb 25%), so 9 c against 130 c moves the cost by roughly 480 c (estimate; R04 has no plan to check it against).
- What it should do: one description of the start item, and the price taken for exactly that item (owner rules on trade and sources).
- Evidence: the files; the `R05 start ring`, `R12 start amulet` and `Thicket Bow (ilvl 78, Hunter)` entries of the fixture (`detail.query` shows `rarity: nonunique`, and no `type` for R05 and R12).
- Impact: start prices of R05, R12, R14, R09, R04; most of the R04 and R05 means.
- Origin: #60 (R05, R10, R11), #26 (R12), #70 (R04, R14), #63 (R08, R09); #351 and #354 (start options from the price file) are open.
- Pattern: one fact written by hand in two places with nothing reconciling them.

### ROUTES-8: Every page says "league Allflame, fetched 2026-10-31", but the prices come from different sources and ages, and the page does not show which   [CONFIRMED] [impact: medium]
- Where: the "Prices" line of every page; fixtures `tests/fixtures/prices/routes-allflame-2026-10-31.json` and `vendor-v01-2026-11-01.json`.
- What it does: R10's essence, 51.8 uses x 2.13 c = 110 c of its 128 c, is `Shrieking Essence of Spite` priced as "median of 5 poe.ninja daily rows in the 7 days ending 2026-06-13 of Mirage" (an older league, `source: poe.ninja-previous-league`). R11's `Shrieking Essence of Loathing` is exactly 1.0 c. V01's `Lion Pelt (ilvl 84)` (2 c) and `Vendor recipe gems (minion, 40% quality)` (6 c) are `source: hand`. R13's belt and R04's quiver are poe.ninja base rows (no instant-buyout proof; ADR-0061 says the report says so). R05, R08 to R12, R14 starts are trade means. The page shows one league and one date for all.
- What it should do: owner: "stale sources lose; every rule carries source, URL, quote, date"; a price that is a fallback, a hand value or an older league's says so on its line (ADR-0061 amendment: "marks the price so").
- Evidence: fixture entries (`detail.league: Mirage`, `source: hand`); page text has no source on any cost line.
- Impact: R10 (nearly all of the cost), V01 (start 8 c x 106 restarts = 850 of 866 c), R13, R04.
- Origin: price layer #21 / #355 / #357; V01 hand prices in #331; the previous-league fallback of the refresher.
- Pattern: provenance carried in the data and dropped at the page.

### ROUTES-9: Alternatives drawn as a numbered sequence, and "Accepts" that does not say what it accepts   [CONFIRMED] [impact: low]
- Where: R05 steps 3 and 4; R13 steps 4 and 5; V01 steps 3 to 10 (seed); `_route_view.py` numbering.
- What it does: R05 step 2's "Chance per use" lists "the item of step 3: about 64%, the item of step 4: about 10%", so steps 3 and 4 are two outcomes (craft Life, or craft Fire Resistance), yet they are numbered 1, 2, 3, 4 with arrows between, and step 4's picture is a different ring (Life "tier too low"). R13 steps 4 and 5 (Augmentation on two different magic belts) likewise. The essence and fossil cards say "Accepts: 4, 5 or 6 mods / other mods: any" for a reroll, which reads as a condition on the input when it is the number of mods the reroll leaves.
- What it should do: owner: "show every in-game step; never show the same route twice": a branch is shown as a branch.
- Evidence: page text.
- Impact: readability of R05, R13, V01.
- Origin: #96 / #78 flow numbering by discovery order.
- Pattern: internal state order shown as a player's order.

### ROUTES-10: R12's start item says tier 3, the game data says tier 7   [CONFIRMED] [impact: low]
- Where: `examples/targets/r12-lightning-amulet.yaml` (`mod: LightningResist2, tier: 3, values: [14]`, comment "check it by hand").
- What it does: `LightningResist2` is "+(12-17)%", required level 13, the second-lowest of eight tiers (`LightningResist8` is (46-48)% at 84); the page derives "T7". Nothing reconciles the hand-written tier with the data. R05 (1), R10 (2), R11 (1) agree with the data. It is inert today (the requirement is the bare family) but is read as meaning wherever a requirement names a tier.
- What it should do: derive the tier of a start mod from the data, or refuse a file whose tier differs (the comment still says "until the planner can derive tiers (ticket #23)").
- Evidence: `chk12.py` printout `r12-lightning-amulet LightningResist2 declared tier 3`; the page shows "T7".
- Impact: R12 now; any start item later.
- Origin: f6861f1 (2026-10-30, #19).
- Pattern: a value written by hand that the data already knows.

### ROUTES-11: R04 produces no page, and the reason the benchmark gives for R14 ("no approximate level, more memory than a runner has") is stale   [CONFIRMED] [impact: medium]
- Where: `src/crafting_system/cli/_benchmark.py:197,235` (`heavy=` strings), `tests/test_cli_r04_r14_real.py` docstring ("The planner's policy for either route was NOT produced ... a 16 GB runner is out of memory in about twelve minutes"), `tests/test_cli_r04_r14_real.py::test_the_default_run_is_refused_with_the_reason`; GitHub runs 41424744960 (R04) and 41424775927 (R14) of `route_pages.py`.
- What it does: `route_pages.py R04` ran 18 min 17 s on a 16 GB ubuntu runner and ended with "The runner has received a shutdown signal ... exit code 143" and no Python traceback and no R04 log line (the script writes its log only on return or exception), which is consistent with the memory death the docstring describes (ADR-0063: the object solver died at 15.7 GB on R04). So R04 has no page, no mean and no given-route mean; the only number is ADR-0063's research-script value, 69,716 chaos. `route_pages.py R14` on the same kind of runner solved in 1,249 s (total 1,295 s) and wrote a page (ROUTES-15), so the strings in `_benchmark.py` ("the exact graph has at least 787,000 states, more than a 16 GB runner holds, and no approximate level exists for a route with metamods") and the test docstring were true at #70 and are not true now. `benchmark` still answers "not solved: ..." for both, and the ADR-0013 acceptance of v1 (every batch passes its benchmark routes) rests on the two it does not solve.
- What it should do: the benchmark routes are the acceptance test (ADR-0013); a limit written into the code is re-measured when the solver changes (the packed solver of ADR-0063 landed in `cli/_packed.py`), and a route that cannot be solved is reported as unsolved on its page and in the README, not only as a refusal inside `benchmark --heavy`.
- Evidence: the two job logs (R04: tail above; R14: `R14.log` "ok solve 1249s total 1295s"); `tests/test_cli_r04_r14_real.py` lines 1-12.
- Impact: R04 (no reading at all), R14 (stale refusal text), and the whole metamod feature, which only these two exercise.
- Origin: #70 (paused), ADR-0023 / #69 (approximate level), ADR-0063 (#312).
- Pattern: a limit recorded as a fact in a docstring and a constant, and never re-measured.

### ROUTES-12: R12 shows an approximate mark that does not bear on the route, with the internal claim id   [CONFIRMED] [impact: low]
- Where: R12 page "Approximate inputs": `harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot: No source says whether a tagged reforge is refused when ...`.
- What it does: the claim is about a Harvest reforge refused when the tag has mods only on a full or locked side. In R12 the amulet has free slots on both sides and the reforge is never refused, so the mark cannot change the number; it is listed because the claim was consulted. The id is printed (seed).
- What it should do: list an approximate input only when a state of the policy depends on it (owner: unknowns get the best estimate and an approximate mark; a mark that never applies teaches him to ignore marks).
- Evidence: page R12 line 7; the policy has one reforge state.
- Impact: R12 (V01's three `vendor.*` marks do apply).
- Origin: ADR-0028 (approximate inputs named on every answer).
- Pattern: a mark attached by consultation, not by dependence.

### ROUTES-13: ADR-0061 and the target comments say the planner plans below the target's item level; no code does   [CONFIRMED] [impact: medium]
- Where: ADR-0061 decision 1 ("Measured: R13 5,492 / 5,638 / 6,311 Chaos at levels 84 / 85 / 86"); `examples/targets/r08-energy-shield-boots.yaml:31-32` ("the planner may plan the boots at 84 or 85 as well"); `src/crafting_system/targets/floor.py` (`floor_of`, `item_level_options`), `src/crafting_system/cli/_plan.py:343` (only `target.item_level`).
- What it does: `floor_of` and `item_level_options` are called by tests only (`grep` over `src/`: no caller outside `targets/`). The R13 page plans at 86 and costs 6,310 c, 15% more than the 5,492 c the ADR measured at 84; R08 is planned at 86 and priced for a base of 86 or more. Tickets #351, #353, #354 and #359 ("plan the start options and choose the cheapest") are open.
- What it should do: the ADR, the comments and the code say the same; the benchmark entry for R13 either plans the levels or says it plans one.
- Evidence: `grep -rn "floor_of\|item_level_options" src` finds only `targets/floor.py` and `targets/__init__.py`.
- Impact: R13 (up to 13% of its mean), R08.
- Origin: #352 (544981a) built the derivation only; ADR-0061 (2026-11-01) was written as if the whole of V1 existed.
- Pattern: a documented capability that no code calls.

### ROUTES-14: R10 labels the 30% Movement Speed "T2", although it is the top tier the item level allows   [CONFIRMED] [impact: low]
- Where: R10 page goal card and start card ("30% increased Movement Speed . T2").
- What it does: tiers are absolute per base (35% is T1 and needs item level 86); the boots are item level 84. A crafter reads T2 as "not the best I could have".
- What it should do: owner: "an unstated tier is the TOP tier the item level allows"; show "top at item level 84", or the range only.
- Evidence: page; `MovementVelocity6` required level 86.
- Impact: R10 reading.
- Origin: #96 (one mod-line format).
- Pattern: an absolute index shown where the player thinks relative to what is reachable.

### ROUTES-15: R14's page has 87,272 steps and is 151 MB; 75% of the steps are the same "Restart" card   [CONFIRMED] [impact: high]
- Where: `src/crafting_system/cli/_route_view.py` (one step per reachable state of the policy, #96: "every reachable state of each policy is in exactly one step"); `.claude/scratch/audit/pages/r14/run-ubuntu-latest-1/R14-r14-hunter-bow.route.html`.
- What it does: the page of the optimal R14 policy (mean 5,800 c, "9 runs in 10: not resolved on the grid (#190)") lists 87,272 steps: 65,433 "Restart: buy Thicket Bow (ilvl 78, Hunter) again" (each a separate card with the same normal empty bow and "On failure: the start item bought again (100%)"), 12,268 "Orb of Annulment", 9,207 "Exalted Orb", 251 "Orb of Alteration" (the first thirty or so steps after the Transmutation are Alterations and Augmentations of different magic bows), 40 "Cannot roll Attack Modifiers", 37 "Remove Crafted Mods", 13 "Orb of Augmentation", 9 "Regal Orb". The first card's "On failure" list names states of steps 3 to 84 and on, one line each. The file is 150,939,017 bytes (an Artifact page may hold 16 MB). The note says "how often a step is used and what it costs are left out: the policy is too large to solve here", so no card carries "Uses on average" or "Step cost". The number of cards equals the 87,271 states the optimal policy reaches (ADR-0063, "the optimal policy ... reaches about a tenth of the reachable states"): the page is the policy table, not a route.
- What it should do: owner: "detail no later decision sees is not tracked at all"; "show every in-game step; never show the same route twice". A crafter wants the route as the handful of things to do and the rule for each outcome. One card per compressed state is the V01 seed (eight Regal steps) at a scale where nobody can read it; 65,433 identical restart cards say that a state which only restarts is still kept apart by junk the restart does not read.
- Evidence: counts of `<h3>N. title</h3>` over the file; page head text; file size.
- Impact: R14 (and R04 once it solves); any large policy; the owner opening R14 gets a 151 MB file.
- Origin: #96 / #78 (the page shows every state), the state compression of ADR-0009 (the state is not coarsened for display), #190 (grid).
- Pattern: state or output detail that no decision reads (the same mistake as the V01 seed, in the display).

## Patterns seen in this area

1. A representative of a class printed as if it were the object (ROUTES-1; "at least 1 of N" as N lines in the seed; ROUTES-9).
2. An oracle that follows from the code under test: the optimum compared with a restriction of itself, the guide's mean read from a YAML written in the planner's own model (ROUTES-2).
3. The owner's rule generalised past its cases, with no mark where the target is stricter than the source (ROUTES-3).
4. A solve-time shortcut or search cut shown as game fact or as the optimum: the hidden Alchemy, the four-orb list, the missing Scouring, the missing catalysts (ROUTES-4, ROUTES-5).
5. An outlier or mixed-provenance input that decides the answer, with the page showing one source and one date (ROUTES-6, ROUTES-8).
6. One fact written by hand in two places with nothing reconciling them: start item and buy spec, tier of a start mod, ADR and code (ROUTES-7, ROUTES-10, ROUTES-13).
7. Coverage that stops where the problem is hard, and a limit written as a fact and never re-measured (ROUTES-11).
8. Output that lists the policy's states instead of the route: one card per compressed state (ROUTES-15, and the V01 seed).
