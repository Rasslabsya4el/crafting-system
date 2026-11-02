# Audit area: THE TESTS AND THE PROCESS (ticket #396)

Auditor: tests/process. Read-only. Everything below was read in the repo at `claude/217-recomb-state` (head 86aa0b0) or reproduced with
single quick commands (`pytest --collect-only`, two targeted test files, one snippet on the real 3.29.3.3 cache, `gh` reads).
Raw pulls I used are in this folder: `_collect_tests.txt` (pytest collection of all 31,027 tests), `_prs_tests.json` (153 PR bodies),
`_issues_tests.json` / `_issues_tests2.json` (243 issues with bodies).

## 0. The numbers that explain "30,000 green tests, faults seen in minutes"

- Collected: **31,027 tests** (CI Ubuntu run of 2026-11-02: 31,106 tests, 30,245 passed, **861 skipped**, 0 failed).
- By what they test (file-name families, `_collect_tests.txt`):

| Family | Tests | Share |
|---|---|---|
| solver math on random abstract graphs (`test_solver_*`, `test_packed*`, `test_prune*`) | 15,732 | **50.7 %** (one file, `test_solver_peek_oracles.py`, holds 10,154 = 33 %) |
| actions (contract suite 2,079 + per-family) | 5,530 | 17.8 % |
| risk math (quantiles, CVaR, budget grids) | 2,421 | 7.8 % |
| abstraction (compressed state, layer 1) | 2,336 | 7.5 % |
| prices / trade (recorded fixtures) | 885 | 2.9 % |
| targets (parse, goal, floor) | 736 | 2.4 % |
| items, data, simulator, rules, layering, other | ~3,000 | ~10 % |
| `cli` (report, route page, offers, verify) | 610 | 2.0 % |
| tests that plan a real route end to end (R04..R14, V01, strands, packed) | ~175 | **0.56 %** |
| comparison with Craft of Exile (`test_proto_*`, `test_coe_*`) | 101 | 0.3 % (24 of them SKIPPED in CI: no local CoE copy) |

