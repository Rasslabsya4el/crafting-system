# The item stores its sockets, a target may ask for them, and actions declare them

Until B6 an item has no sockets. B6's actions work on a socket count, link groups and socket colours, so this amends the limits of ADR-0024 and the item of ADR-0027, as ADR-0027 did for implicits and quality. [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) decided the owner-visible parts; the rest is the main chat's.

## What `Item` stores

- **Sockets**: one colour per socket (white, red, green or blue) in socket order, and the link groups as their sizes in the same order (`(3, 2, 1)` is sockets 1 to 3 linked, 4 and 5 linked, 6 alone). Fusing links by sequential group sizes from the first socket (ADR-0047), so groups are contiguous runs.
- **Quality of a weapon or armour** (ADR-0049), beside the catalyst quality of jewellery (ADR-0027 amended).

An item built before B6 has no sockets and behaves as it did. A **start item that states no sockets** is taken to have one white, unlinked socket: a pessimistic default that costs at most a few orbs, since the Jeweller's Orb rerolls the count anyway; the report says so. A start item may state sockets, links, colours and quality.

## The class maximum and the item-level gate

The most sockets an item can have is the minimum of its **class maximum** and, for the Jeweller's Orb, the **item-level gate**:

- class maximum (wiki, "Item socket", checked 2026-11-01): body armour, two-handed weapons, bows and staves 6; helmets, gloves, boots 4; one-handed weapons and shields 3. The exception the wiki names inside the 20 classes of the bench data is the Gnarled Branch (a staff base with 3). The wiki adds that other low-level bases with a smaller inventory size have exceptions without naming them; Path of Building's `socketLimit` (the prototype, ADR-0016) is a test oracle, not a source, and every base where it differs from this table is listed in the S1 pull request for the main chat;
- item-level gate (wiki generation table): 3 sockets from item level 2, 4 from 25, 5 from 35, 6 from 50.

The bench and the two Black Mórrígan recipes ignore the item-level gate and respect the class maximum (bench: wiki, "ignoring item level restrictions"; the beasts: the owner's answer, round 1 answer 4: "maximum" is what the item type allows). No target above the class maximum is reachable; a socket target beyond it is refused with the maximum named.

## What a socket change keeps

When a Jeweller's Orb, the bench count craft or the Shield Crab recipe **adds** sockets, the old sockets **keep their colours and links**; the new sockets are white and unlinked (owner, round 1 answer 3a; the white colour is official 3.29.0). When the new count is **lower**, the last sockets are removed and the first ones keep their colours; a link group is cut where the sockets end. The removal rule and the bench count craft's use of the owner's answer are the main chat's reading, marked `approximate`, and a check on the owner's in-game list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)). An Orb of Fusing changes only the link groups, a Chromatic Orb only the colours, and no other action changes sockets except Orb of Binding (ADR-0048).

## The target form

`sockets: {count, links, colours: {R, G, B}}`, every key optional:

- `count`: at least this many sockets;
- `links`: a linked group of at least this many sockets;
- `colours`: at least this many red, green and blue sockets, **counted in one linked group of at least `links` sockets** when `links` is given, over the whole item otherwise. With `links` given, the colours must add up to at most `links`, and `links` to at most `count` when that is given; the parser says which key is wrong.

"A group of at least `links`" and not "the largest group" so that a three-linked target on six sockets with two three-linked groups reads as a player reads it. There is no "k non-white sockets of any colour" target: since 3.29 a gem in a socket of another colour loses nothing and gains no bonus, so only a named colour matters.

A target that names `quality` on a weapon or armour (ADR-0049) is the same form as ADR-0029's, without a type.

## What actions declare

`Reads` and `Adds` (ADR-0024) gain a sockets declaration, in the way ADR-0027 added implicits and quality: an action says whether it reads the count, the links or the colours, and what it sets. An action that declares nothing still reads everything and sets nothing it did not declare, so a new action stays correct by default. The contract suite checks on its fixtures that an action that does not declare sockets leaves them unchanged and that no socket action changes mods.

## Corrupted, Abyssal and unsupported items

A socket action on a corrupted item is refused (the Tainted orbs and the bench crafts that cost Vaal Orbs are B4's). A socket target on an item with an Abyssal-socket mod, or on jewellery, is refused as out of scope. A start item that already meets the socket target adds no finish cost.

## Buying a base with sockets

Buy specs gain socket and link filters, so "buy a 5-link or 6-link base" competes with "finish by orbs" through the acquisition cost (ADR-0011). It is its own later slice (S7); the trade query layer reports sockets as not covered today.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 1, 3a, 4; draft decisions); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99); ADR-0008, ADR-0011, ADR-0016, ADR-0024, ADR-0027, ADR-0045.
