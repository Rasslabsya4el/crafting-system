"""The crafted pattern: the key of a state and the optimistic model of the key, built from the abstraction alone (ticket #497, research #376).

A **pattern** is a function of the state. The **key** of this module is `(flags, fractured mods, status of the wanted mods, the item state beyond
the mods, the crafted slots, the ordinary mods per side)`, and with the metamods modelled also the **protected tags** of the ordinary mods per
side (`PatternKey`). The **optimistic model** of the key has one abstract state per key and, in it, the actions of the concrete states that have
it, seen through the key. A concrete policy is a policy of that model (it takes the action of the member it is in), so its optimal value never
exceeds the exact value of a member: `V_key(key(s)) <= V*(s)`. Research #376 measured this bound on the walked graphs (99.48% of the exact cost
on R04, 98.10% on R14, 99.99% with the tags, 100% on S02). This module builds the same model **without the walk**: `members(key, mode)`
makes the concrete states of a key from the key alone, `Pattern.expand` offers the kernels of those members, and `build_pattern_model` explores
the keys from the start key.

Admissible by construction (an action offered in a key is at least as good as the action of every concrete state of the key, for any values of
the successor keys; costs are the offers' own, the same for every member; no outcome is dropped, because the kernel of a member is the exact
kernel of `Abstraction`, pushed through the key, and chances that fall in one key add). What has to be argued is that the members offered
stand for all the members. The members of a key are the states with that key, and their ordinary mods differ in two ways.

* **Which goal-relevant mods they hold.** An ordinary slot is *relevant* unless its kind is a family type `~n` none of whose mods gives the
  goal anything ("pure junk"); relevant slots (those that give a leaf something, those of a family type that has such a mod, and the families an
  enabled action names) are enumerated exactly: every multiset consistent with the status, the counts and the tags. Nothing is assumed of them.
* **Which pure junk they hold.** A pure junk slot of side `s` and tag set `T` (its *class*) stands for one family of a family type of that class.
  The classes' counts are in the key (with the tags in it) or enumerated (without). Within a class the members differ in which types they hold,
  and so in the pool weight `H_c` the held families take out of the pool.

The member policy of an action (`Pattern.mode_of`) says which pure junk assignments are offered, and is the soundness argument of the action
class. In the notation `V` is any value of the successor keys and `backup_m(V)` is the chance-weighted sum for the member `m`:

* `ANY` (one member): an erasing reroll that reads no junk (Chaos, Alteration, Transmutation, an essence, a Harvest reforge), when the key holds
  no lock. Its outcome is a function of the flags, the fractured mods, the crafted slots and the item state (the pool excludes the fractured
  families only; the other mods are erased), all in the key (ADR-0023, "block-invariant", checked on the fixtures by the contract suite).
  **Proved** by the same argument as ADR-0023; with a lock it is not (the locked side keeps its junk through a reroll, the draw excludes
  those families, and several mods are drawn: the chance is a product of ratios, not a linear-fractional function), so a key that holds a lock
  uses `ALL`.
* `ONE` (one member for each relevant multiset and class composition): an action that reads the junk but is declared block-invariant and reads
  no pool weight (a bench craft, Remove Crafted Mods, the Annulment). Bench crafts read the families they name (relevant kinds, enumerated);
  Remove Crafted Mods reads nothing of the junk; the Annulment removes one removable slot uniformly, and the removable slots are counted by
  class (the tags are in the key, or the compositions are enumerated), so its pushed kernel is the same for every assignment of the pure junk
  of a class: the chance of a successor key is `(removable slots that lead to it) / (removable slots)`. **Proved** for the Annulment under
  protected tags when the tags are in the key or enumerated (an Attack/Caster metamod keeps the protected-tag slots out of the candidates, and
  that is a function of the class); the locked side is kept (a lock in the key makes the mode `ALL`).
  A reroll of values in place that reads nothing of the junk but its count (`Reads.rerolls_values`, a Divine Orb; #830) is `ONE` too: it keeps
  every slot and draws a new roll for each slot whose mod a roll limit tells apart. Those are relevant slots (a rollable mod is the kind
  `$<mod id>` and gives its leaf BELOW or PASSING, never nothing), enumerated exactly; a pure junk slot gives the goal nothing at any roll, so
  its roll is not in the state and it stays as it is. Its refusals read the rarity and whether a changeable mod is held, both functions of the
  key. So its pushed kernel is the same for every pure junk assignment. **Proved** so, and checked against every member on the fixtures
  (`tests/test_pattern_rolls.py`); under a lock the locked side keeps its rolls and the mode is `ALL`.
  The unveil, the picks and the Veiled Exalted Orb (#828) are `ONE` too, a lock or not, with the folded families of "The folded families"
  below. Each reads of the junk its count and the families it names (the unveiled pool's: told apart by name; a pure junk family type that
  holds a mod of one, a hybrid whose family key is not that family alone, makes the policy `ALL`, `Pattern._pure_holds`; 3.29.3.3 has none) and
  keeps the rest (`Reads.junk`, `Reads.families`). The unveil draws the offer from the unveiled pool less the families on the item, and a pick
  puts the k-th mod of the offer in place of the placeholder, refused when its family is on the item: both read only named families and the key
  (the placeholder, the offer, a lock), and change no ordinary slot. The Veiled Exalted Orb removes one removable slot uniformly (the locked side
  and the fractured mods are not removable, every other slot is, whatever its tags) and puts a placeholder on the side with room: the removable
  slots are counted by class, so the chance of a successor key is `(removable slots of that class) / (removable slots)`; it is refused when the
  key holds a veiled mod. **Proved** so, and checked against every member on the fixtures (`tests/test_pattern_veiled.py`).
* `ANY` for an action the abstraction gives a view of the item without its ordinary slots (`Abstraction._erases`: the action reads no junk and
  no lock keeps a side), whether or not it declares block invariance (the Veiled Chaos Orb, #828): every member has the same view, so the same
  kernel and the same refusals. **Proved** by the construction of the kernel (#827), not by a declaration.
* `EXTREMES` (the lightest and the heaviest assignment in each class that holds pure junk): an addition that keeps the mods (`Reads.variants`:
  Augmentation, Regal, Exalted; one mod drawn). The chance of a successor key is `(a + sum_c b_c H_c) / (W - H_rel - sum_c H_c)` with `H_c` the
  pool weight (under the protected tags the key's metamods impose) the held pure junk of class `c` takes out, `H_rel` that of the relevant slots
  (the same for every assignment) and `W` the pool total: a drawn pure junk mod of class `c'` lands in the same successor key whichever of its
  types it is, and the chance of that is `(W_c' - H_c') / (W - H)`. A linear-fractional function with a positive denominator is quasi-linear,
  so the least and the greatest backup over a box of `H_c` are reached at its corners; the achievable `H` vector is a subset of the box whose
  corners are achievable (the lightest and the heaviest fill of each class, independently), so the least backup over all members is reached at
  an offered one. **Proved for a single draw** (ADR-0023); **extended here to the protected tags** (the draw excludes the mods of the blocked
  tags and the held families take out their eligible weight) and checked against all members on the fixtures. A corner that two classes make
  impossible together (one family type shared by two tag kinds) is not offered: the key then falls back to `ALL`.
  An action that draws by tag or by item level (`Reads.draw_tags`, `Reads.draw_levels`) makes the family types differ by more than weight: `ALL`.
* `RELAXED` (one member for each relevant multiset and class composition, as `ONE`, each with the choice nodes of `_relaxed`): a reroll whose
  pool weighs the families the item holds (`Action.held_weight_factor`: the likelihood Harvest reforges, #975). Each fill of the pure junk
  is a pool of its own and the draw is several mods, so neither `ONE` nor `EXTREMES` holds; the choice nodes walk the draw at the level of
  the key, with the weight each class has left in a box that every fill lies in, and offer each corner of the box at each draw. **Proved**
  in `_relaxed`'s docstring (the least backup over the box is at a corner, by induction on the draws) and checked against every member on the
  toy pools (`tests/test_pattern_relaxed.py`). Under a lock, or with a family on both sides, `ALL`; a member where the walk does not hold
  (`relaxed_draw` returns None) makes the key's offer `ALL`.
* `ALL` (every pure junk assignment): the Fracturing Orb (the successor key holds the type of the mod fractured, a function of which types the
  member holds: not of the weights), any action that is not declared one of the above, and an erasing reroll under a lock. **Unproved to be
  cheaper, and exact by construction.**

Every member offered is checked to be an item (`Abstraction._item_of`), so a member that no item has is never offered.

**The impossible corner (#1192).** The lightest fill of each class, taken together, need not be an item: one family type can hold mods of two
tag classes (on R20's helmet the one family of critical strike chance for socketed gems has an attack mod and a caster mod, each the lightest
kind of its class), and two slots of one family are no item. `EXTREMES` rests on the corners of the box, so there the composition is offered
at every fill (`ALL`, exact). `ANY` and `ONE` do not: by their own arguments above the pushed kernel and the refusals of the action are the
same at every fill of the pure junk of a composition (the action reads of the pure junk its count and its classes; the families it names are
relevant slots, enumerated, or folded families, the `named` members), so any one fill that is an item stands for all of them, as the lightest
does where it is one. The composition is then offered at the first fill that is an item (`Pattern._assemble`), not at every one: on R20's
guide offers a key of three prefixes and three suffixes had 11,263 members under `ONE` and 8,062 under `ANY` where a few dozen stand for
them, and each was a pair of every such offer. With folded families to tell apart (`named`), every fill is still made. The rows of the
model are the same (a pair left out gave a kernel another pair of its composition gave); a build counted in pieces counts the pairs it
looks at, so it gets further on the same count.

**The fills an action cannot tell apart (#1192).** `ALL` makes every fill of the pure junk: every multiset of family types, class by class.
An action seldom reads which type a slot holds; what it reads of the junk is its own declaration (`Reads`), and two fills that show the
action the same give it the same kernel pushed through the key, and the same refusal. So of the fills of a composition that an action
cannot tell apart, the first that is an item is offered and the others are not (`Pattern.alike_of`, `_assemble_alike`): the rows of the
model are the ones every fill gives, from fewer pairs. What an action reads of the pure junk of a side is one of three things.

* **Nothing but its count and class**: an action that reads the junk through the families it names and adds no mod drawn from the pool
  (`Reads.families` a set, no `pool_weight`: a Harvest swap, a catalyst, a socket craft, and under a lock an Annulment, a bench craft, a
  Divine Orb). The families it names are relevant slots, enumerated; a pure junk type holds none of them (`Kinds._members_of`). Its result
  keeps the pure junk slots or removes some, whatever their type, and the key counts them by class. One fill for each composition, as
  `ONE` has; `ONE` itself asks `Reads.block_invariant` and no lock, which these keys or actions lack.
  The same holds for the side an erasing reroll erases at a key with one lock (`Reads.junk` False: it "does not look at" the mods it
  erases); the side it keeps is told apart by type, as before: the families kept leave its pool, and several mods are drawn.
* **The weight a held family takes out of its draws**: an addition that keeps the mods (`Reads.pool_weight`, with `families` a set), where
  `EXTREMES` is not its policy. A draw gives a mod of the pool with the chance of its weight among the families the item does not hold,
  so a held family shows the draw the weight of its mods and nothing else; the key reads of a drawn mod its side, what it gives the goal
  and its protected tags; and a draw the action restricts to tags (`Reads.draw_tags`) or makes at another item level (`Reads.draw_levels`)
  reads those of each mod besides. Two family types whose mods have the same weights, summed over the mods alike in all that (for a
  draw by tag, over the mods with the tag alone: the others are in no draw of the action), are exchanged by a renaming of the families
  that the action's kernel and the key do not see: the held one of the first fill for the held one of the second, each staying in the
  pool of the other fill with the same weights in the same classes of mods. The family types of the state are finer than that (they
  carry every tag and level that any enabled action reads, and every mod's weight for the additions that draw from the whole pool), so
  for one action many types are alike: on R17's ring a Harvest craft that adds a lightning mod reads of a family the weight of its
  lightning mods, which most families lack, and about 320 fills a key showed it a handful of different pools.
* **Which type each slot holds** (no reduction): a Fracturing Orb (the successor key holds the type of the mod fractured), a
  recombinator, an action that reads the influence mods or weighs the held families (`held_weight_factor`), the veiled actions, an action
  that declares no families, and the side a reroll keeps under a lock.

The argument is the declaration's own: `Reads.families` and `Reads.pool_weight` say what of the junk a result may depend on, and the
contract suite compares the actions against them. Checked here by building a model both ways (`SHARE_ALIKE`), on the hand-worked world
and on real targets: the same rows at every key (`tests/test_pattern_alike_fills_real.py`).

**The members an action cannot tell apart (#1338).** `ONE` makes one member for each relevant multiset, because a bench craft, a Divine Orb
or an unveil reads which relevant mods a member holds. An Annulment does not: at R04's keys of thousands of relevant multisets it was asked
at each (597,014 pairs in five minutes of the first bound) and each pair was a kernel key of its own (the key holds the slots kept), 596,911
kernels for 13,284 distinct ones. Call the *view* of an ordinary slot what the key reads of it: its side, its protected tags and what it
gives the goal (`Pattern.view`: `key` counts the slots by side and by (side, protected tags), and the status of a state is the per-leaf best
of what its slots give, the very function `members` checks a status against).

*Lemma.* Let `a` be an action that is declared block-invariant, names no family of the junk (`Reads.families` empty), adds no mod (no
draw, nothing named, no fracture: `Adds`) and reads nothing else of a mod (no pool weight, variant, reroll of values, influence, tier or
input: `Pattern.views_only`). If two members `m1`, `m2` of a key have the same multiset of views, then `a` refuses both or neither, and
their kernels pushed through the key are equal.

*Argument.* The members of one key hold the same flags, fractured, crafted and veiled slots and item state beyond the mods; they differ in
their ordinary slots alone. Equal multisets of views give a bijection `p` from the ordinary slots of `m1` to those of `m2` that keeps each
view. `a` reads of an ordinary slot no family and no mod (its declaration) and adds none, so each outcome of `a` at `m1` is `m1` with some
of its ordinary slots removed, the rest kept, and the parts the key holds changed as the action does (an implicit, the quality, a crafted
mod removed); which slots it removes, and with what chance, it reads from the key and from the side and the protected tags of each slot
(the Annulment: one removable slot uniformly, a removable slot being one not on a locked side and of no tag a metamod protects; the
Eldritch Annulment the same on the dominant side, which the key holds; Remove Crafted Mods, an Ember, an Ichor, an Orb of Conflict, a
Harvest quality enchant: none). The same outcome at `m2` removes the slots `p` maps those to, with the same chance, and its refusals read
the same counts. The two successors then have ordinary slots of the same views, so the same counts, tags and status (a per-leaf best of
the same contributions with the key's own slots): the same key. So the pushed kernels are equal, outcome by outcome. **Proved** so.

The build asks such an action once for each multiset of views at a key (`SHARE_VIEWS`: the first member with those views; the others take
its answer: its kernel, its refusal or its model gap; `stats.view_pairs`), before its kernel key is made: the rows are the ones every member
gives, from one kernel each. The pairs left out still count as pairs, as a certain addition's do, so a counted build stops where it did.
Checked against every member of every key a seeded walk meets, with a lock and without, on the hand-worked world and on the Eldritch
world (`tests/test_pattern_member_views.py`); the model built both ways is the same on the hand-worked world (exact and approximate) and
on a counted build of R04's quiver; R04's first bound on the server: the same 78,715 keys, 145,259 kernels and start value, from 182,642
kernels made where every member made 1,644,703.

**The veiled slots (#828, ADR-0026).** The veiled placeholder and the mods unveiled from the pool (the kinds `VeiledPrefix`, `VeiledSuffix` and
`^<family>`) are held by the key exactly, as the crafted slots are (`PatternKey.veiled`), and are left out of its counts and tags; the universe
holds none of them, so a member holds the key's veiled slots and no other (never a double veil, which every veiled action refuses as a model
gap). The offer of an unveil is in the key's `held`, whole: the k-th mod is the one `Pick(k)` takes. The unveil's backup in the model is then
the expectation, over the offers, of the least backup of the picks at each offer key: a minimum inside the expectation, as in the exact graph.

**The folded families (#828).** The unveil and the picks name every family of the unveiled pool, so the abstraction tells apart by name each
ordinary family the unveiled pool shares (on the boots of R24, 12 of the 33 ordinary families: attack speed, strength, physical damage, ...).
Held as relevant slots, those would be enumerated exactly in every key, for every action: about 244 members a key for an Exalted Orb where the
family types give a few. A family is *folded* (`Pattern._folded`) when only the veiled actions name it: no other enabled action that reads
the junk does, none reads every family, and it has mods on one side only (a family on both sides takes both out of a draw, which the weight
of a pure type, of one side, does not hold). A folded family that gives the goal nothing is pure junk of its class (side, tags), a type of one
family (`_PureType.named`), and its slots are left out of the relevant multisets. The key does not change: it counts the ordinary slots by
class already. What has to be argued is each action's policy with folded families among the pure junk.

* The actions that do not name a folded family (every action but the unveil and the picks, by the definition) see a folded family as a family
  type of one family. `ANY` and `ONE` read no pure junk but its count and class, so they hold as they did. `EXTREMES` holds as above: a folded
  family has the weight of its mods in the pool like a type, a drawn mod of it is pure junk of its class in the successor key, and the box of
  `H_c` keeps its corners (a type of capacity one is filled or not). The Veiled Exalted Orb names them, but reads no ordinary slot by family:
  its refusal reads the veiled slots, which the key holds, and its removal is uniform over the removable slots. `ALL` makes every assignment.
* The unveil and the picks read them, and only where they are live (`Pattern.named_of`, the members `Pattern.members(key, ONE, named)`).
  Both need the placeholder: at a key without it each is refused at every member, by the key. At a key with the placeholder and an offer, the
  unveil is refused at every member (the offer is drawn once), and a pick reads, of the ordinary slots, whether one shares a family with the
  mod it takes: `named` is the offer's families. At a key with the placeholder and no offer, the picks are refused at every member, and the
  unveil reads which families of the unveiled pool the item holds: `named` is every folded family it names. Those members are every way the
  pure junk of each class holds the folded families of `named` (each within its capacity), the other slots the lightest fill of the other kinds
  (`_named_fills`), and the kernel of the action at a member is a function of the key, the relevant slots and the folded families of `named`
  it holds: a family type's representative is never a family the abstraction tells apart by name (`Kinds._members_of`), and the action reads
  nothing else of the junk. So every member's kernel is the kernel of an offered member. **Proved** so.

Every member of a key is then matched, for each action, by an offered member with the same pushed kernel or one whose least backup is no
higher, and the induction of the first paragraph gives `V_key(key(s)) <= V*(s)`: the bound stays a lower bound. Checked against every member of
the walked keys and against the exact graph's values, with and without a lock, on the fixture of `tests/test_pattern_veiled.py`.

**The imprints (#833, ADR-0034, ADR-0060).** A state that keeps the imprints is `(s, H)`: the item `s` and the set `H` of the snapshots it was
imprinted at (each a state with no imprint of its own). The key holds, in place of each snapshot `h`, its key `K(h)` (`CompressedState.held`
at `IMPRINTS`, sorted by an order of the keys alone, `Pattern._snapshot_order`); a member is `(m, R)`, `m` a member of the mods as above and `R`
one snapshot of each key held (`Pattern.held_of`: the first met of that key). For a member `(s, H)` of the key and an action `a`:

* `a` moves no imprint. No such action reads `H`: its kernel acts on `s`, and its result keeps `H` or forgets it where the result is fractured,
  corrupted or a new item (`Abstraction._carried`), which the result and the action say. So the kernel of `(s, H)` pushed through the key is
  that of `(s, R)`, and the member policies above hold as they are.
* `a` is an imprint (adding one, or replacing the j-th). Its result is `(s, H')` with `H'` = `H` less the snapshot replaced, plus `s`: its
  key holds `K(H')`, which is `K(H)` less the key replaced plus `key(s)`, the key's own: one certain successor, the same for every member
  that takes it. The game's refusals read the rarity, the base, a fracture, a corruption and `|H|`: the key's. The rule that refuses an
  imprint of a state already held (`s in H`) reads the member; where it refuses the member asked (the one that is its own key's snapshot in
  `R`), another member of the key is asked (`PatternBuilder._move`), and an imprint that would replace that very snapshot leads back to the
  key and is left out (a positive cost to the same key).
* `a` is a restore of `h in H`. Its result is `(h, H - {h})`, of key `K(h)` holding `K(H) - {K(h)}`: the same for every `h` of the key
  `K(h)`. The restores of a member and those of the key are matched by the snapshot, not by the index (a member's j-th snapshot need not be
  the key's j-th): all cost the same (`RESTORE_COST`), and together they reach every key held. The rule that refuses a restore onto the state
  the item is in (`h = s`) reads the member, and the restore it refuses is never needed: then `K(h)` is the key's own `k`, and the
  restore's backup `c + V(k, X)` is at least `V(k, X + {k})`, by this claim on the values `V` of the model (its fixed point): for every key
  `k'`, every set `X` and every snapshot key `x`, `V(k', X + {x}) <= V(k', X)`. Play at `(k', X + {x})` the optimal policy of `(k', X)`,
  carrying `x`: an ordinary action leads to the same successor key with `x` held too, or with both forgetting their imprints; a restore of a
  snapshot of `X` to the same key with `x` held too; a restart to the start key; an imprint that adds to the same key with `x` held too, or,
  where the set with `x` is full, the imprint that replaces `x` to the very successor of `(k', X)`. Each action is one the model offers at
  `(k', X + {x})` (the refusals of the key read `|H|`, and a full set has the replacing imprints), and the cost of the coupled run is the
  cost of the run from `(k', X)` until `x` is replaced or forgotten, after which both are in one key. So the policy costs at most `V(k', X)`.

Every concrete action is so matched by an offered one with the same pushed kernel, and the induction of the first paragraph gives
`V_key(key(s, H)) <= V*(s, H)`. The key loses nothing by holding `K(h)` rather than `h`: what `h` gives a plan is the restore, which leads to
`K(h)` whichever `h` it is. Checked against the exact graph (`tests/test_pattern_imprint.py`). A bound made of the bound of the item without
its imprints, `min(LB(s), c + LB(h))`, is not one: an item at its own snapshot holds the beast's price more than its value (the toy loop of
ADR-0060: `V(h, {h}) = V(h, {}) - beast`), and a gamble from `h` is worth less with `h` held than without it.

**The Eldritch implicits (#835, ADR-0025).** The key holds the item state beyond the mods exactly (`held`), and with it the pair of a state that
keeps the implicits (`CompressedState.implicits`): the grade of each side, what its implicit gives each implicit wanted (its roll included),
and its line where a requirement names one (`ImplicitSide`). Every member of a key holds the key's pair, so the dominant side, a function of
the two grades, is the key's. The Eldritch currencies then have these member policies, each from what it declares (`Reads`):

* An Ember or an Ichor, and an Orb of Conflict (`Reads.block_invariant`, no draw: `ONE`, and `ALL` under a lock by the rule of `ONE`). Neither
  changes an explicit slot: the result holds the member's slots and a new pair, drawn from a pool that the base, the side and the grade fix
  (an Ember's), or moved inside the lines the pair holds (a Conflict's), the other side's implicit kept. Their refusals read the class, the
  corruption, the influences and, for a Conflict, whether both implicits are there: the key's. So the kernel pushed through the key is the
  same at every member (`ANY` would do too). **Proved** so.
* An Eldritch Orb of Annulment (`Reads.block_invariant`: `ONE`, `ALL` under a lock). It is the Annulment on the dominant side: it removes one
  of that side's removable slots uniformly (not fractured, not on a locked side, not of a tag an Attack or Caster metamod protects), so the
  chance of a successor key is `(removable slots of that class on that side) / (removable slots on that side)`, counted by class as the
  Annulment's are (the side is the key's). It is refused where nothing is dominant or nothing is removable: the key's. **Proved** so.
* An Eldritch Exalted Orb (`Reads.variants`: `EXTREMES`). It is the Exalted Orb restricted to the dominant side `d`: one mod drawn from that
  side's pool less the families held, the others kept. The chance of a successor key is `(a + sum_c b_c H_c) / (W_d - H_rel,d - sum_c e_c H_c)`
  with `e_c` 1 for a class of side `d` and 0 for one of the other side: a pure junk family of the other side takes nothing out of a draw of
  side `d` when no family has mods on both sides. That is a linear-fractional function of the `H_c` with a positive denominator, so the
  argument of `EXTREMES` holds as it is: the least backup over the box is at a corner, and the corners are offered. A pool with a family on
  both sides (`partners`) breaks `e_c` (a held family of the other side takes its partner's weight out of the draw, which is not its `H_c`):
  there the orb is `ALL` (`Pattern.mode_of`). **Proved for a single draw.**
* An Eldritch Chaos Orb (`ALL`). It erases the dominant side's unfractured mods and draws several, keeping the other side, whose families the
  draws exclude: an erasing reroll under a lock, whose chances are products of ratios. **Exact by construction.**

Every other action keeps the pair or reads it as the key holds it (the kernel carries the implicits; a goal reads what each gives), and a
restart leads to the start key. So every concrete move is matched as above and the induction of the first paragraph gives `V_key <= V*`.
Checked against the exact graph of a small Eldritch pool (`tests/test_pattern_eldritch.py`): every Eldritch move of every state is offered at
its key, and the model is a lower bound at every state.

**Refusals.** An action that the game forbids at a member (`NotApplicableError`) is not an action of that member and is left out
of it. An action that raises a model gap at a member (`OutOfScopeError`: no admitted rule covers the item) is left out only when
no member of the key can take it (each is a game refusal or a gap: the exact model has no action at any state of the key, as the walk and the
planner treat a gap as unavailable). If another member can take it, the build refuses and names the offer and the key: the exact model drops
the action only at the states where the gap is, so leaving it out of the key could put the bound above the exact cost (`_gap_everywhere`). A
model gap in `_item_of` always refuses. An action that declares `Reads.refusal_by_families` (a bench craft, Remove Crafted Mods) is refused alike
at every item of one refusal class (`Abstraction._refusal_class`, #1178): a pair whose class holds a refusal already is counted as refused
without asking `kernel_key` (`Abstraction.refusal_class_of`, `refused_in_class`; #1256: R04's round of bench crafts asked 2.3 million pairs,
2.28 million of them refusals of a class met before), the very answer `kernel_key` gives it. Where such an action names no family (Remove
Crafted Mods, a Fracturing Orb: `Abstraction.refusal_names_no_junk`), its class at a member is the action and the member's item without its
junk, with the junk's count per side. The members of a key differ in their ordinary slots alone, which are that junk: the flags, the fractured
mods, the crafted and the veiled slots, the item state beyond the mods and the count of ordinary slots per side are the key's. So every member
of the key has the class of the first, and once one member's class holds a refusal the others are counted as refused without making their
item to look the class up (#1193: a Fracturing Orb is asked at every pure junk assignment, `ALL`, and at most keys it is refused by the
key: not rare, fewer than four mods, a fractured mod; on R04's 19 offers 154,808 of its 225,719 pairs, each of which built the member's item
to find the class). A member with no class (a fractured family type that may decide the refusal) is asked as before, and so are the members
after it.

**The certain additions (#1193).** An action declared `Adds.only_named` (a bench craft, an aspect beast; the contract suite checks it) has
one outcome: the item it was given with its named mods added, nothing else changed. At a member `m` of key `k` that takes it, the successor
holds `m`'s flags, fractured mods, item state beyond the mods and veiled slots; its crafted slots are `k`'s with the crafted mod added, its
ordinary slots `m`'s with an ordinary named mod added (one slot of a kind the mod alone fixes, so the counts and the tags of `k` move by a
fixed step); and its status is the per-leaf best of `m`'s status and what the named mods give (`best_of`), with `m`'s status `k`'s. Each part
is a function of `k` and the action, so the successor key is the same at every member of `k` that takes it, and so is the pushed kernel: one
certain successor. The members differ only in whether they take it (the refusal, which reads the junk of the families named). So the build
asks the members in turn until one takes the action and leaves the rest out (`PatternBuilder._offers_of_key`): they would add only that same
kernel, and no new slot (theirs are of the universe already, and the named mods are noted with the first). The pairs left out still count as
pairs of the build (`stats.pairs`, the counted net's `Tally`), so a build counted in pieces stops where it did; a member the quality rule
prunes (#159) is passed over before, as for any action, and counts as no pair. Its model gaps (a normal item,
an item with no mod, a roll limit on the named mod) read the key and the action alone, so no member left out could have raised one. R04's
round of bench crafts asked 73 crafts at every member of every key, 1.17 million pairs nearly all of distinct kernels (#1193). **Proved** so;
the tests compare the whole model built so with the one built asking every member, on the hand-worked world (bench crafts) and on a real
route under a counted net (`tests/test_certain_additions.py`). An aspect beast, whose named mod is ordinary, rests on the argument alone.

**The universe.** The members of a key are made of the ordinary slots an item can hold. They come from three places: the pool of an empty rare
item (every mod a draw can give, under a roll limit once for each outcome of its roll, #830; the pure junk types are made of these), what an offered action adds by name (`Adds.named`: an essence's forced
mod, which the pool does not list; `Universe._seed_named`), and every slot a kernel the build evaluates produces (`note`; a slot found this way
that the two others missed starts the build again on the grown universe, `stats.universe_growth`). A slot that a non-offered member's kernel would produce, and no
offered member's, cannot be one of the first two: a draw gives a mod of the pool, and a forced mod is the same at every member. What is left is
a draw from a pool wider than the empty rare item's (a fossil's added mods) at a member that is not offered, which `Adds` does not name: the
universe may miss that slot, and the members that hold it are not made (issue #520). No route of the benchmark has such an action.
"""

