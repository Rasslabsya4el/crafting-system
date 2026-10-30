# Compressing the Item State of a Crafting MDP, With Measured Error

## Executive conclusions

The most important distinction is between **exact quotienting** and **approximate aggregation**. Exact lumpability and MDP bisimulation say that two concrete states can be merged only when their one-step behavior, viewed through the quotient, is identical; under those conditions the quotient is genuinely Markov and an optimal quotient policy lifts to an optimal ground policy. Approximate aggregation instead deliberately merges states whose behavior differs, so the compressed process is generally not a true MDP unless an additional distribution over the hidden concrete states is fixed. citeturn321875search11turn455099view1turn455099view2

For the crafting problem, **plain target-status + junk counts is too coarse to have a general guarantee**. Its hidden variable is the residual mod pool: which exclusion groups have disappeared, and—when mechanics inspect tags—which kinds of groups or existing mods remain. The practical abstraction should therefore be built around the **future interaction signature of the residual pool**, not around arbitrary mod identity. Exact symmetry reduction then becomes possible whenever two junk groups are interchangeable under every currently enabled action. This is precisely the kind of redundancy that MDP homomorphism and probabilistic symmetry-reduction methods are designed to exploit. citeturn293229search41turn293229search1

The strongest design for this application is therefore a refinement of your B/C ideas: keep target-mod status exactly, but represent junk by a **canonical multiset of behavioral group types**. A behavioral group type records everything about an exclusion group that any available craft can observe: its weight vector under the base, target-tier membership, relevant tag mask, influence constraints, and transformations under fossils/metamods/Harvest. Groups having identical such vectors are symmetric and need only a blocked-count, not an identity. Exceptional groups—especially target groups and groups containing stateful special mods—stay explicit. This can be an *exact* quotient if the signatures are genuinely identical; when signatures are deliberately coarsened, the same machinery becomes an approximate abstraction with measurable error. MDP homomorphisms and model-irrelevance abstractions provide the formal template for this statement. citeturn455099view0turn293229search41

For measured error, I would not use a single Monte-Carlo estimate as the primary certificate. Use **three layers**: an abstract-policy simulation on the exact concrete simulator; lower/upper value bounds from a game/interval abstraction that lets hidden concrete states choose optimistic or pessimistic transition kernels; and local diagnostics measuring how much concrete Bellman backups vary inside each aggregate. Game-based MDP abstraction was developed specifically to separate original nondeterminism from abstraction-induced nondeterminism and thereby produce lower and upper quantitative bounds. For stochastic-shortest-path problems, Bellman-residual bounds are also available under appropriate positive-cost/properness conditions. citeturn984657search17turn984657search30turn984657search37

A crucial qualification is that most of the clean classical approximation bounds—Van Roy’s aggregation bounds and the Ferns–Panangaden–Precup bisimulation metric bounds—are formulated for **discounted** MDPs. Your planner is an undiscounted stochastic shortest-path problem, so substituting \(\gamma=1\) into those bounds is invalid: the usual \(1/(1-\gamma)\) constants blow up. SSP-specific proper-policy theory, positive costs, residual bounds, or game/interval abstractions should supply the certificate instead. citeturn204236view2turn691170search6turn691170search7

## State aggregation and abstraction theory

**Strong and weak lumpability.** In plain language, a Markov chain is strongly lumpable when, after replacing each state by its aggregate label, the observed aggregate process is itself a Markov chain no matter how the original chain was initialized. The classical Kemeny–Snell condition is simple: for any two concrete states \(x,y\) in the same block \(B\), and every destination block \(C\), the summed probability of entering \(C\) must agree,
\[
\sum_{z\in C}P(x,z)=\sum_{z\in C}P(y,z).
\]
That condition is necessary and sufficient for ordinary/strong lumpability. Weak lumpability relaxes this requirement for a particular family of initial distributions; the aggregate can be Markov under those distributions even though the partition is not Markov for arbitrary initialization. Strong lumpability therefore gives an initialization-independent exact quotient; weak lumpability is less useful for a planner whose policy changes the occupancy distribution inside an aggregate. citeturn321875search11turn780706search6

Computationally, checking a proposed strong-lumping partition amounts to comparing transition sums into every block; once the finite transition graph is explicit this is linear to low-polynomial in its nonzero transitions, depending on representation. The coarsest ordinary lumping of a finite Markov chain can be found in \(O(m\log n)\) time for \(n\) states and \(m\) transitions using specialized partition-refinement data structures. That asymptotic result is excellent for a graph that already exists, but does not solve your fundamental problem: \(n\) and especially \(m\) cannot first be materialized. citeturn549970search7

“Approximate lumpability” is not one universally standardized object. Several literatures instead define quasi-lumpability, perturbed lumpability, or explicit error measures between the original and reduced chain. Recent work gives formal transient-distribution error bounds when an aggregate chain is not exactly lumpable, but those are Markov-*chain* results, not automatically optimal-control guarantees for an MDP. They are useful diagnostics for a fixed crafting policy, not sufficient by themselves to certify the optimal crafting policy. citeturn321875academia49turn321875search37

