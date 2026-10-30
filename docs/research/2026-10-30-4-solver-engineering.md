# Engineering a Fast, Exact Stochastic-Shortest-Path Solver for Path of Exile Crafting

## Executive recommendation

For this problem class, the production solver should **not** be plain value iteration, policy iteration, or LP over the whole reachable MDP. The strongest architecture is a hybrid:

**reachable-state generation → exact per-action self-loop elimination → action pruning/bounds → SCC condensation → reverse-topological solution of SCCs → Numba Bellman kernels inside nontrivial SCCs, with policy evaluation used selectively → exact fixed-policy risk evaluation afterward.**

The central reason is structural. Your MDP has strictly positive non-goal action costs, so it fits the standard stochastic-shortest-path setting in which proper policies and Bellman optimality have especially clean behavior; positive costs also enable an unusually cheap, rigorous stopping test based on the Bellman residual. citeturn152691search0turn714636view0 At the same time, the very high self-loop probabilities in crafting make ordinary VI artificially slow: the solver repeatedly rediscoveries the geometric waiting time that can instead be summed analytically.

The most important optimization is therefore **not a faster sparse matrix multiply; it is changing the Bellman equation before iteration.** For an action \(a\) at state \(s\),

\[
Q_a(s)=c_a+p_{ss}^aV(s)+\sum_{j\neq s}p^a_{sj}V(j).
\]

If \(p_{ss}^a<1\), solve the action equation for its own self-reference:

\[
\widehat Q_a(s)
=
\frac{c_a+\sum_{j\neq s}p^a_{sj}V(j)}
     {1-p_{ss}^a}
=
\frac{c_a}{q_a}
+\sum_{j\neq s}\frac{p^a_{sj}}{q_a}V(j),
\qquad q_a=1-p_{ss}^a.
\]

Thus each action can be transformed into an equivalent **“repeat this action until it exits this state” macro-action**, with expected immediate cost \(c_a/q_a\) and conditional exit probabilities \(p_{sj}^a/q_a\). This is simply the scalar geometric-series analogue of the absorbing-chain fundamental matrix \(N=(I-Q)^{-1}\). citeturn379025search0turn379025search3 If \(p_{ss}=1\) and \(c_a>0\), that action has infinite expected cost and can be discarded whenever a finite proper solution exists.

For the two examples in the prompt, the scale of the gain is dramatic. A \(0.26\%\) chance of leaving means \(p=0.9974\) and an expected \(1/0.0026\approx384.6\) repetitions. If a VI error component contracts approximately as \(p^k\), reducing it by \(10^{-6}\) takes about

\[
\frac{\log 10^{-6}}{\log 0.9974}\approx5{,}307
\]

sweeps. At \(0.1\%\) success, the expected repetitions are \(1{,}000\), and the analogous count is about \(13{,}809\) sweeps. These two sweep counts are **derived estimates, not published benchmark measurements**. Exact self-loop elimination removes that geometric mode immediately for a pure repeat-until structure.

After eliminating self-loops, apply SCC decomposition to the remaining dependency graph. Topological Value Iteration (TVI) explicitly does this: it finds SCCs and solves them in dependency order; once one component is converged, later components cannot change it. citeturn738896view0turn250501view0 Dai, Mausam, Weld, and Goldsmith's measured C implementation found very large gains when action elimination broke large SCCs: on MCar700, the largest component fell from 390,191 states under TVI to size 1 under FTVI, and runtime fell from 233.98 s to 13.06 s. citeturn250501view2turn657058view0 That benchmark is old hardware and a different domain, so it should be treated as evidence for the *algorithmic effect*, not as a runtime forecast for PoE.

For a first production version, I would use **TVI/SCC decomposition plus conservative action elimination**, rather than implementing the entire FTVI search machinery immediately. FTVI is particularly attractive if fossil/essence action candidates create artificial connectivity that bounds can prove irrelevant; its defining idea is precisely to use lower/upper bounds to remove suboptimal actions before computing SCC structure. citeturn738896view0turn250501view1 The PoE setting looks unusually favorable for this because thousands of potential fossil combinations may be dominated before they ever need full transition materialization.

For risk, keep optimization and reporting separate initially: **optimize expected cost exactly, then evaluate the resulting policy for mean, variance/CV, p50, p90, and CVaR.** A fixed policy is an absorbing Markov chain/Markov reward process, for which moments are sparse linear solves and quantiles can be computed by a one-dimensional budget dynamic program. Full CVaR-optimal SSP control is possible in theory, but published algorithms are substantially heavier and the 2022 CVaR-SSP work describes its tested models only as “moderately sized”; it does not establish practicality at \(10^6\)–\(10^7\) crafting states. citeturn738896view1

## Method comparison

The table below treats “memory” as **algorithmic overhead beyond the transition model**. With \(10^8\) or more stored outcomes, the transition representation will dominate memory regardless of the solver.

