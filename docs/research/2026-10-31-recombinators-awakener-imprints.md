# Awakener's Orb, recombinators and imprints in 3.29

Research ticket [#90](https://github.com/Rasslabsya4el/crafting-system/issues/90), inventory rows M-43 to M-46, for the B3 grill ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94)) beside the solver ticket [#91](https://github.com/Rasslabsya4el/crafting-system/issues/91). Checked on 2026-10-31 against patch 3.29.3.3. It re-checks `2026-10-30-3-multi-item-recombinators.md`, ADR-0011 and ADR-0012; it does not redo the solver survey.

## Answer in brief

1. **Awakener's Orb is fully specified except three points.** Two rare-or-magic items of the same class, each with exactly one influence, different from each other, none corrupted. The donor is destroyed; the receiver becomes a rare with both influences, keeps one influenced mod from each input (picked at random if an input has several), and every other mod is rerolled "as if using a chaos orb". Open: which influenced mod survives when the two share a mod group (the wiki says random, Craft of Exile says always the receiver's), whether the two kept mods count inside the 4/5/6 total (Craft of Exile: yes), and the exact refusal list for mirrored/fractured/synthesised items.
2. **Unpredictable recombination: the pooling and count rules are published and agree across the wiki, the owner-trusted 3.25 guide and the 3.26 follow-ups; the selection rule is not.** Prefixes and suffixes are pooled per side; the kept count comes from a table over the pooled count (1: 41% none, 59% one; 2: 67/33; 3: 39/52/10; 4: 11/59/31; 5: 43/57; 6: 28/72, the wiki rounds 3, 4 and 6 differently); the base is 50/50; item level is `min(floor((A+B)/2 + 2), max(A,B))`.
3. **ADR-0012's direction looks wrong and should be re-opened.** It admits only rules where rarer mods are kept at least as often as common ones. Every measurement we have points the other way: the 3.25 guide (written after the 3.25.1 note) says "modifiers with higher weights are more likely", the 3.26 follow-up says retention is "lower than 50%" for "extremely low weight" mods, and the wiki says the same. The 3.25.1 note only says rarer mods got "a much higher chance … than before", which fits a flattened rule between weight-proportional and equal chance. Section 5 proposes the family `P ∝ weight^α`, α in [0, 1], and shows the interval is wide (one rare target mod: 55% at α = 0, 4% at α = 1).
4. **The exclusive-mod trick of the 3.25 guide (its section 7, benchmark R26) is dead since 3.26.** The 3.26 notes cut the output count for inputs full of mods that cannot roll naturally, and the guide's author reports exclusive mods now count once per side and the 50/50 side-order no longer holds. R26's `still_valid: yes` is wrong for its exclusive-mod steps.
5. **Predictable recombination exists since 3.26 and destroys both inputs on failure; its PoE 1 formula is not published.** The only formula is the PoE 2 one (success contribution per selected mod, each capped at 50%), which the 3.25-guide author says PoE 1's predictable mode follows. No benchmark route in R15-R19, R25-R29 needs it.
6. **Cost: the Thaumaturgic Dust and Gold price of a recombination has no published formula.** PoEDB has two datamined constants (multiplier 3, exponent 0.75) and players report 50 000 to 250 000 Dust per combine. Dust has no market listing that I could find, so "priced from the market" (owner decision, [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)) needs a rule; see question 1.
7. **Imprints: two beast recipes since 3.29 (magic items with the Craicic Croaker, Rare Talismans with the Fenumal Plagued Arachnid); the Eternal Orb is drop-disabled.** An imprint restores mods, quality, strands and the like; it refuses fractured, corrupted and mirrored items and cannot restore a recombinator output.

## How this was read

