# Spec: ordinary catalyst quality-state distributions and finite finishing policy

Worktree: `.worktrees/catalyst-quality-policy` (branch `w-catalyst-quality-policy`).
May touch ONLY `src/craftoracle/item_model.py`, `src/craftoracle/actions.py`,
`src/craftoracle/quality.py`, `src/craftoracle/cli.py`, `tests/test_quality.py`.
Dependency: fractured-item-actions and optimizer accepted first, so shared model/CLI files
have no concurrent writer. Bounded45minute task. No modifier-value evaluator or market data.

## Why
Owner14 is resolved by S74/S47. Provide a usable quality-finishing policy with exact
outcome/cost distributions; item metadata must survive ordinary crafting (S46 since3.15).
Read mechanics/quality_catalysts.md fully. All interpretation is already in that sheet.

## Requirements
1. Append quality:int=0 and catalyst_type:str|None=None to ItemState, retaining compatibility
   with existing positional arguments. Existing deterministic/state replacement helpers must
   preserve these fields; use dataclasses.replace where it removes manual field loss. No
   changes to ordinary generation weights (S46 explicitly removed catalyst weighting).
   Existing APIs treat this as metadata; do not invent magnitude rounding/PoB utility.
2. Add catalyst_distribution(item,data,catalyst_type)->dict[ItemState,float] and independent
   apply_catalyst(...,rng:random.Random). Validate source class Ring/Amulet/Belt, non-unique
   normal/magic/rare, ilvl positive, quality integer0..20, supported regular catalyst name
   and coherent existing type when quality>0. Only bases present in ActionData are supported.
   All Q9 special flags remain explicitly unsupported for this first family slice. Reject
   Tainted/Dextral/Sinistral rather than guessing their special eligibility/effect mapping.
   Ten regular names come from the fact sheet; store source pointers/confidence in module.
3. Implement S47 f(i), floor/ceil probabilities (integer f single outcome), cap20; different
   catalyst type first resets quality0. Preserve all affixes/rarity/identity. The distribution
   is over quality/type state, never collapsed to a modifier-only OutcomeClass.
4. Provide plan_catalyst(item,data,type,target_quality,unit_price) using a finite backward
   recurrence: terminal states require0 additional crafts; each increment moves quality
   upward, so at most20 paid applications. Return count distribution, final quality-state
   distribution, expected applications/cost, exact p90 applications/cost, ordered steps,
   source confidence and supplied-price disclaimer. Same type already at target needs0;
   a different requested type must reset and build it even if old quality met target.
   Target in1..20; invalid/nonfinite/negative prices reject. Zero price is valid.
5. Add a small `python -m craftoracle quality` CLI branch with --base, --item-level,
   --catalyst, --target-quality(default20), --price, --json; default starts quality0 ordinary
   rare jewellery. It prints the usable repeat-until-quality policy and exact distribution.
   No edits to plan input schema or general damage/utility integration. Existing helmet/bow
   planner behavior remains unchanged because quality was already a fixed supplied input.
6. Tests first: class/type/input gates, switching types, caps, same-type already complete,
   metadata preservation through a basic deterministic transition and seeded sampling;
   at least one CLI invocation. Run python -m pytest -q tests/test_quality.py. Use one
   independent10,000-sample bounded repeated-application check, seed20260921; report an
   error bound for a CDF event, not an arbitrary mean tolerance.

## Numbers a test must reproduce
S47/lead-derived sheet: ilvl1..11 gain20 certainly; ilvl95..100 gain1 certainly.
At86 f=1.4066471503830453, gain1 probability.5933528496169547,
gain2 probability.40664715038304533. From0 to20, expected14.423723570517014 applications,
p90=16; quality19->20 in1. At price2: mean28.847447141034028, p90cost32.
Same-type quality20 target20 ->0 costs; switching type at20 is equivalent to starting0.
Constant gain1 from18 to20 ->2 applications, final mass1. Mathematical gain2 from17 clipped
at20 needs2 applications. Source item/mod IDs do not change. Final quality never exceeds20.
CDF P(applications<=16) from exact count law must match independent MC within
sqrt(log(2000)/(2*10000))=.019494746035204052. Uniform unique+1 is documented in the sheet
but outside this non-unique API slice; no unsourced unique item-model extension.

## Numbers to report
Exact formula probabilities, real ilvl86 count mean/p90/costs and MC CDF/bound; deterministic
edge cases, CLI command/output, tests and commits/files. Final starts `=== FINAL REPORT ===`.
