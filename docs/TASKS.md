# Tasks (`[x]` done + commit, `[~]` in progress, `[ ]` not started, `[!]` blocked + question id; never delete, strike with a reason)

## GOAL 2 — trusted numbers and optimised policies

- [x] Owner-unblocked Harvest: adapter `527efa7`; protected-half helmet policy `55c8191` (39 focused tests), exact mean2703.61 with full-prefix recovery cost.
- [x] Complete S14 metamod matrix as data and tests (`614c9c3`): 33 actions x 4 columns = 132 cells, 33 notes, 10 passing tests.
- [x] Record answered source gates: rare counts, multimod and essence rarity boundary (`ffcf869`); fifteen Harvest tags/prices in loadout (`55c8191`).
- [x] Produce 12 offline CoE validation cases over helmet/body/ring/amulet/boots (`3712602`; docs/validation/coe_cases.md):25 correspondences, max difference2.08735%, none above5%. Broader Q14 proof stays separate.
- [x] Add amulet/boots literal projection for those cases (`deae811`):561 records/548 names,15 focused tests.
- [x] Correct the 15-row owner question sheet without re-asking answered questions (`ffcf869`; S63-S79 and owner answers).
- [x] Conditional attempt kernel and paid-restart costs (`0f012a1`):10 lead tests; means21.5/22; independent exact p90 fixtures44/45/97.
- [x] Expose and optimise template parameters (`560f8c2`):56 lead tests including real CLI; protected8357.19→1948.60, Harvest2703.61→1986.20; grids24/8/96/4. Final default plans and timings recorded in docs/research/goal2-results.md; full394-test suite0.915minute after593d5be.
- [x] Bounded solver experiment (`b89f775`):11 lead tests, hand optima8/4/4.75; real helmet reaches100000 states in0.23022minute before first Alchemy row completes. Negative result accepted; further graph solving parked, docs/research/solver-experiment.md.
- [x] Verify bow distribution/threshold/frontier path after fossils (`2c069fc`):14 reachable pairs, two Scorched frontier points; mean162.37513/9739.87719, p90372.5/22426.5. Final fracture integration preserves explicit bow exclusion (`000e8d9`, lead CLI tests).
- [x] Bounded research for owner rows2,6,7,9,10,12,13,14 recorded (`ffcf869`): first/all Harvest remains provisional; resonators/ordinary fracture/catalyst gains resolved; CoE additive fossils selected.
- [x] Locate matching recombinator Reddit/diagram chain S66-S69 and document classic and selected-mod modes separately (`ffcf869`); current exact odds remain open.
- [x] Implement each newly unblocked ordinary family with sourced tests and a usable policy: Harvest55c8191, catalyst14be5e9, fossil2c069fc, fracture000e8d9. Comparisons: docs/research/goal2-results.md. Other rows resolve eligibility or research scope only; their named numeric/model gates remain below.
- [x] Ordinary fossil adapter (`0de86dd`):18 supported fossils, additive default/multiplicative sensitivity,43 focused tests;93 real entries/84 classes, seeded common marginal agrees.
- [x] Ordinary fossil policy (`2c069fc`):all15 subsets, full recipe prices, terminal mixture and cache/endpoint/work-limit guards;48 lead affected tests plus26 final changed tests. Full default helmet0.44minute/bow0.85minute, all96 Magic candidates complete.
- [x] Concrete fracture identity and retained-mod basic actions (`d348533`):74 lead tests; finish p=.06101200110346221/30 classes,627 of10000 seeded successes, identity loss0 and Divine Life9 value132 retained.
- [x] Fracture-Life then Envy policy (`000e8d9`):47 lead affected tests plus17 final input tests, exact mean4227.73669,p908744[8500,9353.5], all replacement/preparation costs paid; two-candidate audit, exact target guards, distributions and explicit bow exclusion. Full default helmet0.51minute,12 routes, Envy still best.
- [x] Catalyst quality distribution and supplied-jewellery finishing policy (`14be5e9`):48 lead core tests and19 final CLI checks; mean14.42372357 applications,p90 16; independent binomial CDF/MC agree. Ordinary jewellery only, no damage-value inference.
- [x] Final GOAL 2 acceptance (`593d5be`, final docs commit follows):394 tests54.90s/0.915minute; full default helmet0.51minute/bow0.85minute; ten-line STATE, results report and explicit-path commits. All currently unblocked ordinary families implemented; remaining source gates explicit.
- [x] Bound only the rule-mutation cache regression to a hand pool (`593d5be`, Luna medium):lead test passes,p1/2→1,mean2.5→1.5,four cache entries. Production and real helmet assertions unchanged; final394 tests0.915minute.

## Phase 0 -- knowledge harvest

Exit review completed in 68dd82d. Completed research tasks below do not certify unsupported
branches as executable; those dependencies remain separate tasks and questions.

