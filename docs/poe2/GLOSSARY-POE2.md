# PoE2 crafting terms

The PoE2 section of the glossary, in the form of `GLOSSARY.md` (term, definition, `_Avoid_`). Only terms that are new in PoE2 or that mean something else than in PoE1; a term not listed here keeps its `GLOSSARY.md` meaning (Mod, Family, Mod type, Tier, Roll, Fractured mod). Facts are those of PoE2 0.5.5.10 (2026-11-24); each one is sourced in `docs/poe2/claims/` and `docs/poe2/research/`.

## Items and modifiers

**Modifier level**:
The `required_level` of a mod record: the lowest item level on which the mod can spawn. PoE2's Greater and Perfect orbs and Ancient bones set a lowest modifier level for the mod they add, so a draw can be limited from below as well as from above (by the item level).
_Avoid_: mod tier (as a synonym; the tier is the place in the ladder, the level is the number)

**Minimum modifier level**:
The lowest modifier level a tiered orb or a bone may add (`TieredCurrency.MinimumModLevel`, `AbyssBenchTicketTypes.MinimumModLevel`); a mod below it is out of that draw's pool.
_Avoid_: tier floor

**Tiered currency**:
A Greater (tier 2) or Perfect (tier 3) version of Transmutation, Augmentation, Regal, Exalted or Chaos. It does what the plain orb does with a minimum modifier level.
_Avoid_: upgraded orb

**Desecrated mod**:
A mod added by an abyss bone (or an essence of the Abyss) that stays hidden until it is revealed; the reveal offers a choice among drawn options. Its pool includes the mods of the three Abyssal lords (Amanamu, Kurgal, Ulaman) as well as ordinary mods.
_Avoid_: abyssal mod (an Abyss jewel socket in PoE1 is something else), veiled mod (PoE1)

**Unrevealed desecrated mod**:
The hidden state of a desecrated mod between the bone and the reveal; it takes a prefix or suffix slot.
_Avoid_: veiled mod

**Reveal**:
The choice step that turns an unrevealed desecrated mod into one mod chosen by the player among the options shown (the Well of Souls in the Abyss mechanic); the Omen of Abyssal Echoes allows one reroll of the options.
_Avoid_: unveil (PoE1)

**Sanctified item**:
An item whose mod values were changed by the Omen of Sanctification with a Divine Orb; it can no longer be modified. (Confirm the exact text in `docs/poe2/claims/omen.yaml`.)
_Avoid_: blessed item

**Augment**:
The game's word for everything that goes into an item's augment socket: runes, soul cores, talismans, idols (trade groups "Runes", "Soul Cores", "Idols").
_Avoid_: gem (PoE2 gems do not go into gear), socketable (the dat tables' word, fine in code only)

**Augment socket**:
A socket on a martial weapon, wand, staff or armour that holds one augment; the Artificer's Orb adds one, corruption may add one.
_Avoid_: rune socket

**Rune**:
An augment with a fixed stat per item category (martial weapon, wand or staff, armour), in Lesser, plain, Greater and Perfect grades and named variants.

**Soul core**:
An augment from the Vaal (Incursion) mechanic; Atziri's and Jiquani's named cores have special effects. The Core Destabiliser changes a soul core.

**Idol**:
An augment from the Ritual mechanic (trade group "Idols"); effects per slot (shield, buckler, sceptre, ...).

**Corruption enchantment**:
The implicit-like line a Vaal Orb outcome adds to an item; the Orbs of Sacrifice upgrade it and remove a random mod.
_Avoid_: corrupted implicit (PoE1 word), enchant (Tempering/Tailoring in PoE1)

**Omen**:
An item that, set active in the inventory, changes what the next matching currency does (which side it acts on, how many mods it adds, which mod it removes) and is consumed when triggered. It is a modifier of the next action, not an action of its own.
_Avoid_: metamod (PoE1's bench mods that act alike)

## Methods and places

**Reforging bench**:
The bench that takes three items and gives one item of the same kind (or class); no PoE1 counterpart in the planner.
_Avoid_: vendor recipe

**Salvage bench**:
The bench that breaks an item with quality or sockets into quality currency or Artificer's shards.

**Temple bench**:
A crafting room of the Temple of Atziri (Incursion in PoE2, table `Incursion2Crafting`): the Corruption Instiller (Architect's Orb, a second corruption), the Gem Corrupter, the Soul Core Infuser, the Masterwork Forge (Vaal infusers: quality above the maximum), the Extraction Workbench, the Morphology Mechanism (Vaal Cultivation Orb) and the campaign workbenches.
_Avoid_: Incursion room (PoE1)

**Double corruption**:
Modifying an item that is already corrupted, with an Architect's Orb (equipment or jewel) or Crystallised Corruption (gem); the outcome may destroy the item.

**Recombinator** (PoE2):
The Expedition recombination of two items of a recombinable class into one, paid in Expedition artifacts (Black Scythe, Broken Circle, Order, Sun) per class (`RecombinableClasses`).
_Avoid_: PoE1's Sentinel recombinator (dust and gold)

**Verisium craft**:
The Runes of Aldur (Expedition 2) craft that turns a base into another base for an amount of Verisium (table `Expedition2VerisiumCrafts`).

**Currency Exchange**:
The in-game exchange of stackable items, with a gold fee per trade (`CurrencyExchange.GoldPurchaseFee`); a price source as well as a market.
