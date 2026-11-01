# Unveiling is a chance node, then a choice node

A veiled mod is a placeholder that takes a prefix or suffix slot until it is unveiled. Unveiling shows three mods and the player picks one, so the solver cannot treat it as one random action: the offer is chance, the pick is the policy's. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) fixes how the two are encoded. The mechanics are in [the veiled research](https://github.com/Rasslabsya4el/crafting-system/issues/87).

## The orbs

- **Veiled Chaos Orb** is a Chaos Orb reroll that guarantees one veiled placeholder, counted inside the drawn 4/5/6 mods. It goes to the only side with room, otherwise to prefix or suffix with chance 1/2. **The veil ignores a lock with room** (Craft of Exile; the wiki has no row for it; marked approximate): a side locked by `Prefixes/Suffixes Cannot Be Changed` that has an open slot can take it. It is refused when a veiled mod would be kept (on a locked side or fractured).
- **Veiled Exalted Orb** removes one mod, uniformly among those not on a locked side and not fractured (crafted mods and metamods included; the Attack/Caster blocks do not protect), then adds a placeholder by the same side rule. It is refused on an item that holds a veiled mod, its bench version, **or a mod unveiled from the pool** (the owner's answer, as far as the owner knows).
- An item holds at most one placeholder from the orbs. The signature veiled mods are not in their pools. A start item with a signature or a double veil is out of v1.

## The two nodes

1. **Chance node.** The unveil action draws the offer: up to three mods from the unveiled pool of the placeholder's side, by weight (the first spawn tag the base has), without replacement and one mod per family, after removing the families already on the item. The offer is drawn **when the unveil is taken and stays fixed**: closing and reopening shows the same three (the owner). There is no free second look, so a loop that unveils, blocks and unveils again pays for a new veil each time. A pool has at most 546 distinct offers. There is **no offer filter**: `Cannot roll Attack Modifiers` does not thin it and no item level gates it (Craft of Exile, marked approximate).
2. **Choice node, the offer state.** The state holds the item with the placeholder and the offer. **The only actions in it are Pick(k)**, one per shown mod; there is no decline, so an item in an offer state cannot be left. Unveiling and every pick cost a small epsilon, not zero, so the solver's positive-cost rule holds; the pick is acyclic, so the epsilon does not threaten the proper-policy test. The offer state is compressed by the ordinary rules (ADR-0009): mods that give no requirement and block nothing are counted by family type.

An **unveil block** is a bench craft of a family in the unveil pool: the family leaves the next offer, because explicit mods, bench crafts included, block options. The craft is an ordinary bench action taken before the unveil, and the planner offers it as a block when its family is in the pool of the placeholder (it need not give the target anything itself). R02 and R30 use it.

## Open

Whether a block crafted **after** seeing the offer redraws it is unknown: the export carries a per-placeholder `veiled_mod_seed` that may fix the offer for good. Until someone checks, the offer is drawn once and never redrawn; this is the more cautious reading, so a route that blocks after the peek is not offered. The claim says so and carries `approximate` (ADR-0028).

## What this changes in the solver

- The state holds the placeholders (side, no family, not crafted) and, in an offer state, the offer. The pool signature of Unveil includes the side, the base's pool and the families on the item.
- The actions read and add through ADR-0027 (implicits, the offer).
- Unveil and Pick are not block-invariant (ADR-0023): they refuse the coarse state until a ticket proves them.

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions V-01, V-02, V-06 by the main chat; the owner's round 1 answers on the offer and the Veiled Exalted Orb); [Veiled mods and unveiling](https://github.com/Rasslabsya4el/crafting-system/issues/87); ADR-0009, ADR-0013, ADR-0023.

## Amendment: the actions ([#144](https://github.com/Rasslabsya4el/crafting-system/issues/144))

`actions/veiled.py` holds the four actions (claims `veiled.yaml` and `unveil.yaml`, kinds `veiled-chaos-orb`, `veiled-exalted-orb`, `unveil`, `pick`; none a planner kind until the compressed model has the placeholder slot and the offer state, #145):

- `VeiledChaosOrb` is a `Mixture` of one pool draw per side the veil can take, each `Outcomes.reroll` with the placeholder (`VeiledPrefix` or `VeiledSuffix`) as the forced mod, so the veil counts inside the total of 4, 5 or 6. A drawn offer goes with the placeholder it belonged to. It reads nothing of the junk and declares the offer flag (it throws an offer away).
- `VeiledExaltedOrb` is a `Finite`: one result per removable mod and per side with room after the removal. It reads the families of the placeholder and of the unveiled pool. A mod unveiled from a family that an ordinary mod shares (Movement Speed on boots) is the same kind of slot as that mod in a compressed state, so #145 must tell the domains apart for the refusal after an unveil to be exact. A "craftable version" of a veiled mod is a crafted mod of Jun's bench (`JunMaster...`) with the side and the stat ids of an unveiled mod (928 of 994, research VEI-20); the canonical id of a crafted slot (same families, side, contribution) can merge a craftable version with another crafted mod of its family, which #145 must also keep apart.
- `Unveil` is a `Finite` with one result per offer (at most 546 per pool) and an empty `resources`: it is free, and the epsilon of this ADR belongs to the compressed model (#145). It refuses an item whose offer is drawn, and works on a corrupted item (the veiled orbs refuse corrupted items).
- `Pick(k)`, k = 1 to 3, takes the k-th mod of the offer **in mod id order** (the order `Item.veil_offer` keeps), at its lowest values.
- A signature placeholder and a double veil raise `OutOfScopeError` in all four; a jewel has no veiled pool, so the two orbs refuse it (`OutOfScopeError`).
- The one-mod-per-family rule of the offer counts **every** family of a mod, as `Item` does when it checks an offer. Craft of Exile's `poec_simUnveilMod` compares every modgroup of a picked mod with every modgroup of the others (its data holds 13 hybrid generic mods with 2 or 3). The research's figure for the wand's Minion attack and cast speed (0.194) counts the first family only; with every family, as the code and `Item` do, it is 0.1996 on the 3.29.3.3 export. The boots and helmet figures hold both ways.