| Method | Convergence / large sparse behavior | Near-\(1\) self-loops | Rigorous stopping | Extra memory | Implementation burden | Fit for this planner |
|---|---|---|---|---|---|---|
| **Jacobi value iteration** | One embarrassingly parallel Bellman sweep over all active state-action outcomes. Standard SSP VI converges under the usual proper-policy assumptions; positive action costs satisfy the condition that improper policies incur infinite cost somewhere. citeturn714636view0turn152691search0 | Bad without elimination: error associated with a \(p\)-self-loop can decay on the \(p^k\) timescale. | A raw Bellman residual alone is not generally an SSP error bound. For positive costs and lower-bound VI, Hansen–Abdoulahi show that if residual \(c_k<g_{\min}\), the greedy policy is proper and give a computable upper bound with no extra work beyond the residual. citeturn714636view0 | \(O(S)\) for old/new values and policy. | Very easy; ideal Numba kernel. | **Excellent baseline after self-loop elimination/SCC decomposition.** |
| **Gauss–Seidel VI** | Uses newly updated values immediately and can improve more per sweep, particularly with a good state ordering. SSP GS convergence is established under standard conditions. citeturn714636view0turn514036search10 | Better than Jacobi but still needlessly slow for \(p\approx1\) if the self-reference is left explicit. | Same positive-cost residual machinery can be adapted; otherwise residual-only stopping is not by itself a suboptimality certificate. citeturn714636view0 | One value array instead of two. | Easy serially; awkward to parallelize strongly. | **Good within SCCs** or as a serial polishing pass. |
| **Prioritized sweeping / asynchronous VI** | Backs up states whose value changes matter most and propagates priorities to predecessors; historically developed to avoid uniform sweeps over unimportant parts of a stochastic model. citeturn473274search2 | Can focus repeated work around slow loops, but it does not analytically remove them. | Requires the same SSP convergence/properness machinery as other asynchronous VI methods. | Requires predecessor lists plus a heap/priority queue, potentially substantial at \(10^8\) edges. | Moderate-high. | **Secondary optimization**, especially if only a small region remains unsettled. Less attractive if reverse-edge memory is expensive. |
| **TVI / SCC decomposition** | Decomposes the dependency graph into SCCs and solves them in topological order; acyclic pieces effectively need only dependency-ordered backups. citeturn738896view0turn250501view0 | Self-loops remain SCCs of size one unless eliminated, so combine TVI with analytic self-loop removal. | Each SCC can use the same certified stopping rule as its internal solver. TVI's paper shows that convergence component-by-component bounds the overall Bellman error. citeturn250501view0 | SCC IDs, DFS/Tarjan/Kosaraju work arrays: \(O(S+E_{\text{graph}})\). | Moderate. | **Best structural backbone.** |
| **FTVI-style action elimination + TVI** | Heuristic search tightens lower/upper bounds, eliminates provably suboptimal actions, then recomputes a much more useful SCC structure. Dai et al. found FTVI faster than TVI in all their tested domains and often much faster than heuristic-search alternatives. citeturn738896view0turn250501view2 | Indirectly excellent if the slow-loop action is dominated; still explicitly eliminate self-loops first. | Bound-based elimination is exact when a lower bound on \(Q^*(s,a)\) exceeds an upper bound on \(V^*(s)\). citeturn250501view1 | Lower and upper value vectors plus active-action flags. | Moderate-high. | **Strong second-stage optimization**, especially for thousands of fossil actions. |
| **Policy iteration** | Policy evaluation solves \((I-P_\pi)V=c_\pi\), followed by greedy improvement. Often takes many fewer outer iterations than VI, but each evaluation is a sparse linear solve. Standard SSP PI converges under the proper-policy assumptions. citeturn514036search9turn514036search15 | Excellent: the linear solve sums all loops exactly. | Exact policy evaluation plus “no improving action” is an exact optimality test modulo numerical tolerances. | A policy matrix with \(O(E_\pi)\) nonzeros plus factorization/preconditioner memory; sparse LU fill-in can exceed the original matrix substantially. SciPy exposes direct sparse solution through `spsolve`. citeturn194407search0 | Moderate. | **Excellent on small/medium SCCs**, risky as a whole-graph algorithm at millions of states because factorization can dominate. |
| **Modified policy iteration** | Alternates greedy improvement with only a finite number of policy-evaluation sweeps, interpolating between VI and PI. The classic formulation was developed for discounted MDPs, so SSP use needs the SSP properness safeguards rather than blindly applying discounted theory. citeturn514036search0 | Much better than VI if inner evaluation handles loops well; still inferior to explicit self-loop elimination for trivial loops. | Use Bellman/properness bounds after improvement, or periodically perform exact policy evaluation. | Similar to VI unless exact evaluations are invoked. | Moderate. | **Promising accelerator inside large SCCs** after the robust TVI baseline works. |
| **LP** | SSP Bellman optimality has a linear-programming/polyhedral formulation; LP gives a useful independent oracle and policy certificate on manageable problems. citeturn379025search17turn514036search15 | LP handles loops globally rather than iteratively. | Solver primal/dual feasibility and optimality tolerances supply a certificate at the LP level. | Potentially enormous: Bellman form has roughly one constraint/state-action and transition coefficients for every outcome. | Easy mathematically; hard on memory at your scale. | **Validation only**, except heavily reduced instances. Use HiGHS/highspy. |
| **LAO\*** | Expands only states relevant to the current partial solution graph and supports cyclic policies; with an admissible heuristic it can converge without evaluating the whole state space. citeturn473274search0turn473274search3 | Still performs Bellman updates, so near-self-loop pathology remains unless transformed. | Original LAO* bounds can be expensive; the positive-cost Hansen–Abdoulahi test gives a cheaper properness/suboptimality certificate. citeturn714636view0 | Only expanded graph, potentially much less than full reachable graph. | High relative to VI/TVI. | **Useful if optimal-policy reachability is much smaller than raw reachability.** |
| **LRTDP** | Trial-based, focuses on greedy-policy-reachable states and labels converged regions; designed to improve RTDP's slow final convergence. citeturn473274search4 | Rare but important outcomes can make trial-based convergence poor; Dai et al. measured severe slowdowns on long-depth benchmarks. citeturn250501view3 | Labels are based on local consistency; combine with the positive-cost global/error bound if a formal \(\epsilon\) guarantee is required. citeturn714636view0 | Expanded states plus labels; can be much lower than all-state VI. | High. | **Not my first choice** for deep crafting routes with tiny-probability branches. |
| **FRET** | Designed for generalized SSPs containing traps/reward structures where ordinary LAO*/LRTDP assumptions fail; it explicitly finds and removes traps. citeturn473274search1turn473274search5 | Handles genuine traps, not merely expensive positive-cost self-loops. | Designed to restore correct convergence in GSSPs where ordinary Bellman fixed-point assumptions can fail. | Search graph + trap analysis. | High. | **Unnecessary under your stated positive-cost SSP assumptions.** Reconsider only if zero-cost cycles or generalized rewards enter the model. |

### Recommendation by component size

