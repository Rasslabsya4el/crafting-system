# Spec: ordinary tagged Harvest outcome distributions and seeded transitions

Worktree: `.worktrees/harvest-distributions` (branch `w-harvest-distributions`).
You may touch ONLY `src/craftoracle/harvest.py`, `src/craftoracle/actions.py`,
`tests/test_harvest.py`, `data/rules/harvest.json`.

## Why
Owner answers 1-3 unblock ordinary tagged reforges. Implement the lead's rule and distribution
contract so a later policy can correctly price failed full-prefix reforges.

## Requirements
1. Read `docs/mechanics/harvest.md`, especially Accepted ordinary reforge model and hand examples.
   Implement `harvest_distribution(item,data,tag,labels=None,*,type_filter="first_only")`
   and `apply_harvest(item,data,tag,rng,*,type_filter="first_only") -> ItemState` in harvest.py.
   Add action_distribution dispatch `harvest_reforge`, keyword `harvest_tag`, and optional
   `harvest_type_filter="first_only"`. Use a local import if needed to avoid an import cycle.
   Existing prepare_roll need not represent a two-phase forced draw; do not distort RollScenario.
2. Rare ordinary items only; reuse action validation (special Q9 states still rejected).
   Preserve side-protected affixes, count occupied slots and groups, select one tagged mod
   with original attack/caster flags, then ordinary draws to chosen 4/5/6 total. First-only
   disables type filtering on later draws; explicitly named all_draws is a sensitivity mode.
   Never infer universal current validity from source table cells. Reject unknown tags/modes,
   empty tagged pool, no available slot, bad RNG, bad labels and invalid items explicitly.
3. Supported tags: fire,cold,lightning,physical,life,defence,chaos,attack,caster,speed,critical,
   minion,elemental,attribute,mana (S42 and owner row3). Match literal PoB modTags, except the
   public spelling `defence` maps explicitly to PoB `defences` (ModExplicit.lua:115+,
   IncreasedEnergyShield1..8). Test a real defence draw has eligible mods. Do not synthesize
   tags. Store the mapping, tags, model selection and source/confidence metadata in harvest.json.
4. Exact terminal OutcomeClass distribution retains group identity internally across the
   forced and ordinary draws. May enumerate each forced mod and call accepted draw_distribution
   for the rest; share equivalent computations where needed. Never continue an ordinary
   transition from a projected junk class. Preserve original item; correct rare output.
5. The sampler makes independent weighted draws using explicit random.Random and individual
   eligible entries; no sampling from the exact terminal distribution. Include count selection,
   forced group exclusion, retained identity and updated flags, using the same declared model.
6. Keep existing ordinary tests green. Run `python -m pytest -q tests/test_harvest.py tests/test_actions.py`.
   Fixtures should not repeatedly enumerate expensive full real rerolls: one protected helmet
   distribution and a seeded MC comparison suffice; synthetic cases cover the mechanics.

## Facts this implements
`docs/mechanics/harvest.md`: S19 official3.27 type restriction change, S14 first-added-only
note, S42 current recipes, owner rows1-4. PoB weights/groups and D14 unbiased draws.
No policy implementation, prices, loadouts or source interpretation belongs to this worker.

## Numbers a test must reproduce
All synthetic fixture definitions are in the named sheet. Count4: A/B=1/4,3/4; count5:
AX,AY,BX,BY=1/8,1/8,3/8,3/8; mixed counts: prefixes1/2/3=2/3,1/4,1/12 and P(A)=1/4.
Attack fixture: first-only BA/BX/BY=1/5,2/5,2/5; all_draws BY=1. Three retained suffixes
including no-attack+multimod, original bench729 prefix: this is a legal three-bench input.
Royal Burgonet86 life prefix pool13000, forced Life9 chance1/13. Its final chance includes
possible Life9 after a hybrid forced mod; compute and report final chance, no guessed target.
Exact mass1 within1e-10. Seed20260921, N10000 real protected-helmet samples: target Life9
frequency agrees with exact within Hoeffding two-sided delta=0.001 bound
sqrt(log(2/0.001)/(2*N)); all original three suffixes survive every sample.

## Numbers to report
Synthetic probabilities above, real pool weight and final Life9 probability, number of real
terminal classes, MC successes/N and bound, preserved-suffix violations (0), test summary,
commits/files. Final message starts `=== FINAL REPORT ===`.