**MDP bisimulation.** Bisimulation is the control analogue of strong lumpability. Two MDP states are bisimilar when, for every action, their immediate rewards/costs agree and they place exactly the same probability mass into every equivalence class of the quotient. Givan, Dean and Greig show that quotienting by stochastic bisimulation preserves the information required for optimal control: an optimal policy in the quotient induces an optimal policy in the original MDP. Their largest bisimulation relation is the coarsest exact bisimulation quotient. citeturn455099view1turn455099view2

Formally, for equivalence relation \(\sim\),
\[
s\sim t \Longrightarrow
c(s,a)=c(t,a),\qquad
P(C\mid s,a)=P(C\mid t,a)
\]
for every action \(a\) and every block \(C\in S/{\sim}\). Givan et al. compute the greatest such relation by repeatedly splitting blocks that are unstable: if two states currently in the same block send different probability mass into some splitter block under an action, they must be separated. The method terminates at stochastic bisimilarity and performs only linearly many splits in the number of final blocks, although the cost of stability checks depends on the state representation. Their paper also shows how factored representations can perform block splitting symbolically rather than enumerate all ground states. citeturn455099view1

The pitfall for crafting is that exact bisimulation can be almost as fine as the concrete state space. If two blocked exclusion groups alter the residual spawn weights differently, the corresponding concrete item states are not bisimilar unless those differences cancel exactly after mapping successors to quotient blocks. Thus bisimulation gives the right *definition* of exactness, but naïvely computing its partition over \(10^8\)–\(10^{11}\) concrete states is infeasible. citeturn455099view2

**Bisimulation metrics.** Ferns, Panangaden and Precup replace the binary question “bisimilar or not?” with a distance. Their fixed-point metric combines immediate-reward difference with a Kantorovich/Wasserstein distance between successor distributions, where the transportation cost between successor states is itself the current state distance. Distance zero coincides with bisimulation, while small distance implies similar discounted optimal values. citeturn691170search11turn749068view0

A representative fixed-point form is
\[
d(s,t)=\max_a\left[
c_R|r(s,a)-r(t,a)|
+c_T\,W_d(P(\cdot\mid s,a),P(\cdot\mid t,a))
\right],
\]
with \(c_R+c_T=1\). When the discount factor satisfies the paper’s condition, the optimal value is Lipschitz in this metric; hence metric clustering provides a quantitative aggregation criterion rather than a yes/no relation. The original finite-state algorithm repeatedly solves transportation problems over state pairs and is polynomial but expensive; the paper reports an \(O(|A||S|^4\log |S|\cdot \log\delta/\log c_T)\)-type worst-case operation count for prescribed precision. Later on-the-fly work reduces practical effort by concentrating metric calculations on important pairs rather than exhaustively updating every pair. citeturn691170search1turn691170search2

For this project the conceptual value is high but direct use is limited: the metric assumes a finite state set on which pairwise distances can be evaluated, and its clean value bounds are discounted. It is better used as inspiration for a **local discrepancy score** between concrete representatives of an aggregate—e.g. transportation distance between their abstract successor distributions—than as the primary solver. citeturn691170academia10

**Li–Walsh–Littman’s abstraction hierarchy.** Their hierarchy distinguishes what information an abstraction preserves. Model-irrelevance requires equal reward and equal transition probability into every abstract block. \(Q^\pi\)-irrelevance merges states having identical action values for every policy; \(Q^*\)-irrelevance only requires identical optimal action values; \(a^*\)-irrelevance requires a common optimal action *and its optimal value*; and \(\pi^*\)-irrelevance only requires a common optimal action. These notions become progressively coarser:
\[
\phi_{\text{model}}
\preceq\phi_{Q^\pi}
\preceq\phi_{Q^*}
\preceq\phi_{a^*}
\preceq\phi_{\pi^*}.
\]
citeturn455099view0

For planning, their key result is that model-, \(Q^\pi\)-, \(Q^*\)- and \(a^*\)-irrelevance abstractions have an optimal abstract policy that is also optimal in the ground MDP, whereas a \(\pi^*\)-irrelevance abstraction can yield a suboptimal abstract solution. This is a genuine guarantee, not a heuristic. The practical catch is circularity: constructing the coarsest \(Q^*\)- or \(a^*\)-irrelevance partition generally requires knowledge of \(Q^*\) or optimal actions, which is approximately the problem you were trying to avoid solving. Model-irrelevance/bisimulation is therefore much easier to derive from the simulator alone. citeturn455099view0

**Value-iteration aggregation bounds.** Van Roy analyzes approximate value iteration in which a partition is chosen first and the value function is forced to be constant inside each block. For discounted problems, the projected Bellman operator has a fixed point and the error can be bounded in terms of how well \(J^*\) can be represented by blockwise constants. One of his main sup-norm bounds is
\[
\|\Phi\tilde r-J^*\|_\infty
\le
\frac{2}{1-\gamma}
\min_r\|J^*-\Phi r\|_\infty,
\]
and the greedy-policy performance bound contains another \(1/(1-\gamma)\) factor. He also shows that weighting the projection by an invariant distribution can substantially improve the performance-loss bound. citeturn312602view5turn204236view2

