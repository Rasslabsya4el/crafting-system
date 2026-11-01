# Craft of Exile emulator, headless (ticket #198)

A debug tool, not part of the planner and not run by CI. The skill `.claude/skills/coe-emulator-check/` says when and how to use it.

- `emulator.py` fetches the site into `.claude/scratch/coe/site/` (git-ignored: it is third-party code and this repo is public) and runs checks written in Craft of Exile's terms. Needs only Python with Playwright 1.58 and its Chromium.
- `driver.js` is loaded into the page; it calls the emulator's own functions, the ones its buttons call, and re-implements no rule.
- `compare.py` is the debug loop: a check in our terms, our verdict and distribution beside the emulator's. Needs the project (`uv run --with playwright==1.58.0`).
- `checks/` holds worked checks: the #197 shield and its neighbours, the first sweep over every action kind, the Awakener's Orb and the #201 jewel questions in CoE terms.

## How the functions were found

The emulator tab (Wraecrafter Ultra) of `https://www.craftofexile.com/?game=poe1` has no separate script: it lives in `packages/package.js` with the calculator and the mass simulator, and it reads the data from `json/data/main/poec_data.json` (`poecd`). Its functions are the `poec_sim*` and `crsim_*` globals; the ones the driver uses:

| What | Function |
|---|---|
| start an item | `poec_simGoToStart`, `poec_simPickBaseGroup`, `poec_simPickBase`, `poec_simPickItem` (step 5 sets ilvl 100, quality 20), `poec_simFinishSetup` |
| add a mod from the mod list, fracture it | `poec_simApplyCraftGO({action: "add" \| "frac", ...})`, the forced branch the mod-list click takes |
| a bench craft | `poec_simForceAction(button, "cb", aid, tindex)`, the click on the bench tier (it reads the row's `blktrue`/`aftblktrue` classes, so the mod list is refreshed first) |
| what is legal | `poec_updateActionEnabling`: `crsim_actions.*.enabled`, the subset buttons' `disabled` class, the reasons in `crsim_dreasons` |
| apply a currency or an action | `poec_simApplyCraftGO(null, null, true)` with `crsim_params` set as `poec_simSetParams` sets it; an essence also needs `crsim_curessmod` (the `essmod` of its tier button) |
| Awakener's Orb | `poec_simAwaken` with the donor's export in `#poecSimWokeData` (the importer says "the item to be destroyed"); the item in the emulator is the receiver |

The state is `crsim_settings`, `crsim_data`, `crsim_catalyst` and the `enabled` flags; the driver restores them between repeats, so one built item gives any number of independent results. No logic reads the DOM except the bench click's row classes and the essence and Awakener buttons above.

Harvest crafts are `{action: "harvest", subaction, ssaction}`: `hreroll` with the mtype id of the tag (Fire 6, Cold 7, Lightning 8, ...; `inf` for influence), `haugment` (add and remove: the "Harvest nerf" toggle is on by default), `hresist` with `hrftc` and the like, `hother` with `rfmlk` / `rfllk` (more / less likely).

## Version

Fetched 2026-11-01 10:26 UTC. `package.js` and `poec_data.json` have the same bytes as the copy of 2026-09-20 in `sources/raw/coe/` that `tests/coe_support.py` pins: the site has not changed its code or data in between (data version 3.29.0.3).

| File | SHA256 |
|---|---|
| `packages/package.js` | `faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639` |
| `json/data/main/poec_data.json` | `2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a` |
| `js/poe1.js` | `8dbeda50b0fca1ddab8057bdefda68bd0db40d8c04646fec434524bd3c82ea02` |
| `json/data/poec_common.json` | `c188d17ab6f017123f49dcf2b89459fc98f8e9eac43f67f53b8bc65650cd5478` |

`fetch` writes every file's hash to `manifest.json` beside the copy.

## Limits

- Not built yet: implicits (Eldritch included), catalysts, sockets, veiled mods, a corrupted start; checks needing them go to the owner's Chrome.
- Not in the emulator: Remove Crafted Mods as one button, the Harvest damage swap, the Wild Bristle Matron, talisman fracture (`NOT_IN_EMULATOR` in `compare.py`).
- After an Awakener's Orb the page throws in `poec_simWokerClose` (it reads back the currency the enabling step just unselected); the craft is done by then, and the driver reports the error as `page_errors_after_craft`.
- `compare.py` maps a CoE mod to ours by side, level, value ranges and mod group; then without the level (a crafted mod's level in CoE is the bench's); then by level, group and stat text (values in other units: our life regeneration is per minute, CoE's per second). Dummy display stats of the data and the single value of a metamod are ignored.
- For a draw of several mods our side is a sample of our own model, not exact: a z-score of 4 is the line.
