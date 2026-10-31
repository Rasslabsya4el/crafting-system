---
name: patch-update
description: Patch update: move the planner to a new Path of Exile patch or league (new repoe-fork export, changed rules, claims, prices, suite). Use when a patch or league launches, the data pin must move, or GGG patch notes touch crafting.
---

# Patch update

The owner's targets (#81, round 3): new numbers the same day, a changed rule of an existing method in a few hours. One branch, one PR titled `Patch update <version>`; the PR never merges itself. What each command prints, and the timings of the rehearsal, are in `docs/patch-update.md`.

Run every command from the repo root. The old pin stays in `PIN.json` until step 5, so steps 1-4 work on the old data. GitHub's API is read without a login at 60 calls an hour per address; with many sessions on one machine set `GITHUB_TOKEN` (or `GH_TOKEN`) in the environment, and the data commands send it to api.github.com only.

## 1. Find the export

Take the game version of the patch you move to (`3.29.4.1`). The data commands take it as a name and find the repoe-fork commit themselves: the newest `Export <version>` commit of repoe-fork.github.io (`Version <version>` commits and exports of other versions never match), printed on the first line of the output. Step 2 prints it before the diff; there is no separate lookup.

Done when you know the version; the `Export of <version>: commit ...` line step 2 prints must name the export you expect. A version with no export is refused with the newest export it did see; a patch hours old may not be exported yet.

## 2. Diff and impact

```bash
mkdir -p .claude/scratch
uv run python -m crafting_system.data diff pinned <version> > .claude/scratch/patch-diff.txt
```

The file holds three parts: the diff (mods, weights, families, tags, bench options, essences, fossils), the **impact report** (which targets, routes, claims and tests name something that changed, and the tests that read the real cache), and the command that moves the pin to the export. The first run downloads the commit (about 45 MB, seconds); step 5 reuses that download.

Done when you have read all three parts and written down: the essences, fossils and bench options that changed, every claim in the impact report, every target or route in it.

## 3. Read the patch notes

For every patch between the pinned one and the new one read GGG's notes: the wiki page `https://www.poewiki.net/wiki/Version_<x.y.z>` through the built-in browser (WebFetch is refused there), and its hotfix list. Keep the lines about crafting: essences, fossils, the bench, Harvest, currency orbs, mod weights, recombinators, influences, corruption.

Build a table with one row per such line: the note, the diff entry that shows it, the claim ids (`grep -n "<keyword>" src/crafting_system/rules/claims/*.yaml`) that state the mechanic.

Done when every diff entry in Essences, Fossils and Bench options and every crafting line of the notes sits in the table. A behaviour change the data cannot show (a rule fixed in the client) has no diff entry; its row names the claims it may break.

## 4. Open a research ticket per unclear mechanic

A row is unclear when the notes say a rule changed and no source states the new rule. Open one ticket per row (`gh issue create`, the `wayfinder:task` form of #109 as the pattern) naming the claim ids, the patch and the question; decide nothing from memory. Work goes on while it is open.

Done when each unclear row carries an issue number.

## 5. Move the pin

```bash
uv run python -m crafting_system.data pin <commit> <version>
uv run python -m crafting_system.data verify
```

Run the line that step 2's output ended with (`To move the pin to this export: ...`): it names the commit you analysed, so a newer export that appears in between is not pinned by mistake (`pin <version>` alone asks GitHub again and takes the newest). `pin` takes the files `diff` already downloaded (nothing is downloaded twice), files them under the version's cache folder, checks the five files, and only then rewrites `src/crafting_system/data/PIN.json`; if a step fails the files go back to the commit's folder and a rerun downloads nothing. A commit alone reads its version from the commit message. Nobody edits `PIN.json` or any Python.

Done when `pin` and `verify` print the five files and `PIN.json` names the new version. The printed hashes come from the first download of the commit, and the commit id names its content, so a later download that disagrees with them is the alarm; nothing else needs checking.

## 6. Update the claims

For each claim of the impact report and of the table: open its `url`, read the new source, and decide. The claim still holds: `patch_verified` becomes the new version and `date_checked` today. The claim's value changed: new `statement`, `value` and `quote`, the new `patch_verified`, and the old version of the claim as an entry of its `history` list, oldest first (the old `statement` and/or `value`, `held_until` = the `patch_verified` the claim had before, and the `source_kind`, `url` and `quote` of the source that showed the change). A rule you cannot source stays on the research ticket of step 4.

```yaml
    patch_verified: "3.29.4.1"
    value: 3
    history:
      - statement: A Chaos Orb costs 2 Chaos.
        value: 2
        held_until: "3.29.3.3"
        source_kind: official
        url: https://www.poewiki.net/wiki/Version_3.29.4
        quote: "Chaos Orb now costs 3 Chaos."
```

The registry refuses a malformed entry with the file, the claim and the line. Code never reads `history`; the claim's `value` stays what it was.

List the claims that were not verified on the pinned version (the one `PIN.json` names, so run it after step 5):

```bash
uv run python -m crafting_system.rules stale
```

One line per claim: id, `patch_verified`, source kind, the `url` to re-read. A claim you re-read and found unchanged gets the new `patch_verified` and drops off the list.

Done when each claim of the table is changed or has a ticket, `rules stale` lists only claims that have a ticket (or nothing), and the registry loads (`uv run pytest -q tests/test_rules_registry.py tests/test_rules_history.py`).

## 7. Prices

```bash
uv run python -m crafting_system.prices fetch
uv run python -m crafting_system.prices check
```

`fetch` takes the league poe.ninja lists as current; pass `--league <id>` otherwise. The benchmark needs the start-item price of each benchmark target (R12: `R12 start amulet`) in `price_overrides.toml` beside `prices.json` (`[prices]` table, Chaos), or from `prices trade --spec`. A route whose start item has no price is not run; `benchmark` prints the exact line (`"R12 start amulet" = 0`, put the price in place of the 0), the file it goes in, and the `prices trade --spec examples/buy/...` command when a buy spec names the item.

Done when `check` reports no stale file and the start items are priced.

## 8. Suite and benchmark

```bash
CRAFTING_CACHE_DIR=<the cache with the new export> uv run pytest -q -p no:cacheprovider
uv run python -m crafting_system.cli benchmark --out .claude/scratch/bench
```

No test holds the pin by hand: the pin test reads `PIN.json`, and `tests/test_simulator_real_data.py` reads the dump through the cache like the other real-data tests, so a moved pin needs no test edit. Read every `SKIPPED` line of the run: a skip that says the real game data is not in the cache means the new export is not in the cache you pointed at.

Other tests that pin numbers of the real dump fail when the dump moved. Fix each by the new number from the new data and say in the commit which diff entry caused it. A failure the diff does not explain is a regression: find its cause before the pin moves.

Done when the suite is green with no skip that names the pinned dump, and `benchmark` says `matches` for every published odds and `solver not dearer than the guide: yes` for every route.

## 9. Compare with the guides

For each benchmark target in `examples/`: the solver's mean and the given route's mean before and after the update, side by side. A guide that is now dearer than the solver, or a published odds that no longer match, is a finding: a research ticket or a note in the PR, never a silent edit of the guide.

Done when the PR body holds that table.

## 10. Open the PR

Body: the diff summary, the table of step 3, the claims changed (the old value of each is in its `history`), the claims `rules stale` still lists and why, the tickets opened, the benchmark table, the minutes each step took. Turn Auto-fix on; the main chat merges.

Done when the PR is open with that body and `Closes #<ticket>` of the update.