Those results are important warnings for crafting: small one-step aggregation error can turn into large long-horizon policy loss, and the worst-case amplification becomes severe as the effective horizon grows. But the theorem is not an SSP theorem; using it with \(\gamma=1\) gives no finite certificate. Bertsekas’ aggregation work and adaptive aggregation methods similarly emphasize coarse-to-fine aggregation and residual/error correction, but SSP certification should rely on SSP-specific theory. citeturn667669search40turn667669search15

**Newer results useful here.** Abel, Hershkowitz and Littman develop approximate versions of state-abstraction classes and prove bounded degradation of behavior in discounted finite MDPs; this is useful conceptually when you intentionally tolerate small within-block \(Q^*\) variation. More directly relevant to an undiscounted crafting planner, Hansen derives computable suboptimality bounds from the Bellman residual for stochastic-shortest-path problems, including positive-cost settings where not every policy is proper. Merge-and-shrink theory has also recently been extended specifically to SSPs and identifies abstractions that yield admissible or perfect heuristics. citeturn541124search0turn984657search37turn984657search35

The comparison most relevant to implementation is:

| Method | Guarantee | Computational character | Lazy? | Fit for crafting |
|---|---|---|---|---|
| Strong lumpability | Exact Markov quotient for a fixed chain, all initial distributions | Proposed partition easy to test; coarsest finite-chain lumping \(O(m\log n)\) | Only after successor structure is available | **Partly**: useful for policy evaluation, not enough for control unless enforced actionwise |
| Weak lumpability | Exact aggregate chain only for certain initial distributions | Depends on occupancy/initial distribution; more fragile | Poor | **No** as main abstraction; policy changes invalidate the hidden occupancy assumption |
| MDP bisimulation / model-irrelevance | Exact values; optimal quotient policy lifts exactly | Partition refinement; symbolic implementations possible | **Partly** | **Yes**, as the definition of an exact abstraction |
| Bisimulation metric | Quantitative discounted value-similarity bound | Transportation problem for many state pairs; expensive | **Partly**, via on-the-fly variants | **Partly**: useful discrepancy score, poor direct fit at concrete scale |
| \(Q^*\)-irrelevance | Exact optimal \(Q\) preserved | Requires \(Q^*\) knowledge in general | No practical shortcut known | **Conceptually yes, computationally circular** |
| \(a^*\)-irrelevance | Common optimal action/value; abstract optimum lifts | Also depends on optimal-value information | No | **Conceptually yes, computationally circular** |
| Approximate \(Q^*\) abstraction | Bounded discounted policy loss | Requires estimating value differences | Yes with samples | **Partly**, but bounds are discounted |
| Symmetry / MDP homomorphism | Exact if the group action preserves costs and dynamics | Canonicalization can be cheap once symmetries are known | **Yes** | **Excellent** for interchangeable junk groups |
| Game/interval abstraction | Lower/upper quantitative bounds | Solve a larger robust/game abstraction | **Yes** if kernels can be bounded lazily | **Excellent for certification/refinement** |
| CEGAR / adaptive refinement | Exact in limit if refinement reaches ground model; intermediate bounds depend on abstraction framework | Concentrates work on ambiguous blocks | **Yes** | **Excellent** |
| SSP Bellman-residual bounds | SSP-specific suboptimality certificate under stated conditions | Cheap once candidate value/policy exists | **Yes** | **Excellent auxiliary certificate** |

The exact-quotient statements in the table follow from Kemeny–Snell and Givan et al.; the \(Q^*/a^*\) policy guarantees are Li–Walsh–Littman’s; metric bounds are Ferns et al.; the robust-bound and refinement entries follow the probabilistic abstraction-refinement literature. citeturn321875search11turn455099view1turn455099view0turn691170search11turn984657search30

## Deriving the abstraction from the simulator

**Partition refinement** gives the coarsest exact model-irrelevance/bisimulation quotient compatible with an initial partition. Start with states separated by immediately observable distinctions—goal versus non-goal, action availability and immediate action cost—and repeatedly split any block whose members have different probabilities of reaching some current block under some action. When it stabilizes, the result is the coarsest stochastic bisimulation refining the initial partition. citeturn455099view1turn549970search7

The obstacle is not the refinement algorithm but successor generation. A standard explicit refinement method assumes that the states and transitions it compares can be accessed. If a single Alchemy transition already produces roughly \(10^5\) concrete outcomes in your simulator, merely populating the transition graph dominates any \(O(m\log n)\) minimizer. Givan et al.’s factored treatment is the important exception: their block-splitting operations can work against a symbolic factored representation without enumerating the entire ground state space, but efficiency depends on whether your crafting transition rules admit compact symbolic partitions. citeturn455099view1

**Feature/relevance selection** should therefore happen structurally before partition refinement. Treat each concrete attribute—target tier, rolled value, exclusion group, tag mask, crafted/fractured flag, rarity, etc.—as a candidate feature. An attribute may be discarded exactly only if, conditional on the retained features, it cannot change immediate cost, action availability, goal status, or the distribution of retained features after any action. That is simply model-irrelevance expressed in a factored state representation. If dropping a feature merely leaves small transition differences, the result is heuristic/approximate and needs later error measurement. citeturn312602view0turn455099view0

