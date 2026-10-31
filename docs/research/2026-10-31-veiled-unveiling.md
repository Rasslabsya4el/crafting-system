# Veiled mods and unveiling in 3.29 (research for ticket #87)

Ticket: https://github.com/Rasslabsya4el/crafting-system/issues/87 (map #1, inventory row M-26, batch B2). Date checked: 2026-10-31. Patch: 3.29.3.3 (pinned dump `.claude/scratch/real-cache/repoe-fork/3.29.3.3/`, published at https://repoe-fork.github.io/mods.json, `base_items.json`). Scope of the owner (#81): equipment, jewellery and jewels; no unique is a target.

**Answer in one paragraph.** A veiled mod is a placeholder that takes one prefix or suffix slot and does nothing until it is unveiled. The Veiled Chaos Orb is a Chaos Orb reroll that guarantees one such placeholder (it counts inside the usual 4/5/6 mods); the Veiled Exalted Orb removes one random mod (side locks respected, attack/caster blocks not) and then adds one placeholder, and is refused on an item that already carries a veiled mod. Unveiling is free (since 3.26 a right-click on the item), shows **three** options and the player picks one. The options are drawn from the `unveiled` mod domain of the placeholder's side, weighted by the first matching spawn-weight tag of the base item, **without replacement and one mod per mod family**, never from a family already on the item. The datamined weights and Craft of Exile's data agree on every base checked. The solver therefore needs a chance node (the offer, at most 546 distinct offers per pool) followed by a choice node (the policy picks one of the shown options), and an "unveil block" is a real part of the crafts the reference routes use.

Reddit could not be read: four `gpt-research` runs failed (3 timeouts, 1 dead worker; job ids `20261031-133114-318b`, `-133838-ae8b`, `-134127-f4c8`, `-134532-41c9`). Nothing below rests on a Reddit post that I did not see; the reference routes' Reddit threads (R22, R24) are cited only through [the reference-routes note](2026-10-30-5-reference-routes.md).

## Admitted claims

Evidence kinds: **wiki** (poewiki.net read in the built-in browser pane 2026-10-31; page text, no `oldid` captured), **official** (patch notes of pathofexile.com, read through the wiki's Version pages which quote them), **datamined** (`mods` = https://repoe-fork.github.io/mods.json, `base` = https://repoe-fork.github.io/base_items.json, 3.29.3.3), **coe** (Craft of Exile's `package.js` and `poec_data.json`, local copies in `sources/raw/coe/`, fetched 2026-09-20, the page of 2026-09-21 reads as patch 3.29.0.3 in the other notes).

### The orbs

**VEI-01** Veiled Chaos Orb is its own currency again; it reforges a rare item like a Chaos Orb and guarantees one veiled modifier. Kind: wiki. URL: https://www.poewiki.net/wiki/Veiled_Chaos_Orb. Quote: "It reforges a rare item with new random modifiers similarly to the standard Chaos Orb, but also guarantees one veiled modifier." Also official, 3.26.0 notes https://www.pathofexile.com/forum/view-thread/3787013 (via https://www.poewiki.net/wiki/Version_3.26.0): "Reintroduced Veiled Chaos Orbs, which reforges a Rare item with new random modifiers including a random Veiled modifier."

**VEI-02** Veiled Exalted Orb removes a random mod, then adds a random veiled mod; "Veiled Orb" was renamed in 3.26.0 with unchanged function (the 3.24.0 behaviour). Kind: wiki. URL: https://www.poewiki.net/wiki/Veiled_Exalted_Orb. Quote: "It removes a random modifier from a rare item, and then adds a random veiled modifier to it." Official 3.26.0: "Veiled Orbs have been renamed to Veiled Exalted Orbs, their functionality is unchanged."

