# Rebuild 4 inventory: the facts written by hand in more than one place

Date: 2026-11-06. Read-only inventory of `main` at `4982989` (`main` is now `9948e14`; since then only ten test files changed, the goal oracle and the packed and solver light tests, and one citation moved: `tests/test_goal_oracle_comparison.py:77` is now `:80`), written as the fact base for audit rebuild step 4, "One description per fact" (`docs/research/2026-11-02-codebase-audit.md`, class 2 and "Rebuild proposal, per root", item 4). It makes no decision and changes no code. Rules cited as `OR-n` are those of `docs/owner-rules.md`. The ones that frame it: OR-3 (the target, the buy spec and the price agree, the test of every table in section 1), OR-6 (a start item is given or bought), OR-7 and OR-8 (the trade price and its marked fallback, section 2), OR-9 (the system refreshes prices itself, section 5 point 14), OR-16 (the Alchemy of R08 and R09), OR-26 (roots, not patches) and OR-29 (section 5 is the list of points to file).

## What was read

- The audit, class 2 and proposal 4; `docs/owner-rules.md` in full (the rules that bear on this: OR-1 to OR-4 targets, OR-6 start items, OR-7 to OR-9 prices, OR-16 and OR-17 the page, OR-26 and OR-29 process).
- Issues #417, #418, #425, #426, #427, #428, #429, #406, #403, #408, #410, #453, #235, and the tickets of the buying block #351, #353, #354, #356, #359, #360 with their comments, plus #352, #355, #357, #358 (closed) for what they left in the code.
- All 14 files of `examples/targets/`, all 8 files of `examples/buy/`, the 3 committed price files in `tests/fixtures/prices/`, the recorded trade answers in `tests/fixtures/trade/recorded/`, the whole `tests/reconcile/` package (`checks.py`, `files.py`, `known.py`, `ladder.py`, `export.py`, the three test modules, `expected_checks.txt`).
- In `src/crafting_system/`: `targets/` (`model.py`, `parse.py` start-item and price keys, `floor.py`, `resolve.py`), `prices/` (every module that names or stores a price: `price_file.py`, `price_names.py`, `price_source.py`, `trade_market.py`, `trade_pricing.py`, `trade_query.py`, `trade_stats.py`, `fetch.py`, `ninja_items.py`, `fallbacks.py`, `__main__.py`), `cli/` (`_plan.py`, `_starts.py`, `_start_options.py`, `_start_types.py`, `_offers.py`, `_main.py`, `_benchmark.py`, `_report.py`, `_route_view.py`, `_route_trade.py`, `_route_card.py`), `config.py`.
- The real game data (the repoe-fork export) was not used, so nothing here re-runs `tests/reconcile/test_reconcile_real.py`. Every statement about what the data says (a tier, a pool, a shared name) is the one pinned in `tests/reconcile/known.py` or in a test named next to it.

Notation. `routes.json` is `tests/fixtures/prices/routes-allflame-2026-10-31.json`; `vendor.json` is `tests/fixtures/prices/vendor-v01-2026-11-01.json`; `T:` is a file of `examples/targets/`, `B:` a file of `examples/buy/`. A path with no prefix is from the repository root. "Slot" is a reconcile check name (`<target>::<slot>` in `tests/reconcile/expected_checks.txt`).

## Counts in one place

