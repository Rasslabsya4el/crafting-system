---
name: coe-emulator-check
description: Craft of Exile emulator check: put our planner's legal actions and outcome distribution beside Craft of Exile's emulator (Wraecrafter Ultra), run headless from a local copy. Use when a mechanic is doubtful, before an in-game check goes on the owner's list #182, when a route's numbers look wrong, or when the owner reports something he saw in the emulator.
---

# Craft of Exile emulator check

The emulator is the site's own JavaScript, run headless in Chromium from a copy in `.claude/scratch/coe/site/`; a check is a script and a frequency is thousands of repeats in seconds. How the copy was found, its version and the driver's limits: `tools/coe_emulator/README.md`.

Every check is a **debug loop**: our system answers first, the emulator second, and a difference is a *candidate* until you have read the code place on both sides.

## 1. Have the copy

For a quick local check: if `.claude/scratch/coe/site/manifest.json` is missing, run from the repo root (main checkout or worktree):

```bash
python -I tools/coe_emulator/emulator.py fetch
```

It needs only a Python with Playwright 1.58 and its Chromium (both on the owner's machine). Done when the manifest lists `packages/package.js`. Compare its SHA256 with the one in the README: a different hash means Craft of Exile changed its code; say so in your report.

## 2. Ask our system, then the emulator

Write the check in **our** terms: our base id, our mod ids (and which are fractured), the labels of our catalog's actions. The harness builds our `Item`, lists our catalog with each action's verdict, translates the item and each action to the emulator's buttons and runs them on the same item. The check format is in `compare.py`'s docstring; `tools/coe_emulator/checks/` holds worked examples (the #197 shield and its neighbours, the first sweep, the Awakener's Orb and the #201 jewels in CoE terms). A label our catalog does not have comes back with the nearest labels.

**Where it runs.** The owner's PC stays light: locally only a quick targeted check, one process under a minute (one or two actions, a few hundred repeats). Anything with thousands of repeats or several items, a sweep included, runs on GitHub through `run.yml`, which fetches the site in the job (nothing is committed): push the check file on your branch, then

```bash
gh workflow run run.yml --ref <branch> -f os=windows-latest -f timeout_minutes=30 -f command='P="uv run --no-sync --with playwright==1.58.0"; $P python -m playwright install chromium > $OUT_DIR/install.log 2>&1 && $P python tools/coe_emulator/emulator.py fetch > $OUT_DIR/fetch.json && $P python tools/coe_emulator/compare.py <check.json> --out $OUT_DIR/report.json'
```

Windows, because `ubuntu-latest` is Ubuntu 26.04 and Playwright 1.58 cannot install Chromium there (run 41306487186); the #197 shield ran this way in about 10 minutes (run 41307098189). Watch it with `gh run watch <id> --exit-status` in the background and read `report.json` from the artifact (`gh run download <id>`). `fetch.json` has the hashes of the copy the job used. For a long list, `-f runners=N` (up to 16) runs the command N times with `RUNNER_INDEX` 1..N: split the checks into `checks-1.json` ... `checks-N.json` and name `checks-$RUNNER_INDEX.json` in the command. A quick local check:

```bash
CRAFTING_CACHE_DIR="<main checkout>/local/cache" UV_CACHE_DIR=... UV_PYTHON_INSTALL_DIR=... ../../scratch/uv-venv/Scripts/uv.exe run --with playwright==1.58.0 python tools/coe_emulator/compare.py check.json --out report.json
```

Done when every asked action has a row with both verdicts, and every applied draw has its distribution or its per-mod marginals.

## 3. Turn candidates into findings

The report flags a candidate for: verdicts that differ, an outcome, a mod or a shape with |z| > 4, a CoE mod that maps to none of ours (`coe:aid:tindex`). Most first candidates are mapping gaps; fix the harness first. |z| ≤ 4 at N = 2000 only rules out a gross difference: a cell near 17% can be a quarter off unflagged, so raise N when a few percent matter. For each one:

- **Our side**: open the row's `our_place` (the action's `outcomes`) and follow it to the rule and its claim in `src/crafting_system/rules/claims/`. Name the file and line that produce our answer.
- **Their side**: find the emulator function that produced theirs: `poec_simApplyCraftGO` dispatches every craft, `poec_updateActionEnabling` decides what is legal, `poec_simRerollItem` / `poec_simRollAffix` / `poec_simRemoveAffix` draw and remove. Quote the few characters that decide it.
- A mapping problem (two mods with the same tiers and group, a crafted mod's level) is a harness fix, not a finding.

A finding names: the item, the action, our answer with its code place, the emulator's answer with its counts. "I could not find the rule in our code" is not a finding: say exactly where you looked.

## 4. Route each finding

- The emulator contradicts our claim's source, and another trusted source (wiki, player test) agrees with the emulator or with neither: the question goes on the owner's in-game list #182 as a comment, with both sides quoted.
- Otherwise our code is wrong against the evidence: one ticket per fix, with the report row as its evidence.
- A mechanic our system does not model yet (Awakener's Orb, Divine values): record what the emulator does in the claim file of that mechanic, `source_kind: coe`, `approximate: true` with the contradicting source in `approximate_reason` when there is one.

## When the harness cannot ask

- **No action of ours** (Awakener's Orb, influenced Exalted Orbs): write the check in Craft of Exile's terms and run `emulator.py run check.json`; the format is in its docstring, with a `donor` item for an Awakener's Orb. Mod ids are CoE `aid`s and tier indexes (`-1` is the highest); find them in `json/data/main/poec_data.json` of the copy.
- **The local copy cannot run it** (a new page feature, a check that needs the owner's view): the owner's Chrome through Claude in Chrome. Load the tools in one `ToolSearch`, `list_connected_browsers`, `select_browser` a profile no other session uses, open the emulator in a new tab, build or import the item, apply, read the result as text, repeat for a frequency (N ≥ 20), close your tab. Log in, buy, change site settings and accept dialogs never; decline cookie banners. If a step fails (importing a second item), stop and tell the owner exactly where: he offered to help.