**VEI-03** Both orbs add a *generic* veiled mod only: the signature veiled mods of the Syndicate members are not in the pool. Kind: wiki. URLs: https://www.poewiki.net/wiki/Veiled_Chaos_Orb and `.../Veiled_Exalted_Orb`. Quote: "The pool of possible outcomes does not include signature veiled modifiers." Data: the generic placeholders are `VeiledPrefix` and `VeiledSuffix`; the other 20 (14 prefix, 8 suffix in all, generic ones included) are the signature ones: 18 named after a member (`HakuVeiledPrefix`, `CatarinaVeiledPrefix`, `AislinVeiledSuffix__`, ...) and two for unique Abyss items (`AbyssVeiledPrefixUnique`, `AbyssVeiledSuffixUnique`) (mods: `domain`="veiled", 22 records, `spawn_weights`=[], `generation_weights`=[]; `VeiledPrefix` has `veiled_mod_type` 1, `VeiledSuffix` 2, `HakuVeiledPrefix` 7, and all carry `veiled_mod_seed` min 1 max 30000; every prefix placeholder has the family `VeiledPrefix`, every suffix one `VeiledSuffix`, so the ordinary family rule already allows one per side).

**VEI-04** The veiled mod is an ordinary prefix or suffix: it takes one slot of its side, is not a crafted mod (does not use a crafted-mod slot), and an item holds at most one veiled mod obtainable from the orbs. Kind: wiki. URL: https://www.poewiki.net/wiki/Veiled_modifier (3.15.0). Quotes: "Veiled modifiers are no longer considered Crafted modifiers." and "Veiled Chaos Orbs can no longer be used to obtain multiple Veiled modifiers on an item." Start items can still carry two: "Veiled items with two veiled mods can be found as a Safehouse reward" (same page) and 3.26.0 "She instead now drops rare double Veiled items."

**VEI-05** Veiled Chaos Orb: the veiled mod counts inside the drawn total of mods; locked sides and fractured mods stay; the veiled mod goes to the only side that still has room, otherwise to prefix or suffix with probability 1/2 each, **with no regard to a side lock**. Kind: coe. URL: https://www.craftofexile.com/packages/package.js. Quote: `if(blkpr){if(blksf){...veiltype=null}else{veiltype="suffix"}}else{if(blksf){veiltype="prefix"}}if(veiltype===!1){var rolled=poec_rand(0,2,!0);if(rolled==1){veiltype="prefix"}else{veiltype="suffix"}}` in `poec_simRerollItem` (called as `poec_simRerollItem("rare",null,null,null,!1,!1,!1,!0,null,!1,!1,!0,!1)`; `prmods` counts the kept mods and the veiled one, the draw is `noaffix-prmods`). The wiki's Metamod table has **no Veiled Chaos row** (it lists Chaos Orb: "Respected, but open prefixes may be filled"), so "open slots of a locked side may take the veil" is CoE only; see open point V-01.

**VEI-06** Veiled Chaos Orb is refused when a veiled mod would be kept, i.e. one sits on a locked side or is fractured. A "veiled mod" for this check is the placeholder, an unveiled mod of the veiled pool, or a bench craft that is the "craftable version" of a veiled mod. Kind: coe. Quote: `if((hasveiled.prefix&&haslock.prefix)||(hasveiled.suffix&&haslock.suffix)||hasfrac){var errtxt="Could not generate mod (Can't use while veiled affix is present)"` (case `'veiledchaos'`); `hasveiled` is set for `mgrp==10` (veiled pool), `id==-1` (placeholder) and `mgrp==11` (bench) mods whose text equals a veiled-pool mod. The wiki says nothing for Veiled Chaos; V-02.

**VEI-07** Veiled Exalted Orb is refused on an item that has a veiled mod or its craftable version; an already unveiled mod counts in CoE. Kind: wiki, with coe for the unveiled case. URL: https://www.poewiki.net/wiki/Veiled_Exalted_Orb. Quote: "Veiled Exalted Orbs cannot be used on an item with a veiled modifier or its craftable versions." CoE: `if(hasveiled.prefix||hasveiled.suffix){...Can't use while veiled affix is present` with `mgrp==10` counted, so a mod that was unveiled from the pool also blocks the orb (V-02). Also refused when no mod can be removed.

