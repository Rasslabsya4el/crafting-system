# Orb of Binding links the sockets it finds, and the Black Mórrígan recipes are finish steps

Two things in B6 are not Jeweller's, Fusing or Chromatic work. The Orb of Binding is a mod action that also touches sockets. The two Black Mórrígan beast recipes change sockets in one step. [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 3c and 4) settles both.

## Orb of Binding

- **Mods**: Binding upgrades a normal item to rare and "functions the same way as an Orb of Alchemy" (wiki, "Orb of Binding", checked 2026-11-01), so its mod roll is Alchemy's, with the Orb of Binding's price. It refuses a corrupted or non-normal item. It is offered when the target names sockets or when its price is below the Alchemy's; otherwise it is an Alchemy at a higher price and ADR-0031's pruning drops it.
- **Sockets**: Binding **links the sockets the item already has and never adds sockets** (owner, from play, answer 3c: a two-socket item becomes two-linked; the draft's "four linked white sockets from two" was wrong). The wiki adds: "up to four linked sockets", and "if used on an item with more than four sockets or links, the extra sockets will be lost". The planner takes both: an item with `n` sockets ends with `min(n, 4)` sockets, all linked, the surviving sockets keeping their colours (the loss is the wiki's only; marked `approximate`, with the colours of survivors).
- **A contradiction recorded**: the same wiki page says the orb adds sockets "ignoring item level" and gives "4 linked sockets even below item level 25", and the 3.29.0 notes list Binding among the orbs whose added sockets are white. The owner's play outranks them for the count; a short confirmation is on #182. Nothing here changes if it is confirmed.
- **In the state**: the compressed state keeps a `bound` flag only when the target names sockets and Binding is enabled (ADR-0045). The start item's sockets are a constant, so the flag selects one of two finish values: the item as it began, or as Binding leaves it.

## The Black Mórrígan recipes

The owner offered both recipes. Each consumes The Black Mórrígan and one more beast, bought on the trade site and priced from the beast listings (price file names for the three beasts, as B3 prices imprint beasts, ADR-0034):

- **Craicic Shield Crab**: the item gets **the maximum sockets its type allows** (owner: body armour and two-handers 6, shields 3, and so on), ignoring the item-level gate, which is the class maximum of ADR-0046. Old sockets keep colours and links, the new ones are white and unlinked.
- **Craicic Sand Spitter**: the item gets **the maximum sockets its type allows, all linked**: the owner's words are "'maximum' means the maximum sockets the item type allows ... all linked for the link recipe", read literally. The narrower reading (link only the sockets the item has) is noted on #182 and changes only the Sand Spitter's value; the planner uses the literal reading.

Both are deterministic finish actions, refused on a corrupted item, and each marked `approximate` (no source but the owner's answer; the research found the recipes unverified). They can follow any other finish action. Saqawine Rhoa and Saqawine Vulture are out (they create a random rare, like the unique-item beasts).

## Why the recipes do not need a measurement

The standing rule is that a design never asks for a check mid-plan. The recipes get the owner's reading of "maximum", the planner prices them, and the beasts' purchase is part of the price. A line on #182 asks for a confirmation when the owner has the beasts; the plan does not wait for it.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 3c and 4); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99); ADR-0030, ADR-0034, ADR-0045, ADR-0046.
