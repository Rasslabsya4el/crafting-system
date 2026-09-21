# Spec: geometric loop costs and independent stage chains

Worktree `.worktrees/loop-costs`, branch `w-loop-costs`.
Allowed files `src/craftoracle/costs.py`, `tests/test_costs.py`.
Budget 25 minutes; source is mathematical derivation in docs/design/build_contract.md and
GOAL step 4. No game constants, prices, external I/O or network.

## Requirements
1. Frozen `LoopCost` with success_probability, expected_attempts, expected_cost, attempts_p90,
   cost_p90, method. `geometric_cost(p, attempt_cost, *, reset_cost=0, setup_cost=0)` computes
   N~Geom(p), E[N]=1/p and smallest n>=1 with 1-(1-p)^n>=.9. Total C=setup+c*N+r*(N-1).
   Use log1p for tiny p; verify boundary with stable CDF. p=1 =>1 attempt, no reset; p=0
   explicitly unreachable (infinite attempts/cost/p90, even if nominal currency price0).
   Reject p outside[0,1], nonfinite parameters, negative costs and bool numeric inputs.
2. `geometric_cdf(n,p)` counts total attempts including success, CDF0 for n<1 and p=0,
   CDF1 for p=1 and n>=1. Integer n required. `geometric_quantile(p,q=.9)` also supports
   q in (0,1), never return 0 for p>0. No lookup constants for answers.
3. `chain_cost(stages)` accepts independent stage inputs `(p,attempt_cost,reset_cost,setup_cost)`.
   Expected cost is sum of individual expectations, but p90 is NOT sum of p90s. Return
   expected_cost, cost_p90, method, plus explicit optional quantile error metadata if estimated.
   First implement exact lattice convolution: convert finite decimal costs to integer lattice
   via Decimal(str(value))/Fraction, scale by denominator LCM and GCD; each stage has shifted
   geometric support. For a bound K, truncated convolution with geometric uses recurrence
   out[k]=p*previous[k-step]+(1-p)*out[k-step] with stage offsets handled explicitly. Increase
   finite bound until CDF>=.9, hard operation/array cap. Deterministic p=1 or zero step collapses
   to a shift. Return the smallest crossing grid value. If exact lattice exceeds the bound,
   raise NotImplementedError('cost convolution work limit') rather than call it exact or sum
   marginal quantiles. A later caller may explicitly estimate that case. No unbounded loops.
4. Empty chain costs0. Any unreachable stage makes chain unreachable; validate all parameters
   first. Return clear statuses/methods and retain exact expectations. No general Markov solver.

## Hand-computed acceptance numbers
- p=.5,c2 => attempts2,cost4,n90=4,c90=8.
- p=1/6,c2 => attempts6,cost12,n90=13,c90=26.
- p=.5,c2,reset3,setup7 => mean14, q90=24 (7+5*4-3).
- p=1,c2,reset3,setup7 => mean=q90=9,attempts1.
- p=.1,c1 => attempts10,n90=22; CDF21<.9<=CDF22.
- p=0 => unreachable infinite cost; invalid -0.1/1.1/NaN rejected.
- Two independent stages p=.5,c1 => mean4,p90=7. CDF6=57/64<.9, CDF7=15/16>=.9.
  Two marginal p90s sum8 and MUST NOT be reported as chain p90.
- Same two stages c2 => mean8,p90=14; c.25 => mean1,p90=1.75.
- Deterministic stage cost3 plus previous c1 chain => mean7,p90=10.
- Tiny p=1e-9 finite quantile and stable boundary. No simulation needed to check it.

## Report
Commits, pytest summary, all fixtures, complexity bound and exact-vs-unreachable semantics.
Full focused diff will be reviewed; no raw data/builders. At most two corrections.