For an SCC of size one after self-loop removal, evaluate it once after all downstream SCCs are solved. For small SCCs, exact policy iteration with sparse policy evaluation is attractive because its linear solve sums every cycle at once. For medium/large SCCs, use Numba GS or Jacobi VI with positive-cost residual bounds; if a component remains very large, run FTVI-style bound/action elimination and recompute SCCs before spending many sweeps.

There is an important distinction in the phrase “solve an SCC exactly.” A **fixed-policy** SCC is a linear problem:

\[
(I-P_{\pi,CC})V_C
=
c_{\pi,C}+P_{\pi,C,\mathrm{out}}V_{\mathrm{out}}.
\]

A **control** SCC with multiple actions is not one linear system because of the Bellman minimum. It becomes a sequence of linear systems under policy iteration, or an iterative nonlinear Bellman solve. Policy evaluation as a system of \(|S|\) linear equations is standard SSP theory. citeturn714636view0turn194407search0

For your particular graph, the self-loop transformation should happen **before** SCC detection. Otherwise every repeat-until action creates a graph cycle that is mathematically trivial but can make topology look less favorable than it actually is.

## Recommended solver stack

### Transition compilation and storage

Do not store one SciPy CSR matrix per crafting action. CSR is excellent for ordinary sparse matrix-vector multiplication and SciPy's representation is built around compressed rows, but your action set is ragged: each state has a different number of applicable actions and each action a different number of outcomes. citeturn194407search2turn194407search8 Thousands of fossil candidates also make “one matrix per action kind” especially wasteful.

Use a **two-level ragged CSR**, contiguous by state and then by action:

```text
state_action_ptr : int64[S + 1]

action_edge_ptr  : int64[M + 1]
action_cost      : float64[M]
action_code      : compact integer metadata[M]      # optional

succ             : int32[E]
prob             : float64[E]
```

Here \(M\) is the number of retained state-action pairs and \(E\) the number of retained non-self outcomes. If actions for each state are physically contiguous, no explicit action-ID array is needed.

At \(E=10^8\), just `succ:int32` plus `prob:float64` is \(12E=1.20\) GB. If \(M=5\times10^6\), `action_edge_ptr:int64` uses about 40 MB and `action_cost:float64` another 40 MB; one more float64 action array adds another 40 MB. For \(S=10^6\), `state_action_ptr:int64` is about 8 MB. Thus a basic \(10^8\)-outcome model is roughly **1.3 GB before state hashes, policies, temporary values, SCC metadata, predecessor data, and Python/container overhead**. Those numbers are derived directly from primitive type sizes, not a benchmark.

The widest nominal case illustrates why aggressive generation/pruning is mandatory. \(10^7\) states × 50 actions × 20 outcomes is \(10^{10}\) outcomes. At 12 bytes/outcome, successors and probabilities alone would consume about **120 GB**, before any pointers or values. A 32 GB desktop therefore cannot materialize that graph in this format; it must use lazy action generation, action pruning, repeated-transition templates, or an external-memory/distributed design.

A CSR-per-action representation has the same outcome payload but also needs row pointers for every action matrix. Even just 50 dense-in-state action matrices over \(10^6\) states require roughly 200 MB of 32-bit row pointers, before probabilities/columns; thousands of sparse fossil matrices would be much worse. The flat ragged representation also maps naturally to a Numba state loop.

### Compile self-loops out exactly

During transition generation, aggregate duplicate successors and separate the self probability:

```text
leave_weight = total_weight - self_weight

if leave_weight == 0:
    # positive cost => infinite expected cost
    discard action
else:
    effective_cost = raw_cost * total_weight / leave_weight

    for each nonself successor j:
        effective_prob[j] = weight[j] / leave_weight
```

When probabilities originate from integer mod weights, calculate `leave_weight` from integer sums rather than evaluating `1.0 - p_self`. This avoids subtraction of nearly equal floating-point numbers and preserves the exact rational structure until the final division.

The transformed action is exact because it conditions on the first eventual non-self exit and sums the geometric sequence of repeated costs. This is the same mechanism underlying fundamental matrices for absorbing chains. citeturn379025search0turn379025search4

This transformation also improves numeric conditioning. A raw equation containing \(0.999999V(s)\) forces a solver to recover information from \(1-0.999999\); integer `leave_weight` gives that denominator directly.

### Bound and prune actions before expensive graph work

Start with an admissible lower bound. Dai et al. used \(h_{\min}\), which replaces each stochastic action by its cheapest possible successor and can be computed by a backward deterministic shortest-path calculation. citeturn250501view0 For crafting, stronger domain-specific lower bounds are possible: minimum currency cost to introduce each still-required mod class, ignoring conflicts and success probabilities, for example.

Maintain an upper bound from any known proper crafting strategy. An action can be discarded whenever

\[
LB_Q(s,a)>UB_V(s),
\]

which is the action-elimination condition used by FTVI. citeturn250501view1 This is especially valuable before expanding 4,000 fossil candidates: first compute cheap lower bounds for them; construct exact transition distributions only for candidates that survive.

Cache transition calculations by a canonical **pool signature** consisting of every feature that determines the mod-weight distribution: item class/base, item level, influence state, relevant tags, open prefix/suffix slots, blocked mod groups, action parameters, and any other game rule that changes eligibility/weights. Store a template of `(outcome-class, exact weight)` rather than recomputing weight scans. The expected hit rate is application-specific; I found no published PoE crafting benchmark that quantifies this cache's benefit, so it needs measurement on your workload.

### Condense and solve SCCs

Run Tarjan or Kosaraju over the dependency graph after self-loop elimination and action pruning, construct the condensation DAG, and solve components from goals backwards. TVI's reachability/SCC preprocessing is linear in the generated graph size and its published implementation explicitly ignores unreachable components after a reachability traversal. citeturn250501view0

A practical policy is:

```text
build reachable compressed states
compile/prune actions
eliminate self-loops exactly

repeat:
    compute SCCs of active action graph

    for SCC in reverse topological order:
        if singleton with no nonself cycle:
            exact Bellman backup once

        elif SCC is small and sparse-factorization looks safe:
            initialize a proper policy
            repeat:
                solve (I - P_pi) V = rhs
                greedily improve actions
            until policy unchanged

        else:
            run Numba Bellman sweeps
            periodically:
                compute rigorous SSP residual bound
                eliminate actions proven suboptimal

    if no action elimination changed graph topology:
        break
```

