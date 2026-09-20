# Harvest

## Current evidence

Craft of Exile exposes Harvest reforge and augment actions in `sources/raw/coe/package.js`, including a global `crsim_hnerf` switch and a separate augment dispatch. The cached code is used to inventory branches and names; it is not copied into the engine.

The official 3.27.0 patch notes and the Wiki version-history page state that Harvest reforges respect modifier-type restrictions. The exact behavior for suffix locks and for removing versus adding a modifier is still explicitly marked for confirmation on the Wiki observation. The 3.27 statement is therefore a documented condition, not a complete algorithm.

## Implementation boundary

Do not implement a Harvest probability or lock interaction until the exact action matrix is sourced. A future sheet must distinguish reforge, augment, remove, and add/remove crafts and record whether prefixes/suffixes are preserved for each.

## Sources and confidence

- `documented`: S18 Wiki version 3.27.0 and S19 official patch notes.
- `reimplemented-from-CoE`: S3 `package.js`, Harvest dispatch and nerf toggle.

Open questions Q3 and Q6 in `docs/OPEN_QUESTIONS.md` remain active.
