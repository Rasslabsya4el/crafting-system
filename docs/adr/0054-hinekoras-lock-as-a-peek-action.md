# Hinekora's Lock is one solver action, a Peek: it throws every preview, then chooses

[Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) takes the Lock from [the research](../research/2026-10-31-hinekora-lock.md) ([#101](https://github.com/Rasslabsya4el/crafting-system/issues/101)). Hovering a currency over a locked item shows the exact result of using it next; looking is free and changes nothing; using one currency applies its shown result and ends the foresight (R1 to R5 of the note). The plan is therefore a policy with information: the dice of every previewable currency are thrown first, and the player chooses after. This ADR is how the solver holds that. Which currencies preview and what the Lock refuses is ADR-0055, the burn and the price ADR-0056, the report and the checks ADR-0057.

## The rule: previews are independent

Each currency's outcome is randomised separately under each Lock, and one outcome tells nothing about the others (owner, from play, [#106](https://github.com/Rasslabsya4el/crafting-system/issues/106) answer 2, 2026-11-01). This is an admitted rule of source kind `owner` (ADR-0005), not an approximate input: it is not listed under "Approximate inputs" and nothing is printed beside the plan to hedge it. Three facts follow:

- one draw per currency item under one Lock, fixed while the Lock stays (the wiki: every currency item of one type shows the same preview each time, R4);
- a new Lock, a relock after a burn included, throws every draw again, independent of the first;
- the best of several previews is better than the best of one, so several options at a state are worth more than their cheapest.

The research's "one-look" ceiling (a Peek of one option chosen before looking, valid for any correlation) existed only to cover a shared draw. It is **not built**.

## No stored state

Lock, look and react are taken inside one state. The foreseeing flag is never stored and the previews are never states, because every state a Lock can lead to is one the previewable actions already reach (note 6.4); the second solve below builds those it needs, among them states the Lock-free plan's pruning never built; a state with no `V_noLock` (the Lock-free solve never reached it) is offered the Lock, which is sound and only slower. Looking is free: the units of each option currency that the player hovers are kept, and an option's price `c_a` is charged only when it is used. Storing the previews would cost the product of the options' outcome counts per state (three currencies of 20 outcomes: 8,000 stored states per state), and one currency at a time (s, a, o) would multiply the state count by K, in the hundreds. The compressed state of ADR-0009 gains no component. A start item is never foreseeing in v1 (ADR-0055).

## The Peek kind

`solver` gains one generic kind beside `Action`: `Peek(label, cost=L, options, fallback)`, stdlib only. The solver still knows nothing of Path of Exile. At a state `s`:

- the **options** are `P(s)`, each with its price `c_a` and the kernel `K_a(s, .)` it already has as an ordinary action;
- the **fallback** is `F(s)`, the best way to give the Lock up (below);
- the backup is

  `V(s) = min( best plain action, L + E[ min( min_{a in P(s)} ( c_a + V(o_a) ), F(s) ) ] )`, with the `o_a` drawn independently from the `K_a`.

`Action(label, cost, outcomes)` cannot carry this: there the choice is made before the dice are thrown.

### The value is a sorted-tail sweep

With `X_a = c_a + V(o_a)` independent, `E[min(X_1..X_m, F)]` is the integral over `t` from 0 to `F` of the product over `a` of `P(X_a > t)`. Sort the distinct values of all options once, sweep, and multiply the tails: O(K log K + K m) for K outcomes in total and m options (m is at most about a dozen, the previewable currencies), against O(K) for a plain backup, and no product space. The weights are exact integers (the denominators multiply, a few big integers per Lock state), the values float64, converted once as ADR-0010 says. A hand test, checked by script on 2026-11-01: states goal 0, middle 30, brick 400; A costs 1 and gives 20/50/30%; B costs 2 and gives 10/80/10%. Without the Lock the best is B at 66. With the Lock before its price, and the fallback `F` = 66 (some action that is not previewable, a bench craft say, worth 66 to finish), the cost is **23.97** both by enumerating the 9 pairs and by the sweep, so the Lock pays below 42.03. It is the oracle of the build (ADR-0057).

### Options and the fallback

- The options at `s` are every action of the full catalog at `s` whose kind is previewable (ADR-0055), **one per currency item**; if two offers ever use one item, the cheaper is the option. **The pruning of offers does not apply to options**: neither the equal-kernel merge of ADR-0031 (two currencies with the same kernel are two independent draws, and the best of two is better than one) nor the bound pruning (an offer that the Lock-free optimum never needs, a Chaos Orb for instance, can still win as one more independent preview). The Peek takes its options from the catalog, before twins, merges and bound pruning, and only at the states where the Lock survives the pruning test below, so the extra kernels are built for few states.
- `F(s)` is the best action at `s` whose kind is not previewable: an unpreviewed action (bench, Harvest, beasts, recombinator, imprint), the restart by buying the start item, or a burn (ADR-0056). Doing any of them ends the foresight blind (note R7).
- An option never carries a `Need`: the only previewable two-input action, the Awakener's Orb, is not an option in v1 (ADR-0055). The fallback may hold actions with inputs (recombinator; the imprint has none, ADR-0060, but its states carry the held snapshots, which the fallback keeps); that is fine, because the Peek adds only its own backup, which is monotone and continuous, so the least-fixed-point argument of ADR-0022 covers it wherever it sits in a component, and under a fixed reaction the whole operator is affine.

## Solving it

- **Value iteration** from zero rises to the least fixed point, as in ADR-0022: the Peek backup is monotone and continuous.
- **Policy iteration.** The Peek is a minimum, over every reaction (a function from the thrown previews to a choice), of an affine backup: it is an ordinary MDP whose states are `(s, previews)`, collapsed by independence. Policy iteration starts from the Lock-free policy, which is proper, evaluates the chain that the current reaction induces (next section) and improves with the sweep. The reaction is computed from `V` by the sweep: take the option with the smallest `c_a + V(o_a)` if it is below `F(s)`, else give up.
- **`_certify` holds.** Under a fixed reaction the operator is affine and its constant term is positive (`L` and every cost are positive), which is all the identity `T_mu(aV) = a T_mu V + (1 - a) k` uses (ADR-0010, ADR-0022). `error_bound` keeps its meaning.
- **A reaction that never accepts is improper**: it is a probability-1 cycle through the give-up branch (a burn back to `s`), and the proper-policy analysis sees it. The Lock-free initial policy is proper, so the iteration never starts there.

## The reaction is an acceptance set; the policy expands into ordinary actions

The reaction is stored as an **acceptance set**, never as a threshold on `V`: the list of `(option, result state)` pairs the player accepts, ranked by `c_a + V(o)` with ties broken by state id and option order, a strict total order. Under a fixed acceptance set the Peek is replaced, in the policy graph only, by ordinary actions with fixed costs:

- the Lock (cost `L`) leads to the pseudo-state "apply a" with the chance that option `a` is the best accepted pair, or to "give up" with the chance that no pair is accepted. That chance is exact: `p_a(o)` times the product over the other options of the chance that their result is not ranked better, which is the same tails as the sweep;
- "apply a" (cost `c_a`) leads to each `o` with the chance that `a` wins with `o`, over the chance that `a` wins;
- "give up" is the fallback action. A burn that returns to `s` is a cycle through the Lock, which the SCC solver already handles (the exact self-loop elimination of ADR-0010 does not apply, because `V(s)` sits inside the Peek's minimum; value iteration slows as the chance of no acceptable preview nears 1, and policy iteration finishes it).

Besides the Lock's own node there are `m + 1` pseudo-states per Lock state (the `m` "apply a" nodes and "give up"), in the policy only. `risk.evaluate` (which needs one cost per action), the simulator, the given routes and the interval driver over rule axes (ADR-0033's `risk` ticket) see only ordinary actions. Under another rule reading the acceptance set stays and the chances are recomputed from that reading's kernels.

## The coarse level and exact pruning

- **The coarse level (ADR-0023).** The optimistic and pessimistic models read an option's kernel pushed through the block map; the variant argument of [#130](https://github.com/Rasslabsya4el/crafting-system/issues/130) is for backups linear in the kernel and does not carry over to the sorted-tail sweep. A query with a Lock offered anywhere has no coarse level, **unless the exact pruning below removes the Lock from every state**, tested against the pessimistic values (an upper bound on the exact Lock-free value, which is all the test needs). Otherwise the report says that the Lock is the reason there is no approximate answer, and a target's `actions:` can drop it. At the coarse level `c_min` is taken over the actions legal in at least one member of the block (the optimistic offer), which is a lower bound for every member and so keeps the test sound. An expensive target (R29's mirror-class steps) keeps the Lock at its expensive states and so has no coarse level unless it drops the Lock.
- **Exact pruning.** The Lock is offered at `s` only if `L + c_min(s) < V_noLock(s)`, with `c_min(s)` the smallest cost among the options and the fallback actions at `s`. This is exact: values are at least 0, so a Peek's value is at least `L + c_min(s)`, and adding the Lock can only lower `V`, so a state that fails the test never profits. A first solve without the Lock gives `V_noLock`, and the second solve starts from its proper policy. At the Lock's price, about 100,000 Chaos on 2026-10-31, this removes the Lock from every state whose Lock-free value is below roughly that price plus its cheapest action; a target worth a mirror keeps it at its expensive states, and the second solve is then larger. The build measures the time on R29 and tracks it against the one-minute goal (ADR-0010, ADR-0014); it is not assumed here. The Lock is a planner kind on by default; a target's `actions:` can drop it.

## Rejected

- Storing the previews, or one preview at a time, as states (above): 8,000 stored states per state, or K times the state count.
- A Peek whose options are kernels merged by equal kernel (ADR-0031): it counts two independent draws as one.
- Holding the reaction as a threshold on `V`: the policy would change under the evaluation that `risk` and the rule-axis driver run on other readings, and the pseudo-states could not be built.
- The one-look model: needed only for a shared draw, which the owner excluded.

Origin: [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) (round 1, answer 2, and the main chat's technical decisions in the round draft); [Hinekora's Lock in 3.29](../research/2026-10-31-hinekora-lock.md) sections 4 and 6; ADR-0005, ADR-0009, ADR-0010, ADR-0022, ADR-0023, ADR-0031.