For direct policy evaluation, SciPy's `spsolve` accepts CSR/CSC input, uses a sparsity-preserving column ordering by default, and uses SuperLU unless UMFPACK is installed/selected. citeturn194407search0turn194407search3 Do **not** set a universal component-size cutoff such as “10,000 states”; fill-in depends on graph structure far more than on state count. Benchmark factorization memory/time on representative crafting SCCs and use that to choose the crossover.

For large components, use a Numba kernel rather than calling one SciPy sparse matrix multiply per action. Numba's documentation explicitly supports no-Python compiled loops and `prange` parallel loops. citeturn194407search6turn194407search35 The Bellman kernel is irregular and branchy enough that direct nested loops are a better fit than constructing \(A\) separate temporary vectors and reducing them.

A Jacobi kernel is roughly:

```python
@njit(parallel=True)
def sweep(V, Vnew, state_action_ptr, action_edge_ptr,
          cost, succ, prob, policy):
    for s in prange(n_states):
        best = np.inf
        best_a = -1

        for a in range(state_action_ptr[s], state_action_ptr[s + 1]):
            q = cost[a]
            for e in range(action_edge_ptr[a], action_edge_ptr[a + 1]):
                q += prob[e] * V[succ[e]]

            if q < best:
                best = q
                best_a = a

        Vnew[s] = best
        policy[s] = best_a
```

After analytic self-loop elimination, this update no longer contains `V[s]` through the same action unless there is a genuine state cycle through other states.

Use `prange` for Jacobi over states; each iteration writes a disjoint output cell and is naturally thread-safe. Gauss–Seidel's value comes from immediate use of preceding updates, which conflicts with unrestricted state parallelism; use it serially within SCCs, block it, or parallelize independent SCCs at the same condensation-DAG level. Numba's parallel machinery supports explicit `prange`, but its documentation also notes that not every loop is profitably parallelizable and nested parallel loops may be serialized. citeturn194407search27turn194407search35

On a 12-core machine, expect scaling to saturate before 12× if the Bellman sweep becomes memory-bandwidth-bound. I found **no published benchmark for this exact ragged SSP Bellman kernel**, so a precise transitions/second claim from unrelated sparse or Numba benchmarks would be misleading.

Numba does provide useful context on interpreter overhead: an older official benchmark on an Intel i7-4790 with a \(10^7\)-element input reported a plain Python loop taking about 25.2 s versus roughly 0.67 s for the compiled Numba loop, with NumPy at roughly 0.58 s; those numbers were explicitly labeled indicative. citeturn194407search25 They justify avoiding Python's inner loops, but **do not predict your SSP throughput**.

Avoid `multiprocessing` for Bellman sweeps unless the graph is deliberately sharded. Shared-memory threaded Numba avoids serializing/copying multi-gigabyte transition arrays and preserves a single value vector. Use process-level parallelism across *different target items* instead.

### Rigorous termination

Initialize \(V_0\) as an admissible lower bound and maintain monotone lower-bound VI where practical. Let

\[
r_k=\max_s(V_k(s)-V_{k-1}(s))
\]

for a monotone lower-bound iteration, and let

\[
g=\min_{s,a}c(s,a)>0.
\]

Hansen and Abdoulahi prove that if \(r_k<g\), the greedy policy is proper and give the pointwise upper bound

\[
J_{\mu_k}(s)
\le
\frac{(V_k(s)-r_k)g}{g-r_k}.
\]

Thus

\[
0\le V^*(s)-V_k(s)
\le
\frac{(V_k(s)-r_k)g}{g-r_k}-V_k(s)
\]

and the analogous greedy-policy suboptimality gap can be checked against the requested tolerance. The convergence test requires no extra asymptotic work beyond computing the residual, although the authors note that the bound is tightest when positive action costs are reasonably uniform. citeturn714636view0

This is substantially stronger than “stop when the value changed by \(10^{-8}\).” The same paper points out that an ordinary Bellman-residual threshold alone neither supplies a true error bound nor necessarily certifies a proper greedy policy in an SSP. citeturn714636view0

Because PoE action prices can span several orders of magnitude, the global \(g_{\min}\) bound may sometimes be loose. In that case, use exact evaluation of the final greedy policy to obtain a reliable upper bound and compare it with the lower-bound value vector. That policy evaluation is a sparse linear system. citeturn714636view0turn194407search0

### Floating-point policy

Use integer weights as the source of truth and `float64` for runtime probabilities and values. Normalize a transition once when compiling it, not during every sweep. Remove zero-weight edges, combine duplicate successors, and assert that each transformed action's non-self probabilities sum to one within a tolerance chosen from construction error rather than an arbitrary large epsilon.

Do not represent an impossible/dead state merely by putting `inf` in `V` and then blindly perform `0.0 * inf`, which produces NaNs. Detect states from which no proper policy reaches the goal as a graph/model property, skip zero-probability edges, and explicitly assign infinite value to dead ends.

The standard SSP assumptions matter here: Bertsekas–Tsitsiklis require at least one proper policy and conditions that make improper policies unattractive; with strictly positive non-goal costs, an indefinitely cycling improper policy accumulates unbounded expected cost. citeturn714636view0turn152691search0 If zero-cost cycles are ever introduced by “free” crafting operations, this clean positive-cost guarantee no longer applies; that is exactly the kind of generalized setting for which FRET was developed. citeturn473274search5

### Risk metrics after the mean-optimal policy

Once the optimal stationary policy \(\pi\) is fixed, remove goal states and form its transient transition matrix \(Q\). The absorbing-chain fundamental matrix is

\[
N=(I-Q)^{-1},
\]

and \(N\mathbf1\) gives expected steps to absorption. citeturn379025search0turn379025search4 There is usually no reason to form \(N\) explicitly; solve sparse systems with \(I-Q\).

