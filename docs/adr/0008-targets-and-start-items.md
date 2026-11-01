# A target is a conjunction of requirements, reached from a concrete start item

A target is a conjunction of requirements. A requirement names a mod by family or by English stat text, with a minimum tier or a minimum roll; k-of-n requirements ask for at least k of n listed requirements. How a mod got onto the item (natural, crafted, fractured) does not matter unless a requirement is marked "not crafted". Every other mod is don't-care: v1 has no "must not have".

A query starts from any concrete item, by default a fresh normal base with an item level and influence; buy actions give other starts. B1 to B4 start items carry no Memory Strands (main chat, 2026-10-30, in [Owner decisions on B1 mechanics no source or Craft of Exile settles](https://github.com/Rasslabsya4el/crafting-system/issues/28)); **from B5 a start item may carry a strand count** (amendment below).

A target names the price of its start item with the optional key `start_price`: the name that item has in the price file (a bought item is priced by the trade API under its buy spec's name, a hand override wins). Without it the start item counts as free. Added in [R12 end to end: CLI, JSON policy and text tree](https://github.com/Rasslabsya4el/crafting-system/issues/26).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q6.

## Amendment: start items with Memory Strands ([Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103), 2026-11-01)

The owner allowed a plan to start from a bought item that carries Memory Strands and to use an Orb of Remembrance on a fresh base ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)). A start item therefore has an optional `memory_strands` count from 0 to 100: the key `memory_strands: N` in the item YAML and the pasted line `Memory Strands: N` (ADR-0040). **A target never asks for strands.** A Genesis-born or otherwise acquired item is just a start item; acquisition methods are not modelled (ADR-0043).

## Amendment: sockets in targets and start items ([Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), 2026-11-01)

A target may carry `sockets: {count, links, colours: {R, G, B}}` and, on a weapon or armour, `quality: {min_percent}` (ADR-0046, ADR-0049). A socket requirement is a requirement of the finish, not of the mod problem: it adds no line to the mod requirements. A start item may state its sockets, links, colours and quality; when the target names sockets, one that states none has one white, unlinked socket (ADR-0046); otherwise it gets no socket.

## Amendment: start items from vendor recipes ([#329](https://github.com/Rasslabsya4el/crafting-system/issues/329), 2026-11-01)

A start item may also be **made by a vendor recipe** from a Normal base and cheap goods: a Magic item with one chosen mod, priced as the sum of the goods. The planner plans the plain start item and each recipe-made one and keeps the cheapest total. A target asks for no recipe; the choice is made outside the solver ([ADR-0059](0059-vendor-recipes-are-start-item-sources.md), which also amends ADR-0043's "acquisition methods are not modelled" for vendor recipes only).
