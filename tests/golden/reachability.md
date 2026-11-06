# Reachability report

What a plan can reach today, read from the planner's own code (ticket #414, audit #396 class 3). Made by `.github/scripts/reachability_report.py`; the committed copy is `tests/golden/reachability.md`, and a test fails with a diff when this text changes, so a kind that becomes reachable shows up in review. Nothing here solves a plan.

- Game data: repoe-fork 3.29.3.3 (commit ee2084de).
- Targets: the 14 files of `examples/targets/`, each through `make_plan(..., solve_it=False)` (the gates, `offers_for`, the pricing and the abstraction, nothing solved), and each start option `vendor_recipe_starts` lists for it.
- Prices: `tests/fixtures/prices/routes-allflame-2026-10-31.json`, or the target's own `price_file`; they only decide which offers are dropped for lack of a price.
- A run of the entry that outlasts `--target-seconds` is reported as "not measured, too slow" (none did).

## Summary

|  | Count |
|---|---|
| Action kinds in the catalog | 59 |
| - with `planner=False` (no plan can use them) | 28 |
| - with `planner=True` | 31 |
| - `planner=True` and offered by at least one target (reachable) | 15 |
| - `planner=True` and offered by no target | 16 |
| Benchmark targets | 14 |
| - the planner entry plans them | 12 |
| - the planner entry refuses them | 2 |
| - not measured, too slow | 0 |
| Settings and flags the planner accepts | 28 |
| - read by some code | 23 |
| - never read | 5 |
| - read, and turned on they make `make_plan` refuse every plan | 2 |

Kinds that no target is offered: 44 of 59 (28 closed by `planner=False`, 16 planner kinds that no benchmark target reaches).

## 1. Action kinds

One row per kind of `actions.catalog`, in catalog order. *Offered by* lists the targets whose planner entry offers an action of the kind after the filters and the pricing. *Why not* is what the code says: `why_not` of a `planner=False` kind, and for a planner kind the first gate or filter that removes it, with the targets it removes it for.