**VEI-08** Veiled Exalted removal: uniform over the mods that are not on a side locked by "Prefixes/Suffixes Cannot Be Changed" and not fractured (crafted mods and the metamods themselves included); the cannot-roll-attack/caster blocks are **not** respected by the removal. Kind: wiki + coe. URLs: https://www.poewiki.net/wiki/Veiled_Exalted_Orb ("The mod removal does not respect cannot roll attack/caster modifiers, but does respect prefixes/suffixes cannot be changed."), https://www.poewiki.net/wiki/Metamod (table row "Veiled Exalted Orb: Respected, Respected, Ignored[3], Ignored[3]"; [3] = Guy_GGG, 2022-09-30, forum thread "T4 Aisling failed to obey meta mods?"). CoE: `poec_simRemoveAffix(null,null,null,!0,!1,!0,!1,!1,null)` (side locks on, attack/caster off) and `poec_simCatToRWeight(weight,apcat,mod){return weight}` (uniform). The reference route R22 step 7 reads the same way: the removal may hit the crafted "Suffixes Cannot Be Changed" prefix instead of Life, "described as 50/50".

**VEI-09** Veiled Exalted placement: after the removal, the veiled mod goes to the only side with room; when both sides have room, prefix or suffix 1/2 each; the "15% second veiled mod" branch of the old Aisling code is dead (`var rolled=99; ... if(rolled<15)`). Kind: coe. URL: https://www.craftofexile.com/packages/package.js, case `'veiled'`: `var losuf=...;var lopre=...;if(loaff>1){var rolled=99;var veiltype=null;if(losuf==0||lopre==0){...}...if(veiltype==null){var rolled=poec_rand(0,2,!0);...}poec_simAddVeiledAffix(veiltype)}else{if(loaff==1){...}}`. As for the chaos orb, the side lock is not consulted (V-01).

**VEI-10** The wiki's drop facts, for the price layer: Veiled Chaos Orb has drop level 61, "Has a chance to drop from Leaders of Syndicate Safehouses" (stack 20); Veiled Exalted Orb "Drops from Catarina, Master of Undeath" and can be made from 2 Outfoxed divination cards; the Veiled Exalted Orb "cannot be obtained in leagues with Ruthless mode enabled" (the page for the Chaos one says the same, marked "confirmation needed"). Kind: wiki. CoE's poe.ninja keys are `Veiled Chaos Orb` and `Veiled Exalted Orb` (group `currency`, `package.js` index `poeninja`).

### Unveiling

**VEI-11** Unveiling shows three random mods and the player picks one; no cost, no NPC since 3.26.0; the picked mod is not a bench craft. Kind: wiki + official. URL: https://www.poewiki.net/wiki/Veiled_modifier. Quote: "Unveiling the mod presents three random mods, and allows the player to choose which one the veiled mod becomes." Official 3.26.0: "You are no longer required to speak with Jun to Unveil your items. You can now Right-click (or use Circle/B on Controller) on a Veiled item and simply select the Modifier you wish to Unveil." Corrupted and mirrored items can be unveiled again since 3.25.0 (wiki version table).

**VEI-12** The offer pool of a placeholder is the `unveiled` domain: 258 mods (162 prefix, 96 suffix), all `required_level` 60 except one (level 1); each mod is its own record (no tier ladder: the bench versions, the "Crafted1/2/3" ladder, are separate `crafted`-domain mods). Of the 258, 150 are generic (78 prefix, 72 suffix, 80 families), 57 belong to a signature pool (spawn-weight tags `catarina_veiled_prefix`, `it_veiled_prefix`, `haku_veiled_prefix`, ... only), 51 have weight 0 everywhere (legacy, e.g. the Damage over Time Multiplier prefixes, quiver/flask legacy, "Trigger a Socketed Spell on Using a Skill"). Kind: datamined. URL: mods. Quote: `{"domain":"unveiled","generation_type":"prefix","groups":["LocalPhysicalDamagePercent"],"required_level":60,"spawn_weights":[{"tag":"wand","weight":500},{"tag":"sceptre","weight":500},{"tag":"dagger","weight":500},{"tag":"weapon","weight":1000},{"tag":"default","weight":0}],"name":"Chosen"}` (`JunMasterVeiledLocalIncreasedPhysicalDamageAndImpaleCrafted`). The wiki's "List of veiled modifiers" (https://www.poewiki.net/wiki/List_of_veiled_modifiers) prints the same weights and level 60 per mod.

