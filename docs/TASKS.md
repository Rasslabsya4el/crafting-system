# Tasks (`[x]` done + commit, `[~]` in progress, `[ ]` not started, `[!]` blocked + question id; never delete, strike with a reason)

## Phase 0 -- knowledge harvest
- [x] Cache Craft of Exile's application and data files once; list them in `docs/SOURCES.md` (`f51e468`; 11 files plus homepage)
- [x] Worker delegation smoke: one PoB row and two tests, own worktree, lead acceptance (`c1df1b6`; spec `6b4f0fe`)
- [x] Mechanical offline method inventory from frozen CoE code (`cd5e976`; worker `82fbf2b`, 95 nodes / 84 leaves / 13 custom subsets)
- [x] Action catalogue `docs/mechanics/INDEX.md` (`cd5e976`; rows and honest status/confidence)
- [x] Fact sheets: basic currency (Transmute .. Divine) (`1aa58e9`)
- [x] Fact sheets: bench crafts and metamods (`1aa58e9`)
- [~] Fact sheets: essences; fossils and resonators; harvest (`cd5e976`; essence and harvest sheets; fossil rules pending)
- [~] Fact sheets: eldritch currency; Awakener's Orb; fracturing; veiled mods; recombinators; corruption (`cd5e976`; inventory/partial sheets; matrices pending)
- [ ] How Craft of Exile's calculator computes probabilities; how its simulator chains steps (notes with pointers)
- [ ] Data builders from Path of Building's data files into `data/*.json` (PoB version recorded)
- [ ] Cross-check of 50+ mods over 5 item classes against Craft of Exile and PoEDB; discrepancies into `OPEN_QUESTIONS.md`

## Phase 1 -- engine core
- [ ] Item model and mod-pool resolver
- [ ] Actions as pure functions, one module per rule family
- [ ] Exact probability calculators + expected cost of spam loops
- [ ] Monte Carlo harness agreeing with the exact calculators
- [ ] 30+ known-answer tests with their sources

## Phase 2 -- item spec -> ranked strategies
- [ ] Item spec format + the owner's helmet example
- [ ] Price table and loadout files
- [ ] Strategy templates 1-6 of the brief
- [ ] The ranker and `python -m craftoracle plan ...`
