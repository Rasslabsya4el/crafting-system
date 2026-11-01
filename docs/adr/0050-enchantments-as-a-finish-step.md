# An enchantment is a finish step, chosen only when the target names it

An item holds **one enchantment** besides its implicits and explicit mods, and a new one replaces the old (claim `enchantment.one_slot_new_replaces_old`). Three methods put one there: the Tempering Orb (a weapon), the Tailoring Orb (a body armour) and the Harvest quality enchants ([the research](https://github.com/Rasslabsya4el/crafting-system/issues/100)). [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) decides how the planner uses them. The pools and weights are ADR-0051, the Harvest enchants and the quality line ADR-0052, the extra crafted slot ADR-0053.

## What is stored

- `Item` gains one field, `enchantment`: a mod id or none (ADR-0027 pattern). An item built before B7 has none and behaves as before. The values of an enchant are fixed, so there is no roll to store.
- The enchantment is **out of the compressed state**. No action of B1 to B4 reads it or removes it (the bench removes it for 3 Orbs of Scouring, claim `enchantment.bench_removes_for_three_scouring`, and the planner never needs that, since clicking again replaces for free), so nothing a policy does earlier changes what an enchant step costs later. It is a **finish step**, like the catalyst (ADR-0029).
- The one enchant that changes other actions is the extra crafted slot. It raises the bench's crafted-mod limit, so the limit of crafted mods reads it as a constant of the problem taken from the start item, not as a state field (ADR-0053).

## The target form

```yaml
enchantment:
  any_of: [<stat text or mod id>, ...]
```

The list names the enchants that satisfy the target. An entry is a Tempering/Tailoring pool enchant (ADR-0051), a Harvest quality enchant (ADR-0052) or, for a start item only, the extra crafted slot (ADR-0053). The planner **never adds an enchantment the target does not name** (owner, grill B7, answer 3): a target without `enchantment:` has no finish cost, and a start item's enchantment is kept and left alone. The enchant that would make a roll requirement cheaper (a Life enchant under "Life at least 100") is not searched for; the owner writes it into the target if they want it.

- An entry that matches a pool enchant with a **socket rider** (no colour, All Sockets Linked, -3 maximum sockets) or a **downside** (less of another tag, higher attribute requirements) is accepted only when it is listed by its own text or id. A tag name alone (`Life`) stands for the **clean** enchants of that tag: a positive magnitude on the tag, no socket rider and no downside; a hybrid of two positive tags and a requirement reduction stay in (the set the research counted as "clean": 4 on body armour for Life).
- An item holds one enchantment, so only `any_of` exists. A target that lists two enchants as required together (`all_of`, two `enchantment:` keys) is refused with a message naming the rule, and a list that mixes kinds is read as alternatives. A target that asks for the extra crafted slot on a start item without it is refused with the message of ADR-0053.

## The actions

Two new kinds, `tempering` and `tailoring`, live in `actions/enchant.py` (one file, ADR-0024); the Harvest quality enchants are in `actions/harvest_quality.py` (ADR-0052). An orb draws one enchant from its pool with replacement; the planner does not search over the orbs as steps, it prices them through the finish cost below.

## The finish cost

For a target with an acceptable set `S` the planner adds to the value of a goal state:

- **0** when the start item already holds an enchant of `S`;
- otherwise the cheaper of
  - the **orb route**: click until the draw lands in `S`. The draw is with replacement and each click replaces the old enchant, so the expected number of orbs is exactly `1 / P(S)`, where `P(S)` is the sum of the weights of `S` over the sum of the pool's weights (ADR-0051); the cost is that times the orb's price;
  - the **Harvest route**: the cheapest quality enchant in `S`, its Lifeforce priced from the price file, plus the expected cost of the quality line that enchant needs (ADR-0052: one number, fixed by the item level and the prices).

Mixing the two never beats the cheaper alone, because a click gives no information that would make buying one worth it. The quality line sits on the Harvest side so that the comparison is not biased towards it; it adds one constant and is no search. Like the catalyst finish, the cost is added at every goal state, so a restart that buys a new base pays it again (ADR-0029). The orb's price and the Lifeforce price come from the price file (ADR-0011's prices layer); an enchant route with a missing price is refused with a message that names it. Nothing here asks the owner for a price: the price layer's source decides (#13).

The planner ends the search at the goal state without the enchant, as with the catalyst. The finish cost is a function of the item class, `S` and the prices, so it cannot change which explicit-mod route is cheapest, except through the restart.

## Where the step stands in a plan

The report prints the enchant step **after the last step that changes mods and before any step that touches sockets or corrupts**:

- the pool enchants with a socket stat reforge the sockets and break the links (claim `enchantment.socket_stat_enchant_reforges_sockets`), so sockets are set after the enchant; B6 ([#104](https://github.com/Rasslabsya4el/crafting-system/issues/104)) takes this as an input;
- the orbs refuse a corrupted item (ADR-0004: no admitted rule says they work there), and corrupting does not remove an enchant (claim `enchantment.mirrored_and_corruption`), so a route that corrupts clicks first.

The step does not spend Memory Strands (claim `enchantment.tailoring_orb_leaves_memory_strands`), which B5 ([#103](https://github.com/Rasslabsya4el/crafting-system/issues/103)) is told, and the Tailoring Orb is a currency whose behaviour under Hinekora's Lock B8 ([#106](https://github.com/Rasslabsya4el/crafting-system/issues/106)) decides. B7 sets neither.

## Refusals

An enchant action is refused on a mirrored item, a corrupted item, an item of the wrong class (Tempering: the weapon classes the pool has; Tailoring: body armour; the class list is read from the game data by the build ticket), and for a Tailoring Orb an item with fixed sockets (a unique, so never a target). A refusal appears in the report like any other (ADR-0004).

## The sockets a socket-stat enchant touches

The planner does not model sockets before B6. A target may list a socket-stat enchant by its own text; the report then carries the line "this enchant reforges the sockets and breaks the links". No source gives the exact reforge, and B6's socket work owns it; B7 never says "measure later": the line states what the evidence says, which is only that the links break and the colours are rerolled.

## Verification

B7 has no benchmark route of R01 to R30 (R21's helmet enchant is a historical Labyrinth enchant and R29's is Runesmithing, both out). Agents write four test routes, because the owner is not a crafter ([ADR-0013](0013-four-batches-with-benchmark-routes.md) says the same of the benchmark routes): a rare body armour with a T1 Life prefix and a clean Life enchant; a weapon with a clean Critical enchant; a bought base with the extra crafted slot and two bench crafts; a body armour with a quality enchant. A route passes when the planner's finish cost equals the closed form of ADR-0051, `--verify` agrees, and the enchant claims appear under "Approximate inputs". The contract suite (`tests/contract_support.py`) runs unedited on the new kinds.

## Rejected

- **An enchant searched for its effect on the roll requirements** (grill answer 3): 54 and 136 candidates per query, a plan that sets an enchant the owner did not ask for, and a slower solve. The magnitude's effect on a requirement is still read when the target names the enchant (a build ticket, blocked by [#71](https://github.com/Rasslabsya4el/crafting-system/issues/71)).
- **The enchant inside the compressed state**: nothing reads it, so it would only multiply the state count.

Origin: [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (round 1, answer 3 and the standing rule); [Tempering, Tailoring and quality enchants](https://github.com/Rasslabsya4el/crafting-system/issues/100); ADR-0004, ADR-0011, ADR-0024, ADR-0027, ADR-0029.
