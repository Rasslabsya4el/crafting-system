# Tempering, Tailoring and quality enchants in PoE 1 3.29

Ticket: [#100 Tempering, Tailoring and quality enchants in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/100) (inventory rows M-75, M-76, M-77; batch B7; scope of [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81): equipment targets, no flasks, no anointments). Date checked: **2026-10-31**. Patch: **3.29.3.3**. Evidence rule: map #1 Notes (the best information today; a source shown out of date by a 3.29 note or the 3.29.3.3 data loses).

Files: this note; `2026-10-31-enchantments-claims.yaml` (17 draft claims, seven provenance fields each, valid YAML); `2026-10-31-enchantments-pools.py` (stdlib; `python -I <script> <repoe-fork 3.29.3.3 folder>` prints every count below).

## Answer

- **What exists.** The Tempering Orb (one weapon) and the Tailoring Orb (one body armour) each "add or replace an enchantment" drawn from their own pool, and "may reforge the sockets". The Harvest craft table has 14 quality enchants (6 weapon, 8 body armour). All three are in the 3.29 game; none is removed by any 3.29 note.
- **Pools in 3.29.** Weapon **136** enchants, body armour **54**. The weapon number is the wiki's list and equals the dump (181) minus the 45 the 3.29.0 note removes. The body-armour number is *derived*: the wiki's Tailoring page (last edited 26 July 2026) and the dump both still list 75, including the 21 enchants the 3.29.0 note removed; the wiki's Tempering page was updated, its Tailoring page was not.
- **Weights are not published anywhere I could reach.** The wiki's number column is the mod's `required_level`; the dump gives all 256 Heist enchant mods empty `spawn_weights` and `generation_weights`; Craft of Exile has no enchant data; PoEDB's table is name / level / description. The only odds datum is one second-hand figure of **1 in 283** for "Can have 1 additional Crafted Modifier" (a 2025 forum post quoting a Reddit spreadsheet), which a uniform pool contradicts (1 in 75 then, 1 in 54 now). Section 4 designs the measurement and shows it is expensive.
- **Reddit was not reached.** `gpt-research` timed out on all six jobs I started (ids in section 7); I did not switch models. The forum was behind a Cloudflare challenge / HTTP 429. Everything below is wiki, datamined, PoEDB and a web-search snippet; the in-game facts that only Reddit or a click would settle are in section 6.
- **Price.** PoEDB's live exchange rows (US realm, 2026-10-31) put a Tempering Orb at 1.44 Divine (471 Chaos by the second pair) and a Tailoring Orb at 2.15 Divine (570 Chaos). A third-party aggregator showed 19.4 Chaos in late July 2026 and an older guide ~88 Chaos for a Tailoring Orb. These disagree by more than 20x; the price layer (#84, #40) must pick the source.

## 1. Rules with provenance

Kinds: `official`, `wiki`, `datamined`, `experiment`, `coe`, `owner`. Checked 2026-10-31 for all. Wiki revisions read: Tempering Orb (live, 3.29.0 sentence in its history), Tailoring Orb rev 1681191 (26 July 2026), Modifier rev 1703013 (10 Oct 2026), Grand Heist (edited 22 Apr 2026), Curio Display rev 1462102 (12 Jul 2024), Quality rev 1673652 (16 Jul 2026), List of harvest crafting options rev 1699144 (5 Aug 2026), Crafting Bench rev 1700860 (16 Aug 2026), Version 3.29.0 (5 Aug 2026). The claim ids are in the YAML.

**What the orb does**

- **ENC-01** (wiki) Tempering: "Adds or replaces an enchantment on a weapon / This may reforge the weapon's sockets". Tailoring: the same for "a body armour". https://www.poewiki.net/wiki/Tempering_Orb, https://www.poewiki.net/wiki/Tailoring_Orb. The base item text in the dump says the same (`Metadata/Items/Currency/CurrencyHeistWeaponEnchant`, `...HeistArmourEnchant`; datamined). Claim `enchantment.heist_orbs_add_or_replace`.
- **ENC-02** (wiki) One enchantment slot, separate from implicits; "Most items can have up to one enchantment at a time"; "Applying an enchantment on an already enchanted item replaces the old enchantment with the new one." https://www.poewiki.net/wiki/Modifier#Enchantments. Claim `enchantment.one_slot_new_replaces_old`. So a re-click is a free re-roll of the enchant: nothing is kept, the orb is the only cost (plus the socket side effect, ENC-09).
- **ENC-03** (wiki; datamined) The bench removes an enchantment for **3 Orbs of Scouring**, always available (3.15.2), for body armour and every weapon class (29 classes incl. flasks). Bench record 309: `remove_enchantments=true, cost CurrencyConvertToNormal x3, bench_tier 0`. https://www.poewiki.net/wiki/Crafting_Bench ("Remove Enchantments 3x Orb of Scouring"). Claim `enchantment.bench_removes_for_three_scouring`.
- **ENC-04** (wiki) "Mirrored cannot receive an enchantment." "Corruption does not remove the enchantments of an item." Removal is only for a non-corrupted item. https://www.poewiki.net/wiki/Modifier#Enchantments. Claim `enchantment.mirrored_and_corruption`. Enchantment values are fixed, so Blessed Orbs do nothing to them.
- **ENC-05** (wiki) "Tailoring Orbs cannot be used on items with fixed sockets": Kaom's Heart, Replica Kaom's Heart, Skin of the Loyal, Skin of the Lords (3.20.0 fix). All unique, so no target of ours is refused. https://www.poewiki.net/wiki/Tailoring_Orb#Mechanics. Claim `enchantment.tailoring_not_on_fixed_sockets`.

**What is in the pools**

- **ENC-06** (wiki; official text) 3.29.0: "Enchantments on Body Armour and Weapons related to White Sockets or those that set all Sockets to be Blue, Green or Red no longer appear on Heist Rewards or from Tailoring and Tempering Orbs." https://www.poewiki.net/wiki/Version_3.29.0 (the wiki's copy of the patch notes; the official thread is https://www.pathofexile.com/forum/view-thread/3985332, behind Cloudflare today, cited by the #10 note as HRV-20). Claim `enchantment.removed_from_pool_in_3_29_0`.
- **ENC-07** (datamined + wiki) Pools, counted by `docs/research/2026-10-31-enchantments-pools.py` from `mods.json` (groups `EnchantmentHeistWeapon`, `EnchantmentHeistArmour`; generation type `unique`, domain `item`):

  | | in dump | removed by stat (white socket, or all sockets red/green/blue) | pool 3.29 |
  |---|---|---|---|
  | Weapon | 181 | 45 (12 white + 33 one-colour) | **136** (= wiki's 136 rows) |
  | Body armour | 75 | 21 (6 white + 15 one-colour) | **54** (derived) |

  Required level of the mods (the wiki's number column): weapon 1:7, 10:1, 20:52, 30:5, 40:1, 69:33, 70:30, 74:3, 78:3, 80:1; body armour 1:7, 20:6, 30:20, 69:17, 70:3, 80:1. Claims `enchantment.weapon_pool_136`, `enchantment.armour_pool_54`.
  *Caution*: the repoe-fork mod ids and texts disagree on colour naming ("...NoBlueSockets" carries the text "Has no Green Sockets", and the wiki repeats the swap); the stat ids `local_cannot_have_red/green/blue_sockets` are the reliable key, and the pairing between the three "No X sockets" mods and a colour needs an in-game check before it is coded (O-04).
- **ENC-08** (wiki; datamined) What an enchant does: "8% increased Explicit Life Modifier magnitudes" turns "+100 to Maximum Life" into "+108". Kinds in a pool: single magnitude (8%, one of Physical, Fire, Cold, Lightning, Chaos, Caster Damage, Mana, Speed, Critical, Attribute, Ailment for weapons; Life, Defence, Mana, Resistance, Attribute for armour), hybrid of two tags at 6% each, one tag at 6-8% plus a rider, one tag at 10-15% with a downside (25% to 50% less on another tag, "200% increased Attribute Requirements", "-3 to maximum Sockets"), and three specials: "40% reduced Attribute Requirements", "All Sockets Linked", "Can have 1 additional Crafted Modifier". The modifier magnitudes are all fixed values. https://www.poewiki.net/wiki/Modifier#Heist_Enchantments. Claim `enchantment.magnitude_enchants_scale_explicit_mods_by_tag`. The tags are the same mod tags Harvest uses (HRV-05 of #10).
- **ENC-09** (datamined; wiki) The sockets: enchants carrying `local_all_sockets_linked`, `local_cannot_have_{red,green,blue}_sockets` or `local_maximum_sockets_+` (-3) are the ones that must touch the sockets. In the 3.29 pools 56 of 136 weapon and 26 of 54 body-armour enchants carry one of these. The wiki says only "This may reforge the weapon's sockets" and, on Tailoring, "due to the effect of the hybrid enchantment". A web guide says a socket-touching enchant can reroll the socket setup so a six-linked body armour can lose its links (vhpg.com, unverified, third-party). How the reforge works (number, colours, links, when the colours already satisfy the enchant) is **not documented by a source I could read**: O-03.
- **ENC-10** (datamined; wiki) "Can have 1 additional Crafted Modifier" exists once in each pool (required level 80, stat `local_can_have_additional_crafted_mods` 1). The Crafting Bench page: "It is possible to craft more than one mod onto an item with the of Crafting meta-crafting mod, or a similar enchantment from Tempering Orbs, Tailoring Orbs or certain items found in Grand Heists." Claims `enchantment.crafted_slot_enchant`, `enchantment.crafted_slot_enchant_allows_several_bench_crafts`. It is the single most valuable result and the one with the only odds datum (section 3).
- **ENC-11** (wiki) An enchant raises the item level requirement "up to 80% requirement of the mod ... rounded down", so the 69/70/80 enchants put the requirement at 55/56/64. https://www.poewiki.net/wiki/Modifier#Mod_Level. Claim `enchantment.raises_item_level_requirement`. Matters only for the target's level.

**Where the orbs come from**

- **ENC-12** (wiki) Curio Displays in the last room of a Grand Heist hold five choices, one may be taken: currency (Tempering Orb, Tailoring Orb, Delirium orbs, scarabs ...), equipment (Thief's Trinkets, experimented bases, Enchanted Rare Body Armour, Enchanted Rare Weapon), or a replica unique. "The following rewards only drop from Curio Displays in Grand Heists." Heist entered the core game in 3.13.0 ("Greatly increased the chance of finding Tempering and Tailoring Orbs from Blueprint rewards"). The Grand Heist page (edited 22 Apr 2026) has history to 3.28.0, no removal; the Curio Display page (July 2024) is old but not contradicted. https://www.poewiki.net/wiki/Grand_Heist, https://www.poewiki.net/wiki/Curio_Display. Claim `enchantment.heist_orb_source`.
- **ENC-13** (PoEDB; a price page, no claim drafted) Both orbs are on the Currency Exchange: "Currency Exchange 250 Gold", NoteCode `tempering-orb` / `tailoring-orb`. https://poedb.tw/us/Tempering_Orb, https://poedb.tw/us/Tailoring_Orb (read 2026-10-31). Prices in section 5.

**Harvest quality enchants (M-77)**

- **ENC-14** (datamined; wiki) 14 mods in groups `AlternateWeaponQuality` (6) and `AlternateArmourQuality` (8) in the dump; the wiki's Quality page lists the same 14 as "Harvest enchantments", and the Harvest options table ("Core game") has 14 matching craft rows (the "Ruthless mode" table repeats them). Weapon: no extra physical damage from quality, instead +0.1 m weapon range per 10% (melee only), 1% area per 4%, 1% accuracy per 2%, 1% attack speed per 8%, 1% critical strike chance per 4%, 1% elemental damage per 2%. Body armour: no extra Defences, instead +1 per 2% quality of Maximum Life, Maximum Mana, Strength, Dexterity, Intelligence, or +1% Fire, Cold, Lightning Resistance. Claim `enchantment.harvest_quality_enchants_14`.
- **ENC-15** (wiki) Lifeforce cost, in items (Wild / Vivid / Primal; no Sacred, no Rancour): body armour 3,250 each - Life, Strength, Fire resistance Wild; Dexterity, Cold resistance Vivid; Mana, Intelligence, Lightning resistance Primal. Weapon 5,000 each - Range, Area Wild; Accuracy, Attack Speed Vivid; Critical, Elemental Primal. Wiki rev 1699144, 5 Aug 2026; the page's history to 3.24.0 shows no change to them. Claim `enchantment.harvest_quality_enchant_costs`. The cost in the tables is also an input of the price layer (Lifeforce prices, #84).
- **ENC-16** (wiki) The quality enchant changes only the stat, "This does not affect other aspects of quality such as the chance to have a certain number of sockets or links." Quality from currency is capped at 20% (30% only for items that dropped so). Catalysts act on jewellery, so no catalyst quality exists on these items. https://www.poewiki.net/wiki/Quality#Effect_on_items. Claim `enchantment.quality_enchant_leaves_socket_odds`.
- **ENC-17** (wiki; inference) The Modifier page lists "Certain Harvest crafting options allow you to add enchantments to weapons and body armours" in the same list as the Heist ones, and the general rule is one enchantment per item, new replaces old. So a quality enchant and a Tempering / Tailoring enchant should replace each other. **No source states this case**; O-05.

## 2. What the pool looks like to the planner

Under a *uniform* pool, the draw is one of N equally likely enchants and every click may be repeated at the cost of one orb (replacement is free, removal 3 Scouring). A route to a set S of acceptable enchants is then "click until in S"; expected orbs = N / |S|. Examples from the 3.29 pools by the script's rules (positive magnitude on the tag, no downside; "clean" also excludes riders that touch sockets):

| Target set | Pool | in set | clean | uniform p (any / clean) | expected orbs (any / clean) | at PoEDB's price (any / clean) |
|---|---|---|---|---|---|---|
| Life magnitude, no downside | armour 54 | 8 | 4 | 14.8% / 7.4% | 6.8 / 13.5 | 14.6 / 29 Div (Tailoring 2.15) |
| Resistance magnitude, no downside | armour 54 | 8 | 4 | 14.8% / 7.4% | 6.8 / 13.5 | 14.6 / 29 Div |
| Physical magnitude, no downside | weapon 136 | 10 | 6 | 7.4% / 4.4% | 13.6 / 22.7 | 20 / 33 Div (Tempering 1.44) |
| Critical magnitude, no downside | weapon 136 | 13 | 9 | 9.6% / 6.6% | 10.5 / 15.1 | 15 / 22 Div |
| Additional crafted modifier | armour 54 | 1 | 1 | 1.9% | 54 | 116 Div |
| Additional crafted modifier | weapon 136 | 1 | 1 | 0.74% | 136 | 196 Div |
| (same, if the 1-in-283 datum holds) | either | 1 | 1 | 0.35% | 283 | 608 Div armour / 408 Div weapon |

The last row shows why the weights matter: the same target is 5x dearer if the report is right. The prices are PoEDB's snapshot and not asserted by this note (section 5). A magnitude enchant moves a modifier by 6-15%, so most of the value of a "clean" Life enchant to a finished item is a few life points (8% of one mod).

## 3. Weights: what is known

- **No source.** Wiki: the column is a level ("For generated item/monster modifiers the minimum item/monster level"). Dump: `spawn_weights: []`, `generation_weights: []` for all 256. Craft of Exile (`sources/raw/coe`): no Heist enchant data (grep). PoEDB: Name / Level / Description. Prototype (`git show archive/prototype`): the orbs are not modelled ("Heist/flask enchantments ... catalogue-only", `docs/research/phase0-coverage.md`).
- **One odds datum**, second-hand: forum thread https://www.pathofexile.com/forum/view-thread/3813036 "Tailoring Orb - Can have 1 additional Crafted Modifier" (about 474 days old on 2026-10-31, i.e. mid 2025; pool then 75, before the 3.29.0 removal). Read only through a web-search snippet (Cloudflare/429 stopped the page): the poster "spent over 600 Tailorings" without the mod and quotes "a reddit post where a guy made a speadsheet of heist drops and out of the calculation this mod should appear once every 283 time"; a reply says 600 misses at 1/283 is normal. Check with a uniform pool of 75: P(no hit in 600) = (1 - 1/75)^600 = 0.03%, at 1/283: 12%. If the report is true the pool is not uniform. Not admitted as a claim: second-hand, spreadsheet not located, thread unread.
- Nothing in any source says how the pool is structured (per mod, per level group, per tag). The entries are built from a small grid (a tag, a rider, a level), so a grouped weighting is plausible, but that is a guess, not evidence.

## 4. Measurement design

**Goal.** Estimate P(enchant = e) for the 136 + 54 enchants, or the weights of whatever groups structure them.

**What can and cannot be measured.**

- A single enchant with p = 1/283 needs 3/p = **850 clicks** just to show it exists at 95% (rule of three: zero hits in 850 gives upper bound 0.35%) and **about 4,400 clicks** to know p within +/-50% (n = z^2 (1-p) / (p r^2) = 3.84 / (0.00353 x 0.25)). At PoEDB's 1.44 Div (Tempering) to 2.15 Div (Tailoring) per orb that is 6,000 to 9,500 Div: not a plan.
- Group-level shares are affordable: with n clicks, a group of true share q is estimated to +/-1.96 sqrt(q(1-q)/n). For the body-armour pool by required-level groups (7 / 6 / 20 / 17 / 3 / 1 mods): n = 400 gives +/-4.2 points on a 25% group and +/-2.1 points on a 5% group; it separates "uniform over 54" from a structure in which the large groups (20 and 17 mods) differ by ten points or more, and it does not resolve the 3-mod and 1-mod groups. 400 Tailoring Orbs ~ 860 Div at the PoEDB price.
- Cheaper alternatives, none unbiased: (a) the trade site's listing counts per enchant text (selection bias: sellers keep the good ones); (b) the rate of ready-made "Enchanted Rare" items in Curio Displays (a different draw; unknown relation); (c) players who already hold large logs (the Reddit spreadsheet above, Heist streamers).

**Protocol if the owner wants it.** One cheap body armour (or weapon), identical base, never corrupted, no mods needed. Click the orb on it N times; after each click record the enchant text (and the socket line, to answer O-03 at the same time) in a CSV; the click replaces the old enchant so nothing accumulates. Stop rule: the full 400, or sooner if the Bayesian pool-structure comparison (uniform vs. level-group weights) reaches a likelihood ratio of 100. Analysis: multinomial counts per enchant, chi-square against uniform, then a Dirichlet posterior per group; report 95% intervals, not the point estimate. A weapon run has 136 categories, so for the same power it needs about 2.5x the clicks (1,000 clicks): do the armour pool first.

**Recommendation.** Do not buy the sample. Model the weights as an explicit assumption set in the solver (uniform, and the 1/283-consistent tier model as the pessimistic bound) and let the "approximate answer" mode (#83) report the cost as a range with a flag; run the measurement only if the owner wants B7 targets with an enchant to be priced exactly. Ask Reddit (via the owner's trusted sources) for an existing log before spending Divines.

## 5. Prices (inputs, not rules)

| Item | Source | Value | Date | Note |
|---|---|---|---|---|
| Tempering Orb | PoEDB US realm exchange | 1.44 Divine / 1 (vol 453); 471 Chaos / 1 (vol 150) | 2026-10-31 | league not named on the page |
| Tailoring Orb | PoEDB US realm exchange | 2.15 Divine / 1 (vol 527); 570 Chaos / 1 (vol 99) | 2026-10-31 | same page type |
| Tempering Orb | outof.games (via web search) | ~19.4 Chaos; Divine ~383 Chaos | late July 2026 | stale; 24x off |
| Tailoring Orb | vhpg.com guide (via web search) | ~88 Chaos | undated | old |
| Bench removal | wiki / dump | 3 Orbs of Scouring | | |
| Quality enchant | wiki | 3,250 / 5,000 Lifeforce items | | prices from #84 |

The PoEDB rows imply 327 and 265 Chaos per Divine in the two pairs, so even inside one page the pairs are not consistent. Take the orb price from the price layer's source, not from this note.

## 6. Open points and questions for the owner

**Open points (not settled by a source I could read)**

- **O-01 Weights.** Unpublished; section 4. Blocks exact costs for enchant targets.
- **O-02 Body armour pool of 54.** Derived by removing the 21 mods named by the 3.29.0 note from the 75 the dump and the (stale) wiki page list. One click series on a body armour (look for a white-socket or all-one-colour result) or a newer wiki edit would confirm; the page's edit history after 26 July 2026 was not checked.
- **O-03 Socket reforge.** Which results reforge, what the reforge does (re-roll the number, colours, links), whether it cannot lower the item below what the enchant allows ("-3 to maximum Sockets" on a 6-socket piece), what happens to existing links, and how it works with the 3.29.0 colour rework (#99). No source read. A handful of clicks on a cheap body armour with 6 sockets answers it.
- **O-04 Colour mapping** of the three "No X sockets" enchants (mod id vs. text swap, ENC-07).
- **O-05 Slot exclusivity** of a Harvest quality enchant with a Tempering / Tailoring enchant (ENC-17); the wiki's general rule says they replace each other.
- **O-06 Additional crafted modifier.** How many extra crafts (+1 means two crafted mods?), whether it stacks with the metamod "of Crafting" (3 in total?), and which items accept it. Draft claim keeps it open.
- **O-07 Reddit.** Not reached: `gpt-research` timed out six times; the forum was blocked. A rerun later (or the owner's trusted posts) could settle O-01, O-03, O-06 and replace the second-hand 1/283 figure with a first-hand one.
- **O-08 Item level / base gating.** Do any enchants not roll below a given item level or on some bases (e.g. quivers are not weapons for the orb, claws vs bows)? The dump has no gating (no spawn tags) and no source states any; assume none.
- **O-09 Price source** (above).

**Questions for the owner (the main chat asks; each with my recommendation)**

1. *Do enchant targets need exact odds now?* The weights are unpublished; an exact figure costs on the order of 800 Divines of orbs (section 4). Options: (a) price enchants with an explicit assumption range and a flag (cheap, honest, the cost is a range); (b) buy the sample; (c) wait for a community log. **Recommend (a)**, with (c) tried first.
2. *May a target ask for a quality enchant and a Heist enchant on the same body armour?* If the wiki's rule is right they replace each other, so the planner must refuse the combination. **Recommend refusing it** (O-05), unless an in-game check shows two slots.
3. *Should the planner offer "rolling the enchant until it fits" on a mod-crafted item?* The socket reforge (O-03) can ruin links, so enchanting last would be safe only if the item has no socket target. **Recommend the order enchant-first, sockets after**, since the 3.29 socket work (B6) comes after it anyway and a pre-built 6-link would be lost.
4. *What cost is acceptable for an enchant target?* By PoEDB's price a clean Life enchant is about 15 to 30 Divine and the extra crafted slot 100 to 600. **Recommend** treating the orb as a plain price-layer input like any currency and letting the player's own budget filter the route, not a rule in the planner.

## 7. Method and gaps

- Read: wiki pages above (built-in browser; table rows counted by script), the repoe-fork 3.29.3.3 dump in `.claude/scratch/real-cache/repoe-fork/3.29.3.3` (`mods.json`, `crafting_bench_options.json`, `base_items.json`), PoEDB pages (Tempering Orb, Tailoring Orb, Heist Enchantment Modification: a challenge page, "equip 10 of 14 enchants", not a pool), `sources/raw/coe` (no enchant data), the prototype (catalogue-only), inventory rows M-18, M-74 to M-79.
- `gpt-research` jobs, all `terra`, all failed with "timed out": 20261031-140322-cd8f (wide brief), 20261031-140504-22ae and 20261031-140529-4337 (the same brief split in two), 20261031-140921-854c and 20261031-140922-f959 (single-question briefs), 20261031-141046-c3f5 (one-line brief). No report text exists to quote.
- Pathofexile.com forum pages returned a Cloudflare challenge (browser pane hidden) or HTTP 429 (fetch agent), so the official 3.29.0 thread and thread 3813036 were not read directly; the 3.29.0 sentence is verified on two wiki pages (Version 3.29.0 and the Tempering Orb history, which carry it verbatim) and the thread's content only through a search snippet.
- Not verified: the Curio Display chance of an orb or an Enchanted Rare (no weights), PoEDB's league.