import time
from bisect import bisect_left
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from enum import StrEnum
from fractions import Fraction
from functools import cache, reduce
from itertools import product
from math import gcd, lcm
from typing import NamedTuple

from crafting_system import budget
from crafting_system.actions import BLOCKED_TAG, LOCKED_SIDE, Action, NotApplicableError, OutOfScopeError, Reads, allowed_by_tags, partners
from crafting_system.data import Mod
from crafting_system.items import Item, ItemError, Metamod, Rarity, Side
from crafting_system.items.model import VEILED_DOMAIN

from ._goal import Status
from ._kernel import Abstraction
from ._relaxed import ChoiceNode, relaxed_draw
from ._kinds import ALIKE, MOD_PREFIX, TYPE_PREFIX, UNVEILED_PREFIX, kind_families, kind_tags, protected_tags
from ._rolls import is_rollable
from ._recent import Recent, kept_entries
from ._state import CompressedState, Slot, best_of

# The two families of refusal an action raises (`actions/errors.py`, #506). A game refusal (`NotApplicableError`: the game forbids the action on that
# item) may drop the action at a member: it is not an action there. A model gap (`OutOfScopeError`: no admitted rule covers the item) may not: at a
# member that is not a state of the route it says nothing about the states that are, and dropping the action from the key could put the bound
# above the exact cost. The build refuses and says why. The clauses name the families themselves (`tests/test_cli_model_gaps.py` scans for them).

