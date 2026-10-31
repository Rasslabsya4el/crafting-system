# Patch update

How the planner moves to a new Path of Exile patch or league. The steps an agent follows are the project skill [`patch-update`](../.claude/skills/patch-update/SKILL.md); this page is what stands behind them: the targets, what the commands print, what they cannot see, and how long a real update took in a rehearsal.

Targets (owner, [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81) round 3, 2026-10-31): new numbers (weights, new mods, prices) ready the same day, almost automatically; a changed rule of an existing method in a few hours of agent work. A brand-new method is a different job (ticket [#108](https://github.com/Rasslabsya4el/crafting-system/issues/108), one action contract). The decision behind it is [ADR-0017](adr/0017-one-ruleset-at-a-time.md): one ruleset at a time, a diff on every patch.

## The pieces

| Piece | What it does | Where |
|---|---|---|
| Pin | The repoe-fork commit, with the sha256 and size of the five files the normalizer reads. Moving it is editing `PIN` and nothing else. | `src/crafting_system/data/pin.py` |
| `data diff OLD NEW` | Downloads a commit it has not seen (hashes learned once), prints what changed in mods, weights, families, tags, bench options, essences and fossils, then the impact report, then the lines to paste into `PIN`. `--no-impact` leaves the report out. | `python -m crafting_system.data diff pinned <commit>` |
| Impact report | Which files of this checkout name something that changed (below). | `src/crafting_system/data/impact.py` |
| Claims | Every rule with its source and the `patch_verified` it was last checked on. | `src/crafting_system/rules/claims/*.yaml` |
| Prices | poe.ninja prices of the current league, hand prices beside them. | `python -m crafting_system.prices fetch` |
| Benchmark | The solver against each guide's route, with the guide's published odds recomputed. | `python -m crafting_system.cli benchmark` |

## Reading the impact report

The report looks, in the checkout, at `examples/**/*.yaml` (targets and routes), the claims, and `tests/*.py`, for:

- the ids of mods that were added, removed or changed, and the families of those mods (a changed tier of Cold Resistance touches every target that names the family);
- the ids of changed base items, essences and fossils, and their names (a target names its base by name);
- the mod texts of changed mods (`+# to Cold Resistance`; the ranges in a text count as `#`);
- the mods a changed essence, fossil or bench option adds or stops adding.

An id counts when it stands alone as a word in a line, a name or text when a quoted string or the value after `key:` is exactly it. An id that is one plain word (a family called `Nothing` or `Strength`) is searched for only after `family:` or `mod:`, because prose would match it. "Mods" in the header counts every mod that differs in any field; the diff shows a change of tags only under Tags, so its mod count can be smaller.

It always lists the test files that read the real cache (`real` as a word of the file name, or an import of `real_game_data`), because their numbers move with any patch, and it lists changed essences, fossils and bench options in words. A bench option has no id in the data; it is told by its master and actions, and one that gained or lost item classes, cost or tier is one `changed` line.

What it cannot see: a rule that changed in the game client without a change in the data (a bug fix, a new interaction). Those come only from the patch notes, which is why step 3 of the skill reads them and step 4 opens a research ticket where no source states the new rule.

## Rehearsal

On 2026-10-31 the runbook was followed on a scratch worktree with the pin moved from 3.29.3.3 back to 3.29.0.2 (repoe-fork commit `d400e21c34be22dc47776346b89cbdb1fb8d3e03`, "Export 3.29.0.2", 2026-07-25), against a copy of the real cache. "Command time" is what the commands took; reading, deciding and writing add to it (about 25 minutes in all for this update, most of it step 3 and the suite).

| Step | What happened | Command time |
|---|---|---|
| 1 Find the export | `gh api` over three pages of repoe-fork commits; many exports per patch, only the commit message tells the version | seconds |
| 2 Diff and impact | 806 lines: 217 mods, 300 base items, 1 essence (Essence of Desolation, level 0 to 8), 6 bench options (Niko's reroll crafts lost item classes). The impact report named 1 claim (`essence.desolation_is_not_a_b1_action`), 1 test file (`test_actions_essence.py`), the 7 real-cache test files, and no target or route. Its first run printed `Nothing` and `Tablet` as hits (families that are plain words); fixed in `impact.py` | 20 s (45 MB download) |
| 3 Patch notes | WebFetch and a fetch agent are refused by poewiki (bot check); the built-in browser reads it. 3.29.3 lists a fix about Essence of Desolation, 3.29.1 fixes bench crafts on Maps, Invitations and Contracts: both match diff entries | about 4 min |
| 4 Research tickets | none needed: every essence and bench entry matched a note | - |
| 5 Move the pin | paste of the printed lines into `pin.py`; `verify` then failed ("not in the cache folder") because the diff stored the commit under its own folder; `fetch` downloaded it again | 6 s |
| 6 Claims | one claim to change; no field for the old value, so it goes in the commit message | 3 s |
| 7 Prices | `prices fetch` found league Allflame, 3452 prices; `benchmark` stopped for want of the price of `R12 start amulet` until a hand price was written to `price_overrides.toml` | 5 s |
| 8 Suite and benchmark | 5377 passed, 1 failed, 3 skipped. The failure: the test that holds the old version, commit, size and hash by hand. The skips: `test_simulator_real_data.py` looks for the dump in `.claude/scratch/repoe-<version>`; after copying it, 4 passed | 6 min; 17 s; 4 s |
| 9 Compare with the guides | R12: solver and given route both 154.95 Chaos on either pin, published odds 2.88% and 1.338% match, solver not dearer | 4 s |

Findings that need code, as proposed tickets:

1. **Move the pin by command.** `data pin <commit> <version>` that writes `PIN` and leaves the cache usable (reuse the commit's folder), replacing the paste of five lines and the second download.
2. **Name a patch, not a commit.** `data diff pinned 3.29.4.1` resolving the version to the repoe-fork commit through the GitHub API.
3. **A claim keeps its history.** An optional `history` field in the registry (`rules`) for the old value and its patch, and a command that lists the claims not verified on the pinned patch.
4. **Real-data tests do not hold the pin.** The pin test should read its expectations from nothing but the structure of `PIN`, and `test_simulator_real_data.py` should use the cache like the other real tests instead of skipping.
5. **The benchmark names its prerequisites.** A missing start-item price should print the line to add to `price_overrides.toml`, or `prices` should price the start items of the benchmark targets.
