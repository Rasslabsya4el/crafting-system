# Crafting route planner

A planner for Path of Exile 1 item crafting: for a target item it finds the crafting policy with the lowest mean cost, with exact odds. Decisions behind these terms live in `docs/adr/`.

## Items and modifiers

**Concrete item**:
One specific item: its base, item level, influence, rarity and every mod with its tier, roll and origin.
_Avoid_: real item, full item

**Mod**:
One modifier on an item: a prefix, a suffix or an implicit, from one record of game data.
_Avoid_: affix (when an implicit is meant too), stat

**Family**:
An exclusion set of mods: an item never holds two mods that share a family. A mod belongs to one or more families.
_Avoid_: group, mod group, exclusion group

**Mod type**:
The game data's classification of a mod; mods of several types can share a family.
_Avoid_: group (Path of Building's `group` is a mod type)

**Tier**:
One level-gated version of a mod within its family on a given item class; tier 1 is the best.

**Roll**:
The value a mod's stat takes within its tier's range.

**Metamod**:
A bench-crafted mod that changes what other actions may do to the item, such as `Prefixes Cannot Be Changed`.

**Fractured mod**:
A mod made permanent in its slot by the Fracturing Orb.

**Pool**:
The mods an action can add to a given item at a given moment, each with its weight.
_Avoid_: modpool

## Targets

**Target**:
The item the owner wants to end with, stated as a conjunction of requirements.
_Avoid_: goal item, desired item

**Requirement**:
One condition of a target: a mod, named by family or by English stat text, with a minimum tier or a minimum roll, optionally marked "not crafted".
_Avoid_: constraint, filter

**k-of-n requirement**:
A requirement met when at least k of its n listed requirements are met.
_Avoid_: group, choice group

**Start item**:
The concrete item a query starts from; by default a fresh normal base.

## Crafting

**Primitive**:
One kind of game action whose outcome distribution the planner models: an orb, an essence, a fossil combination, a Harvest reforge, a bench craft, buying an item.
_Avoid_: method, recipe

**Action**:
One choice the solver can take in a state: a primitive with its parameters (which essence, which fossils, which bench craft).

**Action contract**:
The five answers every action gives, so that a new one is one file: its label, its outcomes on a concrete item, its resources, what it reads and what it adds. Nothing outside the actions names a concrete action.

**Action kind**:
A family of actions defined together and registered by the module that defines them: every essence, every bench craft, every fossil set. A kind may be left out of the planner's offers while staying in the catalog.
_Avoid_: action type, action class

**Catalog**:
The list of the actions of every registered kind that can apply to an item. The planner builds its offers from it.
_Avoid_: registry (that is the rules registry)

**Label**:
The stable name of an action that routes and reports use ("Chaos Orb", an essence's own name); two actions share one only when their variants differ.

**Resources**:
What one use of an action consumes, by price-file name, with counts, read from admitted rules.
_Avoid_: cost (the price of the resources in Chaos)

**Reads**:
What of the item, besides its fractured mods, the result of an action depends on: nothing (the action erases the other mods and redraws), their number, or their number and some families. It decides what a compressed state must keep.

**Adds**:
What an action puts on the item as far as can be told without running it: the mods it names, whether they are crafted, whether it draws from the pool and with which tag. A planner can ask it whether an action can matter for a target.

**Crafting method**:
A technique players name, such as essence spam or fracture-then-reforge. Here it is a pattern that appears in a policy, never something coded.

**Acquisition cost**:
The expected cost of obtaining an item in a given state, by crafting it or buying it, whichever is cheaper.

**Input**:
Another item an action consumes besides the one in hand (the donor of a recombinator, the imprint, the second item of an Awakener's Orb). An action with inputs is a two-input action. Its cost on every attempt is the action's own cost plus the acquisition cost of each input, because a retry consumes fresh inputs.
_Avoid_: ingredient, second item (when the solver's `extra_inputs` is meant)

**Need**:
What an action asks for as an input: a start item and the compressed state wanted from it. The solver sees it as the start state of an acquisition process.

**Acquisition process**:
The sub-problem whose value is an acquisition cost: the same actions as the main problem, aimed at one wanted state instead of the target, so that an input costs the value of reaching it. The main target is one more acquisition process.
_Avoid_: sub-craft, donor craft

**Branching component**:
A strongly connected component of the solver's graph that contains an input edge, such as donors that need each other. Its equations are not a contraction; the solver finds their least fixed point from below.

**Value ceiling**:
The cost above which the solver declares a state infinite, since a supercritical branching component never converges.

**Selection rule**:
One admissible way a recombinator chooses which mods to keep (ADR-0012). The admitted rules form a family; each is solved separately and the interval is read across them.

**Policy**:
The action to take in every state reachable from the start item, with the expected remaining cost of each state. It is what the planner returns.
_Avoid_: plan, strategy

**Route**:
A policy read as a person follows it: the main line of actions and where to go on a miss.
_Avoid_: chain, path

**Benchmark route**:
A published crafting route (R01–R30 in the reference routes research) whose cost and odds a batch must match or beat. Its guide's cost is its **Given route** evaluated at the same prices.
_Avoid_: test craft, reference craft

**Given route**:
A route written down in a YAML file by an agent from a guide, and evaluated exactly as a fixed policy instead of searched for: ordered rules "when the compressed state matches these conditions, do this action", the first match wins, and a rule may restart by buying the start item again. A reachable state no rule covers is reported as a gap. It gives the guide's cost, which guides do not state, and `--route` also lets users compare their own route with the solver's.
_Avoid_: guide policy, manual policy

**Batch**:
One stage of v1's action set (B1 to B4), finished when its benchmark routes pass.
_Avoid_: phase, milestone

## State and solving

**Compressed state**:
An item as the solver sees it: the status of each requirement, junk as counts per family type, exceptional families, and flags such as rarity, fractured, crafted, metamods and influence.
_Avoid_: abstract state, item state

**Junk**:
The mods on an item that no requirement asks for.
_Avoid_: filler, bad mods

**Family type**:
A set of families that every enabled action treats alike, so junk in any of them is counted rather than identified.
_Avoid_: junk class, tag class

**Exceptional family**:
A family that fits no family type and is tracked by identity.

**Slot**:
One mod of a compressed state that is not fractured, kept as a side, a kind and what it gives each requirement (a crafted mod also by its mod). The slots are a multiset: junk of one side and kind is counted, not identified. The kind is empty for a family type and the family itself for an exceptional family.
_Avoid_: junk entry

**Pool signature**:
Everything about a compressed state and an action that decides the action's outcome distribution; states with equal signatures share one kernel. Different actions can share one signature: a fossil set whose factors change no weight of the base has the signature of a Chaos Orb.

**Kernel**:
The probability distribution over next compressed states for one action from one compressed state.
_Avoid_: transition table

**Exact merge**:
Treating concrete items as one compressed state when every action behaves identically on them. An approximate merge is one that is not exact; it is allowed only as a coarse state with an optimistic and a pessimistic model (ADR-0023).

**Coarse state**:
A block of compressed states treated as one, used only to bound an answer: some slot kinds are renamed to a coarser kind, never a requirement's status, a slot count or a side. Its members are the compressed states it stands for.
_Avoid_: abstract state

**Family group**:
Families that no requirement asks for and that no relevant bench craft clashes with, pooled into one kind in a coarse state.
_Avoid_: family pool (a pool is the mods an action can add)

**Optimistic model**:
The coarse state in which a block offers every action that is legal in at least one member and pays what the cheapest member pays; its value is a lower bound on the exact mean cost of every member.

**Pessimistic model**:
The coarse state in which a block offers only the actions legal in every member and pays what the worst member pays; its policy is an ordinary policy of the exact problem and its value is an upper bound on that policy's cost.

**Approximate answer**:
A policy with the interval between the optimistic and the pessimistic value, marked as approximate; given when the exact state would not fit in about a minute.
_Avoid_: estimate, heuristic answer

**Certified gap**:
The upper bound over the lower bound, minus one: at least the true relative error of an approximate answer's mean cost. The owner's tolerance is a certified gap of at most 1%.

## Evidence

**Admitted rule**:
A claim about game behaviour, with provenance, that the planner may use. Anything else is an open question.
_Avoid_: assumption, likely rule

**Provenance**:
Where an admitted rule comes from: source kind, URL, short quote, patch verified, date checked.

**Source kind**:
The kind of source behind an admitted rule: official, wiki, datamined, large-sample experiment, `coe` (Craft of Exile) or `owner` (the owner's in-game check or knowledge).

**Open question**:
A mechanics question no admitted rule answers; the actions and branches that depend on it are invisible to the solver until it is settled.
_Avoid_: unknown, TODO

**Ruleset**:
The one game patch and mode that all data and rules are pinned to; now PoE 1 3.29.3.3, ordinary.
_Avoid_: league, version

## Prices

**Price file**:
The dated local file of prices, in Chaos Orbs, that the solver reads.
_Avoid_: price feed, price cache