**VEI-13** The weight of a mod on a base is the weight of the **first** `spawn_weights` entry whose tag the base item has; 0 excludes it (`default` 0 closes the list). The side of the offer is the side of the placeholder. Kind: datamined + wiki (https://www.poewiki.net/wiki/Modifier, "Spawn-weight entries have leftmost matching priority", read 2026-09-20 in `sources/raw/wiki/browser-observations-2026-09-20.md`). Result for the generic pools: boots 19 mods (7 prefix W 8500, 12 suffix W 13100), gloves 23, helmet 19, body armour 21, shield 17, quiver 17, belt 16, ring 18, amulet 24, wand/sceptre/dagger/claw/axe/sword/mace/staff 30 (weapon pools differ in weights, see the CSV), bow 23. **Craft of Exile's data agrees on every base compared** (19 bases: same mod count and the same total weight, e.g. boots 19 / 21600, helmet 19 / 19600, wand 30 / 27000, staff 30 / 30000): its veiled group `id_mgroup`=10 with `vex`=0 is the generic pool, `vex`=1 the signature pools.

**VEI-14** Offer draw: up to 3 draws from the pool by weight, **without replacement**; after each pick every other mod of the **same mod family** (modgroup) is removed from the pool, so the three options are always from three different families; the families of the mods already on the item are removed before the first draw; fewer than 3 options when the pool runs dry; only the first tier counts (PoE 1 has a single tier per mod). Kind: coe. URL: https://www.craftofexile.com/packages/package.js, `poec_simUnveilMod`. Quote: `let unveilModsNumber=3; ... for(var j=0;j<unveilModsNumber;j++){if(varr.length==0)break; ... picks.push({"id":useWhichArray[k].id,"tier":0});chosengrp=...;vtweight-=...; ... if(mconflict){vtweight-=varr[k].weight}else{narr.push(...)}`, the pool is built from `usefmodpool[useaffixes[swapindex].atype][crsim_veiledmgrp]` and keeps only entries with `vex==0` whose groups are not in `blkmgrps`. The three-options rule is also the wiki's (VEI-11). The weights are not documented by GGG; the repoe weights and Craft of Exile's data agree (VEI-13), and VEI-17 is only a rough plausibility figure.

**VEI-15** The groups on the item that block options are those of every explicit mod, bench crafts included (CoE collects `modgroups` and additional groups of all `useaffixes` with `id>0`); implicits, enchants and the other veiled placeholder are not read. This is why a bench craft of an unwanted family is an "unveil block": the reference route R30 (Pohx, https://pohx.net/crafts/advanced-endgame-boots/) says "Craft Evasion Rating while Focused as an unveil block, then unveil the preferred Movement Speed modifier", and R02 "Block a prefix (Zombies)". Kind: coe (+ guide, reference routes note).

**VEI-16** A veiled mod gets no item-level gate in CoE: `useitemlevel` is read but not used by the PoE 1 branch (only the PoE 2 branch uses `minimumLevel`). The unveiled records have `required_level` 60. Whether the game refuses or filters on an item level below 60 is not documented (V-04). All benchmark items are item level 82+ (R07 84) so v1 is not hurt.

**VEI-17 (not a claim; an open point, V-12)** R02's "+2 AoE" unveil carries 0.45 ("SKRYAH slide transcription", a pre-3.29 quiz slide copied into the reference-routes note) with a Zombies prefix block. The algorithm on the 3.29.3.3 helmet prefix pool (9 families, W 12000) with `MaximumMinionCount` (W 2000) blocked gives 0.4375; without the block 0.3717. The two figures differ by 0.0125. Possible reasons, none checked: the slide is rounded or from an older pool (the quiz is "pre-3.29"; the AoE/gem-level mods changed items in 3.26.0), other families on the crown block part of the pool, or the algorithm differs a little from the game. The figure is neither an experiment nor independent evidence of the weights; it only shows that the order of magnitude is right. Offers are drawn at unveil time from the current item, so a block changes the odds (VEI-15).

**VEI-18** Reflecting Mist (new in 3.29.0) "Cannot be used on Veiled or Influenced items." Kind: official. URL: https://www.pathofexile.com/forum/view-thread/3985332 (3.29.0 notes; text read at https://www.poewiki.net/wiki/Version_3.29.0).

**VEI-19** A fractured veiled mod exists: since 3.28.0 "Veiled Items dropped by Defeated Syndicate Members in your Maps have a 5% chance to drop with a Fractured Veiled Modifier" (Pillage and Plunder). Kind: official, https://www.pathofexile.com/forum/view-thread/3913392. What the game does with it under Veiled Chaos/Exalted, Annulment, Scouring is not documented except CoE's refusal (VEI-06), V-05.

**VEI-20** "Craftable versions" of veiled mods (what VEI-06/07 refuse on): in the dump the crafted-domain `JunMaster*` mods are 994; 928 of them (all 18 untagged and 910 of the 976 `unveiled_mod`-tagged) have the same side and the same set of stat ids as an `unveiled`-domain mod, the other 66 do not (signature or legacy mods). CoE decides by displayed text equal to a veiled-pool mod of the same side. Kind: datamined (computed here, https://repoe-fork.github.io/mods.json). The tier ladder differs: unveiled (120-139)% physical vs crafted tiers (81-85)/(86-94)/(95-105)%.

### The pools that matter for the benchmark routes (repoe, generic, 3.29.3.3)

Full list per base class with weights: [2026-10-31-veiled-pools.csv](2026-10-31-veiled-pools.csv) (23 representative bases, 594 rows; `mod_id` is the mods.json key).

| base | prefix pool (families / W) | suffix pool (families / W) | notes |
|---|---|---|---|
| Boots (any attribute type) | 7 mods, 5 families / 8 500 | 12 mods, 11 families / 13 100 | Movement Speed has **three** variants in one family (+Onslaught on Kill, +100% Avoid being Chilled, +Movement Speed if not Hit Recently), each W 1500: only one of them can be in an offer. |
| Helmet | 9 / 12 000 | 10 / 7 600 | Area of Effect + 2 AoE gems W 1500 (prefix); Trigger Socketed Spells when you Focus W 1000 (suffix, helmet only). |
| Gloves | 10 / 12 750 | 13 / 14 600 | |
| Body armour | 6 / 10 000 | 15 / 13 100 | the old Avoid Elemental Ailments and Stun mod has W 0. |
| Wand | 13 mods, 4 families / 10 000 | 17 mods, 11 families / 17 000 | four physical variants (W 500 each) share one family; six `WeaponCasterDamagePrefix` variants share another. |
| Staff | 13 / 13 000 | 17 / 17 000 | W 1000 per mod. |
| Ring / Amulet / Belt | 8 / 6 800, 8 / 6 800, 6 / 8 000 | 10 / 9 100, 16 / 18 100, 10 / 8 600 | jewels have no veiled pool (CoE's `veil_bgroups` are only 1-8: jewellery, body, boots, helmets, gloves, 1H, 2H, off-hands). |

Exact offer probabilities (sequential draw, one option per family, computed here over the repoe pool; the enumeration is in "Method and limits"):

| target | pool | P(target in the offer) |
|---|---|---|
| any Movement Speed variant on boots (veil on prefix) | boots prefix | 0.942 |
| one named Movement Speed variant (Onslaught, or Avoid Chilled) | boots prefix | 0.314 each |
| the same, after crafting the Evasion Rating while Focused block (R30) | boots prefix minus 1 family | 0.326 |
| the same, after blocking all four non-Movement-Speed families | boots prefix | 0.333 (the MS family is always offered, one of three variants) |
| +2 AoE gems (R02) | helmet prefix | 0.372; with the Zombies block 0.437; also blocking Life 0.486 |
| Trigger Socketed Spells when you Focus | helmet suffix | 0.388 |
| Minions' attack and cast speed (R07's craft, higher values than the bench) | wand suffix | 0.194 |
| Minion damage + life | staff prefix | 0.140 |

These are the offer odds only; the odds of the veil landing on the wanted side (1/2 when both sides have room) and the odds of the rest of the reroll are separate factors.

## What the solver must model

1. **State.** The veiled mod is an element of the item: a placeholder with its **side** (prefix/suffix) and its **kind** (generic; signature only on start items, not produced by the orbs). It takes a slot, has no family (the other draws are not blocked by it), is not crafted, and an item may carry up to two (start items). The pool of a placeholder depends on (base class tags, side) and on the families present on the item at the time of the unveil.
2. **Veiled Chaos Orb** = the Chaos reroll of #7 with one forced slot: choose the side (VEI-05), then draw the remaining `total − kept − 1` mods (kept = fractured, mods of a locked side). Cost: one orb (price key `Veiled Chaos Orb`).
3. **Veiled Exalted Orb** = remove one mod uniformly among the unprotected ones, then add the placeholder (VEI-08, VEI-09). Cost: one orb (`Veiled Exalted Orb`). Refused with a veiled mod on the item.
4. **Unveil** = a **chance node followed by a choice node**: the offer (≤ 3 mods, one per family) is a random variable of the state; the policy then picks the option whose next state has the smallest expected remaining cost, or, if every option is bad, does something else on the veiled item (Annulment, a bench block, another reroll) - the offer is information. Unveiling itself costs nothing.
5. **Encoding.** The existing solver wants actions with a positive cost and integer weights (the solver-interface note of ticket #17: `Action(label, cost, outcomes)`, cost > 0). Two ways to carry the choice: (a) an *offer state* (item + placeholder + offer set) with one zero-cost deterministic "pick option i" action per shown option (≤ 3), the unveil action's outcomes being the offers with integer weights over the sum of the pool weights; the number of distinct offers (unordered sets of up to three mods) per pool is at most 546 (amulet suffix; 540 for the wand, staff, sceptre and dagger suffix), 405 for the body armour suffix, 264 for the gloves suffix, 120 for the gloves prefix, 22 for the boots prefix, 10 for the shield prefix; (b) with the goal known, compress the offer to "which target-relevant options are shown", every other option collapsing to "a junk mod on this side that blocks nothing relevant" - the pick between target and junk is then trivial in most goals. The pick action is acyclic (offer state → picked state), so a zero (or ε) cost does not break the proper-policy test; if the solver insists on positive costs, ε = 1e-9 of the cheapest orb is enough. This decision belongs to the state-compression and solver tickets (#59, #17), not to this note.
6. **Decline.** The player can always leave the item veiled; a decline is not an action with an effect (the placeholder stays, the offer is the same). Whether the offer survives closing and reopening the window, or is re-drawn, decides if "peek, then block, then peek again" is a free information loop (V-03). Recommended v1: no decline action, the offer is drawn when the unveil action is taken, and the cost of every block craft is paid as an ordinary bench craft.
7. **Blocks.** A bench craft of a family in the pool removes that family from the next offer (VEI-15). Because the solver chooses actions by expected cost, nothing special is needed: the bench craft is an ordinary action and the pool is recomputed from the families on the item.

## Benchmarks

| route | veiled step | what 3.29.3.3 says |
|---|---|---|
| R02 Archdemon Crown | lock suffix, Veiled Chaos, block Zombies, unveil +2 AoE (0.45) | executable; our 0.4375 is close to the quiz's 0.45, not equal (V-12). |
| R03 Velour Boots | Veiled Chaos, unveil move speed | executable: any MS variant 0.942 with a prefix veil. |
| R07 +2 minion wand | "Craft Prefixes Cannot Be Changed, Veiled Chaos, unveil Trigger a Socketed Spell on Using a Skill; otherwise settle for the bench Trigger" | **the unveil of that mod is not possible in 3.29.3.3**: `JunMasterVeiledTriggerSocketedSpellOnSkillUse_` has `spawn_weights` `[{weight:0 for weapon},{default 0}]` and the wiki lists it under "Legacy Suffix" with `weapon 0`. Only the bench Trigger remains. The wand suffix pool does contain Minion attack/cast speed (P 0.194), the third suffix of R07. |
| R22 GG fractured boots | Veiled Exalted, "50/50", unveil MS + Avoid Chilled | executable; the 50/50 is the removal hitting the metamod prefix or Life (VEI-08); MS+Avoid Chilled offered 0.314 given a prefix veil. |
| R23 fractured-suppression boots | veiled | same boots pool. |
| R24 Mana-fractured boots (3.29) | lock suffixes, Veiled Chaos, MS+Onslaught | executable; MS+Onslaught 0.314 given a prefix veil, with suffixes locked and full the veil is forced onto the prefix. |
| R30 Pohx boots | full suffixes, Wild Bristle Matron lock, Veiled Chaos, Evasion-while-Focused block, unveil MS | executable; 0.326 with the block. |

## Open points and questions for the owner

Each is a gap a quick in-game check or his own knowledge settles; recommended answers are the rules above.

- **V-01 Where does Veiled Chaos / Exalted put the veil when a side is locked and has an open slot?** Only CoE's code speaks (VEI-05, VEI-09: 1/2, lock ignored; forced to the side with room when the other is full). The wiki's Metamod table has no row for Veiled Chaos. R30 and R24 use full locked suffixes, which forces the prefix in both models, so the benchmarks do not depend on it. *Recommended: adopt CoE (lock ignored); owner or an agent checks once with a locked-prefix item that has a free prefix slot.*
- **V-02 Does an already unveiled mod, or a bench craft equal to a veiled mod, block Veiled Exalted (and a locked one block Veiled Chaos)?** CoE says yes (VEI-06, VEI-07); the wiki words it "veiled modifier or its craftable versions". *Recommended: adopt CoE.*
- **V-03 Is the offer fixed per veiled mod?** The placeholder carries a stat `veiled_mod_seed` (an integer from 1 to 30000, in `mods.json`), which suggests the offer is a function of that seed and the current pool, and the same whenever the window is opened. *Question: open the unveil window, close it, open it again: the same three? And after a bench block is crafted?* Recommended v1: model the offer as drawn when the unveil action is taken, no free re-peek (see "Decline").
- **V-04 Item level below 60.** Does Veiled Chaos/Exalted work on, and does the offer exist for, an item whose level is below 60 (the unveiled mods are level 60)? CoE has no gate. *Recommended: no gate in v1.*
- **V-05 Fractured veiled mods and the other currencies.** What happens to a fractured veiled mod under Veiled Exalted, Annulment and Scouring, and does a Fracturing Orb ever pick the placeholder? Not documented. CoE refuses Veiled Chaos; Veiled Exalted removal never takes a fractured mod. *Recommended: a start item with a fractured veiled mod is out of v1 (it is a drop of a rare Atlas passive).*
- **V-06 Do the unveil offers respect Cannot roll Attack / Caster Modifiers?** CoE's offer code has no check; the wand/staff pool holds attack and spell mods side by side. The wiki's table says the Veiled Exalted removal ignores them and is silent on the offer. *Recommended: no filter in v1; an in-game check on a wand with "Cannot roll Attack Modifiers" would show whether physical damage options still appear.*
- **V-07 Signature veiled start items** (Haku's, Catarina's ...) and double-veiled drops: the placeholder kind exists in the data (22 records) with its own offer pools (57 mods). *Scope question for the owner: do start items with a signature veil count in B2? Recommended: no, generic veils only; the second placeholder of a double-veiled item is supported by the state element but not by any v1 action.*
- **V-08 Signature mods through Veiled Orbs.** The wiki says the orbs' pool excludes them; CoE agrees (`vex`=1 not drawn). No open question, recorded for the claim.
- **V-09 Other actions on an item with a veiled mod** (essences, fossils, Harvest reforges, Eldritch orbs, Annulment, Scouring, Awakener, recombinators): only Reflecting Mist is documented (VEI-18). CoE disables the PoE 2 desecration on veiled items and has no further check for PoE 1. *Left to the tickets of those actions; the state element above is what they need to read.*
- **V-10 Patch gap.** I read the patch notes of 3.26.0, 3.27.0, 3.28.0 and 3.29.0 through 3.29.3 on the wiki (hotfixes are inside those pages); veiled lines exist only for 3.26.0, 3.28.0 and 3.29.0. 3.29.3.3 itself is a data patch (the dump).
- **V-11 Reddit** not read (four failed runs). *Recommended: rerun `gpt-research` when the worker is stable, aimed at V-01, V-03 and V-06.*
- **V-12 The R02 figure.** The quiz slide says 0.45, the algorithm 0.4375 (VEI-17); the difference of 0.0125 is unexplained (rounded slide, older pool, other families on the item, or a small difference in the game's draw). Not a claim. *Recommended: no action; an in-game count on a helmet would settle it.*

## Draft claims for `src/crafting_system/rules/claims/`

17 draft rules, in `docs/research/2026-10-31-veiled-claims-draft/veiled.yaml` (12 rules, family `veiled`) and `unveil.yaml` (5 rules, family `unveil`), same text as the resolution comment on #87. The real registry loader (`crafting_system.rules.registry.load_registry`) accepts the folder; every Craft of Exile quote is a substring of `package.js`. The claim ids map to the numbered claims above: `veiled.chaos_*` VEI-01/05/06, `veiled.exalted_*` VEI-02/07/08/09, `veiled.orbs_generic_pool_only` VEI-03, `veiled.mod_*` VEI-04 and VEI-03's placeholder data, `veiled.reflecting_mist_refused_on_veiled` VEI-18, `unveil.*` VEI-11 to VEI-16, VEI-20.

## Method and limits

- Pool arithmetic: `mods.json` domain `unveiled` (258 records), first-match spawn weight over the `tags` of one representative base per class from `base_items.json`; the same totals recomputed from CoE's `poec_data.json` (`modifiers.seq` with `id_mgroup`=10, `tiers[mod][base][0].weighting`, `modbases`) for 24 bases (all matched). Offer probabilities are exact (fractions, full enumeration of the 3-draw tree).
- CoE code read: `poec_simUnveilMod`, `poec_simAddVeiledAffix`, `poec_simRerollItem` (veiled branch), cases `'veiled'` and `'veiledchaos'`, `poec_simRemoveAffix`, `poec_simCatToRWeight`. The earlier prototype note `docs/mechanics/veiled.md` of `archive/prototype` (read-only) reached the same reading of CoE and left the weights open ("Q12"); this note closes that gap with the datamined weights.
- Wiki pages read 2026-10-31: Veiled_Chaos_Orb, Veiled_Exalted_Orb, Veiled_modifier, Metamod, List_of_veiled_modifiers, Version_3.26.0 / 3.27.0 / 3.28.0 / 3.29.0-3.29.3. The wiki showed a Cloudflare check once; it cleared by itself and nothing was clicked.

Enumeration used for the offer table (`pool` = list of `(mod_id, family, weight)` of one side of one base, `Fraction` for exact odds):

```python
from fractions import Fraction

def offers(pool, n=3):
    """{frozenset(mod ids): probability} of the offer, n draws without replacement, one mod per family."""
    out = {}
    def rec(cur, chosen, prob):
        if len(chosen) == n or not cur:
            key = frozenset(chosen)
            out[key] = out.get(key, 0) + prob
            return
        total = sum(w for _, _, w in cur)
        for mod, family, w in cur:
            rest = [x for x in cur if x[1] != family]   # the picked mod's family leaves the pool
            rec(rest, chosen + [mod], prob * Fraction(w, total))
    rec(pool, [], Fraction(1))
    return out

# pool for a base: for each unveiled-domain mod of the placeholder's side, weight = first spawn_weights entry whose tag the base has;
# drop weight 0 and every family already on the item. P(target offered) = sum of the probabilities of the offers that contain it.
```
