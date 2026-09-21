# Spec: legal protected-suffix Harvest helmet policy and loadout

Worktree: `.worktrees/harvest-helmet-policy` (branch `w-harvest-helmet-policy`).
You may touch ONLY `src/craftoracle/harvest_policies.py`, `src/craftoracle/policies.py`,
`src/craftoracle/plan_inputs.py`, `data/prices.example.json`, `data/loadouts/endgame.json`,
`tests/test_harvest_policies.py`, `tests/test_plan_inputs.py`, `tests/test_plan_cli.py`,
`tests/test_policies.py` (lead-authorized correction and existing policy regression tests).
Dependency: accepted harvest.py/action adapter must be present before this worker starts.

## Why
Owner row1 and GOAL2 require the protect-half + tagged-reforge route in the helmet plan.
Charge restarts when a failed reforge fills all prefixes; do not invent a free prefix slot.

## Requirements
1. Add explicit allowed action keys `harvest_reforge:<tag>` for the fifteen tags in
   data/rules/harvest.json to the input validator; prices never grant permission. Endgame
   permits all fifteen. D21 prices:11 classic tags cost1 each; extra minion/elemental/attribute/
   mana cost100 each, same as `harvest_add_remove_sacred` placeholder100. Disclose invented
   prices and owner-provisional extra-tag equality in note/sources and policy assumptions.
   Existing loadouts remain valid, no required new schema fields.
2. Add `suffix-protected-harvest-life` policy through evaluate_policies. It applies to the
   existing exact helmet target and ordinary state guards, bench729 and Envy permissions.
   Stage1 is the existing Envy preparation event (desired chaos/elemental targets, three
   suffixes, <=2 prefixes). It deliberately defers success testing until the Harvest stage
   for this baseline; a later parameter optimizer can change that acceptance rule.
3. Use the accepted exact Harvest distribution on three concrete ordinary suffixes and
   bench729. Full-suffix + disjoint prefix/suffix groups makes prefix transitions independent
   of which third suffix was prepared. Check this guard; representative suffixes must not
   invent group identities. Evaluate prefixes only and combine with every prepared suffix
   label class. Keep one stage distribution and a terminal distribution conditional on success.
4. Let p=Life9 final chance; b=failed results with three prefixes; r=1-p-b. On a nonfull
   failure, lock suffixes and reforge again. On full-prefix failure, Envy resets the SAME
   base and repeat preparation. Charge every craft. Base cost is charged only once.
   A=essence_price/preparation_p, c=bench729+harvest_reforge:life. Exact mean is
   base_cost + A + (c+b*A)/p. Expected reforge attempts1/p; preparations1+b/p;
   total essence attempts=(1+b/p)/preparation_p. Print these decisions and full-failure
   probability. Item destruction risk0 is distinct from losing the prepared suffixes.
5. Estimate cost p90 with explicitly seeded independent NumPy draws: K~Geom(p),
   R~Binomial(K-1,b/(1-p)), J~NegBinomial(R+1,preparation_p)+(R+1).
   Cost=base+K*c+J*essence_price. For p=1 use R=0. This exactly samples the renewal cost
   law (not its mean times a multiplier). N50000, seed20260921, DKW99% quantile interval,
   method/seed/N/interval in output, matching existing p90 metadata conventions. Validate
   inputs and finite results; no unbounded loops. Keep mean exact and distinguish p90
   estimation uncertainty from a percentile of the underlying total cost.
6. Source assumptions: S14 first-only type filtering, S19 type restriction support, owner
   rows1-4; current policy has no attack/caster blocker but names the adopted Harvest model.
   No silent skipped candidates. If permissions/missing prices fail, report explicit reason.
7. Focused tests only; update old CLI policy-count assertions to check actual policy IDs
   and distributions, not an obsolete fixed count. Do not broaden or remove coverage.

## Facts this implements
docs/mechanics/harvest.md (accepted model and legal policy); D20/D21; ordinary benchmark
docs/design/night-policies.md. Reuse accepted scoring, source groups and method helpers.

## Numbers a test must reproduce
- Renewal synthetic: preparation_p=.5, essence_price5 => A10; p=.25,b=.25,c2 => mean28.
  p=.25,b0,c2 => mean18. Add base7 =>35/25. Total essence attempts4; reforge attempts4
  for the first case. p1,b0 => mean12 (base0).
- Source-protected helmet: preparation_p0.0556753020849824 (within1e-12); baseline old
  Exalt protected mean8357.19392785 remains present until the later optimizer change.
- New life route has p>1/13 (hybrid forced mod can subsequently roll Life9), b>0,
  mean below the old protected route for declared example prices. Do not assert it beats
  Envy spam without measuring. Report all measured quantities and best overall policy.
- Fixed seed repeats exact MC estimate. Synthetic simulated cost mean agrees with28
  within a statistically justified bound; p90 CDF checked independently by bounded direct
  convolution/enumeration on the small fixture. N and DKW interval explicit.
- Extra tags all permitted and each price100; ordinary life1; Sacred placeholder100;
  removing life permission or price makes this policy explicitly unavailable.

## Numbers to report
Focused pytest; synthetic means; helmet p,b,preparation_p,total expected essence/reforge
counts, exact mean, estimated p90+interval, best policy before/after; extra-tag prices.
Commit explicit files; final report begins `=== FINAL REPORT ===`.