- ~59 % of the suite (solver + risk + simulator) is arithmetic on synthetic graphs. It has strong, genuinely independent oracles
  (brute force over policies, HiGHS LP, exact fractions) and says **nothing about what a PoE item or a route page means**.
  The faults the owner saw live in the 2 % that touches targets/pages and the 0.56 % that plans a real route, where the only oracles
  are goldens, "no dearer than the guide", and `--verify` (all of which share the code's reading).
- Goldens: 26 files in `tests/golden/`, 43 commits, 22 commit messages that say "regenerate / re-make / golden".
- Tickets: of 199 issues with a "Done when" section, 8 mention Craft of Exile/emulator, 13 a wiki/published number, 38 an oracle or brute
  force (all mechanic tickets); 18 carry the line "solver mean no more than the given route's"; 3 carry a golden as the acceptance.

## 1. Test layers: what each compares against

"Independent" = a source outside the code under test (game data, a published number, a hand-computed case, the owner's rule).

| # | Layer (size) | Compares the code against | Independent? | Circular points |
|---|---|---|---|---|
| L1 | Contract suite (`test_actions_contract.py` 2,079; `contract_support.py`) | the action against its own declarations: outcomes vs `chance_all` vs `sample()` vs declared `reads`/`adds`; kernel vs brute force of the same outcomes | internal consistency only | `contract_support.py:296-312` `finished()` is built from `part.distribution` (the code's); `:494-497` and `:500-511` compare two paths of one `Outcomes` class; `:314-317` `_roll_in` takes tiers from `tier_table(...).get(mod_id, 1)`; docstring `:10` "each against something written without the code under test" is true of the listing, not of the rules |
| L2 | Hand oracles (`actions_oracle`, `essence_oracle`, `fossil_oracle`, `magic_oracle`, `metamod_oracle`, `jewel_oracle`, `influence_oracle`, `awakener_oracle`, `recombinator_oracle`, `abstraction_adds_oracle`) | a second implementation of the rules, typed by hand over a hand-typed pool, exact `Fraction`s | independent of the code; **not of the claim**: each says "the claims of the registry, written again as plain code" (`abstraction_oracle.py:8`, `actions_oracle.py:8`, `essence_oracle.py:9`, `fossil_oracle.py:10`, `jewel_oracle.py:9`, `magic_oracle.py:5`, `metamod_oracle.py:7`, `abstraction_adds_oracle.py:8`, `abstraction_metamod_oracle.py:9`) | one spec read twice by one author; a wrong claim is wrong in both |
| L3 | Layer-1 abstraction checks (2,336; `abstraction_oracle.py`, `coarse_support.py`, `abstraction_*_support.py`) | the compressed kernel vs full enumeration of finished items | independent for compression; shares the rules, the pool (`from crafting_system.actions import PoolFamily, build_pool`, `abstraction_oracle.py:33`) and the placeholders | `abstraction_oracle.py:148` `crafted_item` = `ExplicitMod(mod_id, 1, low, crafted=True)` (the bench placeholder `CRAFTED_TIER = 1` re-typed); `:78` and `:142` `tier_table(...).get(mod_id, 1)`; `abstraction_metamod_oracle.py:175` `low_roll(data, mod_id, 1, crafted=True)` |
| L4 | Real-data tests (50 `*_real.py` files, 831 tests) | exact fractions / floats "that the engine gave on 3.29.3.3" plus a sampler and brute force on a subset | no: **regression pins** | `test_actions_essence_real.py:6,36-39` (four 60-digit Fractions "a regression pin"); `test_actions_fossil_real.py:7,34-37` (R08/R09 floats); `test_abstraction_b1_real.py` `rolled()` gives every mod tier 1 |
| L5 | Goldens (26 files) | the output of the code on the day `UPDATE_GOLDEN=1` (or a script on main) wrote them | no | see section 3 |
| L6 | Benchmark / route end to end (`test_cli_routes_real.py`, `test_cli_r08_r09_real.py`, `test_cli_r13_real.py`, `test_cli_r04_r14_real.py`, `test_vendor_benchmark_real.py`, `cli/_benchmark.py`) | "solver mean <= the guide's given route mean", "policy reaches the goal", `--verify` agrees, goldens | the given route is written by an agent; its mean is evaluated by the same `risk.evaluate`, the same goal check, the same tier reading | `test_cli_routes_real.py:123-131` (R05: 12.2 c vs 135 c passes); `:67-80` `leaf_mods` copies `cli/_offers.py:242` `counting` |
| L7 | `--verify` / simulator (251 + `test_cli_verify*`) | the policy run on concrete items, mean +- 5 sigma vs the computed mean | independent of the kernel and the solver (ADR-0019 layer 2); shares the actions' `sample()` and `Target.is_met_by` | `cli/_verify.py:3-6` says so itself; `:128` passes `target.is_met_by`; power: see TESTS-9 |
| L8 | Solver and risk math (15,732 + 2,421) | brute force over all policies, HiGHS, exact Fractions; `risk_oracle_evaluate.py:1` is "`evaluate` as it was before #82" (old code as oracle) | independent, but of abstract graphs | none for game meaning; 823 of the 861 CI skips happen inside these random tests ("no state has a finite value" 444, "first action of every state is not proper" 379) |
| L9 | Claims registry (`test_rules_registry.py`, `test_rule_references.py`, per-family `*_claims.py`, ~340) | claim files for form (fields, URL shape, date, quote <= 400 chars); code refers only to registered ids | form only: nothing checks that a quote supports its statement or that the cited page says it; `sources/` is git-ignored (0 tracked files), so CI cannot | `test_rules_registry.py:168-182`; no claim exists for "a crafted mod counts as tier 1" (grep of `rules/claims`: none) |
| L10 | Layering / path / hygiene (`test_layering.py`, `test_actions_no_concrete_imports.py`, `test_no_absolute_paths`, `test_no_timing`, ~280) | the import graph and file hygiene | n/a (architecture, not meaning) | - |
| L11 | Craft of Exile comparison (`test_proto_coe_comparison.py`, `coe_support.py`; `tools/coe_emulator`; `test_coe_emulator_record.py`) | CoE's own kernel on 4 of the prototype's 12 cases (Chaos Orb x3, one essence); recorded emulator counts for the Harvest reforge on one shield | **yes, the only independent check of B1 mechanics** | skipped in CI (24 skips: "no local Craft of Exile copy"), CoE copy is data version 3.29.0.3 vs our 3.29.3.3; the emulator tool is "not run by CI" (`tools/coe_emulator/README.md:3`) |
| L12 | Published/wiki numbers (catalysts, Memory Strands, Foulborn, recombinator, sockets; R12's 2.88 % / 1.338 %) | tables typed from the wiki/guide with URL | **yes** | covers B5-B7 families and R12 only; none for the B1 core (essence, bench, Alteration/Regal tiers, goal reading) |
| L13 | Prices / trade (885) | recorded listings replayed against the stored price | recordings are real; the check is arithmetic on them | `test_prices_start_items.py:39-48` replays the same body that made the price; never compared with the target's start item (TESTS-7) |
| L14 | Heavy (`test_packed_heavy.py` 10; 9 skipped in CI) | goldens R04/R14/S02 "a function of the main they were taken on" (`:1-18`) | no | own values |

Hand-computed small cases (`test_proto_known_answers_*`, 95 tests; the ADR-0054 hand test for the Lock) are a thin independent layer on
the mechanics side. R12 is the only route with a published number.

## 2. Circular oracles, listed

1. `tests/test_targets_files.py:386-395` crafted Life, tier typed `1`, value 45, passes `target.is_met_by` for a Life T1 (+(100-114)) goal; name says "rolled_or_crafted".
2. `tests/abstraction_oracle.py:148`, `tests/abstraction_metamod_oracle.py:175` re-type the bench tier 1.
3. `.get(mod_id, 1)` as the tier of anything outside the tier table (crafted, essence-only, veiled, influence): `abstraction_adds_oracle.py:36`, `abstraction_b2_support.py:44`, `abstraction_metamod_oracle.py:121`, `abstraction_oracle.py:78,142`, `abstraction_pool.py:49`, `abstraction_removals_support.py:119`, `abstraction_rolls_oracle.py:82`, `abstraction_veiled_support.py:74`, `beasts_support.py:89`, `coarse_support.py:109,185`, `contract_support.py:197,317`, `item_state_support.py:75`, `test_abstraction_b2_real.py:79`, `test_abstraction_beasts.py:51`, `test_abstraction_harvest_b2.py:61`, `test_abstraction_veiled_real.py:76`, `test_actions_harvest_swap.py:140` (20 places; production has 13 of the same: `abstraction/_kernel.py:909,924,1071,1088,1097,1104,1528`, `actions/outcomes.py:77,272`, ...).
4. `tests/test_cli_routes_real.py:123-131`: the guide's route is evaluated by `evaluate_route` (same goal check and tier reading as the plan); `:67-80` `leaf_mods` is a copy of `cli/_offers.py:242`.
5. `tests/test_cli_routes_real.py:205` `NOTE_PARTS` is a whitelist of the strings the page already prints (it includes `at least \d+ of \d+`, the seed fault).
6. `tests/test_cli_routes_real.py:224-243` "owner's rule" test: vacuous (reproduced, TESTS-3).
7. `tests/test_targets_files.py:21-24` (`ROUTES` table) vs the buy specs: both typed by hand, only the name is compared with the target (TESTS-7).
8. `cli/_verify.py:128` the simulator judges the goal with `target.is_met_by`, the same function whose reading is in question.
9. All of L5 (goldens), `plans_118.json`, `b1_unchanged_142.json`, `risk_unchanged_349.json`, `packed_values.json`.
10. `test_actions_fossil_real.py:31-32,84-85` `HIGH_LIFE = ("IncreasedLife", 44)` = "two best tiers" for R09, while `examples/targets/r09-life-boots.yaml` asks tier 1 only: the test pins the chance of a goal that no target has.
11. `targets/floor.py:57` `BENCH_TIER = 1  # actions.bench.CRAFTED_TIER`: one fact in two modules, joined by a comment; no test reads both.

## 3. Golden files: how made, how accepted, what they encode

How made: `UPDATE_GOLDEN=1 pytest` (`route_view_support.py:57-65`, `targets_sockets_support.py:118-125`, `test_vendor_benchmark_real.py:172`,
`test_packed_heavy.py:73`) writes the file from the code's output; or a script run on main before a ticket
(`b1_unchanged_support.py`, `risk_unchanged_support.py`, `plans_118.json` "made by planning the three targets on main at 147fdad").
How accepted: the test goes green and CI is green. There is no README, no review checklist in `tests/golden/`, `docs/`, `CLAUDE.md` or
the checker's brief. The only recorded human look at any page: the owner accepted the **R10** page in the main chat (#96, 2026-10-31).

| Golden | Commits (`git log --follow`) | What it is | Encodes |
|---|---|---|---|
| `r12_fixture.html` | 7 | toy-data page of R12 | claim id line, "any tier" |
| `restart.html`, `essence.html` | 6, 6 | hand-made policies | "any tier" |
| `b1_unchanged_142.json` | 6 | SHA-256 digests of offers and kernels of 6 routes | "unchanged since main of that day"; unreadable by design |
| `branch.html`, `r12_fixture_given_route.html` | 5, 5 | hand-made / toy | "any tier", claim id |
| `real_r10.html`, `real_r11.html`, `real_r05.html`, `remove_crafted_then_chaos.html`, `gap.html` | 4 each | real routes (3) and hand-made | see below |
| `interval_tiny.*` (4 files), `bench_craft.html`, `given_route_differs.html`, `target_*.json`, `v01_minion_helmet.txt` | 3 each | | claim ids (`interval_tiny.*`, `given_route_differs`), V01 text |
| `plans_118.json` (1.9 MB), `v01_minion_helmet.json` (83 KB) | 2 | policy dumps of R05/R10/R11, of V01 | R05 mean 9.61 c pinned |
| `approximate_conflict.html`, `unveil_offer.html`, `risk_unchanged_349.json` | 1 | | claim id |

Readability of a regeneration: every HTML golden is 47 lines, but the page sections are single lines of up to 3,100-15,100 characters
(`real_r05.html` 12,211, `v01_minion_helmet.html` 15,146). A `git diff` of a regeneration shows one replaced line (e.g. 071046d changed
`real_r05.html` by "2 +-"), so a reviewer cannot read what moved. The PR body is the only place a change can be explained; #170
(regenerated R10/R11/R05) gave a table of old/new mean and p90 (R05 29.6 -> 12.2 c, R10 411 -> 128, R11 1,460 -> 1,110) and no remark
that R05 now cost 11x less than the guide's route.

Goldens that encode outputs that break the owner's rules (linted from the files):

- `real_r05.html`: (a) planner mean 12.2 c vs the guide's route 135 c; (b) steps 3 and 4 "Benchcraft: +(35-44) to maximum Life" /
  "+(16-20)% Fire Resistance", crafted, make the item reach "Life T1 +(100-114) / Resistance T2 +(42-45)%" (the seed); (c) the target card prints
  "T1, at least 1 of 4" four times (Life and the three resistances as four mod lines; 8 "at least k of n" lines on the page); (d) 12 "tier too low" and
  20 "in some" lines. First written 9ca2c85 (2026-10-31 16:46, #96), before real-data tests ran in CI (see TESTS-13).
- `v01_minion_helmet.html/.txt/.json`: steps 3-10 are the same step "Regal Orb" eight times (identical goal and accepts; chance per
  use 0.95 / 0.91 / 0.91 / 0.94 %, the item cards identical); three internal claim ids
  (`vendor.gem_qualification_is_uncorrupted_skill_gems: ...`) on the goal card. Committed in ef74f8b under the Done-when line
  "its golden (text, JSON and route page) is committed" (#331); #372's checker: "passes; no finding breaks a 'Done when' line ...
  ran the three golden tests under two hash seeds".
- 10 goldens print internal claim ids as a line of the page: `approximate_conflict.html`, `given_route_differs.html`, `interval_tiny.{html,json,txt}`,
  `r12_fixture.html`, `r12_fixture_given_route.html`, `v01_minion_helmet.{html,json,txt}` (e.g. `harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot`,
  `recombinator.count_table`, `conflict.odds`). Test `test_cli_approximate_inputs.py:139` is named "lists its own actions' claims sorted by claim id": the id is a designed output.
- 9 goldens print "any tier" (the owner: "any of 9 Life tiers is meaningless"): `approximate_conflict`, `branch`, `essence`, `gap`, `given_route_differs`,
  `interval_tiny`, `r12_fixture`, `r12_fixture_given_route`, `restart` (toy targets with unstated tiers; R12's own target also states none).
- `plans_118.json`: R05 `mean_remaining` 9.613376 (+2.6 start = the 12.2 of the page) pinned since 2026-10-31 as the thing a pruning refactor must not move.

Not covered by any golden: real R08, R09, R13, R04, R14 pages (the real-data tests for them check "reaches the goal / no dearer than the
guide / verify agrees" only).

## 4. The checker and the briefs

- `checker.md` (all of it): read the ticket (`gh issue view`), read the diff, give each acceptance line "met / not met / not tested", hunt
  "edge inputs the ticket does not name: empty, huge, wrong type, missing file, two runs at once", run quick tests, report in 40 lines. It does not
  mention the game, the owner, a page, a target, a golden's content or the glossary. `coder.md` / `coder-light.md`: "read the ticket", "a domain word is in
  GLOSSARY.md", "Done = green". `CLAUDE.md` landing rule: CI green on both systems + `checker` passed + "its tests cover the ticket's Done when". The
  specification of "right" is therefore the ticket text and nothing else.
- The owner's reading rules (unstated tier = top tier at item level, rolled, not from the bench; exact tier of an essence/bench/bought mod; one mod
  format; show every in-game step; never the same route twice; instant buyout; crafter-like search) are in: a memory file outside the repo
  (`owner-route-reading.md`), one comment on #96, and prose inside example target YAMLs. Not in `CLAUDE.md`, `.claude/agents/*`, `docs/`, `GLOSSARY.md`, an ADR,
  or a claim. `git grep -il "owner's tier rule|owner's rule|top tier the item level"` outside `.claude/` hits only target YAMLs, one ADR (0057, about a different "owner's rule", the Lock's independence), three research notes, `prices/poe_watch.py` and three test files. ADR-0061 turns the rule into an opt-in key `tiers_top_at_item_level` (set in 11 of 14 example targets; R08, R13 and J01 do not set it), so the default reading stays the old one.
  ADR-0008 still says "How a mod got onto the item (natural, crafted, fractured) does not matter unless a requirement is marked 'not crafted'", the opposite default.
- Tickets created after the rule (2026-10-31 16:25): 150; 38 touch targets / pages / start items / goldens; **only 3 carry any owner reading rule** (#163, #143 by "one mod format",
  and this audit #396). Not carrying it: #331 (V01), #330, #354, #298 (route page and given routes), #221 (report), #245 (end to end), #233 and #244 (report)...
- Checker verdicts: 130 of 153 PR bodies mention the checker; none of its verdicts cites the owner's rules or inspects a page for them (the two PRs whose "checker" segment
  contains "owner rule" are #131, which quotes the owner's decision, and #41, a process PR). Examples of what it does: fuzzing solvers (~17,000 instances), brute-force sweeps of all 141
  single-mod belts, 4.24 M weight comparisons against a port of CoE's code (#80 - the only independent cross-check of mechanics I found, and it was not kept as a test), 6,500 probe pairs for
  state merging (#373).
- "Done when" that can be met while the meaning is broken (examples):

| Ticket | Done when (quoted) | How a fault passes |
|---|---|---|
| #60, #63, #66, #70, #146, #150, #153, #156, #159, #160, #223-225, #292, #299 (18 tickets; ADR-0013 "Pass rule: at equal prices the solver's route costs no more than the guide's") | "the solver's mean is no more than the given route's" | one-sided: a fault that makes plans cheaper (bench crafts as T1: R05 12.2 c vs 135 c) only helps it pass; the guide's route is evaluated with the same reading |
| #331 | "its golden (text, JSON and route page) is committed" | a golden of 8 identical Regal steps and claim ids satisfies it |
| #163 | "the real route goldens ... pass with the new prices; the PR lists old and new mean and p90" | regenerating the goldens is the acceptance; R05 29.6 -> 12.2 c listed, not questioned; the R05 price came from a spec that searches any ring |
| #143 | "golden route pages, one of them with a Conflict mark and one with an unveil offer" | claim ids on the page |
| #96 | "the main chat shows the R10 page to the owner and he accepts it" | R10 only; R05 and R11 pages (same ticket, same goldens) were never shown |
| #352 | "R13 and R08 floors are 84, R05 is not lowered" | no statement of what the page then shows |
| #60 PR #113 | "R05 counts a crafted Life/Resist (the guide ends with a bench craft)" listed under "Caveats (please read)" | disclosed once in a PR, never became a rule check; one day later the owner's tier rule was applied to R05 without touching it |

## 5. Findings

### TESTS-1: Where the test mass is not where the meaning is   [CONFIRMED] [impact: high]
- Where: `tests/` as a whole; `_collect_tests.txt`; CI run 41418171876 summary (31,106 tests).
- What it does: 50.7 % of the tests are solver math, 7.8 % risk math, 0.8 % simulator; `cli` 2.0 %; tests that plan a real route ~0.56 %; Craft of Exile comparisons 0.3 % (24 skipped in CI).
- What it should do: put independent oracles where the owner's meaning is decided: the reading of a target, the start item, the goal state, the page, the mechanics of the routes' own actions against the game.
- Evidence: counts above. ADR-0019 promises "each link of the chain from rules to policy is checked against something written independently of it" in five layers (kernel vs enumeration; simulator vs kernel; solver vs LP; benchmark policy run on concrete items; published numbers). The joints that are in none of the five: game -> claim, guide/owner wording -> target file, target -> goal state, buy spec -> start item, plan -> page. Layer 5 "published numbers are acceptance tests" exists for R12's two odds only (`cli/_benchmark.py:109-119`, comment at `:107`: "The guides of these six publish no odds, so there is nothing to recompute"); the reference-routes file records `stated_cost` null for R05/R10/R11.
- Impact: a green suite says the machinery computes the *model's* numbers exactly; it cannot say the model is the game or the owner's reading.
- Origin: ADR-0019 (grill round 3, Q19); ADR-0020; it is how the suite grew (each ticket's oracle sits next to the code it wrote).
- Pattern: verification effort follows where an exact oracle is easy to build, not where the risk is.

### TESTS-2: The tier placeholder is pinned as the expected value in the tests, in 20 places, and tests disagree with each other about it   [CONFIRMED] [impact: high]
- Where: `tests/test_targets_files.py:386-395`; `tests/abstraction_oracle.py:148`; `tests/abstraction_metamod_oracle.py:175`; the 20 `.get(mod_id, 1)` places in section 2 item 3; `tests/test_items_tiers.py:78-82` vs `src/crafting_system/actions/bench.py:57`, `targets/floor.py:57`; `tests/test_targets_floor.py:98-106`.
- What it does: `test_the_r05_ring_is_met_by_the_essence_strength_and_a_top_tier_life_or_resistance_rolled_or_crafted` builds `ExplicitMod("EinharMasterIncreasedLife3", 1, (45,), crafted=True)` (a +(41-55) craft, tier typed by hand as 1) and asserts `target.is_met_by(...)` for a goal "Life tier 1" (+(100-114) on a ring) with the comment "the guide ends with a bench craft". `test_a_mod_that_cannot_spawn_on_the_base_has_no_tier` asserts `mod_tier(...)` raises `TierError` for a mod that cannot spawn. Both pass (run: 5 passed / 2 passed). `Item` stores tier "as given" (`items/model.py:24`), so no test or validation relates a stored tier to a value range. Reproduced: `tier_table(real, ring)` lacks `EinharMasterIncreasedLife3`; `mod_tier` raises "it cannot spawn there"; the same mod is accepted as Life T1.
- What it should do: the owner's rule says an unstated tier is the top tier, rolled, not from the bench; a crafted mod is never a tier of the spawn ladder. Tests should assert the opposite of line 395 (or the rule that decides it), and a reconciliation test should fail when two modules hold copies of one constant (`BENCH_TIER` / `CRAFTED_TIER`) or when a stored tier is inconsistent with the mod's value range.
- Evidence: lines above; `tests/golden/real_r05.html` steps 3-4; `test_targets_floor.py:98` is named "the bench gives a mod at its own level unless the target wants it rolled": the placeholder became a feature (ADR-0061, #352) with its own tests, none of which asks whether a bench mod has a tier.
- Impact: every test that could have caught R05's "finish with bench crafts" was written with the same placeholder; a Life craft of 45 is "T1" in the test oracle, the kernel, the floor, the goal check and the golden.
- Origin: PR #74 (#56, 2026-10-31) "Open points for the main chat ... `sample` gives crafted mods tier 1 (crafted mods have no tier in the data)": flagged in PR prose, not in a ticket or a test. #60 / PR #113 then read R05's last group with "a crafted Life/Resist counts" (`examples/targets/r05-strength-ring.yaml` comment: "a bench craft counts as tier 1 of what it crafts whatever its range"). Brief of #56: "Done when ... tests for each refusal ... costs ... pins" (no tier question).
- Pattern: a type placeholder copied into the test support, so the oracle shares the fault.

### TESTS-3: The two tests that were meant to guard the owner's rules cannot fail on the owner's headline fault   [CONFIRMED] [impact: high]
- Where: `tests/test_cli_routes_real.py:224-243` (`test_the_tiers_the_target_asks_for_can_appear_at_its_item_level`) and `:205-221` (`NOTE_PARTS`, `test_every_mod_line_of_the_pages_has_the_one_format_...`).
- What it does: the first selects the mods of a leaf with `tiers.get(m, 1) <= leaf.min_tier` and asserts that *some* has `required_level <= item_level`. A looser `min_tier` only lengthens the list, so it cannot fail. Reproduced on the real R05 target: for AllAttributes, IncreasedLife, FireResistance, ColdResistance, LightningResistance the check is True at `min_tier` = 1, 2, 5, 9 and None. The Life leaf's `mod_ids` holds 323 mods outside the ring's tier table (uniques, implicits, crafts) that `.get(m, 1)` makes "tier 1". The second accepts any note matching the whitelist `T\d+( or better)?|any tier|crafted|essence only|tier too low|in some|at least \d+ of \d+` - it includes the exact strings of the seed faults ("any tier", "at least k of n").
- What it should do: owner rule 1 as an equality: for every leaf without an exact `mod:`, `min_tier` must equal the best tier whose `required_level <= item_level` on that base (and for a family leaf, crafted mods must not count unless the leaf is explicit); the format test should come from the rule ("one line per mod, a k-of-n group printed once") not from the strings already printed.
- Evidence: the snippet output above; the test file lines.
- Impact: gives a false sense that the owner's tier rule is under test for R05/R10/R11; any tier loosening would pass.
- Origin: added in #96 (PR #131) to cover "owner's decision after the first look at the R10 page".
- Pattern: a lint built from the current output / a one-sided check dressed as a rule.

### TESTS-4: "Solver mean <= the guide's route" is a one-sided pass rule and cannot flag an implausibly cheap plan   [CONFIRMED] [impact: high]
- Where: ADR-0013 ("Pass rule: at equal prices the solver's route costs no more than the guide's ... the check on the solver's route is recorded, never a failing test" - in `benchmark`); 18 ticket bodies (#1, #57, #60, #63, #66, #70, #97, #146, #150, #153, #156, #159, #160, #223, #224, #225, #292, #299); tests `test_cli_routes_real.py:123-131`, `test_cli_r08_r09_real.py:106`, `test_cli_r13_real.py:115`.
- What it does: passes whenever the plan is cheaper; the given route is evaluated by the same evaluator. R05: planner 12.2 c, given route 135 c (golden `real_r05.html`); R10/R11 "Same as the given route" (identical policy), so only R05 diverged - and R05 is the route the owner opened and found broken.
- What it should do: a divergence from the guide is a finding to explain in plain words (which step differs and why a human crafter would not do it), and a plan >k times cheaper than a published human route is an alarm for review (not a search cut-off; a report line). Two-sided.
- Evidence: PR #113 table R05 planner 27.94 c vs guide 39.49 c (ratio 0.71); PR #131 (after the owner's tier rule) 29.6 c vs 152 c (0.19); PR #170 / golden 12.2 c vs 135 c (0.09) - the ratio fell 8x over three PRs with the rule satisfied each time. Nothing in the PRs comments on it.
- Impact: every end-to-end ticket (R08, R09, R13, R04, R14, S02-style routes) is accepted by this rule; a systematic "too cheap" bias passes by construction.
- Origin: ADR-0013 / grill round 1 Q7, 3 Q23.
- Pattern: acceptance that only the fault can help to pass.

### TESTS-5: Goldens are accepted by their own regeneration and encode the faults the owner found (and more)   [CONFIRMED] [impact: high]
- Where: `tests/golden/*` (section 3); `route_view_support.py:57-65`; `targets_sockets_support.py:118-125`; `test_vendor_benchmark_real.py:172`.
- What it does: a golden equals the output of the code; there is no review procedure; HTML goldens are single-line sections up to 15 KB so a diff is unreadable; digest goldens (`b1_unchanged_142.json`, `risk_unchanged_349.json`) cannot be read by anyone; `plans_118.json` is 1.9 MB.
- What it should do: a golden is accepted only when someone has read the plain-text rendering against the owner's rules; keep few goldens, one fact per line, and a lint that fails on the owner's list (claim ids, k-of-n as n lines, duplicated steps, crafted-as-tier).
- Evidence: section 3 (R05, V01, 10 goldens with claim ids, 9 with "any tier"; 43 commits, 22 "regenerate" messages; only R10 was ever shown to the owner).
- Impact: "the golden is committed" (#331) and "goldens pass with the new prices" (#163) were satisfied by pages that break at least four of the owner's rules.
- Origin: #78 (PR #114) introduced `assert_golden`; real pages in #96 (9ca2c85, before the owner's second look); V01 in #331.
- Pattern: a snapshot of the output treated as a specification.

### TESTS-6: The checker and the briefs carry the ticket text only; the owner's rules have no home in the repo   [CONFIRMED] [impact: high]
- Where: `.claude/agents/checker.md`, `coder.md`, `coder-light.md`; `CLAUDE.md` (landing paragraph); `docs/agents/*`; ticket bodies.
- What it does: see section 4: the gate is CI + a ticket-only review + "tests cover Done when"; owner rules live in a memory file, one issue comment and YAML comments; 2 of 37 post-rule tickets that touch targets/pages carry a rule; no checker verdict cites one; there is no ticket template in the repo (`git grep "Done when"` outside `docs/adr`, `docs/research` finds only `CLAUDE.md`).
- What it should do: one tracked document of the owner's reading rules and of the game facts that decide readings, linked from `checker.md`, `coder*.md`, the ticket template and `CLAUDE.md`; the checker reviews every ticket that touches a target, start item, buy spec, page or golden against it and against what a player does in the game, and says so in its verdict.
- Evidence: section 4; `checker.md` full text (14 lines); #372 verdict.
- Impact: the same fault classes repeat (the owner's R10 complaints of 2026-10-31 returned on 2026-11-02, memory `roots-not-patches.md`).
- Origin: `.claude/agents/` (#30); owner rules recorded 2026-10-31 in #96 and memory only.
- Pattern: the specification of "right" lives in one chat's memory.

### TESTS-7: Two hand-written descriptions of one start item are never reconciled (and the test that looks like a reconciliation is a replay)   [CONFIRMED] [impact: high]
- Where: `tests/test_targets_files.py:21-24,220-230`; `tests/test_prices_start_items.py:39-48`; `examples/buy/r05-start-ring.yaml`, `r12-start-amulet.yaml`, `r10-start-boots.yaml`, `r11-start-helmet.yaml` vs `examples/targets/*`.
- What it does: `test_a_route_buy_spec_loads_and_is_the_start_price_of_its_target` compares the spec's name with the target's `start_price` and its mod list with a table typed in the test (`ROUTES = {"r05": (..., "+# to all Attributes", 13)}`); `test_prices_start_items` replays the recorded search that produced the price (body equals body, mean of the 5 cheapest listings). Nothing compares the spec with `target.start_item` (base, item level, tier/roll of the fractured mod, influence, corrupted).
- What it should do: derive the search from the target's start item (one source), or fail when a spec describes a different item.
- Evidence: R05 target: Amethyst Ring (chaos-resistance implicit), item level 75, `AllAttributes4` [14] fractured; spec: `category: accessory.ring`, no `base_type`, `item_level_min: 75`, fractured >= 13 -> 602 listings of any ring, 2.6 c (PR #170). R12 spec: `category: accessory.amulet`, `item_level_min: 75`, fractured Lightning Resistance with no minimum vs target Paua Amulet item level 84, `LightningResist2` tier 3 [14]. R10/R11 name `base_type`, so the mismatch is partial (the spec cannot say the exact fractured tier, only a minimum).
- Impact: R05's start price (and so its whole mean, 2.6 c of 12.2 c) and R12's are for a different set of items than the plan assumes.
- Origin: #60 (spec files), #163 (re-priced "under the tier rule" from the same specs, R11 got the tier minimum, R05 did not get a base).
- Pattern: one fact (the start item) written by hand in two places with nothing reconciling them.

### TESTS-8: No oracle for over-splitting: "detail no later decision sees" is never checked   [CONFIRMED] [impact: medium]
- Where: `tests/contract_support.py:514-552` (`check_declarations_agree`), `check_item_state_declarations`, `check_block_invariance`; no file tests minimality.
- What it does: the suite checks that what an action declares it reads is sufficient (the result is the same without the other parts of the item). Nothing checks that tracked detail is necessary: that two states with the same future (same legal actions, same goal contribution, same outcome classes) are one state. `test_cli_route_flow.py:1,330` makes the *steps* of a page the coarsest grouping by action and exact chances, so any exact difference in chance, however tiny, makes a new step.
- What it should do: a refinement/bisimulation check on small exact graphs and on the real routes: count the states a policy can reach, merge states with equal futures, and report the ratio; the V01 page (eight "Regal Orb" steps, chances 0.95/0.91/0.91/0.94 %) is the example.
- Evidence: `tests/golden/v01_minion_helmet.html` steps 3-10; grep for "bisimul|minimal|coarsest" in `tests/` finds only the route-flow grouping.
- Impact: pages show internals instead of what a player does; state counts (and so runtime and memory of R04/R14) are inflated by an unknown factor.
- Origin: ADR-0009 (design D) argued exactness of the merges, never minimality; owner rule "crafter-like search" arrived later.
- Pattern: a one-directional invariant (merge is exact) taken for the two-directional one (the state is minimal).

### TESTS-9: `--verify` is an independent check of the solver, not of the model, and for R11 it can only reject a 29 % error   [CONFIRMED] [impact: medium]
- Where: `cli/_verify.py:3-10,28,82-92,128`; `tests/test_cli_routes_real.py:35` (`RUNS = {"R10": 3_000, "R11": 300, "R05": 3_000}`); V01 not verified on real data (PR #372 "Not in this ticket"); R04/R14 "heavy".
- What it does: simulates with each action's own `sample()` and judges the goal with `target.is_met_by`; agreement is within `SIGMAS = 5` standard errors; the module's own `detectable_error` is `SIGMAS * SE / mean`, "a cost is about as spread as its mean" so about 5/sqrt(runs): 10,000 runs 5 %, 3,000 runs 9 %, **300 runs 29 %**.
- What it should do: say in the output what it does not check (the model), and run enough to detect the error the owner cares about; keep it as the check of kernel + solver only.
- Evidence: the arithmetic above from the code's own docstring; R11 at 300 runs because "R11 takes about a thousand uses per finish".
- Impact: "`--verify` agrees" is in the Done-when of nine tickets (#1, #26, #60, #63, #66, #70, #71, #243, #245) and reads as correctness of the answer; it is correctness of the arithmetic.
- Origin: ADR-0019 layer 2/4.
- Pattern: an independent check of one link presented as a check of the chain.

### TESTS-10: The one independent oracle of B1 mechanics (Craft of Exile) does not run in CI, is stale, and a +2 % essence gap is accepted under a fixed 5 % threshold   [CONFIRMED] [impact: medium]
- Where: `tests/test_proto_coe_comparison.py:86-88,164`, `tests/coe_support.py:120-140`, `tests/test_coe_emulator_record.py`, `tools/coe_emulator/`, `.claude/skills/coe-emulator-check`.
- What it does: 24 tests skip in CI ("no local Craft of Exile copy") because CoE is third-party data kept out of the repo; the copy is data version 3.29.0.3 (`coe_support.py`, README) vs the pin 3.29.3.3; 4 of the prototype's 12 cases are carried (Chaos Orb helmet/ring/amulet, one essence); the other 8 (Exalted C03; Alchemy/Alteration/Regal C04, C05, C07, C08, C10, C11, C12) "wait for their tickets" (#64, #67, both closed since 2026-11-01) and ticket #97, whose Done-when is to carry them, is still OPEN; `grep` finds no test for them. C02 (Deafening Essence of Envy on a rare helmet) differs by **+2.09 %** and C06 by -1.27 %: "not attributed to a cause ... within the 5% threshold and pinned, nothing more" (`THRESHOLD_PERCENT = 5.0`, `DRIFT_PERCENT = 0.1`). The emulator tool is "not run by CI"; recorded emulator counts exist for one Harvest case (#198) and 5 check files (`tools/coe_emulator/checks/`).
- What it should do: record the emulator's frequencies for every action family the planner offers on the routes (counts are our measurement and may be committed, as `test_coe_emulator_record.py` does), so the comparison runs in CI; explain or remove each unexplained gap; no fixed percentage threshold.
- Evidence: CI summary of run 41418171876: "24 x no local Craft of Exile copy"; docstring of `test_proto_coe_comparison.py` last two paragraphs.
- Impact: the essence (used by R05/R10/R11) has an unexplained difference from the reference tool, pinned as accepted.
- Origin: #73 (carry over the prototype's checks), #97.
- Pattern: a tolerance that hides a residual.

### TESTS-11: Regression pins are filed under verification, and some pin a goal nobody plans   [CONFIRMED] [impact: medium]
- Where: `tests/test_actions_essence_real.py:6,36-39`; `tests/test_actions_fossil_real.py:7,31-37`; `tests/test_prune_bound.py:19-21`; `tests/b1_unchanged_support.py`; `tests/test_packed_heavy.py:1-18`.
- What it does: exact values "that the engine gave" (R10_86, R11_86, R05_86/75; R08/R09 chances) with the docstring "a regression pin: the independent check is the hand oracle ... on the fixture"; R09's `HIGH_LIFE` is the two best Life tiers (levels 44 or 54) though the R09 target now asks tier 1 only; digests of kernels/offers; heavy values "a function of the main they were taken on".
- What it should do: name them as pins in the test names (some do), keep the independent check beside them for the *real* goal, and rewrite or delete a pin whose goal changed.
- Evidence: files above; `examples/targets/r09-life-boots.yaml` ("high Life: the top tier ... tier 1, +(115-129)").
- Impact: moderate; these pins move with every correct change and so train people to regenerate (see TESTS-5).
- Origin: #55, #61, #118, #142.
- Pattern: "what the engine gave" as expected value.

### TESTS-12: Hand oracles and claim tests share one spec; claims are checked for form only   [CONFIRMED] [impact: medium]
- Where: section 1 L2/L9; `tests/test_rules_registry.py:168-182`; `tests/test_rule_references.py`; `.gitignore` (`sources/`).
- What it does: every hand oracle replays "the claims of the registry, written again as plain code"; the registry tests check fields, URL shape, date type and quote length; no test checks that the quote says what the statement says, that the source is not stale (`date_checked` age), or that a game-deciding constant in `src/` has a claim (no claim for "a crafted mod has tier 1"; `CRAFTED_TIER`, `BENCH_TIER` carry none).
- What it should do: keep the quote text in the repo (a recorded excerpt hash), fail on a claim whose source is older than the current patch, and list game-deciding module constants without a claim.
- Evidence: `git ls-files sources | wc -l` = 0; `grep -rn "CRAFTED_TIER\|BENCH_TIER" src/crafting_system/rules` = none.
- Impact: a misread claim is wrong in code, in the oracle, and in the test of the claim.
- Origin: ADR-0004 (binary admission and a registry), hand oracles from #23 on.
- Pattern: one spec, two implementations, no check of the spec.

### TESTS-13: Real-route coverage is thin, was local-only at birth, and the pages were shown to the owner once   [CONFIRMED] [impact: medium]
- Where: `.github/workflows/ci.yml` history (9c30d5f 2026-10-31 22:52 "Run the full suite with the real game data" #165); goldens `real_r05/10/11` first written 9ca2c85 2026-10-31 16:46; PR #131 text "(real cache; they skip in CI, which has none)"; #96's last comment.
- What it does: for ~26 hours (CI skeleton 2026-10-30 20:46 to the real-data CI 2026-10-31 22:52) every `*_real.py` test and the three real goldens ran only on the owner's PC ("an overloaded PC", PR #170, "not run here"); R08, R09, R13, R04, R14, V01-with-verify have no page golden and no look; the first page the owner saw was R10, and R05's golden was written the same day without a review.
- What it should do: every real route has its page read against the owner's rules before it becomes a golden; R05 and R11 went through #96 without the owner and without a rule lint.
- Evidence: git dates above; `grep write_route_page tests/` lists test files for R05/R10/R11/V01/fixtures only.
- Impact: the R05 golden is the oldest page in the suite and never reviewed.
- Origin: #96 Done-when "shows the R10 page to the owner".
- Pattern: one reviewed instance stands for the family.

### TESTS-14: Defects found by the build are parked in PR prose, not in tickets or tests   [CONFIRMED] [impact: medium]
- Where: 33 of 153 PR bodies have "Open points / Known limits / Known and left" sections; example PR #74 ("`sample` gives crafted mods tier 1"), PR #136 ("Follow-up outside this scope ... the kernel gives every influence mod tier 1 ... Notes in the shared folder"), PR #113 ("Caveats (please read): R05 counts a crafted Life/Resist").
- What it does: `gh issue list` search finds no issue about the crafted-mod tier before #396 (a grep of 243 issue bodies for "crafted ... tier" returns #19, #177, #1, #396 - none is that question). The #136 follow-up was in fact absorbed by #69; the #74 one never was.
- What it should do: every open point becomes a ticket line or a test with `xfail` and a reason, listed where the main chat looks.
- Impact: this is the path by which the seed fault stayed for two days.
- Origin: PR template habit; `CLAUDE.md` says the state of the work lives in the issues, but PR prose is not in the issues.
- Pattern: findings stored where nobody reads them.

### TESTS-15: The owner's rules are not written back into the ADRs/glossary, and the tests follow the ADR   [CONFIRMED] [impact: medium]
- Where: `docs/adr/0008-targets-and-start-items.md` line 3; `GLOSSARY.md`; `src/crafting_system/targets/model.py:7,57`.
- What it does: ADR-0008 and the target model implement "how a mod got onto the item does not matter unless a requirement is marked not crafted"; the owner's rule of 2026-10-31 / 2026-11-02 is the opposite for an unstated tier. The target YAMLs carry the conflict as "a choice that can be changed here".
- What it should do: amend ADR-0008 (or add one) with the owner's reading rules, and let tests cite it.
- Evidence: ADR-0008 line 3 vs `examples/targets/r05-strength-ring.yaml` comment block; no ADR states the rule as a default: ADR-0061 point 1 only says "a level is not lowered where the author wrote it to mean 'the top tier at that level'" and adds the per-target opt-in key `tiers_top_at_item_level` (11 of 14 example targets set it; `r08`, `r13`, `j01` do not).
- Impact: any new coder/checker reading the ADRs learns the old default.
- Origin: ADR-0008 (round 2), owner rule 2026-10-31.
- Pattern: a later decision recorded in a chat, not in the record the agents read.

### TESTS-16: CI gate is weaker than it looks   [CONFIRMED] [impact: low]
- Where: `.github/workflows/ci.yml:66` (`--min-tests 1000`); `.github/scripts/ci_summary.py:29,119-121`.
- What it does: the test-count floor is 1,000 against 31,106; only skips whose reason contains "not in the cache" fail the summary; 861 skips pass (823 inside random solver tests, 24 CoE, 9 heavy R04/R14/S02 goldens that never run in CI); PR CI is Ubuntu only (real Windows runs happen in integration runs).
- What it should do: floor near the real count, a list of expected skips, and the CoE/heavy skips visible as "not covered" on the PR.
- Impact: deleting most of the suite would pass the check; silent skip of the only independent comparison.
- Origin: #165.
- Pattern: a gate that checks the shape of the run, not its power.

### TESTS-17: The oracle is written by the implementer, reviewed by the same model family   [SUSPECTED] [impact: medium]
- Where: `coder.md`, `coder-light.md` ("call `mattpocock-skills:tdd`, a test that goes red, then the code"), `checker.md` (Sonnet 5.5 as the coder).
- What it does: the test that defines "right" for a piece is written by the same agent that writes the code, from the same ticket; the reviewer is the same model reading the same ticket. Where the ticket is silent (tier of a crafted mod; the buy spec), both fill the gap the same way (`CRAFTED_TIER = 1`, `.get(m, 1)`, "crafted counts").
- What it should do: for any piece with a reading to make, the oracle comes from outside the author: a published number, the owner's rule, or a second reading by a different agent given only the game source.
- Evidence: 20 copies of `.get(mod_id, 1)` in test support, written by different tickets' coders, each copied from the production line.
- Impact: correlated blind spots; cannot be proven from the repo alone.
- Pattern: author = oracle.

### TESTS-18: No lint of the example targets against the owner's tier rule   [SUSPECTED] [impact: low]
- Where: `examples/targets/*`; no test.
- What it does: unstated tiers remain in `r12-lightning-amulet.yaml` (`stat: "+1 to Level of all Lightning Skill Gems"`, `family: LightningResistance`), `r13-life-resist-belt.yaml` (`AllDamage`, `IncreasedWeaponElementalDamagePercent`, crafted allowed), `v01-minion-helmet.yaml` (the +1 Minion mod), `j01-cobalt-life-attack-speed.yaml` (3 families), and `r10-fractured-boots-70-life.yaml` (a `not_crafted` stat without a tier). Some are one-tier mods (+1 gems), others are not (Lightning Resistance has 8 tiers; R12 reads the guide as the fractured one, so it may be intended).
- What it should do: a parse-time lint "every leaf without an exact `mod:` states a tier or is single-tier at the item level".
- Evidence: scan with `yaml.safe_load` of the 14 target files (output in the session): leaves with neither `min_tier` nor `mod` are those above.
- Impact: unknown; each needs a reading.
- Pattern: no lint at the file boundary.

## 6. Proposed independent oracles (what is missing)

Each is a gap I confirmed by absence in `tests/`; the "should" is the proposal.

### TESTS-19: An owner-rules check of every route's target and goal states   [CONFIRMED gap] [impact: high]
- Where: none exists. Proposal: a module written from the owner's rules only (not from `Target.is_met_by` or `Goal`): for each example target, resolve every leaf on the real data to the exact set of mods it admits, with the rules (unstated tier = top tier whose required level <= item level; essence/bench/bought = the exact mod; a crafted mod satisfies a leaf only by name); then play the planner's final states: every goal state of the policy (and every final item the simulator reaches) must satisfy this independent reading. A crafted +(35-44) Life must fail "Life T1".
- Evidence it would have fired: R05 golden step 3 (crafted Life) and the test line `test_targets_files.py:395`.

### TESTS-20: A page lint from the owner's list, run on every real route and every golden   [CONFIRMED gap] [impact: high]
- Proposal: on the page model (and the text report) assert: no dotted claim id or snake_case token or `Metadata/` path on the page; a k-of-n group printed once ("at least 1 of: Life T1, Fire T2, Cold T2, Lightning T2"); no two steps with the same action, goal and accepts (merge); every in-game step present (essence on a rare says "no Scouring"); the final card satisfies the target under TESTS-19; a bench-crafted mod is never labelled with a spawn tier; the guide's route is not drawn twice. Failing lines of V01, R05 and the 10 claim-id goldens are the regression cases.

### TESTS-21: A reconciliation test for every "same fact in two places"   [CONFIRMED gap] [impact: high]
- Proposal: generate the trade search from `target.start_item` (delete the hand-written buy specs), or assert spec == item for base, item level, influence, fractured mod and tier; assert `targets.floor.BENCH_TIER == actions.bench.CRAFTED_TIER` until the placeholder is removed; assert a stored `ExplicitMod.tier` equals the derived tier for every non-special mod (a property test over all items reached in every policy walk); assert the pinned test goal (R09 `HIGH_LIFE`) equals the target's.

### TESTS-22: A plausibility report against the guide, two-sided   [CONFIRMED gap] [impact: medium]
- Proposal: `benchmark` lists, per route, where the planner's policy differs from the given route, in plain words, with the cost ratio; a ratio below a configured review line is a "needs a human" row in the PR (a review prompt, not a search cut). Also an independent "naive crafter" interpreter of the guide's text rules on concrete items (written from the guide, using only repoe data and the owner's rules), to cost the given route without `risk.evaluate`.

### TESTS-23: Recorded Craft of Exile (emulator) frequencies for the B1 core, runnable in CI   [CONFIRMED gap] [impact: medium]
- Proposal: extend `test_coe_emulator_record.py`'s method (counts recorded from the emulator, committed as our measurement) to Chaos Orb, the essences of R05/R10/R11, Alteration/Augmentation/Regal at a stated tier, bench crafts, fossils; remove the 5 % threshold; explain C02's +2.09 %. Add a tier-aware check: the emulator's probability that a crafted/essence mod satisfies "tier T1" must be what our goal says.

### TESTS-24: An owner-visible review step for goldens   [CONFIRMED gap] [impact: medium]
- Proposal: write goldens as plain text one fact per line; `UPDATE_GOLDEN` also writes a plain-words diff to the PR body; the first page of each route is shown to the owner in the chat (not only R10); the checker is told to read the golden against TESTS-20 and say so. Delete digest goldens that no one can read once a readable invariant covers the same ground.

### TESTS-25: A minimality / bisimulation report (see TESTS-8)   [CONFIRMED gap] [impact: medium]
- Proposal: for each route, group the reachable states by (legal actions, goal contribution, future), print the ratio exact-states / minimal-states and the groups with equal futures but different chances; V01's eight Regal steps are the first case.

### TESTS-26: Published-number and community-measurement tests for the B1 core   [CONFIRMED gap] [impact: medium]
- Proposal: like the wiki tables for catalysts and strands: the wiki's essence rule (guaranteed mod, number of mods), Alteration/Regal tier odds as listed on the wiki or poedb, trusted Reddit measurements of Alteration spam on a T1 mod; each with URL, quote, date, as the claims require. Only R12's two odds and the B5-B7 families have this today.

## 7. Patterns seen in this area

1. **A snapshot of the output is the specification.** Goldens, regression pins, digests, "what the engine gave": TESTS-5, TESTS-11, section 3; accepted by their own regeneration; unreadable by construction.
2. **The oracle shares the code's reading.** A second implementation of the same claims (TESTS-12), the same placeholder (TESTS-2: 20 copies of `.get(mod_id, 1)`), the same goal check in `--verify` (TESTS-9), the same evaluator for the guide (TESTS-4).
3. **Type placeholders copied into the test support** so that the fault is also the expectation (TESTS-2).
4. **One-sided acceptance and one-sided lints** that only the fault can pass: "solver <= guide" (TESTS-4), the tier "can appear" check and the format whitelist (TESTS-3), "reads are sufficient" without "necessary" (TESTS-8).
5. **The specification of "right" lives in one chat's memory**: owner rules in memory/ticket comment/YAML comments; checker and coders never see them; ADR-0008 still says the opposite (TESTS-6, TESTS-15, section 4).
6. **Same fact written by hand in two places with no reconciling test**: buy spec vs start item, `BENCH_TIER` vs `CRAFTED_TIER`, `HIGH_LIFE` vs the R09 target (TESTS-7, TESTS-11, section 2).
7. **Verification effort goes where an exact oracle is easy**: 59 % of the tests are abstract-graph math; 0.56 % plan a real route (TESTS-1).
8. **One reviewed instance stands for a family**: the owner saw R10 only; R05, R11, V01 and every later page never got a review (TESTS-13).
9. **Findings are parked in PR prose** and never become tickets or tests (TESTS-14).
10. **A gate checks the shape of a run, not its power**: test-count floor 1,000 of 31,106, CoE and heavy skips pass, `--verify` at 300 runs (TESTS-9, TESTS-16).
