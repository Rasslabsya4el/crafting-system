# Spec: paid fracture-Life preparation and Envy finishing policy

Worktree: `.worktrees/fracture-essence-policy` (branch `w-fracture-essence-policy`).
May touch ONLY `src/craftoracle/fracture_policies.py`, `src/craftoracle/optimizer.py`,
`src/craftoracle/plan_inputs.py`, `data/loadouts/endgame.json`, `data/prices.example.json`,
`tests/test_fracture_policies.py`, `tests/test_plan_inputs.py`.
Dependencies: accepted fractured-item-actions, template optimizer and fossil policy
integration (shared files). Bounded60minutes; no independent source decisions.

## Why and source
GOAL2 owner row9 unblocks fracture-then-spam. Read docs/design/family-policies.md's fracture
section and mechanics/fracturing.md/essences.md. Fracture selection is explicitly CoE1/n,
eligibility is documented. Prices/salvage assumptions are caller inputs.

## Requirements
1. Add allowed action fracturing and invented example price fracturing=1000. Keep old
   loadout schema compatible. Require Alchemy, Scour, Fracturing and allowed Deafening Envy
   plus their prices. The selected first route only supports the exact ordinary Royal
   Burgonet86 helmet target with Life9/Chaos6/any elemental8; return explicit unavailable
   reason on other targets, including the utility bow. Do not guess tier mappings.
2. Compute actual Alchemy distribution. Preparation gate is exactly4 ordinary explicits
   with Life9. Optimize early completion false/true; if true, all already complete target
   outcomes go to u, and are excluded from v. Obtain f=1/4 by calling the accepted concrete
   fracture distribution on sourced Life9/Chaos6/Fire8/Cold8; validate eligible refs.
3. Obtain final Envy distribution from an accepted concrete Life9-only fractured rare
   state, retaining the fracture. Its identity-free scored outputs are terminal only.
   The reset effect makes other prepared identities immaterial; reference the design's
   reason. Use raw distribution caching by all resolved draw inputs, never data identity.
4. Implement exact mean/counts and seeded p90 law from the design, including every rejected
   Scour, replacement base, failed fracture and Envy attempt. N50000, seed20260921, DKW99%
   interval with metadata. Salvage0 explicit. Preserve wrong-fracture output state in the
   action API; the policy deliberately sets it aside and pays replacement. Cost no free undo.
5. Expose fracture-life-envy through optimize_policies with parameters, two-candidate audit,
   stage distributions, conditional final mixture/utility, readable gates/recovery/rare
   inputs and expected action counts. Report wrong-fracture risk per trial and expected
   discarded bases separately from item-destruction risk0. Default policy boundary is
   ilvl86; optional level search reports why other levels are outside this selected slice.
6. Independent hand cases and bounded exact p90 fixture, MC mean/CDF checks, seed stability,
   missing permission/price, no-target/unreachable and base-price scaling tests. Use one
   shared real fixture; no repeated expensive full plan grids in ordinary unit tests.
   Keep source/model confidence visible, especially uniform CoE selection.

## Numbers to reproduce/report
- u0,v.5,f.25,p.5,B3,A2,S1,F5,E4 ->mean60.
- u.1,v.4 otherwise same ->mean34; bases2.5, Alchemy5,Scour2.5,Fracturing2,Envy1.
- u0,v1,f.25,p1,B1,A1,S0,F2,E3 ->cost4Geom(.25)+3,mean19,p90 39.
- Early off has4 expected Fracturing and4 fresh bases; raising base price by7 raises
  its mean by28, not7. Early-on follows expected-base multiplier s/z.
- Lead independent DP/renewal reference at2f30602, default prices/base0:
  finishing p=.06101200110346221,30 terminal classes. Early-off v=.024298372342207553,
  mean4244.571170153949. Early-on u=.000024282088455126462,v=.02428733447648724,
  mean4227.736691448135; expected bases3.988050380133888,Alchemy164.0388811447735,
  Scour160.05083076463964,Fracturing3.9840671735118507,Envy16.324932396315752.
  Reproduce through your actual adapter/policy; these are checks, not implementation constants.
- Real selected u,v,f,p, mean,p90+interval, expected counts, candidate early-stop choice,
  terminal mass1; best helmet before/after at invented Fracturing1000; bow unavailable.
- Focused tests/commits/files; questions and limitations; report starts `=== FINAL REPORT ===`.
