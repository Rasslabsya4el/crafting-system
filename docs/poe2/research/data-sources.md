# PoE2 crafting: data sources and tools

- **Checked:** 2026-11-24, from the owner's server (plain `curl` with a generic browser User-Agent, no cookies, no login).
- **Game:** Path of Exile 2, patch 0.5.5 (repoe-fork export `0.5.5.10`; poe2db lists hotfixes up to 0.5.5d).
- **Leagues seen** (`/api/trade2/data/leagues`): `Forbidden Rites` (current: poe2scout `IsCurrent: true`), `HC Forbidden Rites`, `Runes of Aldur` (previous), `HC Runes of Aldur`, `Standard`, `Hardcore`.
- **Purpose:** porting a PoE1 planner that uses repoe-fork, poe.ninja, the official trade API and Craft of Exile's emulator.

## Summary

| Source | Holds | Freshness (seen) | Trust | Plain server request |
|---|---|---|---|---|
| repoe-fork PoE2 export | Mods, base items, tags, item classes, stat translations, `mods_by_base`. **Spawn weights are 0/1 only.** No essences/fossils/bench files | `0.5.5.10`, exported 2026-11-19 | High for structure (it is the game files). It has no real weights | 200, static JSON |
| poe2db.tw | Per-base modifier pages with tiers, ilvl and **estimated weights** (`DropChance`); currency, omen, essence and desecrated lists | 0.5.5 (hotfix 0.5.5d) | High for structure. The weights are community estimates (Krakenbul), and some are missing | 200, HTML with JSON embedded |
| Craft of Exile PoE2 (www) | Emulator data `poec_data.json`: mods, tiers, weights, essences, catalysts; prices | **Stale:** data 2026-06-16, version `0.5.0`, prices for Runes of Aldur 2026-07-13 | Medium | 200 |
| Craft of Exile PoE2 (beta) | `json/poe2/0.5.5.5/data.json`: mods, classmods with weights, essences, omens (`methods.omens`); `prices.json` keyed by metadata path | data 2026-11-23, `0.5.5.5` | Medium. Weights estimated; `1` = stand-in | 200 |
| Official trade2 API | `data/stats`, `data/items`, `data/static`, `data/leagues`; search, fetch and bulk exchange | live | Authoritative for listings | 200 anonymous (rate-limited) |
| Official Currency Exchange digest | Hourly per-league market digests (volume, stock, ratios), keyed by metadata path | hourly; current hour not given | Authoritative (real trades) | `web.poecdn.com/api/currency-exchange/poe2/<ts>` 200; `www.pathofexile.com/api/currency-exchange/poe2` 401 |
| poe.ninja PoE2 | Exchange overviews per category (Currency, Essences, Ritual = omens, Abyss, Runes, SoulCores, ...) | live (Forbidden Rites) | High | site page **403** (bot wall); `/poe2/api/...` JSON **200** |
| poe2scout | Currency and unique prices with daily history; leagues; exchange snapshot; MIT source | live, Forbidden Rites to 2026-11-24 | Medium-high | `api.poe2scout.com` 200 (Cloudflare cache) |
| poe.watch | PoE1 only; no PoE2 found (`poe2.watch` does not resolve) | n/a | n/a | n/a |
| Path of Building PoE2 | `ModItem.lua` (weights 0/1, same as RePoE), **`Essence.lua` (essence to mod per item class)**, runes, corrupted | data export 0.5.5 (2026-09-10); repo push 2026-11-24 | High as a cross-check | 200 (GitHub raw) |
| dat-schema + pathofexile-dat | Schema for PoE1 and PoE2 `.datc64` tables (`validFor`: 1 PoE1, 2 PoE2, 3 both); exporter library | schema built 2026-11-18; `pathofexile-dat` 16.0.1, 2026-10-19 | High (community-maintained schema) | 200 (GitHub release / npm) |

---

## 1. repoe-fork PoE2 export

