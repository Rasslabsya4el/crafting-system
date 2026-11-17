# The bound's build makes an erasing action's kernel from the alike twin

Ticket [#1146](https://github.com/Rasslabsya4el/crafting-system/issues/1146) (re-cut on 2026-11-17 by the dispatcher's decision A). Rules: OR-10, OR-12, OR-13, OR-14, OR-16. Builds on the crafted pattern of `abstraction/_pattern.py` (#497, its module text) and on the erasing view of `Abstraction._erases` (#827).

## The problem

When every method is on, one enabled action reads the junk (a bench craft, an Exalted Orb, a swap), so `Kinds` tells apart, on every state, every family any enabled action names. The outcome of a draw that erases the junk (a Chaos Orb, an essence, a Harvest reforge, a Veiled Chaos Orb) then holds one state for each set of junk it can roll. Measured on the server (`Budget.in_states`, one process, load 6 to 13; probes in `.claude/scratch/t1146/`):

| route | N | the bound's build until the search starts | fine kernels made | largest erasing kernels (outcomes) |
|---|---|---|---|---|
| R05 | 10,000 | 167 s, 2.1 GB | 294,270 | Harvest Reforge 322,025; essences 162k to 553k; Veiled Chaos Orb 718,936 |
| R12 | 10,000 | 172 s, 3.1 GB | 233,605 | Harvest Reforge 315,961; essences 315k to 322k; Veiled Chaos Orb 1,123,061 |
| R05, R12 | 1,000,000 | not done after 30 minutes (killed), 7.6 to 9.2 GB | | |

These kernels are made by the pattern bound's build (`PatternBuilder._offers_of_key`), before any search: each is made at full junk detail and then pushed onto the pattern keys, which do not read the junk's families. A cProfile of R05's build at N = 10,000 puts 46 s of 475 s in the kernels (34 s in the erasing draws) and 59 s in noting and keying their 3.1 million outcomes.

## What was tried first, and why it is not this

Session 1 designed a free "look" pseudo-action in the search: an erasing draw's outcome a coarse state, the fine outcomes revealed by a free step. It saves a state only where the readers' bound at the coarse key is above the erasing action's. Measured at N = 10,000 on R05 and R12 at the start's two cheapest erasing draws: the bound is flat at 5.0 on every key the build finished; the cheapest reader (a bench craft) is at 5.01 to 5.04, the cheapest erasing action (the restart) at 6.0 to 7.2: the readers are cheaper on 100% of the mass, and the look would be taken everywhere. That design waits for a sharper reader bound, [#1169](https://github.com/Rasslabsya4el/crafting-system/issues/1169). Lumping junk in a way the answer would have to call approximate is not taken (OR-14: exact among realistic routes).

## Decision

In the bound's build, the kernel of an action that erases the ordinary slots of a member (`Abstraction._erases`: it reads no junk and no lock keeps a side) is made by the **alike twin** (`Abstraction.alike_twin`), and pushed onto the keys as before. The twin is the same abstraction (goal, item, enabled actions, readings, the numbers of the family types) whose drawn and held ordinary slots are told apart by side and by the protected tags alone (`Kinds.slot_kind`: `ALIKE`, with the tags under the metamods). A veiled placeholder and a mod unveiled from the pool keep their own kind (the key holds them exactly); a fractured mod keeps the kind it has in the fine abstraction. Its outcomes are never noted in the slot universe. `LUMP_ERASING` in `_pattern.py` switches it (on).

## Why the bound stays a lower bound (OR-12)

The build's value at a key is at most the exact value V* of each member (the module text of `_pattern.py`). The twin changes only the kernel of an erasing action at a member, and the build reads of that kernel only its push onto keys and, before this, the slots it taught the universe.

1. **The push is the same.** An erasing action's kernel reads the view of the member without its ordinary slots (`_view`, #827), which the twin builds from the same member. Its outcomes are items the same action left; the twin compresses each with the same flags, fractured mods, status (what each slot gives the goal: the contribution, not the kind), item state, crafted and veiled slots, and with ordinary slots that differ from the fine ones only in kind. `Pattern.key` reads of an ordinary slot its side and, with the tags, its protected tags: the kinds of both carry the same ones. So each fine outcome and the twin outcome its labels merge into fall on one key, and the chances of a key add up the same. Checked at every member of a random walk of the bow world (`tests/test_pattern_lumped.py`, the metamods, a lock, essences, Harvest reforges, tags on and off).
2. **The members are the same.** A key's members are made from the key and the slot universe (`Pattern.members`), never from the outcomes that reached it. So a key reached only through lumped outcomes has the members it would have had.
3. **The universe is the same.** The universe is the item's pool, each mod at every contribution its roll law can give (`_rolled_contributions`), and every mod an offered action adds by name (`_Universe._seed_named`). An erasing draw puts on the item a pool mod or a mod it adds by name, so before this change its outcomes taught the universe nothing it lacked: noting them was a safety net. To keep that true without the net, a mod added by name is now seeded at every contribution its roll law can give, as a pool mod is (before: at its low roll only). That an erasing draw's fine outcomes teach the seeded universe nothing is checked on the bow world (`tests/test_pattern_lumped.py`, the build without the twin: no erasing kernel grows the universe); a key with no member at all still makes the build refuse (`_no_member`), as before. A later offer that joins grows the universe through its names and begins the keys again (`PatternBuilder.extend`), as before.

With 1 to 3, the model built with the twin is the model built without it: the same keys, rows and values. `tests/test_pattern_lumped.py` checks this on the bow world (a plain start and a lock start, tags on and off), checks the bound at or below V* at every state of the exact graph, and plans the coarse world through the planner's entry on a count of states with and without the twin: the same plan, mean and lower figure.

## What it guarantees, and what it does not change (OR-13, OR-16)

Nothing of the answer changes: the bound is the same number, so no cut needs a new sentence (OR-13). The search still makes the fine kernel of an erasing draw it takes (its states are the plan's), so the route page is unchanged (OR-16). The change is the build's time and memory (OR-10: the build no longer keeps junk detail that no key reads).

## What it does not solve

At N = 10,000 the build's largest cost on R05 is not the erasing draws: 336 s of the profiled 475 s are `Abstraction.kernel_key` of the readers at each member (about a million calls, each building an item). That is a separate root; see the issue filed from this ticket's PR. The search's own first draw at small N (the ticket's old title) is cut by `_counted_kernel` as before (#1105).