| List | Count |
|---|---|
| Target files / distinct routes | 14 / 13 (R10 has two files that share one start item, one spec and one price) |
| Targets with `start_price` / without (J01, R03, R06) | 11 / 3 |
| Targets with a `start_item` block / without (R04, R06, R13, R14, V01) | 9 / 5 |
| Buy specs (`examples/buy/`) / targets with no spec although they have a price (R13, V01) | 8 / 2 |
| Distinct start price keys / price entries for them (two committed files) | 10 / 19 (V01's key is only in `vendor.json`) |
| Start entries by source: `trade-api` / `poe.ninja` / `hand` | 7 / 2 / 1 |
| Reconcile checks / known disagreements pinned as strict `xfail` | 178 / 30 in 11 targets (R10 twice and R11 have none) |
| Known disagreements by issue: #427 / #417 / #418 / #428 / #426 / #425 / #403 | 8 / 6 / 5 / 4 / 3 / 2 / 2 |
| Facts inventoried / with no reconcile slot at all / with a slot on the spec side only | 11 / 3 (quality, sockets, trade query) / 3 (influence, rarity, start mods, each against the price entry) |
| Derivations of one fact from another that already exist in code | 17 (section 3) |
| Places where a price source is chosen or recorded | 22 (section 2.1) |
| Places where a price source is lost on its way to the answer | 9 (section 2.3) |
| Places that no open issue listed (all filed: #470 to #473, #478) | 14 (section 5) |
| Buying-block tickets read | 6 |
| Options for the single source | 5, A to E (section 6) |

---

## 1. Facts written by hand in more than one place

### 1.0 Where a fact can be written

| Kind of place | Files | What it can say |
|---|---|---|
| Target | 14 in `examples/targets/` | `base`, `item_level`, `influence`, `start_item` (`rarity`, `mods` with `mod`, `tier`, `values`, `fractured`), `quality`, `sockets` (goals), `start_price`, `price_file`, `tiers_top_at_item_level`, `item_level_floor` |
| Buy spec | 8 in `examples/buy/`, 1 copy for tests in `tests/fixtures/trade/r12_buy_spec.yaml`, 4 more in `docs/research/2026-11-01-strand-routes-files/buy/` | `name`, `base_type`, `category`, `rarity`, `item_level_min` and `_max`, `influence`, `corrupted`, `mods` (`stat`, `minimum`, `fractured`) |
| Price entry | 2 committed files with start keys, `routes.json` (108 entries) and `vendor.json` (113 entries, 108 of them equal copies); a third, `tests/fixtures/prices/foresight-allflame-2026-11-02.json`, holds 8 `poe.ninja` entries (Hinekora's Lock, the burn currencies, Chaos and Divine) and no start key, and only `tests/test_prices_foresight.py` reads it | key, `chaos`, `source`, `note`, `detail` (`league`, `date`, `listings`, `used`, `usable`, `k`, `query`, `query_hash`) |
| Recorded search | `tests/fixtures/trade/recorded/start_items/search_body_{r05,r10,r11,r12}.json` | the body that was sent for four of the start items |
| Test constant | 19 test files name a start price key, 7 a buy spec, 28 a target file, 17 a price fixture (45 files in all, `tests/reconcile/` not counted) | the same names and numbers again |
| Guide route | 11 files in `examples/routes/`; 5 of them carry a `do: restart` rule (`r04-penetrating-quiver.yaml:133`, `r04-penetrating-quiver-restart.yaml:143,146`, `r13-life-resist-belt.yaml:61`, `r14-hunter-bow.yaml:49`, `r14-hunter-bow-restart.yaml:59,137`), which buys the start item again at the start price (read at `cli/_route.py:253,460`) | the start item in header prose: `r04-penetrating-quiver.yaml:10` and `r04-penetrating-quiver-restart.yaml:19` ("Buy a quiver of item level 81 or more"), `r05-strength-ring.yaml:12` ("Buy a ring with a fractured All Attributes"), `r08-energy-shield-boots.yaml:15` and `r09-life-boots.yaml:15` ("a rare pair of boots, as the target does"), `r10-fractured-boots.yaml:12`, `r11-reservation-helmet.yaml:12`, `r12-lightning-amulet.yaml:10`, `r13-life-resist-belt.yaml:17` ("a magic belt; the target starts from a normal one") |
| Page | `tests/golden/`: 8 pages carry a price key as the title of the buy step | `Buy R05 start ring` and its kin |
| Prose | target and spec headers, `README.md:34,38`, `docs/adr/0008-targets-and-start-items.md:7`, `src/crafting_system/targets/__init__.py:74-75`, `GLOSSARY.md:118`, `ExpectedStart.why` of V01 (`src/crafting_system/cli/_benchmark.py:247-253`) | what the file says in words, with numbers |

How the test counts were made (files under `tests/`, `tests/reconcile/` left out, `grep -rlE ... --include=*.py`): a start price key is any of `R05 start ring|R08 start boots|R09 start boots|R10 start boots|R11 start helmet|R12 start amulet|Penetrating Arrow Quiver \(ilvl|Leather Belt \(ilvl 86\)|Thicket Bow \(ilvl 78|Lion Pelt \(ilvl 84\)` (19 files); a buy spec is `examples/buy|BUY_SPECS|BUY /|BUY_DIR|start-(boots|ring|helmet|amulet|quiver|bow)\.yaml|"examples" / "buy"` (7 files); a target file is `(r0[3-9]|r1[0-4]|v01|j01)-[a-z0-9-]+\.yaml|examples/targets|EXAMPLES / |TARGETS / ` (28 files); a price fixture is `routes-allflame-2026-10-31|vendor-v01-2026-11-01` (17 files).

No code path joins these. The only link between a target, its spec and its price is the string equality `target.start_price == spec.name == key of the price entry`. It is checked in three places: `tests/reconcile/files.py:148-155` (`buy_spec_of`), `src/crafting_system/cli/_benchmark.py:472-481` (`_buy_spec_named`, used only to print a hint when a price is missing), and `tests/test_targets_files.py:219-242` and `tests/test_strand_routes.py:214-217` (R10, R11, R05 and the strand routes only).

### 1.1 The 14 targets, fact by fact

For each target: where each fact is written (with its value), and the reconcile slots that disagree today (from `tests/reconcile/known.py:47-79`). A fact the target does not state says "none".

**J01** `T:j01-cobalt-life-attack-speed.yaml` (3 checks, 2 known)
- base `:11` Cobalt Jewel; item level `:14` 84; influence none; quality none; sockets none.
- start item `:18-19` rarity rare, no mods (the comment `:16-17` calls it "what you hold after you scour a rare jewel"); start price none; buy spec none; trade query none; price entry none.
- Known: `start_price.written` and `buy_spec.exists` (#427): the start item counts as free.

**R03** `T:r03-avoid-shock-boots.yaml` (5 checks, 2 known)
- base `:43` Velour Boots; item level `:46` 100; `tiers_top_at_item_level` `:49`; influence `:53` `[]`; quality none; sockets none.
- start item `:87-98` rare, one mod `ChanceToSuppressSpells5__` tier 1, values `[13]`, fractured; the same mod is named again as a requirement at `:71-72`. Comment `:38-40` says "and no price: the file has no buy spec for it, so the planner treats it as free until one is added".
- Known: `start_price.written`, `buy_spec.exists` (#427).

**R04** `T:r04-penetrating-quiver.yaml` (14 checks, 3 known)
- base `:30` `Metadata/Items/Quivers/QuiverNew5` (by id, because two bases are named Penetrating Arrow Quiver); item level `:33` 81; `tiers_top_at_item_level` `:36`; influence `:38` `[]`; no `start_item` (a normal quiver).
- start price key `:77` `Penetrating Arrow Quiver (ilvl 81)`.
- Spec `B:r04-start-quiver.yaml:8-13`: `base_type` Penetrating Arrow Quiver, category `armour.quiver`, rarity normal, `item_level_min` 81. Its header `:4-7` says the committed price is not this search's.
- Entry `routes.json:244` (`vendor.json:254`): `poe.ninja`, 9.0 Chaos, a hand-typed note "item level 85, 43 observations"; no `detail`, so no query.
- Known: `price.base` (#418: the name is also `Quiver12`), `price.item_level` (#425: the line is 85, the key says 81), `price.source` (#426: a stand-in).
- Guide route: `examples/routes/r04-penetrating-quiver.yaml:10` and `r04-penetrating-quiver-restart.yaml:19` restate "Buy a quiver of item level 81 or more"; both end in `do: restart` (`:133`; `:143,146`), which buys the start item again at the price above.

**R05** `T:r05-strength-ring.yaml` (19 checks, 4 known)
- base `:35` Amethyst Ring (comment `:34` "every plain ring has the same pool of mods", which #428 refutes); item level `:38` 75; `tiers_top_at_item_level` `:43`; influence `:47` `[]`.
- start item `:75-86` rare, one mod `AllAttributes4` tier 1, values `[14]`, fractured; requirement `:51-54` names the same family with `min_tier: 1`. Key `:90` `R05 start ring`.
- Spec `B:r05-start-ring.yaml:6-16`: no `base_type`, category `accessory.ring`, rare, `item_level_min` 75, mod `+# to all Attributes` minimum 13 fractured.
- Entry `routes.json:283`: `trade-api`, 2.6 Chaos, 2026-10-31, 602 listings; stored query: category `accessory.ring`, rare, `ilvl.min` 75, `fractured_item`, stat `fractured.stat_1379411836` at least 13. Same body in `search_body_r05.json`.
- Known: `buy.base` (#417), `buy.pool` (#428, Unset Ring and Bone Ring roll other mods), `price.base` (#418), `price.pool` (#428).
- Guide route `examples/routes/r05-strength-ring.yaml:12` restates "Buy a ring with a fractured All Attributes" (no level, no base).

**R06** `T:r06-strength-heavy-belt.yaml` (3 checks, 2 known)
- base `:40` Heavy Belt; item level `:43` 75; `tiers_top_at_item_level` `:46`; influence `:50` `[hunter]`; no `start_item`.
- quality `:83-85` is a goal (intrinsic catalyst, at least 20 percent); sockets none. `make_plan` refuses a target with `quality` (`src/crafting_system/cli/_plan.py:311-315`), so R06 cannot be planned today.
- Start price, spec, entry: none. Known: `start_price.written`, `buy_spec.exists` (#427).

**R08** `T:r08-energy-shield-boots.yaml` (14 checks, 1 known)
- base `:27` Sorcerer Boots; item level `:30` 86 (comment `:31-33`: the guide's level, not the floor; no `tiers_top_at_item_level`); influence `:35` `[]`.
- start item `:45-47` rare, `mods: []`; the comment `:37-44` says the Alchemy is folded into the price. Key `:51` `R08 start boots`; `actions` `:55`.
- Spec `B:r08-start-boots.yaml:9-14`: `base_type` Sorcerer Boots, category `armour.boots`, rarity normal, `item_level_min` 86.
- Entry `routes.json:348`: `trade-api`, 29.82716 Chaos = 29.8 (the trade price of the normal base) + 0.02716 (the file's own `Orb of Alchemy` entry, `routes.json:215`, typed into the sum); date 2026-11-01; stored query: `type` Sorcerer Boots, category `armour.boots`, rarity normal, `ilvl.min` 86, no stat filter.
- Known: `buy.rarity` (#417, OR-16: target rare, spec normal; the Alchemy is hidden in the price).
- Guide route `examples/routes/r08-energy-shield-boots.yaml:15`: "a rare pair of boots, as the target does (see `start_item` in the target)".

**R09** `T:r09-life-boots.yaml` (14 checks, 4 known)
- base `:25` `Metadata/Items/Armours/Boots/BootsAtlas1` (by id; the comment `:22-24` says three bases are named Two-Toned Boots); item level `:26` 86; `tiers_top_at_item_level` `:29`; influence `:30` `[]`.
- start item `:40-42` rare, `mods: []`; key `:45` `R09 start boots`; `actions` `:48`.
- Spec `B:r09-start-boots.yaml:9-14`: `base_type` Two-Toned Boots, `armour.boots`, normal, `item_level_min` 86.
- Entry `routes.json:403`: `trade-api`, 5.02716 Chaos = 5.0 + 0.02716 (Alchemy); stored query `type` Two-Toned Boots, normal, `ilvl.min` 86.
- Known: `buy.rarity` (#417), `buy.pool` (#428: BootsAtlas2 and 3 have other pools), `price.base` (#418), `price.pool` (#428).
- Guide route `examples/routes/r09-life-boots.yaml:15`: the same sentence as R08's.

**R10** `T:r10-fractured-boots.yaml` and `T:r10-fractured-boots-70-life.yaml` (19 checks each, 0 known)
- base `:31` / `:32` Sorcerer Boots; item level `:35` / `:36` 84; `tiers_top_at_item_level` `:38` / `:39`; influence `:42` / `:43` `[]`.
- start item `:70-81` / `:74-85` rare, `MovementVelocity5` tier 2, values `[30]`, fractured; the requirement names the same mod id (`:49-50` / `:50-51`). Key `:85` / `:89` `R10 start boots`.
- Spec `B:r10-start-boots.yaml:7-18`: `base_type` Sorcerer Boots, `armour.boots`, rare, `item_level_min` 84, mod `#% increased Movement Speed` minimum 30 fractured.
- Entry `routes.json:458`: `trade-api`, 17.0 Chaos, 2026-10-31, 156 listings; stored query `type` Sorcerer Boots, rare, `ilvl.min` 84, stat `fractured.stat_2250533757` at least 30. Same body in `search_body_r10.json`.
- All places agree (R10 and R11 are the two bought start items that agree everywhere).
- Guide route `examples/routes/r10-fractured-boots.yaml:12` restates "Buy boots with a fractured Movement Speed" (no level, no minimum).

**R11** `T:r11-reservation-helmet.yaml` (19 checks, 0 known)
- base `:32` Lion Pelt; item level `:36` 84; `tiers_top_at_item_level` `:39`; influence `:43` `[]`.
- start item `:69-80` rare, `ChaosResist6` tier 1, values `[33]`, fractured; the requirement `:47-49` is the family with `min_tier: 1`. Key `:84` `R11 start helmet`.
- Spec `B:r11-start-helmet.yaml:7-18`: `base_type` Lion Pelt, `armour.helmet`, rare, `item_level_min` 84, mod `+#% to Chaos Resistance` minimum 31 fractured (header `:14` restates "31 is the lowest roll of tier 1").
- Entry `routes.json:524`: `trade-api`, 20.0 Chaos, 2026-10-31, 42 listings; stored query `type` Lion Pelt, rare, `ilvl.min` 84, stat `fractured.stat_2923486259` at least 31. Same body in `search_body_r11.json`.
- All places agree.
- Guide route `examples/routes/r11-reservation-helmet.yaml:12` restates "Buy a helmet with a fractured Chaos Resistance" (no level, no tier).

**R12** `T:r12-lightning-amulet.yaml` (19 checks, 6 known)
- base `:12` Paua Amulet; item level `:15` 84; `tiers_top_at_item_level` `:18`; influence `:22` `[]`.
- start item `:43-54` rare, `LightningResist2` written as tier 3, values `[14]`, fractured (the data says tier 7 of 8). The requirement `:39` is the family with no tier. Key `:60` `R12 start amulet`.
- Spec `B:r12-start-amulet.yaml:4-11`: no `base_type`, category `accessory.amulet`, rare, `item_level_min` 75 (header `:2-3`: the level the gem prefix needs), mod `+#% to Lightning Resistance` fractured, no minimum. A second spec of the same item is `tests/fixtures/trade/r12_buy_spec.yaml:4-11` (names the family `LightningResistance`, same level 75).
- Entry `routes.json:590`: `trade-api`, 1.0 Chaos, 2026-10-31, 909 listings; stored query category `accessory.amulet`, rare, `ilvl.min` 75, stat `fractured.stat_1671376347` with no minimum. Same body in `search_body_r12.json`.
- Known: `buy.base`, `buy.item_level` (#417); `start_mod.LightningResist2.tier`, `.buy_minimum` (#403); `price.base`, `price.item_level` (#418).
- Guide route `examples/routes/r12-lightning-amulet.yaml:10`: "Start from an amulet with Lightning Resistance fractured".

**R13** `T:r13-life-resist-belt.yaml` (8 checks, 2 known)
- base `:13` Leather Belt (one base, `Belt3`; `BeltRoyale1` is a Battle Royale copy, `tests/reconcile/test_reconcile_real.py:131-133`); item level `:16` 86; no `tiers_top_at_item_level`; no influence line; no `start_item` (`:18`).
- Key `:22` `Leather Belt (ilvl 86)`; `actions` `:29`. No spec.
- Entry `routes.json:195` (`vendor.json:200`): `poe.ninja`, 10.0 Chaos, note "item level 86, 41 observations" typed by hand; no `detail`.
- Known: `buy_spec.exists` (#427), `price.source` (#426).
- Guide route `examples/routes/r13-life-resist-belt.yaml:17`: the guide starts from a magic belt, the target from a normal one; `do: restart` at `:61`.

**R14** `T:r14-hunter-bow.yaml` (14 checks, 1 known)
- base `:26` Thicket Bow; item level `:29` 78; `tiers_top_at_item_level` `:32`; influence `:34` `[hunter]`; no `start_item`.
- Key `:69` `Thicket Bow (ilvl 78, Hunter)`; `actions` `:39-49`.
- Spec `B:r14-start-bow.yaml:5-11`: `base_type` Thicket Bow, `weapon.bow`, rarity `nonunique`, `item_level_min` 78, `influence` `[hunter]`.
- Entry `routes.json:872`: `trade-api`, 13.0 Chaos, 2026-11-01, 164 listings; stored query `type` Thicket Bow, `weapon.bow`, `nonunique`, `ilvl.min` 78, stat `pseudo.pseudo_has_hunter_influence` at least 1.
- Known: `buy.rarity` (#417: target normal, spec any non-unique). The influence appears in the target, the spec, the stored query and the key, and no slot compares the last two.
- Guide route `examples/routes/r14-hunter-bow.yaml:49` and `r14-hunter-bow-restart.yaml:59,137`: `do: restart`.

**V01** `T:v01-minion-helmet.yaml` (8 checks, 3 known)
- base `:30` Lion Pelt; item level `:34` 84; `tiers_top_at_item_level` `:37`; influence `:41` `[]`; no `start_item` (comment `:56-57`).
- Key `:59` `Lion Pelt (ilvl 84)`; `price_file` `:63` names `vendor.json`; `actions` `:44`. No spec.
- Entry `vendor.json:205`: `hand`, 2.0 Chaos, note "hand price for benchmark route V01 (ticket #331); the refresher does not fetch this line yet (ticket #360)"; no level, no `detail`. The recipe start derives the same string again from the base: `src/crafting_system/cli/_start_options.py:280`.
- Known: `buy_spec.exists` (#427), `price.item_level` (#425), `price.source` (#426).

### 1.2 The 11 facts: where written, where read, which wins, what pins it, which issue

Counts of "written" are places in the repository that state the fact by hand (a price entry is counted once, though `vendor.json` holds a copy).

#### F1. Base

- **Written (target 14, spec 8, price entry 10, recorded search 4, spec fixture 1).** Target `base:` (14, two by id: R04 `:30`, R09 `:25`). Spec `category:` (8) and `base_type:` (6; R05 and R12 have none). Price entry: query `type` (R08, R09, R10, R11, R14), query `category` (all 7 trade entries), the base name inside the key (R04, R13, R14, V01). Recorded bodies carry the category (4) and the `type` (r10, r11). Prose in every target and spec header.
- **Read.** The planner reads only the target: `targets/parse.py:295` `read_base` (name or id, `targets/resolve.py:201-224`), then `Target.base_id` in `cli/_plan.py:330,357`, `cli/_start_options.py:170,195,279,317`, `targets/floor.py:185`, `cli/_route_card.py:350`. The spec is read by `prices trade --spec` (`prices/__main__.py:196`) and by the page when `--buy-spec` is given (`cli/_main.py:98,165` into `cli/_route_view.py:695-697`). The price entry's base is read by nothing in `src`.
- **Wins.** For the item that is planned, the target. For what it costs, whatever entry sits under the key, whatever base it was taken for. On the page, the card shows the target's base (`_route_view.py:430-434`) while the "Accepts" lines and the trade link come from the spec, and `_accepts` prints neither `base_type` nor `category` (`cli/_route_trade.py:74-90`); the golden `tests/golden/real_r05.html` shows "Amethyst Ring" on the card and "Rare, item level 75 or more" under Accepts.
- **Pinned by.** Slots `target.base` (14, all agree), `buy.base`, `buy.category`, `buy.pool` (9 each), `price.base`, `price.pool` (11 each); `tests/test_targets_files.py:267,329` (the base ids and levels of R10 and R11), `tests/reconcile/test_reconcile_real.py:131-133`.
- **Known disagreements.** `buy.base` R05, R12 (#417); `buy.pool` R05, R09 (#428); `price.base` R04, R05, R09, R12 (#418); `price.pool` R05, R09 (#428): 10.
- **Issue.** #417, #418, #428. Audit INPUTS-1, INPUTS-6, ROUTES-7. Not listed anywhere: the page's "Accepts" omits the base and its step is titled by the internal price key (audit INPUTS-7; section 5, row 4).

#### F2. Item level

- **Written (target 14, spec 8, price entry 10, recorded search 4, spec fixture 1).** Target `item_level:` (14) plus the author's flags about how far it may be lowered: `tiers_top_at_item_level: true` in 11 targets (not J01, R08, R13), `item_level_floor` in none. Spec `item_level_min:` (8; `item_level_max` in none). Price entry: query `ilvl.min` (7 trade entries) and the label `(ilvl N)` in the key (R04, R13, R14, V01); R04's and R13's notes also state the level of the poe.ninja line (85 and 86) in words.
- **Read.** `parse.py:302` `read_item_level` into `Item.build` (`parse.py:1009`) and `Abstraction(..., target.item_level, ...)` (`cli/_plan.py:358`); `targets/floor.py:247-340` (`floor_of`, `level_groups`, `target_at_level`; no code outside `floor.py` and its re-export calls them, so the floor of ADR-0061 is built and not wired); `_start_options.py:218,280`; `_route_card.py:358,365`. The spec's level is read by `build_query` (`prices/trade_query.py:307-308`) and by the page's Accepts line (`_route_trade.py:76-81`). The key's label is read as text by `resolve_start_price`, not parsed; `prices/poe_watch.py:71` compares `base.item_level`, parsed from a wanted key, with a poe.watch row.
- **Wins.** The target for the plan; the price entry for the cost. The level an entry was taken for is a free label in the key, so R04's key says 81 on a poe.ninja line of 85, R12's key and spec say 75 against a planned 84, and V01's hand price records no level at all.
- **Pinned by.** Slots `buy.item_level` (9), `price.item_level` (11, reading the level from the query, else the note, else the key label: `tests/reconcile/files.py:204-224`); `tests/test_targets_floor_real.py:49-84,100,154-180` (floors of R13 and R08 at 84, R05 pinned at 75, the 11 pinned targets); `tests/test_cli_r04_r14_real.py:46`.
- **Known disagreements.** `buy.item_level` R12 (#417); `price.item_level` R12 (#418), R04 and V01 (#425): 4.
- **Issue.** #417, #418, #425; #403 for the 11-of-14 opt-in key; ADR-0061 and #351, #359 for lowering the level. #352's checker comment on #359: `target_at_level` does not touch `start_price`.

#### F3. Influence

- **Written (target 12 lines, 2 non-empty; spec 1; price entry 1).** Target `influence:` (12 of 14 files; J01 and R13 omit it; R06 and R14 say `[hunter]`). Spec `influence: [hunter]` (R14 only). R14's entry carries it twice: the key suffix `, Hunter` and the stored query stat `pseudo.pseudo_has_hunter_influence` at least 1.
- **Read.** `parse.py:312` into `Item.build`; `_start_options.py:171,280` (item and price key); `trade_query.py:302` (`build_query` adds the pseudo stats); `_route_trade.py:82-85` (Accepts); `trade_pricing.py:232-250` drops a listing whose influences differ from the spec's.
- **Wins.** The target for the plan; the spec for the query; nothing compares the entry's influence with the target's.
- **Pinned by.** Slot `buy.influence` (9, none known). There is no `price.influence` slot.
- **Issue.** None.

#### F4. Quality

- **Written (target 1).** Only as a goal of R06 (`T:r06...:83-85`). No start item states quality; the spec has no field for it; the trade query says "not covered" (`prices/trade_query.py:31-33`).
- **Read.** `parse.py:632` `read_quality`, then refused by `make_plan` (`cli/_plan.py:311-315`).
- **Pinned by.** No slot, no test of a spec or entry. **Issue.** None on the buying side (#235 covers sockets and links only).

#### F5. Sockets

- **Written (none).** No target states `sockets` as a goal or on its start item. The spec has no field; the query says "not covered" (`prices/trade_query.py:34`). `make_plan` refuses a target with sockets (`cli/_plan.py:316-320`).
- **Pinned by.** No slot. **Issue.** #235 (open): socket and link filters in buy specs.

#### F6. Start mods (and whether fractured)

- **Written (target 6, spec 4, price entry 4, recorded search 4, repeats in requirements 5).** Target `start_item.mods` in R03, R05, R10 (two files), R11, R12: `mod`, `tier`, `values`, `fractured`. Spec `mods` in R05, R10, R11, R12: `stat` (English text), `minimum`, `fractured`. Entry: the stat filter with its minimum, in the stored query. The requirements repeat the same mod: R03 `:71-72` (`mod:`), R10 (two files, `mod: MovementVelocity5`), R05, R11 (`min_tier: 1` on the family), R12 (family). Spec headers restate the tier in words (R11 `:14`).
- **Read.** `parse.py:1062-1088` `read_start_mod` stores `tier` and `values` as written (`Item` only checks tier at least 1, `items/model.py:213-214`). The written tier and values reach the search through `abstraction/_kernel.py:809-812` (`_contribution`, `status_of(..., entry.tier, entry.values, ...)`) and `targets/model.py:55` (`mod.tier > self.min_tier`). The page reads the tier from the data instead (`cli/_route_card.py:303`, `tier_table`). `targets/floor.py:251-254` reads the mods' required levels. The spec's mods go through `trade_stats.py:159` `resolve_buy_mod` into stat ids.
- **Wins.** The plan uses the written tier and values; the page prints the data's tier; the price uses the spec's minimum (R12's has none, so the price is the cheapest fractured Lightning Resistance of any tier while the plan holds a tier-3 roll of 14).
- **Pinned by.** Slots `start_mod.<mod>.tier`, `.values` (6 each), `.buy_mod`, `.buy_minimum` (5 each), `buy_mod.<stat>.in_target` (5): 27 checks. `tests/test_targets_files.py:35` pins the wrong R12 tier 3; `:268,285` (R10 tier equals the data's 2), `:330,346` (R11), `:373` (R05); `tests/test_goal_oracle_comparison.py:80`; `tests/test_prices_start_items.py:73-82` (R11 searched at the tier-1 minimum 31).
- **Known disagreements.** `start_mod.LightningResist2.tier` 3 against 7 and `.buy_minimum` (#403): 2.
- **Issue.** #403. Audit TARGETS-5, INPUTS-9, PLANNING-11, ROUTES-10.

#### F7. Start rarity

- **Written (target 9 blocks and 5 defaults, spec 8, price entry 7, recorded search 4).** Target `start_item.rarity` (J01, R03, R05, R08, R09, R10 x2, R11, R12; a block with mods and no rarity means rare, `parse.py:1045-1047`; no block means a fresh normal item, `parse.py:954`). Spec `rarity:` (normal in R04, R08, R09; rare in R05, R10, R11, R12; `nonunique` in R14). Entry: the query's rarity filter. R08 and R09 also type the Alchemy into the price (0.02716) and into the note.
- **Read.** `parse.py:1045` `read_rarity` into `Item.build`; `trade_query.py:306` into the query; the page's Accepts first line is `spec.rarity` (`_route_trade.py:75`) and the start card shows "any mod or empty" for any rare start (`_route_view.py:430-434`), so R08's page can say "Normal" in Accepts and draw a rare card.
- **Wins.** The target for the plan, the spec for the price and for Accepts.
- **Pinned by.** Slot `buy.rarity` (9). No slot for the entry's rarity.
- **Known disagreements.** `buy.rarity` R08, R09 (#417, OR-16), R14 (#417, OR-3): 3.
- **Issue.** #417, #408 (OR-16 for R08 and R09 on the page). Audit PLANNING-9, TARGETS-9, INPUTS-5.

#### F8. The buy spec

- **Written (8 files for 7 routes; 5 more copies elsewhere).** `examples/buy/` (R10's is shared by two targets). Copies of the same idea: `tests/fixtures/trade/r12_buy_spec.yaml`, four specs in `docs/research/2026-11-01-strand-routes-files/buy/`. R13 and V01 have a price and no spec; J01, R03, R06 have neither.
- **Read.** Not by the planner. `prices trade --spec` (`prices/__main__.py:90,196`) prices it; the route page builds its Accepts lines and trade link from a spec the person passes with `--buy-spec` (`cli/_main.py:98,165-169`), a path with no tie to the target's `start_price`; `cli/_benchmark.py:472-481` prints its path in a missing-price hint. The command that reads a spec is a hand-run one, and `cli/_plan.py:248-251` and `cli/_benchmark.py:492` tell the user to run it, which OR-9 says the system does itself (#478).
- **Wins.** Nothing is compared at run time; the name decides which price the planner looks up.
- **Pinned by.** Slot `buy_spec.exists` (14); `tests/test_targets_files.py:16-22,219-242,277-285,340-346`, `tests/test_prices_trade_market.py:41-46,80-100`, `tests/test_prices_start_items.py`, `tests/test_cli_routes_real.py:50,155`, `tests/test_strand_routes.py:214-217`, `tests/test_cli_benchmark.py:133-157` (pins `buy_spec` is `None` for the belt).
- **Known disagreements.** `buy_spec.exists` J01, R03, R06, R13, V01 (#427): 5; the 6 #417 rows and 4 #428 rows above.
- **Issue.** #417, #427, #428.

#### F9. The trade query

- **Written (never by hand; stored 7 times, copied 5 times).** It is built from the spec by `build_query` (`prices/trade_query.py:291-315`) with stat ids from the site's stat list (`trade_stats.py:159`). It exists as: the body stored inside each trade-api entry (`detail.query` and `detail.query_hash`, 7 entries, 14 with the copy file); the recorded `search_body_*.json` (R05, R10, R11, R12; plus `search_body_r12_1week.json`); and a third time at page time, rebuilt from the spec and the cached stat list (`cli/_route_trade.py:36-51`, called at `_route_view.py:695-697`). The constants of OR-7 are `DEFAULT_STATUS = "securable"` and `DEFAULT_INDEXED = None` (`trade_query.py:63-64`); the sentence of ADR-0007 about a one-week window is marked replaced in main (`docs/adr/0007-prices-from-a-dated-local-file.md:7` and its last amendment).
- **Wins.** The price is the stored body; the link on the page is the rebuilt one. A spec edited after pricing, or a stat the list cannot resolve (left out of the link and named in `BuyStep.unresolved`, `_route_trade.py:42-48`), makes them differ with no warning.
- **Pinned by.** `tests/test_prices_start_items.py:35-82` (stored body equals the recorded body for four starts; status `securable`; no `trade_filters`); `tests/test_prices_trade_market.py:80-100` (replays the recorded listings against the spec, taking the body from the recording, not from `build_query`); `tests/test_cli_routes_real.py:150-158` (the link of R05, R10, R11 is golden). No test builds the query of a real `examples/buy` spec and compares it with a stored body.
- **Issue.** None (section 5, row 2).

#### F10. The price key

- **Written (target 11, spec 8, price entries 10 keys, tests 19 files, goldens 8, prose 4+).** Target `start_price:` (11). Spec `name:` (8; canonicalised by `BuySpec.__post_init__`, `trade_query.py:268`). Entry keys: 10 distinct, in two schemes. Six are route-tagged names that no base row can have (`R05 start ring`, `R08 start boots`, `R09 start boots`, `R10 start boots`, `R11 start helmet`, `R12 start amulet`); four are base-price names of the form `<base name> (ilvl N[, Influence])` (R04, R13, R14, V01), which is also what `base_price_name` writes (`prices/price_names.py:81-85`) and what the poe.ninja fetch stores (`prices/ninja_items.py:66`).
- **Read.** `cli/_plan.py:245-252` `resolve_start_price`; `cli/_benchmark.py:460`; `_goods` of the recipe source (`cli/_start_options.py:280-294`); the report and page (`_report.py:308`, `_route_view.py:399-400,473` use it as a title: "Buy R05 start ring", "Restart: buy R12 start amulet again"); `prices/__main__.py:200-202` (`trade` refuses a name held by another source).
- **Wins.** A caller that hands `make_plan` a ready `StartPrice` as `start_price_of` (`cli/_plan.py:266,310`) skips the key lookup altogether: `plan_with_starts` does it for every non-plain start candidate (`cli/_starts.py:88-90`), so neither the key nor `--start-price` applies to them. Otherwise the target's string chooses the entry; `--start-price` beats the file (`_plan.py:239-242`) and `price_overrides.toml` beats the entry (`prices/price_file.py:325-339`). A key that matches no entry is the one mismatch the code reports: `PlanError "no price for the start item"` (`_plan.py:247-251`).
- **Pinned by.** Slots `start_price.written` (14), `price.entry` (11); the name link tests above; `tests/test_cli_r04_r14_real.py:46`, `tests/test_cli_r08_r09_real.py:35`, `tests/test_cli_r13_real.py:37`, `tests/test_vendor_benchmark_real.py:55,85`; goldens `real_r05`, `real_r10`, `real_r11`, `restart`, `gap`, `given_route_differs`, `r12_fixture`, `r12_fixture_given_route`.
- **Known disagreements.** `start_price.written` J01, R03, R06 (#427); `price.base` (the key is a name, the target a base id) R04, R05, R09, R12 (#418).
- **Issue.** #418, #427, #429.

#### F11. The price entry and its source

- **Written (10 start entries; 7 `trade-api`, 2 `poe.ninja`, 1 `hand`).** In two committed files (section 2.4) and, outside the repository, in `<data dir>/prices.json` (the fetcher) and `<data dir>/price_overrides.toml` (by hand). `--start-price` is a third, per run.
- **Read.** `resolve_start_price` copies only `chaos` and `source` (`_plan.py:252`); `make_plan` turns it into the `restart` offer when above 0 (`_plan.py:340-344`); the report prints the source (`_report.py:309,525`); the page prints the money and the title only. The resolved `Plan.start_price` is read again by: `cli/_route.py:253` (a given route's `restart` is refused when it is 0) and `:460` (the `restart` action is built from it); `cli/_interval.py:345` (the shift added to every total); `cli/_verify.py:139-156` (the simulation's `start_cost` and the computed total); `cli/_report.py:293,505`, `cli/_route_report.py:31,71`, `cli/_route_sim.py:72`, `cli/_benchmark.py:387,445,640`; for a candidate, `cli/_start_report.py:36` prints its `price_name`.
- **Wins.** `start_price_of` (a ready `StartPrice`; non-plain candidates, `cli/_starts.py:89`; printed by `cli/_start_report.py:36`), then `--start-price`, then the override file, then the entry of the file that was loaded.
- **Pinned by.** Slots `price.entry`, `price.base`, `price.item_level`, `price.source`, `price.pool` (11 targets, 55 checks, 12 known); `tests/test_prices_start_items.py` (4 entries against their recordings); `tests/test_prices_trade_market.py:80-100`; the price tests listed under F10.
- **Known disagreements.** `price.source` R04, R13, V01 (#426); the `price.*` rows of F1 and F2: 12 in all.
- **Issue.** #426, #425, #418, #428, #429, #406; #356 and #357 comments for the refresher.

---

## 2. Price sources

### 2.1 Where a source is chosen or recorded (22 places)

| # | Place | What it records or chooses |
|---|---|---|
| 1 | `prices/poe_ninja.py:18-19` | `poe.ninja`, `poe.ninja-history` |
| 2 | `prices/fetch.py:90,111,121,123` | stamps every current overview line `poe.ninja`; a stash line keeps only `{"category": kind}`, the observation count is dropped (`:106-111`) |
| 3 | `prices/ninja_history.py` via `prices/fallbacks.py:53` | `poe.ninja-history` with `{league, date}` in `detail` |
| 4 | `prices/poe_watch.py:32-33` | `poe.watch`, `poe.watch-history` |
| 5 | `prices/previous_league.py:33-34` | `poe.ninja-previous-league`, `poe.ninja-standard`: the Chaos number copied from another economy, unscaled (audit INPUTS-10) |
| 6 | `prices/default_prices.py:12` | `default` for Thaumaturgic Dust and Gold |
| 7 | `prices/trade_market.py:25` and `prices/trade_pricing.py:399` | `trade-api`, with the full `detail` (league, date, listings, used, usable, k, query, query_hash) |
| 8 | `prices/price_file.py:26,337` | `override`: the hand price of `price_overrides.toml` replaces the entry and drops its source, note and detail |
| 9 | the committed JSON, 5 entries in `vendor.json` | `hand`: a source string no code knows (`grep "hand"` finds no constant in `src/crafting_system/prices/`) |
| 10 | `cli/_offers.py:116,121` | the labels `fixed` (Chaos Orb) and `rate` (Divine Orb) in an offer's parts |
| 11 | `cli/_plan.py:242` | `given on the command line` (`--start-price`) |
| 12 | `cli/_plan.py:244` | the sentence "the target names no start price, so the start item counts as free" used as a source |
| 13 | `cli/_start_options.py:294,352` | per good, the entry's source; per recipe start, the string `vendor recipe: 1 <name> + ...` |
| 14 | `prices/price_source.py:41-44,101-105,154-210` | `trade`, `poe.ninja`, `override`, `none` and a `fallback` flag with marks (`SourcedPrice`) |
| 15 | `prices/trade_market.py:83-150` | `quoted`, `thin`, `none`, `stale`, `unknown` and the reason (`TradeOffer`) |
| 16 | `prices/price_file.py:46-66` | `MarketRecord`: a `thin` or `none` search kept as a state |
| 17 | `prices/price_file.py:76` | the `ninja` table: a poe.ninja row beside a trade price; no code writes it |
| 18 | `config.py:50,52,65` and `cli/_main.py:101,134` | the setting `price_source` (`ninja`, `trade`, `both`) and `--price-source` |
| 19 | `cli/_start_options.py:62-75` (`StartContext`) and `cli/_starts.py:104-122` | the setting is carried to every start source; the one source there reads none of it |
| 20 | `cli/_start_types.py:61` (`StartCandidate.sourced`) | the field that would hold a `SourcedPrice`; no code sets it |
| 21 | `prices/trade_pricing.py:402-405,408-415,483-531` | `refuse_name_collision`, `store_trade_price` and `merge_trade_prices`: a trade price is refused or dropped when another source holds the name |
| 22 | `tests/reconcile/checks.py:54` | `TRADE_SOURCE = "trade-api"`, the oracle's own copy of the constant |

Sources in the committed files: `routes.json` has 91 `poe.ninja`, 7 `trade-api`, 7 `poe.ninja-previous-league` (Mirage, 2026-06-13), 3 `poe.watch`; `vendor.json` adds 5 `hand`.

### 2.2 How the source travels to the answer

```
price file entry (source, note, detail)                   prices/price_file.py:206-221
  -> load_prices: a hand override replaces it, source "override"   price_file.py:325-339
  -> resolve_start_price: StartPrice(name, chaos, source)         cli/_plan.py:245-252   (note and detail dropped)
  -> make_plan: the restart offer, part (name, 1, chaos, source)  cli/_plan.py:340-344
  -> Plan.start_price                                             cli/_plan.py:94
       (or start_price_of, a ready StartPrice, which skips the lines above   cli/_plan.py:266,310; built at cli/_starts.py:88-90)
  -> read again: given-route restart refused at 0 / restart action     cli/_route.py:253,460
  -> read again: the shift added to every total                       cli/_interval.py:345, cli/_verify.py:139-156
  -> text report "Start item (name): X Chaos [source]"            cli/_report.py:309
  -> JSON "start": {price_name, price_chaos, price_source}        cli/_report.py:520-526
  -> route page: the money and the title only                     cli/_route_view.py:388,473
```

The other path, the recipe goods: `_goods` (`cli/_start_options.py:276-295`) keeps the source of each entry in `Goods`; the text report prints it (`cli/_start_report.py:62`), the JSON keeps it (`:116,170`), the page's vendor row does not (`_route_view.py:446-461`).

The path that was built for OR-7 and does not run: `source_price` (`prices/price_source.py:154`) and `trade_market.offer` (`:83`) are called by no code in `src/` (`grep` over `src` finds only definitions, re-exports and a docstring). `StartContext.price_source`, `.gap_percent`, `.today` are carried to `vendor_recipe_starts`, which reads none of them.

### 2.3 Where the source is lost (OR-7), 9 places

1. `cli/_plan.py:252`: `resolve_start_price` copies `chaos` and `source` only; the note ("item level 85, 43 observations"), the date and the listing count stay in the file.
2. `cli/_plan.py:245-252`: it takes any entry under the name, so a `poe.ninja` or `hand` stand-in (R04, R13, V01) is used as a trade price with no mark. OR-7 allows the stand-in only when marked as a fallback with its reason (#426, #406).
3. `prices/price_file.py:337`: an override entry has source `override` and no note or detail; what it replaced is gone.
4. `cli/_route_view.py:388,473,555`: the page shows the money, the key as title and one line "league ..., fetched ..." for all prices (audit INPUTS-3, ROUTES-8, #406).
5. `cli/_route_view.py:446-461`: the vendor row prints each good with its price and no source.
6. `prices/fetch.py:106-111`: the observation count of a poe.ninja base row is checked against `MIN_COUNT` (5) and dropped; the fixtures carry it as typed words in a note (R04 43, R13 41).
7. `prices/trade_pricing.py:521-522`: `merge_trade_prices` drops a trade price when the fresh poe.ninja fetch has an entry of the same name (the case #357 left for the refresher to resolve); `store_trade_price` (`:408-415`) refuses the reverse through `refuse_name_collision` (`:402-405`). R14's key is both a trade price and the name of a poe.ninja base row.
8. `committed R08 and R09 entries`: `source: trade-api` on a number that is a trade price plus the file's `Orb of Alchemy` price, typed into the sum (29.82716, 5.02716): the source says trade and the number is not one (audit INPUTS-5, #417).
9. `prices/price_source.py:154-210` read against the committed entries: `hand`, `poe.ninja-previous-league`, `poe.watch` and `default` are neither a poe.ninja row (`NINJA_SOURCES`, `:39`), nor a trade price, nor an override. If the planner called `source_price`, V01's plain start `Lion Pelt (ilvl 84)` (`hand`) would be "no price" under every setting, and R13 and R04 (`poe.ninja`) would be used as marked fallbacks although neither has a trade price to fall back from, and R04's row is a different item level.

### 2.4 Which price file wins (#429)

Order of precedence in code, first wins:

1. `start_price_of`: a ready `StartPrice` handed to `make_plan` (`cli/_plan.py:266,310`). It skips `resolve_start_price`, so it beats `--start-price`, the override file and the file. `plan_with_starts` passes it for every non-plain start candidate (`cli/_starts.py:88-90`, price built at `:89`, printed by `cli/_start_report.py:36`); the candidate's own goods were priced from the file with the overrides on top (`cli/_start_options.py:276-295`).
2. `--start-price` (`cli/_plan.py:239-242`); it applies to the plain start item only.
3. `price_overrides.toml` beside the file that was loaded (`prices/price_file.py:325-339`, `cli/_inputs.py:11-14`).
4. The entry in the file that was loaded: `target.price_file` when the target names one (read at `cli/_main.py:116` and `cli/_benchmark.py:377`, `:463`), else `<data dir>/prices.json` (`cli/_inputs.py:13`; `crafting.toml` sets the data dir to `local/data`, not committed).

Only V01 names a file (`T:v01-minion-helmet.yaml:63`). Nothing in `src/` reads a committed fixture. The third committed file, `foresight-allflame-2026-11-02.json` (8 `poe.ninja` entries, no start key), is read only by `tests/test_prices_foresight.py`. The committed files are chosen by the callers:

| File | Chosen by |
|---|---|
| `routes.json` | 15 test files by a constant (`test_cli_approximate_real`, `_jewel_real`, `_parallel_real`, `_r04_r14_heavy`, `_r04_r14_real`, `_r08_r09_real`, `_r13_real`, `_roll_real`, `_routes_real`, `test_packed_heavy`, `_packed_plan_real`, `test_prices_start_items`, `_trade_market`, `test_prune_bound`, `_prune_equal`; a 16th, `test_risk_r04_r14_chains`, only cites it in its docstring) and 10 scripts under `.github/scripts/` (`count_states`, `measure_routes`, `measure_sim`, `packed_routes`, `profile_plans`, `reachability_report`, `simulate_route`, `state_bloat`, `time_plans`, `time_routes`) |
| `vendor.json` | `T:v01-minion-helmet.yaml:63`, `tests/test_vendor_benchmark_real.py:52`; the measurement scripts get it for V01 through `load_target_prices` |
| both | `tests/reconcile/files.py:158-173` (`price_files_of`): every committed file that holds the key, so each of R04, R05, R08, R09, R10, R11, R12, R13 and R14 is read twice |

The two files share 108 keys and all 108 entries are equal today (compared entry by entry in this inventory); `vendor.json` adds 5 keys, all `hand`: `Lion Pelt (ilvl 84)`, `Sorcerer Boots (ilvl 84)`, `General's Helmet (ilvl 84)`, `Quicksilver Flask`, `Vendor recipe gems (minion, 40% quality)`. Nothing keeps the 108 equal. A refresh of one copy changes what a test reads and what V01 reads, and no check fails (the reconcile `price.*` slots read both and a differing pair would surface only as a changed pinned value).

Two more facts about the files, both bearing on #351 and #359: the rows their "Done when" names are in neither file (R13 at levels 84 and 85, 1.7 and 1.0 Chaos; R08 at 84, 85, 86, 1.03, 5.33, 7.43; the only `Sorcerer Boots (ilvl 84)` is a `hand` entry at 3.0 in `vendor.json:887`); and the trade entries are dated 2026-10-31 (R05, R10, R11, R12) and 2026-11-01 (R08, R09, R14), while `trade_market.offer` calls an entry older than `MAX_AGE_DAYS = 7` (`prices/price_file.py:29`) stale, so a test that wires `source_price` needs a fixed `today`.

---

## 3. Derivations that already exist in code (17)

Direction is "derives X from Y". "Called by" is every caller found by search.

| # | Derives | From | Where | Called by |
|---|---|---|---|---|
| D1 | a base id | an English name or id (skips Battle Royale copies) | `targets/resolve.py:201-224` | `parse.py:295` `read_base` |
| D2 | the start item | `base`, `item_level`, `influence`, the `start_item` block (a fresh normal item when the block is missing) | `parse.py:950-1018` `read_start_item` (`Item.build`) | `parse.py:215` |
| D3 | a one-mod Magic start item | the target's base, level and influences plus a recipe step | `cli/_start_options.py:167-172` `_start_item` | `_examine` (`:211-212`) |
| D4 | a start item at another level | the target, a level | `targets/floor.py:326-340` `target_at_level` | no code in `src` (tests: `test_targets_floor_real.py:154-180`) |
| D5 | the lowest level and the level groups | the requirements, the start mods, the offered actions | `targets/floor.py:247-310` `floor_of`, `level_groups`, `item_level_options` | no code in `src` |
| D6 | a price key | base name, level, influences | `prices/price_names.py:81-85` `base_price_name` | `cli/_start_options.py:280` (the recipe's base), `prices/ninja_items.py:66` (poe.ninja rows); `BuySpec.__post_init__` and the loaders re-spell it through `canonical_price_name` (`trade_query.py:268`, `price_file.py:197,230,261,318`, `cli/_plan.py:245`, `cli/_benchmark.py:460`, `prices/__main__.py:197,259`, `fetch.py:75-76`) |
| D7 | the base, level and influences from a key | a key string | `prices/price_names.py:88-97` `parse_base_price_name` | `prices/fetch.py:172,174` (to look a wanted name up in poe.ninja) |
| D8 | the start price | the target's `start_price` name, the file, a run override | `cli/_plan.py:231-252` `resolve_start_price` | `_plan.py:310`, `_starts.py:54` |
| D9 | the `restart` offer | the start item and its price (only when above 0) | `cli/_plan.py:340-344` | `make_plan` |
| D10 | a start candidate | the target, the file, an override | `cli/_starts.py:51-58` `plain_candidate` | `plan_with_starts` (`:126`) |
| D11 | a target for a candidate | the target and the candidate's item | `cli/_starts.py:88` (`dataclasses.replace(target, start_item=..., start_price=None)`) | `_plan_candidate` |
| D12 | the recipe starts and their price | target, recipes, file | `cli/_start_options.py:310-362` `vendor_recipe_starts` | `plan_with_starts` through `SOURCES` (`_starts.py:48`) |
| D13 | the trade query | a buy spec, the resolved stat filters | `prices/trade_query.py:291-315` `build_query` | `prices/trade_pricing.py` (price time), `cli/_route_trade.py:49` (page time) |
| D14 | a trade stat id | a mod's stat text, family id or mod id, the site's stat list | `prices/trade_stats.py:159-185` `resolve_buy_mod` (with `named_mods`, `:151`) | the two callers of D13 |
| D15 | the page's Accepts lines and trade link | a buy spec | `cli/_route_trade.py:36-90` | `cli/_route_view.py:697` |
| D16 | the page's "Accepts" when no spec is given | the target's start item | `cli/_route_view.py:419-428` `start_accepts` | `buy_row` |
| D17 | the tier of a mod on a base | the game data | `items/tiers.py:31-70` `tier_table`, `mod_tier` | the abstraction (`_kernel.py:246,430`), the actions, `_route_card.py:303`, `_start_options.py:195`, `floor.py:190`; never to check or fill a start mod's `tier:` |

Not derivations, but the same kind of link: `parse.py:271` decides `buys` from "has a `start_price`" (the corruption check); `cli/_benchmark.py:472-481` finds a spec file from the price name by scanning `examples/buy/`.

Derivations that exist only in tests: the item class to trade category map (`TRADE_CATEGORY`, `tests/independent/ladder.py:94-105`, 10 classes; `src` has no such map, the spec's `category:` is typed); the level and base name of a price entry from its query, note or key (`tests/reconcile/files.py:189-224`); the natural tier of a start mod and the window of minimums that price it (`tests/reconcile/checks.py:197-262`); the mod pool of a base (`tests/reconcile/ladder.py:64-80`).

What does not exist: a spec from a target, a key from a base id, a start mod's tier from the data, the trade category of a base, any check that the entry was taken for the item the target starts from.

---

## 4. The buying block of the v1 map

Blockers as of today: #351 is unblocked (#357 closed); #354 is unblocked (#352 closed); #353 waits for #351; #356 waits for #354; #359 waits for #351, #353, #354; #360 waits for #356. Facts: B base, L item level, I influence, M start mods, R start rarity, S buy spec, Q trade query, K price key, E price entry and its source. "reads" and "writes" are what the ticket's text and its comments require.

| Ticket | B | L | I | M | R | S | Q | K | E |
|---|---|---|---|---|---|---|---|---|---|
| #351 start options from the price file | reads | reads | reads | none | none | none | none | reads and builds | reads (`prices`, `ninja`) |
| #353 rails and the cut report | none | none | none | reads (count) | none | none | none | none | reads (listing count) |
| #354 fractured-start candidates | reads | reads | reads | reads and writes | writes | writes | writes | writes | none |
| #356 refresher | reads | reads | reads | reads | reads | reads | writes | reads and writes | writes |
| #359 plan the options | reads | reads | reads | reads | reads | none | none | builds | reads |
| #360 vendor-recipe prices | none | none | none | none | none | writes | writes | builds | writes |

**#351 Start options from the price file.** Lists the target's base at levels from the floor to 86, the influence sets the target needs, one option per equal-pool group, each with the trade price and the poe.ninja row (at least 5 observations).
- Reads B (`Target.base_id`), L (`floor_of` and `level_groups`, `targets/floor.py:247,290`, unwired today), I (`Target.influences`; "the influence sets the target needs" is not stated by any file: the target's `influence:` is the author's word, R06 and R14 only).
- Builds K by `base_price_name(base.name, level, influences)` as `_start_options.py:280` does: by base name. For R09 the name `Two-Toned Boots` is three bases with other pools (#418, #428), and for R04 two quivers; a poe.ninja line has no base id, only name, level and variant (`prices/ninja_items.py:59-66`), so a name that is shared cannot be told apart from the line.
- Its derived key equals the typed `start_price` for 4 of the 11 targets (R04, R13, R14, V01) and can equal none of the other 7 (route-tagged names). For R14 the derived key is also the name of the trade entry, which is the collision of F10 and section 2.3 row 7.
- Reads E in two tables: `PriceFile.prices` and `PriceFile.ninja` (`price_file.py:76`; no code writes `ninja`, the fixtures have none). "At least 5 observations" is a property the fetcher drops (section 2.3 row 6).
- The "Done when" fixture rows (R13 84/85/86, R08 84/85/86) are in no committed price file (section 2.4); where they will live is the #429 decision.

**#353 Realism rails and the cut report.** Two settings, `listing_count_min` (10) and `max_wanted_mods` (1), applied to every bought-start option; the report names the rail and value for each option left out.
- Reads E: `detail.listings` of a trade entry, `MarketRecord.listings` (`price_file.py:51-66`); `trade_market.offer` already takes `min_listings` (`trade_market.py:83-88`). A poe.ninja row has an observation count and no listing count (OR-7: it "does not prove an instant-buyout listing"), so how the first rail applies to a ninja-priced option is not said.
- Reads M: the number of wanted mods of a candidate (the 4 hand start items R05, R10, R11, R12 each have 1).
- Writes only report lines and two entries of `_PLANNER_SETTINGS` (`config.py:50`).

**#354 Fractured-start candidates, cut by the route.** From the target: one stat text per leaf the base can roll, the minimum roll of the lowest accepted tier, for each pool group of item levels; dropped when no offered action can rework a rare item; each converts to a buy spec with `item_level_min` and `_max`.
- Reads B (the pool), L (level groups), M (the target's requirement leaves as stat texts; the lowest accepted tier from `tier_table` and `min_tier`/`min_roll`), the offered actions (`Target.actions`).
- Writes S, Q, K for each candidate: it is the first code that derives a buy spec from a target. It meets every problem of F1 to F10 at once: the category (item class to trade category exists only in `tests/independent/ladder.py:94-105`), `base_type` by name against base id, the rarity (rare), a `minimum` from a tier (done by hand for the 4 existing specs; the window is computed only in `tests/reconcile/checks.py:240-262`), `item_level_max` (set by none of the 8 specs; `BuySpec` has it, `trade_query.py:259`), and a new price key with no naming scheme.
- Its R05 result (5 candidates) includes the item the hand spec `B:r05-start-ring.yaml` already describes; so does R10's, R11's and R12's own start item. Two descriptions of one bought item would exist unless one replaces the other.

**#356 Price refresher service component.** Scheduled; fetches the poe.ninja base list and anonymous trade queries for the candidates of #351 and #354 that are not fresh; writes the price file; through the limiter of #358.
- Reads the candidate lists (K and S from #351 and #354) and freshness (`trade_market.offer(...).fresh`, `trade_market.py:77-80`); writes E (`prices`, `markets`, and the `ninja` table), Q (the stored body and hash through `entry_for`, `trade_pricing.py:384-399`), K (the spec's name).
- Must resolve the collision #357 left in its comment: `merge_trade_prices` and `store_trade_price` drop or refuse a trade price whose name a poe.ninja price holds (section 2.3 row 7).
- Writes the same file the planner reads, so the committed fixtures become test data only; which of the two is the model for that file is #429.
- The comment from #358: the limiter's state is lost on restart. Not a fact of this inventory.

**#359 Plan the start options and choose the cheapest.** Plans each option with its own restart; answers with the cheapest total; extends `plan_with_starts` (`cli/_starts.py:96-170`).
- Reads B, L, I (`target_at_level` sets the level and the start item's level only, not `start_price` or `price_file`; the #352 checker's comment asks for a test where the named price's level differs from the planned level), M (a fractured candidate becomes the start item: the pattern of `_starts.py:88`), E under the price source setting (`source_price(..., fractured=True)`, the #357 comment).
- Builds K for every option other than the plain one, while the plain option keeps the typed `start_price`: two key mechanisms side by side. For R04 the typed key is a label on an item-level-85 line, and for R13 at level 84 the typed key names level 86.
- Sets `StartCandidate.sourced` (`_start_types.py:61`), which nothing sets today. Its "Done when" needs R13's 84 row (section 2.4).
- With `source_price` wired, the plain start items that are stand-ins change behaviour (section 2.3 row 9): V01's `hand` base is "no price"; R13's and R04's `poe.ninja` rows are marked fallbacks.

**#360 The refresher also fetches vendor-recipe flask and gem prices.** Flasks through the buy-spec fetcher ("a Normal flask of the base type"), gems through a new gem query; added to the candidate list under the same market rule and price source.
- Writes S (a spec for a Normal flask: `base_type`, rarity normal, no level, no mods; a gem query with no spec shape today), Q, K (`good_name`, `gem_price_name`, `_start_options.py:128-139`: `Quicksilver Flask`, `Vendor recipe gems (minion, 40% quality)`), E (replacing 4 of the 5 `hand` lines of `vendor.json`; the fifth is the base `Lion Pelt (ilvl 84)`, which is both V01's `start_price` and the recipe's derived base key).
- V01's `price_file:` line (`T:v01-minion-helmet.yaml:63`) exists because these lines are not fetched (its comment `:24-27`); when #360 lands, that line and the `hand` entries are what #429 decides about.

---

## 5. Places that no open issue lists

Filed (OR-29): each point is in exactly one issue, linked at its end. Each has its file and line.

1. **The entry's own rarity, influence, corrupted flag and mods are compared with nothing.** The `price.*` slots cover base, level, source and pool only (`tests/reconcile/checks.py:93-94`). R14's entry encodes the influence in a pseudo stat and its key; R08's and R09's encode rarity normal; R05's, R10's, R11's and R12's encode the fractured mod. (F3, F6, F7.) Filed: #470.
2. **The stored query is never compared with the query the spec builds.** No test calls `build_query` on a real `examples/buy` spec and compares the body with `detail.query` or `search_body_*.json`; the page link is rebuilt at render time (`cli/_route_trade.py:36-51`) and is golden for R05, R10, R11 only (`tests/test_cli_routes_real.py:50,155`). Specs of R04, R08, R09, R12, R14 have no link check. (F9.) Filed: #470.
3. **`--buy-spec` is a free path.** `cli/_main.py:98,165-169` builds the page's Accepts and link from whatever file is passed; nothing ties it to the target's `start_price`. (F8.) Filed: #470.
4. **The page's buy step is titled by the internal price key and omits the base.** `cli/_route_view.py:473` (`Buy R05 start ring`), `cli/_route_trade.py:74-90` (no `base_type`, no category); audit INPUTS-7. #406 lists only the source and age (`_route_view.py:390,555`). (F1, F10.) Filed: #470.
5. **The observation count of a poe.ninja base row has no field.** The fetcher drops it (`prices/fetch.py:106-111`); the two ninja start entries carry it as words in a note (R04 "43", R13 "41"). #351 and the research note (`docs/research/2026-11-01-buying-any-state.md`, section 4, "the report shows the observations") need it. (Section 2.3 row 6.) Filed: #472.
6. **#351's "Done when" rows exist in no committed file.** R13 at 84 and 85, R08 at 84, 85, 86 are in neither `routes.json` nor `vendor.json`; `vendor.json:887` holds a `hand` `Sorcerer Boots (ilvl 84)` at 3.0 Chaos where the poe.ninja row is 1.03 (research note, section 1.3). #429 asks which file wins, not where these rows go. Filed: #473.
7. **V01's plain start key is typed and derived.** `T:v01-minion-helmet.yaml:59` and `cli/_start_options.py:280` write the same string; only `tests/test_vendor_benchmark_real.py:85` ties them. The same holds for R04, R13, R14 against `base_price_name`. Filed: #471.
8. **Wiring `source_price` changes the stand-in entries.** V01's `hand` start is "no price" under every setting; R04's and R13's `poe.ninja` entries become marked fallbacks with no trade price behind them. #426 and #406 name the stand-ins and the unwired function; neither names this consequence for #359 and #360. (Section 2.3 row 9.) Filed: #472.
9. **The committed trade entries age out.** Dated 2026-10-31 and 2026-11-01, they are stale for `trade_market.offer` after 2026-11-07 and 2026-11-08 (`prices/trade_market.py:140-143`, `MAX_AGE_DAYS` 7). A test that calls `source_price` needs a fixed `today`. Filed: #473.
10. **A typed number inside a trade price.** The `0.02716` of R08 and R09 is the file's own `Orb of Alchemy` price added by hand under `source: trade-api` (`routes.json:348,403`). #417 names the hidden Alchemy step (OR-16); it does not name the typed sum or its source label. Filed: #472.
11. **A price written in prose.** `ExpectedStart.why` of V01 states 8, 866 and 1,349 Chaos (`cli/_benchmark.py:247-253`); nothing checks them against the fixture they cite. Filed: #473.
12. **`item class -> trade category` exists only in tests.** `tests/independent/ladder.py:94-105`; `src` takes `category:` from the hand-written spec. Any spec derived from a target (#354) needs it in `src`. Filed: #471.
13. **A shared base name cannot be told apart by the poe.ninja line.** The line has name, level and variant (`prices/ninja_items.py:59-66`), no base id; the fix proposed in #418 and #417 ("derive the key from the base id") has no counterpart on the poe.ninja side for R09's three Two-Toned Boots or R04's two quivers. Whether the trade site tells same-name bases apart (a discriminator in its item list) was not checked: no request was made. Filed: #471.
14. **The user is told to run the price commands by hand (OR-9).** `cli/_plan.py:248-251` and `cli/_benchmark.py:463-468,483-493` send the user to `python -m crafting_system.prices trade --spec ...`; `prices/price_file.py:30,161-163,358-361` quote the `fetch` command; `prices/__main__.py:77-91,196` is a hand-run command; `README.md:32,34` and `examples/targets/r12-lightning-amulet.yaml:56-58` describe it. OR-9: the system refreshes prices itself. Filed: #478.

---

## 6. Options for the single source

No decision is made here. The question each option answers: which one description is typed, and what derives from it. "Blast radius" counts the files that name the thing that changes, from the searches of this inventory (tests are counted without `tests/reconcile/`, which every option rewrites: 3 test modules, `checks.py`, `files.py`, `known.py`, `expected_checks.txt`, 178 checks, 30 known).

Common to every option, and listed once: `src/` files that mention `start_price`: 16 (`cli/_benchmark.py`, `_interval.py`, `_main.py`, `_plan.py`, `_report.py`, `_route.py`, `_route_report.py`, `_route_sim.py`, `_route_view.py`, `_starts.py`, `_start_report.py`, `_verify.py`, `cli/__init__.py`, `targets/model.py`, `parse.py`, `targets/__init__.py`; most of them mean `Plan.start_price`, which is the resolved price, not the key). Test files that mention `start_price`: 35.

### Option A. The target is the only description; the spec, the query and the price key are computed from it

- Derives: start item (as today, D2); buy spec = function of (base, level, influence, rarity, start mods); trade query = `build_query` of that spec; price key = function of the same fields. No `examples/buy/` files and no `start_price:` line.
- Needs that does not exist: item class to trade category in `src` (section 5 row 12); a minimum from a tier (the window in `tests/reconcile/checks.py:240-262`); a base discriminator for same-name bases at the trade site and a base-id key for poe.ninja rows that carry only a name (section 5 row 13); a decision for the 3 targets with no price (#427, #410 point 4).
- Blast radius. Targets: 14 files (11 lose `start_price`; J01, R03, R06 must say what they cost or that they are given). Specs: 8 files go. Fixtures: 2 price files re-keyed (19 start entries), 4 recorded bodies and 1 spec fixture regenerated where the derived spec differs from the hand one (R05 and R12 gain a base and R12 a level). `src/`: about 19 files (`targets/parse.py`, `model.py`, `__init__.py`, `corrupted.py`; `cli/_plan.py`, `_starts.py`, `_start_options.py`, `_benchmark.py`, `_main.py`, `_route_view.py`, `_route_trade.py`, `_report.py`; `prices/trade_query.py`, `__main__.py`, `price_names.py`, `price_file.py`, `trade_pricing.py`, `fetch.py`, `ninja_items.py`) plus one new module. Tests: 24 files name a key or a spec, 8 goldens carry a key as title.
- Closes: #417, #418, #427, #428 and the `price.base` rows; not #425, #426, #429 by itself.

### Option B. Keep the names and the spec files, but generate the spec from the target and check the committed copy

- Derives: the buy spec (and with it the query and the page's Accepts and link) from the target; `start_price` stays a typed name; the committed `examples/buy/` files become generated artefacts or are checked against the generated ones (the reconcile package becomes that check).
- Blast radius. `src/`: about 6 files (`prices/trade_query.py` for the derivation, `cli/_main.py`, `_route_view.py`, `_route_trade.py`, `prices/__main__.py` for `--target` in place of `--spec`, `cli/_benchmark.py`). Specs: 8 files regenerated. Tests: 7 files name a spec. Fixtures: unchanged unless a derived spec differs from the hand one (R05, R12). Targets: unchanged.
- Closes: #417, #428; #418 only in part (the key stays a name and the entry still does not name a base). Same needs as A for the category, the minimum and the discriminator.

### Option C. Make "given or bought" explicit and the price required; leave the spec and the key as they are

- Derives: nothing new. A target says whether its start item is given or bought (OR-6); a bought one must name a price; the coupling "no price means free and no restart" goes (the places P1 to P14 listed in #453, point 2).
- Blast radius. Targets: 3 files (J01, R03, R06). `src/`: 14 files: `targets/parse.py`, `model.py`, `corrupted.py`; `cli/_plan.py`, `_starts.py`, `_benchmark.py`, `_route.py` (the restart refused at 0, `:253`, and built at `:460`), `_route_view.py`, `_report.py`, `_interval.py` (`:345`), `_verify.py` (`:139-156`), `_offers.py` (P12 the free-action cost, P14 the Chaos and Divine special cases); `risk/_free.py` and `risk/_evaluate.py` (the recognition of a free action by its value). Tests: about 8 files (`test_targets_parse.py`, `test_risk_free_actions.py`, `test_prune_bound.py`, `test_cli_benchmark.py`, `test_cli_plan.py`, `test_targets_corrupted.py`, plus the reconcile rows). Fixtures and specs: unchanged.
- Closes: #427 (the 8 rows); none of the base, level or price-key rows.

### Option D. The price entry describes the item it was taken for; the planner checks it against the target

- Derives: nothing is generated; each price entry carries the base (name and, where known, id), item level, influence, rarity and mods it was taken for, and `resolve_start_price` refuses an entry that does not describe the target's start item.
- Blast radius. `src/`: about 6 files (`prices/price_file.py` schema and loaders, `trade_pricing.py` `entry_for`, `fetch.py` and `ninja_items.py` for the poe.ninja rows, `cli/_plan.py`, `price_source.py`). Fixtures: 2 price files (19 start entries get fields; the 91 poe.ninja rows only where a start item uses one). Tests: 43 test files construct `PriceEntry(` (they keep working if the new fields are optional), 5 pin the entry's shape (`test_prices_start_items`, `_trade_market`, `_trade_cli`, `_trade_pricing`, `test_prices_file`). Targets and specs: unchanged.
- Closes: #418, #425 (the entry names its level), part of #426 (the source and the reason can sit in the same record); not #417 or #427.

### Option E. The reverse: the buy spec is the only description; the target's start item is read from it

- Derives: start item (base, level, influence, rarity, mods) from the spec; the query from the spec (as today); the key is the spec's `name`; the target keeps only the requirements.
- Against it, from the code: `BuyMod.stat` is the trade site's language (English text, family or mod id, `trade_query.py:233`) and a `minimum`, not a mod id and a tier, so the target's `tier:` and `values:` (F6) would have to be derived from a minimum and the data, and 9 targets lose their `start_item` blocks. The 3 targets with no spec and the vendor recipes (whose start items are not bought) have no spec to read.
- Blast radius. Targets: 9 files with a `start_item` block lose it. `src/`: `targets/parse.py` and `model.py` read a spec, plus the 3 callers of `Item.build` for a start item. Tests: the 28 files that name a target file and `tests/test_targets_files.py:16-22,263-285,330-346,373`.
- Closes: #417 and #428 by construction; leaves #427 and the price rows open.

### Choices that change the blast radius of every option

- **Key by name or by base id.** The poe.ninja side cannot give an id (section 5 row 13); a key by id is trade-only unless the ninja rows are attached to every base of the name and the pool difference is accepted or flagged.
- **Which price file the planner reads, and whether a committed file may hold other routes' keys** (#429). It decides whether the 108 shared entries exist once or twice, where the rows #351 and #359 need go, and what `T:v01-minion-helmet.yaml:63` becomes when #360 replaces the `hand` lines.
- **How a stand-in is marked** (OR-7, #426, #406). It decides whether `resolve_start_price` keeps calling "any entry under the name" or calls `source_price`, and so whether V01, R04 and R13 stay plannable (section 2.3 row 9).
- **Whether the Alchemy of R08 and R09 is a step or a priced fact** (OR-16, #417): the target says a rare item with no mods, the spec a normal one.
- **Whether a start mod's tier is typed or derived** (F6). A derivation would also fill the minimum of the spec; `tests/test_targets_files.py:35` pins today's typed R12 value.
