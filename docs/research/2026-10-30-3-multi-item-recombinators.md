# Planning Crafts with Two-Input Stochastic Actions: Recombinators as Branching Stochastic Shortest Paths

## Executive conclusion

The right mathematical abstraction for Path of Exile recombination is **not an ordinary single-item MDP with a slightly larger action set**. A recombination action requires the planner to obtain *two* precursor items before one stochastic operation can occur, so the natural Bellman equation contains terms such as \(V(A)+V(B)\). That makes the problem a form of **branching stochastic shortest-path / stochastic AND-OR planning**, closely related to directed hypergraphs, AND/OR graphs, context-free “grammar” shortest-path problems, and branching MDPs. Knuth's 1977 generalization of Dijkstra handles the deterministic, monotone, acyclic-cost analogue; AO\* handles acyclic AND/OR solution graphs; LAO\* extends heuristic search to cyclic stochastic policies; and branching-MDP fixed-point theory gives the closest formal match to the proposed recurrence. citeturn523990search1turn946474search0turn983240search0

For this application, I recommend a **hybrid exact/anytime solver** rather than materializing a global hypergraph. Keep the existing single-item transition model, add lazily generated binary “procurement hyperactions,” maintain lower and upper bounds on the acquisition cost of item classes, and solve the resulting monotone Bellman system with asynchronous value/policy iteration or an LAO\*-style envelope search. Inside each recombination action, enumerate outcomes exactly under the chosen recombinator model; outside it, generate only donor pairs that survive feasibility, dominance, target-coverage, and lower-bound tests. This retains optimality **provided every pruned donor or pair has a valid dominance or lower-bound certificate**. Beam limits and arbitrary helper-mod caps should be treated explicitly as heuristics with no general multiplicative or additive approximation guarantee. citeturn946474search0turn121186search5turn121186search6

A particularly important implementation point is that the mapping

