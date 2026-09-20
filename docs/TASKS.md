# Tasks (`[x]` done + commit, `[~]` in progress, `[ ]` not started, `[!]` blocked + question id; never delete, strike with a reason)

## Phase 0 -- knowledge harvest
- [x] Cache Craft of Exile's application and data files once; list them in `docs/SOURCES.md` (`f51e468` initial 8, `1aa58e9` four supplementary sources; 12 cached files total)
- [x] Worker delegation smoke: one PoB row and two tests, own worktree, lead acceptance (`c1df1b6`; spec `6b4f0fe`)
- [x] Mechanical offline method inventory from frozen CoE code (`cd5e976`; worker `82fbf2b`, 95 nodes / 84 leaves / 13 custom subsets)
- [~] Action catalogue `docs/mechanics/INDEX.md` (`b313a2d` first draft; `ebe5ab9` missing families and status corrections; current-rule classification pending Q3)
- [~] Fact sheets: basic currency (Transmute .. Divine) (`1aa58e9` reviewed ordinary branches; eligibility matrix Q9 incomplete)
- [~] Fact sheets: bench crafts and metamods (`1aa58e9`; Q6/Q7/Q9 incomplete)
- [~] Fact sheets: essences; fossils and resonators; harvest (`b313a2d`, `ebe5ab9`; numeric essence/fossil examples recorded, Harvest steps and special fossils pending)
- [~] Fact sheets: eldritch currency; Awakener's Orb; fracturing; veiled mods; recombinators; corruption (`b313a2d`, `ebe5ab9`; explicit status per sheet; Q11 Conflict disagreement, several inventory-only placeholders)
- [~] How Craft of Exile's calculator computes probabilities; how its simulator chains steps (`ebe5ab9`, `docs/research/coe-calculator-and-policies.md`; exact/extrapolation and configuration read, execution loop and Q14 verification pending)
- [~] Data builders from Path of Building's data files into `data/*.json` (PoB version recorded; explicit projection `b0a19ae`; other tables and complete stat/range coverage pending)
- [x] Full ModExplicit literal projection: 4310 records with source lines and hash, no inferred rules (`b0a19ae`; 19 tests pass)
- [ ] Base tags and bench/essence/veiled/eldritch/corruption/Delve/synthesis builders (separate bounded specs)
- [ ] Cross-check of 50+ mods over 5 item classes against Craft of Exile and PoEDB; discrepancies into `OPEN_QUESTIONS.md`
- [ ] Review beast crafts, Dominance, influence orbs, synthesis implicits, catalysts/quality and item/mod-level gates (catalogue now exposes gaps; `ebe5ab9`)
- [ ] Complete inventory-only sheets with preconditions, rule steps, numbers, conditions, examples and explicit source comparisons before implementation
- [x] Read BRIEF 3b before engine design and record outcome-distribution/value contract (`970745a`, D7 and `docs/design/build_contract.md`)

## Phase 1 -- engine core
- [ ] Item model and mod-pool resolver; preserve state information needed by later policies, not only a scalar score (BRIEF 3b / D7)
- [ ] Actions as pure functions, one module per rule family
- [ ] Exact stage outcome distributions; target predicates and value thresholds reduce the same distribution to success probabilities
- [ ] Expected cost of spam loops, attempt/cost distribution and p90; hand-computed fixtures in `docs/design/build_contract.md`
- [ ] Monte Carlo outcome frequencies agreeing with exact distributions; seed, sample count and estimated-method labels
- [ ] 30+ known-answer tests with their sources

## Phase 2 -- item spec -> ranked strategies
- [ ] Item spec format accepting required mods OR a group/tier value table + stopping threshold; preserve owner's helmet example
- [ ] `examples/bow_value_table.yaml` with explicitly invented values and threshold (BRIEF 3b)
- [ ] Price table and loadout files
- [ ] Strategy templates 1-6 as policies with stopping/restart rules and decision points
- [ ] The ranker and `python -m craftoracle plan ...`: Pareto frontier of evaluated policies with expected utility, expected cost, p90 cost, irreversible-failure risk and rare inputs
- [ ] Validate two thresholds on one distribution, conditional terminal value, and dominance filtering; distinguish cost quantiles from confidence intervals
