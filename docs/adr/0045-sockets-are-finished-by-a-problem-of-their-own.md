# The sockets of an item are finished by a problem of their own

Sockets, links and socket colours are the owner's target from v1 ([grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), round 1 answer 1): a target may ask for a socket count, a linked group and named colours in it. No mod action of B1 to B3 changes sockets, and no socket action changes mods, so the two problems do not mix. This generalises ADR-0029 (catalysts as a finishing step) from a closed-form cost to a small decision problem. The mechanics are in [the sockets research](https://github.com/Rasslabsya4el/crafting-system/issues/99).

## What B6 contains

- **Actions**: Jeweller's Orb, Orb of Fusing, Chromatic Orb; the 13 socket bench crafts (count 2 to 6, links 2 to 6, "at least 2, 3 or 4 non-white"); Omen of the Jeweller, Omen of Connections, Omen of Trichromatism; Orb of Binding and the two Black Mórrígan recipes (ADR-0048); Blacksmith's Whetstone and Armourer's Scrap (ADR-0049).
- **Out of B6**: the Tainted socket orbs and the bench crafts on corrupted items (B4, [#29](https://github.com/Rasslabsya4el/crafting-system/issues/29)); Vaal and Locus colour outcomes (B4); Saqawine Rhoa and Saqawine Vulture (they create a random rare, like the unique-item beasts left out in ADR-0030); jewellery sockets (the Unset Ring's one socket cannot change); items that hold an Abyssal-socket mod (a socket target on such an item is refused as out of scope: only the 3.29.2 fix is sourced, nothing says how an Abyssal socket counts toward the total).

## The finish is solved on its own state

The finish starts from the sockets the goal state's item has and ends when the target's socket requirement holds. It does not depend on the mods. So the planner solves the mod problem to its goal states and adds the finish value to each goal state, as ADR-0029 adds the catalyst cost: a restart that buys a new base pays the finish only for the finished item, and doing sockets last is the cheapest order for the mean because a restart throws away socket work done before it. A target that names no sockets has no finish, adds nothing to the compressed state and changes no answer (the one-socket default of ADR-0046 is created only when a target names sockets).

**It is not a fixed chain.** The three socket actions do not commute: each rerolls one thing (count, links or colours) without reading the others, but the colour requirement is counted in a linked group, so which sockets the group lands on matters. On a four-socket item that must hold a three-linked group with one red, green and blue socket, "colours first, then links until the group falls on the coloured sockets" costs 44.6 orbs (the optimal policy, which may mix the actions) against 103.0 for "links first, then colours" at equal prices (a throwaway computation at design time on four-socket items, 2,048 states, with the repeat exclusion of ADR-0047 and Siveran's forced-colour weights: the two agree in the tested cases where the group is the whole item, and are 2.3 times apart for a three-linked group and 2.7 times for a two-linked group, 64.5 against 174.0). So the finish is the exact problem over the item's count, link groups and colours, and the plan chooses the order.

## The finish state and its size

The state is the socket count (up to the class maximum, ADR-0046), the link groups as sizes in socket order, and one colour per socket. It is reduced to what the target reads:

- colours the target does not name merge with white; a target that names no colour has no colour in the state;
- when the colour requirement covers the whole item (a link group as large as the item, or no link requirement), positions drop out and only the linked or unlinked status and the capped colour counts remain;
- item level, class and quality are constants of the sub-problem (quality is compared at two levels, ADR-0049).

State counts over sockets 1 to 6: no named colour 63, one named colour 2,730, two 27,993, three 149,796. The Chromatic Orb has up to `k^n` outcomes (k = named colours + 1) and the Orb of Fusing up to 32, and neither reads the current colours or links except for the one excluded outcome of the Chromatic Orb (ADR-0047), so the dense product of states and outcomes (5 × 10^8 for six sockets and three named colours) is too large to hand to `solver.solve` as it is. **How the rerolls are encoded is a prototype ticket** (S4 in the B6 chart, the pattern of B3's prototype tickets): shared outcome tables with the excluded outcome as one correction, solved by `solver.solve` unchanged, or a dedicated routine in `abstraction` (which would amend ADR-0010). The ticket must reproduce the dense value iteration of the kernels on every case of up to four sockets and three named colours, and report the time and memory of the worst case. The throwaway check at design time solved every four-socket case by value iteration over aggregated tables, so the approach exists; it is not the product's code.

## Readings

Two inputs have a second reading (ADR-0047): the Jeweller's table (the wiki Developer table is the plan, the 2014 table the second number) and, only for a target that needs exactly one coloured socket, the colour of the Chromatic Orb's forced socket (Siveran's weights are the plan, the flatter reading of the data the second number). The finish is solved at the plan's readings; the other reading's number is the plan's policy evaluated at it (not a re-solve), as the recombinator interval of ADR-0012 does. The 215 against 223 Jeweller's Orbs from one to six sockets (both tables, item level 84, rechecked) keeps the interval under 4%.

## Orb of Binding is the one mod action that touches sockets

Binding turns a normal item rare as an Alchemy does and links the sockets the item has (ADR-0048). The compressed state keeps a `bound` flag, only when the target names sockets and Binding is enabled; the start item's sockets are a constant of the query, so there are exactly two finish values per target (with and without the flag) and a goal state adds the one its flag names. Without the flag the finish would overpay for links Binding gave for free.

## The report

The finish is its own sub-route on the route view and in the JSON, beside the mod route: its steps, odds, mean and p90. The total mean is the mean of the mods plus the finish. The mods and the finish are independent given the goal state, so the p90 of the total comes from the convolution of the two cost distributions (the `risk` work of [#190](https://github.com/Rasslabsya4el/crafting-system/issues/190)). The approximate inputs the finish reads are named as ADR-0028 asks, with the second readings beside the numbers they change.

## Verification

Layer 1 (ADR-0019): the finish kernels equal brute force over every socket assignment of up to four sockets. Layer 2: the simulator draws the finish from the claims and its mean lies within five standard errors of the solver's value. Layer 3: the finish value equals the dense value iteration. The route-level numbers are in ADR-0013's B6 amendment.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 1 and 2, standing rule); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99); ADR-0005, ADR-0010, ADR-0012, ADR-0019, ADR-0027, ADR-0028, ADR-0029.
