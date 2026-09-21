# Spec: concrete ordinary fracture identity and retained-mod transitions

Worktree: `.worktrees/fractured-item-actions` (branch `w-fractured-item-actions`).
May touch ONLY `src/craftoracle/item_model.py`, `src/craftoracle/actions.py`,
`src/craftoracle/fracturing.py`, `src/craftoracle/divine.py`, `src/craftoracle/harvest.py`,
`src/craftoracle/fossils.py`, `tests/test_fracturing.py`, `tests/test_item_model.py`,
`tests/test_actions.py`, `tests/test_divine.py`.
Dependency: ordinary fossil adapter accepted first. This spec does not add CLI policies.

## Why
Owner9/S33 unblock an ordinary fracture-then-spam route. A boolean cannot retain the chosen
modifier. Implement its concrete identity and the sourced basic transitions before a policy.
Read mechanics/fracturing.md, basic_currency.md, affix_generation.md and essences.md fully.
Maximum60minutes, one worker, no source interpretation or unrelated state changes.

## Requirements
1. Append optional fractured_mod_id to ItemState, preserving positional existing arguments.
   It identifies exactly one existing ordinary ModRef when fractured=True. A true legacy
   flag without identity remains unsupported Q9; identity without flag, missing/duplicate
   identity or bench/veiled identity rejects explicitly. The first slice supports only
   ordinary non-corrupted/non-mirrored/non-influenced/non-synthesised/non-split inputs.
   Other special flags remain Q9, even when the broader fact sheet documents eligibility.
   Existing ModRef fields are unchanged. Validate at public action/pool boundaries.
2. fracture_distribution(item,data) -> dict[ItemState,float] validates rare, >=4 ordinary
   explicit mods and no existing fracture, then returns one outcome per chosen identity,
   probability1/n. apply_fracturing(item,data,rng) uses direct uniform random.Random index,
   preserves all other identity/rarity/mod fields and input immutability. No value reroll.
   Do not project this action through OutcomeClass, which would erase its essential new
   state property; expose the explicit state distribution as a family API.
3. Existing basic rerolls retain the identified fracture, count its occupied side/group and
   draw only the remaining slots to the normal count total. Chaos/Alteration and Scour
   retention uses the fracture in addition to existing side protection; Scour single retained
   affix becomes magic under the accepted source rule. Exalt/Augment/Regal may add legal
   nonconflicting mods. Annul never removes the fracture. Divine never rerolls its numeric
   values, preserving existing side-lock behavior. Existing known-answer tests stay green.
4. Essence on a legal rare fractured input retains fracture plus forced modifier. A forced
   group matching the fracture is rejected as a conflict, not duplicated or silently removed.
   S3 poec_simRerollItem2428-2433 retains fractures; essence branch prechecks fractured group
   conflicts (essences.md). Remaining draw count is total minus both retained affixes. No
   alteration to ordinary unfractured probabilities. Data-based pool resolution uses an empty
   internal ordinary item only after validating the real input; explicit group exclusion
   still includes the fracture, and state reconstruction must preserve its identity.
5. Until separately specified, Harvest/fossil family wrappers continue to reject fractured
   input explicitly: shared validation changes must not accidentally enable an adapter that
   fails to preserve it. No special-item path becomes enabled merely from a broader shared
   resolver. Planner ItemSpec flags remain unchanged; a later dedicated policy constructs
   its intermediate fractured states internally.
6. Tests first. Uniform4/6 outcomes, retained identity through real and tiny actions,
   count/cap/group gates, malformed identity, RNG validation, no forbidden fracture removal,
   conflicting essence and immutable source. One real seeded MC comparison N10000, seed
   20260921, Hoeffding delta.001 bound.019494746035204052; no costly full pool repetition.

## Facts and numbers
S33 documented Fracturing preconditions; S3 dispatch2280-2281 uniform1/n. S3 reroll2428-2433
retains fractures; basic_currency.md/affix_generation.md give counts and Annul/Divine/Scour
conditions. Confidence remains source-scoped, not universal datamined fracture odds.
Toy A/B/C/D ordinary mods ->4 fracture states each1/4; acceptable A orB ->1/2. Six mods,
one desired ->1/6. Already fractured input cannot fracture again. Annul with one fracture
and3 otherwise eligible mods ->1/3 each, fracture removal0. Scour ->one unchanged fracture.
Toy fixed rare count4 with retained fracture+forced essence produces2 additional draws,
not3 or4. Empty group-conflict candidate pool must fail explicitly.
Real Royal Burgonet86 input IncreasedLife9/ChaosResist6/FireResist8/ColdResist8: four
outcomes each1/4; desired fracture IncreasedLife9. On that successful outcome, Envy3
retains Life9 and forces Chaos6; compute final exact target probability for any T1 elemental
resistance and compare direct seeded draws to it. No guessed probability is supplied.
Life9 numerical value132 remains132 under a Divine of the fractured item while another
supported integer-range affix rerolls over its existing accepted range.

## Numbers to report
All synthetic probabilities/counts; real fracture p1/4 and Envy-finish chance/classes,
MC successes/bound, fracture identity/value loss0; tests, commits/files, explicit unsupported
paths. Final report begins `=== FINAL REPORT ===`.
