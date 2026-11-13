# Reachability report

What a plan can reach today, read from the planner's own code (ticket #414, audit #396 class 3). Made by `.github/scripts/reachability_report.py`; the committed copy is `tests/golden/reachability.md`, and a test fails with a diff when this text changes, so a kind that becomes reachable shows up in review. Nothing here solves a plan.

- Game data: repoe-fork 3.29.3.3 (commit ee2084de).
- Targets: the 17 files of `examples/targets/`, each through `make_plan(..., solve_it=False)` (the gates, `offers_for`, the pricing and the abstraction, nothing solved), and each start option `vendor_recipe_starts` lists for it.
- Prices: `tests/fixtures/prices/routes-allflame-2026-07-31.json`, or the target's own `price_file`; they only decide which offers are dropped for lack of a price.
- A run of the entry that outlasts `--target-seconds` is reported as "not measured, too slow" (none did).

## Summary

|  | Count |
|---|---|
| Action kinds in the catalog | 62 |
| - with `planner=False` (no plan can use them) | 25 |
| - with `planner=True` | 37 |
| - `planner=True` and offered by at least one target (reachable) | 21 |
| - `planner=True` and offered by no target | 16 |
| Benchmark targets | 17 |
| - the planner entry plans them | 15 |
| - the planner entry refuses them | 2 |
| - not measured, too slow | 0 |
| Settings and flags the planner accepts | 34 |
| - read by some code | 33 |
| - never read | 1 |
| - read, and turned on they make `make_plan` refuse every plan | 2 |

Kinds that no target is offered: 41 of 62 (25 closed by `planner=False`, 16 planner kinds that no benchmark target reaches).

## 1. Action kinds

One row per kind of `actions.catalog`, in catalog order. *Offered by* lists the targets whose planner entry offers an action of the kind after the filters and the pricing. *Why not* is what the code says: `why_not` of a `planner=False` kind, and for a planner kind the first gate or filter that removes it, with the targets it removes it for.

