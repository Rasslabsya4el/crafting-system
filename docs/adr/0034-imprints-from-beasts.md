# Imprints come from beasts, are used up, and may be kept several to an item

An imprint stores the state of one item and restores it later. [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) takes the rules of [the research](https://github.com/Rasslabsya4el/crafting-system/issues/90) (section 7) and the owner's answers on the two points no source settles.

## Where an imprint comes from

**Beasts only.** The Eternal Orb has not dropped since 2.0.0 and can be bought only in Standard (3.28), which is out of v1, so the planner never offers it. Two beast recipes make an imprint (3.29):

- **Craicic Croaker**: an imprint of a **magic** item;
- **Fenumal Plagued Arachnid**: an imprint of a **rare Talisman** (it replaced the amulet-to-Talisman craft in 3.29.0).

A rare item that is not a Talisman cannot be imprinted. The beast is priced from the beast listings (the price file, ADR-0007), once per imprint made.

## What it restores, and when it is refused

- **Restores**: implicit and explicit mods, enchantments, quality amount and type, base defence values and Memory Strands; it works on influenced and eldritch-implicit items. It can undo an Awakener's Orb on the receiver (ADR-0032) but never brings back a donor.
- **Refused**: fractured items (an imprint made before a Fracturing Orb cannot undo it), corrupted and mirrored items.
- **Not restorable**: an item made from the original: a recombinator output, an Allflame copy, a split item. An imprint of an input does nothing for a recombination (ADR-0033).
- **Used up** when it restores (owner, answer 4b). **Several imprints of one item** can be kept, for example one from before a Regal Orb and one after it (owner, answer 4b). Both rest on 2014 player answers, unverified by the research, and on the owner; they are not marked `approximate` because the owner decided them, and an optional in-game check may change them.

## What this means for the planner

An imprint is a restore point: making it costs a beast, using it costs the imprint. R15 (a magic bow) and R17 (a rare Talisman) loop on it: imprint, annul down to the one wanted mod, restore on failure. Because it is used up, every restore needs a fresh imprint made at the state it returns to, and because several are allowed, the item may hold imprints of different states at once. How the compressed state keeps those snapshots, and how a restore is priced so that the cost of building the snapshot state is not charged twice, was a prototype ticket in the B3 chart (ADR-0013 spoke of "imprint as acquiring a copy"; paying a copy's full acquisition cost on every restore would double-count the item the imprint was made of). **Settled by [ADR-0060](0060-an-imprint-is-a-snapshot-held-in-the-item-state.md)**: the snapshots are held in the item's state, a restore is a move to one and costs nothing but the imprint, at most `max_imprints` (default 1; the model allows several) are kept.

Origin: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) (round 1 answer 4b; decisions list); [Awakener's Orb, recombinators and imprints in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/90); ADR-0011, ADR-0013, ADR-0022.
