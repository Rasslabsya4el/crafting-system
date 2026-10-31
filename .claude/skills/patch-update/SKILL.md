---
name: patch-update
description: Patch update: move the planner to a new Path of Exile patch or league (new repoe-fork export, changed rules, claims, prices, suite). Use when a patch or league launches, the data pin must move, or GGG patch notes touch crafting.
---

# Patch update

The owner's targets (#81, round 3): new numbers the same day, a changed rule of an existing method in a few hours. One branch, one PR titled `Patch update <version>`; the PR never merges itself. What each command prints, and the timings of the rehearsal, are in `docs/patch-update.md`.

Run every command from the repo root. The old pin stays in `PIN` until step 5, so steps 1-4 work on the old data.

## 1. Find the export

```bash
gh api "repos/repoe-fork/repoe-fork.github.io/commits?per_page=60" --jq '.[] | [.sha, .commit.committer.date, .commit.message] | @tsv'
```

repoe-fork writes several `Export <version>` commits per patch, and `Version <version>` commits between them. Skip the `Version` ones; take the newest `Export` whose version is the patch you move to.

Done when you hold a 40-character commit and the version it exports.

## 2. Diff and impact

```bash
mkdir -p .claude/scratch
uv run python -m crafting_system.data diff pinned <commit> > .claude/scratch/patch-diff.txt
```

The file holds three parts: the diff (mods, weights, families, tags, bench options, essences, fossils), the **impact report** (which targets, routes, claims and tests name something that changed, and the tests that read the real cache), and the lines to paste into `PIN`. The first run downloads the commit (about 45 MB, seconds).

Done when you have read all three parts and written down: the essences, fossils and bench options that changed, every claim in the impact report, every target or route in it.

## 3. Read the patch notes

For every patch between the pinned one and the new one read GGG's notes: the wiki page `https://www.poewiki.net/wiki/Version_<x.y.z>` through the built-in browser (WebFetch is refused there), and its hotfix list. Keep the lines about crafting: essences, fossils, the bench, Harvest, currency orbs, mod weights, recombinators, influences, corruption.

Build a table with one row per such line: the note, the diff entry that shows it, the claim ids (`grep -n "<keyword>" src/crafting_system/rules/claims/*.yaml`) that state the mechanic.

Done when every diff entry in Essences, Fossils and Bench options and every crafting line of the notes sits in the table. A behaviour change the data cannot show (a rule fixed in the client) has no diff entry; its row names the claims it may break.

## 4. Open a research ticket per unclear mechanic

A row is unclear when the notes say a rule changed and no source states the new rule. Open one ticket per row (`gh issue create`, the `wayfinder:task` form of #109 as the pattern) naming the claim ids, the patch and the question; decide nothing from memory. Work goes on while it is open.

Done when each unclear row carries an issue number.

## 5. Move the pin

Edit `PIN` in `src/crafting_system/data/pin.py`: `version`, the commit comment (name and date of the export), and `commit` / `files` from the pasted lines. Then:

```bash
uv run python -m crafting_system.data fetch
uv run python -m crafting_system.data verify
```

`fetch` downloads the commit again, because the diff stored it under the commit's folder and the pin looks in the version's folder.

Done when `verify` prints `ok` for all five files. The printed hashes come from the first download of the commit, and the commit id names its content, so a later download that disagrees with them is the alarm; nothing else needs checking. If `verify` fails before `fetch` with "not in the cache folder", that is the folder naming above, not a bad pin.

## 6. Update the claims

For each claim of the impact report and of the table: open its `url`, read the new source, and decide. The claim still holds: `patch_verified` becomes the new version and `date_checked` today. The claim's value changed: new `statement`, `value` and `quote`, the new `patch_verified`, and the old value in the commit message (`was X on <old version>`), because a claim has no history field. A rule you cannot source stays on the research ticket of step 4.

List the claims that were not verified on the new version:

```bash
uv run python -c "from crafting_system.rules.registry import load_registry as r; [print(x.id, x.source_kind.value, x.patch_verified) for x in r().values() if x.patch_verified != '<new version>']"
```

Done when each claim of the table is changed or has a ticket, and the registry loads (`uv run pytest -q tests/test_rules_registry.py`).

## 7. Prices

```bash
uv run python -m crafting_system.prices fetch
uv run python -m crafting_system.prices check
```

`fetch` takes the league poe.ninja lists as current; pass `--league <id>` otherwise. The benchmark needs the start-item price of each benchmark target (R12: `R12 start amulet`) in `price_overrides.toml` beside `prices.json` (`[prices]` table, Chaos), or from `prices trade --spec`.

Done when `check` reports no stale file and the start items are priced.

## 8. Suite and benchmark

```bash
CRAFTING_CACHE_DIR=<the cache with the new export> uv run pytest -q -p no:cacheprovider
uv run python -m crafting_system.cli benchmark --out .claude/scratch/bench
```

Two tests hold the old pin by hand: `test_the_real_pin_is_the_pinned_..._export` in `tests/test_data_fetch.py` names the version, commit, and the size and hash of `mods.json`; copy the new values from `PIN`. `tests/test_simulator_real_data.py` looks for the dump in `.claude/scratch/repoe-<version>/`, not in the cache, and **skips** three tests (a `SKIPPED ... pinned dump repoe-<version> is not on this machine` line) until you copy the five files there from the cache's version folder. Read every `SKIPPED` line of the run.

Other tests that pin numbers of the real dump fail when the dump moved. Fix each by the new number from the new data and say in the commit which diff entry caused it. A failure the diff does not explain is a regression: find its cause before the pin moves.

Done when the suite is green with no skip that names the pinned dump, and `benchmark` says `matches` for every published odds and `solver not dearer than the guide: yes` for every route.

## 9. Compare with the guides

For each benchmark target in `examples/`: the solver's mean and the given route's mean before and after the update, side by side. A guide that is now dearer than the solver, or a published odds that no longer match, is a finding: a research ticket or a note in the PR, never a silent edit of the guide.

Done when the PR body holds that table.

## 10. Open the PR

Body: the diff summary, the table of step 3, the claims changed (with the old value of each, since the registry keeps no history), the tickets opened, the benchmark table, the minutes each step took. Turn Auto-fix on; the main chat merges.

Done when the PR is open with that body and `Closes #<ticket>` of the update.
