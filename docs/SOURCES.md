# Sources (one row per source; nothing enters code or a fact sheet without a row here)

| id | URL or path | date read | used for | cached copy |
|---|---|---|---|---|
| S1 | Path of Building Community v2.67.2 (PoE 3.29), `src/Data/` (MIT licence; github.com/PathOfBuildingCommunity/PathOfBuilding) | 2026-09-20 | mod pools, weights, bases, essences, bench, veiled, eldritch | `sources/pob/Data/` (a copy of the parent project's pinned PoB data; not committed) |
| S2 | https://www.craftofexile.com/json/data/poec_common.json | 2026-09-20; focused read 2026-09-21 | Network smoke; bench quantities including `2775b52[2]` = 2 chaos for bench131 finish. JavaScript assignment, not standalone JSON. | `sources/raw/coe/poec_common.json`; 124215 bytes; SHA-256 `c188d17ab6f017123f49dcf2b89459fc98f8e9eac43f67f53b8bc65650cd5478` |
| S3 | https://www.craftofexile.com/packages/package.js | 2026-09-20; focused read 2026-09-21 | Method inventory; ordinary dispatch, draws, metamods; bench currency indexes; Divine integer sampler lines2529-2540. Contains PoE1/2 branches. | `sources/raw/coe/package.js`; 1525266 bytes; SHA-256 `faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639` |
| S4 | https://www.craftofexile.com/json/data/main/poec_data.json | 2026-09-20; focused read 2026-09-21 | Method lookup, PoB cross-check; bench2775/base52/tier2 range56..74 matched to PoB bench131. Not imported into engine. | `sources/raw/coe/poec_data.json`; 8651001 bytes; SHA-256 `2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a` |
| S5 | https://www.craftofexile.com/json/data/affinities/poec_affinities.json | 2026-09-20 | Cached for later review; no mechanics accepted from it yet | `sources/raw/coe/poec_affinities.json`; 5663642 bytes; SHA-256 `6264859bb58d2df6b7f8acf64a99ccfc68e5c2f027e5d97c61bdd81b06954f93` |
| S6 | https://www.craftofexile.com/json/data/exdata/poec_exdata.json | 2026-09-20 | Cached for later supplemental-data review | `sources/raw/coe/poec_exdata.json`; 1124447 bytes; SHA-256 `8c12f48182e2e10a48628c09062f6b865b9dc0edee84497dfb2ad441173204a9` |
| S7 | https://www.craftofexile.com/json/data/poec_guides.json | 2026-09-20 | Cached guide catalogue; guide evidence needs individual review | `sources/raw/coe/poec_guides.json`; 23098 bytes; SHA-256 `d4a45f7762d0e9d8a3ae45f1ee76795fdbea6b94658369efa4a6e29e884d1b68` |
| S8 | https://www.craftofexile.com/json/data/lang/poec_lang.us.json | 2026-09-20 | English names/text lookup; not a current-patch rules guarantee | `sources/raw/coe/poec_lang.us.json`; 399664 bytes; SHA-256 `b1434054209f1705182c3242310337e673f6cf6be94801ac63af8e7997b27869` |
| S9 | https://www.craftofexile.com/ | 2026-09-20 | PoE 1 page context and navigation/source discovery | `sources/raw/coe/index.html`; 28733 bytes; SHA-256 `35dfae13170e0de6ea50cc67c76ae34e6ae830e83e79b5f7de150d7a1ebbca98` |
| S10 | `sources/pob/Data/ModExplicit.lua`, key `Strength1`, line 5 | 2026-09-20 | Datamined input for worker smoke test; no eligibility interpretation | Local S1 snapshot; SHA-256 `6d400101f60ec48f854daad9a5ca2479b43e9e405f92724e80631b276eaf4568` |
| S11 | `sources/pob/Data/ModMaster.lua`, lines 732-736, `ItemGeneration*` groups | 2026-09-20 | Datamined metamod affix sides, names, level fields and supported class list | Local S1 snapshot; SHA-256 `ddf3fb7499539db0596678d9527c433cc043fa68555f2ea47687b6ffd94cd301` |
| S12 | https://www.craftofexile.com/js/poe1.js | 2026-09-20 | PoE 1 overrides: omen checks return false; named special-base IDs | `sources/raw/coe/poe1.js`; 1672 bytes; SHA-256 `8dbeda50b0fca1ddab8057bdefda68bd0db40d8c04646fec434524bd3c82ea02` |
| S13 | https://www.craftofexile.com/?page=basics | 2026-09-20 | Currency descriptions, rarity limits, bench and crafting prose; stale claims flagged | `sources/raw/coe/basics.html`; 27689 bytes; SHA-256 `1399963fa6709c8c3f7df1a5d528398fbeb97146faae638a1798cc00c992d10e` |
| S14 | https://www.craftofexile.com/?page=metamods | 2026-09-20 | Metamod interaction table including cell classes and notes; author warns about patch lag | `sources/raw/coe/metamods.html`; 22734 bytes; SHA-256 `979a268175e91f2a073545dd50df7ef62054cdb8382e06e36e92efb62f384aef` |
| S15 | https://www.craftofexile.com/?page=advanced | 2026-09-20 | Mod-group blocking and item-level strategy leads; historical recipes not accepted | `sources/raw/coe/advanced.html`; 16709 bytes; SHA-256 `1cd95c1b84478e9fd8ec7b8ce6c18f8a354b5b4c7b56ab5e35e3f39ec204ce4a` |
| S16 | https://www.poewiki.net/wiki/Metamod | 2026-09-20 (attempt only) | Access limitation Q5; no wiki facts obtained | `sources/raw/wiki/Metamod.html`; 7811-byte Anubis challenge, not the article; no retry |
| S17 | https://www.poewiki.net/wiki/Metamod | 2026-09-20, user-opened browser session | Overview, Rules and Exceptions, Examples, Version history; includes explicit confirmation-needed flags | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md`; page edited 2026-08-11; not a full HTML cache |
| S18 | https://www.poewiki.net/index.php?title=Version_3.27.0&oldid=1674443 | 2026-09-20, browser | Harvest behavior change and link to official patch notes | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S19 | https://www.pathofexile.com/forum/view-thread/3869068 | 2026-09-20, browser | Official Content Update 3.27.0, League Changes: Harvest respects modifier-type restrictions | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S20 | https://www.poewiki.net/wiki/Chaos_Orb | 2026-09-20, browser | Mechanics review; no independent count weights obtained from the reviewed section | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S21 | https://www.poewiki.net/index.php?title=Essence&oldid=1700895 | 2026-09-20, browser | Crafting section: rare reforge tier threshold and low-tier random-mod level caps | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S22 | `sources/pob/Data/Essence.lua`, key `Metadata/Items/Currency/CurrencyEssenceRage4` | 2026-09-20 | Shrieking Rage tier 6, Helmet -> Strength8 mapping | Local S1 snapshot (ignored); own projection `data/pob_essences.json` accepted in `8d49e8f` |
| S23 | https://www.poewiki.net/wiki/Orb_of_Conflict | 2026-09-20, browser | Non-unique / dual-implicit eligibility, Lesser removal, relative-tier odds; approximate odds cite a player post on the page | Selected observation in `sources/raw/wiki/browser-observations-2026-09-20.md`; last edited 2026-07-26 |
| S24 | `sources/pob/Data/ModExplicit.lua`, all rows, keys `Strength1`, `Strength8`, `DeepwaterSwordGrantedSkillGhostCannons` | 2026-09-20 | Builder acceptance: 4310 rows/IDs, zero skipped rows; lines 5, 12, 4314 | Local S1 snapshot; same SHA-256 as S10. Own limited projection `data/pob_mod_explicit.json` from `tools/build_pob_explicit.py`, hash `e09344ce07c248bfef894aaf85141b5ec9be87f10da1709527d29e657bb92fb9` |
| S25 | `sources/pob/Data/ModVeiled.lua`, keys `JunMasterAvoidStunAndElementalStatusAilments1`, `JunMasterVeiledLocalIncreasedPhysicalDamageAndImpaleCrafted`, lines 5-6 | 2026-09-20 | Verify definitions and literal fields; not an unveiling probability model | Local S1 snapshot (ignored) |
| S26 | https://www.poewiki.net/index.php?title=Modifier&oldid=1697362 | 2026-09-20, user-opened browser | Mod Level, Group/family, Spawn weight tag, Mod tag; first matching spawn weight and multiple exclusion families | Selected observations in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S27 | `sources/pob/Data/Bases/{helmet,bow,ring,body,gloves}.lua` | 2026-09-20 | Five-class literal base projection; keys Iron Hat line 6, Crude Bow line 5, Iron Ring line 6, Simple Robe line 412, Iron Gauntlets line 6 | Local S1 snapshot; per-file hashes and 375-record specification in `docs/specs/2026-09-20-pob-base-tags.md` |
| S28 | https://poedb.tw/us/Helmets_str | 2026-09-20 | Ordinary life family, 10 tiers, for cross-check with Iron Hat | `sources/raw/poedb/Helmets_str.html`; SHA-256 `41b793f58fb74c3ae8d3bb450db69d31f68b05c1cdfc8b1f8620939d792ad20b` |
| S29 | https://poedb.tw/us/Bows | 2026-09-20 | Ordinary flat fire family, 10 tiers, group discrepancy versus PoB | `sources/raw/poedb/Bows.html`; SHA-256 `bb515fa6f35eaa471472a7866cf5eb97d1a0c93d3b1e0af12346fd03a39e98c2` |
| S30 | https://poedb.tw/us/Rings | 2026-09-20 | Ordinary cold resistance 8 tiers and chaos resistance 6 tiers | `sources/raw/poedb/Rings.html`; SHA-256 `cd2a59059e375817c34062b1b71fe0c162c765c5e21fde2a45d2e1680273b929` |
| S31 | https://poedb.tw/us/Body_Armours_int | 2026-09-20 | Ordinary flat energy shield, 11 tiers, group discrepancy versus PoB | `sources/raw/poedb/Body_Armours_int.html`; SHA-256 `4ec519836677852231b21d5bc38c402e0aa5549516edc0f30d84c2919e29ba2b` |
| S32 | https://poedb.tw/us/Gloves_str | 2026-09-20 | Ordinary Strength, 9 tiers | `sources/raw/poedb/Gloves_str.html`; SHA-256 `082f4aaa7cad9b5ae1dfab63d12c1775fe1fad11c7a30c00611c9fb2de81fc0f` |
| S33 | https://www.poewiki.net/index.php?title=Fracturing_Orb&oldid=1681353 | 2026-09-20, browser before restart | Mechanics and 3.29 tooltip/synthesis condition; no independent equal-odds proof | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S34 | https://www.poewiki.net/index.php?title=Veiled_Exalted_Orb&oldid=1681145 | 2026-09-20, browser before restart | Remove/add order, metamods, signature exclusion and 3.26 naming | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S35 | https://www.poewiki.net/index.php?title=Veiled_Chaos_Orb&oldid=1681146 | 2026-09-20, browser before restart | Rare reforge, forced veil, signature exclusion, 3.26 reintroduction | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S36 | https://www.poewiki.net/index.php?title=Veiled_modifier&oldid=1675918 | 2026-09-20, browser before restart | Three offers followed by player choice; unveiled is not bench-crafted | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S37 | https://www.poewiki.net/index.php?title=Vaal_Orb&oldid=1702321 | 2026-09-20, browser before/after restart | Equipment outcome categories; 3.29 socket wording (confirmed by S39); tainted/bench exceptions | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S38 | https://www.poewiki.net/index.php?title=Locus_of_Corruption&oldid=1673917 | 2026-09-20, browser | Four category outcomes, destruction, eligibility, replacement and version conditions | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S39 | https://www.pathofexile.com/forum/view-thread/3985332 | 2026-09-20 | Official 3.29.0 notes: Gem Socket Changes, Talisman Revamp, Item Changes, new bench options | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md; full page not downloaded |
| S40 | https://www.poewiki.net/index.php?title=Awakener%27s_Orb&oldid=1697721 | 2026-09-20, browser | Input conditions, receiver properties, tier/value retention, metamods, conflict survivor discrepancy | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S41 | https://www.poewiki.net/index.php?title=Recombinator&oldid=1701130 | 2026-09-20, browser | Two operating modes, input destruction, ilvl formula, estimated count table and internal 70/72 conflict; page update warning retained | Selected paraphrases in sources/raw/wiki/browser-observations-2026-09-20.md |
| S42 | https://www.poewiki.net/index.php?title=Harvest_crafting&oldid=1699145 | 2026-09-20, browser | Current tag reforges and add/remove recipes; metamod conditions and resource amounts | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S43 | https://www.poewiki.net/index.php?title=Orb_of_Dominance&oldid=1699839 | 2026-09-20, browser | Class/rarity gates, tier transformation and protection | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S44 | https://www.poewiki.net/index.php?title=Beastcrafting&oldid=1673867 | 2026-09-20, browser | Beast-level exchange, current recipes, Matron singleton and synthesis unique restriction | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S45 | https://www.poewiki.net/index.php?title=Imprint&oldid=1702288 | 2026-09-20, browser | Restoration identity, stored properties and fracture/corruption exceptions | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S46 | https://www.poewiki.net/index.php?title=Catalyst&oldid=1675910 | 2026-09-20, browser | Level-dependent quality, type reset, special catalysts | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S47 | https://www.poewiki.net/index.php?title=Quality&oldid=1673652 | 2026-09-20, browser | Quality amount conditions and worked armour example 342 | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S48 | https://www.poewiki.net/index.php?title=Crusader%27s_Exalted_Orb&oldid=1683018 | 2026-09-20, browser | Rare/no-influence gate and excluded item flags | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S49 | https://www.poewiki.net/index.php?title=Influenced_item&oldid=1635654 | 2026-09-20, browser | Influence persistence, 15 pairs, Astrolabe exception and ambiguous orb wording | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S50 | https://www.poewiki.net/index.php?title=Synthesised_item&oldid=1675552 | 2026-09-20, browser | 3.29 availability, implicit replacement, retained base status and level distinction | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S51 | https://www.poewiki.net/index.php?title=Blessed_Orb&oldid=1681166 | 2026-09-20, browser | Rollable implicit gate and old-value exclusion conflicting with CoE | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S52 | https://www.poewiki.net/index.php?title=Eldritch_implicit_modifier&oldid=1697697 | 2026-09-20, browser | Six tiers, ordinary classes, dominance and exceptional amulets | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S53 | https://www.poewiki.net/index.php?title=Eldritch_Chaos_Orb&oldid=1683049 | 2026-09-20, browser | Rare rarity, dominant side and equal-tier rejection | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S54 | https://www.poewiki.net/index.php?title=Eldritch_Exalted_Orb&oldid=1683050 | 2026-09-20, browser | Rare rarity, Exarch prefix / Eater suffix addition | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S55 | https://www.poewiki.net/index.php?title=Eldritch_Orb_of_Annulment&oldid=1683051 | 2026-09-20, browser | Magic or rare rarity, dominant-side removal | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S56 | https://www.poewiki.net/index.php?title=Fossil&oldid=1702302 | 2026-09-20, browser | Community-interpreted tag multipliers and explicit additive/multiplicative dispute | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S57 | https://www.poewiki.net/index.php?title=Crafting&oldid=1697718 | 2026-09-20, browser | Catalogue completeness: socket/enchantment, unique, Memory, Allflame and other families; overview wording conflicts Q29 | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S58 | https://www.poewiki.net/index.php?title=Resonator&oldid=1675208 | 2026-09-20, browser | Chaotic rare gate, Ruthless alchemical distinction, fossil uniqueness and block precedence | Selected paraphrases in `sources/raw/wiki/browser-observations-2026-09-20.md` |
| S59 | `sources/pob/Data/ModEldritch.lua`, all rows, first key `IncreasedAttackSpeedEldritchImplicit1` line 5 | 2026-09-20 | 4086 literal definitions: Exarch 2016 / Eater 2070; no inferred transition odds | Local S1 snapshot; SHA-256 `39619b75effd511c3a28438fc3f79d75974a97b6056f4e282801a7215f13e22f`; own projection `data/pob_mod_families.json` |
| S60 | `sources/pob/Data/ModCorrupted.lua`, all rows | 2026-09-20 | 371 literal corruption modifier definitions; no inferred outcome distribution | Local S1 snapshot; SHA-256 `de8ca9043284925a18a617c15a9d3f26b5b1b039239935ff0c1741e76a8ae8ba`; own projection `data/pob_mod_families.json` |
| S61 | `sources/pob/Data/ModDelve.lua`, all rows | 2026-09-20 | 186 literal definitions: DelveImplicit 9 / Prefix 74 / Suffix 103; optional arrays preserved | Local S1 snapshot; SHA-256 `7721301d4cc1b95d7722b224e09c8da8a80c2da1969323d0fff9038b0ad21d56`; own projection `data/pob_mod_families.json` |
| S62 | `sources/pob/Data/ModSynthesis.lua`, all rows, first key `SynthesisImplicitLife1` line 5 | 2026-09-20 | 1344 literal definitions, including empty weight arrays; not synthesis selection probabilities | Local S1 snapshot; SHA-256 `dba033ff1d884f1500ae3ce99520f4a4d5b4162ac6885eaa97cf88b759eb351c`; own projection `data/pob_mod_families.json` |

Download policy: one GET per URL, no automatic retries; use the local copy thereafter.
Cached third-party bytes are ignored by Git. Their presence does not establish that every field has been reviewed.

Additional S3 review on 2026-09-20: fossil weights (`poec_workoutFOMTypes`, `poec_getModdedWeight`),
calculator exact/extrapolation paths (`poec_computePermutationsV2`, `poec_computeFinalProbsV2`),
and simulator configuration (`poec_nsimBuildConfig`, `poec_nsimRelayConfigData`). Notes in
`docs/research/coe-calculator-and-policies.md`; no new download.

Further S3 review: Awakener pair/conflict selection (1926-1933, 2443-2446), corruption
(2805-2822), recombination (1886-1925), and per-action policy execution (3365-3399).
Source-local algorithms and cross-source differences are recorded in their sheets; no JS executed.

S11 full-file acceptance on 2026-09-20: 732 anonymous ModMaster rows, lines 5-736;
SHA-256 ddf3fb7499539db0596678d9527c433cc043fa68555f2ea47687b6ffd94cd301.
Own projection data/pob_bench.json, builder tools/build_pob_recipes.py; statOrder:308
contains [857,857.1]. These are ordering literals, not asserted integer game stat IDs.
S22 full-file acceptance: 105 Essence rows, lines 5-109, 2310 class mappings / 622 referenced
ModExplicit IDs; all references found. Source SHA-256
977d1d744bade2d16092511e2d86771b7a3ae7df72a74d97461ebeb310aa1b20.
Own projection data/pob_essences.json. Version pin remains owner-supplied (Q8).
S7 guide-directory review: 52 references (37 video / 15 written), date field spans
2022-01-23 through 2023-09-26. No embedded article bodies; no linked recipe treated as read.

S24/S25/S59-S62 full-family acceptance on 2026-09-20 (merge 375528a): all 15 fields of
10555 records independently matched to raw source. S25 has 258 rows (Prefix 162 / Suffix 96),
SHA-256 72dd5ce5e5ed5e00ace5a69700e522ce23fde692b5cc37d97c706811ce309460.
S24's full projection now includes stat_text/statOrder and optional generated tags/multipliers;
the earlier limited projection remains for its existing cross-check consumer.
`tools/build_pob_mod_families.py` output: 7755518 bytes, SHA-256
a37bd981e34e1d43cbb12c1b7009ab86cc63fa357bdaba41ad20d8d2ba39aee4 (UTF-8 LF).
Ranges remain literal strings, no tiers or numeric game stat IDs inferred. Metadata still
records the owner-supplied version rather than an invented upstream commit (Q8).

## Goal 2 source additions — read 2026-09-21

| id | URL or path | date read | used for | cached copy |
|---|---|---|---|---|
| S63 | https://poedb.tw/us/Screaming_Essence_of_Sorrow | 2026-09-21 | Tier5 item tooltip permits normal upgrade OR rare reforge; S21 corroboration | sources/raw/research/goal2-observations.md |
| S64 | https://www.pathofexile.com/forum/view-thread/3877954 | 2026-09-21 | Historical player bug report, Warlord amulet; no staff reply and no draw-by-draw evidence | sources/raw/research/goal2-observations.md |
| S65 | docs/OWNER_QUESTIONS.md, answers1-15; goal attachment read2026-09-21 | 2026-09-21 | Owner confirmations, provisional prices, CoE fossil default authorization | Tracked owner answers; D20/D21 record decisions |
| S66 | https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ | 2026-09-21 | Butsicles3.25 empirical counts, exclusives and NNN notation; historical baseline | sources/raw/research/recomb-reddit-3.25-and-links.txt |
| S67 | https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/ | 2026-09-21 | Butsicles3.26 corrections, limited tests and cross-game predictable-mode claim | sources/raw/research/recomb-reddit-3.26-and-links.txt |
| S68 | https://www.reddit.com/r/pathofexile/comments/1lfyxxd/326_recombinators_analysisguide/ | 2026-09-21 | statistically-typed post linking the circles/arrows guide; author discussion | sources/raw/research/recomb-reddit-3.26-and-links.txt |
| S69 | https://codeberg.org/poe_notes/poe_notes/src/branch/main/Recombinators.md | 2026-09-21 | Overexplained Guide, ten diagram references/descriptions, stated assumptions and recipe comparisons | sources/raw/research/recombinators-codeberg.md; diagram descriptions in recombinator-diagrams.md |
| S70 | https://www.reddit.com/r/PathOfExile2/comments/1jzu2py/poe_2_patch_020_guide_to_recombinators_part_1/ | 2026-09-21 | PoE2 patch0.2.0 two-selected-mod experiments/formula; not direct PoE1 proof | sources/raw/research/recomb-poe2-and-links.txt |
| S71 | https://www.pathofexile.com/forum/view-thread/3315559 | 2026-09-21, browser | Guy_GGG corrects Wiki affiliation; mechanics claims in this thread are PLAYERS, not a GGG ruling | sources/raw/research/goal2-browser-findings.md |
| S72 | https://poedb.tw/us/Resonator | 2026-09-21 | Four Chaotic resonator tooltips all target rare items; S58 corroboration | sources/raw/research/goal2-browser-findings.md |
| S73 | sources/pob/Data/Bases/amulet.lua; sources/pob/Data/Bases/boots.lua | 2026-09-21 | Literal105/81 source records for external-validation classes | Ignored S1 snapshots; hashes and examples in specs/2026-09-21-validation-base-classes.md |
| S74 | https://www.pathofexile.com/forum/view-thread/3531661 | 2026-09-21, browser | Official3.25 Item Quality rework explicitly includes Catalysts; non-unique increments depend on ilvl | sources/raw/research/official-quality-3.25.txt |

Rechecks2026-09-21: S17 same revision1700578 read through Playwright, full rendered text in
`sources/raw/research/wiki-metamod-2026-09-21.txt`; S47 same revision1673652, full text and
100-row increment table in `wiki-quality-2026-09-21.txt` and `wiki-quality-table-2026-09-21.txt`.
S58 same revision1675208 in `wiki-resonator-2026-09-21.txt`; S33 same revision1681353 in
`wiki-fracturing-2026-09-21.txt`, all under sources/raw/research/. No CoE file was refetched.
