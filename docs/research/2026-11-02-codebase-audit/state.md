# Audit #396: THE STATE (`src/crafting_system/abstraction/`, `src/crafting_system/items/`, layer-1 oracles in `tests/abstraction_*`)

Read in full: `abstraction/_state.py`, `_goal.py`, `_kinds.py`, `_kernel.py` (all 1,877 lines), `_rolls.py`; skimmed `_bound.py`, `_coarse.py`,
`_estimate.py`, `_prime.py`; `items/model.py`, `tiers.py`, `spawn.py`, `veiled.py`, `implicits.py`, `quality.py`, `vendor_recipes.py`;
ADR-0009, 0019, 0025 (skimmed), 0027, 0029, 0036, 0040; the #312 research note; the oracles `tests/abstraction_oracle.py`,
`abstraction_adds_oracle.py`, `abstraction_b2_support.py`, `abstraction_pool.py`, `contract_support.py` and the other `abstraction_*` support files.
All measurements are quick snippets on the real 3.29.3.3 cache (walk of the reachable states with the real kernels; no solve, no sweep, longest run 5 s).
Scratch scripts: the auditor's scratchpad (not kept).

What the compressed state keeps and who reads it (field by field):

| Field | Written from | Read by | Verdict |
| --- | --- | --- | --- |
| `flags.rarity` | item rarity | every action's refusal, capacity in the pool signature | read |
| `flags.corrupted` | item | refusal of every action; `is_goal` | read |
| `flags.influences` | item | pool tags, tier context, kinds | read |
| `fractured` (canonical id, contribution) | fractured mods | every reroll keeps it; family leaves the pool | read |
| `status` (per leaf, BELOW/ABSENT/PASSING of the WHOLE item) | best of all mods | `is_goal` only; the kernel of an erasing action rebuilds it from `fractured` + crafted slots (`_kernel.py:1155-1157`) | dead for non-goal states of reroll-only models (STATE-6) |
| `slots` (side, kind, contribution, crafted) | every non-fractured mod once ANY enabled action reads junk (`Kinds.tracked`, `_kinds.py:148`) | Annulment, bench legality, Augmentation/Regal pool weight | kept in every state, also where no applicable action reads it (STATE-4, STATE-5) |
| `implicits`, `quality`, `offer`, `imprints` | item | only when an enabled action reads/sets them | fine (empty otherwise) |
| `memory_strands`, `sockets`, `enchantment` | item | NOT in the state (`compress` drops strands and sockets silently) | STATE-7 |

---

### STATE-1: a mod that has no tier in the table is read as TIER 1 by the kernel, and the item type forces it   [CONFIRMED] [impact: high]
- Where: `abstraction/_kernel.py:909` (`_drawn_contribution`: `tiers.get(mod.id, 1)`), `:924` (`_law`), `:1071`, `:1088`, `:1097`, `:1104` (`_item_of`), `:1528` (`_canonical_of_mod`);
  the constants `actions/bench.py:57`, `actions/beasts.py:59`, `targets/floor.py:57` (`CRAFTED_TIER = 1`, `BENCH_TIER = 1`); the reason they exist is `items/model.py:213` (`tier < 1` is refused, so a mod with no tier has no representation).
  The state reads it in `abstraction/_state.py:269-` (`status_of`: `leaf.min_tier is not None and tier > leaf.min_tier`).
- What it does: `items/tiers.py:tier_table` ranks only mods with a positive spawn weight on the base. Every other mod a kernel can put on an item (bench crafts,
  essence-only mods, beast aspects, Elevated mods, veiled placeholders) is missing from the table and gets tier 1. The kernel ignores the `tier` the action wrote on the new mod
  (`_split`, `else` branch: `_drawn_contribution(mod, entry.crafted, influences)`), so fixing only `CRAFTED_TIER` in `bench.py` would change nothing in the planner; `compress` of a concrete item reads `entry.tier` instead.