If \(c\) is the deterministic cost paid in each transient state under \(\pi\), the expected total currency cost is

\[
m_1 = c+Qm_1,
\qquad
(I-Q)m_1=c.
\]

The second raw moment follows directly from squaring “current cost + future cost”:

\[
(I-Q)m_2
=
c\odot c+2c\odot(Qm_1).
\]

Then

\[
\operatorname{Var}(C)=m_2-m_1\odot m_1,
\qquad
CV=\frac{\sqrt{\operatorname{Var}(C)}}{m_1}.
\]

The second-moment equation above is a direct Markov-reward derivation; the underlying absorbing-chain linear-system treatment is standard. citeturn379025search0turn379025search33 It costs essentially one additional sparse solve with the same matrix structure after the mean solve, and if a reusable LU factorization is available the second right-hand side is especially cheap.

For **unit action costs**, absorption time is a discrete phase-type distribution. If initial transient-state distribution is \(\alpha\) and the transient matrix is \(Q\),

\[
\Pr(T>n)=\alpha Q^n\mathbf1,
\]

so quantiles can be obtained from repeated sparse matrix-vector multiplication or exponentiation methods. citeturn379025search51

For **nonuniform integer or discretized currency costs**, use a budget DP for the fixed policy. Let \(F_s(b)\) be the probability of reaching a goal with at most budget \(b\). With action cost \(c_s>0\),

\[
F_s(b)
=
p_\pi(G\mid s)
+
\sum_{j\notin G}p_\pi(j\mid s)F_j(b-c_s),
\]

with \(F_s(b)=0\) if \(b<c_s\), and \(F_g(b)=1\). Positive costs make the augmented \((s,b)\) dependency acyclic in the budget coordinate even if the state graph itself is cyclic. The work is \(O(K E_\pi)\) for \(K\) budget bins and policy-edge count \(E_\pi\); rolling budget slices can reduce storage when the cost-lag structure permits it.

This DP gives the CDF directly, hence p50, p90 and tail quantities such as CVaR. If prices are rational, scale to integer ticks only if the resulting denominator is tolerable. Exact reward transformations of discrete phase-type chains exist for nonnegative integer rewards, but expanding a transition into one phase per currency tick can cause a prohibitive state blow-up. citeturn379025search20turn379025search22

For real-valued prices, choose a grid \(\Delta\). If \(K=\lceil B/\Delta\rceil\), a budget-augmented control problem multiplies the nominal state/work dimension by roughly \(K\): \(10^6\) crafting states and 1,000 budget bins imply up to \(10^9\) augmented state-budget pairs. That is not a practical default on 32 GB. This multiplication is a direct consequence of adding remaining budget to the Markov state, not a measured benchmark.

Therefore:

- **Mean + variance/CV:** tractable at full fixed-policy scale using sparse linear systems.
- **p50/p90/CVaR of the mean-optimal policy:** tractable if evaluated only on the much smaller one-action-per-state policy graph and with a sensible/adaptive budget grid.
- **Maximize \(\Pr(C\le B)\):** considerably more expensive because budget must be part of the control state; use only for targeted budgets and preferably after graph reduction.
- **Mean-versus-p90 Pareto frontier:** practical by solving a small family of constrained/risk-penalized reduced problems and evaluating every candidate policy's fixed-policy CDF; there is generally no reason to solve a full two-objective augmented MDP for every user query.
- **Globally CVaR-optimal SSP:** mathematically supported, including provably correct LP- and VI-based methods, but the published CVaR-SSP algorithms have exponential worst-case aspects and were demonstrated only on moderately sized models. They are not presently justified as the default for a \(10^6\)-state PoE engine. citeturn738896view1turn152691search5

## Performance and implementation evidence

The most relevant published apples-to-apples dynamic-programming timings I found are from Dai et al.'s TVI/FTVI experiments. Their code was optimized C on a **2.5 GHz dual-core AMD Opteron with 2 GB RAM**, using a Bellman-error target of \(10^{-6}\) and a five-minute cutoff. citeturn250501view0 These numbers are therefore useful for relative algorithm behavior, **not** as current hardware forecasts.

| Problem | Reachable states | Method | Measured seconds | Hardware / implementation | Source |
|---|---:|---|---:|---|---|
| MCar100 | 10,000 | VI | 1.40 | Optimized C; 2.5 GHz dual-core AMD Opteron, 2 GB | citeturn250501view0turn250501view2 |
| MCar100 | 10,000 | VI + action elimination | 0.74 | Same | citeturn250501view2 |
| MCar100 | 10,000 | TVI | 0.68 | Same | citeturn250501view2 |
| MCar100 | 10,000 | FTVI | **0.22** | Same | citeturn250501view2 |
| MCar300 | 90,000 | VI | 26.12 | Same | citeturn250501view2 |
| MCar300 | 90,000 | ILAO* | 11.91 | Same | citeturn250501view2 |
| MCar300 | 90,000 | LRTDP | 229.70 | Same | citeturn250501view2 |
| MCar300 | 90,000 | TVI | 23.22 | Same | citeturn250501view2 |
| MCar300 | 90,000 | FTVI | **2.35** | Same | citeturn250501view2 |
| MCar700 | 490,000 | VI | 278.16 | Same | citeturn250501view2 |
| MCar700 | 490,000 | VI + action elimination | 124.34 | Same | citeturn250501view2 |
| MCar700 | 490,000 | TVI | 233.98 | Same | citeturn250501view2 |
| MCar700 | 490,000 | FTVI | **13.06** | Same | citeturn250501view2 |
| SAP300 | 90,000 | VI | 42.61 | Same | citeturn250501view2 |
| SAP300 | 90,000 | FTVI | **2.96** | Same | citeturn250501view2 |
| SAP500 | 250,000 | VI | 174.71 | Same | citeturn250501view2 |
| SAP500 | 250,000 | FTVI | **9.56** | Same | citeturn250501view2 |
| Wet-floor 400 | 160,000 | VI | 105.79 | Same | citeturn250501view2 |
| Wet-floor 400 | 160,000 | FTVI | 74.24 | Same | citeturn250501view2 |
| Drive | 75,840 | TVI | 74.70 | Same | citeturn250501view2 |
| Drive | 75,840 | FTVI | 41.93 | Same | citeturn250501view2 |
| Elevator IPPC p13 | 539,136 | TVI | 58.46 | Same | citeturn657058view0 |
| Elevator IPPC p13 | 539,136 | FTVI | 54.11 | Same | citeturn657058view0 |
| Generic loop microbenchmark | \(10^7\) array elements | Pure Python | 25.2 | Intel i7-4790, official Numba performance example | citeturn194407search25 |
| Generic loop microbenchmark | \(10^7\) array elements | Numba `@njit` | ~0.67 | Same; **not an SSP benchmark** | citeturn194407search25 |
| Generic loop microbenchmark | \(10^7\) array elements | NumPy | ~0.58 | Same; **not an SSP benchmark** | citeturn194407search25 |