For the crafting simulator, this analysis can be automated by instrumenting the transition code. For each action, record which concrete item fields are read when computing eligibility, weights, forced-tag conditions, removability, protected sides, and successor fields. Propagate relevance backward from the target predicate and action costs until reaching a fixed point. Such dependency analysis gives a *sufficient* structural abstraction; it need not be the coarsest semantic one because two different dependencies can still cancel numerically. Semantic equivalence requires transition comparison or symbolic algebra. This distinction between structural sufficient conditions and semantic minimality is standard in factored model minimization. citeturn103406view2

**Symmetry reduction** is unusually promising. If a permutation of junk-mod identities leaves action availability, action cost and transition probabilities invariant, the permutation is an MDP automorphism; states in the same orbit can be replaced by one canonical representative. Probabilistic model-checking work constructs quotient MDPs from such automorphism groups, and MDP/SMDP homomorphism theory formalizes the same structure-preserving reduction. citeturn293229search1turn293229search41

For your data, do not search for arbitrary permutations of thousands of mods. Construct them from **behavioral equivalence of exclusion groups**. For each group \(g\), calculate a vector describing every way the enabled action set can see that group: the list of spawn weights by action/filter, membership of target mods and tiers, all relevant tag predicates, influence/base eligibility, and whether drawing a member creates any special persistent flag. If two groups have identical vectors and no externally named identity, permutations among them are exact symmetries. The concrete blocked-set can then be canonicalized to “two blocked groups of type 7, one blocked group of type 11,” rather than three group IDs. This is an exact reduction by construction if the signature includes every observable interaction. The homomorphism/symmetry guarantee, not statistical similarity, is what makes that statement exact. citeturn293229search41turn293229search42

**On-the-fly abstraction** is feasible when coupled to canonicalization. Generate only abstract states reachable from the requested initial item, and for each transition enumerate successor *signatures* rather than successor concrete identities. Real-time dynamic-programming work has explicitly combined symmetry exploitation with reachable-state search; on-the-fly bisimulation-metric algorithms likewise focus computation on state pairs that matter first. citeturn293229search5turn691170search2

Pure Paige–Tarjan refinement cannot magically remain lazy if deciding that two reachable abstract states differ requires enumerating millions of hidden successors. The viable lazy path is instead: symbolic/canonical successor generation first, then refinement over the resulting compact signatures. In other words, use domain structure to remove the enormous branching factor before calling generic abstraction algorithms. citeturn455099view1turn549970search7

## Candidate crafting-state designs and state counts

To make the counts comparable, define \(r\) as the average number of **present states per target mod**, excluding “absent.” A present state should distinguish everything about a target mod that can affect future planning—for example exact relevant tier plus whether its current roll passes the requirement. If a target mod has three relevant present states, use \(r=3\). These counts are engineering counts derived from the state definitions below, not claims from the cited literature.

For one side containing three target mods, if \(m\) targets are present, only \(3-m\) slots remain for junk. Under design A, junk is represented only by its count \(j\in[0,3-m]\). The number of side states is therefore
\[
N_A^{\rm side}
=\sum_{m=0}^{3}\binom 3m r^m(4-m)
=4+9r+6r^2+r^3.
\]
For \(r=3\), this is \(112\) per side and \(112^2=12{,}544\) prefix/suffix core states. For \(r=4\), it is \(200^2=40{,}000\). If your varying flags have roughly \(F=64\) reachable combinations, those become about \(0.80\) million and \(2.56\) million respectively; the exact multiplier should be measured because many nominal flag combinations are illegal.

**Design A — target state + junk count + flags.** This exactly represents capacity, target satisfaction, uniform annulment between categories if all junk is equivalent with respect to removability, rarity restrictions, and any action whose outcome depends only on the retained target/flag fields and number of occupied slots. It does **not** exactly represent future weighted additions whenever two hidden junk identities block different exclusion groups or differ under any tag-sensitive future mechanic. The resulting abstract transition kernel must therefore average over hidden junk identity, and that average is occupancy-distribution dependent. State abstraction is known to become non-Markovian in precisely this situation: the next abstract distribution depends on which concrete states inside the aggregate are currently occupied. citeturn984657search36

A practical A-kernel is
\[
\bar P(z'\mid z,a)
=\sum_{s:\phi(s)=z}\mu_z(s)
\sum_{s':\phi(s')=z'}P(s'\mid s,a),
\]
where \(\mu_z\) is an assumed conditional distribution of concrete items inside aggregate \(z\). This is a **heuristic** unless the right-hand inner distribution is identical for every \(s\in z\); if it is identical, A has accidentally satisfied model-irrelevance and becomes exact. citeturn312602view0

**Design B — target state + counts by interaction class.** Let \(C\) be the number of junk classes and represent a side by a vector \((j_1,\ldots,j_C)\) with total junk at most the remaining capacity. The number of nonnegative count vectors with total at most \(L\) is \(\binom{L+C}{C}\), giving
\[
N_B^{\rm side}
=\sum_{m=0}^3
\binom3m r^m
\binom{3-m+C}{C}.
\]
With \(r=3\), a coarse three-class scheme such as attack/caster/other gives \(245^2=60{,}025\) core states. Six interaction classes give \(552^2=304{,}704\); ten give \(1{,}204^2\approx1.45\) million before flags. This shows why storing independent Boolean tag bits is dangerous: the Cartesian product of Harvest, fossil and metamod tags can create more abstract states than the useful behavioral distinctions warrant.

