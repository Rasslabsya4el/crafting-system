# Spec: execute frozen CoE calculator code for the twelve lead-selected cases

Worktree: `.worktrees/offline-coe-validation` (branch `w-offline-coe-validation`).
May touch ONLY tools/coe_offline.cjs, tools/coe_validation.py, tests/test_coe_validation.py,
and ignored out/coe-validation/ outputs. No production calculator changes or interpretation docs.

## Why
GOAL2 requires independent real-pool numbers from cached CoE JavaScript. The lead interprets
differences. You mechanically prepare inputs, execute the original source functions and report.
Node24.11.1 is available. This task has a90minute ceiling; send a concrete blocker after two
failed integration approaches. Never fetch a file, install a dependency or open a live website.

## Requirements
1. Read docs/research/coe-calculator-and-policies.md. Load source code at runtime from
   sources/raw/coe/package.js and independent CoE data from poec_data.json (JS assignment).
   The lead supplies these ignored files. No CoE function body or compiled data copied into
   tracked code/data. Node built-ins/vm only; Python standard library and existing modules.
2. Execute the UNCHANGED cached poec_computeFinalProbsV2/poec_computePermutationsV2 and their
   needed constants/helpers. You may extract complete declarations at runtime with verified
   boundaries, keeping source hash and line ranges in output. UI-only diagnostics may be
   stubbed, but never rewrite the probability arithmetic or replace it with our answer.
   The numeric override contains weight/mods/tiers/modpool/reqpool/rqgpool; see1530.
   Use forced exact-labelled mode poec_cAlgoMode="x", not extrapolation; preserve its output
   even when it differs from ours. Reset mutable globals between cases; timeout each VM call.
3. Build CoE pools independently from basemods/base_id, modifiers id_mgroup1, tiers with
   positive weighting and ilvl<=86. Preserve source-native modgroups including multiple groups.
   Existing group exclusions, essence-forced group and full sides must be applied to CoE data,
   not by substituting our PoB pool. Validate all correspondences by side/level/range from
   the snapshots. Targets below are exact top available tiers, not arbitrary lower-tier cuts.
   CoE ordinary base IDs: helmet52, bodyINT47, ring1, amulet2, bootsSTR39.
   Known IDs life1775, chaos661, cold684, flatES2007; mechanically identify remaining named
   targets/forced essence from CoE records and report IDs/ranges. Do not infer game rules.
4. Single Exalted/Regal draws: execute CoE's source slam calculation in
   poec_refreshReqZone (around892-913; exact function name verify from source), or use its
   unchanged permutation routine with ONE draw over the eligible weighted pool. In the latter
   case explicitly label this a direct one-draw kernel invocation with source-native weights,
   not the full UI's path. It must evaluate the same conditional single-addition event.
5. Python CLI runs all12 cases in one bounded offline session, our action_distribution versus
   CoE, emits JSON plus a compact TSV/text table to out/coe-validation/. Include both numeric
   values, relative difference (ours-CoE)/CoE, both pool totals, method/mode, existing IDs,
   required IDs/levels/ranges, source hashes, Node version. No market prices, no probabilities
   inferred from rounded displayed attempt counts. Fail loudly on missing/ambiguous matches.
6. Tests: hand synthetic A/B/C weights1/1/2, distinct groups, two draws, P(A)=7/12 and
   P(A,C)=5/12 through the cached JS kernel; synthetic single-draw P(A)=1/4. Confirm case
   count12 and exact case IDs/classes/actions. Test absent source and invalid inputs fail.
   Source-dependent tests may skip clearly when cache absent in future environments. Do not
   execute all12 real expensive cases on every pytest run; run CLI once for acceptance.
   Focused tests only in worktree. No subprocess remains after completion.

## Cases and OUR numbers already measured by the lead
All ordinary ilvl86, Q9 flags false. Empty reroll inputs have required rarity, zero explicits.
Targets are AND; no implicit/quality/magnitude score requirements.
| id | base | action/input | target IDs | expected our probability |
|---|---|---|---|---:|
| C01 | Royal Burgonet | Chaos/rare | IncreasedLife9 + ChaosResist6 | 0.0003673650969794048 |
| C02 | Royal Burgonet | essence/rare, Metadata/Items/Currency/CurrencyEssenceEnvy3 | IncreasedLife9 + FireResist8 (forced ChaosResist6) | 0.0008758259906074872 |
| C03 | Royal Burgonet | Exalted/rare with ChaosResist6,FireResist8,ColdResist8 | IncreasedLife9 | 0.02546148949713558 |
| C04 | Simple Robe | Alchemy/normal | LocalIncreasedEnergyShield11 | 0.03550816560805275 |
| C05 | Simple Robe | Alteration/magic | LocalIncreasedEnergyShield11 + LightningResist8 | 0.0001408371359360036 |
| C06 | Iron Ring | Chaos/rare | ColdResist8 + ChaosResist6 | 0.00010876109551498082 |
| C07 | Iron Ring | Alchemy/normal | ColdResist8 | 0.024246677570894055 |
| C08 | Iron Ring | Regal/magic with IncreasedLife7,FireResist8 | ChaosResist6 | 0.0016909029421711193 |
| C09 | Paua Amulet | Chaos/rare | IncreasedLife8 + ChaosResist6 | 0.00010370039891240398 |
| C10 | Paua Amulet | Alteration/magic | ColdResist8 | 0.006330103412534295 |
| C11 | Iron Greaves | Alchemy/normal | MovementVelocity6 | 0.05122857786828192 |
| C12 | Iron Greaves | Regal/magic with MovementVelocity6,FireResist8 | ChaosResist6 | 0.0030637254901960784 |

Source semantics: accepted ordinary/essence sheets and action adapter. Own numbers measured
2026-09-21 at deae811; these are regressions, NOT external known answers. C03=1000/39275.
Raw CoE metadata may reveal different exclusions/weights; expose that, do not fix either source.

## Numbers to report
All12 ours/CoE/differences, missing/ambiguous mappings(0 expected), source hashes, synthetic
values, runtime in minutes, pytest summary, commits/files. Describe any required stub and
which exact CoE function produced each result. Lead owns final coe_cases.md interpretation.
