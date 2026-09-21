# Spec: bounded atomic-action policy solver experiment

Worktree: `.worktrees/bounded-policy-solver` (branch `w-bounded-policy-solver`).
May touch ONLY `src/craftoracle/solver.py`, `tools/solver_experiment.py`,
`tests/test_solver.py`, ignored `out/solver/` reports. Lead owns interpretation and docs.

## Why
GOAL2 requests a general solver research test. A measured state explosion or failure to
converge is an allowed result after at most two corrections; an unsound compressed policy
is not. Read docs/design/parameter-search.md, especially the solver boundary.

## Requirements
1. Implement finite stochastic shortest-path value iteration (or policy iteration) over a
   supplied sparse MDP: state IDs, legal action cost and successor probabilities, terminal
   states. Return values, a readable selected action per state, Bellman residual, iteration
   count, states/edges and runtime. Validate finite nonnegative probabilities summing1,
   known successor IDs and positive nonterminal action costs. Zero-cost terminal stop is
   legal; zero-cost nonterminal cycles are explicitly outside this experiment, not given
   false finite values. Unreachable terminal states must be identified, not loop forever.
2. Provide a helmet experiment with ONLY accepted ordinary atomic actions supported by
   actions.py and the loadout: Transmute, Alteration, Augmentation, Regal, Alchemy, Chaos,
   Exalted, Annul, Scour, permitted essence IDs and eligible bench recipes. No new game
   mechanic or hand-authored full-template action may replace the action search. Harvest
   may be explicitly omitted from this first ordinary-action experiment if preserving its
   forced-draw identity requires a larger task. Record the exact action set in the result.
3. Item state must retain rarity, each target group tier/none, junk prefix/suffix counts,
   crafted/metamod flags AND enough selected-group/profile identity to preserve future
   probabilities. OutcomeClass alone is NOT a Markov state. It is acceptable to retain
   concrete group IDs with target-label/junk representatives and hit the declared graph
   limit. Collapse only demonstrably symmetric groups under every included future action:
   side/weights/target tiers/type restrictions/bench exclusions must all be equivalent.
   In the experiment all Q9 flags remain false and D14 generated tags/multipliers omitted.
4. Reuse prepare_roll/bench/scour legality and accepted draw semantics. For rerolls enumerate
   concrete group-aware outcomes using source weights/counts; do not invent a conditional
   distribution of junk identity after a projected outcome. Real transition row sums must
   pass checks when completed. Terminal target matches the supplied ItemSpec. Prices are
   read from the existing endgame loadout, including recipe quantities; permission is
   mandatory. A high-level action can internally have bounded random draw substages, but
   those substages are not free player choices.
5. Hard limits:100000 graph states,2000000 successor edges,120seconds for graph construction,
   120seconds for solving,10000 iterations, residual1e-10. One process, no background job.
   Parameterize limits for tiny tests. On a limit, write an honest incomplete report with
   measured states/edges/time/frontier and exact operation that reached the bound. No
   plausible invented helmet optimum or policy. Do not write tests that run the large
   experiment each time. Worker runs it once; lead reruns once for acceptance.
6. On success report expected helmet cost, policy steps, and comparison with the best
   accepted parameterized template at that commit. It must match or beat that candidate
   to be a positive research result; otherwise expose the action/state omission and result.
   Do not call it a global game optimum. A bounded negative result is recorded, not hidden.
7. CLI: python -m tools.solver_experiment --output out/solver/helmet.json (or an equally
   simple documented standard-library entry point). Source absence/invalid input errors
   must differ from a measured complexity-limit status. Focused pytest under a minute.

## Facts and hand optima
Action sources: existing basic_currency.md, bench_metamods.md, essences.md,
affix_generation.md and pool_resolution.md; D14. State fidelity requirement is mathematical.
The following are abstract mathematical MDPs, not claimed game currencies:

- H1: S has retry cost2 ->goal.25,S.75. Exact V(S)=8, selected retry.
- H2: S cheap cost1 ->T.5,S.5, or direct cost6 ->goal; T finish cost2 ->goal.
  Exact V(S)=4,V(T)=2, selected cheap then finish.
- H3: A gamble cost1 ->goal.25,B.75, or direct cost7 ->goal;
  B recover cost2 ->A, or finish cost5 ->goal. Exact V(A)=4.75,V(B)=5;
  selected gamble at A and finish at B. Always restarting is not optimal.
- Add an unreachable self-loop state cost1: report infinite/unreachable without corrupting
  reachable-state values. Malformed row probability1.1 and missing successors reject.
- Tiny crafting identity counterexample: A target weight1 groupA, junk B weight1 groupB,
  junk C weight9 groupC, same side. After B occupied, next A chance1/10; after C occupied,
  chance1/2. Both states have one junk prefix but cannot be merged. Demonstrate this test.

## Numbers to report
H1/H2/H3 values and chosen actions, residual/iterations; counterexample1/10 vs1/2;
real states/edges/time/peak frontier/action set, completed probability-row violations0,
helmet result and template comparison OR explicit measured bound reached; focused tests,
commits/files. Final report starts `=== FINAL REPORT ===`. No speculative optimization or
retry beyond the stated limits; send a concrete blocker if a missing rule prevents progress.
