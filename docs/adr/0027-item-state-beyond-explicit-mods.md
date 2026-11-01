# The item stores implicits, quality and the unveil offer, and actions declare them

Until B2 an action read and wrote explicit mods, the influence set and the corrupted flag. B2's actions work on three more things: the implicits (an Eldritch Ember adds one; a Blessed Orb rerolls the values of the implicits), the catalyst quality (ADR-0029) and the offer a veiled placeholder has drawn (ADR-0026). This amends the limits of ADR-0024 and the item of ADR-0009. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) decided it.

## What `Item` stores

- **Implicits with their values**: the base's implicit mods, the Eldritch implicits of ADR-0025 (the grade follows from the mod), each with the rolled values. A range of a base implicit is read from the game data; a Blessed Orb rerolls inside it.
- **Quality**: the catalyst type and the percent, or none.
- **The unveil offer**: for each veiled placeholder, the offer once drawn, or none.

An item built before B2 has none of the three and behaves as it did.

**Amendment (grill B7):** `Item` stores a fourth thing, the **enchantment**: a mod id (a Tempering or Tailoring pool enchant, a Harvest quality enchant or the extra crafted slot) or none ([ADR-0050](0050-enchantments-as-a-finish-step.md)). `Reads` and `Adds` gain an `enchantment` declaration like the other three, but no action of B1 to B4 reads it, so the compressed state never keeps it; the limit of crafted mods reads the start item's enchantment as a problem constant (ADR-0053). An item built before B7 has none. The explicit mods, the influence set and the corrupted flag are unchanged.

## What actions declare

`Reads` and `Adds` (ADR-0024) gain the matching declarations, so the compressed state keeps a field only when an enabled action reads it:

- `Reads` can name the implicits (Conflict reads both grades, the Eldritch orbs read the dominant side, a Blessed Orb reads the implicit values when a requirement asks for one), the quality, or the offer;
- `Adds` can name an implicit that is added, a quality that is set, an offer that is drawn.

An action that declares nothing still reads everything, so a new action stays correct by default. This lifts, for implicits, quality and the offer, the limit of ADR-0024 that an in-place value change has no place in the contract; **explicit-mod value changes (a Divine-like orb) remain the business of [#71](https://github.com/Rasslabsya4el/crafting-system/issues/71)**.

## Blessed Orb

A Blessed Orb rerolls the value of each implicit that has a range, uniformly inside the range. **The previous value can roll again** (the owner's answer, round 1; it agrees with Craft of Exile and goes against the wiki's exclusion). It refuses corrupted items and items without a ranged implicit. The wiki lets it be used on an item with Eldritch implicits but does not say what it does to them; until a claim admits that effect (main chat, not recorded in the grill), a Blessed Orb on such an item is not offered (ADR-0004: what no admitted rule answers is invisible to the solver). The catalyst scaling of ADR-0029 applies on top of the rolled base value.

## Requirements on values

A requirement on a roll (ADR-0008) compares the **base roll**, the integer the item stores. With a catalyst quality the displayed value is the base roll scaled and rounded down (ADR-0029), so a requirement written in displayed values is turned into the smallest base roll that shows it.

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decision list of 2026-10-31, owner round 1 on Blessed); [Blessed Orb, catalysts and Orb of Chance](https://github.com/Rasslabsya4el/crafting-system/issues/89); ADR-0009, ADR-0024.

## Amendment: the declarations and the compressed state ([#142](https://github.com/Rasslabsya4el/crafting-system/issues/142))

**`Reads` and `Adds`** each gain three flags, `implicits`, `quality` and `offer`, False in the dataclass (the action leaves the part alone) and True in what `Action.reads` and `Action.adds` return for an action that declares nothing, as it reads every mod: a new action stays correct by default. `item_state` says whether any of the three is set. An action that reads the offer reads the veiled placeholder, which is a mod, so it also reads the junk (`Abstraction` refuses one that does not).

**`CompressedState` gains `implicits`, `quality` and `offer`**, each empty unless an enabled action reads or changes that part (`Abstraction.tracks_implicits`, `tracks_quality`, `tracks_offer`; the goal asking for an Eldritch implicit also makes the state keep the pair). A state that keeps none of them is the state B1 always had, down to its `repr`, so B1's kernels, offers and goldens do not move.

- `implicits` is the Eldritch pair, the Searing Exarch side and then the Eater of Worlds side, each `ImplicitSide(grade, contribution)`: the grade (0 for none, 1 to 6) and what the implicit gives each Eldritch implicit the goal wants (`Goal.implicits`, `ImplicitWanted`). The family is not kept (ADR-0025): a mod stands for its side and grade by the smallest id that gives the same contribution, at its lowest values. Dominance is derived, never stored. A goal built from a target does not read `Target.implicits` yet.
- `quality` is the catalyst `Quality` as the item stores it (at most 12 types by 21 percents).
- `offer` holds the mods of the unveil offer, each `OfferedMod(canonical id, contribution)`, the id being the smallest among the unveiled mods of its families and side that give the goal the same and can spawn on the base. The placeholder is an ordinary slot of the state.

The item rebuild gives an action the implicits, quality and offer a state stands for, and the split reads them back from the retained item of each part. An action that erases the junk erases the placeholder, so it is given no offer. The pilot count and the family-group level key their memos on all three, so states that differ in them are never merged.

Not modelled here, and refused with `OutOfScopeError` naming the ticket that lifts it: a base implicit (grade 0) on an item whose state keeps the pair, and a roll limit on an implicit ([#158](https://github.com/Rasslabsya4el/crafting-system/issues/158)). Dominance-limited actions are [#152](https://github.com/Rasslabsya4el/crafting-system/issues/152); the placeholder, the offer state and the Pick actions are [#145](https://github.com/Rasslabsya4el/crafting-system/issues/145).

## Amendment: sockets and the quality of weapons and armour ([Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), 2026-11-01)

`Item` also stores its **sockets** (a colour per socket and the link groups, ADR-0046) and its **quality** has two kinds: the catalyst type and percent of jewellery, or the plain percent of a weapon or armour (ADR-0049); no item class has both. `Reads` and `Adds` gain a sockets declaration in the same way: an action declares whether it reads the count, links or colours and what it sets, and an action that declares nothing still reads everything and sets nothing it did not declare. The quality declaration now covers both kinds.

## Amendment: corrupted implicit requirements ([Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95), ADR-0036)

An `implicits:` entry may carry `corrupted: true`. Its selector is then resolved among the corrupted mods of the base's item class that can occur at the target's item level (ADR-0037's pool), and only among them; without the key a selector never sees corrupted mods. A requirement on its roll is a base roll as before. The target also gains the top-level key `allow_corrupted: true` (ADR-0036). Neither changes `Item` or the compressed state: a corrupted item is final, so the corrupted implicit is judged inside the kernel of the corrupting action and never held by a state the solver continues from. The Blessed Orb still refuses corrupted items (above).