REFUSED = -3  # what `PatternBuilder._offers_of_key` notes for the views of a member the action refuses (#1338) ...
GAP = -4  # ... and of a member where it is a model gap at every member of the key
CHOICE = -2  # the offer index of a row of a choice node (`_relaxed`): a step of a relaxed draw, at no cost (carried at `FLOOR_COST`)
SINK = -1  # the successor of the mass an approximate kernel does not account for: a state that costs nothing (the goal)
SHRINK = Fraction(2**30 - 1, 2**30)  # every chance of a float kernel is taken this much lower; the float error is 1e-13, so no chance is above its exact one
PRIME_FROM = 16  # a key that is given at least this many offers at once primes their distributions in a process pool (fewer cost more in forks than they save: R14, 11 offers), in chunks of ...
PRIME_CHUNK = 32  # ... this many offers (the net is asked between two chunks)
POLL_SECONDS = 0.5  # how often a build asks its net (a clock and a memory read, cheap beside one offer)
SIDES = (Side.PREFIX, Side.SUFFIX)
LOCKS = frozenset({Metamod.PREFIXES_CANNOT_CHANGE.value, Metamod.SUFFIXES_CANNOT_CHANGE.value})
TAG_OF_METAMOD = {metamod.value: tag for metamod, tag in BLOCKED_TAG.items()}
KERNEL_KEY_SHARE, KERNEL_KEY_BYTES = 1 / 12, 1024  # `computed` may hold this share of the memory net, in keys of about 1 KB with their parts (`kept_entries`, #1335)
MEMBER_SHARE, MEMBER_BYTES = 1 / 20, 300  # `Pattern._feasible` may hold this share, in members of about 300 bytes (#1335); a 12 GB net: 2^19 keys, about 2^20 members a generation
KERNEL_KEYS_KEPT: int | None = None  # a generation of `computed` set by hand (the tests); None: from the net (`kept_entries`)
MEMBERS_KEPT: int | None = None  # a generation of `Pattern._feasible` set by hand (the tests); None: from the net
SHARE_KEY_PARTS = True  # a kernel key stored in `PatternBuilder.computed` holds its parts shared with the other keys (`_shared_parts`, #1332); False: as made
SHARE_REFUSED = True  # a pair whose refusal class holds a refusal is answered from it, without `kernel_key` (#1256); False: each pair asks it
SHARE_KEY_REFUSALS = True  # such a pair of an action that names no family refuses the action at the key's other members too (#1193); False: each is looked up
SHARE_ADDITIONS = True  # a certain addition (`Adds.only_named`) is asked at a key's members until one takes it (#1193); False: at every member
SHARE_ALIKE = True  # under `ALL` the fills of the pure junk that an action cannot tell apart are offered at one of them (`Pattern.alike_of`, #1192); False: at every fill
SHARE_VIEWS = True  # an action that tells ordinary slots apart by what the key reads of them alone is asked once for each multiset of those views at a key (`Pattern.views_only`, #1338); False: at every member
SHARE_FILLS = True  # under `ANY` and `ONE` a composition whose lightest fill is no item is offered at one fill that is (#1192); False: at every fill
LUMP_ERASING = True  # an erasing action's kernel in the build is the alike twin's (`Abstraction.alike_twin`, #1146, ADR-0065); False: the fine one
IMPRINTS = 3  # where the imprints are in `CompressedState.held` (implicits, quality, offer, imprints, strands, replaced)
NOTHING = "nothing"  # what `Pattern.alike_of` says of a side whose pure junk an action reads by its count and class alone
COUNT_ONLY = Reads(junk=True, families=frozenset())  # what an action reads of the junk when it reads its count alone (Remove Crafted Mods, and a Divine Orb besides the rolls)


class Mode(StrEnum):
    """Which members of a key an action is offered at (see the module docstring)."""

    ANY = "any"
    ONE = "one"
    EXTREMES = "extremes"
    RELAXED = "relaxed"
    ALL = "all"


class PatternKey(NamedTuple):
    """The pattern of a state: what the optimistic model tells states apart by."""

    flags: object
    fractured: tuple
    status: tuple
    held: tuple
    crafted: tuple
    counts: tuple  # the ordinary (not crafted, not veiled) slots per side: (prefix, suffix)
    tags: tuple | None  # ((side index, protected tags), count) of the ordinary slots, or None when the key carries no tags
    veiled: tuple = ()  # the veiled placeholder and the mods unveiled from the pool, as slots, exactly (#828): never a member's choice


@dataclass(frozen=True)
class _PureType:
    """A family type none of whose mods gives the goal anything: `capacity` families of one `weight`, on a side.

    A folded family (`named` not empty, #828) is a family that only the veiled actions tell apart by name: one family, `capacity` 1, held
    among the pure junk of its class; `named` are its families, which an unveil or a pick live at a key enumerates (`Pattern.named_of`).
    """

    side: Side
    base: str
    capacity: int
    mods: tuple[Mod, ...]  # the mods of one family of the type, with the weight they have in the pool
    weights: tuple[Fraction, ...]
    named: frozenset[str] = frozenset()  # the families of a folded family; empty for a family type ("~n")

    def weight(self, blocked: frozenset[str]) -> Fraction:
        """The pool weight a family of this type takes out of a draw under the metamods that block `blocked` tags."""
        return sum((w for mod, w in zip(self.mods, self.weights) if allowed_by_tags(mod, blocked)), Fraction(0))


@dataclass(frozen=True)
class _PureKind:
    kind: str
    slot: Slot
    type: _PureType


class _Universe:
    """The ordinary slots an item with given influences can hold, split into relevant slots and pure junk kinds."""

    def __init__(self, pattern: "Pattern", influences: frozenset):
        ab = pattern.ab
        context = ab._context(influences)
        kinds = context.kinds
        zero = pattern.zero
        self.relevant: dict[Side, dict[Slot, None]] = {side: {} for side in SIDES}
        self.pure: dict[Side, dict[str, _PureType]] = {side: {} for side in SIDES}
        self.classes: dict[Side, dict[tuple, list[_PureKind]]] = {side: defaultdict(list) for side in SIDES}
        by_type: dict[tuple[Side, str], list] = defaultdict(list)  # (side, type kind) -> [(family, mod, slot)]
        for family in kinds._pool() if kinds.tracked else ():  # a state that keeps no junk holds no ordinary slot
            for entry in family.mods:
                kind = kinds.of(entry.mod)
                for contribution in _rolled_contributions(ab, entry.mod, influences):
                    by_type[(family.side, _base(kind))].append((family, entry.mod, Slot(family.side, kind, contribution)))
        folded = self.folded = pattern._folded(kinds)
        for (side, base), rows in by_type.items():
            silent = all(all(value is Status.ABSENT for value in slot.contribution) for _, _, slot in rows)
            named = _foldable(base, folded) if silent else frozenset()
            if not (silent and (base.startswith(TYPE_PREFIX) or named)):
                for _, _, slot in rows:
                    self.relevant[side][slot] = None
                continue
            families = {family.family: family for family, _, _ in rows}
            first = next(iter(families.values()))  # the families of one type have the same mods and weights (the type is made of them)
            kind_type = _PureType(
                side, base, len(families), tuple(entry.mod for entry in first.mods), tuple(entry.weight for entry in first.mods), named
            )
            self.pure[side][base] = kind_type
            for kind in sorted({slot.kind for _, _, slot in rows}):
                self.classes[side][_tagset(kind)].append(_PureKind(kind, Slot(side, kind, zero), kind_type))
        self.zero = zero
        self.influences = influences
        self.kinds = kinds
        self._seed_named(pattern, pattern.actions)

    def _seed_named(self, pattern: "Pattern", actions: Sequence[Action]) -> int:
        """Add the ordinary mods an offered action puts on the item by name and that the pool does not list (an essence's forced mod).

        `Adds.named` is the same on every use, so the slot is known before any kernel is run; this is what keeps a slot that only a member that
        is not offered would have produced from missing (see the module docstring, "The universe"). Returns how many slots the universe gained.
        """
        ab = pattern.ab
        influences, kinds = self.influences, self.kinds
        gained = 0
        probe = Item.build(ab.data, base_id=ab.base_id, item_level=ab.item_level, rarity=Rarity.RARE, influences=influences)
        for action in actions:
            try:
                adds = action.adds(ab.data, probe)
            except NotApplicableError:
                continue
            if adds.crafted:
                continue
            for mod_id in adds.named or ():
                mod = ab.data.mods.get(mod_id)
                if mod is None or mod.domain == "crafted" or mod.generation_type not in (side.value for side in SIDES):
                    continue
                for contribution in _rolled_contributions(ab, mod, influences):  # each roll's, as the pool's slots (#1146: no kernel teaches a lumped draw's)
                    slot = Slot(Side(mod.generation_type), kinds.of(mod), contribution)
                    if self.note(slot):
                        gained += 1
                        pattern.grown.append((influences, slot))
        return gained

    def note(self, slot: Slot) -> bool:
        """Add a slot a kernel produced that the pool did not list; True when the universe grew."""
        if slot.crafted or slot.side not in self.relevant:
            return False
        base = _base(slot.kind)
        known_pure = self.pure[slot.side].get(base)
        if known_pure is not None and all(value is Status.ABSENT for value in slot.contribution):
            if any(item.kind == slot.kind for item in self.classes[slot.side][_tagset(slot.kind)]):
                return False
            self.classes[slot.side][_tagset(slot.kind)].append(_PureKind(slot.kind, Slot(slot.side, slot.kind, self.zero), known_pure))
            return True
        if slot in self.relevant[slot.side]:
            return False
        self.relevant[slot.side][slot] = None
        return True


def _rolled_contributions(ab: Abstraction, mod: Mod, influences: frozenset) -> list[tuple[Status, ...]]:
    """What a drawn `mod` can give the goal: at its low rolls, and, under a roll limit that its values decide, every outcome of its law (#830).

    A slot holds what its mod gives each leaf as it rolled, so a rollable mod is a slot for each outcome of its roll law (`_rolls.roll_law`;
    a reroll of values in place moves a slot between them). Without the outcomes here the universe would learn them from the kernels only, and
    each one learnt so begins the build again.
    """
    low = ab._drawn_contribution(mod, False, influences)
    if not ab._has_laws:
        return [low]
    cells = ab._law(mod, influences)
    if not is_rollable(cells):
        return [low]
    return list(dict.fromkeys([low, *(tuple(Status(value) for value in ints) for ints, _ in cells)]))


def _base(kind: str) -> str:
    from ._kinds import base_kind

    return base_kind(kind)


def _foldable(base: str, folded: frozenset[str]) -> frozenset[str]:
    """The families of a kind told apart by name that only the veiled actions read (`Pattern._folded`), or none for any other kind (#828)."""
    if not folded or base == ALIKE or base.startswith((TYPE_PREFIX, MOD_PREFIX, UNVEILED_PREFIX)):
        return frozenset()
    families = frozenset(kind_families(base))
    return families if families <= folded else frozenset()


def _placeholder_families(data) -> frozenset[str]:
    """The families of the veiled placeholders (domain `veiled`): the kind of a placeholder slot is its family key (`_kinds.Kinds.of`)."""
    return frozenset(family for mod in data.mods.values() if mod.domain == VEILED_DOMAIN for family in mod.families)


@cache
def _tagset(kind: str) -> tuple:
    """The protected tags of a kind, sorted: the class of a pure junk slot (asked for each slot of each multiset a member enumeration tries: 39 M
    times in 20 minutes of R07 before #828, so kept)."""
    return tuple(sorted(kind_tags(kind)))


def _slot_key(slot: Slot):
    return slot.key


@dataclass
class PatternStats:
    """What a build did, for the report (ticket #497: kernels evaluated against the walk's, time, memory)."""

    keys: int = 0
    goal_keys: int = 0
    members: int = 0  # concrete states offered an action, over all keys and modes (a member counted once per mode)
    pairs: int = 0  # (member, action) pairs whose kernel key was asked for, or that a certain addition left out (`shared_pairs`)
    shared_pairs: int = 0  # pairs of a certain addition not asked: a member before them took it (#1193)
    kernels: int = 0  # distinct kernels computed (the walk's count is its distinct `kernel_key`s)
    abstract_actions: int = 0
    abstract_edges: int = 0
    refused_pairs: int = 0
    gap_pairs: int = 0  # pairs left out because the action is a model gap at every member of the key that is not a game refusal
    universe_growth: int = 0
    restarted_keys: int = 0  # expanded keys a grown universe made again (`PatternBuilder._begin_again`, #1086)
    modes: Counter = field(default_factory=Counter)  # (member mode, label of the offer) -> keys it was expanded at
    seconds: float = 0.0
    view_pairs: int = 0  # pairs answered by the pair of a member with the same views of its ordinary slots (`Pattern.views_only`, #1338)
    fallbacks: int = 0  # compositions whose lightest (or heaviest) fill was no item: offered at every fill, or under `ANY` and `ONE` at one that is (#1192)


@dataclass
class PatternModel:
    """The optimistic model of the key: state 0 is the start key; `actions[k]` are `(offer index, kernel id)` of key `k`."""

    keys: list[PatternKey]
    goal: list[bool]
    actions: list[list[tuple[int, int]]]
    kernels: list[tuple[tuple[int, ...], tuple[int, ...]]]  # (successor keys, integer weights)
    stats: PatternStats
    index: dict[PatternKey, int]
    expanded: list[bool] = field(default_factory=list)  # key -> whether its actions were built; a key the build did not reach is a tip (no actions, not a dead end)
    stopped: str | None = None  # why the build ended before every key was expanded (a net), None for a complete model
    narrow: dict[int, frozenset[int]] = field(default_factory=dict)  # an offer built at some keys only (#1325): offer index -> those keys; at any other key it is not built


def pattern_refusal(abstraction: Abstraction) -> str | None:
    """Why the crafted-pattern bound cannot be built for `abstraction`, or None when it can (#497, #507).

    The one place that decides it: `Pattern.__init__` raises `OutOfScopeError` with this text, and `make_plan` asks it before any solve, so
    `solver="auto"` knows whether the envelope search is possible without starting it. Since #833 it has members for every abstraction: the
    imprints, the last cause, are held by the key as the keys of the snapshots (module docstring, "The imprints"). A roll limit and a reroll
    of values have members since #830: the key's status holds what each wanted mod gives its leaf as it rolled, and a Divine Orb is an action of the model (`Pattern.mode_of`). The unveil offer has since #828: the key holds the veiled slots
    and the offer, and the veiled actions have member policies.
    """
    causes = refusal_causes(abstraction)
    if not causes:
        return None
    return f"the crafted-pattern bound has no members for it: {'; '.join(causes)} (#497)"


# what the bound has no members for: the abstraction's attribute, the cause in the refusal's text, and in a player's words where those differ
# none since #833: the imprints were the last (the key holds the key of each snapshot)
_CAUSES: tuple[tuple[str, str, str | None], ...] = ()


def refusal_causes(abstraction: Abstraction, player: bool = False) -> tuple[str, ...]:
    """What of `abstraction` the crafted-pattern bound has no members for; empty when the bound can be built. `player`: each cause in the words
    an answer may show (`make_plan` says them when a net stops the walk that `solver="auto"` takes instead of the envelope search, #926)."""
    return tuple(shown if player and shown else text for name, text, shown in _CAUSES if getattr(abstraction, name))