- What it should do: a forced or crafted mod is "exactly that mod/tier" (owner rule); a tier compared with `min_tier` must be a ladder fact (or the comparison must refuse/score such a mod BELOW unless the leaf names that mod). The glossary says tier = "one level-gated version of a mod within its family".
- Evidence (real data, quick snippets):
  - Lion Pelt (helmet) ilvl 84, goal `IncreasedLife min_tier=1`, no other actions enabled: the kernel of every Greed essence gives the Life leaf PASSING with chance 1.0, for all five tiers:
    Whispering (forces `IncreasedLifeEssence1_`, +5-14 life, ladder-equivalent T9-T10) ... Deafening (`IncreasedLifeEssenceBootsGloves1`, +91-105, ladder T3-T4; helmet T1 is `IncreasedLife9`, +130-144). Output: `P(Life T1 leaf PASSING)= 1.0` x5.
  - Leather Belt ilvl 86, goal `IncreasedLife min_tier=1`: a bench `HelenaMasterIncreasedLife1` (+15-25 life) and `EinharMasterIncreasedLife2` (+26-40) both give `['PASSING']` (belt ladder: +25-39 is T8). `'EinharMasterIncreasedLife2' in tier_table(belt)` is False.
  - Size of the class: 1,432 of the 2,309 (item class, forced mod) pairs of the essence table have no tier in the table of the class's first base; 1,637 mods of domain `crafted`, none with a table tier on the Lion Pelt.
  - `mods_for_family` (targets/resolve.py:103) puts crafted and essence-only mods into the leaf's `mod_ids`, so these mods can pass a tiered leaf.
- Impact: every route whose target has a `min_tier` leaf on a family that a bench craft or an essence can supply. Known: R05 (the seed). Newly found: essences (R10, R11, R04, R14 targets all have Life/Defences `min_tier: 1`; R10/R11 comment "rolled by the essence reforge" but only `not_crafted` is checkable, see STATE-10).
  I did not solve these routes, so the effect on a given route price is not measured. Elevated mods counted as T1 is the one reading that happens to be defensible (an upgrade of T1).
