# PoE2 crafting research: progress log

Branch `claude/research-poe2-crafting-c00c9f`. Newest entry first. No PoE1 code, data, test or doc is changed on this branch.

## 2026-11-24

- Inventory of the PoE1 formats written (`docs/poe2/research/poe1-formats.md`); paths chosen so no PoE1 test reads them.
- Current PoE2 version found: game data 0.5.5.10 (repoe-fork/poe2 export of 2026-11-19); the official trade site lists the leagues "Runes of Aldur" and "Forbidden Rites" (2026-11-24).
- PoE2 data pinned: 12 repoe-fork/poe2 files and 42 repoe-fork/dat-export tables, by commit, sha256 and size (`research/poe2/data/PIN.json`, fetched by `fetch_poe2.py`).
- Finding: every positive spawn weight in the PoE2 client data is 1 (7,933 of 7,933): the real weights are hidden.
- Readable extracts generated (`research/poe2/data/derived/`): datamined text of all 771 trade-listed crafting items, minimum modifier levels of the 10 Greater/Perfect orbs, 178 essence rows, 12 abyss bones, 313 socketables, 23 temple benches, 30 recombinable classes, 718 Verisium crafts, 687 exchange items, a modifier census per class.
- Web research running in six parts: patch history, currency and omens, essences/socketables/corruption/abyss, data sources, items and modifiers, Reddit evidence.

### Sources that refused this server

- poe.ninja (`https://poe.ninja/poe2/economy`): 403.
- pathofexile.com forum (`/forum/view-forum/2212`): 403. The trade API (`/api/trade2/data/*`) answers.
- reddit.com: refuses; read through the Arctic Shift archive instead. The `gpt-research` MCP server is not connected in this session.