| Kind | Planner | Flags | Offered by | Why not | Audit |
|---|---|---|---|---|---|
| `chaos-orb` | yes |  | j01, r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12 |  |  |
| `harvest-reforge` | yes |  | r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12 |  |  |
| `harvest-reforge-influence` | yes |  | none | not named in the target's `actions:` (11 of 18 entries); the kind lists no action for this start item (5 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-reforge-likelihood` | **no** |  | none | `planner=False`: reads every junk family, so a state is a set of family types and every kernel has all-distinct weights; not in the B1 offer set until pruning (#118) decides | ACT1-4 |
| `harvest-add-remove` | yes | opt-in | r17, r24 |  |  |
| `harvest-resistance-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-damage-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-quality-enchant` | **no** | only: weapon and body armour | none | `planner=False`: a finish step, priced by the finish cost of ADR-0050, never searched over |  |
| `essence` | yes |  | r04, r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12, r24 |  |  |
| `corrupted-essence` | yes | opt-in | r04 |  |  |
| `bench-craft` | yes |  | r04, r07, r08, r09, r10-fractured-boots, r10-fractured-boots-70-life, r13, r14, r17, r24 |  |  |
| `remove-crafted-mods` | yes |  | r04, r07, r10-fractured-boots, r10-fractured-boots-70-life, r13, r14, r24 |  |  |
| `fossil-set` | yes | opt-in | r07, r08, r09 |  |  |
| `alchemy-orb` | **no** |  | none | `planner=False`: not in the B1 offer set; which actions a target needs is pruning (#118) | ACT1-4, PLANNING-2 |
| `transmutation-orb` | yes |  | r17, v01 |  |  |
| `alteration-orb` | yes |  | r13, r14, r17, v01 |  |  |
| `augmentation-orb` | yes |  | r13, r14, r17, v01 |  |  |
| `regal-orb` | yes |  | r13, r14, r17, v01 |  |  |
| `exalted-orb` | yes | opt-in | r04, r14 |  |  |
| `influenced-exalted-orb` | **no** | reads: implicits | none | `planner=False`: a goal built from a target does not name an influenced mod yet (the compressed state holds the orb's result since ticket #155) |  |
| `veiled-chaos-orb` | yes | opt-in, reads: any | r07, r24 |  |  |
| `orb-of-dominance` | **no** |  | none | `planner=False`: a goal built from a target does not name an influenced or an Elevated mod yet (the compressed state tells them apart since ticket #155); the kind lists no action for any benchmark start item |  |
| `veiled-exalted-orb` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `unveil` | yes | opt-in, reads: any | r07, r24 |  |  |
| `pick` | yes | opt-in, reads: any | r07, r24 |  |  |
| `scouring-orb` | **no** |  | none | `planner=False`: not in the B1 offer set; which actions a target needs is pruning (#118) | ACT1-4, PLANNING-2 |
| `annulment-orb` | yes | opt-in | r04, r07, r14, r17, r24 |  |  |
| `fracturing-orb` | yes | opt-in | r04 |  |  |
| `talisman-fracture` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `aspect-beast` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `beast-side-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `wild-bristle-matron` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `divine-orb` | yes |  | r10-fractured-boots, r10-fractured-boots-70-life, r11 |  |  |
| `awakeners-orb` | **no** |  | none | `planner=False`: the planner entry takes no donors yet (#211, #212): it refuses an action with inputs (ADR-0062 'As built'); it takes donor items, and `make_plan` builds the abstraction with `allow_inputs=False` (2 of 17 start items list such actions) | ACT2-11 |
| `beast-influence-recipe` | **no** |  | none | `planner=False`: a goal built from a target does not name an influenced mod yet (the compressed state holds the recipe's result since ticket #155); the kind lists no action for any benchmark start item |  |
| `blessed-orb` | **no** | burns, only: an item with a ranged implicit, reads: any | none | `planner=False`: the planner refuses a target that names an implicit or a quality until ticket #159 opens it (the compressed state holds a base implicit and its roll since ticket #158) |  |
| `recombinator` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 18 entries); not named in the target's `actions:` (11 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) | ACT2-11 |
| `catalyst` | **no** | reads: any | none | `planner=False`: the planner refuses a target that names a quality until ticket #159 opens it (a goal reads the quality and offers a catalyst last since ticket #158) |  |
| `eldritch-implicit-currency` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-chaos-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-exalted-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-annulment-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `orb-of-conflict` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `tempering` | **no** | only: weapon | none | `planner=False`: the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks |  |
| `tailoring` | **no** | only: body armour | none | `planner=False`: the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks; the kind lists no action for any benchmark start item |  |
| `imprint` | yes | opt-in, reads: any | r17 |  |  |
| `restore` | yes | opt-in, reads: any | r17 |  |  |
| `foulborn-augmentation-orb` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `jewellers-orb` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `foulborn-regal-orb` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `orb-of-fusing` | **no** | only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `bench-socket-count` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `foulborn-exalted-orb` | yes | opt-in, needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `bench-socket-links` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `orb-of-remembrance` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `chromatic-orb` | **no** | burns, only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `vaal` | yes | corrupting, only: an item whose class has a corrupted implicit pool | none | it corrupts the item and the target takes no corrupted item (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) | ACT2-1 |
| `bench-socket-colours` | **no** | only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods |  |
| `quality-currency` | **no** | burns, only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0049), bought before the orbs when that is cheaper: solved with the finish of a target that names sockets (`planner/_finish.py`), never searched over as a step of the mods |  |
| `re-anoint` | **no** | burns | none | `planner=False`: a burn only (ticket #295, ADR-0056): as a plain action it changes nothing the state keeps and gives a target nothing; the Peek of a Lock takes it as a fallback |  |
| `locus` | yes | corrupting, only: an item whose class has a corrupted implicit pool | none | it corrupts the item and the target takes no corrupted item (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `unravelling-orb` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (16 of 18 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |

## 2. The planner entry, target by target

| Target | Entry | `actions:` | Offers | Dropped (no price) | Offers with donor items | Kinds | Kinds offered |
|---|---|---|---|---|---|---|---|
| j01 | plans | 1 names | 1 | 0 | 0 | 1 | chaos-orb |
| r03 | refused: the target asks for implicits or quality, which the planner cannot plan yet |  |  |  |  |  |  |
| r04 | plans | 8 names | 7 | 0 | 0 | 7 | annulment-orb, bench-craft, corrupted-essence, essence, exalted-orb, fracturing-orb, remove-crafted-mods |
| r05 | plans | no key | 77 | 0 | 0 | 3 | chaos-orb, essence, harvest-reforge |
| r06 | refused: the target asks for implicits or quality, which the planner cannot plan yet |  |  |  |  |  |  |
| r07 | plans | 8 names | 11 | 0 | 0 | 7 | annulment-orb, bench-craft, fossil-set, pick, remove-crafted-mods, unveil, veiled-chaos-orb |
| r08 | plans | 2 names | 12698 | 0 | 0 | 2 | bench-craft, fossil-set |
| r09 | plans | 2 names | 12698 | 0 | 0 | 2 | bench-craft, fossil-set |
| r10-fractured-boots | plans | no key | 80 | 0 | 0 | 6 | bench-craft, chaos-orb, divine-orb, essence, harvest-reforge, remove-crafted-mods |
| r10-fractured-boots-70-life | plans | no key | 80 | 0 | 0 | 6 | bench-craft, chaos-orb, divine-orb, essence, harvest-reforge, remove-crafted-mods |
| r11 | plans | no key | 78 | 0 | 0 | 4 | chaos-orb, divine-orb, essence, harvest-reforge |
| r12 | plans | no key | 77 | 0 | 0 | 3 | chaos-orb, essence, harvest-reforge |
| r13 | plans | 5 names | 6 | 0 | 0 | 5 | alteration-orb, augmentation-orb, bench-craft, regal-orb, remove-crafted-mods |
| r14 | plans | 9 names | 11 | 0 | 0 | 7 | alteration-orb, annulment-orb, augmentation-orb, bench-craft, exalted-orb, regal-orb, remove-crafted-mods |
| r17 | plans | 11 names | 14 | 0 | 0 | 9 | alteration-orb, annulment-orb, augmentation-orb, bench-craft, harvest-add-remove, imprint, regal-orb, restore, transmutation-orb |
| r24 | plans | 10 names | 12 | 0 | 0 | 8 | annulment-orb, bench-craft, essence, harvest-add-remove, pick, remove-crafted-mods, unveil, veiled-chaos-orb |
| v01 | plans | 4 names | 4 | 0 | 0 | 4 | alteration-orb, augmentation-orb, regal-orb, transmutation-orb |
| v01 (recipe start) | plans | 4 names | 3 | 0 | 0 | 3 | alteration-orb, augmentation-orb, regal-orb |

## 3. What closes the entry

The refusals at the top of `make_plan`, as the code states them (the condition, then the message):

| Condition | Message | Benchmark targets it refuses |
|---|---|---|
| `setting.on` | Memory Strands are on ({setting.why}), which the planner cannot plan yet: the cut and the spend of strands are not built, so an answer would silently ignore them | no benchmark target |
| `target.implicits or target.quality is not None` | the target asks for implicits or quality, which the planner cannot plan yet | r03, r06 |
| `target.enchantment is not None` | the target asks for an enchantment, which the planner cannot plan yet | no benchmark target |
| `axes and solver not in ('auto', 'object')` | an offered action reads a rule the sources leave open ({', '.join((axis_what(axis.name) for axis in axes))}), so the plan is made once for each reading of that rule by the search that holds every item it reaches; `--solver {solver}` does not do that | no benchmark target |

- `Abstraction(..., allow_inputs=bool(donated)) in make_plan`: an action that consumes other items is planned only when it reads a rule axis, with the second items the planner offers (the recombinator: the target's isolated feeders); one without an axis is refused by the kernel.
- `memory_strands` on (`--strands`, or the setting): `make_plan` says "Memory Strands are on (asked for by `--strands` or in the planner settings), which the planner cannot plan yet: the cut and the spend of strands are not built, so an answer would silently ignore them"
- Targets that take a corrupted item (`allow_corrupted`, or a corrupted implicit): none; offers of a corrupting action over all entries: 0.
- Fossil sets that use the Bloodstained Fossil (offered only when the target asks for a corrupted implicit): up to 2302 listed for one start item, 0 offered by any entry.

## 4. Settings and flags

Every key `crafting.toml` accepts and every flag of the plan and `benchmark` commands. An AST search of `src/` follows each value from where it is read (`config.key`, `args.flag`) through the parameters, fields and variables it is handed on to. *Read* means the value is compared, tested, formatted, calculated with or handed to code outside `src/`; storing it and passing it on is not reading. *Planning path* means the function that reads it is reached from `main`, `make_plan` or `plan_with_starts`.

| Setting or flag | Accepted in | Default | Verdict | Where it is read, or where it stops |
|---|---|---|---|---|
| `data` | [paths] | `local/data` | read | prices/price_file.py: default_overrides_path (used in an operation; on the planning path); prices/price_file.py: default_price_file_path (used in an operation; on the planning path) |
| `cache` | [paths] | `local/cache` | read | cli/_route_view.py: _trade_stats (compared; on the planning path); cli/_route_view.py: _trade_stats (used in an operation; on the planning path); and 4 more |
| `output` | [paths] | `local/output` | read | cli/_benchmark.py: benchmark_main (used in an operation; on the planning path); cli/_main.py: main (used in an operation; on the planning path) |
| `memory_strands` | [planner] | `false` | read | planner/_plan.py: strand_setting (decides a branch; on the planning path); planner/_starts.py: _with_starts (read from `**kwargs`; on the planning path); and 1 more; turned on, it makes `make_plan` refuse every plan (section 3) |
| `recipe_starts` | [planner] | `true` | read | planner/_starts.py: _with_starts (used in an operation; on the planning path) |
| `recombinator_junk_craft` | [planner] | `false` | **never read** | no code reads it |
| `max_imprints` | [planner] | `1` | read | cli/_benchmark.py: benchmark_main (passed to `imprints_held_at_most` (outside src); on the planning path); cli/_main.py: main (passed to `imprints_held_at_most` (outside src); on the planning path) |
| `price_source` | [planner] | `both` | read | planner/_starts.py: plan_with_starts (an attribute or method of it is used; on the planning path); planner/_starts.py: plan_with_starts (passed on in `**`; on the planning path) |
| `price_gap_percent` | [planner] | `20.0` | read | cli/_inputs.py: write_json (passed to `json.dumps` (outside src); on the planning path); cli/_main.py: main (used as an index or container; on the planning path); and 9 more |
| `time_limit_seconds` | [planner] | `600.0` | read | budget.py: Binding.early (used in an operation; not on the planning path); budget.py: Binding.words (formatted into text; on the planning path); and 5 more |
| `memory_limit_mb` | [planner] | `share` | read | budget.py: Binding.early (used in an operation; not on the planning path); budget.py: Binding.words (formatted into text; on the planning path); and 8 more |
| `--budget` | command `plan` |  | read | planner/_approx.py: climb (decides a branch; on the planning path); planner/_approx.py: climb (used in an operation; on the planning path); and 4 more |
| `--exact` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |
| `--gap` | command `plan` |  | read | cli/_main.py: main (used in an operation; on the planning path) |
| `--heavy` | command `benchmark` |  | read | cli/_benchmark.py: run_route (used in an operation; on the planning path) |
| `--indexed` | command `trade` |  | read | cli/_trade.py: trade_main (compared; on the planning path); prices/trade_pricing.py: _window_hint (compared; on the planning path); and 6 more |
| `--json` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path); cli/_main.py: main (passed to `Path` (outside src); on the planning path) |
| `--k` | command `trade` |  | read | prices/deepen.py: _deep_reading (an attribute or method of it is used; not on the planning path); prices/essence_recipe.py: _replaced (an attribute or method of it is used; on the planning path); and 16 more |
| `--max-requests` | command `trade` |  | read | prices/trade_http.py: RequestBudget.__init__ (compared; on the planning path); prices/trade_http.py: RequestBudget.remaining (used in an operation; not on the planning path); and 2 more |
| `--memory-limit` | command `plan` |  | read | budget.py: Binding.early (used in an operation; not on the planning path); budget.py: Binding.words (formatted into text; on the planning path); and 8 more |
| `--min-listings` | command `trade` |  | read | prices/trade_market.py: classify (compared; on the planning path); prices/trade_pricing.py: market_of_listings (compared; on the planning path); and 1 more |
| `--no-recipe-starts` | command `plan` |  | read | cli/_main.py: main (used in an operation; on the planning path) |
| `--out` | command `benchmark` |  | read | cli/_benchmark.py: benchmark_main (decides a branch; on the planning path); cli/_benchmark.py: benchmark_main (passed to `Path` (outside src); on the planning path) |
| `--price-source` | command `plan` |  | read | planner/_starts.py: plan_with_starts (an attribute or method of it is used; on the planning path); planner/_starts.py: plan_with_starts (passed on in `**`; on the planning path) |
| `--progress` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |
| `--refresh-stats` | command `trade` |  | read | prices/trade_pricing.py: _stats (decides a branch; on the planning path) |
| `--route` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path); cli/_main.py: main (passed to `Path` (outside src); on the planning path); and 2 more |
| `--runs` | command `plan` |  | read | cli/_marking.py: verification_lines (formatted into text; on the planning path); cli/_report.py: _verification_lines (formatted into text; on the planning path); and 9 more |
| `--seed` | command `plan` |  | read | cli/_marking.py: verification_lines (formatted into text; on the planning path); cli/_report.py: _verification_lines (formatted into text; on the planning path); and 4 more |
| `--solver` | command `plan` |  | read | planner/_packed.py: packed_result (compared; on the planning path); planner/_packed.py: packed_result (formatted into text; on the planning path); and 5 more |
| `--start-price` | command `plan` |  | read | planner/_plan.py: _override (compared; on the planning path); planner/_plan.py: _override (formatted into text; on the planning path); and 2 more |
| `--strands` | command `plan` |  | read | planner/_plan.py: strand_setting (decides a branch; on the planning path); planner/_starts.py: _with_starts (read from `**kwargs`; on the planning path); and 1 more; turned on, it makes `make_plan` refuse every plan (section 3) |
| `--time-limit` | command `plan` |  | read | budget.py: Binding.early (used in an operation; not on the planning path); budget.py: Binding.words (formatted into text; on the planning path); and 6 more |
| `--verify` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |

Code that takes a never-read setting by its own name:

- `recombinator_junk_craft`: context variable `recombinator_junk_craft` in `actions/recombinator.py`: set by `junk_craft_offered` (0 referrer(s) outside its module)

## 5. Built modules

The public names of the modules the audit says are built and not wired (of a module the command does use, only the names that are built and not wired). *Referenced by* lists the other modules of `src/` that name it (tests are not counted); *Planning path* says whether `main`, `make_plan` or `plan_with_starts` reaches it through such references.

| Built module | Name | In | Referenced by | Planning path | Audit |
|---|---|---|---|---|---|
| the market rule | `PlannedPrice` | `prices/trade_market.py` | nothing | yes | INPUTS-2 |
| the market rule | `TradeOffer` | `prices/trade_market.py` | nothing | yes | INPUTS-2 |
| the market rule | `age_in_days` | `prices/trade_market.py` | prices/trade_pricing.py: trade_price_age_days | **no** | INPUTS-2 |
| the market rule | `classify` | `prices/trade_market.py` | prices/trade_exchange.py: read_offers, prices/trade_pricing.py: is_deep, prices/trade_pricing.py: market_of_listings | yes | INPUTS-2 |
| the market rule | `offer` | `prices/trade_market.py` | prices/price_source.py: source_price | **no** | INPUTS-2 |
| the market rule | `planned_price` | `prices/trade_market.py` | cli/_benchmark.py: _missing_start_price, cli/_trade.py: _priced_as, planner/_bought_starts.py: _option, and 6 more | yes | INPUTS-2 |
| the price-source rule | `SourcedPrice` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `check_gap_percent` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `check_price_source` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `gap_percent` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `ninja_row` | `prices/price_source.py` | planner/_bought_starts.py: _Level.__init__, planner/_bought_starts.py: _without_thin_row | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `source_price` | `prices/price_source.py` | planner/_bought_starts.py: _Level.__init__ | **no** | INPUTS-2, PLANNING-6 |
| the item-level floor | `ItemLevelFloor` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `ItemLevelOptions` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `LevelGroup` | `targets/floor.py` | nothing | yes | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `NodeLevel` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `floor_of` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `item_level_options` | `targets/floor.py` | planner/_bought_starts.py: bought_base_starts | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `level_groups` | `targets/floor.py` | planner/_bought_starts.py: bought_base_starts, targets/start_buy.py: item_level_window | yes | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `refusal_at` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `target_at_level` | `targets/floor.py` | planner/_bought_starts.py: _Level.__init__, planner/_bought_starts.py: bought_base_starts | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the donor loop of two-input actions | `DonorModel` | `planner/_donors.py` | planner/_plan.py: solve_each_reading | yes | ACT2-11 |
| the donor loop of two-input actions | `is_feeder` | `planner/_donors.py` | nothing | **no** | ACT2-11 |
| the donor loop of two-input actions | `solve_with_donors` | `planner/_donors.py` | nothing | **no** | ACT2-11 |

## 6. Target keys

The fields of the `Target` a YAML file fills in, and the modules outside `targets/` that read each one on a receiver known to be a `Target` (a parameter annotated `Target`, or named `target`). A key nothing reads is accepted and ignored.

| Target field | Read by | Audit |
|---|---|---|
| `base_id` | cli/_benchmark_outcomes.py, cli/_route_card.py, cli/_start_step.py, planner/_bought_starts.py, planner/_finish.py, and 1 more |  |
| `item_level` | cli/_benchmark_outcomes.py, cli/_route_card.py, planner/_finish.py, planner/_plan.py |  |
| `influences` | cli/_route_card.py, planner/_bought_starts.py |  |
| `requirements` | abstraction/_goal.py, cli/_benchmark.py, cli/_route_card.py, planner/_bought_starts.py, planner/_plan.py, and 1 more |  |
| `start_item` | cli/_benchmark_outcomes.py, planner/_bought_starts.py, planner/_finish.py, planner/_plan.py, planner/_starts.py |  |
| `start` | cli/_benchmark.py, cli/_main.py, cli/_trade.py, planner/_plan.py, planner/_starts.py |  |
| `price_file` | cli/_benchmark.py, cli/_main.py |  |
| `implicits` | abstraction/_goal.py, cli/_route_card.py, planner/_plan.py |  |
| `quality` | abstraction/_goal.py, cli/_route_card.py, planner/_plan.py |  |
| `actions` | cli/_benchmark_outcomes.py, planner/_plan.py |  |
| `enchantment` | planner/_plan.py |  |
| `allow_corrupted` | abstraction/_goal.py |  |
| `sockets` | planner/_finish.py, planner/_plan.py |  |
| `item_level_floor` | **nothing** | TARGETS-3, PLANNING-8 |