| Tag | Source | Read |
|---|---|---|
| W-rec | [poewiki.net/wiki/Recombinator](https://www.poewiki.net/wiki/Recombinator) (carries a banner "needs to be updated: predictable recombination") | 2026-10-31, built-in browser |
| W-awk | [poewiki.net/wiki/Awakener's_Orb](https://www.poewiki.net/wiki/Awakener%27s_Orb) | 2026-10-31 |
| W-imp | [poewiki.net/wiki/Imprint](https://www.poewiki.net/wiki/Imprint) | 2026-10-31 |
| W-beast | [poewiki.net/wiki/Beastcrafting](https://www.poewiki.net/wiki/Beastcrafting) | 2026-10-31 |
| W-king | [poewiki.net/wiki/Kingsmarch](https://www.poewiki.net/wiki/Kingsmarch) (the Thaumaturgic Dust page redirects here; also flagged outdated) | 2026-10-31 |
| N-ver | Patch notes as reproduced by the wiki's version pages: [3.25.1](https://www.poewiki.net/wiki/Version_3.25.1), [3.26.0](https://www.poewiki.net/wiki/Version_3.26.0), [3.27.0](https://www.poewiki.net/wiki/Version_3.27.0), [3.28.0](https://www.poewiki.net/wiki/Version_3.28.0), [3.29.0](https://www.poewiki.net/wiki/Version_3.29.0), 3.29.0b, 3.29.1, 3.29.2, 3.29.3 | 2026-10-31; a text search for recombin, imprint, awakener, dust, disenchant, Rog |
| DM | repoe-fork 3.29.3.3 `base_items.json` (pinned dump `.claude/scratch/real-cache`) | 2026-10-31 |
| PDB | [poedb.tw/us/Kingsmarch](https://poedb.tw/us/Kingsmarch) constants table | 2026-10-31 |
| COE | Craft of Exile `package.js` (`sources/raw/coe`): `poec_simRecombinate`, `poec_simAwaken`, `poec_simRerollItem`; `basics.html` | local copy, read 2026-10-31 |
| R325 | Reddit, Butsicles, [3.25 Updated Guide to Recombinators](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/) (owner-trusted; about 500-800 combines; edits of 2024-08-21 and 08-23) | cached full text, `sources/raw/research/recomb-reddit-3.25-and-links.txt`, crawl 2026-09 |
| R326 | Reddit, Butsicles, [3.26 Recomb PSAs](https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/) and statistically-typed, [3.26 recombinators analysis/guide](https://www.reddit.com/r/pathofexile/comments/1lfyxxd/326_recombinators_analysisguide/) with its [Codeberg guide](https://codeberg.org/poe_notes/poe_notes/src/branch/main/Recombinators.md) | cached text (posts and top comments), crawl 2026-09 |
| PoE2 | Reddit, Butsicles, [PoE 2 0.2.0 recombinator guide, part 1](https://www.reddit.com/r/PathOfExile2/comments/1jzu2py/poe_2_patch_020_guide_to_recombinators_part_1/) | cached text |
| 3P | [poedustcalculator.app](https://poedustcalculator.app/) (third-party, poe.ninja prices, disenchant yields only) | 2026-10-31 |

**What I could not do.** The `gpt-research` tool failed on all six runs (timeouts or a dead worker), so the Reddit post was read in the cached copy only: its comments after the crawl and any later edit are not seen, and no search for 3.27-3.29 recombinator posts on Reddit was possible. The wiki version pages show no recombinator, Awakener's Orb or Dust change in 3.27, 3.28 or 3.29.x; the wiki's own history table for the Recombinator agrees (last entry 3.27.0: a Dust counter). Absence of a note is not proof the behaviour is unchanged, so the Reddit-based rules carry the patch they were measured in (3.25 or 3.26).

## 1. Awakener's Orb (M-43)

### Rules

| # | Rule | Source |
|---|---|---|
| A1 | Two items of the same item class; the donor is destroyed, the receiver is kept. | DM: "left click an item of the same item class you wish to apply it to"; W-awk |
| A2 | Each item has exactly one influence and the two differ. | W-awk: "Each item must have exactly one influence." |
| A3 | Corrupted donor or receiver: refused. | W-awk |
| A4 | The receiver is reforged as a rare with both influences. Receiver keeps base type, item level, sockets, links, quality and enchantments. | DM description; W-awk |
| A5 | One influenced mod from each input is kept (tier kept, value rerolled); if an input has several, one is picked at random. Craft of Exile picks uniformly among the valid (receiver mod, donor mod) pairs. | W-awk; COE `poec_simAwaken` (`poec_rand(0,nvcombs.length)`) |
| A6 | If the two kept mods share a mod group, only one survives. **Which one is disputed**: the wiki says "one will be discarded at random"; Craft of Exile always keeps the receiver's (`poec_simRerollItem`, the `mconflict` branch); a March 2020 player report lost the receiver's mod. In Craft of Exile the donor's influence is still added when its mod is dropped. | W-awk; COE; the prototype's Q20 |
| A7 | All other mods are rerolled "as if using a chaos orb". Craft of Exile draws the Chaos total (4/5/6 = 8:3:1) minus the kept influenced mods, the same convention as `chaos_orb.kept_mods_count_in_total`. | `basics.html` line 89; COE `prmods++` |
| A8 | Mastercrafting metamods (Prefixes/Suffixes Cannot Be Changed) are ignored by the reforge (since 3.9.1b). | W-awk |
| A9 | Mod groups made mutually exclusive since 3.10 (curse on hit on rings, "physical taken as" elements) and with multiple groups per mod in 3.19. Two such mods cannot be merged. | W-awk version history |
| A10 | An imprint made before the orb restores the receiver, never the donor. | W-awk, W-imp |
| A11 | Craft of Exile also disables the orb for an item level below 68 (influence needs 68). Not in the wiki. | COE line 2006 |
| A12 | The orb is drop-restricted (from Sirus), so its price comes from the market; it does not exist in Ruthless. | W-awk |

### What B3 needs from this

- **Action shape.** Two inputs (receiver, donor), one orb, donor cost = acquisition cost of the donor (ADR-0011), receiver state in; outcome distribution over rare items with a fixed pair of influences, a kept influenced mod pair and a Chaos-style fill. The only discrete choice is which pair is kept, uniform per both sources; the fill reuses the Chaos Orb draw.
- **Refuse, or bound, the group-conflict case.** The outcome of a conflict is binary (receiver's mod survives or donor's), so ADR-0012's best/worst interval covers it exactly: report [receiver survives, donor survives] and do not choose. Benchmarks R18 and R19 avoid the case by construction (the guide for R18 says to check "each input has exactly one influence modifier" and different groups).
- **The sample route R18** (Crusader ES ring + Shaper Assassin's Mark) is valid if the two target mods are in different groups in 3.29 data; its note on the stale mod text stands. **R19** works because the metamod is crafted after the orb.
- **Open:** exact refusal list for mirrored, fractured and synthesised items (3.29: non-unique synthesised items no longer exist, and Fracturing cannot be used on influenced items, so fractured and influenced do not co-occur); whether the kept mods count in the total in the real game (only Craft of Exile says so).

## 2. Recombinators, common rules (M-44)

The Recombinator is a Kingsmarch crafting bench in 3.26+ (fully upgraded from the start); the old Sentinel "Recombinator" currency items were deleted in permanent leagues (3.26.0). It has two modes, a toggle in the window.

### Inputs and the new item

| # | Rule | Source |
|---|---|---|
| C1 | Two **magic or rare** equipment items of the same item class. Corrupted items and normal items were removed in 3.26. Jewels, flasks, gems and maps are not listed (idols only in Standard/Phrecia). The legacy currency was split armour / weapons+quivers / jewellery. | W-rec; N-ver 3.26.0 ("Corrupted items can no longer be recombinated"); DM |
| C2 | The output is a new item; both inputs are consumed in both modes; imprints do not work on it. | W-rec, W-imp |
| C3 | Costs Gold and Thaumaturgic Dust; "depends on the item level and modifiers of the input items". | W-rec |
| C4 | Base chosen 50/50 for unpredictable mode. Copied from the chosen base: base type, influences and influence-like status (fractured, synthesised, eldritch), anointment, enchantments, **quality including catalysts**, implicits, sockets and links. Lost: imprints, Crucible tree, foresight, intangibility. Defence percentile is rerolled. | W-rec; R325 (50/50, "defence percentile … rerolled") |
| C5 | Item level = `min(floor((A+B)/2 + 2), max(A,B))` (100/1 gives 52, 84/79 gives 83). Craft of Exile's `floor((A+B)/2)` is out of date. | W-rec |
| C6 | Mods can land on an item of lower item level than the mod needs. | R325 |
| C7 | Memory Strands stay with the chosen base and are not combined. | R326 (post and a reply, Butsicles) |
| C8 | Output rarity follows its mods: none gives a normal item, one per side a magic item, two or more on a side a rare item (Craft of Exile; matches the guide's 1p/1s results). | COE `poec_simRecombinate` |
| C9 | The output cannot exceed the chosen base's own affix caps per side (3/3 normally; Craft of Exile has per-base caps for the special amulets and rings), even if the pool exceeded 6. | W-rec ("can still only select a maximum of 3"); COE `usemaxaff` |

### Gaps in C-rules

- **Jewels:** nothing says a jewel is accepted; treat as ineligible (question 2).
- **Mirrored items:** not stated (mirrored items cannot be modified anyway).
- **Gold:** no formula or number anywhere except player comments ("300 k gold" for a big craft).

## 3. Unpredictable mode: counts and selection

### Process (R325 section 5, W-rec; 3.26 adjustments in 3.4)

1. Pick the base (50/50).
2. Pool prefixes and suffixes of both inputs separately. Duplicates both enter the pool. NNN and exclusive mods count in the pool total; fractured mods count only if their own base is the chosen one.
3. The final prefix count and suffix count are drawn **independently** from a table over the pooled count of that side. One exception: 1p/0s + 0p/1s has three equally likely outcomes (1p, 1s, 1p1s), never a white item.
4. One side is filled first (50/50 in the 3.25 data); mods are taken one at a time from the pool, each pick removing every mod of the same mod group. If an exclusive mod is picked, all other exclusive mods of both pools become ineligible; if a base-bound (NNN) mod cannot sit on the chosen base it is ineligible. The count of step 3 is enforced as far as eligible mods remain, so it can be undershot.
5. Item level, rarity and the like follow section 2.

### The count table: three versions

| Pooled count | 3.25 guide (Table 1, edited 2024-08-21, measured) | Wiki ("estimated", unrounded 66.7/33.3) | Craft of Exile (Sentinel, stale) |
|---|---|---|---|
| 1 | none 41, one 59 | 41 / 59 | 33.3 / 66.7 |
| 2 | one 67, two 33 | 66.7 / 33.3 | 66.7 / 33.3 |
| 3 | one 39, two 52, three 10 | 40 / 50 / 10 | 30 / 50 / 20 |
| 4 | one 11, two 59, three 31 | 10 / 60 / 30 | 10 / 55 / 35 |
| 5 | two 43, three 57 | 43 / 57 | 50 / 50 |
| 6 | two 28, three 72 | 30 / 70 | 30 / 70 |

The guide's own text uses 72% for pool 6 and the wiki uses both 70 and 72 in its examples. Recommended: use the guide's measured table as the central estimate (rows 3 and 4 sum to 101 in print; renormalise) and keep the wiki's table as a second case, because the difference (about 2 points) is below the sampling noise of 500-800 combines. A 2026-09 route comment (R27) quotes "10%" for three prefixes from a pool of 3 and "30%" from a pool of 4, which both tables fit, so the table was still in use in 3.29.

### 3.26 changes that make 3.25 recipes obsolete

- Official 3.26.0: "will result in fewer modifiers on the item on average if the input items were using many modifiers that cannot normally roll on the item, for example Veiled Modifiers or Essence Modifiers".
- Butsicles, 3.26 PSA (about 70 tests, "take what I say with a slight grain of salt"): exclusive mods count as at most one mod per side even if there are several; the 50/50 first-side rule "looks to no longer be the case" when one side has only exclusive mods; "no more easy triple prefix combinations with exclusive modifiers"; the PoE 1 count tables "seem to be largely the same".
- Consequence: the filler/"counterweight" strategy of the 3.25 guide (its sections 7 and 8) and route **R26** no longer work as written. **R25, R27, R28** (plain doubling and pooled counts) are unaffected. A new, narrower use survives: statistically-typed's guide, comment by Butsicles, says a 1p/0s + 0p/1s combine can add one exclusive crafted mod on each side because the two sides "don't see each other", which can lift that step above 50%.

### Selection of which mods: the unresolved rule

What the sources say, in date order:

| Date | Statement | Source |
|---|---|---|
| 2024-07, 3.25.0 | Kingsmarch upgrade "Rarer Modifiers are more likely to be retained" (the wiki says it was "likely removed" in 3.26). | W-rec history |
| 2024-08-13, 3.25.1 | "rarer Modifiers now have a much higher chance to be selected for the resulting item than before." | N-ver 3.25.1 |
| 2024-08-21/23, R325 (after 3.25.1) | "the weights of these modifiers is also a factor, where modifiers with higher weights are more likely"; formula "not currently … fully fleshed out"; tiers "do not seem to be a factor if the weights are the same". | R325 |
| 3.26 (June 2025) | Butsicles: low-weight recombinations need more data; "lower than 50% in the case of extremely low weight modifiers"; you can "annul" low-weight mods by hoping they are not picked. statistically-typed shows 1/3 under equal chance and "closer to 10%" if weight-biased. | R326 |
| now | "Higher weight modifiers are more likely to be selected, although the exact formula is unknown." | W-rec |

Reading: before 3.25.1 the pick was weight-proportional; 3.25.1 flattened it ("much higher chance … than before" for the rare ones); every later statement still has retention rising with spawn weight. Nothing published says a rare mod is kept more often than a common one. The 3.25.1 note alone is also compatible with that reversal, but the post-patch guide and the 3.26 measurement are not.

## 4. Predictable mode

Introduced in 3.26.0: "decide which modifiers on the two items … (with a chance of success displayed to you)"; it "can result in the items being destroyed". The wiki's section is a stub. Known:

- Pick at least one mod from each input; both inputs are destroyed on failure; the output is the left or the right base with exactly the selected mods; wiki example: a rare mod on one base and a common one on the other showed 57% success, 43% both destroyed, and "the base containing the rarer mod will be chosen nearly every time".
- Exclusive and NNN mods "will disappear" in this mode (Butsicles); it "works the exact same way as it does in POE 2".
- PoE 2 formula (patch 0.2.0, Butsicles, part 1): each selected mod adds a success contribution proportional to the summed spawn weight of its own tier and every better tier on the other base, divided by the total weight on that side, each contribution capped at 50%; the PoE 2 sheet generalises it to more mods. Constants are base-specific, and sheet and post both carry version warnings (0.2 and 0.4). **Nobody has published PoE 1 constants.** The prototype's `recombinators_selected.md` already holds the sheet's multi-mod formula.
- Isolating a low-tier mod with a bad base: roughly 50.5-51% success (Butsicles, one setup).

For the planner: this is a different action (success or total loss, base choice weighted), not a variant of the unpredictable one. No benchmark route needs it. Recommendation in question 3.

## 5. The selection rule and ADR-0012's interval

**Finding.** ADR-0012 defines the admissible rules as those "under which the chance to keep a mod does not fall as its spawn weight falls (rarer mods are kept at least as often as common ones; … equal chance is the boundary)". The evidence in section 3 says the opposite direction: retention does not fall as weight rises, flattened since 3.25.1. Equal chance is still a boundary, but it is the *optimistic* boundary for a rare target mod, not the pessimistic one.

**Proposed family** (to settle in the grill): successive draws without replacement from the eligible pool of one side, `P(next = m) ∝ weight(m)^α`, with mod-group removal after each pick, α in [0, 1]. α = 0 is equal chance (the old prototype assumption, Craft of Exile's code); α = 1 is weight-proportional (the pre-3.25.1 rule and the literal reading of the wiki). A route's interval is the minimum and maximum of its success probability over a grid of α (the extreme need not sit at an end: for a set mixing rare and common targets it can be interior). The weights are the spawn weights of the mod on the chosen base (`mods.json`); for the exact weight used with duplicate tiers, see open point 3.

**Size of the interval** (my computation by exact enumeration of the successive draws; pool of 4 prefixes with weights 25 (rare), 1000, 1000, 400, count row 4 of the 3.25 table: 10/60/30):

| Target set | α = 0 | α = 0.5 | α = 1 |
|---|---|---|---|
| the rare mod only | 55% | 17% | 3.8% |
| rare + one common | 25% | 9.6% | 2.5% |
| two common | 25% | 50% | 64% |
| rare + two common | 7.5% | 4.4% | 1.5% |

(α = -1, the rare-favoured reading of ADR-0012, would give 98.6%, 30%, 3.9% and 3.8%.) So for routes whose targets include a rare mod the interval spans an order of magnitude, and the "best route" under the worst case may differ from the one under the best case. This is the main risk for R25-R29.

**How the family could be pinned down.** Butsicles's raw experiment sheet (cited as a data dump in R325) would let a fit of α; I could not open it. A direct test (many combines of one pair) costs Dust and Gold at the rates in section 6, so it is not worth asking the owner for it.

## 6. Dust and Gold

- Wiki: the Recombinator "costs Gold and Thaumaturgic Dust"; the amount depends on item level and mods. 3.27.0 added a Dust counter to the window.
- PoEDB (datamined): `RecombinatorModDustCostMultiplier = 3`, `RecombinatorModDustCostExponentTimes100 = 75`. They suggest a per-mod cost of the form `3 × x^0.75` summed over mods, but the quantity `x` and the Gold formula are not in any source I found. Treat as a hint only.
- Players (3.26): two T1 mods on magic items "easily give costs over 100,000" Dust; crafting two low-tier non-exclusive mods on the side you do not care about "will lower the dust cost by at least a factor of 2" and "as low as 50k"; one necrotic armour with an extra T1 suffix cost 250 000; "1-2 million dust … plus like 300 k gold" for a long craft.
- Supply: Dust comes from disenchanting at Kingsmarch (Rog in towns since 3.27) and "5% chance" Possessed-monster gear converting to Dust (3.26 Atlas keystone). The wiki's Kingsmarch page describes Dust yield by item level, quality (+2% per 1%), influence and corruption implicits (+50% each). A third-party calculator reports cheap uniques at about 150 000 Dust per Chaos plus a Gold fee of about 2 800-3 600 per item; **I found no trade or exchange listing for Dust or Gold**, so a "market price" does not exist as such.
- Consequence: with cheap uniques a combine costs about 1-2 Chaos of Dust, but Gold at the third-party's guess (5 Chaos per 10 000) would be 20-150 Chaos for the same combine. The unit price of Gold therefore matters more than Dust. Question 1.

Cost rule for the planner: cost per combine = f(items), table-driven and recorded per observed pair until a formula appears; the price file holds Dust and Gold unit prices.

## 7. Imprints (M-45) and the Eternal Orb

| Fact | Source |
|---|---|
| The Eternal Orb creates an imprint of any item; the `Imprint` restores it. | DM `CurrencyImprintOrb` ("Creates an imprint of an item for later restoration"); W-imp |
| Beast recipes: "Create an Imprint: Of a Magic Item" (1 Craicic Croaker, renamed from Chimeral in 3.29.0), "Of a Rare Talisman" (1 Fenumal Plagued Arachnid). The Talisman recipe replaced the amulet-to-Talisman transform in 3.29.0. | W-beast; N-ver 3.29.0 |
| The Eternal Orb has not dropped in any league since 2.0.0; since 3.28 it can be bought on the Currency Exchange in Standard only. | W-imp; N-ver 3.28.0 |
| Restores: implicit and explicit mods, enchantments, quality amount and type, base values (armour defence percentile), Memory Strand count, intangibility, the Crucible tree. Works on influenced, synthesised and eldritch-implicit items. It can undo the Harvest synthesise and an Awakener's Orb (receiver only). | W-imp |
| Refused: fractured items (an imprint made before a Fracturing Orb cannot undo it), corrupted and mirrored items. | W-imp |
| Not restorable: an item created from the original (recombinator output, Allflame, split items). Hinekora's Lock foresight is removed on imprinting and not restored. | W-imp |

For the planner: the imprint is a one-item restore point whose creation costs a beast (price from the beast listing) and whose use costs the `Imprint` it consumed. R17's loop (imprint, annul to the 1-mod core, restore on failure) is valid in 3.29. **Not stated anywhere:** whether an imprint is consumed on use, and whether an item can hold several imprints (question 4). Sockets and links are not in the restored list.

## 8. Benchmarks R15-R19, R25-R29

| Route | Needs from this note | Verdict |
|---|---|---|
| R15 (ED/chaos bow, 3.10) | magic-item imprint (Croaker), restore | Rules in section 7 apply; the route is old but the imprint is current. |
| R16 | none of the three (no imprint, no two-input action) | Out of scope of this note. |
| R17 (3.29 +2 Lightning Talisman) | rare-Talisman imprint, restore on failure, annul | Valid; needs claims `imprint.*`. |
| R18 (Crusader/Shaper ES ring) | Awakener, different groups, one influenced mod each | Valid; check group of the Assassin's Mark mod in 3.29 data. |
| R19 (Cyclone ring) | Awakener, then metamod reforge | Valid; consistent with A8. |
| R25 (generic triple T1 prefix) | doubling, count table, selection rule | Valid; its success odds sit inside the section 5 interval. |
| R26 (Necrotic, 3.25) | exclusive counterweights | **Not valid in 3.26+ for its exclusive steps** (section 3). |
| R27 (3.29 chest) | count table, an exclusive "Pantheon" suffix | Counts consistent with the table; the Pantheon suffix's exclusivity is not on any list (open point 4). |
| R28 (+2 amulet) | doubling, count table | Valid. |
| R29 (VLS dagger, 3.25) | influenced essence prefixes, doubling | Influenced mods need a base with that influence (both inputs are Shaper/Elder here). Valid for recombination; essence mods are exclusive so only one survives. |

## 9. Open points

1. Awakener group conflict (A6) and whether the kept mods count in the 4/5/6 total (A7).
2. The real selection rule: α is not measured. A fit to Butsicles's raw sheet would settle it (I could not fetch it). Until then every recombinator result is an interval (ADR-0012).
3. Which weight is used when the pool holds several tiers of one mod group, and how Craft of Exile's `weight` field maps onto the draw.
4. Exclusivity of the crafted mods "Upgraded", "of the Craft", Pantheon/boat suffixes; the guide's list is "non-exhaustive".
5. PoE 1 predictable mode: the formula, constants, the maximum number of selected mods, whether it works on every class, whether NNN and exclusive mods count as claimed.
6. The Dust and Gold formula (section 6); the unit prices.
7. Jewels: whether the bench accepts them (my reading: no).
8. Whether a recombinator output's catalyst quality is the chosen base's (W-rec says quality is copied, 50/50) matters for the catalyst-quality target of B2.
9. Any Reddit material from 3.27-3.29 (tool failed).
10. The prototype's `recombinators.md` and `awakener_orb.md` still hold Q9, Q12, Q16, Q20, Q21, Q22 as open; this note answers Q21 (use the guide table, wiki as second case) and narrows Q20 and Q22 to an interval; it does not close Q9.

## 10. Questions for the owner, each with my recommendation

1. **How should the system price Thaumaturgic Dust and Gold?** Neither is on the trade site or the currency exchange as far as I found; Dust comes only from disenchanting (which you dropped) or Possessed-monster gear. Options: (a) two numbers you set in the price file, with defaults taken from the cheapest-unique rate (about 150 000 Dust per Chaos) and a Gold value you pick; (b) ignore both; (c) treat Dust as the Chaos value of the cheapest item you would disenchant. **Recommended: (a)**, flagged as approximate in every report, because Gold may dominate the cost of a combine and only you know what an hour of Kingsmarch gold is worth to you.
2. **Do jewels go into the recombinator?** My reading of the wiki and the game data is no. **Recommended: treat jewels as ineligible** and drop jewel recombinator routes; if you ever saw a jewel accepted, tell us.
3. **Do you want predictable recombination in B3?** Its PoE 1 formula is unpublished, and no benchmark route uses it. **Recommended: ship B3 with the unpredictable mode only**, add the predictable one later as a flagged, unvalidated action if a route you care about needs it.
4. **Imprint behaviour that only the game shows:** is an imprint used up when it restores, and can one item carry more than one imprint (for example one from before and one after a regal)? **Recommended: assume one imprint is used up by one restore and an item carries one**, unless you can check in the game in two minutes.
5. **The rarity direction of the interval.** ADR-0012 was written on the belief that rare mods are kept as often as or more often than common ones; the evidence says the reverse. **Recommended: amend ADR-0012 to the family of section 5** (weights to the power α, α from 0 to 1) and accept that intervals for routes with rare target mods will be very wide (a factor of ten or more). You decide whether such an interval is still useful or whether recombinators wait until someone measures α.
6. **Awakener group conflict.** **Recommended: report the interval between "receiver's mod survives" and "donor's mod survives"** rather than refusing the pair, since the outcome is binary and ADR-0012 already covers it.

## 11. Draft claims for `src/crafting_system/rules/claims/`

Seven fields as in the existing files (`id`, `statement`, `source_kind`, `url`, `quote`, `patch_verified`, `date_checked`), plus `value` where there is a number. Reddit-based claims carry the patch they were measured in; `date_checked` is the day the text was read (2026-09-21 for the cached Reddit copies, 2026-10-31 otherwise). Quotes are kept to fragments.

### `awakener.yaml`

```yaml
# Mechanic family: awakener (Awakener's Orb, M-43). Research ticket #90.
rules:
  - id: awakener.two_items_same_class
    statement: An Awakener's Orb takes a donor item and a receiver item of the same item class; the donor is destroyed.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "Destroys an item, applying its influence to another of the same item class"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.receiver_reforged_rare_both_influences
    statement: The receiver becomes a rare item with the influences of both inputs and new modifiers.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "The second item is reforged as a rare item with both influence types and new modifiers"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.one_influence_each_and_different
    statement: Each input must carry exactly one influence and the two influences must differ; otherwise the orb is refused.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "Each item must have exactly one influence."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.refused_on_corrupted
    statement: Neither input may be corrupted.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "both the donor item and the base item must be uncorrupted"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.keeps_base_level_sockets_quality_enchants
    statement: The receiver keeps its base type, item level, sockets, links, quality and enchantments.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "base type, item level, sockets, links, quality and enchantments are retained"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.one_influenced_mod_per_input_kept
    statement: One influenced mod of each input is kept on the result (the tier stays, the value roll is redrawn); if an input has several, one is chosen at random. Prefix or suffix does not matter.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "If an item has two or more influenced mods, one will be selected at random"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.pair_choice_uniform
    statement: Craft of Exile chooses uniformly among the valid (receiver influenced mod, donor influenced mod) pairs, where valid means different influence group and different mod id.
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "nvcombs.push({"m1":j,"m2":k})"
    patch_verified: "3.29.0.3"
    date_checked: 2026-10-31

  - id: awakener.same_mod_group_keeps_one
    statement: When the two kept mods share a mod group, only one of them stays on the result. Which one is disputed (awakener.survivor_wiki, awakener.survivor_coe); the planner reports the interval between the two readings.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "the two merged mods cannot share the same ModGroup"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.survivor_wiki
    statement: The wiki says one of two same-group mods is discarded at random (no odds given).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "one will be discarded at random"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.survivor_coe
    statement: Craft of Exile keeps the receiver's mod and drops the donor's when they share a mod group, and still adds the donor's influence.
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "if(!mconflict){useaffixes.push(jQuery.parseJSON(JSON.stringify(woke.m2)))}"
    patch_verified: "3.29.0.3"
    date_checked: 2026-10-31

  - id: awakener.rest_rerolled_like_chaos
    statement: Every other modifier is rerolled as a Chaos Orb rerolls a rare (4, 5 or 6 mods, 8:3:1, affix_count.rare_reroll_ratio).
    source_kind: coe
    url: https://www.craftofexile.com/
    quote: "rerolled as if using a chaos orb"
    patch_verified: "3.29.0.3"
    date_checked: 2026-10-31

  - id: awakener.kept_mods_count_in_total
    statement: Craft of Exile draws the Chaos total minus the kept influenced mods, so the two kept mods count inside the 4/5/6. The wiki is silent; unverified in the game (open point 1).
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "poec_simRollAffix(null,null,null,fossil,noaffix-prmods"
    patch_verified: "3.29.0.3"
    date_checked: 2026-10-31

  - id: awakener.ignores_metamods
    statement: The reforge ignores the crafted metamods (Prefixes/Suffixes Cannot Be Changed and the like).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Awakener%27s_Orb#Mechanics
    quote: "will ignore Mastercrafting Metamods like Suffixes Cannot Be Changed"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: awakener.imprint_restores_receiver_only
    statement: An imprint of the receiver made before the orb restores it; the destroyed donor cannot be restored.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Mechanics
    quote: "The donor base cannot be restored"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

### `recombinator.yaml`

```yaml
# Mechanic family: recombinator (the Kingsmarch bench, M-44). Research ticket #90.
# Unpredictable-mode numbers are player measurements (Butsicles, patch 3.25, rechecked 3.26).
rules:
  - id: recombinator.inputs_magic_or_rare_same_class
    statement: The bench takes two magic or rare equipment items of the same item class. Corrupted items and normal items are refused since 3.26.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator
    quote: "combines two magic or rare equipment items of the same item class"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.corrupted_refused
    statement: Corrupted items can no longer be recombined (3.26.0).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator
    quote: "Corrupted items can no longer be recombinated."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.both_inputs_consumed
    statement: Both modes consume both inputs; the output is a new item, so no imprint of an input restores it.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator
    quote: "Both operating modes destroy the input items."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.base_chosen_even
    statement: In unpredictable mode each input is the base of the output with probability 1/2.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Base_creation
    quote: "Both inputs have equal chance to be selected."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: 0.5

  - id: recombinator.properties_from_chosen_base
    statement: The output copies from the chosen base its base type, influences and influence-like status, anointments, enchantments, quality (catalysts included), implicits, sockets and links; item level is derived and the defence percentile is rerolled.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Base_creation
    quote: "Quality (including Catalysts)"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.item_level_formula
    statement: The output item level is min(floor((A + B) / 2 + 2), max(A, B)).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Base_creation
    quote: "average of the inputs' item level plus 2, rounded down"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.memory_strands_stay_with_base
    statement: Memory Strands stay with the chosen base and are not combined.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/
    quote: "Stay with base, do not combine"
    patch_verified: "3.26"
    date_checked: 2026-09-21

  - id: recombinator.pools_per_side
    statement: The prefixes of both inputs form one pool and the suffixes another; the two sides are drawn independently, except for 1 prefix + 1 suffix on separate inputs, which gives 1p, 1s or 1p1s, one third each.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/
    quote: "only 3 outcomes: 1p/0s, 0p/1s and 1p1s"
    patch_verified: "3.26"
    date_checked: 2026-09-21

  - id: recombinator.count_table
    statement: The number of mods kept on a side depends only on the pooled count on that side (percent; renormalise rows 3 and 4). Measured in 3.25, "largely the same" in 3.26.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/
    quote: "Table 1: Conditional final affix number distributions."
    patch_verified: "3.26"
    date_checked: 2026-09-21
    value: {1: {0: 41, 1: 59}, 2: {1: 67, 2: 33}, 3: {1: 39, 2: 52, 3: 10}, 4: {1: 11, 2: 59, 3: 31}, 5: {2: 43, 3: 57}, 6: {2: 28, 3: 72}}

  - id: recombinator.count_table_wiki
    statement: The wiki's estimate of the same table, a second case for the planner.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Determining_the_number_of_modifier_affixes
    quote: "These estimated probabilities are described in Table 1."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {1: {0: 41, 1: 59}, 2: {1: 66.7, 2: 33.3}, 3: {1: 40, 2: 50, 3: 10}, 4: {1: 10, 2: 60, 3: 30}, 5: {2: 43, 3: 57}, 6: {2: 30, 3: 70}}

  - id: recombinator.output_capped_by_chosen_base
    statement: The output holds at most the chosen base's affix cap per side (3 and 3 on an ordinary rare) even if the pool is larger.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Other_advanced_use_cases
    quote: "can still only select a maximum of 3 prefixes/suffixes"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.duplicates_enter_pool
    statement: A mod present on both inputs enters the pool twice (mod doubling raises the pooled count and the chance of that mod being picked), but once one of them is picked the other is ineligible (same mod group).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Modifier_doubling/blocking
    quote: "increase the chance for a strength roll to be chosen during modifier selection"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.mod_group_exclusion
    statement: Once a mod is picked, every mod of the same mod group is ineligible for the rest of the draw.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Modifier_Selection
    quote: "all modifiers sharing its \"mod group\" are ineligible for selection"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.side_filled_first_even
    statement: Prefixes or suffixes are filled first with probability 1/2 (measured in 3.25; 3.26 reports it no longer holds when one side holds only exclusive mods).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Modifier_Selection
    quote: "The suffixes or prefixes are filled first with 50/50 odds."
    patch_verified: "3.26"
    date_checked: 2026-10-31
    value: 0.5

  - id: recombinator.nnn_needs_native_base
    statement: A mod that needs a specific base (influenced, attribute-bound, base-type-bound) counts in the pool but cannot appear if the chosen base is not native to it. A fractured mod counts only if its own base is chosen.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Special_modifiers:_Non-native,_natural_modifiers_(NNN)
    quote: "cannot appear on the final recombinated item if their \"native\" condition is not satisfied"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.one_exclusive_per_item
    statement: At most one exclusive mod (essence without a tier, beast aspect, veiled, crafted, metacrafted, delve, Breach and Incursion mods, elevated influenced mods) stays on the output; picking one removes the others of both pools.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Special_modifiers:_Exclusive_Modifiers
    quote: "Only one modifier from this list can be present on a recombinated output item."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.fewer_mods_when_inputs_cannot_roll
    statement: Since 3.26 the output holds fewer mods on average when the inputs carry many mods that cannot normally roll on the item (veiled, essence); the old filler strategy of padding with such mods no longer works.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.26.0
    quote: "fewer modifiers on the item on average"
    patch_verified: "3.26"
    date_checked: 2026-10-31

  - id: recombinator.exclusive_counting_report
    statement: Butsicles reports exclusive modifiers count as one on that side and the first side is no longer 50/50 when a side holds only exclusive mods (about 70 tests).
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/
    quote: "exclusive modifiers only count as 1 modifier on that side"
    patch_verified: "3.26"
    date_checked: 2026-09-21

  - id: recombinator.selection_weighted_formula_unknown
    statement: Which eligible mods are picked depends on spawn weight with higher-weight mods more likely; the formula is unknown. The planner treats the rule as an interval over exponents alpha in [0, 1] (selection chance proportional to weight^alpha).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Modifier_Selection
    quote: "Higher weight modifiers are more likely to be selected"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.rarer_mods_note_3_25_1
    statement: Patch 3.25.1 raised the chance of rarer mods against the earlier rule; it does not say rarer mods are kept more often than common ones.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.25.1
    quote: "rarer Modifiers now have a much higher chance to be selected"
    patch_verified: "3.25.1"
    date_checked: 2026-10-31

  - id: recombinator.guide_higher_weight_more_likely
    statement: The guide, written after 3.25.1, finds higher-weight mods more likely and tiers irrelevant at equal weight; the exact formula is not fleshed out.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/
    quote: "modifiers with higher weights are more likely"
    patch_verified: "3.25.1"
    date_checked: 2026-09-21

  - id: recombinator.low_weight_below_even_chance
    statement: In 3.26 the guide's author expects the odds of keeping an extremely low-weight mod to be below the equal-chance case.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1lfyxxd/326_recombinators_analysisguide/
    quote: "lower than 50% in the case of extremely low weight modifiers"
    patch_verified: "3.26"
    date_checked: 2026-09-21

  - id: recombinator.predictable_mode
    statement: Predictable mode: the player selects the mods to merge and sees a success chance; on failure both inputs are destroyed and nothing is made. The PoE 1 formula is unpublished.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.26.0
    quote: "can result in the items being destroyed"
    patch_verified: "3.26"
    date_checked: 2026-10-31

  - id: recombinator.predictable_drops_exclusive_and_nnn
    statement: Exclusive and non-native mods vanish in predictable mode.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/
    quote: "will dissapear on \"predictable\" POE 2 recomb"
    patch_verified: "3.26"
    date_checked: 2026-09-21

  - id: recombinator.costs_gold_and_dust
    statement: A combine costs Gold and Thaumaturgic Dust; the amount depends on the item level and modifiers of the inputs. No formula is published.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator#Mechanics
    quote: "costs Gold and Thaumaturgic Dust"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator.dust_constants
    statement: The game data holds a Dust multiplier of 3 and an exponent of 0.75 for recombinator mods (their use is not documented).
    source_kind: datamined
    url: https://poedb.tw/us/Kingsmarch
    quote: "RecombinatorModDustCostExponentTimes100 75"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {multiplier: 3, exponent: 0.75}

  - id: recombinator.low_tier_crafted_mods_cut_dust
    statement: Crafting two low-tier non-exclusive mods on the side you do not care about lowers the Dust cost at least twofold.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/
    quote: "lower the dust cost by at least a factor of 2"
    patch_verified: "3.26"
    date_checked: 2026-09-21
```

### `imprint.yaml`

```yaml
# Mechanic family: imprint (M-45). Research ticket #90.
rules:
  - id: imprint.eternal_orb_creates
    statement: An Eternal Orb makes an imprint of an item; the Imprint restores that item to the imprinted state.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "Creates an imprint of an item for later restoration"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.eternal_orb_not_dropped
    statement: The Eternal Orb has not dropped in any league since 2.0.0; in Standard it can be bought on the Currency Exchange (3.28).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Version_history
    quote: "Eternal Orbs no longer drop in any league."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.beast_recipes
    statement: Two beast recipes make an imprint: of a magic item (Craicic Croaker) and of a rare Talisman (Fenumal Plagued Arachnid, since 3.29.0).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Beastcrafting
    quote: "Create an Imprint Of a Rare Talisman"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.restores_state
    statement: Restoring reverts implicit and explicit mods, enchantments, quality amount and type, base defence values and Memory Strand count; influenced, synthesised and eldritch-implicit items are allowed.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Mechanics
    quote: "Imprints will revert the item's implicit and explicit modifiers"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.refused_on_fractured
    statement: An imprint cannot be made of or used on a fractured item, and an imprint made before a Fracturing Orb cannot undo the fracture.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Mechanics
    quote: "Imprints cannot be made of or used on Fractured items."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.refused_on_corrupted_mirrored
    statement: An imprint cannot be made of or used on a corrupted or mirrored item (unless a modifier allows modifying it).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Mechanics
    quote: "cannot be created from or be used on corrupted or mirrored items"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.not_for_derived_items
    statement: A new item made from the original (recombinator output, Allflame crafting, split items) cannot be restored with the original's imprint.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Imprint#Mechanics
    quote: "the new item cannot have an Imprint used on it"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: imprint.talisman_craft_replaced_transform
    statement: In 3.29.0 the Bestiary craft that turned an amulet into a Talisman became the craft that makes an imprint of a rare Talisman.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.29.0
    quote: "replaced with a craft that creates an Imprint of a Rare Talisman"
    patch_verified: "3.29.0"
    date_checked: 2026-10-31
```