B is exact if class membership contains every property of existing junk that can influence all future actions **and** if two members of a class block behaviorally interchangeable groups. Merely recording “attack/caster/other” does not satisfy the second condition: two attack-tagged junk mods may block different group-level residual weights. B is nevertheless much better than A because it makes many metamod/tag interactions observable and therefore reduces within-block transition variance.

**Design C — target state + exact blocked exclusion-group set.** Let \(G\) be the number of possible junk groups on a side. Ignoring reductions from already-present target groups, a side has
\[
N_C^{\rm side}
=
\sum_{m=0}^{3}
\binom3m r^m
\sum_{j=0}^{3-m}\binom Gj.
\]
For \(r=3\) and \(G=10\), this is \(1{,}004\) side states, or about \(1.01\) million prefix/suffix core states; at \(G=20\) the core rises to about \(14.8\) million, and at \(G=40\) to about \(370\) million. Thus raw group-set tracking can eliminate most approximation error but recreate the state explosion you were trying to avoid.

Under the mechanics you specified, C exactly captures the effect of junk identity on future pool eligibility **provided** no future action distinguishes two junk mods in the same blocked group through some additional persistent property. If existing-junk tag identity matters to removals or other mechanics, add a tag/signature label for the occupant. Annulment remains simple because its choice is uniform over removable existing mods; spawning and reroll kernels can be computed exactly from the residual group-level weights.

**Design D — recommended: target state + blocked behavioral-group multiset.** First partition exclusion groups into symmetry types \(h=1,\ldots,H\). A type is defined by an exact vector of behavior under every enabled action and every target-relevant outcome. State stores the number of currently blocked groups of each type, plus explicit identities for exceptional groups that are not exchangeable. If all groups in a type are truly permutable automorphisms, this quotient is exact. citeturn293229search1turn293229search41

If all blocked groups can be represented by \(H\) exchangeable types, its combinatorial count has the same stars-and-bars form as B but \(H\) now describes **group symmetry classes**, not arbitrary tag classes:
\[
N_D^{\rm side}
=
\sum_{m=0}^3
\binom3m r^m
\binom{3-m+H}{H}.
\]
For \(r=3,H=4\), that is \(332^2=110{,}224\) core states; for \(H=5\), \(434^2=188{,}356\). These numerical examples are not predictions about your 3.29 data—the actual \(H\) must be computed from the PoB pool—but they show the intended regime: closer to B’s state count with C’s exactness.

For transition computation, **pool-signature caching** is preferable to Wallenius as the general mechanism. A cache key should contain open sides, target groups already blocked, blocked behavioral-group counts, action tag filter, fossil multipliers, metamod exclusions and any forced-tag requirement. Equivalent keys share the same transition kernel. This directly exploits the state abstraction instead of repeatedly enumerating mod IDs.

Wallenius’ multivariate noncentral hypergeometric law is the right mathematical model for sequential biased sampling without replacement when items belong to weighted classes and the odds stay class-defined during the urn process. citeturn742425search0turn742425search26 In your rerolls, however, selecting one mod can eliminate its **entire exclusion group**, changing the set and total weights of future candidates in a group-specific way. Therefore a single Wallenius draw over coarse tag classes is generally **not exact**. It becomes exact only when removal after a draw is equivalent to ordinary removal of the sampled unit/class under the chosen representation. Dynamic programming over group-level pool signatures is safer and, because only up to six affixes are drawn, has shallow depth.

## Recommended implementation

The representation I would implement is a hybrid of B, C and symmetry reduction:

```text
TargetStatus:
    ABSENT
    or PRESENT(
        target_id,
        tier_bucket,          # exact tier when it changes Divine/satisfaction behavior
        roll_good,
        fractured,
        crafted_if_relevant
    )

GroupType:
    canonical tuple(
        side,
        vector_of_spawn_weights_under_each_enabled_filter,
        target_outcome_vector,
        relevant_tag_mask,
        influence/base eligibility,
        persistent_special_effect_class
    )

AbstractState:
    rarity
    prefix_targets[3]
    suffix_targets[3]

    # Exact exceptional blocked groups:
    exceptional_blocked_prefix_groups
    exceptional_blocked_suffix_groups

    # Counts of blocked interchangeable groups:
    blocked_prefix_group_type_counts[H_p]
    blocked_suffix_group_type_counts[H_s]

    prefix_junk_occupant_classes   # only if existing-junk tags/removability matter
    suffix_junk_occupant_classes

    fractured_descriptor
    crafted_descriptor
    metamod_flags
    influence_flags
    eldritch_dominance
```

This representation is an exact bisimulation/homomorphic quotient if every concrete state mapping to the same structure has identical action costs and identical transition mass into every resulting abstract state. That is the model-irrelevance test from Li–Walsh–Littman and the stochastic-bisimulation condition of Givan et al. citeturn312602view0turn455099view2

The abstract transition function should use exact group-level dynamic programming whenever the state signature is certified exact:

