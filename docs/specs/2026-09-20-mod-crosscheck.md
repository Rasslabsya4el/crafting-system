# Spec: frozen 54-mod, five-class comparison report

Worktree `.worktrees/mod-crosscheck`, branch `w-mod-crosscheck`. Target 20 minutes; bounded
offline comparisons only, no processes left running. May touch ONLY `tools/mod_crosscheck.py`,
`tests/test_mod_crosscheck.py`, `docs/research/mod-crosscheck.md`.

## Why
BRIEF phase 0 requires at least 50 mods across five classes checked against CoE and PoEDB.
The lead has read the source structures and selected the correspondences below. Produce a
mechanical table with pointers and discrepancies; do not resolve conflicting game rules.

## Requirements
1. Read WORKER_RULES and AGENTS 1,2,3,5. Standard library, offline only, no source execution,
   eval, scraping, network or dependency installs. Raw source copies are supplied by the lead.
2. Parse CoE's frozen `sources/raw/coe/poec_data.json` as one `poecd=` assignment followed by
   JSON (optional final semicolon). Use `json`, never JS evaluation. PoEDB HTML contains
   `new ModsView(` followed by a JSON object; use JSONDecoder.raw_decode and require closing
   `);` after JSON. Use `normal` rows only and the exact correspondence table below.
3. Load PoB `data/pob_mod_explicit.json`; use each source_line to verify the raw source ID
   and read the first unnamed quoted stat line after `affix = ...`. These selected rows have
   positive integer ranges `(a-b)`; parse only that stated format. Reject unknown/missing
   syntax. In PoEDB `str`, strip markup with HTMLParser then read integer ranges `(a—b)`;
   CoE ranges are `json.loads(nvalues)`. Do not infer game tiers from index order.
4. For each selected PoB ID find exactly one PoEDB `normal` row by affix Name and Level,
   then verify source-specific family, generation side and stat ranges. Select CoE modifier
   by the explicit ID and tiers by base ID; match unique ilvl. Missing or ambiguous match is
   reported as a discrepancy, never silently skipped. Require all 54 selected PoB IDs present.
5. Resolve raw PoB spawn weight using the first matching weightKey from the active base tags
   below (including zero), per `docs/mechanics/pool_resolution.md` S26. No full pool resolver,
   multiplier or influence logic. Bow multiplier fields are outside this comparison's scope.
6. Output a Markdown table with one row per selected mod: class/base, PoB ID + source line,
   level triplet PoB/CoE/PoEDB, weight triplet, range triplet, affix sides, source-native group
   triplet, and differing field names. Preserve unequal group names even for lead-selected
   correspondences. Record all source paths/hashes, CoE modifier/base IDs, PoEDB normal-row
   index/Name/Level, date read 2026-09-20, snapshot labels owner-supplied as in S24.
7. Report per-class counts, total/unique IDs, match counts separately for level, weight,
   ranges, side, and groups; list every discrepant row. Do not write confidence decisions or
   OPEN_QUESTIONS. A difference is an observation, not permission to change engine data.
8. CLI `python tools/mod_crosscheck.py` anchored to its own worktree writes the report;
   deterministic UTF-8 LF output, import side-effect free, pure helpers. Fail on malformed
   source structures, do not leave a partially rewritten report. Include synthetic tests for
   matching rows, different groups/weights, missing/ambiguous matches, zero-first precedence,
   malformed wrappers/ranges and deterministic output. Existing tests remain green.
9. Explicit-path commits only. Report all numbered quantities below, output hash, tests,
   commits and elapsed minutes. No changes to lead docs or data. No CoE code/data in src/data.

## Lead-selected source correspondence (not canonical game group aliases)
S24 PoB, S4 CoE, S28-S32 PoEDB; S27 base tags. File suffix means `.html` under raw/poedb.

| Class/base | PoB IDs | CoE modifier/base | PoEDB file/family | Active base tags |
|---|---|---|---|---|
| Helmet/Iron Hat | IncreasedLife0 through IncreasedLife9 | 1775/52 | Helmets_str / IncreasedLife | armour,default,helmet,str_armour |
| Bow/Crude Bow | LocalAddedFireDamageTwoHand1..7, LocalAddedFireDamageTwoHand8_, LocalAddedFireDamageTwoHand9..10 | 1972/20 | Bows / FireDamage | bow,default,ranged,two_hand_weapon,twohand,weapon |
| Ring/Iron Ring | ColdResist1..8 | 684/1 | Rings / ColdResistance | default,ring |
| Body Armour/Simple Robe | LocalIncreasedEnergyShield1..11 | 2007/47 | Body_Armours_int / BaseLocalDefences | armour,body_armour,default,int_armour |
| Gloves/Iron Gauntlets | Strength1..9 | 2336/33 | Gloves_str / Strength | armour,default,gloves,str_armour |
| Ring/Iron Ring | ChaosResist1..6 | 661/1 | Rings / ChaosResistance | default,ring |

PoB bow group is LocalFireDamageTwoHand, ES group LocalEnergyShield. CoE and PoEDB use the
families listed above. Preserve/report these 21 group-label differences (Q16), do not normalize
away. CoE id_mgroup=1 alone is insufficient: corrupted rows also use it; exact IDs avoid that.

## Numbers a test must reproduce and report
1. 54 selected distinct IDs; class counts helmet10, bow10, ring14, body11, gloves9.
2. Level lists by the six rows above:
   1/5/11/18/24/30/36/44/54/64;
   1/11/18/26/33/42/51/62/74/82;
   1/14/26/38/50/60/72/84;
   3/11/17/23/29/35/43/51/60/69/75;
   1/11/22/33/44/55/66/74/82;
   16/30/44/56/65/81.
3. Weights 1000 throughout except chaos resistance250 and bow [1400 x7,1120,490,126].
   These were read by lead from S24 and the selected S4/S28-S32 rows; expected 54 agreements
   for levels and weights. Report actual discrepancies instead of forcing expected matches.
4. Range spot checks: life0 [[3,9]], life9 [[130,144]]; fire1 [[3,5],[6,7]],
   fire10 [[165,225],[335,390]]; ES1 [[3,5]], ES11 [[91,100]];
   ColdResist1 [[6,11]], ColdResist8 [[46,48]]; Strength1 [[8,12]],
   Strength9 [[51,55]]; ChaosResist1 [[5,10]], ChaosResist6 [[31,35]].
   Compare all 54 ranges, report measured agreements (do not invent remaining expected values).
5. Groups: 33 equal, 21 different labels (10 fire + 11 ES), all retained individually.
   Sides: life/fire/ES Prefix =31; cold/strength/chaos Suffix =23.
6. Synthetic weights keys [blocked,default], values [0,1000], active {blocked,default} ->0;
   active {default}->1000. No matching tag -> explicit error for this bounded tool.
7. Synthetic same level/range but different weight and group -> exactly fields weight,group;
   absent match and duplicate match each reported explicitly, not accepted.
8. Report all input hashes, source counts, 54 row count, field match counts, output hash,
   deterministic two-run equality, and exact pytest summary.
