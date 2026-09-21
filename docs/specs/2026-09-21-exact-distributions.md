# Spec: exact grouped draw distributions

Worktree `.worktrees/exact-distributions`, branch `w-exact-distributions`.
Allowed files: `src/craftoracle/distributions.py`, `tests/test_distributions.py`,
`data/rules/ordinary.json`. Budget 45 minutes. No network or raw source parsing.

## Why / scope
GOAL step 2 needs exact, useful terminal outcome distributions without enumerating each mod
identity/tier combination. This task builds the exact math kernel; the dependent action adapter
will apply the existing fact sheets to concrete items. Keep files small, no framework/refactor.

## Numbered requirements
1. Input entries have `mod_id`, `type` (Prefix/Suffix), `group`, positive integer `weight`.
   Accept objects with these attributes (the item-model worker defines PoolEntry) and expose
   a local minimal dataclass `DrawEntry` with those four fields for standalone tests. Read-only
   caller input. Target labels map mod IDs to strings. All IDs absent from that map are junk.
   Duplicate IDs, nonpositive/nonfinite weights, invalid types, inconsistent group sides or
   invalid caps/counts/initial counts raise ValueError. Empty pool is legal.
2. Expose `draw_distribution(entries, draws, labels=None, *, prefix_cap=3, suffix_cap=3,
   initial_prefixes=0, initial_suffixes=0, initial_labels=(), blocked_groups=())` returning
   dict[OutcomeClass,float], where frozen ordered OutcomeClass holds `labels: tuple[str,...]`,
   `prefixes: int`, `suffixes: int`. Sort labels canonically, retain multiplicities. Initial
   counts/labels are fixed already-present mods. Zero draws returns their unit distribution.
   Caps are explicit math inputs; only action adapters decide them. If pool exhausts, terminate
   at the actually filled count with all remaining mass, never renormalize away failure.
3. Exactly group records by exclusion group. For each group, total eligible weight W and
   its internal label-weight histogram determine its draw. Each selected group disappears.
   Side-closed groups disappear from denominator. At each step probability of choosing a group
   is W / total currently eligible weight, then of its label is label_weight / W.
   Memoized DP may combine exchangeable groups only when side, total and entire label histogram
   are identical. Keep the number selected from each exchangeable bucket; denominator then uses
   remaining multiplicity times W. Do NOT collapse all junk into one reusable weight: junk
   groups disappear too. Retain internal group information until the terminal projection.
4. Expose `scheduled_distribution(entries, stages, labels=None, *, initial_prefixes=0,
   initial_suffixes=0, initial_labels=(), blocked_groups=())` with stages a sequence of
   `(draw_count, prefix_cap, suffix_cap)`. It applies the same DP while caps can grow between
   stages (magic -> rare); even an exhausted stage proceeds to later stages. This supports
   full fixed sequences before terminal aggregation. Do not feed projected terminal classes
   into later arbitrary item transitions; document their information loss.
5. Expose `mixture_distribution(weighted_distributions)` accepting iterable `(weight, dict)`;
   normalize positive mixture weights, merge equal classes. Reject invalid values or input
   distributions whose mass is not one within 1e-10. `probability(distribution, predicate)`
   sums matching mass; `expected_value(distribution, value_function)` uses the same outcomes.
   These helpers never generate a target-only probability in place of a distribution.
6. Use mathematically exact enumeration/DP evaluated with binary floats; describe float rounding
   tolerance, not sampling error. This is unbiased math (GOAL Q2), not the CoE RNG boundary bug.
   A deterministic state/work bound may raise NotImplementedError with an explicit complexity
   message; no silent approximation. A helmet rare 6-draw distribution must finish under one
   minute and preferably well below it on one process. Report state count if easily available.
7. Parameter file `data/rules/ordinary.json` holds rare_count_weights {"4":8,"5":3,"6":1},
   magic_count_weights {"1":1,"2":1}, rare_caps [3,3], magic_caps [1,1], source strings
   (S3 numOfAffixes line 993; affix_generation.md; GOAL lead-provisional 2026-09-20),
   confidence reimplemented-from-CoE. Data, not hardcoded probabilities in action code.

## Facts implemented
Only math and sourced weighted group draws from mechanics/affix_generation.md and
pool_resolution.md with provisional GOAL Q2/Q4/Q16/Q17. Any label/utility in tests is invented.
No new game facts, eligibility rules, tier derivation or third-party code.

## Numbers a test must reproduce
All synthetic fixtures below are hand arithmetic.
- A/B/C distinct groups weights 1/1/2, all Prefix, two draws cap3:
  class AB 1/6, AC 5/12, BC 5/12. P(A)=7/12; normalized mass1.
- A1 weight1 label hit and A2 weight3 junk share group A; B weight2 label b, C weight2
  junk separate groups, all Prefix, two draws: P(hit)=5/24, P(hit AND b)=5/48.
  Derivation select A within two draws 1-(2/8*2/6+2/8*2/6)=5/6 then tier hit1/4.
- Prefix A weight1 label a, Suffix B weight3 label b, magic caps1/1, two draws =>
  (a,b) probability1. One draw => a1/4,b3/4. Mixing one/two draws 1:1 => a1/8,
  b3/8, (a,b)1/2. E[count]=3/2.
- That same pool with B blocked, two draws => only a with probability1 and counts1/0;
  no eligible input => unchanged initial state with probability1.
- Prefix A1/B1/C2 distinct groups, initial prefixes1 with label seed and blocked A:
  one draw gives (seed,b)1/3 and (seed,c)2/3.
- Prefix A1,B1 and Suffix C1,D1, four distinct groups, schedule (2,1,1),(1,3,3)
  gives ABC/ABD/ACD/BCD each1/4, never both prefixes in the first magic stage.
- Invented values a=0,b=6,c=10 and supplied class distribution a1/2,b1/3,c1/6:
  expected_value=11/3; probability(value>=6)=1/2; >=10=1/6. Same distribution object.
- Real Royal Burgonet ilvl86 ordinary pool from committed data (only ModExplicit): labels
  IncreasedLife9=life, ChaosResist6=chaos, FireResist8/ColdResist8/LightningResist8=elemental.
  Six draws normalize to1, nonnegative mass; report target P(life,chaos,>=1 elemental),
  class count and wall time. No fixed golden answer required for this case yet (MC next).

## Report
Commits, allowed files, focused pytest exact summary, synthetic values, real-pool target
probability/time/mass/class count, any complexity limit. At most two correction rounds.
Do not run old source-builder tests (ignored raw sources absent in worktree). Final report
starts `=== FINAL REPORT ===`.