```text
abstract_transition(z, action):
    sig = pool_signature(z, action)

    if kernel_cache.contains(sig):
        return kernel_cache[sig]

    frontier = {(sig, probability=1)}

    for each required draw/removal stage of action:
        next_frontier = {}

        for partial_sig, p in frontier:
            candidates = behavioral_group_candidates(partial_sig, action)

            for outcome_type, q in weighted_outcomes(candidates):
                sig2 = update_signature(partial_sig, outcome_type)
                z2_partial = update_item_summary(z, outcome_type)
                next_frontier[(sig2, z2_partial)] += p*q

        frontier = coalesce_identical_signatures(next_frontier)

    result = map_final_signatures_to_AbstractState(frontier)
    kernel_cache[sig] = result
    return result
```

Coalescing after **each draw** is important. Sequential weighted sampling without replacement is path-dependent; two draw sequences that lead to the same residual behavioral pool may safely merge, while two sequences that merely have the same tag counts may not. This is the same general principle as exact quotienting by future behavior rather than by historical identity. citeturn455099view2turn742425search20

Where a signature is deliberately approximate, define its kernel from a conditional mixture over sampled concrete representatives and simultaneously retain a dispersion statistic:

```text
approx_kernel(z, a):
    reps = representative_concrete_states(z)

    kernels = [
        project_to_abstract(exact_concrete_transition(s, a))
        for s in reps
    ]

    P_bar = weighted_average(kernels, occupancy_weights)

    discrepancy = max_pairwise_transition_distance(kernels)
    backup_range = max_s BellmanBackup(s) - min_s BellmanBackup(s)

    return P_bar, discrepancy, backup_range
```

The refinement loop should then be value-directed rather than blindly splitting every discrepancy:

```text
repeat:
    solve current abstract SSP -> V_bar, pi_bar

    construct optimistic and pessimistic abstract/game bounds
        -> L, U

    simulate pi_bar in exact concrete simulator
        -> concrete cost estimate + confidence interval

    for reachable abstract states z:
        estimate:
            occupancy(z)
            within-block Bellman backup range
            transition disagreement by discarded feature
            policy-action disagreement among concrete representatives

        score(z) =
            occupancy(z)
            * backup_range(z)
            * value_sensitivity(z)

    if start-state bound gap and simulation uncertainty are acceptable:
        stop

    z = highest-scoring block

    choose discarded feature/group distinction that most
    reduces transition or Bellman variance

    split z
    invalidate only affected pool-signature kernels
```

This is a CEGAR-like progressive abstraction. Classical CEGAR repeatedly analyzes a coarse model, finds an abstraction-induced counterexample or ambiguity, and splits only the responsible block; probabilistic MDP frameworks extend the idea using abstraction-induced nondeterminism and quantitative bounds. citeturn549970search8turn984657search30

The best splitting feature is usually **not** “which concrete mod ID?” but “which omitted future interaction?” For example: a blocked group changes the total attack-prefixed spawn weight by 37%; a discarded Harvest tag determines whether the forced-tag pool has one or three groups; or an exceptional group contains a target tier. This preserves the possibility of later symmetry merging.

## Measuring compression loss and diagnosing failures

The error study should be reproducible for every target item and should report both expected-cost loss and where the loss comes from.

1. **Freeze the abstraction and solve it completely.** Record the abstract start-state value, policy, convergence tolerance, number of reachable abstract states and number of cached pool signatures. Do not change the abstraction during the evaluation run; otherwise sampling and value errors become inseparable.

2. **Evaluate the abstract policy against the exact concrete simulator.** At each concrete state \(s\), map to \(z=\phi(s)\) and execute \(\bar\pi(z)\), but let the exact simulator sample the concrete successor. Independent complete crafting episodes then estimate \(J_{\bar\pi}(s_0)\), which is a genuine value of the concrete MDP under the lifted policy rather than the value predicted by the approximate quotient.

3. **Treat rare transition probabilities separately from total-cost estimation.** For a Bernoulli event with probability \(p=0.001\), \(n=\log(0.05)/\log(0.999)\approx2{,}994\) trials are required merely to have 95% probability of seeing the event at least once. Roughly \(10{,}000\) trials give only ten expected occurrences; about \(25{,}000\) give a binomial relative standard error near 20%, and about \(100{,}000\) near 10%. Report exact or conservative binomial intervals for such events rather than “0 occurrences means zero probability”; Clopper–Pearson is the classical exact construction. citeturn984657search2

4. **Estimate episode-cost uncertainty, not only transition uncertainty.** SSP episode costs can have long tails when failure causes repeated expensive resets. Report mean, standard error/confidence interval, high quantiles, maximum observed cost and the fraction of mean cost contributed by the top 1% of episodes. If rare tails dominate the mean, plain Monte Carlo may require far more samples than the per-step rare-event calculation suggests; use targeted conditional simulation or importance sampling as a diagnostic, while keeping an unbiased ordinary simulation as the headline estimate.

5. **Compute an optimistic lower value and pessimistic upper value on each aggregate.** Let \(\mathcal K(z,a)\) be the set of concrete projected kernels attainable by states inside aggregate \(z\). An optimistic abstraction lets a fictitious controller choose the most favorable hidden concrete realization, while a pessimistic/robust abstraction chooses the least favorable one after the abstract action. This is the stochastic-game abstraction principle used to turn abstraction nondeterminism into lower and upper quantitative bounds. For expected-cost SSPs, enforce properness and positive-cost assumptions required by the solver; otherwise a pessimistic game can create artificial nontermination. citeturn984657search17turn691170search13

