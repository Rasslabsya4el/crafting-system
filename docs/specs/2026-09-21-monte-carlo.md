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

## Report
Focused pytest with --basetemp=.pytest_tmp, commits, five case IDs/draws/N/seed, exact and
estimated target probabilities, per-class bound and observed max deviation, runtime.
No game rule decisions. At most two corrections.