- **URL:** https://repoe-fork.github.io/poe2/ (GitHub Pages); source https://github.com/repoe-fork/poe2 (exporter code: https://github.com/repoe-fork/repoe).
- **Version:** the page title reads `RePoE - PoE2 version 0.5.5.10`. The last commits are `[skip ci] Export 0.5.5.10` on 2026-11-19 02:13 UTC and `Version 0.5.5.10` on 2026-11-18.
- **Licence:** neither repo states an SPDX licence (`NOASSERTION`); the data is (c) Grinding Gear Games. The PoE1 port already uses repoe-fork under the same terms.
- **Access:** 200, static files, no protection. Every file comes as `.json` and `.min.json`. `index.json` is the directory tree.

**Files at the root:** `active_skill_types`, `ascendancies`, `audio`, `augments`, `base_items`, `buff_visuals`, `buffs`, `characters`, `cost_types`, `default_monster_stats`, `flavour`, `gem_tags`, `item_classes`, `keywords`, `mods`, `mods_by_base`, `skill_gems`, `skills`, `stat_value_handlers`, `stats_by_file`, `tag_details`, `tags`, `uniques`, `world_areas`; directories `stat_translations/`, `base_items/`, `passive_skill_trees/`, `Metadata/`, `Art/`.

**Missing compared with PoE1 RePoE:** `essences.json` (404), `fossils.json`, `crafting_bench_options.json`, `mod_types.json`, `cluster_jewels.json`, `harvest`/`beast` crafts. Nothing maps omens or currencies to their effects, apart from the in-game `description` text in `base_items`.

**`mods.json`** has 16,911 mods. Domains include `item` (8,151), `desecrated` (415) and `crafted` (45). Generation types include `prefix` (2,767), `suffix` (2,458), `essence` (117), `corrupted` (126) and `unique`. The entry shape is the same as PoE1:

```json
"Strength5": {"domain": "item", "generation_type": "suffix", "groups": ["Strength"],
  "implicit_tags": ["attribute"], "is_essence_only": false, "name": "of the Gorilla",
  "required_level": 44,
  "spawn_weights": [{"tag": "ring", "weight": 1}, {"tag": "str_armour", "weight": 1}, ..., {"tag": "default", "weight": 0}],
  "generation_weights": [], "stats": [{"id": "additional_strength", "min": 21, "max": 24}],
  "text": "+(21-24) to [Strength|Strength]", "type": "Strength", "gold_value": null}
```

**Spawn weights:** across all 2,586 item-domain prefix and suffix mods, every `spawn_weights` value is **0 or 1** (3,811 zeros and 3,329 ones; no other value). The PoE2 client keeps only an "allowed on this tag" flag. GGG does not ship real weights, as poe2db and Craft of Exile both state (sections 2 and 3). So repoe-fork gives eligibility, tiers (`required_level`), groups, stats and tags, but **no probabilities**.

**Other files:**
- **`base_items.json`:** keyed by metadata path, for example `Metadata/Items/Currency/OmenOnChaosPrefix` (`item_class: "Omen"`, `properties.description: "...your next Chaos Orb will remove only prefix modifiers"`). It lists 868 `StackableCurrency` entries, 50 `Omen`, 88 essences (Lesser to Perfect) and 313 `SoulCore`. Greater and Perfect currency tiers are separate bases (`CurrencyAddModToRare2`, `...3`).
- **`mods_by_base.json`:** item class, then a tag set, then `{bases: [...], mods: {...}}`.

---

## 2. poe2db.tw

- **URL:**
  - Per base-type page: https://poe2db.tw/us/Body_Armours_str (pattern `<Class>_<attr>`).
  - Lists: `/us/Omen`, `/us/Essence`, `/us/Stackable_Currency`, `/us/Desecrated_Modifiers`, `/us/Modifiers`.
  - Weights explanation: https://poe2db.tw/us/weightings.
- **Licence:** "Content is available under CC BY-NC-SA 3.0 unless otherwise noted". That means attribution, **non-commercial** use, and share-alike.
- **Freshness:** the home page links patch notes up to Version 0.5.5d.
- **Access:** 200, plain HTML (the Body Armour str page is 462 KB). The mod table is a JSON blob inside the page; there is no public JSON API.

**Shape** (embedded on the Body_Armours_str page, after `"opt":{"ModDomainsID":1,"ItemClassesCode":"Body Armour","tags":"str_armour"}`):

```json
"normal":[{"Name":"of the Brute","Level":"1","ModGenerationTypeID":"2","ModFamilyList":["Strength"],
  "DropChance":"1000","str":" +(5 — 8) to Strength ","fossil_no":["attribute"],
  "spawn_no":["ring","amulet",...,"default"],"hover":"?s=Data%5CMods%2FStrength1"}, ...]
```