6. **Use the Bellman residual as an independent SSP diagnostic.** Evaluate how far the candidate value function fails the concrete Bellman equation on sampled or symbolically covered concrete states. SSP-specific results show that Bellman residuals can provide suboptimality bounds under positive-cost and related conditions where ordinary discounted contraction arguments do not apply. This is especially useful because it tests the decision equation directly rather than trusting the aggregate transition model. citeturn984657search37

7. **Locate error spatially.** For every frequently visited aggregate \(z\), sample concrete members and compute each action’s exact one-step backup using the current continuation value. Record the range of backups, disagreement about the greedy action, and variation of projected successor distributions. Weight those quantities by visitation probability under the abstract policy. A large discrepancy in an unreachable state is harmless; modest disagreement in a state visited on 80% of failed crafts can dominate expected cost.

8. **Test explicitly for hidden history dependence.** Gather visits to the same aggregate \(z\) and split them by provenance: preceding action, number of rerolls, previous aggregate, or hidden blocked-group signature. If the empirical next-aggregate distribution changes materially after conditioning on provenance, then \(z_t\) is not Markov. This is the characteristic failure of state aggregation when the occupancy distribution inside an aggregate carries information omitted from the state. citeturn984657search36

9. **Refine using the responsible hidden variable.** If variation comes mainly from one exclusion group, split that group from its current class. If it comes from a tag combination, split the behavioral signature on that tag. If several identities remain indistinguishable under every action, keep them symmetric. CEGAR’s central principle is exactly this: refine only abstraction distinctions implicated by the current error/counterexample. citeturn549970search8

10. **Report a trust envelope, not a single number.** A useful route report should say, for example: “abstract predicted cost 4.83 div; exact-policy simulation 4.91 ± 0.06 div at 95%; certified abstraction interval 4.72–5.08 div; estimated policy regret relative to the lower bound ≤0.36 div; 91% of the remaining bound gap comes from two aggregate states involving blocked attack-prefix groups.” A human can then distinguish numerical solver tolerance, Monte-Carlo uncertainty and abstraction uncertainty instead of seeing them collapsed into one unexplained expected cost.

The most serious operational pitfall is **policy reversal**. Two concrete states can have nearly equal values but different best actions; aggregation averages them and selects an action that is poor for one hidden state. Li–Walsh–Littman explicitly distinguish value-preserving and action-preserving abstractions because preserving only coarse policy information is not enough to guarantee that solving the abstract MDP reproduces the ground optimum. Detect this by tracking the action-gap
\[
\Delta(s)=Q(s,a_{(2)})-Q(s,a_{(1)})
\]
for cost minimization and comparing within-block backup variation with that gap. If abstraction error exceeds the local action gap, the chosen action is unstable even when total-value error looks small. citeturn455099view0

A second pitfall is **averaging-kernel drift**. If \(\bar P\) is estimated using the conditional distribution of junk identities seen under one policy, changing the policy changes that conditional distribution and hence the “correct” aggregate kernel. The quotient is then policy-dependent and non-Markov. Detection is the history/provenance test above; repair is either refinement or explicitly treating hidden identity as belief state, which is usually too expensive for this planner. citeturn984657search36

A third pitfall is **improper SSP behavior** introduced by abstraction. An aggregate transition can create a spurious self-loop or conceal that one concrete member has a zero-probability escape to goal. Stochastic-shortest-path theory requires care about proper policies and conditions under which dynamic programming has the desired solution. Track goal-reach probability and expected hitting time under the lifted policy separately from expected currency cost, and reject aggregates whose pessimistic model admits nontermination unless that possibility exists concretely. citeturn691170search7turn984657search37

Finally, **floating-point equality is unsuitable for discovering exact bisimulation**. Spawn-weight sums and normalized transition probabilities can differ because of accumulation order even when the underlying rational/integer weights are semantically identical. Build canonical signatures from integer game weights and exact combinatorial counts wherever possible, and normalize only at the final probability calculation. Givan et al.’s refinement requires true equality of block transition probabilities for an exact quotient; numerical near-equality should instead enter the approximate/refinement path. citeturn455099view1

## Recommended choice

For a one-machine Python/Numba implementation with a seconds-to-minutes target, I would start with **Design D**, not A, B or raw C. Build behavioral exclusion-group types once from the mod pool and active action set; preserve target groups and special-state groups explicitly; canonicalize interchangeable junk groups by counts; and cache transition kernels by the resulting residual-pool signature. This attacks the dominant combinatorics *before* the MDP solver sees them and can be exact whenever the group typing establishes a true automorphism/homomorphism. citeturn293229search41turn293229search1

Where the exact group typing still creates too many types, merge only the least important types and mark those merges “approximate.” Then solve a coarse SSP, evaluate its policy in the concrete simulator, construct optimistic/pessimistic bounds from sampled or symbolically characterized within-block kernels, and split the aggregates with the largest visitation-weighted Bellman disagreement. That provides an anytime continuum: the first model can be close to B, repeated refinement approaches C or exact bisimulation only where necessary, and symmetric regions never need to expand to concrete mod IDs. This is much better aligned with probabilistic CEGAR and adaptive aggregation than choosing one global hand-written granularity. citeturn549970search8turn667669search40turn984657search30