- [x] Cache Craft of Exile's application and data files once; list them in `docs/SOURCES.md` (`f51e468` initial 8, `1aa58e9` four supplementary sources; 12 total)
- [x] Worker delegation smoke: one PoB row and two tests, own worktree, lead acceptance (`c1df1b6`; spec `6b4f0fe`)
- [x] Mechanical offline method inventory from frozen CoE code (`cd5e976`; worker `82fbf2b`, 95 nodes / 84 leaves / 13 custom subsets)
- [x] Action catalogue `docs/mechanics/INDEX.md` (`b313a2d`, `ebe5ab9`, `caccd08`, `68dd82d`; ordinary PoE 3.29 target confirmed Q3/D11)
- [x] Fact sheets: basic currency (Transmute .. Divine) (`1aa58e9`; reviewed ordinary branches, explicit eligibility/count limitations Q4/Q9)
- [x] Fact sheets: bench crafts and metamods (`1aa58e9`; preserved Q6/Q7/Q9; recipe data accepted `8d49e8f`)
- [x] Fact sheets: essences; fossils and resonators; harvest (`b313a2d`, `ebe5ab9`, `caccd08`, `ce4b7bf`; current Harvest steps, special CoE fossil branches and ordinary resonator gates; disputed stacking remains Q13)
- [x] Fact sheets: eldritch currency; Awakener's Orb; fracturing; veiled mods; recombinators; corruption (`5900774`, `caccd08`, `68dd82d`; conditions, examples and source conflicts retained; complete algorithms not implied)
- [x] How Craft of Exile's calculator computes probabilities; how its simulator chains steps (`ebe5ab9`, `caccd08`; exact/extrapolation, routing, batch/cost aggregation reviewed; Q14 proof is a separate follow-up)
- [x] Data builders from Path of Building's data files into `data/*.json` (`b0a19ae`, `3cb707d`, `8d49e8f`, `375528a`; selected Phase 0 tables with version/hash/line provenance; semantic stat/range interpretation remains below)
- [x] Full ModExplicit literal projection: 4310 records with source lines and hash, no inferred rules (`b0a19ae`; initial narrow projection, 19 tests then)
- [x] Base tags and bench/essence/veiled/eldritch/corruption/Delve/synthesis builders (`3cb707d`, `8d49e8f`, `375528a`; 10555 full family records, 732 bench, 105 essences)
- [x] Five-file base projection: 375 records / 371 names, 34 tests then, all fields checked by lead (`3cb707d`)
- [x] Cross-check of 54 mods over 5 item classes against CoE and PoEDB (`d440ffd`; 54 level/weight/range/side agreements each, 21 group differences Q16.01-Q16.21)
- [x] Review beast crafts, Dominance, influence orbs, synthesis implicits, catalysts/quality and item/mod-level gates (`caccd08`, `68dd82d`; six added sheets plus shared pool sheet, explicit source conflicts)
- [x] Complete original inventory-only sheets with preconditions, rule steps, numbers, conditions, examples and source comparisons before implementation (`caccd08`, `68dd82d`; researched core sheets complete in format; unsupported rule branches remain named)
- [x] Read BRIEF 3b before engine design and record outcome-distribution/value contract (`970745a`, D7 and `docs/design/build_contract.md`; reaffirmed D11)
- [x] Classify 3.29 changes from official patch notes: socket corruption, synthesis, beast splits, Fractured Fossil and bench rerolls (`5900774`, `caccd08`, Q18/Q19; replacement algorithms remain below)
- [x] Independent acceptance of all 10555 family and 837 recipe records; parser regression corrections and combined 78-test suite (`375528a`, `8d49e8f`, acceptance ledger `68dd82d`)
- [x] Phase 0 coverage audit: required families, 20 fact sheets, 62 sources and explicit optional backlog (`68dd82d`, `docs/research/phase0-coverage.md`)

## Research dependencies and catalogue follow-ups

These are retained limitations of the next implementation, not claims that Phase 0 discovered
all game mechanics. No dependent path may silently guess.

