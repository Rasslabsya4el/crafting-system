# Sources (one row per source; nothing enters code or a fact sheet without a row here)

| id | URL or path | date read | used for | cached copy |
|---|---|---|---|---|
| S1 | Path of Building Community v2.67.2 (PoE 3.29), `src/Data/` (MIT licence; github.com/PathOfBuildingCommunity/PathOfBuilding) | 2026-09-20 | mod pools, weights, bases, essences, bench, veiled, eldritch | `sources/pob/Data/` (a copy of the parent project's pinned PoB data; not committed) |
| S2 | https://www.craftofexile.com/json/data/poec_common.json | 2026-09-20 | Network smoke test; `poecc.leagues`, `poecc.clngs`, `poecc.benchcosts`. JavaScript assignment, not standalone JSON. | `sources/raw/coe/poec_common.json`; 124215 bytes; SHA-256 `c188d17ab6f017123f49dcf2b89459fc98f8e9eac43f67f53b8bc65650cd5478` |
| S3 | https://www.craftofexile.com/packages/package.js | 2026-09-20 | Method inventory; action dispatch, rerolls, weighted draws, metamods; contains both PoE 1 and PoE 2 branches | `sources/raw/coe/package.js`; 1525266 bytes; SHA-256 `faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639` |
| S4 | https://www.craftofexile.com/json/data/main/poec_data.json | 2026-09-20 | Cached for method lookup and later independent PoB cross-check; not imported into our engine | `sources/raw/coe/poec_data.json`; 8651001 bytes; SHA-256 `2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a` |
| S5 | https://www.craftofexile.com/json/data/affinities/poec_affinities.json | 2026-09-20 | Cached for later review; no mechanics accepted from it yet | `sources/raw/coe/poec_affinities.json`; 5663642 bytes; SHA-256 `6264859bb58d2df6b7f8acf64a99ccfc68e5c2f027e5d97c61bdd81b06954f93` |
| S6 | https://www.craftofexile.com/json/data/exdata/poec_exdata.json | 2026-09-20 | Cached for later supplemental-data review | `sources/raw/coe/poec_exdata.json`; 1124447 bytes; SHA-256 `8c12f48182e2e10a48628c09062f6b865b9dc0edee84497dfb2ad441173204a9` |
| S7 | https://www.craftofexile.com/json/data/poec_guides.json | 2026-09-20 | Cached guide catalogue; guide evidence needs individual review | `sources/raw/coe/poec_guides.json`; 23098 bytes; SHA-256 `d4a45f7762d0e9d8a3ae45f1ee76795fdbea6b94658369efa4a6e29e884d1b68` |
| S8 | https://www.craftofexile.com/json/data/lang/poec_lang.us.json | 2026-09-20 | English names/text lookup; not a current-patch rules guarantee | `sources/raw/coe/poec_lang.us.json`; 399664 bytes; SHA-256 `b1434054209f1705182c3242310337e673f6cf6be94801ac63af8e7997b27869` |
| S9 | https://www.craftofexile.com/ | 2026-09-20 | PoE 1 page context and navigation/source discovery | `sources/raw/coe/index.html`; 28733 bytes; SHA-256 `35dfae13170e0de6ea50cc67c76ae34e6ae830e83e79b5f7de150d7a1ebbca98` |
| S10 | `sources/pob/Data/ModExplicit.lua`, key `Strength1`, line 5 | 2026-09-20 | Datamined input for worker smoke test; no eligibility interpretation | Local S1 snapshot; SHA-256 `6d400101f60ec48f854daad9a5ca2479b43e9e405f92724e80631b276eaf4568` |
| S11 | `sources/pob/Data/ModMaster.lua`, lines 732-736, `ItemGeneration*` groups | 2026-09-20 | Datamined metamod affix sides, names, level fields and supported class list | Local S1 snapshot; SHA-256 `ddf3fb7499539db0596678d9527c433cc043fa68555f2ea47687b6ffd94cd301` |

Download policy: one GET per URL, no automatic retries; use the local copy thereafter.
Cached third-party bytes are ignored by Git. Their presence does not establish that every field has been reviewed.
