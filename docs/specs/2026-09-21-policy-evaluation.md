# Spec: evaluate the lead's concrete crafting policies

Worktree `.worktrees/policy-evaluation`, branch `w-policy-evaluation`.
Allowed `src/craftoracle/policies.py`, `tests/test_policies.py`.
Budget60 minutes. Read accepted actions/distributions/costs/plan_inputs modules; do not modify
them unless lead explicitly authorizes an integration correction. No new game decisions.

## Required behavior
1. Implement `evaluate_policies(spec,loadout,data)` returning plain result with ranked policy
   records and explicitly unavailable candidates/reasons. Read docs/design/night-policies.md
   IN FULL; it is the lead's exact design, including paid setup/reset, independent stages,
   target-specific eligibility and deliberately nonoptimal fixed cycles. Never silently swap
   in a different recipe. All output probabilities are exact under provisional GOAL assumptions.
2. Policy fields: id/name, stages (name, probability, expected_attempts, actions, decisions),
   expected_cost,cost_p90,cost_method,expected_utility,irreversible_failure_risk,rare_inputs,
   assumptions,steps,decision_points,within_budget,frontier (may initially false), method,
   terminal_distribution (list of label/count/probability objects or original OutcomeClass map).
   Required-mode utility1 on completion, utility-mode conditional on passing threshold. Terminal
   distribution is conditional on completion and clearly labelled; store per-attempt or per-stage
   distributions separately so failed mass is not hidden. Risk0 is ordinary item-destruction
   risk under the slice, not probability of overspending. Budget criterion expected cost <=budget;
   p90 overbudget stays explicitly visible as a separate field/assumption.
3. Candidate (a) Chaos spam uses Alchemy setup intentionally discarded, then Chaos trials.
   Alchemy+Scour trials start Alchemy on normal and reset only failures. Essence spam evaluates
   each allowed essence, forced mapping from data, costs exact supplied ID. Keep candidates with
   p>0 even when dominated; zero p marked unreachable. Every required action/essence/recipe
   permission must be checked, base cost charged once. No price lookup default0. Missingprices
   reject that candidate with explicit reason or input error. Distinct essences distinct policies.
4. Candidate (b) first Transmute setup; attempt Alteration, optional Augmentation if1mod, Regal,
   three Exalted additions. Use scheduled DP (2,1,1),(4,3,3); maps actual labels. For magic completion and Regal, stage probability1 denotes legal completion (the real
   pool has sufficient groups); the final evaluation stage probability is the target chance.
   Also expose `target_probability_after_stage` for after magic completion, Regal and final
   six draws (it can0, never turn that into infinite stage attempts). Every stage execution
   count is outer loop1/p, not independent 1/intermediate-target-probability. The single cycle target probability determines
   renewal success. Costs use compound_geometric_cost with half augmentation coin, paid failure
   Scour+Transmute. No multiplication of mean trialcost by geometric p90. Under loadout lacking
   one of these actions it is unavailable. No claim optimal or early stopping before cycle end.
5. Candidate(c) helmet suffix protection only when it matches the described exact target-ID
   structure (one required prefix IncreasedLife9, ChaosResist6 plus elemental-any targets),
   base has separate prefix/suffix groups, all required recipe permissions exist, and full3/3
   ordinary caps apply. Stage1 Envy3 distribution, event chaos+>=oneelemental, suffixes3,
   prefixes<=2. This includes more than one elemental label. Stage2 locks/scours/exalts each
   try with p=sum target prefix weight/sum ordinaryprefixweight, exact1000/39275 for example.
   Independence follows empty prefix state, full suffix side and no cross-side groups: explicitly
   check these guards, otherwise mark unavailable, never approximate. Stage1 natural life is
   intentionally scoured. Chain independent geometric costs with base cost once, recipe729
   per stage2 attempt. Terminal suffix label classes from conditional stage1, remove any old
   life label, add target life label, counts1prefix/3suffixes. Costs from current input prices.
