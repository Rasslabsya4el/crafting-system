# The compressed state is design D, with exact merges only

The solver's compressed state keeps, for each target mod, an exact status: absent, present but below the required tier or roll, or present and passing. Junk is a multiset of family types: families that every enabled action treats alike are merged and counted, not identified. Exceptional families that no family type covers stay explicit. Flags carry rarity, fractured and crafted mods, metamods and influence. Transition kernels are cached by pool signature, so equal signatures share one kernel.

The reason is the trade-off measured in [state compression research](../research/2026-10-30-2-state-compression.md): tracking every blocked family by identity is exact but explodes (about 1 million core states at 10 families per side, 370 million at 40); counting junk by tag class is small but not exact, because two junk mods with the same tags can block different families and so change the pool differently. Design D is close to the class-count size and stays exact.

v1 allows only exact merges. An approximate merge is flagged, and its policy is checked on the concrete simulator with an error interval; approximate merges are built only if exact family types blow up the state (map [Crafting system v1](https://github.com/Rasslabsya4el/crafting-system/issues/1), "Not yet specified").

## Widening for B1 ([Compressed state for essence reforges and bench crafts](https://github.com/Rasslabsya4el/crafting-system/issues/59))

The non-fractured mods are kept as slots (side, kind, what the mod gives each requirement) once an enabled action reads them. The kind is a family type for the families that every enabled action treats alike, and the family itself where one does not: today only the bench, whose craft is refused when a family on the item clashes with its mod, so the families of the enabled crafts are told apart. With only the erasing rerolls (Chaos Orb, Harvest reforge, essence) enabled no slot is kept besides the crafted ones, and the state is as small as before. Crafted mods are always slots, by their canonical mod id. An action that adds or removes one mod will refine the family types by pool weight when it is added.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q8.
