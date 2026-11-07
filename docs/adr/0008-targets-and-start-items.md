# A target is a conjunction of requirements, reached from a concrete start item

A target is a conjunction of requirements. A requirement names a mod by family or by English stat text, with a minimum tier or a minimum roll; k-of-n requirements ask for at least k of n listed requirements. How a mod got onto the item (natural, crafted, fractured) does not matter unless a requirement is marked "not crafted" (**amended for a requirement with no stated tier: see "Amendment: the owner's reading rules" below**). Every other mod is don't-care: v1 has no "must not have".

A query starts from any concrete item, by default a fresh normal base with an item level and influence; buy actions give other starts. B1 to B4 start items carry no Memory Strands (main chat, 2026-10-30, in [Owner decisions on B1 mechanics no source or Craft of Exile settles](https://github.com/Rasslabsya4el/crafting-system/issues/28)); **from B5 a start item may carry a strand count** (amendment below).

A target names the price of its start item with the optional key `start_price`: the name that item has in the price file (a bought item is priced by the trade API under its buy spec's name, a hand override wins). Without it the start item counts as free. Added in [R12 end to end: CLI, JSON policy and text tree](https://github.com/Rasslabsya4el/crafting-system/issues/26).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q6.

## Amendment: start items with Memory Strands ([Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103), 2026-11-01)

The owner allowed a plan to start from a bought item that carries Memory Strands and to use an Orb of Remembrance on a fresh base ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)). A start item therefore has an optional `memory_strands` count from 0 to 100: the key `memory_strands: N` in the item YAML and the pasted line `Memory Strands: N` (ADR-0040). **A target never asks for strands.** A Genesis-born or otherwise acquired item is just a start item; acquisition methods are not modelled (ADR-0043).

## Amendment: sockets in targets and start items ([Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), 2026-11-01)

A target may carry `sockets: {count, links, colours: {R, G, B}}` and, on a weapon or armour, `quality: {min_percent}` (ADR-0046, ADR-0049). A socket requirement is a requirement of the finish, not of the mod problem: it adds no line to the mod requirements. A start item may state its sockets, links, colours and quality; when the target names sockets, one that states none has one white, unlinked socket (ADR-0046); otherwise it gets no socket.

## Amendment: start items from vendor recipes ([#329](https://github.com/Rasslabsya4el/crafting-system/issues/329), 2026-11-01)

A start item may also be **made by a vendor recipe** from a Normal base and cheap goods: a Magic item with one chosen mod, priced as the sum of the goods. The planner plans the plain start item and each recipe-made one and keeps the cheapest total. A target asks for no recipe; the choice is made outside the solver ([ADR-0059](0059-vendor-recipes-are-start-item-sources.md), which also amends ADR-0043's "acquisition methods are not modelled" for vendor recipes only).

## Amendment: the owner's reading rules ([#401](https://github.com/Rasslabsya4el/crafting-system/issues/401), owner decisions of 2026-10-31 and 2026-11-02)

The owner's rules for reading a target are written in [`docs/owner-rules.md`](../owner-rules.md) (OR-1 to OR-6), which is the document of record. They replace the default stated at the top of this ADR for a requirement with no stated tier:

- **An unstated tier is the top tier the item level allows, rolled** (OR-1). A requirement that names a mod by family or stat text with no `min_tier` and no `min_roll` means that top tier of its ladder, on a mod that was rolled, not made at the bench; a requirement with a `min_roll` asks that roll, with no tier (OR-4). The earlier default, "any tier, any source", is replaced. A crafted mod meets a requirement only when the requirement names that craft exactly.
- **A mod forced by an essence or a bench craft is exactly that mod and tier** (OR-2): the requirement names it with `mod:`. A mod of a bought start item is the tier the trade price was taken for (OR-3).
- **The guide's own wording wins** (OR-4). A tier, a number or a soft wish the guide states goes into the target as written ("preferably at least 70 Life" is a roll of at least 70, not tier 1). The top tier applies only where the guide states no tier.
- **A target never says which actions are allowed** (OR-5). Every kind is offered and pruning decides; a target states what to end with and what to start from.
- **A start item is given or bought** (OR-6), as ADR-0043 says; this ADR's start item is not an acquisition method.

The model, the target files and the tests are not changed by this amendment. Where they still follow the old default, that is listed in the open points of #401 and fixed by the tickets of the audit's rebuild (steps 2 to 4), against an oracle that does not share the planner's reading. Until then `docs/owner-rules.md` is what a builder, a checker and a test follows, and the old default is not to be copied into a new target.

## Amendment: the target is the only description of a bought start item ([#474](https://github.com/Rasslabsya4el/crafting-system/issues/474), 2026-11-06)

The key `start_price` and the hand-written buy specs of `examples/buy/` are gone. A target says `start: bought` when its start item is bought (it replaced the stand-in `buys_start_item: true` in #505, see the last amendment); the base, item level, influences, start rarity and start mods it already states are then the only description of the item. From them `targets/start_buy.py` computes:

- the buy spec (`buy_spec_of`): the trade `type` is the base's name, the category comes from the item class, the rarity is the start item's, as the target states it (the committed prices of R08 and R09 are of a Normal base plus a typed Alchemy and are marked as a price for another item, OR-16, #494), the item level window runs from the target's level to the highest level with the same mod pool (`floor.level_groups`), the influences are the start item's, and each start mod is searched by its stat text with the lowest roll of the mod's own range as the minimum (OR-3), fractured as the target says;
- the trade query: `build_query` of that spec;
- the price key (`start_price_key`), the name of the spec, readable as the item: `Amethyst Ring, item level 75, fractured +(13-16) to all Attributes`. A base whose name another released base shares carries its id (`Two-Toned Boots [BootsAtlas1], item level 86-100`). The trade site's item list has one entry per base type and its `disc` field only marks legacy uniques, so `type` cannot tell them apart; where the implicits of the bases read differently (the three Two-Toned Boots) the query also asks for the base's own implicit (`BuyMod.own`: part of the base, not a bought mod), and where they read alike (the two quivers) nothing can. A price whose stored search differs from the computed one is shown with the line "price taken for a wider item (...)" in the report and on the page.

`python -m crafting_system.cli trade TARGET.yaml` prices a target's start item (it replaces `prices trade --spec`; it sits in `cli` because `prices` may not import `targets`, ADR-0018). The route page's buy step is titled by the key and gets its filter and trade link from the computed spec, so `--buy-spec` is gone.

## Amendment: a start item is given or bought, and a bought one must have a price ([#505](https://github.com/Rasslabsya4el/crafting-system/issues/505), 2026-11-06)

OR-6 says a start item is given or bought. A target now says which, in the required key `start: bought` or `start: given` (`buys_start_item` is gone; a file without the key is an error that offers both words). The key decides the rest, never the price:

- **bought**: the price is looked up under the key computed from the target (`start_price_key`), and a missing entry is a `PlanError` that names the key. `--start-price` must be above 0 (a zero, a negative, NaN or infinity is refused). A `restart` buys the item again; a given route may name it.
- **given**: its cost is not counted and the plan never buys another, so no `restart` is offered (a route that names one is refused, whatever the price file holds), `--start-price` has nothing to set, the text report reads "Start item: given: its cost is not counted, and the plan never buys another", the page's first row is "Start item (given)", and the answer carries the limit "The start item is given" with that guarantee (OR-13). The reason is written in a YAML comment that quotes the guide ("you already have the item").
- The corruption check of ADR-0036 reads the key: a target that says `start: bought` (or whose start item is corrupted itself) is not checked for the corrupting kinds; a given one is.
- A start option the plan cannot price is reported as unpriced (`StartCandidate.price` is None, `start_price_chaos` is null in the JSON), never as an infinite price. The benchmark's "missing price" is an error that asks for a price above 0 and writes no `= 0` placeholder.
- Where a guide buys the item and the trade site holds fewer listings than the rail, the target stays `bought`, no price is written, and the plan refuses (R03, R06: #483).

Out of this amendment: the price entry's own description, one price file, marked stand-ins and the source on the page (#429, #426, #406); the recognition of a free action by its value and the fixed Chaos and Divine prices (P12, P14 of #453).

## Amendment: the key carries the corruption, and a shared-name poe.ninja line prices a base only when the bases agree ([#471](https://github.com/Rasslabsya4el/crafting-system/issues/471), 2026-11-07)

The price key (`start_price_key`, the name of the buy spec) now carries the start item's corruption, after the influences and before the start mods (`Amethyst Ring, item level 75, corrupted, fractured +(13-16) to all Attributes`), so a start item bought corrupted and one bought clean read two price entries (OR-3). The key is made in one place (`targets/start_buy.py`); `base_line_name` makes the other name made there, the poe.ninja-style line of the Normal base a vendor recipe buys.

A poe.ninja or poe.watch line has a name, a level and a variant and no base id. For a name that several bases share, the line prices a base only when every base of the name is the same item to a crafter: the same item class, the same implicit mods (by text and stat range) and the same mod tags (the tags some mod's weights read, so the same mod pool). Then it prices any of them (R04's `QuiverNew5` and `Quiver12`; the legacy tag of `Quiver12` is read by no mod). When they differ in any of the three (R09's three Two-Toned Boots) the line is the price of none of them and `resolve_start_price` refuses it with the words that say what differs; a price from the trade site, by hand or by `--start-price` is kept. R04's start price stays `source: poe.ninja` with its stand-in mark (OR-7, #426).

## Amendment (#545): the start item is stated, never made up

`start_item:` and its `rarity:` are required in every target file. A file without the block, or without the rarity, is refused with a message naming the key; the old defaults (a fresh Normal item when the block is absent, Rare when mods are listed and the rarity is absent) are gone, because they were claims about the player's item that the file did not make (OR-6). A target that asks for `sockets:` states its start item's sockets under `start_item.sockets`, or writes `sockets: any` there; the one assumed white socket of ADR-0046 is gone. The vendor-recipe Magic item, the published-odds item, donors, the representative item of a state and the empty rare probe are modelling devices, not claims about the player's item, and never appear as the start item on the route page or in the text answer (`tests/test_start_item_devices.py`).