Dai et al.'s strongest results arose when action elimination changed the graph structure rather than merely making each sweep cheaper. On MCar300, TVI's largest SCC was 71,751 states; FTVI reduced it to one state and solved the instance in 2.35 s instead of 23.22 s. On MCar700 the corresponding SCC sizes were 390,191 and one, with times 233.98 s and 13.06 s. citeturn657058view0 This is highly relevant to crafting because dominated crafting actions can create cycles that the optimal policy never uses.

The paper also provides a useful warning against overengineering heuristic search. Extra intra-component FTVI search reduced component size by about 50% on one Wet-floor family but improved convergence by at most 10%, while adding harmful overhead in the other tested domains. citeturn250501view2 Implement simple, measurable structural optimizations first.

For heuristic search, the same study found FTVI generally robust to long goal distance, whereas LRTDP and other search methods could deteriorate sharply; on MCar300 FTVI was reported around one to two seconds over tested starts and roughly two orders of magnitude faster than LRTDP in the hard-depth regime. citeturn250501view3 Your crafting routes can likewise contain very long expected horizons from tiny success probabilities, so purely trial-based search should not be assumed to win just because it touches fewer states.

For LP, HiGHS is the appropriate open-source solver to test: its current project describes it as a high-performance serial/parallel solver for **large-scale sparse LPs** with a Python interface. citeturn194407search1 But a full Bellman LP at \(10^6\) states × 50 actions has around **50 million Bellman constraints**, and if each action has 20 outcomes it exposes about \(10^9\) transition coefficients before solver-specific matrix overhead. On a 32 GB workstation that is not a sensible primary representation. This is a direct scaling calculation; I found no authoritative published cutoff saying “HiGHS can solve an SSP of exactly X states,” because LP feasibility depends heavily on sparsity pattern and conditioning.

`pymdptoolbox` is useful as a small-instance cross-check, not as the production engine. Its documented API accepts SciPy sparse transition matrices and includes value/policy-iteration classes, but its normal examples use discounted MDPs rather than the positive-cost SSP-specific stopping machinery needed here. citeturn194407search4turn194407search17 JAX is similarly not the first choice for this irregular CPU workload; a bespoke Numba kernel gives explicit control over the ragged layout, pruning and SCC order.

## Runtime prediction

A useful ETA should be empirical and machine-calibrated rather than based on generic “states per second” folklore. I found no published work giving reliable percentage-error guarantees for predicting the completion time of SSP VI/TVI from its first few iterations, so the procedure below is an engineering model, not a theorem.

1. **Perform the same reachable-state traversal that production will use.** Start from the requested item state, canonicalize compressed states, enumerate retained actions, and count \(S\), \(M\), and \(E\). Also accumulate self-loop exit probabilities, outcome-count histograms, candidate-vs-retained action counts, and cache-hit statistics. Reachability traversal is exactly the optimization used in TVI to avoid irrelevant components, and its graph-search overhead is linear in the represented graph. citeturn250501view0

2. **Compute a memory forecast before allocating the final arrays.** For the proposed flat representation use, approximately,
   \[
   12E + 16M + 8S
   \]
   bytes for `succ:int32`, `prob:float64`, `action_edge_ptr:int64`, `cost:float64`, and `state_action_ptr:int64`, then separately budget values, policies, hashes, state encodings, SCC arrays and allocator overhead. Refuse materialization or switch to lazy/template storage well before the operating system begins paging. The formula is derived from the selected data types.

3. **Measure transition-generation throughput separately from Bellman throughput.** Crafting transition generation may be dominated by mod-pool construction, eligibility rules, hashing and state compression rather than numeric DP. Cache/JIT warm-up first; then report “states generated/s,” “actions generated/s,” and “outcomes generated/s.” This distinguishes solver cost from game-model cost.

4. **Calibrate the Bellman kernel on the actual machine.** After JIT compilation, time one or more full sweeps or a representative sample of several million outcomes. Fit
   \[
   T_{\text{sweep}}
   \approx
   \alpha S+\beta M+\gamma E
   \]
   from several samples rather than assuming edge count alone determines time. Actions and states carry branch/pointer overhead even when outcome counts are low. Numba's published performance numbers are explicitly machine- and workload-dependent, supporting direct calibration rather than transplanting generic timings. citeturn194407search25

5. **Use SCC statistics to replace one global sweep estimate.** Record the number of SCCs, largest SCC, total internal edges and distribution of component sizes. A graph that has \(10^6\) states but only \(10^4\) states in its largest cyclic component can be dramatically easier than a \(10^6\)-state monolithic SCC; the TVI/FTVI measurements demonstrate exactly this effect. citeturn657058view0 Estimate one-time acyclic/topological work separately from iterative SCC work.

6. **Run a small pilot and estimate the asymptotic residual ratio.** After perhaps 3–8 full updates of a large SCC, record a certified or ordinary Bellman residual \(R_k\). If
   \[
   \rho_k=R_k/R_{k-1}
   \]
   has stabilized below one, estimate
   \[
   N_{\rm remain}
   \approx
   \frac{\log(R_{\rm target}/R_k)}
        {\log \rho}.
   \]
   This is a local geometric-convergence estimate, **not an SSP error certificate**. It should never replace the properness/error stopping test. Policy switches and changing active actions can invalidate the fitted ratio.

