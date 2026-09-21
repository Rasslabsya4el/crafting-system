# Bounded ordinary-action solver experiment — 2026-09-21

Accepted b89f775 (worker b871312). GOAL2 item4 permits a measured negative result.
The generic finite positive-cost value iteration passes the three hand optima; the real
helmet graph hits its explicit state limit before its first Alchemy row is complete.
It therefore provides no helmet optimum, policy or template comparison.

## Reproduce

```powershell
python -m pytest -q tests/test_solver.py
python -m tools.solver_experiment --output out/solver/helmet.json
```

The lead ran the committed worker branch personally:11 passed in0.33s. The lead's one
real rerun took0.23022minute; its JSON is retained locally in out/solver/helmet.json.
These results depend on committed projections, not the raw source cache or the network.

| Hand case | Computed value | Selected action | Residual | Iterations |
|---|---:|---|---:|---:|
| H1 S | 7.999999999744003 (exact8) | retry | 8.53e-11 | 84 |
| H2 S/T | 3.9999999999126885 /2 (exact4/2) | cheap /finish | 8.73e-11 | 36 |
| H3 A/B | 4.75 /5 | gamble /finish | 0 | 6 |

The mathematical inputs and derivations are in specs/2026-09-21-bounded-policy-solver.md.
The unequal-junk-group example remains1/10 after occupying groupB and1/2 after groupC;
one generic junk-prefix count cannot represent both future distributions exactly.

| Helmet measurement | Lead result |
|---|---:|
| Materialized graph states | 1 |
| Distinct pending concrete Alchemy outcomes | 99999 |
| Total states held, hitting limit | 100000 |
| Internal draw edges explored | 506055 |
| Completed action rows /successor edges | 0 /0 |
| Peak draw stack/frontier | 620 |
| Completed-row probability violations | 0 (no complete row yet) |

Status is complexity_limit at materialize pending alchemy outcome. The0 row-violation
count is not evidence that an incomplete Alchemy distribution was normalized. The small
real Transmute test does complete:3569 concrete outcomes,7138 draw edges and unit mass.

## Scope and limits

Concrete modifier/group identities preserve future exclusions. The action set includes
Transmute, Alteration, Augmentation, Regal, Alchemy, Chaos, Exalted, Scour, the four
permitted essences, and priced permitted benches131/728/729/730/731/732. Legality is
checked through accepted actions.py setup. Annul is explicitly omitted: the loadout has
no price and this probe has no concrete removal enumerator. Harvest is omitted because
its forced-draw continuation needs a separate group-preserving implementation here.
Generated tags/multipliers remain omitted under D14; all Q9 flags are false.

Limits:100000 states,2000000 edges,2minutes graph building,2minutes solving,
10000 iterations and residual1e-10. No high-level template is substituted as an action.
There is no inference that the evaluated templates are globally optimal, or that a
different mathematically justified state representation could not solve the problem.
Further large-graph work is parked under GOAL2's bounded-experiment instruction.

Review used one consolidated precommit correction: zero-probability edges, pending-state
accounting, explicit Annul omission, terminal stopping, JSON-safe limits and truthful
template/base-price comparison. Full diff read and all reported numbers checked. Worker
full-suite failures were missing ignored source fixtures, not solver failures; the final
repository-wide regression remains a separate integration check.