I would **not** use multivariate Wallenius as the main reroll engine. Use direct shallow dynamic programming over residual group signatures, with Wallenius only as an exact shortcut for subproblems that really are biased urn sampling without group-dependent state changes. citeturn742425search0turn742425search26

I would also avoid claiming a discounted bisimulation/Van-Roy error number for this planner. Those results are valuable theoretical guides, but the reported production certificate should be SSP-specific: concrete policy evaluation, optimistic/pessimistic abstraction bounds, Bellman residuals, and explicit rare-event confidence intervals. citeturn204236view2turn691170search6

## References

| Reference | Relevance |
|---|---|
| J. G. Kemeny & J. L. Snell, *Finite Markov Chains*, lumpability chapters | Classical strong/weak lumpability criteria. citeturn780706search6turn321875search35 |
| S. Derisavi, H. Hermanns & W. H. Sanders, “Optimal State-Space Lumping in Markov Chains,” 2003 | \(O(m\log n)\) coarsest finite-chain lumping. citeturn549970search7 |
| R. Givan, T. Dean & M. Greig, “Equivalence Notions and Model Minimization in Markov Decision Processes,” *Artificial Intelligence*, 2003 | Stochastic bisimulation, exact quotienting and partition refinement for MDPs. citeturn103406view2turn455099view1 |
| N. Ferns, P. Panangaden & D. Precup, “Metrics for Finite Markov Decision Processes,” UAI/AAAI 2004 | Bisimulation metrics and discounted optimal-value bounds. citeturn691170search11turn691170academia10 |
| G. Comanici, P. Panangaden & D. Precup, “On-the-Fly Algorithms for Bisimulation Metrics” | Lazy/priority computation of approximate bisimulation metrics. citeturn691170search2 |
| L. Li, T. J. Walsh & M. L. Littman, “Towards a Unified Theory of State Abstraction for MDPs,” 2006 | Model-, \(Q^\pi\)-, \(Q^*\)-, \(a^*\)- and \(\pi^*\)-irrelevance hierarchy and planning guarantees. citeturn103406view1turn455099view0 |
| B. Van Roy, “Performance Loss Bounds for Approximate Value Iteration with State Aggregation,” *Mathematics of Operations Research* 31(2), 2006 | Discounted projected value-iteration and policy-loss bounds. citeturn103406view0turn312602view5 |
| D. P. Bertsekas & J. N. Tsitsiklis, *Neuro-Dynamic Programming*, 1996; D. Bertsekas & D. Castañon, “Adaptive Aggregation Methods for Infinite Horizon Dynamic Programming,” 1989 | Classical aggregation, approximation and adaptive refinement. citeturn667669search14turn667669search40 |
| D. P. Bertsekas & J. N. Tsitsiklis, “An Analysis of Stochastic Shortest Path Problems,” *Mathematics of Operations Research*, 1991 | Foundations for undiscounted SSPs and proper-policy reasoning. citeturn691170search7 |
| E. A. Hansen, “Suboptimality Bounds for Stochastic Shortest Path Problems,” UAI 2011 | SSP Bellman-residual suboptimality bounds. citeturn984657search37 |
| D. Abel, D. Hershkowitz & M. Littman, “Near Optimal Behavior via Approximate State Abstraction,” ICML 2016 | Approximate state-abstraction value-loss theory. citeturn541124search0 |
| B. Ravindran & A. G. Barto, “SMDP Homomorphisms: An Algebraic Approach to Abstraction,” IJCAI 2003 | Exact structure-preserving abstractions and symmetries. citeturn293229search41 |
| M. Kwiatkowska, G. Norman, D. Parker et al., work on game-based abstraction/refinement for MDPs | Abstraction-induced nondeterminism, lower/upper bounds, refinement. citeturn984657search17turn984657search30 |
| R. Chadha & M. Viswanathan, “A Counterexample Guided Abstraction-Refinement Framework for Markov Decision Processes,” 2010 | Probabilistic CEGAR. citeturn549970search8 |
| “A Theory of Merge-and-Shrink for Stochastic Shortest Path Problems,” 2023 | SSP-specific exact/admissible abstraction theory. citeturn984657search35 |
| A. Fog, “Calculation Methods for Wallenius’ Noncentral Hypergeometric Distribution” and “Sampling Methods for Wallenius’ and Fisher’s Noncentral Hypergeometric Distributions,” 2008 | Biased sampling without replacement and multivariate Wallenius models. citeturn742425search0turn742425search26 |
| C. J. Clopper & E. S. Pearson, “The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial,” *Biometrika*, 1934 | Exact binomial confidence intervals for rare transition probabilities. citeturn984657search2 |
| F. Michel & M. Siegle, “Formal Error Bounds for the State Space Reduction of Markov Chains,” 2024/25 | Modern finite-time error analysis for approximate Markov-chain aggregation; useful for fixed-policy diagnostics rather than MDP optimality. citeturn321875academia49 |