- [!] Resolve recombinator Wiki internal 70/72 count disagreement and Wiki/CoE formula differences before implementation (Q21/Q22)
- [!] Resolve Awakener conflicting-mod survivor before implementing that branch (Q20; Wiki random discard versus CoE receiver preference)
- [!] Validate canonical exclusion families, generated tags and weight multiplier semantics for a general pool resolver (Q16/Q17)
- [!] Complete action-specific special-item eligibility and replacement-action algorithms before enabling them (Q9/Q12/Q18/Q19; include new bench/Talisman branches)
- [~] Q6 first/all-draw research remains open; owner-authorized first_only adapter merged527efa7. Q26 four extra tags provisionally accepted and loadout merged55c8191.
- [~] Conflict exact odds(Q11), special fossils(Q13), quality magnitude/Tainted gaps(Q23), Blessed exclusion(Q24) and beast exchanges(Q25) remain. Ordinary CoE fossil stacking and catalyst gain distribution are accepted for implementation.
- [!] Test CoE exact-labelled formulas against independent overlapping-group enumeration before using them as an exact oracle (Q14)
- [ ] Obtain independent corroboration of rare reroll count weights (Q4) and pin supplied PoB bytes to an upstream revision (Q8); current confidence/provenance must stay visible
- [ ] Research numeric stat/range interpretation and base identity; expand beyond the five selected classes only when a concrete item slice needs it
- [ ] Expand catalogue-only socket/enchantment/unique, Memory, Allflame, Rog/Genesis and historical families into action-specific sourced sheets if selected for later work (coverage audit lists each family)
- [ ] Audit remaining CoE affinity/supplemental data and individual linked guides only when needed; cached metadata is not evidence that article bodies were read

## Phase 1 -- engine core

- [~] Item model and mod-pool resolver (`d07a1b5` ordinary slice accepted; Q16/Q17 provisionally bounded by GOAL/D14; full model still out of scope)
- [x] Ordinary action distributions and deterministic transitions (`51b386f`); bounded Divine value API (`d332f60`); unsupported value shapes and special families remain explicit
- [x] Ordinary exact stage outcome distributions (`4ee0641`,`51b386f`); predicates/thresholds reduce the same distribution (`f3cf7c2`); unsupported families remain explicit
- [x] Exact geometric/chain/compound loop costs and p90 (`8eeee53`), bounded estimated p90 fallback (`70fcadb`); hand fixtures, no Q28 display shortcuts
- [x] Monte Carlo agrees with exact over five real pools (`70fcadb`); seed, sample counts and error bounds explicit
- [x] 41 indexed hand-computed known-answer tests with sources (`8ac207c`, KA01..KA41); these are mathematical cases, distinct from data-tooling tests

## Phase 2 -- item spec -> ranked strategies

- [x] Item spec accepts required mods OR a group/tier value table + stopping threshold; helmet example (`f3cf7c2`)
- [x] `examples/bow_value_table.yaml` with explicitly invented values and threshold (BRIEF 3b; `f3cf7c2`)
- [x] Price table and loadout files (`f3cf7c2`; invented prices, explicit permissions and sourced bench quantities)
- [x] Strategy templates1-3 within ordinary night slice (`5eeefd3`): fixed spam, magic/Regal/Exalt cycle, protected-half and compatible bench finish; explicit stopping/restart rules
- [x] Ranker and `python -m craftoracle plan ...` (`d344054`,`242091f`): full ranked table plus Pareto membership, utility, mean/p90 cost, risk and required inputs
- [ ] Extend the policy library beyond the fixed ordinary slice: blocking, general bench finishing and templates4-6; special actions retain their research gates above
- [x] Validate two thresholds on shared distributions, conditional terminal utility and dominance (`242091f`); bow12 candidates/3 Pareto points; p90 remains distinct from estimation uncertainty

- [x] Night vertical slice: item model and ordinary PoB pool resolver (`d07a1b5`; 21 focused tests; corrected ordinary pool totals)
- [x] Night exact grouped distribution kernel (`4ee0641`;17 focused tests)
- [x] Night ordinary action adapters (`51b386f`;15 focused tests; one correction round)
- [x] Night loop costs exact geometric/chain/compound arithmetic (`8eeee53`;13 focused tests; explicit work limits)
- [x] Night independent Monte Carlo and p90 cost estimator (`70fcadb`;14 tests, five real pools within stated bounds)
- [x] Night item specs, invented prices and loadouts (`f3cf7c2`;12 tests; two examples and sourced bench finish)
- [x] Night concrete policies (`5eeefd3`,8 tests,9 helmet policies) and direct CLI (`d344054`,`0acb192`,9 focused tests; real helmet/bow subprocesses)
- [x] Night core integration umbrella: GOAL1-6 merged (`d344054`,`0acb192`);187 main tests in0.71minute, mandatory helmet command succeeds
- [x] Night stretch1:41 individually collected hand-computed cases (`8ac207c`,41 passed), indexed in docs/research/known-answers.md
- [x] Night stretch2: Pareto membership and two bow stopping thresholds over shared raw distributions (`242091f`,33 affected tests, full244 green)
- [x] Night stretch3: bounded Divine integer rerolls with side locks (`d332f60`,4 tests;75/225 outcomes,event2/15); selected unblocked family, D17

- [x] Owner worker-model update (`7748e73`): lead selects Terra reasoning; GPT-5.6 Luna for very light tasks with lead-selected reasoning
- [x] Final GOAL acceptance: core plus all three stretch tasks complete (`d332f60`);248 tests in0.84minutes; commands and ten-line morning summary in STATE.md