| Kind | Planner | Flags | Offered by | Why not | Audit |
|---|---|---|---|---|---|
| `chaos-orb` | yes |  | j01, r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12 |  |  |
| `harvest-reforge` | yes |  | r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12 |  |  |
| `harvest-reforge-influence` | yes |  | none | not named in the target's `actions:` (8 of 15 entries); the kind lists no action for this start item (5 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-reforge-likelihood` | **no** |  | none | `planner=False`: reads every junk family, so a state is a set of family types and every kernel has all-distinct weights; not in the B1 offer set until pruning (#118) decides | ACT1-4 |
| `harvest-add-remove` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-resistance-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-damage-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `harvest-quality-enchant` | **no** | only: weapon and body armour | none | `planner=False`: a finish step, priced by the finish cost of ADR-0050, never searched over |  |
| `essence` | yes |  | r04, r05, r10-fractured-boots, r10-fractured-boots-70-life, r11, r12 |  |  |
| `corrupted-essence` | yes | opt-in | r04 |  |  |
| `bench-craft` | yes |  | r04, r08, r09, r10-fractured-boots, r10-fractured-boots-70-life, r13, r14 |  |  |
| `remove-crafted-mods` | yes |  | r04, r10-fractured-boots, r10-fractured-boots-70-life, r13, r14 |  |  |
| `fossil-set` | yes | opt-in | r08, r09 |  |  |
| `alchemy-orb` | **no** |  | none | `planner=False`: not in the B1 offer set; which actions a target needs is pruning (#118) | ACT1-4, PLANNING-2 |
| `transmutation-orb` | yes |  | r13, r14, v01 |  |  |
| `alteration-orb` | yes |  | r13, r14, v01 |  |  |
| `augmentation-orb` | yes |  | r13, r14, v01 |  |  |
| `regal-orb` | yes |  | r13, r14, v01 |  |  |
| `exalted-orb` | yes | opt-in | r04, r14 |  |  |
| `influenced-exalted-orb` | **no** | reads: implicits | none | `planner=False`: a goal built from a target does not name an influenced mod yet (the compressed state holds the orb's result since ticket #155) |  |
| `veiled-chaos-orb` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `orb-of-dominance` | **no** |  | none | `planner=False`: a goal built from a target does not name an influenced or an Elevated mod yet (the compressed state tells them apart since ticket #155); the kind lists no action for any benchmark start item |  |
| `veiled-exalted-orb` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `unveil` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `pick` | yes | opt-in, reads: any | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `scouring-orb` | **no** |  | none | `planner=False`: not in the B1 offer set; which actions a target needs is pruning (#118) | ACT1-4, PLANNING-2 |
| `annulment-orb` | yes | opt-in | r04, r14 |  |  |
| `fracturing-orb` | yes | opt-in | r04 |  |  |
| `talisman-fracture` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `aspect-beast` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `beast-side-swap` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `wild-bristle-matron` | yes | opt-in | none | an opt-in kind and the target has no `actions:` key (5 of 15 entries); not named in the target's `actions:` (8 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `divine-orb` | yes |  | r10-fractured-boots-70-life |  |  |
| `awakeners-orb` | **no** |  | none | `planner=False`: the solver takes no donors yet (#211, #212) and the interval over its rule axis does not exist (#220); it takes donor items, and `make_plan` builds the abstraction with `allow_inputs=False` (2 of 14 start items list such actions) | ACT2-11 |
| `beast-influence-recipe` | **no** |  | none | `planner=False`: a goal built from a target does not name an influenced mod yet (the compressed state holds the recipe's result since ticket #155); the kind lists no action for any benchmark start item |  |
| `blessed-orb` | **no** | burns, only: an item with a ranged implicit, reads: any | none | `planner=False`: the planner refuses a target that names an implicit or a quality until ticket #159 opens it (the compressed state holds a base implicit and its roll since ticket #158) |  |
| `recombinator` | **no** | reads: any | none | `planner=False`: the planner entry takes no donors yet: it refuses an action with inputs until the report and the risk run read policies with inputs (ADR-0062 'As built'; the compressed state is built, #217, and so are the lazy offer loop, #212, and the interval driver, #220, #221); it takes donor items, and `make_plan` builds the abstraction with `allow_inputs=False` (8 of 14 start items list such actions) | ACT2-11 |
| `catalyst` | **no** | reads: any | none | `planner=False`: the planner refuses a target that names a quality until ticket #159 opens it (a goal reads the quality and offers a catalyst last since ticket #158) |  |
| `eldritch-implicit-currency` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-chaos-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-exalted-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `eldritch-annulment-orb` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `orb-of-conflict` | **no** | only: armour | none | `planner=False`: the planner refuses a target that names an implicit until ticket #159 opens it (the compressed state holds the pair since ticket #152, with its rolls, and a goal built from a target reads the implicits wanted, since ticket #158) |  |
| `tempering` | **no** | only: weapon | none | `planner=False`: the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks |  |
| `tailoring` | **no** | only: body armour | none | `planner=False`: the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks; the kind lists no action for any benchmark start item |  |
| `imprint` | **no** | reads: any | none | `planner=False`: the end-to-end ticket #223 wires R15 and R17 and measures the state growth of imprints |  |
| `restore` | **no** | reads: any | none | `planner=False`: the end-to-end ticket #223 wires R15 and R17 and measures the state growth of imprints |  |
| `foulborn-augmentation-orb` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (13 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `jewellers-orb` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `foulborn-regal-orb` | yes | needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (13 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `orb-of-fusing` | **no** | only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `bench-socket-count` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `foulborn-exalted-orb` | yes | opt-in, needs strands | none | needs Memory Strands, which `make_plan` refuses to plan with (13 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) |  |
| `bench-socket-links` | **no** | only: weapon and armour | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `chromatic-orb` | **no** | burns, only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `vaal` | yes | corrupting, only: an item whose class has a corrupted implicit pool | none | it corrupts the item and the target takes no corrupted item (13 of 15 entries); the target is refused by `make_plan` (section 3) (r03, r06) | ACT2-1 |
| `bench-socket-colours` | **no** | only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `quality-currency` | **no** | burns, only: weapon and armour, reads: quality | none | `planner=False`: a step of the socket finish (ADR-0049), bought before the orbs; the finish is attached to the goal states by ticket #231 (B6 S5) |  |
| `re-anoint` | **no** | burns | none | `planner=False`: a burn only (ticket #295, ADR-0056): as a plain action it changes nothing the state keeps and gives a target nothing; the Peek of a Lock takes it as a fallback |  |

## 2. The planner entry, target by target

| Target | Entry | `actions:` | Offers | Dropped (no price) | Offers with donor items | Kinds | Kinds offered |
|---|---|---|---|---|---|---|---|
| j01 | plans | 1 names | 1 | 0 | 0 | 1 | chaos-orb |
| r03 | refused: the target asks for implicits or quality, which the planner cannot plan yet (batch B2, tickets #142 onward) |  |  |  |  |  |  |
| r04 | plans | 8 names | 7 | 0 | 0 | 7 | annulment-orb, bench-craft, corrupted-essence, essence, exalted-orb, fracturing-orb, remove-crafted-mods |
| r05 | plans | no key | 58 | 19 | 0 | 3 | chaos-orb, essence, harvest-reforge |
| r06 | refused: the target asks for implicits or quality, which the planner cannot plan yet (batch B2, tickets #142 onward) |  |  |  |  |  |  |
| r08 | plans | 2 names | 10674 | 2026 | 0 | 2 | bench-craft, fossil-set |
| r09 | plans | 2 names | 10674 | 2026 | 0 | 2 | bench-craft, fossil-set |
| r10-fractured-boots | plans | no key | 60 | 19 | 0 | 5 | bench-craft, chaos-orb, essence, harvest-reforge, remove-crafted-mods |
| r10-fractured-boots-70-life | plans | no key | 61 | 19 | 0 | 6 | bench-craft, chaos-orb, divine-orb, essence, harvest-reforge, remove-crafted-mods |
| r11 | plans | no key | 58 | 19 | 0 | 3 | chaos-orb, essence, harvest-reforge |
| r12 | plans | no key | 58 | 19 | 0 | 3 | chaos-orb, essence, harvest-reforge |
| r13 | plans | 6 names | 6 | 0 | 0 | 6 | alteration-orb, augmentation-orb, bench-craft, regal-orb, remove-crafted-mods, transmutation-orb |
| r14 | plans | 10 names | 11 | 0 | 0 | 8 | alteration-orb, annulment-orb, augmentation-orb, bench-craft, exalted-orb, regal-orb, remove-crafted-mods, transmutation-orb |
| v01 | plans | 4 names | 4 | 0 | 0 | 4 | alteration-orb, augmentation-orb, regal-orb, transmutation-orb |
| v01 (recipe start) | plans | 4 names | 3 | 0 | 0 | 3 | alteration-orb, augmentation-orb, regal-orb |

## 3. What closes the entry

The refusals at the top of `make_plan`, as the code states them (the condition, then the message):

| Condition | Message | Benchmark targets it refuses |
|---|---|---|
| `setting.on` | Memory Strands are on ({setting.why}), which the planner cannot plan yet (batch B5, tickets #275 onward); the cut and the spend of strands are not built, so an answer would silently ignore them | no benchmark target |
| `target.implicits or target.quality is not None` | the target asks for implicits or quality, which the planner cannot plan yet (batch B2, tickets #142 onward) | r03, r06 |
| `target.sockets is not None` | the target asks for sockets, which the planner cannot plan yet (batch B6, tickets #228 and #231 onward): the finish of sockets is not built, so an answer would silently ignore them | no benchmark target |
| `target.enchantment is not None` | the target asks for an enchantment, which the planner cannot plan yet (batch B7, ticket #242 onward) | no benchmark target |
| `axes` | an offered action reads the rule axis {', '.join(axes)}, and the planner does not solve a reading of it with the interval yet (ticket #220) | no benchmark target |

- `Abstraction(..., allow_inputs=False) in make_plan`: an action that consumes other items is refused by the kernel, so the Awakener's Orb and the recombinator cannot be planned.
- `memory_strands` on (`--strands`, or the setting): `make_plan` says "Memory Strands are on (the setting memory_strands is on (`--strands` or crafting.toml)), which the planner cannot plan yet (batch B5, tickets #275 onward)."
- Targets that take a corrupted item (`allow_corrupted`, or a corrupted implicit): none; offers of a corrupting action over all entries: 0.
- Fossil sets that use the Bloodstained Fossil (offered only when the target asks for a corrupted implicit): up to 2302 listed for one start item, 0 offered by any entry.

## 4. Settings and flags

Every key `crafting.toml` accepts and every flag of the plan and `benchmark` commands. An AST search of `src/` follows each value from where it is read (`config.key`, `args.flag`) through the parameters, fields and variables it is handed on to. *Read* means the value is compared, tested, formatted, calculated with or handed to code outside `src/`; storing it and passing it on is not reading. *Planning path* means the function that reads it is reached from `main`, `make_plan` or `plan_with_starts`.

| Setting or flag | Accepted in | Default | Verdict | Where it is read, or where it stops |
|---|---|---|---|---|
| `data` | [paths] | `local/data` | read | prices/price_file.py: default_overrides_path (used in an operation; on the planning path); prices/price_file.py: default_price_file_path (used in an operation; on the planning path) |
| `cache` | [paths] | `local/cache` | read | cli/_route_view.py: _trade_stats (compared; on the planning path); cli/_route_view.py: _trade_stats (used in an operation; on the planning path); and 4 more |
| `output` | [paths] | `local/output` | read | cli/_benchmark.py: benchmark_main (used in an operation; on the planning path); cli/_main.py: main (used in an operation; on the planning path) |
| `memory_strands` | [planner] | `false` | read | cli/_plan.py: strand_setting (decides a branch; on the planning path); turned on, it makes `make_plan` refuse every plan (section 3) |
| `recipe_starts` | [planner] | `true` | read | cli/_starts.py: plan_with_starts (used in an operation; on the planning path) |
| `recombinator_junk_craft` | [planner] | `false` | **never read** | no code reads it |
| `max_imprints` | [planner] | `1` | **never read** | no code reads it |
| `price_source` | [planner] | `both` | **never read** | stops at the field `StartContext.price_source` |
| `price_gap_percent` | [planner] | `20.0` | **never read** | stops at the field `StartContext.gap_percent` |
| `--budget` | command `plan` |  | read | cli/_approx.py: climb (decides a branch; on the planning path); cli/_approx.py: climb (used in an operation; on the planning path); and 4 more |
| `--exact` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |
| `--heavy` | command `benchmark` |  | read | cli/_benchmark.py: run_route (used in an operation; on the planning path) |
| `--indexed` | command `trade` |  | read | cli/_trade.py: trade_main (compared; on the planning path); prices/trade_pricing.py: _window_hint (compared; on the planning path); and 6 more |
| `--json` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path); cli/_main.py: main (passed to `Path` (outside src); on the planning path) |
| `--k` | command `trade` |  | read | prices/price_file.py: _entry_to_json (compared; on the planning path); prices/price_file.py: write_price_file (used in DictComp; on the planning path); and 7 more |
| `--max-requests` | command `trade` |  | read | prices/trade_http.py: RequestBudget.__init__ (compared; on the planning path); prices/trade_http.py: RequestBudget.remaining (used in an operation; not on the planning path); and 2 more |
| `--min-listings` | command `trade` |  | read | prices/trade_market.py: classify (compared; on the planning path); prices/trade_pricing.py: market_of_listings (compared; on the planning path); and 1 more |
| `--no-recipe-starts` | command `plan` |  | read | cli/_main.py: main (used in an operation; on the planning path) |
| `--out` | command `benchmark` |  | read | cli/_benchmark.py: benchmark_main (decides a branch; on the planning path); cli/_benchmark.py: benchmark_main (passed to `Path` (outside src); on the planning path) |
| `--price-source` | command `plan` |  | **never read** | stops at the field `StartContext.price_source` |
| `--progress` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |
| `--refresh-stats` | command `trade` |  | read | prices/trade_pricing.py: _stats (decides a branch; on the planning path) |
| `--route` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path); cli/_main.py: main (passed to `Path` (outside src); on the planning path); and 1 more |
| `--runs` | command `plan` |  | read | cli/_marking.py: verification_lines (formatted into text; on the planning path); cli/_report.py: _verification_lines (formatted into text; on the planning path); and 9 more |
| `--seed` | command `plan` |  | read | cli/_marking.py: verification_lines (formatted into text; on the planning path); cli/_report.py: _verification_lines (formatted into text; on the planning path); and 4 more |
| `--start-price` | command `plan` |  | read | cli/_plan.py: _override (compared; on the planning path); cli/_plan.py: _override (formatted into text; on the planning path); and 2 more |
| `--strands` | command `plan` |  | read | cli/_plan.py: strand_setting (decides a branch; on the planning path); turned on, it makes `make_plan` refuse every plan (section 3) |
| `--verify` | command `plan` |  | read | cli/_main.py: main (decides a branch; on the planning path) |

Code that takes a never-read setting by its own name:

- `recombinator_junk_craft`: context variable `recombinator_junk_craft` in `actions/recombinator.py`: set by `junk_craft_offered` (0 referrer(s) outside its module)
- `max_imprints`: parameter `max_imprints` of `actions/imprint.py: imprint_actions`: 0 referrer(s) outside its module, 0 pass the parameter
- `price_source`: parameter `price_source` of `cli/_starts.py: plan_with_starts`: 2 referrer(s) outside its module, 1 pass the parameter
- `price_gap_percent`: parameter `price_gap_percent` of `cli/_starts.py: plan_with_starts`: 2 referrer(s) outside its module, 1 pass the parameter

- `price_source`: reads of an attribute with the same name on a receiver of unknown type, not counted: cli._main: main, cli._start_report: first_step_document, cli._start_report: first_step_lines, cli._starts: _plan_candidate.
- `price_gap_percent`: reads of an attribute with the same name on a receiver of unknown type, not counted: prices.price_source: SourcedPrice.document, prices.price_source: SourcedPrice.lines.
- `--price-source`: reads of an attribute with the same name on a receiver of unknown type, not counted: cli._main: main, cli._start_report: first_step_document, cli._start_report: first_step_lines, cli._starts: _plan_candidate.

## 5. Built modules

The public names of the modules the audit says are built and not wired. *Referenced by* lists the other modules of `src/` that name it (tests are not counted); *Planning path* says whether `main`, `make_plan` or `plan_with_starts` reaches it through such references.

| Built module | Name | In | Referenced by | Planning path | Audit |
|---|---|---|---|---|---|
| the market rule | `TradeOffer` | `prices/trade_market.py` | nothing | **no** | INPUTS-2 |
| the market rule | `age_in_days` | `prices/trade_market.py` | prices/trade_pricing.py: trade_price_age_days | **no** | INPUTS-2 |
| the market rule | `classify` | `prices/trade_market.py` | prices/trade_pricing.py: market_of_listings | yes | INPUTS-2 |
| the market rule | `offer` | `prices/trade_market.py` | prices/price_source.py: source_price | **no** | INPUTS-2 |
| the price-source rule | `SourcedPrice` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `check_gap_percent` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `check_price_source` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `gap_percent` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `ninja_row` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the price-source rule | `source_price` | `prices/price_source.py` | nothing | **no** | INPUTS-2, PLANNING-6 |
| the item-level floor | `ItemLevelFloor` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `ItemLevelOptions` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `LevelGroup` | `targets/floor.py` | nothing | yes | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `NodeLevel` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `floor_of` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `item_level_options` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `level_groups` | `targets/floor.py` | targets/start_buy.py: item_level_window | yes | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `refusal_at` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the item-level floor | `target_at_level` | `targets/floor.py` | nothing | **no** | TARGETS-3, PLANNING-8, ROUTES-13 |
| the donor loop of two-input actions | `DonorModel` | `cli/_donors.py` | nothing | **no** | ACT2-11 |
| the donor loop of two-input actions | `solve_with_donors` | `cli/_donors.py` | nothing | **no** | ACT2-11 |
| the donor loop of two-input actions | `takes_inputs` | `cli/_donors.py` | nothing | **no** | ACT2-11 |

## 6. Target keys

The fields of the `Target` a YAML file fills in, and the modules outside `targets/` that read each one on a receiver known to be a `Target` (a parameter annotated `Target`, or named `target`). A key nothing reads is accepted and ignored.

| Target field | Read by | Audit |
|---|---|---|
| `base_id` | cli/_benchmark_outcomes.py, cli/_plan.py, cli/_route_card.py, cli/_start_step.py |  |
| `item_level` | cli/_benchmark_outcomes.py, cli/_plan.py, cli/_route_card.py |  |
| `influences` | cli/_route_card.py |  |
| `requirements` | abstraction/_goal.py, cli/_benchmark.py, cli/_plan.py, cli/_route_card.py, cli/_start_options.py |  |
| `start_item` | cli/_benchmark_outcomes.py, cli/_plan.py, cli/_starts.py |  |
| `price_file` | cli/_benchmark.py, cli/_main.py |  |
| `start` | **nothing** |  |
| `implicits` | abstraction/_goal.py, cli/_plan.py, cli/_route_card.py |  |
| `quality` | abstraction/_goal.py, cli/_plan.py, cli/_route_card.py |  |
| `actions` | cli/_benchmark_outcomes.py, cli/_plan.py |  |
| `enchantment` | cli/_plan.py |  |
| `allow_corrupted` | abstraction/_goal.py |  |
| `sockets` | cli/_plan.py |  |
| `start_sockets_assumed` | **nothing** |  |
| `item_level_floor` | **nothing** | TARGETS-3, PLANNING-8 |

