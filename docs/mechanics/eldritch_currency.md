# Eldritch currency and Orb of Conflict

## Supported observations

Craft of Exile has branches for Eldritch Chaos, Eldritch Exalted, Eldritch Annul, Ember/Ichor implicit application, and Orb of Conflict. Its simulator tracks separate red and blue implicit groups and updates a dominance state before applying the action. The code's red/blue names are implementation labels; do not treat them as user-facing Searing/Eater semantics without a source cross-check.

The Wiki Orb of Conflict page says it applies to a non-unique item with both Searing Exarch and Eater of Worlds implicits. One implicit is raised and the other lowered according to relative strength; equal tiers are a 50% split. The page gives an approximate 11% per-tier relative-strength change and identifies Conflict as the route to the highest implicit tiers. These percentages are documented observations and need a reproducible table before entering code.

## Boundaries

The exact tier transition distribution, dominance mapping, base eligibility matrix, and behavior when an implicit reaches its endpoint are unsourced here. They must raise an explicit open question in code rather than be guessed.

## Sources and confidence

- `documented`: Wiki Orb of Conflict browser observation (to be added as S23 in `docs/SOURCES.md`).
- `reimplemented-from-CoE`: S3 `package.js`, Eldritch dispatch and dominance update.