6. Retain the unbench-finished protected policy and additionally offer a deterministic bench
   finish variant using allowed bench131 (example recipe2chaos). Optional keyword
   `finish_bench_index` may select a different recipe for this VARIANT, default None selects131.
   Apply only to the protected policy, not arbitrary projected rerolls. Prove legality using
   its known one life prefix, three ordinary suffixes and zero retained crafts: proposed bench
   must support the base, be Prefix, have group different from life and absent from EVERY possible
   ordinary suffix group. There are two open prefixes, so no junk-prefix ambiguity remains.
   Otherwise mark variant unavailable with explicit projection/legality reason. Use current
   loadout permission and recipe price, never assume the default ID is always permitted.
   Append certain stage probability1, attempts1 and both cost metrics shifted by benchprice;
   terminal outcomes have2prefixes/3suffixes, original target labels retained plus bench label
   only if caller explicitly mapped it. No invented utility for extra armour. Test accepted
   default131 and rejected conflicting-life/suffix/disallowed recipes. Existing base policy
   remains valid without a bench substitute for T1 life. Quantity/identity source is requirement7
   of plan-inputs spec, lead read2026-09-21. This supplies GOAL's real bench-finished template.
7. Rank reachable candidates by expected_cost then cost_p90 then id. Return all available
   ranked entries to CLI so >=3 remain visible even if Pareto dominated. Unsupported candidates
   retain reasons; no swallowed errors, missing target tier or impossible essence advertised as
   success. Numeric exact means floating tolerance only; cost-convolution limits may mark a
   candidate unavailable except the specified compound-cost fallback: if cost convolution
   raises its explicit work-limit error for magic policy, call monte_carlo.estimate_compound_cost_p90
   using actual two trial costs and reset/setup,50000 samples,seed20260921,99% DKW interval.
   Keep mean/attempts/stage probabilities exact, label cost_method='estimated p90; exact mean',
   include p90 interval/samplecount/seed/error bound. Never catch unrelated exceptions as a limit.
8. Printed assumptions stored on every policy: ordinary3.29/Q9 scope; PoB group/first-match
   weight provisional Q16/Q17; no generated tags/multipliers; rare4/5/6 weights8/3/1 sourceCoE;
   prices invented inputs and no base market price; tiers exact-ID mappings for selected base;
   quality fixed input; no PoB damage valuation or CoE exactness proof. Unit from pricefile.

## Acceptance numbers / source
Kernel probabilities independently computed by lead from accepted DP, Royal Burgonet86:
- count-mixture Chaos P(target)=0.000024282088455126466;
- Deafening Envy P(target)=0.0025940606844434217;
- fixed6-mod magic-start P(target)=0.000053545793422886104;
- Envy suffixprep P=0.05567530208498237;
- suffix-protected life P=1000/39275=0.025461489497135583.
They are provisional-model predictions, not external game measurements. Test with 1e-10 relative
tolerance. Target predicate can use spec.labels; elemental alternatives must be OR, not all3.
For exampleprice Chaos1/Alchemy.5/Scour.5/Envy5/base0:
Chaos Ecost=.5+1/p; AlchScour Ecost=1/p-.5; Envy Ecost=5/p.
Protected Ecost=5/p_suffix+(2*100+.5+10)/p_life. Read example prices rather than code constants.
Bench131 variant adds2: default expected8359.193927854994,p90 18987; underlying probabilities unchanged.
Changing allprices by2 doubles cost/p90, leaves probabilities and attempts unchanged.
Removing essence permission excludes correspondingpolicies; removing bench729 excludesprotected.
Reranking pricechanges changes order, never target probabilities. Show all distributions normalized.
Focused tests must avoid rerunning identical expensive DP when price-only changed (fixtures can reuse
results); no speculative globalcache. Report full helmet table and elapsedminutes.

## Report
Commits, tests, every acceptance probability, per-policy expected/p90cost, stageattempts,
available policy count, blocked candidates, runtime and assumptions. At most2corrections.