- `ModGenerationTypeID` is 1 for a prefix and 2 for a suffix; 5 (corrupted) also appears.
- `hover` carries the mod id (`Strength1`), which joins with repoe-fork.

**Weights:** `DropChance` holds real-looking values on that page. Of 144 normal mods, 100 have 1000, 19 have 500, 10 have 800, 6 have 250 and 5 have 900; the rest are 400, 300, 200 and 100. For example, chaos resistance is 250 on every tier, `StunThreshold` is 800, and `BaseSpirit` steps 500 → 500 → 500 → 500 → 400 → 300 → 200 → 100 by tier. The weightings page says: *"Weight information cannot be obtained from game file. Following weight information compiled by Krakenbul, the author of Prohibited Library Discord Mods Weight SpreadSheets using recombinators. ... For bases that cannot be recombined, such as Charms, Jewels, Tablets and Waystones is obtained from parsing trade-site listings. Desecrated Mods on different Item Class was queried from Trade."*

**Unmeasured marker:** a downstream tool (Augur, PR #40, 2026-11-05, RePoE 0.5.5.5) found that a numeric `DropChance` of `1`/`0` (as opposed to a quoted string) is poe2db's marker for "not measured". Its run on 59 pages matched 6,434 weights to RePoE ids and found 1,961 mods unmeasured. The same PR says 18 item classes had no weights then (claws, daggers, 1H/2H swords and axes, maces, traps, jewels, charms, flasks, and str/dex/int body armour). Its spot check against Craft of Exile found 464 weights identical and 15 different, all 15 being CoE stand-in values of 1. Source: https://github.com/ShigenoTV/Augur/pull/40.

---

## 3. Craft of Exile (PoE2)

- **URL:** https://www.craftofexile.com/?game=poe2 (stable); https://beta.craftofexile.com/?game=poe2 (beta, current data); weights note at https://www.craftofexile.com/weightings?game=poe2.
- **Licence:** none published. It is a private site (Patreon, ads), and its data files are not licensed for reuse. The PoE1 port already keeps a local copy only for emulator checks (`.claude/skills/coe-emulator-check`). Treat CoE as a cross-check, not as a pinned input.
- **Access:** 200 on the page and the JSON files. The files are JS assignments (`poecd=` or `coedata=`), so strip up to the first `=` before parsing.

**Stable site (www): stale.** The page loads these files:
- `json/poe2/main/poec_data.json?v=1781640702` (Last-Modified 2026-06-16; the page sets `version='0.5.0'`)
- `json/poe2/prices/poec_prices.json?v=1783967583` (2026-07-13; index `Runes of Aldur` only)
- `json/poe2/lang/poec_lang.us.json`
- `json/poe2/poec_common.json`

**What `poec_data.json` holds:**
- Top-level keys: `bitems`, `bases`, `bgroups`, `modifiers` (1,364), `mgroups` (Base, Desecrated, ...), `mtypes`, `fossils` (0), `catalysts` (13), `essences` (95, with per-base tiers), `tiers`, `basemods`, `modbases`, `socketables`.
- Each `tiers[mod][base]` row looks like `{"ilvl":"1","weighting":"1000","nvalues":"[[5,8]]"}`.
- Weight values across all tier rows: `1` in 10,705 rows (the stand-in), then `1000` (4,137), `500` (1,271), `0`, `800`, `750`, `250`, `100`, ...

**Beta site: current.** It loads these files:
- `json/poe2/0.5.5.5/data.json?v=1795440831` (Last-Modified 2026-11-23)
- `json/poe2/0.5.5.5/prices.json?v=1794755494` (2026-11-15)
- `json/poe2/0.5.5.5/localization/english.json`

**What the beta `data.json` holds** (`coedata=`):
- Top-level keys: `categories`, `classes`, `items`, `mods`, `modgroups`, `classmods`, `tags`, `families`, `essences` (`classmods`, `basemods`, `byessences`), `socketables`, `enums`, `stats`, `methods` (`modules`, `crafting`, `omens`, `socketables`), `skills`, `emotions`.
- `classmods[classId][modIndex] = weight`. Values across all classes: `1000` (6,286), `1` (4,041, stand-in or unmeasured), `500` (2,114), `800`, `750`, `250`, `200`, ...
- `methods.omens.entries` lists the omens it implements, for example `{"item":4436,"action":"OmenOnChaosPrefix","constraints":null}`.

The beta `prices.json` is keyed by metadata path, valued in chaos:

```
coeprices={"leagueSoftcore":{"Metadata/Items/Currency/CurrencyUpgradeToRare":0.01393,"Metadata/Items/Currency/CurrencyAddModToRare":0.001667, ...
```

**Weights statement** (CoE weightings page): *"the information regarding modifier weightings is not part of the game client's for Path of Exile 2. However thanks to Krakenbul and the people at the Prohibited Library Discord [they] have devised a way of finding them out using recombinators."* Bases that cannot be recombined use trade listings plus a normalisation script ("apply breakpoints ... create familiar curves"), and the page itself warns of a bias toward desirable mods. So CoE and poe2db share **one** origin for weights: Krakenbul's recombinator measurements.

---

## 4. Official trade site and APIs (PoE2)

**Static data:** https://www.pathofexile.com/api/trade2/data/{stats,items,static,leagues}. All return 200 anonymously, behind Cloudflare with `cache-control: max-age=14400`.

- **`stats`** (855 KB) has groups `pseudo` (36), `explicit` (3,108), `implicit`, `fractured`, `crafted`, `enchant`, `rune` (595), `desecrated` (755), `sanctum` and `skill`. Example entry: `{"id":"explicit.stat_3299347043","text":"# to maximum Life","type":"explicit"}`. The number is the stat hash, the same as PoB's `tradeHashes`.
- **`static`** has `Currency` (40), `Fragments`, `Runes` (213), `Ritual` (omens), `Abyss`, `Essences` (84), `Breach`, `Delirium`, `Expedition`, `Vaal`, `UncutGems`, `LineageSupportGems`, `Waystones` and `Verisium`. Example entry: `{"id":"transmute","text":"Orb of Transmutation","image":...}`.

**Search, fetch and exchange** work anonymously:
- **Search:** `POST /api/trade2/search/poe2/<league>`. A rare chest search in Forbidden Rites returned `total: 10000` and listing ids.
- **Fetch:** `GET /api/trade2/fetch/<ids>?query=<id>`. It returns `{id, listing{price{type,amount,currency}}, item{..., explicitMods, extended{hashes{explicit:[[stat_id,[idx]]]}}}}`. The sampled item had no `extended.mods` tier or magnitude block, unlike what PoE1's fetch usually returns.
- **Bulk exchange:** `POST /api/trade2/exchange/poe2/<league>` with `{"query":{"have":["exalted"],"want":["divine"],...},"engine":"new"}` answers 200, but returned `total: 0` in both Standard and Runes of Aldur on this check.

**Rate limits** (response headers):

| Endpoint | `x-rate-limit-ip` |
|---|---|
| search | `5:10:60,15:60:300,30:300:1800,600:21600:3600` |
| fetch | `12:4:10,16:12:300,50:300:300,1000:21600:1800` |
| exchange | `5:15:60,10:90:300,30:300:1800` |

Read each rule as hits:seconds:penalty-seconds.

**Developer docs** (https://www.pathofexile.com/developer/docs):
- **Terms:** use OAuth 2.1, register an app, and send `User-Agent: OAuth {clientId}/{version} (contact: ...)`. The Third-Party Notice bars any suggestion of GGG endorsement. The page says "There are currently limited APIs that return PoE2 game information."
- **PoE2 coverage:** public stash tabs are **PoE1 only**. Leagues, ladder (top 1000), item filters, characters and account leagues accept `realm=poe2`.
- **Currency Exchange:** `GET .../currency-exchange[/<realm>][/<id>]`, where `realm` is `xbox`, `sony` or `poe2`, and `id` is a unix hour from `next_change_id`. It gives hourly digests; the current hour is not available.
  - Test result: `https://web.poecdn.com/api/currency-exchange/poe2/<hour>` returned 200 with no auth (1.56 MB for one hour; 1,887 markets across all leagues, 1,142 in Forbidden Rites). Without an id it returns the first hour, which is empty: `{"next_change_id":1733515200,"markets":[]}`.
  - `https://www.pathofexile.com/api/currency-exchange/poe2` returned **401 Unauthorized**: the www host requires the OAuth token.

```json
{"league":"Forbidden Rites",
 "market_id":"Metadata/Items/SoulCores/ThesisOfExperiments|Metadata/Items/Currency/CurrencyModValues",
 "market_pair":["Metadata/Items/SoulCores/ThesisOfExperiments","Metadata/Items/Currency/CurrencyModValues"],
 "volume_traded":{"...ThesisOfExperiments":1,"...CurrencyModValues":9},
 "lowest_stock":{...},"highest_stock":{...},"lowest_ratio":{...},"highest_ratio":{...}}
```

The market ids are metadata paths (`CurrencyModValues` is the Divine Orb), so they join directly with repoe-fork `base_items` keys. In one hour of Forbidden Rites, 545 distinct items were traded, including 37 omens and 43 essences.

---

## 5. poe.ninja (PoE2)

- **URL:** https://poe.ninja/poe2/economy. The HTML page returns **403** to a plain request (bot protection; not worked around).
- **API:** undocumented, public JSON, 200 to a plain request.
  - **League list:** `GET https://poe.ninja/poe2/api/data/index-state` returns `economyLeagues: [{name:"Forbidden Rites", url:"forbiddenrites", ...}, {name:"Runes of Aldur", ...}]`.
  - **Overview:** `GET https://poe.ninja/poe2/api/economy/exchange/current/overview?league=Forbidden%20Rites&type=<T>`. Types that returned data: `Currency`, `Fragments`, `Essences`, `Ritual` (all omens: Sinistral/Dextral Erasure, Exaltation, Annulment, Crystallisation, Whittling, ...), `Abyss`, `SoulCores`, `Runes`, `Delirium`, `Breach`, `Expedition`, `UncutGems`. `type=Omens` returns empty.
  - **Details:** `GET .../exchange/current/details?league=...&type=Currency&id=divine-orb` returns 200.
  - The old PoE1-style `.../temp/overview` endpoint returns 404.
- **Source of numbers:** the official Currency Exchange digests (the overview names `maxVolumeCurrency` and rate).
- **Licence:** none published. Use politely with caching. The PoE1 port already uses poe.ninja.

```json
{"core":{"items":[{"id":"divine","name":"Divine Orb",...}],"rates":{"exalted":452.6,"chaos":16.06},"primary":"divine","secondary":"chaos"},
 "lines":[{"id":"exalted","primaryValue":0.002209,"volumePrimaryValue":188.0,"maxVolumeCurrency":"divine","maxVolumeRate":452.6,
           "sparkline":{"totalChange":2.33,"data":[...]}}],
 "items":[{"id":"alch","name":"Orb of Alchemy","category":"Currency","detailsId":"orb-of-alchemy"}]}
```

`primaryValue` is in divines; for example, 1 divine = 452.6 exalted = 16.06 chaos on 2026-11-24. Items are keyed by poe.ninja ids and names, not metadata paths: join by name, or through `trade2/data/static` ids, which match (`divine`, `exalted`, `alch`).

---

## 6. poe2scout

- **URL:** https://poe2scout.com (site); API at https://api.poe2scout.com (Swagger at `/swagger/index.html`); source https://github.com/poe2scout/poe2scout (**MIT**, .NET API, last push 2026-10-23).
- **Access:** 200 behind a Cloudflare cache. `poe2scout.com/api/...` paths only return the SPA HTML; the API lives on the `api.` host.
- **Routes** (from `net/Poe2scout.Api/Handlers/*`):
  - `GET /Realms` lists `poe1/pc`, `poe1/xbox`, `poe1/sony`, `poe2/poe2`.
  - `GET /{realm}/Leagues`, for example `/poe2/Leagues`, returns `[{"Value":"Forbidden Rites","IsCurrent":true,"DivinePrice":488.39,"ChaosDivinePrice":15.33,"BaseCurrencyApiId":"exalted","BaseCurrencyBaseItemTypeId":"Metadata/Items/Currency/CurrencyAddModToRare",...}]`.
  - `GET /{realm}/Leagues/{league}/Currencies/ByCategory?category=currency&perPage=N`
  - `GET /{realm}/Leagues/{league}/Items/Categories`
  - `GET /{realm}/Leagues/{league}/ExchangeSnapshot`, plus snapshot history and pairs, currency pair history, item price history, and uniques by category.

```json
{"CurrentPage":1,"Pages":13,"Total":38,"Items":[{"ApiId":"mirror","BaseItemTypeId":"Metadata/Items/Currency/CurrencyDuplicate",
 "Text":"Mirror of Kalandra","CategoryApiId":"currency",
 "PriceLogs":[{"Price":2851990.5,"Time":"2026-11-24T00:00:00Z","Quantity":103}, ...]}]}
```

Prices are in the league's base currency (exalted), with daily logs. It carries `BaseItemTypeId` (metadata path), which joins directly with repoe-fork.

---

## 7. Community spawn-weight estimates

- **Krakenbul / Prohibited Library Discord.** Weights are measured by recombinator experiments, and they are the only real measurement. They are published through poe2db (CC BY-NC-SA 3.0) and Craft of Exile (no licence). The values sit on a breakpoint scale (1000, 900, 800, 750, 500, 400, 300, 250, 200, 125, 100, 50) rather than raw counts, so they are normalised estimates, not GGG's numbers. No sample sizes are published on either site.
- **Trade-listing parses.** Used for charms, jewels, tablets, waystones and desecrated mods. They carry a listing bias that CoE admits.
- **Unmeasured mods.** About 1,961 mods in poe2db (Augur count, 0.5.5.5) and 4,041 classmod entries in CoE beta carry the stand-in `1` or `0`.
- **PoE2 wiki.** The poe2wiki.net pages `Modifier`, `Mod`, `Affix` and `Crafting` contain no statement on weights (searched for "weight": no hits). The only explicit statements found are poe2db's and CoE's, quoted above.
- **Reddit and large-sample work.** Not found through web search (reddit is 403 from here). Only a Dec 2024 r/PathOfExile2 thread saying weights were unknown turned up; it is out of date.

---

## 8. Path of Building PoE2

- **URL:** https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2 (branch `dev`; MIT code licence, game data "(c) Grinding Gear Games").
- **Freshness:** latest release v0.23.1 (2026-07-28). `src/Data/ModItem.lua` was last changed 2026-09-10, "Export 0.5.5 data and update trade data". The repo was pushed 2026-11-24.
- **Useful files:**
  - `src/Data/ModItem.lua` (2,550 mods)
  - **`src/Data/Essence.lua`**
  - `ModCorrupted.lua`, `ModRunes.lua`, `ModItemExclusive.lua`, `ModJewel.lua`, `ModCharm.lua`
  - `TradeSiteStats.lua`, `CurrencyNames.lua`, `QueryMods.lua`
- **Weights:** `weightVal` holds only 0/1 values (checked: no other value in the file). This is the same source as RePoE, so it adds no weights.

```lua
["IncreasedLife1"] = { type = "Prefix", affix = "Hale", "+(10-19) to maximum Life", level = 1, group = "IncreasedLife",
  weightKey = { "body_armour", ..., "default" }, weightVal = { 1, 1, 1, 1, 1, 1, 1, 1, 0 }, modTags = { "resource", "life" },
  tradeHashes = { [3299347043] = { "+(10-19) to maximum Life" } } },
-- Essence.lua
["Metadata/Items/Currency/CurrencyLesserEssenceLife"] = { name = "Lesser Essence of the Body", type = "Life", tierLevel = 12,
  mods = { ["Helmet"] = "IncreasedLife3", ["Body Armour"] = "IncreasedLife3", ["Ring"] = "IncreasedLife2", ... } },
```

`Essence.lua` is the essence-to-mod-per-class table that repoe-fork lacks. `tradeHashes` link mod ids to `trade2/data/stats` ids.

---

## 9. dat-schema and pathofexile-dat (our own export)

- **dat-schema:** https://github.com/poe-tool-dev/dat-schema (**MIT**, last commit 2026-11-18). The latest build is at `https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json` (200; `version: 7`, `createdAt` 2026-11-18).
  - Each table carries `validFor` (1 PoE1, 2 PoE2, 3 both); 593 tables are PoE2-specific or have a PoE2 variant.
  - The PoE2 `Mods` table has columns `SpawnWeight_Tags`, `SpawnWeight_Values` (i32[]), `GenerationWeight_Tags/Values`, `ImplicitTags` and `SpawnLevel_Override`. The values in them are the 0/1 that RePoE shows.
  - PoE2 crafting tables include `Essences`, `EssenceType`, `CurrencyItems`, `CurrencyExchange`, `RecombinableClasses`, `CraftableModTypes`, `CraftingBenchOptions`, `AbyssBenchTicketTypes` and `Omens` (validFor 3).
- **pathofexile-dat:** https://www.npmjs.com/package/pathofexile-dat (repo SnosMe/poe-dat-viewer, **MIT**, 16.0.1 of 2026-10-19). It reads the GGPK / patch CDN bundles and exports tables to JSON with dat-schema. This is the route to export `Essences`, `Omens` and `CurrencyItems` ourselves if repoe-fork never adds them. repoe-fork's own exporter (`repoe-fork/repoe`, Python) is the other route.

---

## Gaps (no source gives these)

1. **GGG's true spawn weights.** They are not in the client. The only weights are community estimates (Krakenbul via poe2db/CoE), many mods are unmeasured (stand-in 1), and whole classes had none as of 0.5.5.5.
2. **Desecrated, abyss and omen outcome weights** (Well of Souls choices, omen-modified pools). These are estimates from trade queries at best.
3. **Machine-readable omen and currency rules.** Every source has only description text or each tool's own code (CoE `methods.omens`). The Greater/Perfect minimum-tier rules and Whittling or Erasure targeting must be encoded by us.
4. **Essence to mod mapping in repoe-fork.** Available only from PoB `Essence.lua`, the CoE beta data, poe2db pages, or our own `Essences.datc64` export.
5. **A documented, licensed price API.** poe.ninja and poe2scout are undocumented or unlicensed (poe2scout's code is MIT; its data has no stated terms). The official digest is hourly and has no "current" hour.
6. **Mod tiers and magnitudes on trade2 fetch results**: not seen in the sample.

## Conflicts

1. **Unmeasured weights:** what one mod is "worth" differs by source. poe2db marks an unmeasured mod `1`/`0`; CoE stable has 10,705 tier rows at `1`; CoE beta has 4,041 classmods at `1`. A planner that reads `1` as a real weight will badly under-weight those mods.
2. **CoE stable against beta:** stable `poec_data.json` is 0.5.0 data (2026-06-16) priced for Runes of Aldur; beta is 0.5.5.5 (2026-11-23). repoe-fork is 0.5.5.10. Pin to repoe-fork and use the CoE beta only for cross-checks.
3. **Divine price on one day** (2026-11-24): poe.ninja gives 452.6 exalted; poe2scout gives 488.4 exalted. Their methods and windows differ.
4. **The Currency Exchange docs** describe the endpoint without a required scope. In practice `web.poecdn.com` serves it anonymously, while `www.pathofexile.com/api/...` answers 401.
5. **Classes without weights:** Augur's list (2026-11-05) includes "str/dex/int body armour", yet `Body_Armours_str` shows measured weights on 2026-11-24. Either poe2db has added them since, or the list means the hybrid `str_dex_int` page.
6. **Omen category:** the trade2 `static` and poe.ninja put omens under `Ritual`. poe.ninja's `type=Omens` is empty, and there is no separate omen category on either.

## Sources

- https://repoe-fork.github.io/poe2/ , https://github.com/repoe-fork/poe2
- https://poe2db.tw/us/Body_Armours_str , https://poe2db.tw/us/weightings
- https://www.craftofexile.com/?game=poe2 , https://beta.craftofexile.com/?game=poe2 , https://www.craftofexile.com/weightings?game=poe2
- https://www.pathofexile.com/developer/docs , https://www.pathofexile.com/developer/docs/reference
- https://www.pathofexile.com/api/trade2/data/stats (and `/items`, `/static`, `/leagues`)
- https://poe.ninja/poe2/api/data/index-state , https://api.poe2scout.com/poe2/Leagues , https://github.com/poe2scout/poe2scout
- https://github.com/ShigenoTV/Augur/pull/40
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
- https://github.com/poe-tool-dev/dat-schema , https://www.npmjs.com/package/pathofexile-dat
