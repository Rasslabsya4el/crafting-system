# Recombinators are reported as a best/worst interval

The wiki says recombinator mod selection is weighted but gives no formula, so the planner commits to no single selection rule and drops the old prototype's equal-chance assumption. The admissible rules are those under which the chance to keep a mod does not fall as its spawn weight falls (rarer mods are kept at least as often as common ones; official 3.25.1 note and the wiki); equal chance is the boundary of that set. The wiki's kept-count table (66.7/33.3, 10/60/30, 30/70) is admitted.

A report shows the route with the best worst case and its [best; worst] interval, and beside it the best route without recombinators.

The B3 grill computes the interval and revisits the selection rules against the owner-trusted 3.25 recombinator guide, under ADR-0005.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q3, [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q11.
