# The planner chooses its start base, and a fractured start, from a priced list kept fresh by the system

Ticket [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337), note [`docs/research/2026-11-01-buying-any-state.md`](../research/2026-11-01-buying-any-state.md), owner answers of 2026-11-01. This is the v1 slice. The general "buy any compressed state" mechanism stays a v2 hypothesis (map [#325](https://github.com/Rasslabsya4el/crafting-system/issues/325)); a bought item replaces the item in hand, so every buy offer is a reset to a priced state, and `restart` (ADR-0011) is the one-candidate case.

## Decisions

1. **The target's item level is a floor.** The planner may plan at a lower item level than the file's number when every leaf of the target stays reachable. The floor is derived from the tiers the leaves ask for (tiers are absolute per base), or stated by the target. A level is not lowered where the author wrote it to mean "the top tier at that level" (R05's resistances). One plan per equal-pool group of levels; the answer is the cheapest total of start price plus plan, the other options listed with their totals. Measured: R13 5,492 / 5,638 / 6,311 Chaos at levels 84 / 85 / 86. Built in `targets/floor.py` (ticket #352): the floor is the lowest `required_level` among the mods that pass each requirement's tier, roll and `not_crafted`, from the pool of a draw, the bench and the essences the target's `actions:` leaves in; the author's keys are `item_level_floor` (raises the floor) and `tiers_top_at_item_level` (no lowering, R05); R13 and R08 floor at 84, R05 at 75.
2. **The price source is a profile setting** (with the #323 inputs): `ninja`, `trade` or `both`, default `both`. The refresher fetches both. The planner prices with the trade data (instant buyout); when it is missing or stale it falls back to the poe.ninja base row (item levels 82 to 86, at least 5 observations) and marks the price so. The answer shows both prices side by side and flags a gap above 20% (configurable). This holds for bases and influence, not only fractured starts. A poe.ninja row does not prove an instant-buyout listing and the report says so. No price from the chosen source, no option.
3. **A fractured start (one wanted fractured mod) is priced from the trade data** the system keeps fresh (ADR-0007, amended). A candidate is a stat text of a target leaf that the base can roll, for one pool group of item levels; it is asked for only if an offered action can rework a rare item (R13 has none, so none is asked there). A market exists at **10 or more listings**; the price is the **mean of the 5 cheapest** usable instant-buyout listings.
4. **A bought rare carries at most 1 wanted mod** in v1.
5. **Both are configurable realism rails**: the listing-count threshold (default 10) and the maximum wanted mods (default 1). The planner reports, for every offer left out, which rail cut it and the value that cut it, so the two rails can be compared later.
6. **The recombinator trick for item level is not offered.** The output level cannot exceed the higher input, so the pair is dominated by buying the higher base.
7. Each start option is its own plan with its own restart (an upper bound on the joint optimum; the item level is fixed per abstraction). A joint restart is v2.

## Consequences

- No query is sent while a plan is made; the planner reads the dated price file (ADR-0007). A trade-priced option older than the file's 7 days is a warning, and a stale or missing one is not offered.
- Strands, quality and the extra crafted slot stay as ADR-0043, ADR-0049 and ADR-0053 decided; the fractured list is the place a priced start with one of them would join.
- Vendor-recipe starts (ADR-0059) join the same start-option list with a constructed price.

## Not decided here (v2, #325)

The general mechanism, a finishing-cost bound for routes that are not erasing rerolls, donors as buy offers (`Need`, ADR-0022), mods carried by a bought rare above the cap, SSF owned items, and the questions 6 to 9 of the note.

Origin: [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337); ADR-0007, ADR-0008, ADR-0009, ADR-0011, ADR-0031, ADR-0043, ADR-0059.

## Amendment: how the price source is read ([#357](https://github.com/Rasslabsya4el/crafting-system/issues/357))

The setting is `price_source` (`ninja`, `trade`, `both`, default `both`) and the gap threshold is `price_gap_percent` (default 20), both in the `[planner]` table of `crafting.toml` (the profile, apart from the target), or `--price-source` for one run. `prices/price_source.py` `source_price` answers, per name: `ninja` uses the poe.ninja row only; `trade` uses `trade_market.offer` only (instant buyout, fresh, the listing-count rail met); `both` uses the trade price and, when `offer` says it is missing, stale, thin or unknown, the poe.ninja row, marked as a fallback with the reason. A hand override of the name wins under every setting. A fractured base has no poe.ninja row: under `ninja` it is not offered, under `both` it is priced by trade alone. The poe.ninja row of a name whose trade price covers it is kept in the price file's `ninja` table (a name that only has a poe.ninja row keeps it in `prices`), so the answer can show both prices side by side; the refresher (#356) writes that table. The gap is the dearer price over the cheaper, in percent, flagged when strictly above the threshold, and only under `both`. The start sources receive the setting in their `StartContext`; the plain start item and the recipe starts are priced from the price file as before.
