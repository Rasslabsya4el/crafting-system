# Memory Strands, Foulborn orbs and the Genesis Tree in 3.29

Research ticket [#98](https://github.com/Rasslabsya4el/crafting-system/issues/98) of map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1), for batch B5 (inventory rows M-58 to M-64). Written 2026-10-31 against the pinned patch 3.29.3.3. It re-checks the earlier Reddit note (`docs/research/2026-10-30-memory-strands.md` on branch `research/reddit-sources`) and does not repeat it.

The owner has answered [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81): **a plan may start from a bought item that carries Memory Strands, and may use an Orb of Remembrance on a fresh base.** That amends ADR-0008 ("v1 start items carry no Memory Strands") for B5. Both cases are covered below.

## Answer

1. **The tier cut is exact and checked.** For an item with `s >= 1` strands, every random mod draw sees only the `floor(100 / (2.5 s + 147.5) * (T - 1)) + 1` highest tiers of a mod type that has `T` eligible tiers. I recomputed every breakpoint cell of the wiki table with exact fractions (0 mismatches) and the formula reproduces the "lowest expected tier" of all 1,902 usable rows of the first author's published raw sheet (0 rows below the bound, 814 exactly on it). The cut uses the strands the item had *before* the craft. 0 strands means no cut.
2. **Strands are spent at random.** Each currency spends a whole number up to a ceiling (8 / 16 / 50 / 80 …; Exalted by mod count). Fossils, Harvest, beastcrafting and the ordinary bench crafts spend none; three bench rerolls spend up to 50. This settles the 2025 Reddit disagreement the earlier note left open.
3. **Orb of Remembrance is a re-roll, not an add.** It works on normal equipment, sets any count (also replaces an existing one) to a random number in 10..100, distribution normal(35, 25) redrawn into that range (mean 41.8). Fresh `chi²` fit on the author's own 2,255 results. It can be applied again and again, so the policy may re-roll for a better count.
4. **Orb of Unravelling** spends all strands to try to raise mods; the chance is a player-fitted linear model (approximate), the rest of its rules are on the wiki.
5. **Foulborn orbs** are the strand cut with a fixed `+30 strands` (denominator 100 + 75). On a 0-strand item they keep ceil(N/2) tiers (N ≤ 6), floor(N/2) + 1 (N > 6); I checked that this is exactly the formula at denominator 175. They exist since 3.27.0 (not new in 3.29), and come only from the Genesis Tree.
6. **The Genesis Tree** gives rare armour or jewellery (item level = the Wombgift's level) with up to +60 tier rating from three nodes plus an inherent rating GGG has not published, and mod-type tilts of ×4 / ×0.4. Nothing documents strands on born items.
7. **One rule is not settled and it matters:** what the cut does to the *weights* of the surviving tiers (three candidate models, below). It changes the odds of every cut draw whenever tier weights differ, so it is the first open point.

## Evidence

Under the map's evidence rule. Wiki pages read 2026-10-31 in the built-in browser (Anubis check passed). The wiki's formula and its breakpoint table come from the owner-trusted Reddit post ([/u/Macookta, 2026-09-26/27](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/)), and the wiki cites it. **I could not re-read the post itself this session**: six `gpt-research` jobs failed (the worker process died three times, two timed out, one answered that Reddit was blocked and the search service returned 429). What the note takes from the post (Unravelling model, author's caveats) is therefore taken from the 2026-10-30 note, which was produced through the same skill and marks its quotes verbatim; those are marked below. The post's **raw data sheet** opens without Reddit, and I used it directly (below).

### Memory Strands (kind `wiki`, confirmed by `experiment`)

[Memory strand](https://www.poewiki.net/wiki/Memory_Strands), read 2026-10-31:

- "Memory strands are an item mechanic that can sometimes be found on equipment found in the Atlas. These are displayed with a value ranging from 1-100 on the item's tooltip." Source: Memory-influenced maps (more petals, more chance), and since 3.28.0 any Atlas map after the Voidstone; the Atlas passive "Grasp the Past" makes the strand count lucky 50 % of the time.
- Two effects, both "a version of the Modifier Tier Rating system": identification of a magic or rare item with a Scroll of Wisdom, and currency that replaces or adds mods.
- Formula `rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1`; worked example "at 82 strands … 8 tiers … = 2 … which means only T1 and T2 of this modifier can roll if all 8 tiers are eligible from item level". So `total_tiers` counts the tiers the item level allows (Craft of Exile's own MTR code counts only tiers with `ilvl <= item level`, `baseNumberOfValidTiers`, too).
- Table of breakpoints (row 0: 13 12 11 … 2: "no cut at 0 strands"; row 1: 9 8 7 7 6 5 5 4 3 3 2 1).
- "will deplete a random quantity of Memory Strands, and make it more likely to have outcomes of higher modifier tier based on the quantity of Memory Strands originally on the item." → the cut uses the count before the spend.
- Versions: 3.26.0 introduced; 3.28.0 "Items that drop with Memory Strands will have more Memory Strands on average. Memory Strands will have a larger influence on the tier of Modifiers present on the item than previously."
- "Memory Strand count can be restored with imprints." and "Hinekora's Lock and other methods to lock items can be used to preview exactly how much memory strands are consumed on a craft."

**My exact check of the formula** (Python, `fractions.Fraction`, script not kept in the repo): for each cell of the wiki table I took the first strand count that gives that number of rollable tiers; all 22 rows × up to 12 columns agree, 0 mismatches. Note the exact boundaries: with 8 tiers, 81 strands is exactly `2.0` before the `floor`, so `rollable = 3`, and the table's "82 → 2" follows. Use integer arithmetic: `floor(200 (T-1) / (295 + 5 s)) + 1`.

**Check against the raw sheet** ([Memory Strand Testing](https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/), tab "foulborn and misc currency data", opened through the Sheets CSV export of the page, 2026-10-31): 1,902 usable rows (strands before, currency, total tiers, observed tier, item text before and after).

| Currency | rows | rows below the bound | rows exactly on the bound |
|---|---:|---:|---:|
| Chaos Orb | 615 | 0 | 238 |
| Orb of Alchemy | 649 | 0 | 274 |
| Foulborn Orb of Augmentation | 427 | 0 | 207 |
| Foulborn Regal Orb | 64 | 0 | 32 |
| Exalted Orb | 83 | 0 | 26 |
| Regal Orb | 13 | 0 | 6 |
| Scroll of Wisdom (identify) | 51 | 0 | 31 |

My bound (exact integers, strands = the count in the item text *before* the craft, `+150` in `D` for Foulborn) equals the sheet's own "lowest_expected_tier" column on every row. The observed tier never crosses the bound and reaches it often, so the pre-spend count is right (the post-spend count would be lower and would let weaker tiers through; none appears). The sheet's `mtr` column is `2.5 s + 47.5 (+ 75 for Foulborn)`, e.g. 79 strands Foulborn → 320. The sample has no Foulborn row on a 0-strand item.

### Spend per craft (kind `wiki`; PoEDB `Cost /130` agrees on the first value of each row)

Wiki table, read 2026-10-31: Transmutation, Augmentation, Alteration 0-8; Foulborn Augmentation 0-32; Regal 0-16; Foulborn Regal 0-48; Alchemy, Binding, Chaos 0-50; Chance 0-50; any Essence 0-80; Eldritch Chaos 0-60; Veiled Chaos 0-80; Tainted Chaos 0-60; Awakener's Orb 0-100. Exalted-type orbs: 1 mod 0-16, 2 mods 0-22, 3 mods 0-26, 4 mods 0-32, 5 mods 0-34 (Tainted, 6 mods 0-38); the row for 0 mods is shown as unknown ("likely 0-10"). Foulborn Exalted: 0-62 at 5 mods, the other rows "0-?". The bench: "'Reroll the Rarity of a non-Unique item' … 'Reroll 3 random modifiers on a Rare Item' … 'Reroll a random modifier on a Rare Item'" spend 0-50; "Allflame crafting with any currency items listed above consume Memory Strands as if they were used normally."

**Not spent** (wiki): "Memory Strands are not consumed by the use of resonators, Harvest crafting, Beastcrafting, or crafting benches not using currency listed above … Notably, Veiled Exalted Orb does not consume Memory Strands." This answers the question the earlier note left open (2025 thread: essences eat strands, "Harvest and delve dont"): the 2025 reports were right on both counts.

[PoEDB Memory Strands](https://poedb.tw/us/Memory_Strands) gives the same ceilings but only one figure per orb (Exalted 0-16 for every variant, Foulborn Exalted 0-28); the wiki's by-mod-count table is the finer source and wins. PoEDB's header "Cost /130" is likely the effective strand scale: 100 strands plus the 30 a Foulborn orb adds.

**Distribution of the spend inside the range** (raw sheet, my count): Foulborn Augmentation, 306 uses on items with at least 32 strands (no clipping): spends 0 to 32, five equal bins 64 / 50 / 62 / 59 / 71, 7 zeros (uniform would give 9). Alchemy (260 uses with ≥ 50 strands): 67 / 16 / 55 / 65 / 57. Chaos (130): 45 / 27 / 25 / 21 / 12 (not flat). Exalted spends reach 38 against a first-row ceiling of 16, matching the by-mod-count table. Uniform integer in `[0, ceiling]` is the best simple model for the Foulborn orbs and Alchemy; Chaos does not fit, perhaps because mod count shifts its ceiling; not settled.

### Orb of Remembrance (kind `wiki` for the action, `experiment` for the odds)

[Orb of Remembrance](https://www.poewiki.net/wiki/Orb_of_Remembrance): "Randomises the number of Memory Strands on a normal equipment item … It can be used to add Memory Strands on a non-Memory-influenced item." Drops from the Incarnation of Neglect or in the Scholar's Vault; stack size 10. Memory page: "adds or randomises the quantity of Memory Strands on a normal rarity item. It is not necessary to deplete all Memory Strands before using this orb." PoEDB's page for the orb showed about 56 Chaos Orbs per orb as its 24 h value (read from a search result snippet on 2026-10-31, the page itself not opened; league not stated).

**The odds**, from the author's sheet (tab "remembrance data", 2,255 results, the same count the post gives): every result is between 10 and 100 (none below 10); mean 41.56, median 39, quartiles 26 and 55 (the sheet's own summary cells), three results of exactly 100. Counts by value, 10 to 100:

`10:20 11:32 12:31 13:21 14:31 15:36 16:25 17:37 18:32 19:40 20:43 21:45 22:39 23:37 24:32 25:38 26:37 27:43 28:35 29:50 30:43 31:42 32:48 33:30 34:55 35:35 36:46 37:32 38:44 39:51 40:43 41:46 42:48 43:31 44:34 45:41 46:34 47:37 48:32 49:33 50:39 51:40 52:36 53:34 54:27 55:31 56:31 57:24 58:21 59:34 60:23 61:22 62:20 63:28 64:23 65:22 66:21 67:21 68:17 69:19 70:18 71:14 72:15 73:17 74:14 75:11 76:8 77:9 78:9 79:6 80:14 81:7 82:6 83:5 84:8 85:5 86:2 87:8 88:5 89:5 90:5 91:3 92:3 93:3 94:5 95:1 97:2 98:2 100:3` (96 and 99 never occurred).

The earlier note carried a hypothesis by [/u/sirgog](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcrqc6i/) (2026-09-29): "Generate a random number via normal distribution, mean 35, standard deviation 25 … If the number is 100, discard it". I tested it: the maximum-likelihood normal for the rounded value, truncated to 10..100, is mean 35 (34 to 35), sd 25 (25 to 25.5), and `N(35, 25)` has `chi² = 7.2` over 18 bins of five (17 degrees of freedom; p about 0.98), model mean 41.8 against 41.56 observed. The truncation at 10 is real: the same normal untruncated would put about 15 % of results (about 350) below 10; there are none, and the count at 10 is lower than its neighbours (20 against about 32), as rounding a continuous cut at 10.0 gives (13 expected; the fit is not sensitive to it). The number of 100s (3 against 1.5 expected) does not follow the "discard 100" part, so the upper end is "kept, tiny". Rule: **draw `round(N(35, 25))` and redraw until it is in 10..100.**

Whether the result depends on the previous count is not tested in the sheet (an Orb of Remembrance "randomises"; the post says the author rolled a talisman "to 100 memory strands with orbs of remembrance" by repeating).

### Orb of Unravelling (kind `wiki` + `experiment`)

[Orb of Unravelling](https://www.poewiki.net/wiki/Orb_of_Unravelling), read 2026-10-31: "Consumes all Memory Strands on an item to attempt to upgrade the tier of explicit modifiers based on the number of Memory Strands consumed"; "It is possible to consume all memory strands without upgrading any modifier tier."; "Other T1 affixes do not affect the chance to upgrade sub-T1 affixes."; "does not respect the Suffixes cannot be Changed or Prefixes cannot be Changed metamods."; "cannot upgrade influenced modifiers to an Elevated modifier. It also cannot upgrade a crafted modifier into a regular modifier, as of 3.26.0d."; 3.26.0d "Fixed a bug where Orb of Unravelling could be used on unidentified items." Drops from the Incarnation of Dread.

The chance model is from the post (quotes taken from the earlier note, not re-read): `upgrade_chance = (strands * total_upgrade_candidate_weight)/(2 * total_side_weight)`, where the candidate weight is the sum of the weights of the higher tiers of the mod's type and the side weight is the total mod weight of that side; "Each modifier on the item is calculated independently."; "The number of memory strands only determines the chance for a modifier to upgrade vs. not upgrade. The number of tiers upgraded is not affected by the number of strands."; destination: "assigning each tier a weight consisting of the sum of its own weight and the eligible tiers above it" (corrected by the author's 2026-09-27 edit; originally multipliers 1, 2, 3 from the top). Author's confidence: "I'm not 100% confident the chance scales linearly", "I am confident in the breakpoints where the chance is guaranteed" (36,598 mods tested, no guaranteed-by-formula mod failed to upgrade). Sample sizes: 9,373 orbs; T9 at 32 strands 310/310 upgraded; T9 at 15 strands predicted 47.9 %, observed 63/150 = 42 %.

The two destination models agree only when the higher tiers have equal weights. The community calculator the wiki links ([unravel.port8080.sh](https://unravel.port8080.sh/)) still implements the **original** positional ×1, ×2, ×3 weights (page text: "Successful destinations use separate positional weights of ×1, ×2, ×3, starting with the highest eligible tier"), "Only natural equipment affixes are supported". The raw data (tab "Unravelling data", about 2 million lines of item text, columns include `upgrade_chance`, `upgrade_candidate_weights`, `tier_before`, `tier_after`) is public and could settle it; I did not analyse it.

### Foulborn currency (kind `wiki`, `datamined`, `coe`)

- [Foulborn currency item](https://www.poewiki.net/wiki/Foulborn_currency_item), read 2026-10-31: three orbs (Augmentation and Regal drop level 68, Exalted 80), introduced in 3.27.0 (Keepers), "birthed through the Genesis Tree from a Lavish Wombgift". "Testing suggests" (a Prohibited Library Discord thread, not public): kept tiers `ceil(N/2)` for N ≤ 6 and `floor(N/2) + 1` for N > 6: 1,1,2,2,3,3,4,5,5,6,6,7,7 for N = 1..13. The wiki then scales the weights of the kept tiers by `N / K` ("such that the relative weight ratios between the tiers of a modifier type remain the same"; example 800/400/200/100, two kept, becomes 400/200) and adds: "Alternatively, especially when combined with Memory Strands, it effectively adds +75 to the Modifier Tier Rating value, or effectively +30 Memory Strands."
- **My check:** with denominator 175 (`100 + 75`) the strand formula gives exactly 1,1,2,2,3,3,4,5,5,6,6,7,7, the wiki's list (every N from 1 to 13); the other reading, `147.5 + 75` for a 0-strand item, gives 1,1,1,2,2,3,3,4,4,5,5,5,6 and does not. So on a 0-strand item `D = 175`, and on an item with strands `s >= 1` it is `D = 147.5 + 2.5 s + 75`: the Macookta sheet confirms this on 491 Foulborn rows. The jump of `D` between 0 strands (100) and 1 strand (150) is real in the table (row 0 vs row 1), so a unified rule is `D = 100 + (s >= 1 ? 2.5 s + 47.5 : 0) + (Foulborn ? 75 : 0)` (the Necropolis MTR is `D - 100`).
- Foulborn orbs also spend strands (0-32, 0-48, 0-62 at 5 mods).
- Craft of Exile's code (`sources/raw/coe/package.js`) treats Foulborn as a flag `sanctifiedActive` that multiplies each tier's weight by `1 + (tier level - 40) / 100`. That is the older "higher level mods more likely" model, not the tier cut; it is out of date for this orb (kind `coe` loses to the wiki's Prohibited Library tests and the sheet).

### Modifier Tier Rating and the weights of the kept tiers (the unsettled rule)

The wiki ([Modifier, section Modifier Tier Rating](https://www.poewiki.net/wiki/Modifier#Modifier_Tier_Rating)) lists three models for what happens after tiers are removed: **(1) redistribution** (the removed tiers' weight goes to the kept tiers of the same mod type; the type's total weight against other types is unchanged), **(2) refactored weight** (`new = old * original tiers / remaining tiers`; the type's total changes), and **(3) the Memory Strand model** (the formula above; it says nothing about weights). The Foulborn page uses (2). The in-game text of the Genesis passive (datamined, [PoEDB](https://poedb.tw/us/Modifier_Tier_Rating)) says "Raising Modifier Tier Rating excludes lower tier Modifiers from rolling, distributing their roll chance among higher tier Modifiers of the same Modifier type", which is (1). Craft of Exile's code removes the lowest tiers and uses the kept weights as they are: it computes the removed and the remaining weight, but the branch that would use them is empty (so a third reading, "delete only", is what the one working implementation does). All three agree when tier weights are equal. They differ on common mods (e.g. the wiki's #% increased Physical Damage with weights 1000 for T8-T6 down to 25 for T1).

So the **tier chosen** within a cut mod type is the same in all models (ratios of kept weights unchanged); what changes is **how likely the mod type is against other mod types** (does a Life prefix keep its share of the prefix pool, or shrink). The sheet could settle it (it holds the mod before and after on an item, with the item text), but it needs the pool weights; not done.

### Genesis Tree (kind `wiki`, `datamined`, `coe`)

[The Genesis Tree](https://www.poewiki.net/wiki/The_Genesis_Tree) and [Wombgift](https://www.poewiki.net/wiki/Wombgift), read 2026-10-31; datamined passive text from [PoEDB The Genesis Tree](https://poedb.tw/us/The_Genesis_Tree) (118 tree passives, ids `EquipmentNode2`, `EquipmentNode3b`, `EquipmentNode20a` for the three tier-rating nodes):

- **Mechanism:** "Completing Breach encounters will grant Hiveblood, which is automatically stored." Hiveblood is stored per league for all characters (maximum 100,000), not an item; Wombgifts are items (drop level 1 Provisioning, 13 Lavish, 21 Ancient, 68 Mysterious; Provisioning very common) placed in a womb and fed Hiveblood; passives are free to respec.
- **Equipment womb:** "Baseline rewards: rare armour and jewellery"; optional rare jewels, fractured items (Solid Cysts: 33 % fractured), six-link items. "Rare equipment generated through the Genesis Tree have a base item level equal to the wombgift's specified level." Sockets and links "+10 / +50 times, keeping the best outcome" (an item-level-free roll).
- **Tier rating:** three small passives (`b`, `f`, `k`) each "Birthed Equipment has +20 to Modifier Tier Rating". 3.28.0: "Lowered how much Modifier Tier Rating is granted to Rare items generated from Kingsmarch Shipping, Kingsmarch Mapping, Gambling and the Genesis Tree." 3.29.0: "Equipment Items birthed by the Genesis Tree inherently have slightly less Modifier Tier Rating and bias towards higher tier base types." **The inherent rating is not published anywhere I found** (wiki, PoEDB, Craft of Exile).
- **Mod-type tilt:** notables "300% increased chance" (3.29.0, previously 500 %) for Life, Mana, Defences, Attributes, Resistance, Critical, Attack, Caster, Speed, and the five damage types; the "Forsaken" notables "60% reduced chance". PoEDB lists the same 14 types. The 14 type tags are the tags Craft of Exile's data already assigns to mods (`mtypes`: Attack 3, Attribute 31, Caster 13, Chaos 16, Cold 7, Critical 29, Defences 4, Fire 6, Life 1, Lightning 8, Mana 2, Physical 5, Resistance 35, Speed 14), so the mod-to-type map exists.
- **Other:** `Severing` removes the lowest-level mod; `Divine Rolls` roll values extra times keeping the best; several additional-item chances (the wiki lists 25 % and 50 % nodes, PoEDB 25 % for the small ones); item level `+1` with 25 % chance on two nodes. 3.29.0: "The maximum number of Equipment Genesis Tree Passive Points is now 16 (previously 20)." The wiki's points table lists 16 points for equipment.
- **Foulborn orbs:** the currency womb (node `Flawed Seeds`; `Foulborn Currency Chance`, `Mutation Cultivation` raise it).
- **Craft of Exile (kind `coe`):** the local copy (`poec_genesis`, fetched 2026-09-20) has tier-rating values 20/25/40/50 and weights +1000 % / "scarcer" 400 %: older than 3.29.0 (the notes cut 500 % to 300 %); the wiki and PoEDB win. Its modelling is useful for the design: mod tilts add (`pos_mod += weight`, then `+1`), tier rating feeds the same `necropolis_tier_filtering` function with cut `ceil(100 * (1 - 1/(1 + x/100))) / 100` and `floor(N * cut)` tiers removed from the bottom.
- **Not documented:** whether a born item carries Memory Strands (no source says so; the tree's own text speaks of tier rating, which is the same effect applied once at birth), its item level distribution (the Wombgift's level, which follows the area it dropped in; 3.28.0 "more variance … at endgame"), how many items a Wombgift births on average, and the Hiveblood cost.

### Prototype and code

`git show archive/prototype`: no Memory Strand, Foulborn or Genesis code; its `docs/mechanics/INDEX.md` lists Foulborn and Genesis as "catalogue-only backlog". `main`: `affix_pool.no_memory_strands` (`src/crafting_system/rules/claims/affix_pool.yaml`) and `NO_MEMORY_STRANDS` (`actions/pool.py`) are the two places that hold the v1 assumption; `bench_craft.yaml` already says the 3.29 bench rerolls consume strands. `trade_query.py` already has a `memory_level` filter slot.

## Draft claims for `src/crafting_system/rules/claims/`

Twenty-two claims (YAML below; the seven fields each). The `experiment` claims cite the first author's published sheet; the Unravelling claim quotes the post through the earlier note.

```yaml
rules:
  # --- Memory Strands: the property and the tier cut ---
  - id: memory_strands.property
    statement: >-
      An equipment item carries a Memory Strands count from 1 to 100 (no strands is the count 0). The count survives crafts except for the amount the craft spends. It shows on the item text as "Memory Strands: N".
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "These are displayed with a value ranging from 1-100 on the item's tooltip."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.rollable_tiers
    statement: >-
      For an item with s >= 1 strands, a random mod add or replace draws a mod type's tier only among its `rollable_tiers(T, s) = floor(100 / (2.5 s + 147.5) * (T - 1)) + 1` highest tiers, T being the number of tiers of that mod type eligible on the base at the item level. The lowest tiers are removed. Computed in exact arithmetic, not floats: `floor(200 (T-1) / (295 + 5 s)) + 1` (8 tiers at 81 strands is exactly 2.0 and gives 3 rollable tiers, at 82 strands 2).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.cull_counts_eligible_tiers
    statement: >-
      The tier count T of the cut is the number of tiers of the mod type that the item level allows on that base (a tier the item level forbids is not counted and cannot roll anyway); the cut is made per mod type, so each mod type of the pool is cut on its own T.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "which means only T1 and T2 of this modifier can roll if all 8 tiers are eligible from item level."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.zero_is_no_cull
    statement: >-
      An item with 0 strands is not cut at all (every eligible tier rolls); the formula applies from 1 strand (1 strand already leaves 9 of 13 tiers).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "0	13	12	11	10	9	8	7	6	5	4	3	2"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.cut_uses_strands_before_spend
    statement: >-
      The cut of a craft is made from the strands the item had before the craft; the craft then spends its random amount.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "will deplete a random quantity of Memory Strands, and make it more likely to have outcomes of higher modifier tier based on the quantity of Memory Strands originally on the item."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.rule_check_against_raw_data
    statement: >-
      The formula with the pre-spend count reproduces the lowest rollable tier of all 1,902 usable rows of the first author's published raw sheet (Chaos, Alchemy, Regal, Exalted, Foulborn Augmentation and Regal, Scroll of Wisdom), with no observed tier below the bound and 814 rows exactly on it. Also holds for identification with a Scroll of Wisdom (51 rows).
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/
    quote: "Model 3: 2.5x + 47.5, no rounding"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  # --- What a craft spends ---
  - id: memory_strands.spend_ranges
    statement: >-
      A craft spends a random whole number of strands up to a ceiling per currency (never below 0, never more than the item has): Transmutation, Augmentation, Alteration 8; Regal 16; Alchemy, Binding, Chaos, Chance 50; any Essence 80; Eldritch and Tainted Chaos 60; Veiled Chaos 80; Awakener's Orb 100; the bench rerolls 'Reroll the Rarity of a non-Unique item', 'Reroll 3 random modifiers on a Rare Item', 'Reroll a random modifier on a Rare Item' 50.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "the following crafting options do remove 0-50 memory strands, similar to Orb of Chance or Chaos Orb"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.spend_exalted_by_mod_count
    statement: >-
      The ceiling of an Exalted Orb (and the Eldritch, influence-named and Tainted Exalted variants) grows with the mods the item has when it is applied: 1 mod 16, 2 mods 22, 3 mods 26, 4 mods 32, 5 mods 34 (Tainted, 6 mods 38). The row for 0 mods is not shown by the game (wiki: likely 0-10).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "Despite not showing a range on the item, it can still consume an unspecified number of Memory Strands, likely 0-10."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.not_spent_by
    statement: >-
      Resonators (fossils), Harvest crafting, beastcrafting, the bench crafts other than the three rerolls, and the Veiled Exalted Orb spend no strands. Fracturing, Orb of Annulment, Scouring, Divine and Vaal are not listed by the wiki either way.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "Memory Strands are not consumed by the use of resonators, Harvest crafting, Beastcrafting, or crafting benches not using currency listed above"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.spend_distribution_provisional
    statement: >-
      Provisional: within its ceiling the spend looks like a uniform whole number (Foulborn Augmentation: 306 draws on items with 32 or more strands, spend 0 to 32, flat over five equal bins, 7 zeros of 306 against 9 expected; Alchemy flat in four of five bins). Chaos Orb is not flat (130 draws, first bin 45 of 130 against 26). Treat as uniform [0, ceiling] until a larger test says otherwise.
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/
    quote: "foulborn and misc currency data"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  # --- Orb of Remembrance ---
  - id: memory_strands.remembrance_action
    statement: >-
      An Orb of Remembrance applies only to a normal-rarity equipment item; it sets the item's strand count to a new random number whatever the count was (it adds strands to an item that has none, and re-rolls an item that has some). It can be used again and again.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "Orb of Remembrance adds or randomises the quantity of Memory Strands on a normal rarity item. It is not necessary to deplete all Memory Strands before using this orb."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.remembrance_distribution
    statement: >-
      The strand count after an Orb of Remembrance is a whole number from 10 to 100 drawn from a normal distribution with mean 35 and standard deviation 25, redrawn until it lies in 10..100 (2,255 orbs: no result below 10; chi-square 7 on 17 degrees of freedom against that model; observed mean 41.56, median 39, quartiles 26 and 55, three results of exactly 100). The probability mass function is in the note.
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/
    quote: "mean 41.56097561 / 25th percentile 26 / median 39 / 75th percentile 55"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  # --- Orb of Unravelling ---
  - id: memory_strands.unravelling_effect
    statement: >-
      An Orb of Unravelling applies to an identified equipment item with strands, spends all its strands (count 0 afterwards) and may raise the tier of its explicit mods; it may raise none. It ignores the prefix/suffix-cannot-be-changed metamods. It cannot raise an influenced mod to its Elevated form, and cannot turn a crafted mod into a regular one. A mod that is already the top tier is not raised, and top-tier mods do not change the chance of the others.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Orb_of_Unravelling
    quote: "Orb of Unravelling cannot upgrade influenced modifiers to an Elevated modifier. It also cannot upgrade a crafted modifier into a regular modifier, as of 3.26.0d."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: memory_strands.unravelling_chance_model
    statement: >-
      Approximate. Each explicit mod is tried on its own: it is raised with chance min(1, s * W_up / (2 * W_side)), W_up the sum of the weights of the mod type's higher tiers, W_side the total mod weight of its side (prefix or suffix) of the item's pool; if raised, the new tier is drawn from the higher tiers with weights, for each tier, its own weight plus the weights of the eligible tiers above it (equal to 1:2:3... for equal weights); the strand count changes only the chance, not how many tiers are climbed. The author does not claim the linear form is exact; the guaranteed points (chance 1) held in all 36,598 mods tested.
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/
    quote: "upgrade_chance = (strands * total_upgrade_candidate_weight)/(2 * total_side_weight)"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-30

  # --- Foulborn orbs ---
  - id: foulborn.effect_tier_cull
    statement: >-
      A Foulborn Orb of Augmentation, Regal Orb or Exalted Orb acts like its plain version, but the draw only sees the highest `K(N)` tiers of each mod type, N being the number of eligible tiers: K = ceil(N/2) for N <= 6, floor(N/2) + 1 for N > 6 (N = 1..13 gives 1,1,2,2,3,3,4,5,5,6,6,7,7). The same numbers come out of the strands formula at 175 instead of 147.5 + 2.5 s, i.e. a denominator of 100 + 75, which is how the wiki words it: '+75 Modifier Tier Rating'. Exact arithmetic (8 tiers: 100/175 * 7 is exactly 4).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Foulborn_currency_item
    quote: "it will only be able to roll the 4 highest eligible tiers and the lowest 3 tiers will be culled from the pool"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: foulborn.on_stranded_item
    statement: >-
      On an item with s >= 1 strands a Foulborn orb cuts as if the item had s + 30 strands: denominator 2.5 (s + 30) + 147.5 in `rollable_tiers`. The cut is made before the orb spends its strands. On an item with 0 strands the cut is the table above (denominator 175). The three orbs still spend strands (see foulborn.spend_ranges).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Modifier#Modifier_Tier_Rating
    quote: "In this model, Foulborn currency adds +75 to MTR, or an effective +30 Memory Strands."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: foulborn.weights_of_kept_tiers
    statement: >-
      Disputed, see the note. The wiki's Foulborn page says the kept tiers of a mod type are multiplied by N / K (N eligible, K kept), so the ratios between kept tiers stay and the mod type's total weight against other mod types changes (800/400/200/100 from the lowest tier, two kept, becomes 400/200). The in-game text of the Modifier Tier Rating passive says instead that the removed tiers' chance is distributed among the higher tiers of the same mod type (type total unchanged).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Foulborn_currency_item
    quote: "The weights of the remaining tiers of a modifier are then scaled independently according to a multiplier such that the relative weight ratios between the tiers of a modifier type remain the same"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: foulborn.spend_ranges
    statement: >-
      Foulborn Augmentation spends up to 32 strands, Foulborn Regal up to 48, Foulborn Exalted up to 62 on an item with 5 mods (smaller values for fewer mods are not published; PoEDB lists 28 as the single figure).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Memory_Strands
    quote: "Foulborn Orb of Augmentation	—	0-32"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: foulborn.availability
    statement: >-
      The three Foulborn orbs exist since 3.27.0 (drop level 68, 68, 80) and come only from the Genesis Tree, birthed from a Lavish Wombgift (currency womb, node Flawed Seeds for level 68 and above).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Foulborn_Orb_of_Augmentation
    quote: "Can be birthed from the Genesis Tree from a Lavish Wombgift."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  # --- Genesis Tree ---
  - id: genesis_tree.equipment_womb_item
    statement: >-
      A Provisioning Wombgift grown in the equipment womb births rare armour or jewellery (jewels and fractured items by node choice); the item's base item level is the Wombgift's own level. The passives are free to respec; the equipment womb has at most 16 passive points in 3.29.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/The_Genesis_Tree
    quote: "Rare equipment generated through the Genesis Tree have a base item level equal to the wombgift's specified level."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: genesis_tree.equipment_tier_rating
    statement: >-
      Three equipment-womb passives each give +20 Modifier Tier Rating to the birthed item (so +60 at most, on top of an inherent rating GGG lowered in 3.28.0 and 3.29.0 and has not published). The cut is made at birth, from the item's total rating (the Necropolis rule: the lowest `x / (100 + x)` share of each mod type's tiers is removed, wiki 'redistribution model').
    source_kind: datamined
    url: https://poedb.tw/us/Modifier_Tier_Rating
    quote: "Birthed Equipment has +20 to Modifier Tier Rating"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: genesis_tree.equipment_mod_type_weights
    statement: >-
      The equipment womb's mod-type passives are '300% increased chance' (weight x4) for one of 14 mod types (Physical, Fire, Cold, Lightning, Chaos, Life, Mana, Defences, Attributes, Resistance, Attack, Caster, Critical, Speed), and '60% reduced chance' (weight x0.4) for the same types (the multiplier reading of 'increased' and 'reduced' is the usual one, not stated by a source). Craft of Exile's Genesis table (1000 and 400, tier values 20/25/40/50) is older than 3.29.0 and loses.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/The_Genesis_Tree
    quote: "Equipment Genesis Tree Notable Passives that grant increased chance for Modifiers of a specific type now have values of 300% (previously 500%)."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

## Open points

1. **Weights of kept tiers after a cut (strands, Foulborn, tree rating): models (1), (2) or "unchanged".** Same tier ratios in all; the mod type's share of the pool differs. The Foulborn page says (2), the in-game text of the tree passive says (1), the strands page says nothing. Proposal: resolve with the sheet (or by an experiment with a high-weight mod and a low-weight mod on the same side), or build the action with the rule as one switch and run the benchmark routes under both.
2. **Which draws are cut.** Random mod adds and replacements for the currencies in the spend table, plus identification. Not documented: the *non-guaranteed* mods of an essence craft (the guaranteed essence mod is fixed), the mod of a fossil or Harvest craft (they spend no strands, and the wiki is silent on whether the cut applies), Vaal outcomes, recombinators, Hinekora's Lock previews. Until checked, treat a fossil or Harvest action on an item with strands as "cut unknown".
3. **What survives in the item's strands:** Scouring, Annulment, Divine, Vaal, corruption, fracturing, imprints (the wiki says imprints restore the count), Awakener's/Recombinator outputs. Not documented except imprints.
4. **Spend distribution** inside the ceiling (uniform is the working model; Chaos looks skewed), and what happens when the item has fewer strands than the roll (data show the count never goes below 0).
5. **Foulborn Exalted spend** for 1 to 4 mods (only 5 mods → 0-62 is known; PoEDB's 0-28 is one figure) and Exalted at 0 mods ("likely 0-10").
6. **Foulborn on a 0-strand item:** the wiki's N→K list matches `D = 175` exactly, but the raw sheet has no row for it; the Foulborn orbs' second use on the same item after its strands are spent has no test either.
7. **Unravelling:** linearity of the chance, destination weights (positional vs cumulative; the calculator and the post disagree), what happens to fractured, veiled, desecrated and enchanted mods, whether the strand cut is applied to the destination (the tiers above the mod are all "eligible", not limited by the current strands), the per-side pool weight definition (the post's own examples use the whole pool of the item class). Marked approximate in the claim.
8. **Remembrance:** jewels (the orb says "equipment"; jewels are a separate class on the wiki), whether the result depends on the earlier count (not tested), and the upper tail beyond the 3 hundreds.
9. **Genesis born items:** inherent tier rating after 3.29.0, strands on born items (none documented), item level, number of items per Wombgift, Hiveblood cost per Wombgift (shown on the item), and the tag-to-mod map (CoE's `mtypes` is a candidate; tags with several types: CoE adds the increases).
10. **Patch drift:** the wiki table is from a post dated 2026-09-26 (patch 3.29.0 league); the pinned patch is 3.29.3.3. The 3.29.1 notes (the only hotfix page read besides 3.29.0 and 3.29.0b) change only Genesis unique points; no 3.29.x note found changes strands, Unravelling or Foulborn (wiki pages for 3.29.2 and later did not load: not found or rate-limited, I did not tell which, so later hotfixes are unchecked there). The datamine (repoe-fork 3.29.3.3) has the orbs' names and descriptions only (`CurrencyAddZanaInfluence` is the Orb of Remembrance, `CurrencyRemoveZanaInfluence` the Orb of Unravelling, `CurrencyMutated…` the Foulborn orbs); it carries no strand numbers and no passive tree.

## What changes in the project (for the B5 grill)

- **ADR-0008 and two claims.** "Start items carry no Memory Strands" is replaced for B5: the start item has a strand count (parsed from the pasted item text "Memory Strands: N", or the trade filter), and the target stays free of it. `affix_pool.no_memory_strands` and the comment in `actions/pool.py` change from "never tier-gated" to "tier-gated when `s >= 1`".
- **State.** One more number per item, `s` in 0..100. For tier caps up to 13 the cut vector takes only **22** different values over 0..100 strands (28 for caps up to 15; 14 and 19 for Foulborn); the classes are `0 | 1 | 2-3 | 4-5 | 6-7 | 8-9 | 10-11 | 12-13 | 14 | 15-21 | 22-29 | 30-31 | 32-34 | 35-37 | 38-41 | 42-47 | 48-51 | 52-61 | 62-74 | 75-81 | 82-87 | 88-100`. The *spend* is random and uniform inside a ceiling, so a craft moves `s` by an amount that depends on the exact count; the classes help to size the pool tables, not to lump the state exactly. If a plan starts with 0 strands and no Remembrance, `s` stays 0 and nothing grows.
- **Action shape.** A cut draw is the ordinary draw on a pool whose low tiers are removed for the current `s`; the spend follows. Remembrance is a loop action on a normal item (re-roll until the count is good), priced at the orb's market price (about 56 chaos today); the planner may choose to re-roll. Foulborn orbs are three more plain currencies with a fixed `+75` and their own price (they come from the tree, so only the market sells them).
- **Genesis Tree.** A birthed item is a random start item; the planner starts "from a concrete item", so the tree is either a paste-in of an item the user already has, or a priced start source whose value is the mean over a distribution of items (the second needs the unpublished inherent rating).

## Questions for the owner

Each stands alone; recommendation first.

1. **Orb of Unravelling with approximate odds in v1?** It is the only way to use up strands to *raise* existing mods; its chance rests on a player-fitted formula (exact only where the chance is 100 %, 42 % observed against 47.9 % predicted at 15 strands). *With it:* strands can be spent deliberately at the end of a plan, the plan's odds for that step are marked approximate. *Without it:* strands are only burned by crafting, a stranded item is never unravelled. **Recommend: include it, marked approximate** (the same marking the project already plans for other player-fitted rules).
2. **Genesis Tree: a way to *get* an item, or a plan step?** *Item you already have (recommended):* you paste a tree-born item as the start item; no tree model. *Priced start source:* the planner compares "grow a Wombgift (feed Hiveblood) and craft the result" with "buy a base"; this needs the inherent tier rating GGG has not published, a price for Hiveblood (not tradeable: effectively free, limited), and an average over random items. **Recommend: the first for B5** and revisit when the numbers are known.
3. **Do you or someone you trust want to check three things in the game?** (a) The tooltip of a Foulborn Exalted Orb on items with 1, 2, 3 and 4 mods (strand ceiling); (b) whether a fossil craft on a stranded item still cuts low tiers; (c) whether an Orb of Scouring leaves the strands on the item. **Recommend: no.** You are not a crafter and the agents have no game; instead the planner refuses to use a fossil, Harvest reroll or Scouring on a stranded item (unknown → not admitted, ADR-0004) and uses a ceiling of 62 for Foulborn Exalted until read.
