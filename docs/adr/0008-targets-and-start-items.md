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
