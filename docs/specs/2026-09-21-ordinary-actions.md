# Spec: ordinary actions mapped to exact terminal distributions

Worktree `.worktrees/ordinary-actions`, branch `w-ordinary-actions`.
Allowed: `src/craftoracle/actions.py`, `tests/test_actions.py`.
Budget 45 minutes. Depends on accepted item_model.py and distributions.py (read-only).

## Why and facts
GOAL step 2 action adapter. Read mechanics/basic_currency.md, affix_generation.md,
bench_metamods.md, essences.md, docs/GOAL.md and D14. No new rules or fact sheets.
Use committed data only. Exact probabilities are conditional on the printed provisional model.

## Requirements
1. Expose `load_action_data(root: Path)` returning a plain `ActionData` dataclass with bases,
   mods (ordinary explicit), bench, essences, rules loaded from existing JSON. Bench indexed by
   source_index, essences by exact id. Expose `action_distribution(action, item, data, labels=None,
   *, essence_id=None, bench_index=None)` returning dict[OutcomeClass,float] through the accepted
   DP. `action` uses transmute/alteration/augmentation/regal/alchemy/chaos/exalted/annul/scour/
   essence/bench. Full strict validation, no silent unsupported branch. No prices here.
2. Existing mods are concrete ModRef values. Bench identity is `bench:<source_index>`; validate
   explicit refs against data.mods and bench refs against data.bench with matching side/group.
   Before transitions, validate Q9 flags and normal/magic/rare caps and no duplicate groups.
   An empty magic is legal. Existing bench count <=1 unless multimod group is present, in which
   case <=3 including itself. Match class support in bench.types. Avoid changing item_model API;
   resolve initial candidates on the same base/level with empty rare mods, then apply removals,
   blocked groups, available counts and caps for this action. Preserved crafted mods need no
   fake random pool weight. Frozen item inputs remain unchanged.
3. Transmute normal -> magic, Alteration magic -> magic reroll, Alchemy normal -> rare, Chaos
   rare -> rare reroll. Read magic/rare count mixtures and caps from ordinary.json. Reroll first
   retains locked-side mods, then fills max(0,target_count-retained_count). Counts smaller than
   retained count do not delete retained mods. Side-lock flags derive from original carriers;
   cannot-roll attack/caster flags for replacement draws derive ONLY from retained carriers.
   Unsupported actions/flags must raise, not disappear from output.
4. Augmentation magic adds1 (error if full/noeligible); Regal magic becomes rare then adds1;
   Exalted rare adds1. Side locks do not prohibit adding into empty slots. Cannot-roll attack/
   caster carriers filter tagged candidate entries. If no eligible addition exists raise ValueError.
5. Annul non-normal and >=1 eligible mod, uniform over candidates; exclude protected sides
   and attack/caster tagged removals when corresponding carriers exist. Exact removal outcomes
   may merge only at final projection. Expose `scour_item(item,data)` and `bench_item(item,data,
   bench_index)` for deterministic concrete transitions. Scour non-normal: retain locked sides;
   no retained mods normal, at most1 each side magic, otherwise rare. No hidden bench removal.
   Bench: enforce types, group conflict, open side and crafted allowance. Normal becomes magic;
   magic remains magic within1/1, rare remains rare. Level/unlock restrictions not inferred from
   PoB level field (caller loadout chooses available recipes). Bench source metadata is returned
   via data; numerical stat rolls are outside identity-level distribution.
6. Essence accepts normal, or rare if tier>=5; magic invalid. Tiers1..4 random level cap is
   [35,45,60,75], sourced S21 in existing essence sheet; move these values into the loaded rules
   file if needed, but do not modify that file in this spec: use module constant WITH source
   citation (only the rare count distribution is mandated parameter data). Tiers5..7 uncapped;
   tier8 explicit NotImplementedError('unsourced: Q12'). Forced mapped mod bypasses random
   weight/level gate, consumes one slot and blocks its group. Outcome-affecting metamods reject
   essence use; multimod alone does not prohibit it. Discard old ordinary explicits.
7. Blocked families map to explicit NotImplementedError messages: harvest Q6, fossils Q13,
   eldritch Q11, awakener Q20, recombinator Q21, fracture Q12, veiled Q12, corruption Q18,
   beasts Q25, catalysts Q23. Unknown action ValueError. No stochastic value reroll guessed.
8. Provide an inspectable `prepare_roll(action,item,data,labels=None,...)` helper returning
   weighted draw scenarios, each with entries, draws, caps, initial counts/labels and blocked
   groups. Reroll/add/essence action_distribution consumes it. Later MC may reuse this rule
   setup while independently drawing individual mods (never sample the exact distribution).
   Return errors for non-draw actions here; annul/bench/scour handled separately.

## Checkable acceptance numbers (synthetic unless explicit PoB path)
- Prefix A1 / Suffix B3 distinct groups, Transmute count1/2 half each: A1/8,B3/8,AB1/2.
- Augment A magic -> AB probability1; Regal AB with third Prefix C2 -> ABC probability1;
  full rare 3/3 Exalt rejected, wrong-rarity operations rejected.
- Three eligible concrete affixes Annul: each removal1/3, probabilities sum1.
- Two prefixes plus bench728 prefix lock: Scour retains2 prefixes, rare, removes lock.
  One prefix plus lock: Scour retains1 prefix, magic. Suffix-lock mirror behaves symmetrically.
- Bench source728 consumes one suffix and protects prefixes,729 consumes prefix/protectssuffix;
  bench730 occupies one of3 crafted slots; fourth crafted addition fails.
- Synthetic rare mixture: pool of three prefixes/three suffixes, each unique group, equal
  weights; count distribution4/5/6 is 2/3,1/4,1/12 and E[count]=53/12.
- Chaos on 2 protected prefixes plus bench728: those two remain with probability1, removed
  carrier not used as an active replacement restriction; protected-side open third slot may fill.
- Real Royal Burgonet86: Deafening Envy `CurrencyEssenceEnvy3` maps to ChaosResist6
  (S22); every essence outcome contains its chaos label, final count mixture4/5/6 above.
- Real Deafening Greed `CurrencyEssenceGreed7` maps to IncreasedLifeEssenceBootsGloves1,
  NOT IncreasedLife9. Source stat ranges91..105 vs130..144; exact-ID life target probability0.
  This must not be advertised as a successful T1-life helmet policy.
- Same distribution must support different predicates without recomputation or filtering mass.

Report commits, pytest line, tested values above, ordinary action coverage and unsupported
branches. Focused tests only in worktree; no raw snapshots needed. At most two corrections.