class Pattern:
    """The key of a state and the members of a key, for one `Abstraction`.

    `tags` says whether the key carries the protected tags of the ordinary mods; it defaults to whether the abstraction models the metamods.
    Raises `OutOfScopeError` for an abstraction `pattern_refusal` refuses (none since #833).
    """

    def __init__(self, abstraction: Abstraction, tags: bool | None = None, actions: Sequence[Action] = ()):
        refusal = pattern_refusal(abstraction)
        if refusal is not None:
            raise OutOfScopeError(refusal)
        self.ab = abstraction
        self.data = abstraction.data
        self.actions = tuple(actions)  # the offered actions: what they add by name joins the universe of slots
        self.tags = abstraction.models_metamods if tags is None else tags
        self.width = len(abstraction.goal.leaves)
        self.zero = (Status.ABSENT,) * self.width
        self._universes: dict[frozenset, _Universe] = {}
        self._reads: dict[Action, object] = {}
        self._only_named: dict[Action, bool] = {}
        self._draws: dict[Action, bool] = {}
        self._views_only: dict[Action, bool] = {}
        self._feasible: Recent[bool] = Recent(MEMBERS_KEPT or kept_entries(MEMBER_SHARE, MEMBER_BYTES))  # member state -> whether it is an item (`_ok`), the members asked lately (#1335)
        self._tag_kind: dict[str, tuple] = {}
        self._veiled_kind: dict[str, bool] = {}
        self._pure_reads: dict[tuple, bool] = {}
        self._placeholder_families = _placeholder_families(abstraction.data)
        self._twin: Abstraction | None = None
        self._lumped_read: dict[frozenset, int] = {}  # how many of the alike twin's lumped mods of each influence set were noted (`note_lumped`)
        self._snapshot_keys: dict[CompressedState, PatternKey] = {}  # an imprint's snapshot -> its key (#833)
        self._snapshot_reps: dict[PatternKey, CompressedState] = {}  # a snapshot's key -> the first snapshot of it seen: the one the members hold
        self._snapshot_orders: dict[PatternKey, tuple] = {}
        self._partners: dict[frozenset, bool] = {}
        self._alike: dict[tuple, tuple | None] = {}  # (action, the locked sides of a key) -> what the action reads of the pure junk of each side (`alike_of`)
        self._tokens: dict[tuple, int] = {}  # (influences, side, type, what is read) -> the number of what a family of the type shows the reader (`_token`)
        self._token_ids: dict[tuple, int] = {}
        self._weighted: dict[frozenset, dict] = {}  # influences -> `Kinds._weighted_mods()`, made once
        self.grew = 0
        self.grown: list[tuple[frozenset, Slot]] = []  # the slots the universes gained, with their influences (`may_hold`, #1086)
        self.fallbacks = 0

    def keep_universes(self, before: "Pattern") -> None:
        """Take the universes of `before` (the slots its kernels found included), seeded with what this pattern's actions add by name."""
        for influences, universe in before._universes.items():
            self._universes[influences] = universe
            universe._seed_named(self, self.actions)

    def add_actions(self, actions: Sequence[Action]) -> None:
        """Offer more actions: what they add by name joins the universe, and a universe that gains a slot counts as growth (`grew`), as a kernel's slot does."""
        self.actions = (*self.actions, *actions)
        for universe in self._universes.values():
            self.grew += universe._seed_named(self, actions)

    # ---- the key ----------------------------------------------------------------------------------------------

    def key(self, state: CompressedState) -> PatternKey:
        counts = [0, 0]
        crafted = []
        veiled = []
        tags: Counter | None = Counter() if self.tags else None
        for slot in state.slots:
            if slot.crafted:
                crafted.append(slot)
                continue
            if self.is_veiled(slot):
                veiled.append(slot)
                continue
            side = 0 if slot.side is Side.PREFIX else 1
            counts[side] += 1
            if tags is not None:
                tagset = self._tag_kind.get(slot.kind)
                if tagset is None:
                    tagset = self._tag_kind[slot.kind] = _tagset(slot.kind)
                tags[(side, tagset)] += 1
        held = state.held
        if state.imprints:
            held = (*held[:IMPRINTS], self._snapshots_key(state.imprints), *held[IMPRINTS + 1 :])
        return PatternKey(
            state.flags, state.fractured, state.status, held, tuple(crafted), (counts[0], counts[1]),
            tuple(sorted(tags.items())) if tags is not None else None, tuple(veiled),
        )

    def _snapshots_key(self, imprints: tuple[CompressedState, ...]) -> tuple[PatternKey, ...]:
        """The imprints of a state as the key holds them: the key of each snapshot, in an order of the keys alone (#833, "The imprints")."""
        keys = []
        for snapshot in imprints:
            found = self._snapshot_keys.get(snapshot)
            if found is None:
                found = self._snapshot_keys[snapshot] = self.key(snapshot)  # a snapshot holds no imprint of its own (ADR-0060)
                self._snapshot_reps.setdefault(found, snapshot)
            keys.append(found)
        return tuple(sorted(keys, key=self._snapshot_order))

    def _snapshot_order(self, key: PatternKey) -> tuple:
        """A total order on the keys of snapshots made of plain values, the same for every `Pattern` (not the order the snapshots were met in)."""
        found = self._snapshot_orders.get(key)
        if found is None:
            probe = CompressedState(key.flags, key.fractured, key.status, tuple(sorted((*key.crafted, *key.veiled), key=_slot_key)), *key.held)
            found = self._snapshot_orders[key] = (probe.order_key, key.counts, key.tags or ())
        return found

    def held_of(self, key: PatternKey) -> tuple:
        """The item state beyond the mods that the members of `key` hold: the key's own, with each imprint's key replaced by the one snapshot of
        it the members hold (the first met, `_snapshot_reps`; see "The imprints" in the module docstring)."""
        held = key.held
        if not held[IMPRINTS]:
            return held
        snapshots = tuple(sorted((self._snapshot_reps[found] for found in held[IMPRINTS]), key=lambda snapshot: snapshot.order_key))
        return (*held[:IMPRINTS], snapshots, *held[IMPRINTS + 1 :])

    def is_veiled(self, slot: Slot) -> bool:
        """Whether an ordinary slot is the veiled placeholder or a mod unveiled from the pool (ADR-0026): a slot the key holds exactly (#828)."""
        found = self._veiled_kind.get(slot.kind)
        if found is None:
            base = _base(slot.kind)
            if base.startswith(UNVEILED_PREFIX):
                found = True
            elif base.startswith((TYPE_PREFIX, MOD_PREFIX)):  # a family type or one mod of the ordinary pool: never a placeholder
                found = False
            else:
                found = bool(kind_families(base) & self._placeholder_families)
            self._veiled_kind[slot.kind] = found
        return found

    def _pure_holds(self, influences: frozenset, families: frozenset[str]) -> bool:
        """Whether a pure junk type of the universe has a mod of one of `families` (a hybrid mod whose family key is not one of them alone).

        The member policy `ONE` of the veiled actions rests on the families they read being told apart by name; a pure junk slot of such a type
        could change their kernel between the members of a class, so the policy is then `ALL`. The data of 3.29.3.3 has no such mod.
        """
        found = self._pure_reads.get((influences, families))
        if found is None:
            universe = self.universe(influences)
            found = self._pure_reads[(influences, families)] = any(
                set(mod.families) & families
                for side in SIDES
                for kind_type in universe.pure[side].values()
                if not kind_type.named  # a folded family is told apart by name: `named_of` enumerates it where it is read
                for mod in kind_type.mods
            )
        return found

    def _veiled_reader(self, reads) -> bool:
        """Whether an action reads the junk as the unveil, the picks and the Veiled Exalted Orb do (#828): its count, and families it names of
        which the veiled ones are a part (or an offer), and nothing else (no draw, no weight, no reroll of values: those have policies of their own)."""
        others = reads.variants or reads.pool_weight or reads.fractures or reads.input_classes or reads.rerolls_values or reads.block_invariant
        return bool(
            reads.junk and reads.families is not None and not others and (reads.offer or reads.families & self._placeholder_families)
        )

    def _folded(self, kinds) -> frozenset[str]:
        """The families told apart by name only because a veiled action names them (#828): no other enabled action that reads the junk names
        them, and none reads every family. A folded family that gives the goal nothing is pure junk of its class (`_Universe`), not a relevant
        slot: an unveil and a pick enumerate it where they are live (`named_of`), the other actions do not read it (see the module docstring)."""
        veiled: set[str] = set()
        other: set[str] = set()
        for action in kinds.actions:
            reads = self.reads(action)
            if not reads.junk:
                continue
            if reads.families is None:
                return frozenset()
            (veiled if self._veiled_reader(reads) else other).update(reads.families)
        folded = veiled - other - self._placeholder_families
        if folded:  # a family with mods on both sides takes both out of a draw; a pure type weighs one side only, so it stays a relevant slot
            folded -= set(partners(kinds._pool()))
        return frozenset(folded)

    def holds_placeholder(self, key: PatternKey) -> bool:
        """Whether the key holds the veiled placeholder (not a mod unveiled from the pool), in a veiled slot or fractured: a fractured
        placeholder sits in `key.fractured`, and the unveil and the picks still act on it (`actions/veiled.py`, `holds_placeholder`)."""
        return any(
            not _base(slot.kind).startswith(UNVEILED_PREFIX) and kind_families(_base(slot.kind)) & self._placeholder_families for slot in key.veiled
        ) or any(self.data.mods[entry.mod_id].domain == VEILED_DOMAIN for entry in key.fractured if entry.mod_id in self.data.mods)

    def named_of(self, action: Action, key: PatternKey) -> frozenset[str]:
        """The folded families whose holding the members of `key` must tell apart for `action` (#828): empty but for an unveil or a pick that is
        live at the key, see the module docstring ("The folded families").

        An action that reads the offer and needs the placeholder (an unveil, a pick) is refused at every member of a key without the placeholder.
        With an offer drawn, the unveil is refused at every member and a pick reads, of the ordinary slots, only whether one shares a family with
        the mod it takes: the offer's families. With no offer, the picks are refused at every member and the unveil reads which families of the
        unveiled pool the item holds: all it names. The Veiled Exalted Orb reads no ordinary family (its refusal reads the veiled slots alone).
        """
        reads = self.reads(action)
        if not (reads.offer and self._veiled_reader(reads)) or not self.holds_placeholder(key):
            return frozenset()
        folded = self.universe(key.flags.influences).folded
        if not folded:
            return frozenset()
        offer = CompressedState(key.flags, key.fractured, key.status, (), *self.held_of(key)).offer
        if offer:
            return frozenset(family for entry in offer for family in self.data.mods[entry.mod_id].families) & folded
        return frozenset(reads.families) & folded

    def universe(self, influences: frozenset) -> _Universe:
        found = self._universes.get(influences)
        if found is None:
            found = self._universes[influences] = _Universe(self, influences)
        return found

    def note(self, state: CompressedState) -> None:
        """Learn the ordinary slots of a state a kernel produced (the pool may not list them)."""
        universe = self.universe(state.flags.influences)
        for slot in state.slots:
            if not slot.crafted and not self.is_veiled(slot) and universe.note(slot):  # a veiled slot is in the key, never a member's choice
                self.grew += 1
                self.grown.append((state.flags.influences, slot))

    @property
    def twin(self) -> Abstraction:
        """The alike twin of this pattern's abstraction (`Abstraction.alike_twin`), made at its first use, one for each pattern (#1146)."""
        if self._twin is None:
            self._twin = self.ab.alike_twin()
        return self._twin

    def note_lumped(self) -> None:
        """Learn the ordinary slots of the mods the alike twin lumped (`Abstraction.lumped_mods`, #1146): each mod at its own kind and at every
        contribution its roll can give, as `_Universe` lists a pool mod. A lumped outcome is never noted (its kinds are the twin's), so this is
        what keeps a mod the pool and the offers' names do not list (a mod a fossil adds to the pool) from being left out of the members."""
        for influences, mod in self.twin.lumped_mods(self._lumped_read):
            if mod.generation_type not in (side.value for side in SIDES):
                continue
            universe = self.universe(influences)
            kind = self.ab.kind_of(mod, influences)
            for contribution in _rolled_contributions(self.ab, mod, influences):
                slot = Slot(Side(mod.generation_type), kind, contribution)
                if not self.is_veiled(slot) and universe.note(slot):
                    self.grew += 1
                    self.grown.append((influences, slot))

    def may_hold(self, key: PatternKey, influences: frozenset, slot: Slot) -> bool:
        """Whether a member of `key` may hold the ordinary `slot` of the universe of `influences`: False only when none can (#1086).

        A member is a state whose key is `key` (`members` assembles it so), so it holds a slot only where the key has a place for it: an item of
        the same influences (each has its universe), a slot on its side (`counts`), with the tags its kind has when the key counts them (`tags`),
        and a contribution the key's status allows (`_relevant`; a slot of pure junk adds nothing). A key no grown slot fits keeps its members.
        """
        if key.flags.influences != influences:
            return False
        side = 0 if slot.side is Side.PREFIX else 1
        if not key.counts[side]:
            return False
        if key.tags is not None and (side, _tagset(slot.kind)) not in dict(key.tags):
            return False
        return all(c <= s for c, s in zip(slot.contribution, key.status))

    # ---- the member policy of an action -----------------------------------------------------------------------

    def reads(self, action: Action):
        found = self._reads.get(action)
        if found is None:
            found = self._reads[action] = action.reads(self.data)
        return found

    def adds_only_named(self, action: Action) -> bool:
        """Whether `action` is a certain addition (`Adds.only_named`: module docstring, "The certain additions", #1193)."""
        found = self._only_named.get(action)
        if found is None:
            found = self._only_named[action] = action.adds(self.data).only_named
        return found

    def draws(self, action: Action) -> bool:
        """Whether `action` may draw a mod from a pool (`Adds.draws`; an action that declares nothing draws)."""
        found = self._draws.get(action)
        if found is None:
            found = self._draws[action] = action.adds(self.data).draws
        return found

    def views_only(self, action: Action) -> bool:
        """Whether the kernel of `action` at a member, pushed through the key, is a function of the key and of the multiset of the views of the
        member's ordinary slots (`view`): it is block-invariant, names no family of the junk, draws no mod and adds none, and reads nothing
        else of a mod (module docstring, "The members an action cannot tell apart", #1338)."""
        found = self._views_only.get(action)
        if found is None:
            reads = self.reads(action)
            adds = action.adds(self.data)
            beyond = (
                reads.pool_weight or reads.variants or reads.fractures or reads.rerolls_values or reads.input_mods or reads.input_classes
                or reads.input_influenced or reads.influenced or reads.offer or reads.needs_veiled or reads.by_mod or reads.draw_tags
                or reads.draw_levels
            )  # fmt: skip
            found = self._views_only[action] = bool(
                SHARE_VIEWS and reads.junk and reads.block_invariant and reads.families == frozenset() and not beyond
                and action.held_weight_factor() is None and adds.named == frozenset() and not adds.draws and not adds.fractures
            )  # fmt: skip
        return found

    def view(self, member: CompressedState) -> frozenset:
        """The multiset of what the key reads of each ordinary slot of `member`: its side, its protected tags and what it gives the goal."""
        seen: Counter = Counter()
        for slot in member.slots:
            if slot.crafted or self.is_veiled(slot):
                continue
            tagset = self._tag_kind.get(slot.kind)
            if tagset is None:
                tagset = self._tag_kind[slot.kind] = _tagset(slot.kind)
            seen[(slot.side, tagset, slot.contribution)] += 1
        return frozenset(seen.items())

    def holds_lock(self, key: PatternKey) -> bool:
        """Whether the key holds a lock (`Prefixes` / `Suffixes Cannot Be Changed`), crafted or fractured: a reroll then keeps the locked side."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return any(mod_id in mods and LOCKS & set(mods[mod_id].families) for mod_id in ids)

    def blocked_tags(self, key: PatternKey) -> frozenset[str]:
        """The tags the key's Attack and Caster metamods keep out of a draw and out of an Annulment."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return frozenset(TAG_OF_METAMOD[family] for mod_id in ids if mod_id in mods for family in mods[mod_id].families if family in TAG_OF_METAMOD)

    def mode_of(self, action: Action, key: PatternKey) -> Mode:
        reads = self.reads(action)
        kinds = self.ab._context(key.flags.influences).kinds
        if action.held_weight_factor() is not None:
            # a reroll whose pool reads which families the item holds (the likelihood reforges, #975): the relaxed draw of `_relaxed` at the
            # `ONE` members, every member under a lock or with a family on both sides (see "RELAXED" in the module text)
            return Mode.ALL if self.holds_lock(key) or self._has_partners(key.flags.influences) else Mode.RELAXED
        if reads.variants and reads.junk and reads.pool_weight and not reads.fractures:
            if kinds._tagged or kinds._levels:
                return Mode.ALL
            # an addition that reads the implicits draws from the dominant side alone (an Eldritch Exalted Orb): a family on both sides breaks
            # the corners (module docstring, "The Eldritch implicits", #835)
            return Mode.ALL if reads.implicits and self._has_partners(key.flags.influences) else Mode.EXTREMES
        others = reads.variants or reads.pool_weight or reads.fractures or reads.input_classes
        if reads.block_invariant and not (others or reads.rerolls_values):
            if self.holds_lock(key):
                return Mode.ALL
            return Mode.ONE if reads.junk else Mode.ANY
        if reads.rerolls_values and replace(reads, rerolls_values=False) == COUNT_ONLY:
            # a reroll of values in place that reads nothing else of the junk than its count (a Divine Orb, #830): see the module text, `ONE`
            return Mode.ALL if self.holds_lock(key) else Mode.ONE
        if others or reads.rerolls_values:
            return Mode.ALL
        if not reads.junk and self._erases(action, key):
            # the abstraction gives the action a view of the item without its ordinary slots (a Veiled Chaos Orb, #828): see the module text, `ANY`
            return Mode.ANY
        if self._veiled_reader(reads):
            # an unveil, a pick, a Veiled Exalted Orb (#828): see the module text, `ONE` (with the folded families `named_of` gives), unless a
            # pure junk family type holds a family they read
            return Mode.ALL if self._pure_holds(key.flags.influences, reads.families) else Mode.ONE
        return Mode.ALL

    def policy(self, action: Action, key: PatternKey) -> tuple[Mode, frozenset[str]]:
        """The member policy of `action` at `key`: its mode, and the folded families its members must tell apart (`named_of`, with `ONE`)."""
        mode = self.mode_of(action, key)
        return mode, self.named_of(action, key) if mode is Mode.ONE else frozenset()

    def asked(self, action: Action, key: PatternKey) -> tuple[Mode, frozenset[str], tuple | None]:
        """The members the build asks `action` at: its `policy`, and under `ALL` what it reads of the pure junk of each side (`alike_of`)."""
        mode, named = self.policy(action, key)
        return mode, named, self.alike_of(action, key) if mode is Mode.ALL else None

    def locked_sides(self, key: PatternKey) -> frozenset[Side]:
        """The sides a lock of the key keeps through a reroll (the lock is a crafted or a fractured mod: the key's)."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        families = {family for mod_id in ids if mod_id in mods for family in mods[mod_id].families}
        return frozenset(side for metamod, side in LOCKED_SIDE.items() if metamod.value in families)

    def alike_of(self, action: Action, key: PatternKey) -> tuple | None:
        """What `action` reads of the pure junk of each side at the members of `key`, from its own declarations; None when nothing says it
        reads less than which family type each slot holds (module docstring, "The fills an action cannot tell apart", #1192).

        One entry for the prefixes and one for the suffixes: `NOTHING` (the action reads the count and the class of those slots alone),
        `(tags, levels)` (it reads the weight a held family takes out of its draws: of the mods with one of `tags`, all when empty, at the
        item's level and at `levels`), or None (which type each slot holds).
        """
        if not SHARE_ALIKE:
            return None
        locked = self.locked_sides(key)
        found = self._alike.get((action, locked), self)
        if found is not self:
            return found
        reads = self.reads(action)
        found = None
        beyond = reads.fractures or reads.input_classes or reads.input_mods or reads.influenced or reads.offer or reads.needs_veiled
        if action.held_weight_factor() is not None or beyond or self._veiled_reader(reads):
            found = None
        elif not reads.junk:
            # an erasing reroll: at a key with a lock it keeps the locked side and reads nothing of the side it erases (`Reads.junk`)
            if locked and len(locked) < len(SIDES):
                found = tuple(None if side in locked else NOTHING for side in SIDES)
        elif reads.families is not None and not reads.pool_weight:
            found = (NOTHING, NOTHING)  # it reads the count of the junk and the families it names, which are relevant slots (`Reads.families`)
        elif reads.families is not None and reads.pool_weight:
            drawn = (tuple(sorted(reads.draw_tags)), tuple(sorted(reads.draw_levels)))
            found = (drawn, drawn)  # an addition: the weight the held families take out of its draws (`Reads.pool_weight`, `draw_tags`, `draw_levels`)
        self._alike[(action, locked)] = found
        return found

    def _token(self, influences: frozenset, side: Side, kind_type: "_PureType", read) -> int:
        """A number for what a family of the pure type shows a reader of `read` (`alike_of`): two types of one number are alike to it.

        `NOTHING`: one number for every type. None, and a folded family (told apart by name): the type's own. `(tags, levels)`: the weight
        the family's mods take out of a draw, summed over the mods a draw and a key cannot tell apart (their side, what they give the goal
        and their protected tags, and which of `tags` they carry), at the item's level and at each of `levels`; with `tags`, of the mods
        that carry one alone (the draw is restricted to them), and a mod with no weight at any of those levels is in no such draw.
        """
        if read == NOTHING:
            return 0
        memo = (influences, side, kind_type.base, read)
        found = self._tokens.get(memo)
        if found is not None:
            return found
        kinds = self.ab._context(influences).kinds
        shown: tuple = ("type", side, kind_type.base)
        if read is not None and not kind_type.named and kind_type.base.startswith(TYPE_PREFIX):
            tags, levels = frozenset(read[0]), read[1]
            members = kinds._members_of(side, kind_type.base)
            known = sorted(kinds._levels)
            if members and all(level in known for level in levels):
                at = [0] + [1 + known.index(level) for level in levels]
                rows = self._weighted.get(influences)
                if rows is None:
                    rows = self._weighted[influences] = kinds._weighted_mods()
                sums: dict[tuple, list] = {}
                for other in SIDES:
                    for mod, weights in rows.get((members[0][0], other.value), {}).values():
                        own = tuple(sorted(tags & set(mod.implicit_tags)))
                        weight = [weights[index] for index in at]
                        if (tags and not own) or not any(weight):
                            continue
                        cls = (other.value, repr(kinds.profile(mod)), tuple(sorted(protected_tags(mod))), own)
                        have = sums.setdefault(cls, [0] * len(at))
                        for index, value in enumerate(weight):
                            have[index] += value
                shown = ("weights", side, tuple(sorted((cls, tuple(have)) for cls, have in sums.items())))
        found = self._tokens[memo] = self._token_ids.setdefault(shown, 1 + len(self._token_ids))
        return found

    def _has_partners(self, influences: frozenset) -> bool:
        """Whether the pool of an item with `influences` holds a family with mods on both sides (`partners`, #835)."""
        found = self._partners.get(influences)
        if found is None:
            found = self._partners[influences] = bool(partners(self.ab._context(influences).kinds._pool()))
        return found

    def _erases(self, action: Action, key: PatternKey) -> bool:
        """Whether the abstraction makes the kernel of `action` at the members of `key` from a view without their ordinary slots (`Abstraction._erases`):
        it reads the lock from the crafted and the fractured mods alone, which the key holds."""
        probe = CompressedState(key.flags, key.fractured, key.status, tuple(key.crafted), *self.held_of(key))
        return self.ab._erases(probe, action)

    # ---- the members of a key ---------------------------------------------------------------------------------

    def members(self, key: PatternKey, mode: Mode, named: frozenset[str] = frozenset(), alike: tuple | None = None) -> list[CompressedState]:
        """The concrete states of `key` that stand for all of its members for an action of the policy `mode`; each is an item.

        `named` (with `ONE`): the folded families the action reads at this key (`named_of`): every way the pure junk holds them is a member.
        `alike` (with `ALL`): what the action reads of the pure junk of each side (`alike_of`): one member for the fills it cannot tell apart.
        """
        if mode is Mode.RELAXED:  # the relaxed draw is made at one member for each relevant multiset and class composition (`_relaxed`)
            mode = Mode.ONE
        if not self.ab._context(key.flags.influences).kinds.tracked:
            # no enabled action reads the junk, so a state keeps none of it: its status is a fact about mods that are not stored, and the one
            # state the key stands for is the key itself (no ordinary slot to choose, nothing to check the status against)
            only = CompressedState(key.flags, key.fractured, key.status, tuple(sorted((*key.crafted, *key.veiled), key=_slot_key)), *self.held_of(key))
            return [only] if self._ok(only) else []
        universe = self.universe(key.flags.influences)
        blocked = self.blocked_tags(key)
        base = best_of(self.width, [slot.contribution for slot in (*key.crafted, *key.veiled)] + [entry.contribution for entry in key.fractured])
        found: dict[CompressedState, None] = {}
        allowance = budget.allowed()  # a stage on the clock asks its net here too (#1217): one key's members can take minutes
        prefixes = self._relevant(universe, Side.PREFIX, key.counts[0], key.status)
        suffixes = self._relevant(universe, Side.SUFFIX, key.counts[1], key.status)
        # the status of a pair of multisets is the per-leaf best of the prefixes' (with the key's own slots) and the suffixes': each side's is
        # made once and a pair is looked up by the two (#1256: 3.5 million `best_of` over the pairs took R04's round of bench crafts 17 s)
        fits = _fitting(self.width, key.status, [[slot.contribution for slot in rel] + [base] for rel in prefixes], [[slot.contribution for slot in rel] for rel in suffixes])
        for (rel_p, at_p), (rel_s, at_s) in product(zip(prefixes, fits[0]), zip(suffixes, fits[1])):
            if allowance is not None:
                allowance.tick()
            if not fits[2][at_p][at_s]:
                continue
            relevant = rel_p + rel_s
            for compositions in self._compositions(universe, key, rel_p, rel_s):
                if allowance is not None:
                    allowance.tick()
                for state in self._assemble(universe, key, relevant, compositions, blocked, mode, named, alike):
                    if allowance is not None:
                        allowance.tick()
                    found[state] = None
                if mode is Mode.ANY and found:
                    return list(found)
        return list(found)

    def _relevant(self, universe: _Universe, side: Side, count: int, status: tuple) -> list[tuple[Slot, ...]]:
        """Every multiset of at most `count` relevant slots of `side` that none of its slots exceeds `status` in.

        Two slots that each stand for one mod (`$<mod id>`) of a shared family are never on one item, so no multiset holds them both: `_ok` would
        refuse every state made of it, and under a roll limit there are many (one slot per tier and per outcome of its roll, #830).
        """
        pool = sorted(
            (slot for slot in universe.relevant[side] if all(c <= s for c, s in zip(slot.contribution, status))), key=_slot_key
        )
        families = [self._families_of(slot) for slot in pool]
        out: list[tuple[Slot, ...]] = []

        def grow(start: int, chosen: tuple[Slot, ...], held: frozenset[str]) -> None:
            out.append(chosen)
            if len(chosen) == count:
                return
            for at in range(start, len(pool)):
                own = families[at]
                if own & held:
                    continue
                grow(at, (*chosen, pool[at]), held | own)

        grow(0, (), frozenset())
        return out

    def _families_of(self, slot: Slot) -> frozenset[str]:
        """The families of the one mod a slot stands for (a kind `$<mod id>`); empty for a slot that stands for a family or a type."""
        base = _base(slot.kind)
        if not base.startswith(MOD_PREFIX):
            return frozenset()
        mod = self.data.mods.get(base[len(MOD_PREFIX) :])
        return frozenset(mod.families) if mod is not None else frozenset()

    def _compositions(self, universe: _Universe, key: PatternKey, rel_p, rel_s) -> Iterator[dict[tuple, int]]:
        """The ways the pure junk slots split into classes (side index, tag set): fixed by the key's tags, enumerated without them."""
        have = Counter()
        for slot in (*rel_p, *rel_s):
            have[(0 if slot.side is Side.PREFIX else 1, _tagset(slot.kind))] += 1
        left = (key.counts[0] - len(rel_p), key.counts[1] - len(rel_s))
        if left[0] < 0 or left[1] < 0:
            return
        if key.tags is not None:
            need = {cls: count - have[cls] for cls, count in key.tags}
            for cls, count in have.items():
                if cls not in need:
                    return
            if any(count < 0 for count in need.values()):
                return
            need = {cls: count for cls, count in need.items() if count}
            if any(sum(c for (s, _), c in need.items() if s == side) != left[side] for side in (0, 1)):
                return
            yield need
            return
        per_side = []
        for index, side in enumerate(SIDES):
            classes = sorted(tagset for tagset, items in universe.classes[side].items() if items)
            per_side.append([{(index, tagset): n for tagset, n in zip(classes, split) if n} for split in _splits(left[index], len(classes))] if classes or not left[index] else [])
        for first, second in product(*per_side):
            yield {**first, **second}

    def _assemble(
        self, universe: _Universe, key: PatternKey, relevant, need: dict[tuple, int], blocked, mode: Mode, named: frozenset[str] = frozenset(),
        alike: tuple | None = None,
    ) -> Iterator[CompressedState]:
        if mode is Mode.ALL and alike is not None:
            yield from self._assemble_alike(universe, key, relevant, need, blocked, alike)
            return
        options = []
        for (side_index, tagset), count in sorted(need.items()):
            side = SIDES[side_index]
            fills = _fills(universe.classes[side].get(tagset, []), count, blocked, mode, named)
            if not fills:
                return
            options.append(fills)
        corners = self._states(key, relevant, options)
        if mode is Mode.ALL or all(self._ok(state) for state in corners):
            yield from (state for state in corners if self._ok(state))
            return
        # a corner that two classes make impossible together (or no state at all): every assignment of this composition instead
        every = [_fills(universe.classes[SIDES[side_index]].get(tagset, []), count, blocked, Mode.ALL) for (side_index, tagset), count in sorted(need.items())]
        if SHARE_FILLS and mode in (Mode.ANY, Mode.ONE) and not named:
            # ... of which one stands for them all under these policies (module docstring, "The impossible corner", #1192): the first that is an item
            for state in self._each_state(key, relevant, every):
                if self._ok(state):
                    self.fallbacks += 1
                    yield state
                    return
            return
        found = [state for state in self._states(key, relevant, every) if self._ok(state)]
        if found:
            self.fallbacks += 1
        yield from found

    def _assemble_alike(self, universe: _Universe, key: PatternKey, relevant, need: dict[tuple, int], blocked, alike: tuple) -> Iterator[CompressedState]:
        """`ALL` for an action that reads of the pure junk only what `alike` says: of the fills of a composition that show it the same
        (the same numbers of `_token`, class by class), the first that is an item (module docstring, "The fills an action cannot tell apart")."""
        grouped = []
        for (side_index, tagset), count in sorted(need.items()):
            side = SIDES[side_index]
            items = universe.classes[side].get(tagset, [])
            token = {item.slot: self._token(universe.influences, side, item.type, alike[side_index]) for item in items}
            groups: dict[tuple, list] = {}
            for fill in _fills(items, count, blocked, Mode.ALL):
                groups.setdefault(tuple(sorted(token[slot] for slot in fill)), []).append(fill)
            if not groups:
                return
            grouped.append(list(groups.values()))
        for pick in product(*grouped) if grouped else [()]:
            for state in self._each_state(key, relevant, pick):
                if self._ok(state):
                    yield state
                    break

    def _states(self, key: PatternKey, relevant, options) -> list[CompressedState]:
        return list(self._each_state(key, relevant, options))

    def _each_state(self, key: PatternKey, relevant, options) -> Iterator[CompressedState]:
        """The state of `key` with the `relevant` slots and each pick of one fill from each class's `options`, in the order of the picks."""
        held = self.held_of(key)
        for pick in product(*options) if options else [()]:
            slots = [*key.crafted, *key.veiled, *relevant]
            for part in pick:
                slots.extend(part)
            slots.sort(key=_slot_key)
            yield CompressedState(key.flags, key.fractured, key.status, tuple(slots), *held)

    def _ok(self, state: CompressedState) -> bool:
        """Whether the state is an item the abstraction can give to an action (every slot has a family of its own)."""
        found = self._feasible.get(state)
        if found is None:
            try:
                self.ab._item_of(state, False)
                found = True
            except OutOfScopeError:
                raise
            except (ValueError, ItemError):
                found = False
            self._feasible[state] = found
        return found


def _fitting(width: int, status: tuple, firsts: list[list], seconds: list[list]) -> tuple[list[int], list[int], list[list[bool]]]:
    """Which pairs of `firsts` and `seconds` (lists of contributions) have together the per-leaf best `status`: `best_of(width, first + second)
    == status` is `fits[first's class][second's class]`, where a class is a distinct `best_of` of one side (the best of a union is the per-leaf
    best of the bests). Returns each first's class, each second's class and the table."""
    numbers: list[dict[tuple, int]] = [{}, {}]
    places = []
    for side, lists in enumerate((firsts, seconds)):
        places.append([numbers[side].setdefault(best_of(width, vectors), len(numbers[side])) for vectors in lists])
    table = [[tuple(max(a, b) for a, b in zip(first, second)) == status for second in numbers[1]] for first in numbers[0]]
    return places[0], places[1], table


def _splits(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    """Every way to write `total` as `parts` non-negative integers."""
    if parts == 0:
        if total == 0:
            yield ()
        return
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _splits(total - first, parts - 1):
            yield (first, *rest)


def _fills(items: Sequence[_PureKind], count: int, blocked: frozenset[str], mode: Mode, named: frozenset[str] = frozenset()) -> list[tuple[Slot, ...]]:
    """The ways `count` pure junk slots of one class sit on its kinds: the lightest, the heaviest, or every one, by the pool weight they take out.

    With `named` (`ONE` only), every way the slots hold the folded families of `named`, the rest the lightest fill of the other kinds.
    """
    if count == 0:
        return [()]
    order = sorted(items, key=lambda item: (item.type.weight(blocked), item.kind))
    if mode is Mode.ALL:
        return _all_fills(order, count)
    if named and mode is Mode.ONE:
        return _named_fills(order, count, named)
    lightest = _greedy(order, count)
    if mode is not Mode.EXTREMES:
        return [lightest] if lightest is not None else []
    heaviest = _greedy(order[::-1], count)
    out = [fill for fill in (lightest, heaviest) if fill is not None]
    return [out[0]] if len(out) == 2 and out[0] == out[1] else out


def _greedy(order: Sequence[_PureKind], count: int) -> tuple[Slot, ...] | None:
    used: Counter = Counter()
    chosen: list[Slot] = []
    for item in order:
        while len(chosen) < count and used[item.type.base] < item.type.capacity:
            used[item.type.base] += 1
            chosen.append(item.slot)
    return tuple(sorted(chosen, key=_slot_key)) if len(chosen) == count else None


def _named_fills(order: Sequence[_PureKind], count: int, named: frozenset[str]) -> list[tuple[Slot, ...]]:
    """Every choice of the kinds of folded families in `named` (each within its capacity) for some of the `count` slots, the others the
    lightest fill of the remaining kinds (none of which holds a family of `named`); a choice whose rest cannot be filled is no member."""
    read = [item for item in order if item.type.named & named]
    rest = [item for item in order if not item.type.named & named]
    out: dict[tuple[Slot, ...], None] = {}
    used: Counter = Counter()

    def grow(at: int, chosen: tuple[Slot, ...]) -> None:
        fill = _greedy(rest, count - len(chosen))
        if fill is not None:
            out[tuple(sorted((*chosen, *fill), key=_slot_key))] = None
        if len(chosen) == count:
            return
        for index in range(at, len(read)):
            item = read[index]
            if used[item.type.base] < item.type.capacity:
                used[item.type.base] += 1
                grow(index, (*chosen, item.slot))
                used[item.type.base] -= 1

    grow(0, ())
    return list(out)


def _all_fills(order: Sequence[_PureKind], count: int) -> list[tuple[Slot, ...]]:
    out: list[tuple[Slot, ...]] = []
    used: Counter = Counter()

    def grow(at: int, chosen: tuple[Slot, ...]) -> None:
        if len(chosen) == count:
            out.append(tuple(sorted(chosen, key=_slot_key)))
            return
        for index in range(at, len(order)):
            item = order[index]
            if used[item.type.base] < item.type.capacity:
                used[item.type.base] += 1
                grow(index, (*chosen, item.slot))
                used[item.type.base] -= 1

    grow(0, ())
    return out


# ---- the optimistic model -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternOffer:
    """An action of the plan: `action` is None for the restart (buy the start item again), which leads to the start key."""

    label: str
    action: Action | None
    cost: float


def build_pattern_model(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PatternOffer],
    *,
    tags: bool | None = None,
    progress=None,
    max_keys: int | None = None,
    stop: Callable[[], str | None] | None = None,
    approximate: bool = False,
) -> PatternModel:
    """The optimistic model of the key from the start key, with no walk of the concrete graph.

    For each key, not a goal, and each offer it is offered at the pushed kernel of every member of the policy of the action
    (`Pattern.mode_of`); members that the action refuses do not offer it, and a restart leads to the start key from every key but the start's.
    Two members with the same pushed kernel give one abstract action. If a kernel produces an ordinary slot the pool did not list, the
    universe grows and the build runs again (`stats.universe_growth` counts the restarts). Raises `OutOfScopeError` as `Pattern` does and
    `RuntimeError` when more than `max_keys` keys were found (a safety net the caller asks for, never a default).

    `stop` is the stop-and-say-so net of the build (OR-12, OR-13): it is asked between two offers of a key (so a key that holds thousands of
    offers is no longer one step) and returns the reason once a net is reached. The build then ends with `PatternModel.stopped` set. The key it was
    expanding is left a tip like the keys it had not reached: a tip has no actions in the model, which is not "the key has none", so the caller
    gives it a bound of its own (`_pattern_bound`, a floor action to the goal). If the universe had grown in that pass, the keys expanded before
    the growth lack the members that hold the new slot, so none of them is kept: every key is a tip.

    With `approximate` the distributions behind the kernels are made in floats (`Abstraction.approximate`), which costs a twentieth of the time. A kernel
    made so is not the exact one: each of its chances is shrunk by `SHRINK` (2^-30, above the float error of 1e-13, so no chance exceeds its exact value)
    and the mass that is then missing is the chance of the state `SINK` (a successor of -1, a goal that costs nothing). The expected value of any
    non-negative function of the successors is then at most the exact one, so a model built so is a lower bound of the model built exactly, and it differs
    from it by about 1e-9 of a value.
    """
    return PatternBuilder(abstraction, start, tags=tags, progress=progress, max_keys=max_keys, stop=stop, approximate=approximate).extend(offers)


LATE = 1.0  # a nearly done build may go past its net by at most this many times the net (`Growth`, #1135): one more share, no more (a
# stop-and-say-so net under OR-12, hand-set; `_plan.search_net` lowers it so the rounds after keep half their time, and the last round has none)


@dataclass
class Growth:
    """Where a bound's build that grows its model stands (`_pattern_bound`, #988): the offers its model holds, the one being added included
    (`inside`), of the offers it was given (`total`); and, since #1224, the offers of its first model (`start`) and of the last model it
    solved (`solved`). Set each time a solved model lets more offers join; before that (the floors, the first model's keys) nothing is known
    of how far the build is.

    **A nearly done build finishes (#1135).** A round of `_rounds` that begins with a plan in hand gives its bound's build its whole share
    (#1099), and a build that its share ends before it is complete leaves the round a weak lower figure and no search: R11's Exalted round,
    essences in its base, builds in 18 s on the server and 24 to 28 s on a runner, against a share of 26 to 27 s; complete, its first plan
    costs 188.03 c against the 617.28 c in hand, and cut, its figure is 13 to 15 c and the answer keeps 617.28 c (probe run 44091258887). Its
    model's value stays low until the last offers join (it is the floor of the cheapest offer left out), so the value says nothing of how far
    the build is; what does is how many offers it holds. (Since #1224 the nets decide by the pace of the growth, `Pace`, and
    `nearly_done`, the count below, is no longer read by them.) A build that has used `used` of its net `given` (seconds, or pieces of work) and
    holds `inside` of `total` offers is expected to need `used * total / inside` in all, at most: the offers still out cost on average what
    those in cost, and not every one of them joins (R11's Exalted round ends with 80 of 84). It may go on past its net while that figure is
    within `1 + late` nets, and never past `1 + late` nets (`late` at most `LATE`): the build that is nearly done finishes, a build far
    from done (R11's harvest swap round, 19 of 89 offers at its share) stops at its share as before. On the clock the time it takes past
    its share comes off the rounds after it, so `late` is at most half of what they have (`_plan.search_net`: none for the last round, whose
    share is all the time left, so the run never passes its net); a build that is not nearly done takes nothing from them. Counted in
    states, pieces are not states: a late build takes no states from the rounds after it.

    **The pace of the growth (#1224).** Once growth has added offers, the net knows more: the offers its solved models added since the first
    one, and what that took (`Pace`). The need it then expects is that pace kept to the last offer (`Pace.need`), and it replaces the count
    above, which takes the offers of the model being built as done: on R13 and R17 the first model held 49 of 51 and 64 of 69 offers and
    the model adding the rest was all the build's work, never done (#1180)."""

    inside: int
    total: int
    start: int = 0
    solved: int = 0

    def nearly_done(self, used: float, given: float, late: float = LATE) -> bool:
        """Whether a build that has used `used` of its net `given` goes on past it, to at most `1 + late` times it (see the class text)."""
        if late <= 0 or self.inside <= 0 or given <= 0 or used >= (1.0 + late) * given:
            return False
        return used * self.total / self.inside <= (1.0 + late) * given


class Pace:
    """What a bound's build tells its net of how far it is (`Growth`, #1135, #1224), and the rule the net keeps with it (`verdict`).

    `grown(growth, used)` is called by the build each time a solved model lets more offers join, `used` being what the net has counted so
    far (seconds, or pieces of work). The first call marks where the growth began (the first model solved); from the second on, the growth
    has a pace: the offers it added (`solved - start`) for what it used since. Kept to the offers still out, the build is expected to need
    `need = grew_from + (used - grew_from) * (total - start) / (solved - start)` in all. The figure is set at a solved model and held until the next,
    so a long model being built does not move it (R11's Exalted round: its third and fourth models, 12 Screaming essences, take 7 and 8 s of
    its 38 s) while it stays within that figure.

    **A build that outruns its pace (#1325).** The figure is a forecast from the models solved so far. A build that has used more than
    it, its next model still unsolved, has shown that the forecast was too low, by the time it has run over (`used - forecast`). That
    time is charged to the work the forecast was read from: the pace becomes what the solved models' offers took plus the overrun, and
    kept to the offers still out it gives `forecast + (used - forecast) * (total - start) / (solved - start)` (`reckon`). The figure has
    no jump: at the forecast it is the forecast, and it grows from there by as many seconds a second as the offers still out are to those
    the pace was read from. The build stops once it passes the room (`OUTRUN`), as any build whose pace ends past its room does.

    Since per-key joining (#1325) a model's work is no longer in proportion to its offers: an offer built at the 29 keys that need it
    costs a fraction of a second, and the next model, whose offers grow the universe and begin the build again at 8,943 keys, costs the
    round's whole share. On R13's site plan the second model (4 offers at 29 keys) was solved at once and its pace foretold 0.9 s; read
    alone, that figure let the third run to twice the share, nearly done: 26 builds ran past their share, 13 searches had 0 s, and the
    plan cost 390,773 c against main's 89,548 to 95,719 c. With the overrun charged (24 offers out for 4 solved: 6 s a second) it stops
    at about 7.4 s of a room of 40 s. A build that overruns a little goes on: R11's Exalted round, foretold 36.17 s from its third model
    and ending at 38.3 s, reads at most 36.17 + 2.13 * 74 / 20 = 44 s there, within its room of 54 s."""

    def __init__(self) -> None:
        self.growth: Growth | None = None
        self.grew_from: float | None = None  # the net's count when the first model was solved
        self.need: float | None = None  # the build's expected need at its pace of growth, None until growth has added offers
        self.grows = False  # the build grows its model from part of its offers (its offers' floors are worked out, `_pattern_bound`)
        self.forecast: float | None = None  # the need its pace foretold at its last solved model (`grown`)
        self.outrun = False  # it has used more than its pace foretold, its next model unsolved (`reckon`, #1325)

    def grown(self, growth: Growth, used: float) -> None:
        self.growth = growth
        if self.grew_from is None:
            self.grew_from = used
        if growth.solved > growth.start:
            self.need = self.forecast = self.grew_from + (used - self.grew_from) * (growth.total - growth.start) / (growth.solved - growth.start)
            self.outrun = False

    def reckon(self, used: float) -> float | None:
        """The need `verdict` reads when the build has used `used` (see the class text): the forecast of its pace while the build keeps to
        it; once it has used more, its next model unsolved, `forecast + (used - forecast) * (total - start) / (solved - start)`, the overrun
        charged to the work the pace was read from (it raises `need`, so what a stop says names it). None with no pace."""
        growth, forecast = self.growth, self.forecast
        if forecast is None or growth is None or growth.solved <= growth.start or used <= forecast:
            return self.need
        self.outrun = True
        self.need = max(forecast, forecast + (used - forecast) * (growth.total - growth.start) / (growth.solved - growth.start))
        return self.need

    def verdict(self, used: float, given: float, room: "Room | None") -> str | None:
        """Why a build that has used `used` of its net `given` stops now (`SHARE`, `QUARTER` or `PACE`), or None to go on.

        With no plan in hand (`room` None) the build stops at its net, and the net is the quarter `SEARCH_PER_BUILD` leaves it (the caller
        sizes it). With a plan in hand (#1099, #1224) its net is the round's whole share and its room `1 + room.late` times it:
        * before `room.quarter` of the net it goes on;
        * past it, a build whose growth has a pace goes on only while that pace ends within its room (`need`, or once the build has
          outrun it that forecast with the overrun charged to its pace, `reckon`, #1325), and stops as soon as it does
          not: the rest of the share is its search's, where it took the whole share and left the search none (R17, R20: #1167). A build with
          no pace yet that grows its model (`grows`: its first model not solved, or its growth has added no offer) has nothing that shows
          it will end there: it stops, whatever the plan in hand (R13's round 2, #1142: its first model held 49 of 51 offers and its
          second never ended; R17's site plan: rounds whose first model of 10 to 69 offers was not solved after their whole share, and
          whose searches had 0 s). One that does not grow (one model on every offer, or still working out its offers' floors, or a
          floors pass alone, `_rounds.by_floor`) keeps the whole share, as since #1099;
        * past its net it goes on while nearly done: only at a pace that ends within its room (`reckon`)."""
        if room is None:
            return SHARE if used >= given else None
        whole = (1.0 + room.late) * given
        if used >= given:
            if room.late <= 0 or used >= whole:
                return SHARE
            need = self.reckon(used)
            return None if need is not None and need <= whole else SHARE
        if used < room.quarter * given:
            return None
        need = self.reckon(used)
        if need is not None:
            return None if need <= whole else (OUTRUN if self.outrun else PACE)
        return QUARTER if self.grows else None


SHARE, QUARTER, PACE, OUTRUN = "share", "quarter", "pace", "outrun"  # why a build's net stops it (`Pace.verdict`)


@dataclass(frozen=True)
class Room:
    """What the bound's build of a round with a plan in hand may take (`Pace.verdict`, #1099, #1135, #1224): its net is the round's whole
    share; `late` is how many times its net it may go past it, nearly done; `quarter` the part of its net past which it goes on only at a
    pace that ends within that room (the quarter `_envelope_plan.SEARCH_PER_BUILD` leaves the build of a round with no plan in hand). A plan
    a stopped search walked to (`_rounds.walked`, #1142) is in hand like a held one."""

    late: float = 0.0
    quarter: float = 0.25


class Tally(Pace):
    """The pieces of work of a bound's build counted against a cap, for a run that counts its work and not its seconds (#1101).

    A piece is a (member, offer) pair the builder looks at (`PatternBuilder`) or one offer's floor raised (`_offer_floor.OfferFloors`): what
    the build spends its time and memory on, the same on every machine. Called, it is the build's net: the reason once `Pace.verdict` stops
    the build at `done` pieces of its `cap` (`words(done, cap)`), else what `then` (another net, or None) says. With `room` (a round that
    began with a plan in hand, #1099, #1135, #1224) the cap is the round's whole share of pieces, and the build goes on past a quarter of it,
    or past it, as `Pace.verdict` says, counted in its pieces as the clock's net counts its seconds."""

    def __init__(self, cap: int, words: Callable[[int, int], str], then: Callable[[], str | None] | None = None, room: Room | None = None) -> None:
        super().__init__()
        self.cap, self.words, self.then, self.done, self.room = cap, words, then, 0, room
        self.late = False  # it went past `cap`, nearly done

    def used(self) -> float:
        return float(self.done)

    def __call__(self) -> str | None:
        stop = self.verdict(self.done, self.cap, self.room)
        if stop is not None:
            if stop == SHARE:
                said = self.words(self.done, self.cap)
            elif stop == PACE:
                said = f"it had done {self.done:,} of its {self.cap:,} pieces of work, and at the pace its model grew it would need about {self.need:,.0f}, more than it may take: the rest is left for the search"
            elif stop == OUTRUN:
                said = f"it had done {self.done:,} of its {self.cap:,} pieces of work, past the {self.forecast:,.0f} its model's pace of growth foretold, its next model unsolved, and with what it ran over charged to that pace it would need about {self.need:,.0f}, more than it may take: the rest is left for the search"
            else:
                said = f"it had done {self.done:,} of its {self.cap:,} pieces of work and its model had not grown past its first, so nothing showed that it would end within what it may take: the rest is left for the search"
            return said + (", the build having gone on past it, nearly done" if self.late else "")
        if self.done >= self.cap:
            self.late = True
        return None if self.then is None else self.then()


class PatternBuilder:
    """The model of the key, built on a list of offers that can grow: `extend` adds offers and builds only what they add (ticket #626).

    A model built on a part of the offers and grown by the ones that turn out to matter would cost a whole build for each round if each round began
    again; here a key that is expanded keeps its actions, and an offer added later is offered at the keys already expanded (its members, its kernels,
    each distinct kernel once) and at the keys it finds. `extend` returns a snapshot of the model, so a model returned stays what it was when the builder
    goes on. A build that stops (`stop`) leaves the builder unusable: the keys it had expanded do not all hold the offers being added, so the caller keeps
    the model of the round before. A universe that grows (a slot no member held) begins the build again at every key whose members it may change.

    What a universe decides is which states are members of a key; the keys (read off states, `Pattern.key`) and the kernels (the abstraction's, at
    a member, their successors' keys read off states) do not depend on it. So a build that begins again (#1086) keeps the keys and the kernels, and
    makes again the members and the row of each key a grown slot may be in (`Pattern.may_hold`); the other keys have the same members on the grown
    universe, so the same kernel keys and the same row. Every key a build from scratch on the grown universe reaches is reached, with the same row,
    and a kernel met again is not made again. A key may stay that it would not reach: a member that the grown universe replaced (the lightest or
    the first member of a key, where a new kind sorts before it) reached it. Such a key is read off a real state and has the row of its own
    members, so its value is a lower bound all the same, and no key reached leads to it: it changes no value reached. Before, every key began again: on R11 with the Exalted Orb four essences joined the bound's model with a forced
    mod the pool does not list, and the bound took 17.9 s on a runner where the model takes 5.6 s built at once.
    """

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        *,
        tags: bool | None = None,
        progress=None,
        max_keys: int | None = None,
        stop=None,
        grow: bool = False,
        approximate: bool = False,
        tally: "Tally | None" = None,
    ) -> None:
        self.tally = tally  # a build counted in pieces of work (`Tally`): each (member, offer) pair adds one, and the net is asked at every offer, never on the clock
        self.approximate = approximate  # the kernels are made in floats, shrunk and completed with the sink (see `_lowered`): a lower bound of the exact model
        self.grow = grow  # the builder will be extended: the members of a key are kept (they are made again for each offer added otherwise, and cost most of a round)
        self.ab = abstraction
        self.start = start
        self.tags = tags
        self.progress = progress
        self.max_keys = max_keys
        self.stop = stop
        self.offers: list[PatternOffer] = []
        self.restarts = 0
        self.began = time.perf_counter()
        self.dead = False
        self._reset()

    def _reset(self) -> None:
        before = getattr(self, "pattern", None)
        self.pattern = Pattern(self.ab, self.tags, [offer.action for offer in self.offers if offer.action is not None])
        if before is not None:
            # the build begins again because the universe grew: it begins on the grown universe. Made afresh, the universe would lose the slots the
            # kernels found (a fossil's added mods, which the pool does not list), find them again in the same pass, and begin again forever (#829:
            # a fossil world with bench crafts, the build ran past 25 minutes on CI, 109 restarts in a minute here)
            self.pattern.keep_universes(before)
            self.pattern._twin, self.pattern._lumped_read = before._twin, before._lumped_read  # the twin and what its lumped mods taught the universes
        self.stats = PatternStats()
        self.index: dict[PatternKey, int] = {}
        self.keys: list[PatternKey] = []
        self.goal: list[bool] = []
        self.rows: list[list[tuple[int, int]]] = []
        self.expanded: list[bool] = []
        self.kernel_ids: dict[tuple, int] = {}
        self.kernels: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        self.computed: Recent[int] = Recent(KERNEL_KEYS_KEPT or kept_entries(KERNEL_KEY_SHARE, KERNEL_KEY_BYTES))  # kernel key of the abstraction -> kernel id of the model, the keys asked lately (#1335); each stored with its parts shared (`_shared_parts`, #1332)
        self.parts: dict = {}  # one object for each distinct part of the kernel keys stored since `computed` last let a generation go (`_shared_parts`)
        self.parts_of = 0  # the generation of `computed` that `parts` serves
        self.gaps: dict = {}  # (key, offer index) -> whether no member of the key can take the action (see `_gap_everywhere`)
        self.done = 0  # the number of offers every expanded key has been given (each built there unless it is held at some keys only)
        self.wide: list[int] = []  # the offers built at every key, in order
        self.narrow: dict[int, set[int]] = {}  # an offer built only at some keys (#1325): offer number -> the numbers of those keys
        self.at_key: dict[int, list[int]] = {}  # key number -> the offers held at it only (`narrow`)
        self.pending: dict[int, list[int]] = {}  # an expanded key -> the offers of `narrow` it is to be given at the next pass
        self.members_kept: dict[int, dict[tuple[Mode, frozenset[str], tuple | None], list[CompressedState]]] = {}
        self.relaxed: dict[tuple, int] = {}  # (member, action) -> the kernel id of the row that enters its relaxed draw (`_relaxed_rows`)
        self.relaxed_made = 0  # how many relaxed draws were made: each one's name, kept across `_begin_again` so no two choice nodes are equal
        self.pattern.note(self.start)
        self.start_id = self._intern(self.start)

    def _intern(self, state: CompressedState) -> int:
        key = self.pattern.key(state)
        found = self.index.get(key)
        if found is None:
            found = self.index[key] = len(self.keys)
            self.keys.append(key)
            self.goal.append(self.ab.is_goal(state))
            self.rows.append([])
            self.expanded.append(False)
            if self.max_keys is not None and len(self.keys) > self.max_keys:
                raise RuntimeError(f"more than {self.max_keys} keys")
        return found

    def extend(
        self, offers: Sequence[PatternOffer], at: Sequence[Iterable[int] | None] | None = None, spread: dict[int, Iterable[int]] | None = None
    ) -> PatternModel:
        """Add `offers` to the model and build what they add; the snapshot of the model, with `stopped` set if a net ended the build.

        `at` (one entry an offer, #1325): the numbers of the expanded keys an offer is built at, None for every key. An offer held at some keys only is
        not built at any other key, nor at a key found later; the model's `narrow` says where it is, and the bound's floor action carries its floor
        at every other key (`_pattern_bound`). `spread`: offers already held at some keys (offer number -> keys) that are to be built at these too."""
        if self.dead:
            raise RuntimeError("the build was stopped; use the model of the round before")
        first = len(self.offers)
        self.offers.extend(offers)
        if self.done == 0 and not any(self.expanded):
            # nothing is expanded yet: the names of the offers seed the universe before the first pass, as `build_pattern_model` always did. Seeding them
            # as an addition would count as growth and begin the whole first pass again (R04: a second pass of 280 s where the model takes 96 s).
            self._reset()
            self._place(first, at, spread)
        else:
            self._place(first, at, spread)
            self.pattern.grew = 0
            self.pattern.grown = []
            self.pattern.add_actions([offer.action for offer in offers if offer.action is not None])
            if self.pattern.grew:  # the names of the offers that join grew the universe: the keys they fit begin again before the pass
                self.restarts += 1
                self._begin_again()
        while True:  # each pass that grows the universe adds slots to a finite set, so this ends; a pass that adds none is the answer
            stopped = self._pass()
            if stopped is not None:
                self.dead = True
                if self.pattern.grew:
                    self.expanded = [False] * len(self.keys)
                    self.rows = [[] for _ in self.keys]
                return self._snapshot(stopped)
            if not self.pattern.grew:
                return self._snapshot(None)
            self.restarts += 1
            self._begin_again()

    def _place(self, first: int, at, spread) -> None:
        """Record where the offers from number `first` on are built (`extend`), and give each expanded key the ones it is to be given."""
        for n, oi in enumerate(range(first, len(self.offers))):
            keys = None if at is None else at[n]
            if keys is None:
                self.wide.append(oi)
            else:
                self.narrow[oi] = set()
                self._hold(oi, keys)
        for oi, keys in (spread or {}).items():
            self._hold(oi, keys)

    def _hold(self, oi: int, keys: Iterable[int]) -> None:
        holders = self.narrow[oi]
        for k in keys:
            if k in holders:
                continue
            holders.add(k)
            self.at_key.setdefault(k, []).append(oi)
            if self.expanded[k]:
                self.pending.setdefault(k, []).append(oi)

    def _given(self, i: int) -> list[int]:
        """The offers key number `i` is to be given at this pass: all it holds when it is not expanded, else the ones added since."""
        if not self.expanded[i]:
            return sorted([*self.wide, *self.at_key.get(i, ())]) if self.narrow else self.wide
        new = self.wide[bisect_left(self.wide, self.done) :]
        pending = self.pending.get(i)
        return sorted([*new, *pending]) if pending else new

    def _begin_again(self) -> None:
        """The universe grew (`Pattern.grown`): every expanded key a grown slot may be in is made again (members, row, gaps); keys and kernels stay."""
        grown, pattern = self.pattern.grown, self.pattern
        again = {
            i for i, key in enumerate(self.keys)
            if self.expanded[i] and not isinstance(key, ChoiceNode) and any(pattern.may_hold(key, influences, slot) for influences, slot in grown)
        }
        self.relaxed = {}  # a relaxed draw reads the universe's classes: the keys made again make theirs again
        for i in again:
            self.rows[i] = []
            self.expanded[i] = False
            self.members_kept.pop(i, None)
            self.pending.pop(i, None)  # made again from the start: it is given all it holds
        keys = {self.keys[i] for i in again}
        self.gaps = {found: value for found, value in self.gaps.items() if found[0] not in keys}
        self.stats.restarted_keys += len(again)
        pattern.grew = 0
        pattern.grown = []

    def _snapshot(self, stopped: str | None) -> PatternModel:
        stats = replace(self.stats)
        stats.keys = len(self.keys)
        stats.goal_keys = sum(self.goal)
        stats.fallbacks = self.pattern.fallbacks
        stats.universe_growth = self.restarts
        stats.abstract_actions = sum(len(row) for row in self.rows)
        stats.abstract_edges = sum(len(self.kernels[kid][0]) for row in self.rows for _, kid in row)
        stats.seconds = time.perf_counter() - self.began
        stats.modes = Counter(self.stats.modes)
        return PatternModel(
            list(self.keys), list(self.goal), [list(row) for row in self.rows], list(self.kernels), stats, dict(self.index), list(self.expanded), stopped,
            {oi: frozenset(keys) for oi, keys in self.narrow.items()},
        )

    def _pass(self) -> str | None:
        """Expand every key for the offers it lacks; the reason a net ended it, or None when it ran to the end.

        The net on the clock and on memory is asked inside the making of a key's members and of one kernel too (`budget.asking`, #1217, #1238),
        not only between two offers: either can run for minutes and take gigabytes. A build counted in pieces of work asks at its pieces alone."""
        with self.ab.approximate() if self.approximate else nullcontext():
            try:
                with budget.asking(self.stop if self.tally is None else None):
                    return self._pass_keys()
            except budget.NetReached as reached:  # inside a making: the key's row is whole or untouched, as at a stop between two offers
                self._release()
                return reached.reason

    def _pass_keys(self) -> str | None:
        pattern, offers, stats, progress = self.pattern, self.offers, self.stats, self.progress
        last = polled = time.perf_counter()
        i = 0

        def tick(oi: int, inner: bool = False) -> None:
            """Between two offers: ask the net, and say where the build is every 30 seconds (a key can take minutes: no longer one silent step).

            `inner`: asked inside one offer's work too, between two members of the key and between two pairs that `_prime` prepares (#1179: one
            chunk of R14's Harvest swaps over a key's members ran past the run's net for minutes). Only on the clock: a run counted in pieces asks
            at every offer, as before, so that where it stops stays the same on every machine."""
            nonlocal last, polled
            if inner and self.tally is not None:
                return
            now = time.perf_counter()
            if self.tally is None:  # counted in pieces of work, the net is asked at every offer: where it stops must not depend on the machine's speed
                if now - polled < POLL_SECONDS:
                    return
                polled = now
            if self.stop is not None:
                reason = self.stop()
                if reason is not None:
                    raise _Stopped(reason)
            if progress is not None and now - last >= 30:
                last = now
                progress(
                    f"keys found {len(self.keys):,} expanded {i:,} (now offer {oi + 1:,} of {len(offers):,} of key {i:,}) kernels {stats.kernels:,} members {stats.members:,}"
                )

        while i < len(self.keys):
            if self.stop is not None and (reason := self.stop()) is not None:
                return reason
            if isinstance(self.keys[i], ChoiceNode):  # a node of a relaxed draw: its rows were made with it
                self.expanded[i] = True
                i += 1
                continue
            if not self.goal[i]:
                given = self._given(i)
                if given:
                    firsts = None
                    if not self.expanded[i]:  # a key expanded before had a member: the universe only grows
                        firsts = (pattern.members(self.keys[i], Mode.ANY), pattern.grew)
                        if not firsts[0]:
                            raise _no_member(self.keys[i])
                    try:
                        self._offers_of_key(i, given, tick, firsts)
                    except _Stopped as reached:
                        self._release()
                        return reached.reason
                    self._release()
            self.pending.pop(i, None)
            self.expanded[i] = True
            i += 1
            now = time.perf_counter()
            if progress is not None and now - last >= 30:
                last = now
                progress(f"keys found {len(self.keys):,} expanded {i:,} kernels {stats.kernels:,} members {stats.members:,}")
        self.done = len(offers)
        return None

    def _release(self) -> None:
        """Drop the pairs prepared for one key, in the abstraction and in the pattern's twin (`Abstraction.release_prepared`)."""
        self.ab.release_prepared(keep_erased=True)
        if self.pattern._twin is not None:
            self.pattern._twin.release_prepared(keep_erased=True)

    def _prime(self, key: PatternKey, chunk: Sequence[int], members_for: Callable[[tuple[Mode, frozenset[str], tuple | None]], list[CompressedState]], ask: Callable[[], None] | None = None) -> None:
        """Make, side by side in a process pool, the exact distributions that the offers numbered `chunk` need at the members of `key` (ticket #250, #626).

        The kernel of a fossil set is a distribution of seconds, computed once per pool and cached; a model built on hundreds of offers asked for them
        one after the other. Nothing is built here and nothing changes in the answer; with one worker, or no `fork`, this does nothing. A chunk is
        at most `PRIME_CHUNK` offers so that the net is asked between chunks; the pool's `map` cannot be interrupted, so a net is overshot by at most one chunk.
        `ask` (the build's tick) is called between two pairs the chunk prepares before the pool starts, and raises when the net is reached (#1179).
        """
        requests = []
        for offer in (self.offers[oi] for oi in chunk):
            if offer.action is None or offer.action.imprint_move() is not None or _refused_by_key(self.pattern, offer.action, key):
                continue
            if not self.pattern.draws(offer.action):
                # nothing is drawn (a bench craft, a Fracturing Orb, an Annulment): no walk to make ahead, and preparing its pairs here would
                # make the item of every member, the ones the build then answers without one too (a certain addition, a refusal of the key;
                # #1193: on R04's 19 offers the Fracturing Orb's pairs were prepared at every pure junk assignment of every key)
                continue
            policy = self.pattern.asked(offer.action, key)
            if policy[0] is Mode.RELAXED:  # no fine kernel is made for a relaxed draw
                continue
            members = members_for(policy)  # the key's members of the policy, made once (`_offers_of_key`)
            last = self.ab.quality_last_action(offer.action)
            requests.extend(
                (member, offer.action)
                for member in members
                if not (LUMP_ERASING and self.ab.lumps(member, offer.action))
                # the pairs `_offers_of_key` skips where only the quality is left, or a catalyst before it (#159): no kernel is made for them
                and not (self.ab.quality_offer_pruned(member, offer.action) if last else self.ab.quality_finish_only(member, offer.action))
            )
        self.ab.prime(requests, ask=ask)

    def _offers_of_key(self, i: int, given: Sequence[int], tick, firsts: tuple[list[CompressedState], int] | None = None) -> None:
        """Add to the row of key number `i` the abstract actions of the offers numbered `given` (one `(offer index, kernel id)` for each distinct pushed kernel).

        `firsts`: the members of the key for `Mode.ANY` that the pass made to check the key has one, with the pattern's growth count then. The
        offers of policy `ANY` take them while the universe has not grown since (#1256: each key made them twice, 7 s of R04's round 8); they are
        the list `members` would make again, so the build is the same."""
        pattern, ab, stats, offers = self.pattern, self.ab, self.stats, self.offers
        key = self.keys[i]
        by_mode: dict[tuple[Mode, frozenset[str], tuple | None], list[CompressedState]] = self.members_kept.setdefault(i, {}) if self.grow else {}
        anyone = (Mode.ANY, frozenset(), None)

        def members_for(policy: tuple[Mode, frozenset[str], tuple | None]) -> list[CompressedState]:
            members = by_mode.get(policy)
            if members is None:
                if policy == anyone and firsts is not None and firsts[1] == pattern.grew:
                    members = firsts[0]
                else:
                    members = pattern.members(key, *policy[:2]) if policy[2] is None else pattern.members(key, *policy)
                by_mode[policy] = members
                stats.members += len(members)
            return members
        added: list[tuple[int, int]] = []
        for n, oi in enumerate(given):
            offer = offers[oi]
            tick(oi)
            if n % PRIME_CHUNK == 0 and len(given) >= PRIME_FROM:
                self._prime(key, given[n : n + PRIME_CHUNK], members_for, lambda: tick(oi, True))
            if offer.action is None:
                if i != self.start_id:
                    added.append((oi, _kernel_id(self.kernel_ids, self.kernels, {self.start_id: Fraction(1)})))
                continue
            if _refused_by_key(pattern, offer.action, key):
                continue
            move = offer.action.imprint_move()
            if move is not None:  # an imprint or a restore: one certain successor key, the same at every member that takes it (#833)
                stats.modes[("move", offer.label)] += 1
                kid = self._move(key, offer, move)
                if kid is not None:
                    added.append((oi, kid))
                continue
            policy = pattern.asked(offer.action, key)
            members = members_for(policy)
            stats.modes[(policy[0].value + ("+named" if policy[1] else ""), offer.label)] += 1
            certain = SHARE_ADDITIONS and pattern.adds_only_named(offer.action)
            classed = ab.refusal_class_of(offer.action) if SHARE_REFUSED else None
            keyed = SHARE_KEY_REFUSALS and classed is not None and ab.refusal_names_no_junk(offer.action)
            refused_at_key = False  # a member's refusal class, which is the key's (`keyed`), holds a refusal: every member's does
            seen: set[int] = set()
            by_view: dict[frozenset, int] | None = {} if pattern.views_only(offer.action) else None  # the views of a member -> its answer (#1338)
            last = ab.quality_last_action(offer.action)  # a catalyst: an action only of a member that meets all but the quality (#159)
            if policy[0] is Mode.RELAXED:
                relaxed = self._relaxed_rows(key, oi, offer, members, last, tick)
                if relaxed is not None:
                    added.extend((oi, kid) for kid in dict.fromkeys(relaxed))
                    continue
                members = pattern.members(key, Mode.ALL)  # the relaxed draw does not hold at a member: every member, exactly
                stats.members += len(members)
            for member in members:
                tick(oi, True)
                if ab.quality_offer_pruned(member, offer.action) if last else ab.quality_finish_only(member, offer.action):
                    # exact: a catalyst is pruned at every such state by the search too (`_envelope_plan`); another action where only the quality
                    # is left changes no value (`Abstraction.quality_finish_only`), and the search then leaves it out there as the model does
                    continue
                if certain and seen:  # a certain addition taken at a member: this one adds that same kernel (module docstring, #1193)
                    stats.pairs += 1
                    stats.shared_pairs += 1
                    if self.tally is not None:
                        self.tally.done += 1
                    continue
                stats.pairs += 1
                if self.tally is not None:
                    self.tally.done += 1
                if refused_at_key:  # the class of this member is the one that member was refused in (module docstring, "Refusals", #1193)
                    stats.refused_pairs += 1
                    ab.refusals_shared += 1
                    continue
                found = classed(member) if classed is not None else None
                if found is not None and ab.refused_in_class(found):
                    # a refusal met in the pair's class: what `kernel_key` would raise here (module docstring, "Refusals", #1256)
                    stats.refused_pairs += 1
                    refused_at_key = keyed
                    continue
                view = None
                if by_view is not None:
                    view = pattern.view(member)
                    kid = by_view.get(view)
                    if kid is not None:  # a member with these views was asked: its answer is this one's (module docstring, #1338)
                        stats.view_pairs += 1
                        if kid == REFUSED:
                            stats.refused_pairs += 1
                        elif kid == GAP:
                            stats.gap_pairs += 1
                        elif kid not in seen:
                            seen.add(kid)
                            added.append((oi, kid))
                        continue
                try:
                    ck = ab.kernel_key(member, offer.action)
                except NotApplicableError:
                    stats.refused_pairs += 1
                    refused_at_key = keyed and found is not None and ab.refused_in_class(found, count=False)
                    if view is not None:
                        by_view[view] = REFUSED
                    continue
                except OutOfScopeError as gap:
                    if _gap_everywhere(pattern, self.gaps, key, offer):
                        stats.gap_pairs += 1
                        if view is not None:
                            by_view[view] = GAP
                        continue
                    raise _gap(offer, key, gap) from gap
                kid = self.computed.get(ck)
                if kid is None:
                    lumped = LUMP_ERASING and ab.lumps(member, offer.action)  # its outcomes from the twin, pushed onto the same keys (#1146)
                    try:
                        if lumped:
                            with pattern.twin.approximate() if self.approximate else nullcontext():
                                exact = pattern.twin.kernel(member, offer.action)
                        else:
                            exact = ab.kernel(member, offer.action)
                    except NotApplicableError:
                        stats.refused_pairs += 1
                        if view is not None:
                            by_view[view] = REFUSED
                        continue
                    except OutOfScopeError as gap:
                        if _gap_everywhere(pattern, self.gaps, key, offer):
                            stats.gap_pairs += 1
                            if view is not None:
                                by_view[view] = GAP
                            continue
                        raise _gap(offer, key, gap) from gap
                    stats.kernels += 1
                    if lumped:
                        pattern.note_lumped()
                    pushed: dict[int, Fraction] = defaultdict(Fraction)
                    for successor, chance in exact.items():
                        if not lumped:  # a lumped outcome holds no slot the universe lacks (`LUMP_ERASING`), and its kinds are the twin's
                            pattern.note(successor)
                        pushed[self._intern(successor)] += chance
                    if self.approximate:
                        pushed = _lowered(pushed)
                    if self.parts_of != self.computed.generation:  # the keys that held the parts are going: the parts go with them (#1335)
                        self.parts, self.parts_of = {}, self.computed.generation
                    kid = self.computed[_shared_parts(self.parts, ck) if SHARE_KEY_PARTS else ck] = _kernel_id(self.kernel_ids, self.kernels, pushed)
                if view is not None:
                    by_view[view] = kid
                if kid not in seen:
                    seen.add(kid)
                    added.append((oi, kid))
        self.rows[i].extend(added)  # the row of a key is whole or untouched: a stop in the middle leaves it as it was

    def _relaxed_rows(self, key: PatternKey, oi: int, offer: PatternOffer, members, last: bool, tick) -> list[int] | None:
        """The kernel ids of the rows that enter the relaxed draws of `offer` at the `ONE` members of `key` (`_relaxed`), None where one does
        not hold (the caller then makes every member). A member the game refuses gives no row; a model gap is treated as at a member."""
        pattern, ab, stats = self.pattern, self.ab, self.stats
        found: list[int] = []
        for member in members:
            tick(oi, True)
            if ab.quality_offer_pruned(member, offer.action) if last else ab.quality_finish_only(member, offer.action):
                continue
            stats.pairs += 1
            if self.tally is not None:
                self.tally.done += 1
            cache = (member, offer.action)
            kid = self.relaxed.get(cache)
            if kid is None:
                try:
                    draw = relaxed_draw(pattern, member, offer.action, offer.action.held_weight_factor())
                except NotApplicableError:
                    stats.refused_pairs += 1
                    continue
                except OutOfScopeError as gap:
                    if _gap_everywhere(pattern, self.gaps, key, offer):
                        stats.gap_pairs += 1
                        continue
                    raise _gap(offer, key, gap) from gap
                if draw is None:
                    return None
                owner = self.relaxed_made
                self.relaxed_made += 1
                ids = []
                for at in range(len(draw.nodes)):
                    ids.append(len(self.keys))
                    self.keys.append(ChoiceNode(owner, at))
                    self.goal.append(False)
                    self.rows.append([])
                    self.expanded.append(True)
                for node, kernels in zip(ids, draw.nodes):
                    for kernel in kernels:
                        pushed: dict[int, Fraction] = defaultdict(Fraction)
                        for target, chance in kernel.items():
                            if isinstance(target, int):
                                pushed[ids[target]] += chance
                            else:
                                pattern.note(target)
                                pushed[self._intern(target)] += chance
                        self.rows[node].append((CHOICE, _kernel_id(self.kernel_ids, self.kernels, pushed)))
                        stats.kernels += 1
                kid = self.relaxed[cache] = _kernel_id(self.kernel_ids, self.kernels, {ids[0]: Fraction(1)})
            found.append(kid)
        return found

    def _move(self, key: PatternKey, offer: PatternOffer, move) -> int | None:
        """The kernel id of the imprint or restore `offer` at `key`, or None where no member needs it (#833, "The imprints" in the module docstring).

        Its kernel is asked of one member (`Mode.ANY`): the game's refusals (rarity, a Talisman, a fracture, a corruption, the cap, the index) read
        the key alone. The rule that refuses an imprint of a state already held, and a restore onto the state the item is in, reads the member: it
        fires at the member that is the snapshot the members hold of its own key. A restore refused so is dominated and left out; an imprint is
        asked of another member of the key, unless it would replace that very snapshot (its successor is then the key itself).
        """
        pattern, ab, stats = self.pattern, self.ab, self.stats
        firsts = pattern.members(key, Mode.ANY)  # the caller checked that the key has a member
        member = firsts[0]
        stats.pairs += 1
        try:
            exact = ab.kernel(member, offer.action)
        except NotApplicableError:
            stats.refused_pairs += 1
            bare = replace(member, imprints=())
            if move.restore or bare not in member.imprints:
                return None
            if move.index is not None and (move.index >= len(member.imprints) or member.imprints[move.index] == bare):
                return None  # the game's refusal (no such imprint to give up), or a replacement that leads back to the key
            exact = None
            for other in _then_all(pattern, key, firsts[1:], stats):  # the members already made first: every member only if none of them will do
                if replace(other, imprints=()) in other.imprints:
                    continue
                stats.pairs += 1
                try:
                    exact = ab.kernel(other, offer.action)
                except NotApplicableError:
                    stats.refused_pairs += 1
                    return None
                break
            if exact is None:
                return None
        except OutOfScopeError as gap:  # model gaps: none for a move of the imprints, which reads nothing of the mods
            raise _gap(offer, key, gap) from gap
        stats.kernels += 1
        pushed: dict[int, Fraction] = defaultdict(Fraction)
        for successor, chance in exact.items():
            pattern.note(successor)
            pushed[self._intern(successor)] += chance
        return _kernel_id(self.kernel_ids, self.kernels, pushed)


def _then_all(pattern: Pattern, key: PatternKey, firsts: Sequence[CompressedState], stats: PatternStats) -> Iterator[CompressedState]:
    """`firsts`, then every member of `key` (`Mode.ALL`, made only if the caller goes on past `firsts`)."""
    yield from firsts
    every = pattern.members(key, Mode.ALL)
    stats.members += len(every)
    yield from every


def _refused_by_key(pattern: Pattern, action: Action, key: PatternKey) -> bool:
    """Whether the game refuses `action` at every member of `key` by the key alone: the draw of a bought listing's mods works only on the
    unopened listing and every other action only on an opened item (`Abstraction._prepare`), and whether the item is unopened is a flag of the key;
    an action that needs the veiled placeholder (`Reads.needs_veiled`: an unveil, a pick) is refused at a key that does not hold it, and the
    placeholder is in the key (`PatternKey.veiled`, #828).

    No member is made for such an offer: the draw reads every family, so it made them all at every key (#830: 99,272 of the 103,250 pairs of
    divine-roll-limits/medium); the unveil and the three picks were asked at every member of every key (#828: 98,572 times each on R07).
    """
    if bool(getattr(action, "opens_listing", False)) != bool(getattr(key.flags, "unopened", False)):
        return True
    return pattern.reads(action).needs_veiled and not pattern.holds_placeholder(key)


class _Stopped(Exception):
    """Raised by the tick of a build when a net is reached, inside the expansion of one key."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _no_member(key: PatternKey) -> OutOfScopeError:
    """The refusal of a build that reached a non-goal key it can make no member of: a defect of the member builder, never a fact about the game.

    The concrete state that reached the key is itself an item of the key, so the key has a member. With none, the key would keep only the
    restart, and its value, and every value that leans on it, would sit above the exact cost: a bound that a cut would trust (OR-12, OR-13).
    """
    refusal = OutOfScopeError(
        f"the crafted-pattern bound reached a key it can make no member of (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}, tags {key.tags}, rarity {key.flags.rarity.value}, {len(key.fractured)} fractured). That is a defect of the member "
        "builder, since the state that reached the key is a member of it; its value would sit above the exact cost, so the build refuses."
    )
    refusal.player = (  # type: ignore[attr-defined]  # what `make_plan` says under `solver="auto"` (#535, OR-13); the text above is the developer's
        "the planner met a fault of its own while working out the cheapest possible cost of each kind of item the crafting can reach"
    )
    return refusal


def _gap_everywhere(pattern: Pattern, memo: dict, key: PatternKey, offer: PatternOffer) -> bool:
    """Whether no member of the key can take the action: each is refused by the game or is a model gap.

    Then the exact model has no action at any state of the key either (a gap makes it unavailable, as the walk and the planner do), so leaving
    it out of the key is what the exact model does. If one member can take it, a gap at the member that was asked may not be left out.
    """
    found = memo.get((key, id(offer)))
    if found is None:
        found = True
        for member in pattern.members(key, Mode.ALL):
            try:
                pattern.ab.kernel_key(member, offer.action)
            except (NotApplicableError, OutOfScopeError):
                continue
            found = False
            break
        memo[(key, id(offer))] = found
    return found


def _gap(offer: PatternOffer, key: PatternKey, gap: Exception) -> OutOfScopeError:
    """The refusal of a build that met a model gap at a member: the action cannot be dropped from the key without risking a bound above the exact cost."""
    refusal = OutOfScopeError(
        f"{offer.label} raised a model gap at a member of a key (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}) while another member of the key can take it: {gap}. The crafted-pattern bound cannot drop the action from the "
        "key (the exact model drops it only where the gap is), so it refuses the route instead of returning a bound that may be above the "
        "exact cost (OR-12, OR-13)."
    )
    refusal.player = (  # type: ignore[attr-defined]  # what `make_plan` says under `solver="auto"` (#535, OR-13); the text above is the developer's
        f"the planner has no rule for {offer.label} on some of the items the crafting can reach, while it has one on others like them, so it "
        "cannot work out the cheapest possible cost of that action there"
    )
    return refusal


def _lowered(pushed: dict[int, Fraction]) -> dict[int, Fraction]:
    """A kernel made in floats as a kernel that is below the exact one: each chance shrunk by `SHRINK`, the mass that is missing given to `SINK`.

    A kernel with no float in it (a deterministic result, or a draw made exactly) is the exact one and stays. The chances of a float kernel are
    positive sums and products of at most a few dozen steps, each with a relative error of 2^-53, so each is within 1e-13 of its exact value and
    `chance x SHRINK` is below the exact one; a total above one after the shrink would mean an error far above that, and is refused.
    """
    if not any(isinstance(chance, float) for chance in pushed.values()):
        return pushed
    lowered = {successor: Fraction(chance) * SHRINK for successor, chance in pushed.items()}
    missing = 1 - sum(lowered.values(), Fraction(0))
    if missing < 0:
        raise RuntimeError(f"a float kernel adds up to more than one after its chances were shrunk by 2^-30 (by {float(-missing):.3g}): its error is far above the float error")
    if missing:
        lowered[SINK] = missing
    return lowered


def _shared_parts(parts: dict, key):
    """`key` with each of its parts (a tuple, a frozenset, a hashable leaf) replaced by the one equal part `parts` holds, which is added when
    there is none (#1332): the stored key equals `key`, so a lookup of `computed` finds what it found before, and the parts many keys repeat
    are held once.

    A kernel key (`Abstraction.kernel_key`) is a fresh tuple of every part of the pair it reads, and the keys of one model repeat most of
    them: the flags, the slots kept and added, the status of each leaf, the pool signature. Stored as made, the keys held about 4.5 KB each,
    3.4 GB of R13's first bound of 742,710 kernel keys at 10 minutes and 6.9 GB of R04's of 1,347,857 at 11 minutes, more than every other
    store of the build together (`.claude/scratch/t1332`, a sampled run, #1332). With the parts shared, R13's keys at 6 minutes took 348 MB
    in place of 1,954 MB, with 1.69 million distinct parts. A part equal to another of another type (1 and `Fraction(1)`, `True` and 1) may
    be held as the other: they are equal and hash alike, so no lookup tells them apart."""
    kind = type(key)
    if kind is tuple:
        key = tuple([_shared_parts(parts, part) for part in key])
    elif kind is frozenset:
        key = frozenset([_shared_parts(parts, part) for part in key])
    return parts.setdefault(key, key)


def _kernel_id(ids: dict[tuple, int], kernels: list, pushed: dict[int, Fraction]) -> int:
    """The id of a pushed kernel (successor keys with integer weights, gcd-reduced), interned."""
    items = sorted(pushed.items())
    common = lcm(*(chance.denominator for _, chance in items))
    weights = [chance.numerator * (common // chance.denominator) for _, chance in items]
    divisor = reduce(gcd, weights)
    entry = (tuple(k for k, _ in items), tuple(w // divisor for w in weights))
    found = ids.get(entry)
    if found is None:
        found = ids[entry] = len(kernels)
        kernels.append(entry)
    return found


__all__ = ["CHOICE", "ChoiceNode", "Growth", "LATE", "Mode", "OUTRUN", "PACE", "Pace", "Pattern", "PatternBuilder", "PatternKey", "PatternModel", "PatternOffer", "PatternStats", "QUARTER", "Room", "SHARE", "Tally", "build_pattern_model"]
