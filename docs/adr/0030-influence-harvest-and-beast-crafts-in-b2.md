# Influence, Harvest and beast crafts in B2 follow the data, then Craft of Exile

B2's single-item additions that are not Eldritch, veiled or catalysts: the influenced Exalted Orbs, the Orb of Dominance, the Harvest add/remove and swap crafts, and the beasts. For each the research ([#86](https://github.com/Rasslabsya4el/crafting-system/issues/86), [#88](https://github.com/Rasslabsya4el/crafting-system/issues/88)) left points no source settles. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) settled them by the evidence rule (ADR-0005, [#28](https://github.com/Rasslabsya4el/crafting-system/issues/28)): where the owner knows, the owner's answer; where nothing speaks, Craft of Exile, and the claim carries `approximate` (ADR-0028).

## Influenced Exalted Orbs and the Orb of Dominance

- Six orbs (Shaper's, Elder's, Crusader's, Hunter's, Redeemer's, Warlord's) add their influence and one mod of it to a rare item with an open slot and item level 68 or more. The mod is drawn only from that influence's mods, through the shared draw (item level, family exclusion, weights, side locks, Attack/Caster blocks). They are refused on **every item that already has an influence, the orb's own included, and on an item with an Eldritch implicit** (the owner has not checked; an optional in-game check may change it, #86 O-01 and O-02), and on fractured and synthesised items. An empty pool refuses the orb.
- The **Orb of Dominance** (body armour, boots, gloves, helmet, with two influenced mods) removes one influenced mod and upgrades another by one tier; a top-tier mod becomes its Elevated version. Both picks are uniform (Craft of Exile, marked approximate). It respects the side locks and ignores the Attack/Caster blocks.
- **Beast influence recipes** add a mod drawn from that influence's pool, as its Exalted Orb would draw it (only the pool is borrowed: the item already has the influence); no source says which mod, so the claim is marked unverified and approximate.
- Randomise Influence and the Awakener's Orb are not here (the first is out of v1; the second is B3).

## Harvest add/remove

Eleven crafts (Fire, Cold, Lightning, Physical, Life, Defence, Chaos, Attack, Caster, Speed, Critical). The craft adds a mod of the tag, then removes **another** one. The addition is drawn **in proportion to the weight** among the tag's mods the item can roll at its item level; the removal is **uniform** among every other non-fractured mod on an unlocked side, crafted mods and metamods included (Craft of Exile, marked approximate). The addition obeys the side locks (open slots on a locked side can be filled) and the Attack/Caster blocks; the removal obeys the locks and ignores the blocks. It needs a non-influenced item and an open slot for the addition. It **works on items with an Eldritch implicit or a fractured mod** (the owner).

## Swaps

- **Resistance swaps** (six, 500 lifeforce of the target colour) change a resistance mod to another element. **The tier is kept and the value is rerolled inside the tier** (the owner); this holds for maximum-resistance swaps too. The required levels of the tiers differ by element, so **a swap into a tier above the item level is refused** (main chat). It respects the side locks.
- **Damage swaps** (six, 500 lifeforce and one Crystallised Rancour) follow Craft of Exile for **which mods qualify**, marked approximate; critical strike multiplier mods are excluded (wiki, since 3.28.0).

## Beasts

- **Wild Bristle Matron** adds one of the five metamods "randomly, only if allowed". Odds: **uniform among the allowed metamods** (main chat, marked approximate). It needs an open slot on the metamod's side and no crafted mod (except `Can have up to 3 Crafted Modifiers`); with the suffixes full and a prefix open the only allowed one is `Suffixes Cannot Be Changed`.
- **Farric Wolf Alpha and Lynx Alpha** add a prefix and remove a random suffix, or the reverse, on rare items. The added mod is gated by the **beast level**, not the item level: a setting, **default 83** when a target names none. "Any rare creature" slots cost 1 chaos each, also a setting.
- **Aspects** (Avian, Cat, Crab, Spider; level 20, or 30 with The Black Mórrígan) are offered only when a target names one. They add a suffix, need an open suffix, and an item holds one aspect; they are **not bench crafts, so they do not use the crafted-mod limit** (Craft of Exile, marked approximate).
- **Talisman fractures**: one fracture on a rare Talisman with at least 4 mods, two with at least 6, not on influenced or fractured items. **Which mods are fractured is uniform** (main chat, marked approximate). The Talisman base reroll is out of v1.

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions list; owner round 1, point 4, items 3 to 5); [Influence crafts](https://github.com/Rasslabsya4el/crafting-system/issues/86); [Harvest add/remove/swap and beasts](https://github.com/Rasslabsya4el/crafting-system/issues/88); ADR-0013, ADR-0028.
