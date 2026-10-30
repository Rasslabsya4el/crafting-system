# Eleven modules, each depending only on those listed before it

The code splits into eleven modules; each may depend only on modules listed before it:

1. `data`: fetch, pin and normalize repoe-fork; knows nothing of crafting.
2. `rules`: the registry of admitted mechanics with provenance (ADR-0004).
3. `items`: the concrete item.
4. `actions`: primitives, each with its exact outcome distribution and sampling on a concrete item.
5. `abstraction`: design D, compression, family types, pool signatures, the cached kernel (ADR-0009).
6. `solver`: the stochastic shortest path; branching in B3 (ADR-0010, ADR-0011).
7. `risk`: metrics of a fixed policy (ADR-0006).
8. `simulator`: runs a policy on concrete items (ADR-0019).
9. `prices`: the price file and its fetchers (ADR-0007).
10. `targets`: the YAML target and the goal check (ADR-0008).
11. `report` / `cli` (ADR-0015).

Origin: [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q18.