7. **Report a range, not a single ETA.** Use a robust statistic such as the median of recent \(\rho_k\) values and construct optimistic/pessimistic estimates from their recent spread. Suppress the ETA while ratios are unstable, after a major action-elimination/SCC rebuild, or when the greedy policy is still changing extensively.

8. **Continuously reforecast.** Every few sweeps update edge throughput, active-action count, remaining SCCs and residual contraction. FTVI's experiments show that action elimination can radically alter SCC size mid-solve, so an ETA based solely on the initial graph can become pessimistic after successful pruning. citeturn657058view0

9. **Store calibration by CPU and model version.** Keep rolling empirical coefficients for transition generation, single-thread Bellman work, 12-thread Bellman work, SCC construction and sparse policy evaluation. After a few hundred real targets, a simple regression using \(S,M,E,\) largest-SCC edges, action-cache hit rate and early \(\rho\) will almost certainly be more useful than literature benchmarks. This last recommendation is an engineering inference; I found no published PoE/SSP dataset against which to quote ETA accuracy.

A particularly useful pre-solve number is the **geometric difficulty index**

\[
D_{\rm loop}
=
\max_{\text{retained }(s,a)}
\frac{1}{1-p_{ss}^{a}}
\]

*before* self-loop elimination. If this is \(10^3\) or \(10^4\), it predicts that raw VI is the wrong representation; after elimination, it should largely disappear from runtime prediction. That index is a proposed diagnostic, not a standard literature metric.

## Validation plan

Use three independent solution mechanisms on small models: the production TVI/Numba solver, exact-policy PI, and an LP through HiGHS. Agreement among algorithms with different failure modes is much stronger evidence than any one implementation testing itself. SSPs admit VI, PI and LP formulations under the standard conditions. citeturn714636view0turn514036search15

- [ ] **One-state repeat-until test.** One action costs \(c\), succeeds to goal with probability \(q\), self-loops with \(1-q\). Assert \(V=c/q\), and verify the self-loop-eliminated action produces this in one Bellman evaluation.

- [ ] **Competing repeat-until actions.** Give two actions \((c_1,q_1)\) and \((c_2,q_2)\); assert the optimum is \(\min(c_1/q_1,c_2/q_2)\). This catches incorrect elimination performed only on the currently selected action rather than every candidate action.

- [ ] **Two-stage reset example.** Stage B sometimes resets to A. Solve the resulting \(2\times2\) equations analytically and compare with VI, PI and sparse direct policy evaluation.

- [ ] **Acyclic DAG.** Generate random positive-cost stochastic DAGs and solve exactly in reverse topological order; TVI should agree after one pass per state dependency.

- [ ] **Small cyclic SCC.** Generate a random fixed policy with known absorbing goal, solve \((I-Q)V=c\) using dense NumPy and SciPy sparse methods, and compare with iterative evaluation. The fixed-policy linear equation follows directly from SSP policy evaluation. citeturn714636view0turn194407search0

- [ ] **Random controlled SSP oracle suite.** Generate hundreds or thousands of small positive-cost MDPs while deliberately constructing at least one proper policy. Compare production VI/TVI, policy iteration and HiGHS LP to a tight absolute/relative tolerance. HiGHS supports sparse LP and Python interfaces. citeturn194407search1

- [ ] **Original vs self-loop-eliminated model.** On random small MDPs with explicit \(p_{ss}\) up to \(0.9999\), solve both formulations and assert equal values and equivalent optimal actions within numeric tolerance.

- [ ] **SCC decomposition invariance.** Solve the whole random MDP and the same MDP component-by-component; values and greedy policy must agree. TVI's theoretical basis is exactly that converged downstream components can be treated as fixed sinks. citeturn250501view0

- [ ] **Action elimination safety.** Every removed action must satisfy its proof condition \(LB_Q>UB_V\). On small oracle cases, assert that no eliminated action belongs to any independently computed optimal policy. citeturn250501view1

- [ ] **Proper-policy test.** Deliberately create a positive-cost closed non-goal SCC plus a proper escape action. Confirm the solver assigns infinite value to a policy trapped in the SCC and ultimately picks a proper policy. Standard SSP theory distinguishes proper and improper policies precisely because this failure mode matters. citeturn152691search0turn714636view0

- [ ] **Unreachable goal.** Construct a start-state region with no route to a goal. Solver should report “no proper policy / infinite expected cost,” not falsely converge to a large finite number.

- [ ] **Zero-cost-cycle rejection.** Even though production inputs promise positive costs, inject a zero-cost cycle and assert that validation rejects it or switches algorithms. The positive-cost convergence/error result explicitly relies on positive non-goal costs; generalized zero-cost trap problems motivate methods such as FRET. citeturn714636view0turn473274search5

- [ ] **Probability invariants.** For every generated action: integer weights are nonnegative; total weight is positive; duplicate successor states are merged; normalized probabilities are nonnegative and sum to one within construction tolerance; transformed non-self probabilities sum to one.

- [ ] **Tiny-probability stress.** Exercise probabilities from ordinary values down through the smallest realistic mod-weight ratios. Compare rational/high-precision small cases against float64.

- [ ] **`inf`/NaN test.** Include zero-probability edges to infinite states and ensure preprocessing eliminates them so no `0 * inf` contamination reaches a Bellman sum.

- [ ] **Cost scaling.** Multiplying every action cost by \(k>0\) must multiply every finite optimal value by \(k\) without changing optimal policies except at ties.

- [ ] **Action-set monotonicity.** Adding an available action cannot increase the optimal expected cost; removing an action cannot decrease it.

- [ ] **Cost monotonicity.** Increasing the price of one action while leaving all transitions unchanged cannot lower the optimal value.

- [ ] **Outcome-splitting invariance.** Replacing one edge of probability \(p\) by two identical-successor edges whose probabilities sum to \(p\) must leave values unchanged.

