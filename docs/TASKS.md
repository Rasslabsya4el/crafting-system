# Tasks (`[x]` done + commit, `[~]` in progress, `[ ]` not started, `[!]` blocked + question id; never delete, strike with a reason)

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
- [!] Resolve post-3.27 Harvest retained-flag behavior (Q6) and applicable Rancour tag/loadout rules (Q26)
- [!] Establish Conflict tier-transition odds (Q11), fossil stacking (Q13), current quality rounding (Q23), Blessed reroll exclusion (Q24) and beast exchange details (Q25)
- [!] Test CoE exact-labelled formulas against independent overlapping-group enumeration before using them as an exact oracle (Q14)
- [ ] Obtain independent corroboration of rare reroll count weights (Q4) and pin supplied PoB bytes to an upstream revision (Q8); current confidence/provenance must stay visible
- [ ] Research numeric stat/range interpretation and base identity; expand beyond the five selected classes only when a concrete item slice needs it
- [ ] Expand catalogue-only socket/enchantment/unique, Memory, Allflame, Rog/Genesis and historical families into action-specific sourced sheets if selected for later work (coverage audit lists each family)
- [ ] Audit remaining CoE affinity/supplemental data and individual linked guides only when needed; cached metadata is not evidence that article bodies were read

## Phase 1 -- engine core

- [~] Item model and mod-pool resolver (`d07a1b5` ordinary slice accepted; Q16/Q17 provisionally bounded by GOAL/D14; full model still out of scope)
- [~] Ordinary action distributions and deterministic transitions (`51b386f`); special families explicitly blocked; bounded Divine remains stretch
- [x] Ordinary exact stage outcome distributions (`4ee0641`,`51b386f`); predicates/thresholds reduce the same distribution (`f3cf7c2`); unsupported families remain explicit
- [x] Exact geometric/chain/compound loop costs and p90 (`8eeee53`), bounded estimated p90 fallback (`70fcadb`); hand fixtures, no Q28 display shortcuts
- [x] Monte Carlo agrees with exact over five real pools (`70fcadb`); seed, sample counts and error bounds explicit
- [ ] 30+ known-answer tests with their sources (the current 78 tests validate data tooling, not 78 crafting probabilities)

## Phase 2 -- item spec -> ranked strategies

- [x] Item spec accepts required mods OR a group/tier value table + stopping threshold; helmet example (`f3cf7c2`)
- [x] `examples/bow_value_table.yaml` with explicitly invented values and threshold (BRIEF 3b; `f3cf7c2`)
- [x] Price table and loadout files (`f3cf7c2`; invented prices, explicit permissions and sourced bench quantities)
- [~] Strategy templates1-3 within ordinary night slice, with stopping/restart rules and decisions; templates4-6 remain future/blocked-family work
- [~] The ranker and `python -m craftoracle plan ...`: Pareto frontier of evaluated policies with expected utility, expected cost, p90 cost, irreversible-failure risk and rare inputs
- [ ] Validate two thresholds on one distribution, conditional terminal value, and dominance filtering; distinguish cost quantiles from confidence intervals

- [x] Night vertical slice: item model and ordinary PoB pool resolver (`d07a1b5`; 21 focused tests; corrected ordinary pool totals)
- [x] Night exact grouped distribution kernel (`4ee0641`;17 focused tests)
- [x] Night ordinary action adapters (`51b386f`;15 focused tests; one correction round)
- [x] Night loop costs exact geometric/chain/compound arithmetic (`8eeee53`;13 focused tests; explicit work limits)
- [x] Night independent Monte Carlo and p90 cost estimator (`70fcadb`;14 tests, five real pools within stated bounds)
- [x] Night item specs, invented prices and loadouts (`f3cf7c2`;12 tests; two examples and sourced bench finish)
- [x] Night concrete policies (`5eeefd3`,8 tests,9 helmet policies) and direct CLI (`d344054`,`0acb192`,9 focused tests; real helmet/bow subprocesses)
- [x] Night core integration umbrella: GOAL1-6 merged (`d344054`,`0acb192`);187 main tests in0.71minute, mandatory helmet command succeeds
- [~] Night stretch1: 41 individually collected hand-computed cases (`specs/2026-09-21-known-answers.md`); dispatch after core green
- [ ] Night stretch2: Pareto membership and two bow stopping thresholds over shared raw distributions (`specs/2026-09-21-stretch-frontier.md`)
- [ ] Night stretch3: bounded Divine integer rerolls with side locks (`specs/2026-09-21-divine-values.md`); selected unblocked family, D17