\[
V(S)=\min_a\left[c_a+\mathbb E V(S')\right]
\]

for ordinary one-input crafting becomes

\[
V(S)=\min\left\{\text{one-input alternatives},\
c_r+V(A)+V(B)+\sum_o p(o\mid A,B,r)V_{\text{continuation}}(o)\right\},
\]

but **this expression is not a contraction in the usual discounted-MDP sense** because the coefficients attached to child acquisition values can sum to more than one. The relevant solution is therefore the **least non-negative fixed point**, under properness/finite-cost assumptions, rather than the unique Banach fixed point of a discount contraction. Branching-MDP work establishes least-fixed-point Bellman characterizations for closely related systems, while ordinary stochastic-shortest-path theory establishes convergence of value and policy iteration when suitable proper-policy assumptions hold. citeturn983240search0turn983240search1turn983240search4

There is also a current-game correction relevant to the sample route. In PoE 3.29, the old Bestiary crafts that split a rare item into two or three items were replaced by Talisman fracture crafts, and Fractured Fossils no longer create split copies. Therefore step 4, “Split to isolate Global Defences,” is **not a generally available 3.29 crafting operation** in the form used by older routes; any 3.29 planner should disable those historical split actions unless another currently valid mechanism with the required semantics is explicitly modeled. citeturn211953search0turn688409search1

## Algorithm comparison

The key distinction is between a **hyperarc** of the deterministic form “to produce \(S\), produce all of \(A,B\)” and a **stochastic hyperaction** of the form “produce \(A,B\), pay the recombination cost, then nature chooses one successor.” Directed hypergraphs and AND/OR graphs capture the first structure naturally; stochastic shortest-path MDPs capture nature's choice and cycles; branching MDPs combine both. Gallo et al. formalized directed hypergraphs and efficient path algorithms for several additive/superior cost measures, but general shortest-hyperpath definitions can become NP-hard, so the exact complexity depends strongly on what “hyperpath cost” means. citeturn717148search0turn717148search2turn717148search3

| Method | Guarantee | Cycles | Stochastic outcomes | Complexity / important qualification | Fit for PoE |
|---|---|---:|---:|---|---|
| **AO\*** | Optimal solution tree with an admissible heuristic under its standard acyclic-solution assumptions. citeturn946474search1 | No, not when the solution itself contains loops. citeturn946474search1 | Yes, through AND/chance children when the graph is acyclic. citeturn946474search8 | Worst-case exponential in the implicit search space; heuristic accuracy determines how much of the graph is expanded. citeturn946474search1 | Good conceptual model for non-recycling craft trees; insufficient by itself once failed outputs are recycled. |
| **LAO\*** | Optimal policy for finite cyclic MDP-style problems when used with an admissible heuristic and converged dynamic programming on the explicit solution graph. citeturn946474search0turn946474search11 | Yes. | Yes. | Worst-case can still require the full reachable state graph; value-iteration convergence may be asymptotic. citeturn946474search11 | Very good outer search architecture if donor/pair generation is lazy. |
| **Knuth 1977 generalized Dijkstra** | Exact for the “grammar problem” when production cost functions are *superior*: monotone in every child and no smaller than the maximum child value. citeturn523990search0turn523990search7 | Handles recursive grammar structure only where the superior-function label-setting assumptions make the finalization logic valid. | Not natively a stochastic-policy algorithm. | Dijkstra-like label setting; efficient for superior/weakly-superior functions, but the theorem does not cover arbitrary stochastic Bellman operators. citeturn523990search5turn523990search7 | Excellent for deterministic “recipe acquisition” subproblems and lower bounds; not the whole recombinator problem. |
| **Gallo–Longo–Pallottino–Nguyen directed hyperpaths** | Exact for the particular polynomial-time hyperpath measures covered by the paper; not for every plausible total-hyperedge-cost definition. citeturn717148search0turn717148search3 | Directed hypergraphs themselves may contain cycles; algorithmic tractability depends on the path measure. | Deterministic base formulation; stochastic routing extensions exist. citeturn946474search6 | Reachability is linear in hypergraph size; several shortest-hyperpath measures are polynomial, while general shortest hyperpaths can be NP-hard. citeturn717148search6turn717148search3 | Useful representation and lower-bound machinery; avoid assuming “hypergraph shortest path” is automatically easy. |
| **Stochastic hyperpath formulations** | Exact for the specific adaptive-routing objectives encoded by the hypergraph construction. citeturn946474search6turn946474search10 | Often formulated on time-expanded acyclic hypergraphs; cyclic crafting requires a more general SSP treatment. | Yes. | Some stochastic routing constructions become linear in the expanded hypergraph size, but that result is tied to their special structure. citeturn946474search6 | Conceptually useful, but PoE has procurement branching plus recycling cycles, so a branching SSP is closer. |
| **Subset / Held–Karp-style DP** | Exact when the state really is a subset and every optimal solution decomposes according to the recurrence. | Usually acyclic by subset cardinality. | Stochasticity can be integrated into each recurrence if outcomes stay inside the DP state family. | Standard Held–Karp has \(O(n^2 2^n)\) time; “partition a subset into two sub-subsets” recurrences commonly total \(O(3^n)\). citeturn121186search0turn121186search2 | Strong for a small target-mod universe, e.g. 3–6 essential mods. Poor once helper mods, bases, tiers and junk counts become first-class dimensions. |
| **Factored MDP / symbolic DP** | Exact only if the symbolic representation is solved exactly; most practical factored-MDP methods use approximation. | Yes. | Yes. | Factoring can exponentially compress representation, but exact solution can still be exponential in interaction width; approximate factored value functions can scale to enormous nominal state spaces. citeturn674926search3turn674926search5 | Promising longer term if mod/base variables factor cleanly; probably excessive engineering for a first solver. |
| **Branching MDP / min-polynomial Bellman systems** | Least-fixed-point characterization; some related BMDP quantitative problems admit polynomial-time approximation to desired precision. citeturn983240search0turn983240search1 | Yes. | Yes. | Complexity results depend on the exact BMDP objective; generalized Newton/LP methods can outperform naive iteration on suitable monotone systems. citeturn983240search1turn983240search9 | Closest theoretical model to “one decision recursively requires multiple child resources, then stochastic continuation.” |

### Plain-language interpretation

AO\* says: “a recipe is an OR choice, and choosing a recipe creates several AND requirements.” LAO\* adds: “a failed craft may send you back to a state already seen.” Knuth says: “if combining child costs is monotone enough, you can finalize cheapest ingredients in Dijkstra order.” Hypergraph algorithms say: “an action can have several prerequisite vertices rather than one predecessor.” Subset DP says: “if the only thing that matters is which desired mods have been assembled, enumerate masks rather than concrete items.” Factored MDPs say: “represent bases, mods, tiers and flags as variables instead of enumerating every item.” Branching MDPs say: “one decision can spawn several independent subproblems before the stochastic process continues.” citeturn946474search0turn523990search0turn674926search5turn983240search0

For the full PoE problem, **LAO\*-style heuristic search over a lazily generated branching Bellman graph** is a better engineering fit than a literal implementation of any single classical algorithm. It naturally reuses the existing value-iteration infrastructure, supports recycling, and allows exact pruning certificates. citeturn946474search0turn946474search11

## Unified fixed point with the single-item MDP

### State semantics

There are two quantities worth separating in the implementation:

\[
C(x)=\text{minimum expected currency cost to acquire one item of class }x
\]

and

\[
J_t(x)=\text{minimum expected additional cost to reach target }t
\text{ when one item }x\text{ is already held.}
\]

Keeping them distinct avoids a common accounting error: if a recombination consumes \(A\) and \(B\), their acquisition costs belong **before** the stochastic transition; once the output \(o\) exists, the continuation cost is \(J_t(o)\). Buying \(x\) from trade gives an exogenous upper bound \(C(x)\le p_{\text{trade}}(x)\). The single-item crafting MDP acts on \(J_t\); the procurement tree acts on \(C\); the two communicate because a procured intermediate can immediately enter the single-item policy. This is equivalent to introducing an explicit “no item held / procure an item” portion of a larger SSP, but avoids materializing inventories. Ordinary SSP Bellman equations use immediate cost plus expected successor value, and their solution theory relies on policies eventually reaching the terminal state. citeturn674926search9turn983240search4

For an ordinary one-item action \(a\),

\[
Q_a(x)=c(a)+\sum_y P(y\mid x,a)J_t(y).
\]

For an unpredictable recombination of independently procured \(A\) and \(B\),

\[
Q_r(A,B)
   = C(A)+C(B)+c(r)
     +\sum_o P(o\mid A,B,r)J_t(o).
\]

Then the target-conditioned value is

\[
J_t(x)=
\min\left[
\mathbf 1_{\text{goal}(x,t)}\cdot 0,\
\min_{a\in\mathcal A_1(x)}Q_a(x),\
\min_{(A,B,r)\in\mathcal A_2(t,x)}Q_r(A,B)
\right].
\]

The precise indexing of the two-input term depends on whether a recombination is allowed only from an abstract “procure and combine” node or while holding one donor; both are equivalent if costs are accounted consistently. The mathematical feature that matters is the additive \(C(A)+C(B)\) prerequisite. Branching-MDP Bellman systems likewise combine values from multiple descendants and characterize optimal quantities through a least fixed point. citeturn983240search0turn983240search1

### Recombinator mechanics in the transition kernel

Current PoE 1's unpredictable recombination chooses one input base with 50/50 probability; pools prefixes and suffixes separately; determines a final affix count from the pooled count; and then selects eligible mods subject to rules involving mod groups, exclusive modifiers and non-native modifiers. The wiki currently gives estimated count probabilities of 66.7/33.3% for keeping one/two from a pool of two, 10/60/30% for one/two/three from four, and 30/70% for two/three from six. It also says modifier selection is weighted rather than known to be uniform. citeturn829063search0

That last point matters materially to the planner: **uniform eligible-mod selection is a model assumption, not an established live-game mechanic**. The current wiki explicitly says rarer/higher-weight behavior affects selection and that the exact formula is unknown; patch 3.25.1 also stated that rarer modifiers were given a much higher chance to be selected. Therefore every expected-cost route whose advantage depends on uniform selection should carry a visible “mechanics-model assumption” flag. citeturn829063search0turn829063search1

### Recycling and cycles

Suppose recombining \(AB\) and \(AC\) can yield \(ABC\), \(AB\), \(AC\), \(A\), or other reusable outcomes. The Bellman equation simply keeps those outcomes as ordinary successors:

\[
Q_r=C(AB)+C(AC)+c_r+
p_{ABC}J(ABC)+p_{AB}J(AB)+p_{AC}J(AC)+\cdots.
\]

If \(J(AB)\) itself chooses a recombination whose possible outcome is again \(AB\), the graph is cyclic. This is exactly the situation for which LAO\* replaces AO\*'s acyclic bottom-up backup with value or policy iteration. citeturn946474search0turn946474search1

For nonnegative costs, monotonicity gives a natural fixed-point interpretation. Starting from a componentwise lower bound, repeated Bellman backups generate nondecreasing lower bounds; under suitable properness and finite-value assumptions they converge to the least fixed point. Closely related branching-MDP systems are explicitly characterized this way. However, unlike a discounted MDP, there is no universal geometric convergence factor such as \(\gamma^k\), and naive value iteration can be arbitrarily slow near almost-self-looping policies. citeturn983240search0turn983240search9turn946474search11

A simple PoE example explains the slowdown. If an action costs \(c\), succeeds with probability \(p\), and otherwise returns to exactly the same decision state, then

\[
V=c+(1-p)V
\quad\Rightarrow\quad
V=\frac c p.
\]

Plain iteration from zero reduces the residual by a factor \(1-p\) per sweep, so a \(1\%\) success craft has a convergence factor near \(0.99\). This is why analytical self-loop elimination, policy evaluation, or Newton-style updates are preferable for low-success repeated crafts. The algebra itself is elementary; the broader fact that SSP value iteration may be asymptotic, and that Newton methods are used for monotone recursive polynomial systems, is established in the cited literature. citeturn946474search11turn983240search9

### Consumed inputs and destruction

“Both inputs are consumed” does **not** require a special penalty term if \(C(A)+C(B)\) is charged on every attempt. The input acquisition cost has already been paid before the random outcome is sampled. If unpredictable recombination always produces one output, even a bad output is simply another successor state and can be recycled if useful. Current PoE documentation describes unpredictable recombination as the no-destruction alternative to predictable recombination. citeturn829063search0turn829063search2

Predictable/selected-mod recombination is different. Current PoE lets the player select modifiers, displays a success probability, and destroys both inputs without output on failure. citeturn829063search0turn829063search2 If success deterministically gives class \(Y\) and failure leaves nothing, repeated production of \(Y\) obeys

\[
C(Y)
\le C(A)+C(B)+c_r+(1-p)C(Y),
\]

hence, if that retry policy is chosen,

\[
C(Y)=\frac{C(A)+C(B)+c_r}{p}.
\]

If success has several output classes, introduce an explicit **empty/no-item continuation state** \(E_t\):

\[
Q_r=C(A)+C(B)+c_r
+\sum_o p_oJ_t(o)
+p_{\rm fail}J_t(E_t).
\]

This is safer than pretending failure transitions to either donor, because neither donor survives. The selected-mod mode is therefore straightforward once “nothing held” is represented explicitly. citeturn829063search0

### Recommended solver skeleton

```text
Inputs:
    target T
    single-item action generator A1(x)
    recombination transition model R(A, B)
    market/baseline acquisition costs buy[x]
    admissible lower bounds LB[x]
    tolerance eps

Maintain:
    C[x]      # cost to acquire one x
    J[x]      # remaining cost to target while holding x
    policy[x]
    candidate donor classes generated lazily

Initialize:
    C[x] = buy[x] or +inf
    J[x] = 0 for goal classes
    J[x] = known feasible upper bound otherwise
    frontier = classes relevant to T

repeat:
    changed = false

    # Single-item Bellman backups
    for x in active classes:
        best = J[x]
        for a in A1(x):
            q = price(a) + sum_y P(y|x,a) * J[y]
            best = min(best, q)

        if best improves J[x]:
            J[x] = best
            policy[x] = a
            changed = true

    # Lazy two-input generation
    for demanded output/continuation region G:
        donors = generate_classes_relevant_to(G)

        donors = remove_infeasible(donors)
        donors = dominance_prune(donors)

        for unordered pair (A,B) generated best-first:
            lower =
                LB[A] + LB[B] + recomb_price
                + expected_continuation_lower_bound(A,B,G)

            if lower >= current_upper_bound(G):
                skip pair       # exact branch-and-bound pruning

            outcomes = exact_or_assumed_recomb_distribution(A,B)

            q = C[A] + C[B] + recomb_price
                + sum_o outcomes[o] * J[o]

            # Predictable mode:
            # add p_fail * J[EMPTY] when failure destroys both inputs.

            if q improves J/G:
                update value and policy
                add newly reachable outcomes/classes to frontier
                changed = true

    # Improve acquisition costs of intermediate classes
    for x in active classes:
        C[x] = min(
            buy[x],
            cheapest known single-item way to produce x,
            cheapest known recombination way to produce x
        )

    # Strongly connected portions of current greedy policy
    # should be solved by policy evaluation / local linear solve,
    # rather than one Bellman sweep at a time.

until Bellman residual <= eps
      and no unexplored pair has lower_bound < incumbent

return policy, value bounds, risk report
```

The **exactness certificate** is the last condition: every ungenerated pair must have an admissible lower bound no better than the incumbent. Without that certificate, lazy generation becomes a heuristic. This is the standard branch-and-bound logic: regions whose lower bound cannot beat the incumbent may be removed without losing the optimum. citeturn121186search6turn121186search5

For performance, solve the strongly connected component induced by the current policy as a linear system whenever the policy is fixed. In an ordinary SSP policy, \(J=c+P_\pi J\), so a proper finite component can be evaluated through \((I-P_\pi)J=c\); LAO\* explicitly allows policy/value iteration on cyclic solution graphs instead of acyclic back-propagation. citeturn946474search0turn983240search10

## Pruning and scale

### Raw scale

Using unordered donor pairs with self-pairing allowed, \(N\) donor classes produce \(N(N+1)/2\) pairs. The four cases in the question therefore give:

| Case | Donor classes | Raw unordered pairs |
|---|---:|---:|
| 3 T1 prefixes, one base | 80 | 3,240 |
| 3 prefixes + 3 suffixes, one base | 400 | 80,200 |
| + 5 helper mods per side | 19,600 | 192,089,800 |
| + 4 bases | 78,400 | 3,073,319,200 |

The crucial point is that **pair count, not item-state count, becomes the dominant combinatorial term**. Even before outcome enumeration, \(78{,}400\) states are manageable on one desktop while \(3.07\) billion pair evaluations are not.

No academic or PoE source I found reports a defensible “expected number of recombinator pairs remaining” after the exact pruning rules proposed here. Therefore numerical post-pruning pair counts should be reported as measurements from your own corpus, not as literature-backed expectations. The literature does support the correctness of lower-bound and dominance pruning, but not a domain-specific survival rate. citeturn121186search6

### Dominance

The strongest exact pruning rule is not merely “cheaper and more target mods.” Donor \(A\) dominates donor \(B\) only if **every recombination action for which \(B\) is eligible can replace it by \(A\) without worsening the transition distribution relevant to the objective**, while \(C(A)\le C(B)\). Generic branch-and-bound dominance is exact when every completion descending from the dominated state has an at-least-as-good completion from the dominating state. citeturn121186search6

For recombinators this means the dominance key must include all transition-relevant properties: base eligibility, item level, influence/status, prefix/suffix counts, mod groups, exclusive/NNN status, and any property affecting selectable-mod weighting. A donor containing a strict superset of desired mods is **not automatically better** if its additional affix changes the kept-affix-count distribution or competes during modifier selection. Current recombinator mechanics make pooled affix count and eligibility relevant to the output probabilities. citeturn829063search0

A safe implementation is therefore to maintain a Pareto frontier inside equivalence classes of identical recombination behavior. Within one such class, if two donors induce exactly the same transition kernel and one has higher acquisition cost, discard it. Broader dominance can be added only after proving stochastic dominance of the entire output kernel.

### Admissible lower bounds

A lower bound for a candidate pair can be extremely cheap:

\[
LB(A,B)=LB_C(A)+LB_C(B)+c_r+\sum_o p_o\,LB_J(o).
\]

If this is already at least the best known feasible policy value, the pair cannot improve the solution. This is exactly the admissible-heuristic / branch-and-bound principle used by A\*, AO\* and generic B&B. citeturn121186search5turn946474search1turn121186search6

Useful PoE lower bounds include: ignoring junk competition; pretending the desired base is always chosen instead of 50/50; replacing uncertain modifier-selection probabilities by an optimistic survival probability of 1; allowing a target mod to appear at its cheapest possible acquisition price regardless of incompatibilities; or solving a relaxed subset DP that forgets tiers, bases and helper identities. Because all of these relax constraints, they can only make the hypothetical route cheaper and are therefore admissible if implemented consistently.

### “Only pairs that advance the target”

This is safe only with a careful definition of “advance.” The sample route itself shows why a naive rule is wrong: mana and % Evasion can be valuable solely because they alter a future recombination probability. Current recombinator mechanics explicitly make the number and eligibility of pooled affixes matter, so a helper mod can improve the probability of retaining the truly desired mod even though the helper is later discarded. citeturn829063search0turn829063reddit7

An exact rule is: discard a pair only if its entire outcome distribution lies in states whose lower-bound continuation value is no better than the incumbent and it cannot change any future recombination-relevant feature. “Adds a target mod now” is a heuristic; “can provably never improve any reachable continuation state” is an exact pruning certificate.

### Lazy generation

Lazy generation is almost mandatory at the 19,600- and 78,400-class levels. Rather than create \(O(N^2)\) hyperedges, index donors by compact signatures: target-prefix mask, target-suffix mask, helper category, prefix/suffix counts, base family, item-level bucket, influence/NNN eligibility, and exclusive-mod flags. Generate compatible partner buckets only when an active Bellman backup asks for them. LAO\*'s main advantage over full dynamic programming is precisely that it can solve the portion of a state space reachable under promising policies without evaluating the whole state space. citeturn946474search0

If after dominance and relevance filtering only \(K\) donor classes remain for a target region, the local worst case drops from \(N(N+1)/2\) to \(K(K+1)/2\). For orientation, \(K=1{,}000\) means 500,500 pairs; \(K=300\) means 45,150; \(K=100\) means 5,050. Those are arithmetic consequences, **not empirical survival predictions**.

### Subset DP as a lower bound or exact special case

If the only semantic variable is a mask of \(m\) desired mods and an action combines two disjoint/overlapping masks, an exact partition DP can enumerate every mask and every submask split in \(O(3^m)\) aggregate time. This is the same combinatorial phenomenon that appears in Steiner-tree subset recurrences; standard Held–Karp-style dynamic programming reduces factorial search to exponential subset search. citeturn121186search0turn121186search2

For \(m=6\), \(3^m=729\), so an exact mask relaxation is tiny. That makes it an excellent admissible lower bound for the full item-state solver: forget bases, tiers, helper identities and junk, solve the best abstract way to assemble the missing desired-mod mask, and use that cost to prioritize or prune concrete donors.

### Automatic helper-mod choice

Treat helper mods as **features that modify a recombination kernel**, not as a fixed curated list. For every potential helper \(h\), compute or estimate:

\[
\Delta_h=
\frac{\text{expected reduction in downstream cost caused by adding }h}
     {\text{expected cost of acquiring }h}.
\]

Generate helper candidates from mod data by requiring that they are cheap to place and that adding/removing them changes at least one transition-relevant statistic: pooled affix count, exclusivity interaction, native eligibility, or selection weighting. Current recombinator guides explicitly exploit filler/exclusive modifiers to change retained-affix probabilities, which supports this modeling choice. citeturn829063reddit7turn829063search0

For an exact solver, the helper search must eventually consider every helper class that is not dominance-pruned. In practice I would first run a heuristic top-\(k\) helper screen, obtain a strong incumbent, then expand additional helpers only if their optimistic lower bound can beat that incumbent.

### Beam search

Beam search—retain only the best \(B\) donors, pairs, or partial policies at each depth—has **no general optimality or bounded-error guarantee** here. A route that looks expensive at depth two can become optimal because a helper changes the odds of a later recombination, and beam search may discard it permanently. Thus the correct label is “heuristic, unknown error” unless you retain a lower bound for every discarded branch and later prove that none could beat the incumbent.

A practical bounded-error variant is to terminate when

\[
U-L\le \varepsilon,
\]

where \(U\) is the cost of the best complete route found and \(L\) is the minimum admissible lower bound among all unexplored or beam-discarded branches. Then \(U-V^\*\le\varepsilon\). This is ordinary branch-and-bound logic rather than a property of beam search itself. citeturn121186search6

### What the four scales imply

At 80 and 400 classes, brute-force pair evaluation is entirely reasonable: 3,240 and 80,200 kernels are small enough that exact outcome enumeration should be preferred.

At 19,600 classes, 192 million pairs make “enumerate everything, then value iterate” unattractive. The search should be lazy, signature-indexed and bound-driven.

At 78,400 classes, 3.07 billion raw pairs make quadratic materialization categorically the wrong representation for a seconds-to-minutes desktop target. The solver needs to act more like a database query optimizer or LAO\*: generate a tiny active subset, derive a good incumbent early, and prove most other pair regions irrelevant by bounds or dominance. This conclusion follows directly from the pair counts and from LAO\*'s motivation of avoiding evaluation of an entire MDP state space. citeturn946474search0

## Prior art in games and crafting planners

### Path of Exile

Craft of Exile is primarily a **probability/cost calculator and crafting simulator**, not a global optimal policy solver. Its public description says it computes odds for mod combinations, simulates outcomes, and converts craft setups to league currency costs; it also warns users to validate very low-probability calculations with large simulations. citeturn829063search5

Esm's current recombinator calculator models PoE recombinator inputs and mod-group interactions, but presents itself as an odds calculator rather than a global acquisition-tree optimizer. Its own documentation warns that recombinator mechanics changed substantially after the 3.25/3.26 work on which many community explanations were based. citeturn846607search4

A particularly relevant open-source project is **Recipinator**, which explicitly describes itself as a recombinator recipe optimizer. It uses bottom-up dynamic programming, stores the top-\(K\) recipes for item classes, reports expected costs and base-item requirements, and can account for inventory of failed crafts. That is quite close to the subset-DP layer proposed here, although its public README describes a bounded top-\(K\) dynamic program rather than a general cyclic stochastic-shortest-path optimizer over the full PoE crafting system. citeturn846607search5

PoE 2 also has recombinator probability calculators, but at least one current tool explicitly labels its probability model speculative and based on early data/legacy weighting assumptions. That is useful precedent for clearly separating *mechanics certainty* from *computed numerical precision*. citeturn846607search6

### Persona and Shin Megami Tensei fusion

Persona/SMT fusion calculators are perhaps the closest deterministic game analogue. The widely used Persona 5 calculator enumerates ingredient pairs, deterministically applies arcana and level fusion rules, builds reverse recipes for a target Persona, and attaches an estimated ingredient cost. citeturn244708search0turn244708search6 The broader Megami Tensei fusion tool supports forward and reverse two-way and three-way fusion and recipe generation across many games. citeturn244708search3turn244708search4

Newer Persona planners expose recursive fusion trees. One Persona 3 Reload project describes a backward-chaining, depth-limited search from the target toward base ingredients; another Persona 5 Royal planner exposes a recursive fusion tree with alternate recipes at every node. citeturn244708search2turn244708search1 These systems demonstrate the usability of recursive “how do I acquire both children?” interfaces, but their fusion result is mostly deterministic, so they do not face PoE's recycling-policy fixed point.

### Factorio and Minecraft

Factorio planners demonstrate a different but useful technique: transform crafting into **material-flow optimization**. Modern planners support multiple outputs, byproducts, probabilistic recipes and recycling loops; some explicitly solve production balancing with linear programming, including cyclic recipe chains. citeturn244708search9turn244708search10turn244708search11 LP is natural there because the goal is steady-state production rate and fractional recipe throughput. PoE differs because one cares about discrete items, one-shot stochastic transitions, stateful modifiers and stopping upon success, so a pure flow LP loses essential information.

Minecraft recipe planners are usually simpler backward tree expansion: select a target, recursively expand each ingredient to raw materials, aggregate quantities, and stop at primitive resources. citeturn244708search12turn244708search13 That is directly analogous to an acyclic deterministic hypergraph, but not to stochastic recycling.

### Monster Hunter

Monster Hunter tooling is dominated by **equipment/set optimization**, often using integer or linear programming to meet skill constraints rather than stochastic recipe search. One open-source optimizer uses PuLP for skill-weighted builds and equipment constraints; current decoration planners also use greedy or combinatorial slot assignment. citeturn846607search0turn846607search1 This is useful precedent for Pareto/dominance preprocessing of components, but less directly relevant to stochastic crafting trees.

### Overall lesson from prior art

Existing game tools largely fall into four camps: deterministic recursive recipe enumeration, DP over small fusion state spaces, linear programming over steady-state material flows, and probability calculators for one crafting step. I did **not** find a widely used game-crafting tool that simultaneously optimizes a cyclic, stochastic, two-input acquisition policy over a state space comparable to PoE explicit modifiers. That appears to be the novel part of this project.

## Risk, route presentation, and total-cost distributions

A minimum-expected-cost route can be misleading to a player because two policies with the same mean can have very different tails. Stochastic-shortest-path literature explicitly distinguishes expected total cost from objectives based on the distribution or risk measures such as CVaR; a low expected value does not by itself imply a low probability of a very expensive realization. citeturn674926search7turn674926search8

For each proposed route, the human-facing report should therefore include at least:

| Quantity | Meaning |
|---|---|
| **Expected total cost** | The Bellman objective optimized by the solver. |
| **Median / p90 / p95** | Currency budget exceeded in 50%, 10%, or 5% of runs. |
| **Success probability per attempt** | Especially important for selected-mod recombination and fractures. |
| **Expected number of each donor** | E.g. “2.31 Grasping Mails, 1.84 evasion chests.” |
| **Expected recombinator uses** | Useful operational measure separate from currency. |
| **Intermediate acquisition cost** | Mean cost and market-buy alternative for every reusable class. |
| **Failure branches** | What bad outputs are recycled, sold, recrafted, or discarded. |
| **Mechanics confidence** | “Official,” “community measured,” or “uniform-selection assumption.” |

### Computing the distribution

Once a policy is fixed, the expected value is cheap because expectation is linear. The **full distribution** is more expensive but still tractable for a selected final policy. If costs are discretized into currency buckets, define \(F_x(k)\) as the probability that the remaining total cost from state \(x\) is at most \(k\). An ordinary stochastic craft convolves the immediate-cost distribution with the successor distribution; an AND procurement node convolves the independent distributions for acquiring both children; repeated failure/retry creates a geometric or, more generally, phase-type/Markov-renewal structure. Phase-type constructions are a standard way to encode total stochastic path cost distributions through Markov chains. citeturn674926search6

For a deterministic-cost recombination requiring independent donors \(A,B\),

\[
D_{\text{attempt}}
=
D_A * D_B * \delta_{c_r},
\]

where \(*\) is convolution. If outcome \(o\) occurs with probability \(p_o\),

\[
D_{\text{total}}
=
D_{\text{attempt}}
*
\left(\sum_o p_oD_o\right).
\]

A failure self-loop can be handled analytically as a geometric compound distribution instead of expanding infinitely many retries. For the simple “cost \(c\), success \(p\), otherwise retry” case,

\[
P(C_{\rm total}=nc)=(1-p)^{n-1}p,
\]

which gives the exact quantiles without simulation.

For more complicated policies, two practical choices are appropriate. First, discretized distributional dynamic programming can propagate probability mass until the remaining tail is below a chosen tolerance; the omitted mass gives an explicit numerical error bound. Second, Monte Carlo is easy and excellent for validating p90/p95 once the policy is fixed, but it should not be used as the only optimizer if the goal is a certified cheapest expected-cost policy.

### Human-readable tree

The UI should not show the raw Bellman graph first. Show the **greedy policy as a recipe tree**, collapsing identical subtrees:

```text
Target ES body
└─ Fracture attempt
   ├─ success 25% → TARGET
   └─ miss 75% → rebuild precursor
      └─ Recombinator
         ├─ donor A: isolated Global Defences
         │  └─ ...
         └─ donor B: ES base + flat Armour
            └─ Dread essence ...
```

For cyclic recycling, annotate the branch rather than unfolding it forever:

```text
31% → Global Defences + % Evasion   [continue]
44% → Global Defences only          [recycle as donor A]
25% → unusable                      [sell/discard]
```

The report should also explain *why* a temporary helper exists: for example, “Mana is not a target modifier; it is included because, under the selected recombinator model, increasing the prefix-pool size raises the probability of retaining two or three prefixes.” Current recombinator documentation and community testing explicitly describe affix-pool-size effects of this kind. citeturn829063search0turn829063reddit7

## Recommended architecture and guarantees

The recommended production design is a **three-level solver**.

At the bottom, preserve the existing exact single-item transition engine: given a concrete item class and an ordinary crafting action, enumerate the successor distribution and cost. This part remains a conventional stochastic-shortest-path Bellman backup. citeturn983240search4turn674926search9

In the middle, implement recombination as a lazy binary hyperaction. It requests two independently obtainable donors, evaluates the current recombinator transition model, and returns a probability distribution over output classes. Cache kernels by canonical donor signatures, because many nominal items induce the same recombination behavior.

At the top, run an LAO\*-style envelope search with lower and upper bounds. Expand only states and donor-pair regions reachable under the current best policy; perform exact value/policy iteration inside the explored graph; and stop only when every unexpanded region has a lower bound no better than the incumbent, up to a requested tolerance. LAO\* is specifically designed to combine heuristic expansion with dynamic programming in cyclic MDPs while avoiding evaluation of irrelevant states. citeturn946474search0turn946474search11

The guarantees should be reported exactly as follows:

**Exact mode:** optimal within the stated mechanics model if all reachable classes/actions are either explicitly evaluated or eliminated by proven dominance/infeasibility/admissible-bound pruning, and the Bellman residual plus unexplored lower-bound gap is below the numerical tolerance.

**\(\varepsilon\)-bounded mode:** if best feasible cost is \(U\) and the global lower bound over all unexplored alternatives is \(L\), return a certificate \(U-L\le\varepsilon\). This is an additive bound on expected cost.

**Heuristic mode:** helper caps, beam width, top-\(K\) recipes, arbitrary maximum tree depth, or “only pairs that directly add a target mod” invalidate the optimality certificate unless discarded branches retain lower bounds sufficient to prove they cannot matter.

For the stated 12-core desktop and seconds-to-minutes objective, I would brute-force all pairs in the 80- and 400-class regimes; use lazy exact generation for 19,600 classes; and require signature bucketing, Pareto pruning, abstract-mask lower bounds and best-first pair generation for 78,400 classes. The raw pair counts—3,240, 80,200, 192,089,800 and 3,073,319,200—make that transition in strategy unavoidable.

## References

Knuth, D. E., “A Generalization of Dijkstra's Algorithm,” *Information Processing Letters* 6(1), 1977. Knuth introduced the grammar problem and “superior functions,” generalizing Dijkstra-style label setting to derivation trees. citeturn523990search1turn523990search0

Gallo, G.; Longo, G.; Pallottino, S.; Nguyen, S., “Directed Hypergraphs and Applications,” *Discrete Applied Mathematics* 42, 1993. The paper develops reachability, paths, cuts and optimization algorithms for directed hypergraphs and connects them to AND/OR graphs and other applications. citeturn717148search0turn717148search1

Hansen, E. A.; Zilberstein, S., “LAO*: A Heuristic Search Algorithm that Finds Solutions with Loops,” *Artificial Intelligence*, 2001. LAO\* extends heuristic AND/OR search to cyclic MDP solution graphs using dynamic programming. citeturn946474search0

Bertsekas, D. P.; Tsitsiklis, J. N., “An Analysis of Stochastic Shortest Path Problems,” *Mathematics of Operations Research* 16(3), 1991. This is foundational SSP theory for expected total-cost control and policy/value iteration. citeturn674926search9turn983240search6

Etessami, K.; Stewart, A.; Yannakakis, M., “Polynomial Time Algorithms for Branching Markov Decision Processes and Probabilistic Min(Max) Polynomial Bellman Equations,” *Mathematics of Operations Research* 45(1), 2020. It studies least fixed points and algorithms for branching-MDP Bellman systems. citeturn983240search1

Model-Free Reinforcement Learning for Branching Markov Decision Processes, 2021. The work explicitly gives a min-linear fixed-point system whose least solution yields optimal expected total values for nonnegative-cost branching MDPs. citeturn983240search0

Guestrin, C.; Koller, D.; Parr, R.; Venkataraman, S., “Efficient Solution Algorithms for Factored MDPs,” *JAIR*. Factored MDPs can compress structured state spaces while leaving exact solution complexity dependent on interaction structure; the paper develops approximate dynamic-programming and LP methods. citeturn674926search5

Raghavan, A.; Joshi, S.; Fern, A.; Tadepalli, P.; Khardon, R., “Planning in Factored Action Spaces with Symbolic Dynamic Programming.” The method exploits structure in both state and action spaces and describes exact/approximate symbolic dynamic-programming approaches. citeturn674926search3

Pretolani, D., “A Directed Hypergraph Model for Random Time Dependent Shortest Paths,” *European Journal of Operational Research* 123(2), 2000. It gives a stochastic-routing interpretation through directed hypergraphs for special time-dependent network structures. citeturn946474search6

Krieger, S.; Kececioglu, J., “Shortest Hyperpaths in Directed Hypergraphs for Reaction Pathway Inference,” 2023. The paper emphasizes that general minimum-total-weight hyperpath problems can be NP-complete and gives an exact cutting-plane approach for large reaction networks. citeturn946474search9

Path of Exile Wiki, “Recombinator.” Current documentation describes predictable versus unpredictable recombination, base selection, item-level handling, affix-pool count distributions, eligibility rules and the uncertainty in modifier-selection weighting. citeturn829063search0

Path of Exile 3.26 patch documentation. Patch 3.26 added selectable modifiers with displayed success chance and possible input destruction while retaining unpredictable recombination. citeturn829063search2

Path of Exile 3.29 patch documentation. Patch 3.29 replaced the Bestiary split-into-two and split-into-three crafts with Talisman fracture crafts and changed Fractured Fossils so they no longer create split copies. citeturn211953search0turn688409search1

Craft of Exile. The public tool provides crafting probability calculations, simulations and cost estimates rather than a general optimal cyclic crafting-policy solver. citeturn829063search5

Recipinator. This open-source PoE recombinator optimizer uses dynamic programming, tracks top-\(K\) recipes, inventory failures, expected costs and base-item requirements, making it the closest game-specific prior art found for the proposed tree-search layer. citeturn846607search5

Persona/SMT fusion calculators. Existing implementations enumerate forward and reverse fusion recipes and, in newer tools, recursively construct fusion trees; their fusion transitions are predominantly deterministic rather than stochastic. citeturn244708search0turn244708search1turn244708search2turn244708search3

Factorio production planners. Current tools use flow balancing and in some cases linear programming to handle multi-output recipes, recycling and cyclic production networks, illustrating how recipe graphs can be optimized without explicit tree expansion when the objective is steady-state material flow. citeturn244708search9turn244708search10turn244708search11