- [ ] **Policy simulation.** Simulate the final fixed policy using the exact transition probabilities and compare the Monte Carlo sample mean to the computed \(V_\pi(s_0)\) with a statistical confidence interval. Simulation validates implementation/model consistency but does **not** prove optimality; the small-instance LP/PI comparisons provide the stronger optimality cross-check.

- [ ] **Moment simulation.** Compare simulated variance and CV against the two sparse moment equations. For heavy geometric tails, use enough runs that the confidence interval is meaningful.

- [ ] **Quantile test.** On geometric one-state examples, compare computed p50/p90 to closed-form geometric quantiles. On small multi-state chains, compare budget-DP CDFs against exhaustive probability propagation. Discrete phase-type theory gives the exact absorption-time distribution for unit-cost chains. citeturn379025search51

- [ ] **Risk-grid bounds.** For discretized currency costs, run both downward- and upward-rounded costs and verify the true small-model CDF/quantile lies between the resulting conservative bounds.

- [ ] **Performance regression.** Pin representative targets with recorded \(S,M,E\), SCC profile, cache hit rate, sweep throughput and total solve time. Fail CI or flag a benchmark if transition generation, Bellman ns/edge, or peak memory regresses materially.

The three SSP bugs to treat as release-blocking are **improper policies**, **zero-cost/nonpositive-cost cycles that violate the chosen theory**, and **unreachable goals represented as finite values**. The first two are explicitly central assumptions in the SSP literature, not merely numerical corner cases. citeturn152691search0turn714636view0turn473274search5

## References

Bertsekas, D. P., and J. N. Tsitsiklis. “An Analysis of Stochastic Shortest Path Problems.” *Mathematics of Operations Research* 16(3), 1991, pp. 580–595. Foundational finite-state SSP theory, including proper policies, Bellman optimality, VI and PI. citeturn152691search0turn152691search48

Hansen, E. A. “Suboptimality Bounds for Stochastic Shortest Path Problems.” *UAI 2011*, pp. 339–348. Develops Bellman-residual-based SSP error bounds. citeturn152691search33

Hansen, E. A., and I. Abdoulahi. “Efficient Bounds in Heuristic Search Algorithms for Stochastic Shortest Path Problems.” *AAAI 2015*. Gives the particularly useful positive-cost properness and \(\epsilon\)-optimality convergence test with no extra asymptotic work beyond the residual. citeturn714636view0turn152691search1

Dai, P., Mausam, D. S. Weld, and J. Goldsmith. “Topological Value Iteration Algorithms.” *Journal of Artificial Intelligence Research* 42, 2011, pp. 181–209. TVI, FTVI, SCC decomposition, bound-based action elimination and the principal comparative timing data used above. citeturn152691search3turn738896view0

Hansen, E. A., and S. Zilberstein. “LAO*: A Heuristic Search Algorithm that Finds Solutions with Loops.” *Artificial Intelligence* 129, 2001, pp. 35–62. citeturn473274search0turn473274search3

Bonet, B., and H. Geffner. “Labeled RTDP: Improving the Convergence of Real-Time Dynamic Programming.” *ICAPS 2003*. Introduces the labeling scheme that improves RTDP's final convergence. citeturn473274search4

Moore, A. W., and C. G. Atkeson. “Prioritized Sweeping: Reinforcement Learning with Less Data and Less Real Time.” *Machine Learning* 13, 1993, pp. 103–130. citeturn473274search2

Kolobov, A., Mausam, D. S. Weld, and H. Geffner. “Heuristic Search for Generalized Stochastic Shortest Path MDPs.” *ICAPS 2011*, pp. 130–137. Introduces GSSPs and FRET for settings with traps where standard SSP heuristic-search assumptions do not suffice. citeturn473274search1turn473274search5

Puterman, M. L., and M. C. Shin. “Modified Policy Iteration Algorithms for Discounted Markov Decision Problems.” *Management Science* 24(11), 1978, pp. 1127–1137. Classic MPI reference; its formal setting is discounted MDPs, so SSP adaptation requires care. citeturn514036search0

Garg, M., et al. “The Stochastic Shortest Path Problem: A Polyhedral Combinatorics Perspective.” *European Journal of Operational Research*, 2020. Gives an LP/polyhedral view and convergence results for standard SSP algorithms. citeturn379025search17turn514036search15

Meggendorfer, T. “Risk-Aware Stochastic Shortest Path.” *AAAI 2022*. Gives exact, provably correct CVaR-SSP approaches based on LP and value iteration and reports prototype experiments on moderately sized models. citeturn152691search5turn738896view1

Princeton Laboratory for Intelligent Probabilistic Systems. “The Fundamental Matrix of a Finite Markov Chain.” Summarizes \(N=(I-Q)^{-1}\), expected transient visits and absorption times. citeturn379025search0

DTU lecture notes, “Discrete Phase-Type Distributions.” Gives the interpretation of a discrete phase-type law as absorption time in a finite Markov chain and the survival expression \(\alpha S^n\mathbf1\). citeturn379025search51

SciPy documentation, `scipy.sparse.csr_matrix`, `scipy.sparse.linalg.spsolve`, and sparse solver configuration. Documents CSR representation and sparse direct linear-system facilities using CSR/CSC, SuperLU and optional UMFPACK. citeturn194407search2turn194407search0turn194407search3

Numba documentation, “Performance Tips” and parallel-loop documentation. Documents no-Python compilation and `prange`; published microbenchmark numbers used above are explicitly illustrative rather than SSP measurements. citeturn194407search6turn194407search25turn194407search35

HiGHS project documentation. HiGHS is an open-source C++ solver with Python bindings for large-scale sparse LP/MIP/QP and supplies the recommended independent LP oracle for reduced instances. citeturn194407search1turn194407search30

Python MDP Toolbox documentation. Supports sparse SciPy transition matrices and conventional VI/PI implementations; useful for small cross-checks but not specialized to the positive-cost SSP architecture proposed here. citeturn194407search4turn194407search17