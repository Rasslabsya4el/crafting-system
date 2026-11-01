# Recombinators are reported as a best/worst interval

**Amended by [ADR-0033](0033-the-unpredictable-recombinator.md)** ([grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94)): the admission rule below is contradicted by the data and replaced; see "Amendment" at the end. The rest stands.

The wiki says recombinator mod selection is weighted but gives no formula, so the planner commits to no single selection rule and drops the old prototype's equal-chance assumption. The admissible rules are those under which the chance to keep a mod does not fall as its spawn weight falls (rarer mods are kept at least as often as common ones; official 3.25.1 note and the wiki); equal chance is the boundary of that set. The wiki's kept-count table (66.7/33.3, 10/60/30, 30/70) is admitted.

A report shows the route with the best worst case and its [best; worst] interval, and beside it the best route without recombinators. (Replaced by the plan at one exponent and its interval; see the amendment below.)

The B3 grill computes the interval and revisits the selection rules against the owner-trusted 3.25 recombinator guide, under ADR-0005.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q3, [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q11.

## Amendment: the family `weight^alpha`, planned at one, shown as an interval ([grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), 2026-11-01)

[Research #90](https://github.com/Rasslabsya4el/crafting-system/issues/90) and the fit of [#175](https://github.com/Rasslabsya4el/crafting-system/issues/175) contradict the admission rule above: the guide's author writes that rare, low-weight mods are kept **less** often, and the fit of 68 observations excludes equal chance and rarer-favoured rules (`alpha` at or below 0, for a chaos-resistance weight of 500 or less; at 1000 the gloves alone would not reject it) and does not exclude weight-proportional.

- **The family.** Successive draws without replacement, `P(next = m)` proportional to `weight(m)^alpha`. The old "rarer mods are kept at least as often" rule is dropped; equal chance (`alpha = 0`) is now outside the data, not the boundary of the set. The wiki's count table stays admitted, with the guide's as the first case (ADR-0033).
- **The plan** uses `alpha = 1` (owner, round 1 answer 1: plan by the best estimate), and the answer is marked approximate (ADR-0028), the reason "fitted on 40 + 28 observations, weights 250 to 1500; weights below 250 extrapolated".
- **The interval** is the cost of the plan under every reading of the **grid** `alpha` in 0.4, 0.7, 1.0, 1.3, 1.6 (the fitted range, replacing the first round's [0, 1]), shown beside the plan, **with the best route without recombinators** as before.
- **The extremes are not at the ends** (interior extremes in 132 of 1,200 random cases), so the grid is always evaluated in full: `k` solves and `k^2` evaluations (ADR-0022, reworded). The same cross-evaluation gives the route with the best worst case and the certified bracket of ADR-0022; the report names that route beside the plan when it differs. The Awakener's group conflict (ADR-0032) has its own two-reading interval but no comparison route: the best route without recombinators is the only one shown.

Origin of the amendment: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), "Selection rule after #175"; ADR-0022, ADR-0033.