- Origin: `55f8109` (#24, 2026-10-30, the first compressed state, "R12 actions"): `self._tiers.get(mod.id, 1)` was written when no crafted or forced mod existed yet. #56 (`d1e63ed`) added `CRAFTED_TIER = 1` "crafted mods have no tier in the data (they never spawn); `Item` needs one, from 1".
  #59 (`98891b3`) widened the state to crafted slots and essences and kept the default. None of the tickets (#24, #55, #56, #59) says what tier a forced or crafted mod has.
- Pattern: a type placeholder (a tier is an int >= 1) read as game meaning; the same default copied by hand into 4 constants, 7 kernel lines and 11 test files.

### STATE-2: layer-1 oracles are built from the code under test, so a shared mistake passes (and the tier default is copied into them)   [CONFIRMED] [impact: high]
- Where: `tests/abstraction_oracle.py:78,142,148`, `abstraction_adds_oracle.py:36`, `abstraction_b2_support.py:44`, `abstraction_metamod_oracle.py:121`, `abstraction_removals_support.py:119`,
  `abstraction_veiled_support.py:74`, `abstraction_rolls_oracle.py:82`, `abstraction_pool.py:49`, `contract_support.py:197,317`.
- What it does: the brute force lists the finished items of an action with its own re-written rules, then compares `kernel(compress(start))` with `{compress(item): chance}`. Everything it needs comes from the code under test or from the same default:
  1. every oracle ends in `ab.compress(...)` (the code under test): `status_of`, the canonical ids, the kinds are on both sides, so a wrong `status_of` or a wrong merge cannot differ;
  2. the pool is `actions.build_pool` in all of them (module docstrings say so: "the one thing it takes from `actions` is `build_pool`"); weights, levels, tags, generation weights are never independently checked;
  3. the tier of a drawn or forced mod is `tier_table(...).get(mod_id, 1)` (the kernel's default, STATE-1); `abstraction_pool.roll()` documents it: "(1 for a mod that cannot spawn)"; `abstraction_oracle.crafted_item` (line 148) builds a crafted mod with tier 1 by hand, so the oracle PINS the placeholder: kernel and oracle can only move together;
  4. `abstraction_b2_support.finished_at_tiers` and `contract_support.finished` list the finished items from `action.outcomes` itself (and `tiers_of` from `actions`), so layer 1 for the B2 actions proves only that the kernel marshals the action's own outcomes, not that those outcomes are the game's;
  5. `contract_support._roll_in` (line 317) always uses the AMULET tier table "only amulets are drawn onto in the brute force below".
- What it should do (ADR-0019 layer 1): the oracle for tiers and pools should come from something written independently of the kernel (a hand-written ladder for the small pool; the game data ranks for the real pool), and `compress` should be pinned by hand-written states.
- Evidence: grep above; the `fixture` pool even sets the expected tier by `TIERS.get(mod_id, 1)`. What layer 1 DOES cover (checked): `closure` + `check_layer_1` run `kernel(compress(item))` against the pushforward for every concrete item the closure reaches, so lumpability of `compress` is tested on those items (not only on hand-picked starts).
- Impact: explains why ~30,000 green tests did not see STATE-1; any future fix of the tier reading will fail these oracles first and need them edited.
- Origin: ADR-0019 (#4 Q19): "the compressed kernel equals full enumeration on concrete items"; oracles written in #24 / #59 / #65 / #69 / #149, each reusing `tier_table(...).get(.,1)` and `compress`.
- Pattern: an oracle that shares code (and defaults) with the code under test.

### STATE-3: the concrete item's own `tier` is trusted by `compress` and never reconciled with the tier table; `Item` checks no tier, no level, no spawnability   [CONFIRMED] [impact: medium]
- Where: `abstraction/_kernel.py:760-764` (`_contribution(entry)` reads `entry.tier`), `items/model.py:322-345` (`validate` has no tier check), `items/model.py:20-24` (docstring: "The `tier` of a mod is stored as given"), `targets/parse.py:1073-1077` (start-item `tier:` hand-written), `actions/pool.py:145-161` (`tiers_of`, a second copy of the formula of `items/tiers.py:_compute_tier_table`).
- What it does: two sources of one fact. A drawn mod gets its tier from the table (kernel), a concrete item's mod from the number someone wrote. Reproduced:
  `Item.build(... mods=(ExplicitMod('IncreasedLife0', 1, (3,)),))` (the lowest life mod, table tier 10): `compress(...).status` = PASSING for `min_tier: 1`; with `tier=10` it is BELOW. `Item.build` also accepts item level 10 holding `IncreasedLife9` (required level 64) and `Strength1` (spawn weight 0 on a Dex helmet).
- What it should do: derive the tier from the table when a mod is read from a start item (or refuse a written tier that is not the table's), per the owner rule "a bought start item's mod is the tier priced on the trade site", which is a table lookup, not a free number.
- Impact: every hand-written start item (R10, R11, R04, R14 start items carry a written `tier`; "checked by hand" in the R10 comment) and every item built by tests. Not triggered by the current examples (their tiers were checked by hand), but nothing protects the next one.
- Origin: `5245f08` (#18, the concrete item model): "Not enforced here, because they are rules of `actions` or open questions: a mod's required level against the item level, whether a mod can spawn on the base's tags" (documented as deliberate). No later ticket added the check at the seam where a start item enters.
- Pattern: one fact in two places (item field / table), nothing reconciling them.

### STATE-4: 89% of V01's states are dead ends in which no enabled action applies; they differ in three junk slots and a status vector that nothing reads   [CONFIRMED] [impact: medium]
- Where: `abstraction/_kinds.py:148` (`self.tracked = metamods or any(reads_junk)`: one global switch), `_kernel.py:1454-1466` (`_add_drawn` carries every slot to the next state), `_state.py:CompressedState` (no notion of "live").
- What it does: V01 (4 magic-item orbs, recipe-made start): the walk from the start reaches 786 states; in 697 of them (all rare items) Transmutation, Alteration, Augmentation and Regal are all refused, so the only thing left is the planner's `restart`.
  Those 697 hold 9 goal states and 688 non-goal ones, and differ in rarity-3 + 3 junk slots (`~n` kinds) and status; as futures they are two classes (goal / not goal). Merging them exactly: 786 -> 91 states (89 live + 2).
  (From the plain Normal start: 787 states, same 697.) This is the policy page's long tail S10... of "restart".
- What it should do (owner rule: "detail no later decision sees is not tracked at all"): a state in which no enabled action applies reads nothing; it should be one of two states (goal / dead). Same for goal states (absorbing; R12: 16 of its 33 states are goals, R13: 6, V01: 9).
- Evidence: `ab.reachable([start], acts)` = 786; `kernel` raises `ActionError` for all four actions in 697 of them; distinct `(is_goal, flags)` among them = 2.
- Impact: V01 page and any magic-item-only or rarity-gated action set (R13 has none dead: bench crafts apply to every rare, 0 of 4,066). Size, not wrong numbers.
- Origin: ADR-0009 "Widening for the magic-item orbs" (#65): "the junk is read ... kept as slots" once an adding action is enabled; no step ever asks whether any action can still read them.
- Pattern: state written from what the item shows, not from what a later action reads (no liveness).

### STATE-5: the eight "Regal Orb" states of V01 are the family type of an Augmentation's junk suffix; exact by design, approximate if merged, and no mechanism offers or marks the merge   [CONFIRMED] [impact: medium]
- Where: `_kinds.py:Kinds.of / _type_kinds / _shape` (family type = side + sorted (what each mod gives the goal, weight)); `_kernel.py:_add_drawn`; ADR-0009 "magic-item orbs".
- What it does: after the Augmentation (V01 start = recipe helmet with the Minion mod) the kernel has 8 successors, the slots `(prefix ~0 [wanted mod], suffix ~k)` with `~k` in `{~7,...,~14}` and identical status `[2,0]`. The Regal's kernel DOES read `~k` (the junk family leaves the pool), chance of the goal after the Regal per state:
  `~14 0.009488, ~13 0.009398, ~12 0.009225, ~8 0.009107, ~11 0.009058, ~10 0.008977, ~7 0.008857, ~9 0.008842` (a 7% relative spread); all eight choose "Regal Orb", all eight then fall into dead states.
- What the owner wants vs what is exact: if the junk suffix is told apart only by side (and what it gives the goal), V01 has 31 states instead of 787 (and R13: 601 of 4,066; 280 if no junk slot at all, which also drops the pool weight). That merge is not exact (up to 7% on one step) and nothing in the system offers it as an approximation with a stated guarantee; the exact merge (lumpability, #312) finds R13 4,066 -> 79 only after the whole graph is built.
- Evidence: snippet `v01.py` (outputs above). #312 note: "S02 106,002 -> 20" shows that most of the junk detail is exactly redundant, but only post hoc.
- Impact: V01 page (eight identical steps), every route with Augmentation/Regal/Exalted (R13, R08, R04, R14). Not a wrong answer; a state the owner reads as noise.
- Origin: ADR-0009 (#65): "Two junk families of one type leave the same pool, so the states merge exactly" (true) - the choice "exact, therefore tracked" was never confronted with "a crafter would not track it".
- Pattern: exactness taken as the only licence to merge; no marked, guaranteed approximate merge for detail whose effect is small.

### STATE-6: the status of the mods that the next reroll erases is kept in every non-goal state of reroll-only models   [CONFIRMED] [impact: medium]
- Where: `_kernel.py:426-428` (`status = best_of(... item.mods)`: all mods) against `:1155-1157` (`_prepare`: an erasing action sees only `fractured` and the crafted slots).
- What it does: for R12, R11, R10 the future of a state depends only on `(flags, fractured, crafted slots)` and on whether it is a goal; the per-leaf BELOW/ABSENT/PASSING of the unfractured mods is never read except by `is_goal`.
  Measured on the real routes (walk of the reachable states with the plan's own actions):
  R12 amulet 33 states -> 2 distinct `(flags, fractured, is_goal)`; R11 helmet 18 -> 2; R10 boots 425 -> 2 (3 with crafted slots). These equal the exact class counts of #312 (3, 2, 3). Goal states are 16 of 33 (R12), 19 of 425 (R10).
- What it should do: store `status` only for the part a later action can keep (fractured/crafted + goal flag), or state that the extra detail is intentional.
- Evidence: `fields.py` output: `key=(flags,fractured,is_goal): 2` for R12, R11; `2` for R10; `distinct full` = 33, 18, 425.
- Impact: route pages of R10/R11/R12 list S1...S33/S425 where 2-3 states exist; the packed solver and risk loops pay for them. Not a wrong value.
- Origin: ADR-0009 (design D): "a state is the fractured mods, the flags and the status of each leaf" (the status was needed to recognise the goal; it was never narrowed when the action set made it unreadable).
- Pattern: same as STATE-4 (no liveness); state fields chosen once, never narrowed per action set.

### STATE-7: `compress` silently drops `memory_strands` and `sockets`; two items with 0 and 60 strands are one state, and the Chaos kernel ignores the cut   [CONFIRMED] [impact: medium, latent]
- Where: `abstraction/_state.py` (no field), `_kernel.py:395-444` (`compress`), `:1106-1119` (`_item_of` builds the item with no `memory_strands`, no `sockets`); guard only in `cli/_plan.py:286-292` (`make_plan` refuses strands) and `:300-310` (sockets).
- What it does: `ab.compress(item_0_strands) == ab.compress(item_60_strands)` is True and `ab.kernel(..., ChaosOrb())` is equal, while `ChaosOrb().outcomes` on the 60-strand item has a pool of 52 mods against 141. The ADR-0041 rule "an action that declared no strand use is refused on an item with strands" can never fire inside the kernel, because the rebuilt item has none.
- What it should do: ADR-0040 ("`s` is stored exactly in the compressed state"), ADR-0027 amendment ("the compressed state keeps it only when an enabled action reads it") and GLOSSARY.md "Cut class" ("the state stores the exact count") say the state keeps it. `compress` should at least raise `OutOfScopeError` for an item it cannot represent (as it does for metamods and a foreign enchantment).
- Evidence: snippet: belt with `memory_strands=0` vs `60`: `compress equal: True`, `chaos kernel same: True`, pool sizes `141 vs 52`.
- Impact: none today for `make_plan` (it refuses), but every other caller of `Abstraction` (benchmark, scripts, future B5 actions, the simulator cross-checks) silently gets the strand-free answer. `sockets` are the same by design (ADR-0045) but unguarded the same way.
- Origin: `748ab6c` (#274, B5-1, 2026-11-01) added `Item.memory_strands` and the planner refusal; the state side (B5 tickets #275 onward) is not built.
- Pattern: an item field dropped at the seam while the guard sits one layer up.

### STATE-8: `is_goal` is True for a corrupted item that holds the wrong (or no) corrupted implicit   [CONFIRMED] [impact: low]
- Where: `abstraction/_goal.py:160-163` (a corrupted implicit wish is left out of `Goal.implicits`), `_kernel.py:779-780` (`_implicit_pair` skips corrupted implicits), `is_goal` `:504-516`.
- What it does: target asks `implicits: - family: <AoE corrupted implicit> corrupted: true` plus a life mod; start item = corrupted, holds the Life mod and a DIFFERENT corrupted implicit (or none): `Target.is_met_by(item)` False, `Abstraction.is_goal(compress(item))` True (printed `False` / `True`; same with no implicit).
- What it should do (ADR-0036: "A corrupted item that is a start item is already final: goal or an impossible target"): decide it on the start item; the "a corrupting action decides" argument holds only for states reached through the action's kernel.
- Impact: a bought corrupted start item (buy specs have `corrupted: true`) with a wrong implicit would be planned as "already done, 0 chaos". Rare.
- Origin: `cffea8a` (#258, B4 C4).
- Pattern: a requirement dropped from the goal because "another layer decides it", with no check where the state arises another way.

### STATE-9: the default `Action.reads` ("reads everything") does not cover the tier or values of a held mod   [SUSPECTED] [impact: low]
- Where: `actions/contract.py:634-638` (`Action.reads` default: `families=None`, `by_mod` empty, `rerolls_values` False), `abstraction/_kinds.py:200-223` (`Kinds.of`: kind = family key, not mod), `:243-280` (`representative`: any mod of the family, first in data order), `_kernel.py:1084-1105` (the item given to the action holds the representative at the TABLE tier and LOW values).
- What it does: ADR-0027 and the `Reads` docstring promise "a new action stays correct by default". An action that undeclared depends on which mod of a family is held (its tier, a roll) gets a representative, not the real mod; no refusal. Only goal-driven `$id` kinds (`rerolls_values`, `influenced`, `by_mod`) tell mods apart. There is no such action in the tree today (`grep "\.tier" actions/` hits only a key in `recombinator.py:251`), so this is a trap, not a measured fault. The Orb of Unravelling (ADR-0044, unbuilt) is the first reader.
- What it should do: either `Action.reads` default sets `by_mod`-everything (exact, large) or the contract suite refuses an action whose outcome changes when a held mod is swapped for another of its family.
- Origin: #142 / #149 declarations; `by_mod` added in #149.
- Pattern: a default that claims safety it does not give.

### STATE-10: the item model has no mod origin and no mirrored/unique/synthesised/split flag, but the glossary says it has origin   [CONFIRMED] [impact: low]
- Where: `items/model.py:ExplicitMod` (only `fractured`, `crafted`), `GLOSSARY.md:8` ("every mod with its tier, roll and origin"), five docstrings: `actions/awakener.py:23`, `corruption.py:32`, `divine.py:12`, `enchant.py:32`, `fracture.py:4` ("the item model holds neither").
- What it does: a mod forced by an essence, drawn by a reforge, bought, bench-crafted: only "crafted" is recorded. The owner's targets say "Life, the top tier, rolled by the essence reforge, not crafted"; only `not_crafted` is enforceable, so an essence-forced Life (STATE-1) qualifies as "rolled". The trade query sets `misc_filters.mirrored` explicitly (`prices/trade_query.py:29`), so the buy side is covered; a hand-written start item cannot say it is mirrored.
- What it should do: store the origin (rolled / forced / crafted / bought) or drop it from the glossary; the target rule "rolled" needs it.
- Origin: GLOSSARY written at #4; the model (`5245f08`, #18) never had it.
- Pattern: a documented concept the type cannot hold.

### STATE-11: `Item.canonical` and `veiled_placeholder` state that "the seed changes nothing in the game", while the claim of record says it is unknown   [CONFIRMED] [impact: low]
- Where: `items/model.py:16-17, 163-172, 304-309`; claim `unveil.offer_drawn_once_and_fixed` (`rules/claims/unveil.yaml:51`): "the per-placeholder veiled_mod_seed of the export may fix it for good"; ADR-0026 line 20.
- What it does: every veiled seed is set to its minimum, so two placeholders (two different offers in the game, if the seed decides the offer) are one item/state. The claim is `approximate` only for "a block after the peek redraws"; the docstring asserts the stronger "changes nothing", and the placeholder also gets tier 1 ("a veiled mod has no spawn weight so no derived tier").
- Impact: low (only placeholders of start items; the planner draws its own offers).
- Pattern: a model decision written as a game fact in a docstring while the claim registry holds it open.

### STATE-12: fixed state-count limits decide the size of the pilot count   [SUSPECTED] [impact: low]
- Where: `abstraction/_estimate.py:49-51` (`DEFAULT_LIMIT = 400_000`, `ADDING_LIMIT = 20_000`, `VARIANT_FACTOR = 2`), used in `cli/_decide.py:261`; `_prime.py:20` (`MIN_JOBS = 2`).
- What it does: the pilot count stops at 20,000 states when a walked action (Augmentation, Regal, Annulment...) is enabled; beyond it the plan may be refused or answered at a coarse level (ADR-0023, marked approximate), by a number nobody derived. Not a silent change of an answer (the answer is marked), but a fixed cut-off in the place the owner objects to ("no hard-coded cut-offs").
- Origin: ADR-0023, #118/#125.

### STATE-13: two definitions of "tier"   [CONFIRMED] [impact: low]
- Where: `GLOSSARY.md:23-24` ("within its family on a given item class") against `items/tiers.py:1-12` ("counted among the mods of one mod type (not one family)"; the five "+1 to Level of all X Skill Gems" amulet prefixes share one family and are each tier 1).
- What it does: the code is the one in force; a reader of the glossary expects tiers 1..5 for those prefixes. Also the algorithm is written twice (`items/tiers.py:_compute_tier_table` and `actions/pool.py:tiers_of`) with nothing that checks them equal when the influence set is empty beyond the early return.
- Pattern: one fact written by hand in two places.

---

## Where two situations collapse into one state, or one into many (answer to the area question)

Collapse (one state for two situations):
- 0 vs 60 Memory Strands; any socket layout (STATE-7).
- A corrupted item with the wanted, a wrong, or no corrupted implicit (STATE-8).
- A bench-crafted / essence-forced mod and a rolled top-tier mod, for any tiered leaf (STATE-1, STATE-10).
- Two veiled placeholders with different seeds (STATE-11).
- Mods of one family on a slot of kind `""`/`~n`/family key when an undeclared action reads their tier or values (STATE-9).
- Fractured mods with the same families/side/domain/contribution are one canonical id (intended; exact while no action reads their tier; `by_mod`/`fractures` handle the exceptions).
Split (one situation, many states):
- Dead-end items (STATE-4), the status of erased mods (STATE-6), the family type of a junk suffix (STATE-5), absorbing goal states (R12: 16 of 33).
- BELOW vs ABSENT does not split anything extra in V01, R12 or R13 (checked: the counts stay 787, 33, 4,066 when BELOW is set equal to ABSENT).

Not reproduced (checked and dropped): a single hybrid Life+Mana mod satisfying "at least 2 of {Life, Mana}" - the stat text `+# to maximum Life` does not match the two-line hybrid, goal and target agree (`False`/`False`).

## Patterns seen in this area

1. **A type placeholder read as game meaning** (a tier must be an int >= 1, so "no tier" became 1; a veiled seed set to its minimum; a veiled placeholder tier 1): STATE-1, STATE-11, STATE-10.
2. **One fact in many hand-written copies with nothing reconciling them** (tier: the item field, `tier_table`, `tiers_of`, four `CRAFTED_TIER`/`BENCH_TIER` constants, seven kernel lines, eleven oracle copies; tier defined two ways in glossary and code): STATE-1, STATE-2, STATE-3, STATE-13.
3. **An oracle built from the code under test** (`compress`, `build_pool`, `tier_table`, `action.outcomes`, the default tier): STATE-2.
4. **State written from what the item shows, not from what a later action reads** (no liveness, no per-action-set narrowing; exactness used as the only licence to merge, with no marked approximate merge): STATE-4, STATE-5, STATE-6.
5. **A field or a requirement dropped at a seam while the guard sits one layer up** (strands and sockets in `compress`; corrupted implicit in `Goal`): STATE-7, STATE-8.
6. **A default that claims safety it does not give** ("reads everything" does not include which mod of a family is held): STATE-9.
7. **Fixed budget numbers in the place that picks exact vs approximate**: STATE-12.
