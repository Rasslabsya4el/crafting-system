# The Lock previews the currencies a source or the owner names; everything else is applied blind

The Lock puts an item into a foreseeing state (ADR-0054). Which currencies show a preview, what the Lock refuses, and what ends the foresight are mechanics, decided here by the evidence rule (ADR-0005, ADR-0028) from the [research](../research/2026-10-31-hinekora-lock.md) and the owner's play ([Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106), answers 3a to 3d, 2026-11-01).

## Which currencies preview

Each action kind declares `previewable`: `named` (a source names it), `by_item_text` (only the Lock's own text covers it, marked `approximate`) or `no`. The default is `no`, so a new action stays blind until a claim says otherwise.

| Currency item | `previewable` | Source |
|---|---|---|
| Chaos Orb | named | wiki: "any given Chaos Orb" shows the same preview each time |
| Divine Orb | named | wiki; a 2023 player report (note 3.1). It becomes an option once the Divine action exists ([#71](https://github.com/Rasslabsya4el/crafting-system/issues/71)); a preview then reads "passes the roll requirement or not" |
| Tailoring Orb | named | wiki. B7 prices the enchant orbs through a finish cost and never offers them as search steps (ADR-0050), so in v1 it is no option; a Lock would preview it, so this errs low |
| Exalted Orb, Orb of Annulment, Regal Orb | named | owner, from play: the Lock does preview them (the research had them by item text only) |
| Orb of Transmutation, Alteration, Augmentation, Alchemy, Scouring | by_item_text, `approximate` | the Lock's item text, "the next Currency item" (PoEDB); no source names these five |

Everything else is applied **blind**: it is still available on a locked item, and using it ends the foresight, but its preview is not an option. That is: essences and fossils in a resonator (the owner does not know; the Craft of Exile code and data in `sources/raw/coe` have no Lock, so the emulator cannot check it, and the question is on the owner's list, [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)); catalysts and quality currency; the Tempering Orb and the Harvest quality enchants (ADR-0050, ADR-0052); Eldritch Ichor and Ember; the Orb of Conflict; Veiled orbs; influenced Exalted Orbs; the Orb of Dominance; the Blessed Orb; socket, link and colour orbs; every Harvest, bench, beast, recombinator and imprint craft and the Locus of Corruption (wiki: not previewed, R7); and any use with an Omen active. The **Vaal Orb** is B4's: it was previewed in 3.22 and 3.29 is not stated; B8 offers none, and B4's design sets the declaration for it.

Blind is the cautious default. A currency treated as blind gives the planner one option fewer than the player really has, so the Lock's value is never overstated by it. A finding on #182 switches one kind with a claim edit and no change to the model (ADR-0024).

**One option per currency item.** All currency items of one type show the same preview, so each kind declares the `currency_item` it is (a price-file name), and a state has one option per item. Of two offers that use one item (an Annulment and another Annulment with a different parameter), only the cheaper is an option.

## What the Lock refuses, and what ends it

- It is refused on corrupted, mirrored and unmodifiable items (wiki); gems are out of v1 ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)).
- **A second Lock on an item already under a Lock is not possible** (owner, 3c). The foreseeing flag is never stored (ADR-0054), so no state is foreseeing, and the Lock is offered only where the flag is off: the rule holds by construction.
- **The Lock is used up when it is applied** (owner, 3d), as a currency is; a relock pays a second Lock (ADR-0056).
- Any modification of the item ends the foresight: a currency, a bench craft, Harvest, a recombinator, a beast craft, an imprint, an anoint, and the currencies that change quality, sockets, links or implicits. Looking does not. Incubators are not an action in any batch.

## What B8 leaves out, and which way each errs

Each of these lowers the Lock's value, so a plan never overstates it:

- **The Awakener's Orb is not an option.** The wiki says its preview depends on the donor. A donor must be owned before the player can look, and he keeps it when he declines, so the option has an acquisition cost paid before the look and kept after it, which the Peek backup does not hold. It waits for the donor state of B3 (ADR-0032) and a later ADR.
- **A start item is never foreseeing.** A bought item that arrives locked counts as unlocked.
- **The Lock costs its market price.** The beast recipe that locks a magic item (a Craicic Croaker and a Black Mórrígan), a drop and the divination cards have no price in any source, so they are not modelled.
- **No Sacred Orb action** (base defence rolls are out of v1).

The one thing modelled that could raise the Lock's value wrongly is the five `by_item_text` previews; every answer that takes a Lock step lists them (ADR-0057).

Origin: [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) (owner's answers 3a to 3d; the round draft); [Hinekora's Lock in 3.29](../research/2026-10-31-hinekora-lock.md) sections 3 and 7; ADR-0004, ADR-0005, ADR-0028.
