# The planner chooses its start base, and a fractured start, from a priced list kept fresh by the system

Ticket [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337), note [`docs/research/2026-11-01-buying-any-state.md`](../research/2026-11-01-buying-any-state.md), owner answers of 2026-11-01. This is the v1 slice. The general "buy any compressed state" mechanism stays a v2 hypothesis (map [#325](https://github.com/Rasslabsya4el/crafting-system/issues/325)); a bought item replaces the item in hand, so every buy offer is a reset to a priced state, and `restart` (ADR-0011) is the one-candidate case.

## Decisions

1. **The target's item level is a floor.** The planner may plan at a lower item level than the file's number when every leaf of the target stays reachable. The floor is derived from the tiers the leaves ask for (tiers are absolute per base), or stated by the target. A level is not lowered where the author wrote it to mean "the top tier at that level" (R05's resistances). One plan per equal-pool group of levels; the answer is the cheapest total of start price plus plan, the other options listed with their totals. Measured: R13 5,492 / 5,638 / 6,311 Chaos at levels 84 / 85 / 86.
2. **Plain bases and influence come from the poe.ninja base list** in the price file (item levels 82 to 86, a row with at least 5 observations). A row is enough for a plain base; it does not prove an instant-buyout listing and the report says so. No row, no option.
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
