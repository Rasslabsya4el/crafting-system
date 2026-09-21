# Spec: independent seeded Monte Carlo for grouped exact draws

Worktree `.worktrees/monte-carlo`, branch `w-monte-carlo`.
Allowed `src/craftoracle/monte_carlo.py`, `tests/test_monte_carlo.py`.
Budget25 minutes. Depends only on accepted item_model and distributions, read-only.

## Requirements / mathematical source
1. Expose `sample_distribution(entries, draws, labels=None, *, samples, seed,
   prefix_cap=3, suffix_cap=3, initial_prefixes=0, initial_suffixes=0,
   initial_labels=(), blocked_groups=())`. Return plain result with probabilities,
   counts, samples, seed, method='estimated', and per-class 95% Wilson intervals.
   Use explicit local random.Random(seed), no global RNG. Caller may alternatively pass rng
   if API documents mutual exclusion; no need for two APIs. Samples must be positive integer.
2. Draw INDIVIDUAL entries directly using unbiased integer randrange(total_weight), with
   current caps and group exclusions, remove all entries in selected group between draws.
   Never call exact DP, never sample its output, never reuse exchangeable-group aggregation.
   May import OutcomeClass and input dataclass. Use the same mathematics in distributions
   spec and affix_generation.md; provisional GOAL Q2/Q16/Q17. Validate input shape/caps.
3. Pool exhaustion preserves probability mass; existing counts/labels retain identity at
   terminal projection only. Sorting labels canonical. Tests show seed reproducibility and
   normalization. Expose `wilson_interval(successes,samples,z=1.959963984540054)` using usual
   binomial-score formula. Zero hits upper bound must be positive, never zero uncertainty.
4. Add at least FIVE real-pool exact-versus-MC cases using committed data, all on one process,
   <=about15 minutes worker time and tests targeted to keep total suite<1 minute. Suggested:
   Royal Burgonet86 draws6; Iron Ring86 draws2; Simple Robe86 draws3; Iron Gauntlets86 draws3;
   Crude Bow86 draws2. Choose real IDs from accepted raw definitions as labels, with nonzero
   probabilities; use 8000-15000 samples per case. Report per-case largest absolute class
   frequency deviation and simultaneous Hoeffding bound sqrt(log(2*K/alpha)/(2*N)), alpha=.001,
   K=union of exact/sampled class keys; assert all deviations <=that bound. Also compare target
   event probabilities, not only total mass. This bound is statistical math, not a game fact.
5. Hand cases for A/B/C weights1/1/2 two draws: A inclusion7/12 and AB1/6. Test zero/one
   empirical hits Wilson behavior, exact replay same seed, invalid input. No probabilistic
   assertion without an explicit error bound; no network or raw-source builder tests.
6. Needed exact-cost-limit fallback: `estimate_compound_cost_p90(p, low_cost, high_cost,
   high_probability, *, reset_cost=0, setup_cost=0, samples=50000, seed=20260921,
   confidence=.99)` uses a local numpy.random.default_rng(seed), draws attempt count N from
   geometric(p), then K~Binomial(N,high_probability). Cost=setup+N*low+(high-low)*K+
   reset*(N-1). This is independent per-attempt price randomness, NOT a replacement for exact
   crafting success probabilities. Return estimated p90, interval endpoints, samples,seed,
   confidence and explicit method. DKW epsilon=sqrt(log(2/(1-confidence))/(2*N_samples));
   interval uses empirical quantiles at .9-epsilon and .9+epsilon (clip0..1). Empirical quantile
   is inverse ECDF/higher order statistic, not interpolation. Report probability-space bound
   epsilon, not an invented standard error in currency. Validate finite costs, low<=high,
   p>0, probabilities0..1, confidence0..1, samples enough to bracket .9. Expected cost remains
   exact in caller via E[C]=setup+(low+(high-low)*h)/p+reset*(1-p)/p.
   Tests same-seed equality; constant-cost p=.5,c2 exact p90=8 lies in reported interval;
   p=1 with zero cost variation deterministic; reject p0,NaN,negative prices. Numpy is explicitly
   allowed by AGENTS and available; never pip-install or write outside repo.

## Report
Focused pytest with --basetemp=.pytest_tmp, commits, five case IDs/draws/N/seed, exact and
estimated target probabilities, per-class bound and observed max deviation, runtime.
Also report compound cost p90/interval for p=.000053545793422886104, low30.6,high30.7,
high_probability=.5,reset.6,setup.1; exact expectation formula above for comparison.
No game rule decisions. At most two corrections.
