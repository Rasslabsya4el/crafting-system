# The item stores its sockets, a target may ask for them, and actions declare them

Until B6 an item has no sockets. B6's actions work on a socket count, link groups and socket colours, so this amends the limits of ADR-0024 and the item of ADR-0027, as ADR-0027 did for implicits and quality. [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) decided the owner-visible parts; the rest is the main chat's.

## What `Item` stores

- **Sockets**: one colour per socket (white, red, green or blue) in socket order, and the link groups as their sizes in the same order (`(3, 2, 1)` is sockets 1 to 3 linked, 4 and 5 linked, 6 alone). Fusing links by sequential group sizes from the first socket (ADR-0047), so groups are contiguous runs.
- **Quality of a weapon or armour** (ADR-0049), beside the catalyst quality of jewellery (ADR-0027 amended).

An item built before B6 has no sockets and behaves as it did. When a target names sockets, a **start item that states none** is taken to have one white, unlinked socket (no socket is created for a target without sockets): a pessimistic default that costs at most a few orbs, since the Jeweller's Orb rerolls the count anyway; the report says so. A start item may state sockets, links, colours and quality.

## The class maximum and the item-level gate

The most sockets an item can have is the minimum of its **class maximum** and, for the Jeweller's Orb, the **item-level gate**:

- class maximum (wiki, "Item socket", checked 2026-11-01): body armour, two-handed weapons, bows and staves 6; helmets, gloves, boots 4; one-handed weapons and shields 3. The exception the wiki names inside the 20 classes of the bench data is the Gnarled Branch (a staff base with 3). The wiki adds that other low-level bases with a smaller inventory size have exceptions without naming them; the class table is the default and is marked `approximate` for that reason. Path of Building's `socketLimit` (the prototype, ADR-0016) is a test oracle, not a source: every base where it differs is reported in the S1 pull request as a finding and changes nothing silently;
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

Buy specs gain socket and link filters, so "buy a 5-link or 6-link base" competes with "finish by orbs" through the acquisition cost (ADR-0011). It is its own later slice (S9); the trade query layer reports sockets as not covered today.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 1, 3a, 4; draft decisions); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99); ADR-0008, ADR-0011, ADR-0016, ADR-0024, ADR-0027, ADR-0045.

## Amendment: the build of the item and the target ([#227](https://github.com/Rasslabsya4el/crafting-system/issues/227))

`Item.sockets` is `Sockets(colours, links)` or None (`items/sockets.py`; `SocketError` is an `ItemError`). `Item.validate` refuses sockets on a class outside the table and a count above the class maximum, naming the maximum; it does not apply the item-level gate, which is the Jeweller's Orb's rule (S2). The class maximum is the claim `sockets.class_maximum_sockets`, `approximate`, with a `by_class` value for the 20 bench classes and a `by_base` exception for the Gnarled Branch; Path of Building's `socketLimit` is compared with it base by base in `tests/test_items_sockets_pob.py` (no differences in the five classes the prototype extracted; the weapon classes and shields have no oracle there).

The target parser refuses a socket target on jewellery and on a class with no table, links above count, colours above links (or above count when no links are given), any of the three above the class maximum (naming it), a corrupted **start item** and an Abyssal-socket item (a start mod or implicit, the base's own implicit, or a requirement that selects an Abyssal-socket mod; recognised by the stat `local_has_X_abyss_sockets`). A target whose *goal* is corrupted (`allow_corrupted`, a corrupted implicit) with sockets is not refused here: corruption is the last step (ADR-0036) and the Vaal Orb's socket outcomes are batch B4's ([#267](https://github.com/Rasslabsya4el/crafting-system/issues/267)). `Target.start_sockets_assumed` records that the one white socket was assumed, so the report (S7) can say so. The planner refuses a target with sockets until S5 (`PlanError`).

## Amendment: the declaration and the actions ([#228](https://github.com/Rasslabsya4el/crafting-system/issues/228))

`Reads` and `Adds` gain three flags each, `socket_count`, `socket_links` and `socket_colours`, with the properties `sockets` on both. A part is **read** when the result (its chances, whether the game refuses the item, or another part of the sockets) depends on it; carrying a part over unchanged to the same place is not reading it, so a Jeweller's Orb that keeps the colours and links of the sockets that stay reads the count only. An action that declares nothing reads and sets all three (`Action.reads` and `Action.adds`), as it does for the other parts of the item. A change of the count changes the links and the colours, so `Adds(socket_count=True)` without the other two is a `ValueError`. `Adds.socket_action(count=, links=, colours=)` builds the declaration of an action that adds no mod and draws none (`only_sockets`). Like the enchantment (ADR-0050) the sockets are **not** part of `item_state`: the compressed state of the mods does not hold them, so declaring them changes no number of states and no offer.

The contract suite (`contract_support.check_socket_declarations`) checks, on every fixture item that holds sockets: a result differs from the item in the count, the links or the colours only where `adds` says so; an action declared with `socket_action` changes no mod and nothing but the sockets, and every result compresses to the state of the item (so the kernel is not compared with the brute force: the rebuilt item has no sockets for the action to change); and an action that does not declare `reads.socket_links` or `reads.socket_colours` gives the same result on the item with that part taken off (all unlinked, all white), the results compared with that part taken off too. `reads.socket_count` is not checked, since a count cannot be taken off. The check found one kind that changes sockets without saying so: the recombinator builds its result from one of its two inputs, so it now declares the three flags.

The actions are `JewellersOrb`, `OrbOfFusing`, `BenchSocketCount` and `BenchSocketLinks` (`actions/socket_orbs.py`); the Omens are the field `omen=True` of the orb they work with, priced as the orb plus the Omen. They are kinds outside the planner until S5 (#231) attaches the finish. An item that states no sockets is `OutOfScopeError` (the one white socket is assumed by the target), a class with no socket table or a corrupted item `NotApplicableError`, an Abyssal-socket mod `OutOfScopeError`. A bench count or link craft that would leave the item as it is is refused (`NotApplicableError`): nothing says the game allows it, and a loop that changes nothing has no place in a plan. A Jeweller's Orb is refused at the class maximum and at the item-level gate, and rolls down among the counts the gate allows when an item holds more sockets than it (sockets from the bench).
