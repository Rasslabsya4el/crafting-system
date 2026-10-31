# Awakener's Orb, recombinators and imprints in 3.29

Research ticket [#90](https://github.com/Rasslabsya4el/crafting-system/issues/90), inventory rows M-43 to M-46, for the B3 grill ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94)) beside the solver ticket [#91](https://github.com/Rasslabsya4el/crafting-system/issues/91). Checked on 2026-10-31 against patch 3.29.3.3. It re-checks `2026-10-30-3-multi-item-recombinators.md`, ADR-0011 and ADR-0012; it does not redo the solver survey.

## Answer in brief

1. **Awakener's Orb is fully specified except three points.** Two rare-or-magic items of the same class, each with exactly one influence, different from each other, none corrupted. The donor is destroyed; the receiver becomes a rare with both influences, keeps one influenced mod from each input (picked at random if an input has several), and every other mod is rerolled "as if using a chaos orb". Open: which influenced mod survives when the two share a mod group (the wiki says random, Craft of Exile says always the receiver's), whether the two kept mods count inside the 4/5/6 total (Craft of Exile: yes), and the exact refusal list for mirrored/fractured/synthesised items.
2. **Unpredictable recombination: the pooling and count rules are published and agree across the wiki, the owner-trusted 3.25 guide and the 3.26 follow-ups; the selection rule is not.** Prefixes and suffixes are pooled per side; the kept count comes from a table over the pooled count (1: 41% none, 59% one; 2: 67/33; 3: 39/52/10; 4: 11/59/31; 5: 43/57; 6: 28/72, the wiki rounds 3, 4 and 6 differently); the base is 50/50; item level is `min(floor((A+B)/2 + 2), max(A,B))`.
3. **ADR-0012's direction looks wrong and should be re-opened (re-checked first-hand on 2026-10-31).** It admits only rules where rarer mods are kept at least as often as common ones. In the guide's comment thread (725 comments read) the author writes, on 2024-08-21, that "Affix weights matter, but you want to avoid situations where they do, since those are definitely not in your favor for most valid use cases (e.g. +1 all spell skill gems, t1 flat ele, t1 % phys)"; his raw sheet has one contrast of chaos resistance (weight 250) kept 29% against other resistances (weight 1000) 75%; in 3.26 he computes with weights as proportional shares and says low-weight outcomes are "below" the even-chance figure. No one reports the reverse. But there is no fitted formula and no controlled sample ("hundreds more data points" needed, the author), and the first version of the guide says only that weighting is "factored in" with "specifics … not currently known". The 3.25.1 note says only "than before". So: the direction is well supported, the size is not. Section 5 proposes the family `P ∝ weight^α`, α in [0, 1], and shows the interval is wide (one rare target mod: 55% at α = 0, 4% at α = 1).
4. **The exclusive-mod trick of the 3.25 guide (its section 7, benchmark R26) is dead since 3.26, but NNN padding came back in 3.29.** The 3.26 notes cut the output count for inputs full of mods that cannot roll naturally, and the guide's author reports exclusive mods now count once per side and the 50/50 side-order no longer holds. R26's `still_valid: yes` is wrong for its exclusive-mod steps. In 3.29, Ducats add non-native mods (a belt prefix, Pantheon suffixes, attribute rerolls) that count in the pool and never transfer; players (August 2026, one thread of 101 comments, a counted example of 3/8 for a six-mod belt) use them as padding, and route R27 rests on it.
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

**Reddit, second pass (2026-10-31, after the tools were fixed).** Read first-hand through the Reddit archive tool: the 3.25 guide thread `1exyavx` (the first posted version, 725 comments with authors and dates), the 3.26 PSA thread `1ldc3lz` (127 comments) and the 3.26 analysis thread `1lfyxxd` (190 comments), plus the author's public raw sheet. The earlier cached copy was a later edit of the guide: it differs in Table 1 and carries the sentence about higher weights. See the second-pass results list at the end of section 9 for the searches I ran.

**First pass (superseded).** The `gpt-research` tool failed on all six runs (timeouts or a dead worker), so the first version of this note read the Reddit post in the cached copy only. The wiki version pages show no recombinator, Awakener's Orb or Dust change in 3.27, 3.28 or 3.29.x; the wiki's own history table for the Recombinator agrees (last entry 3.27.0: a Dust counter). Absence of a note is not proof the behaviour is unchanged, so the Reddit-based rules carry the patch they were measured in (3.25 or 3.26).

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

The guide's own text uses 72% for pool 6 and the wiki uses both 70 and 72 in its examples. Recommended: use the guide's measured table as the central estimate (rows 3 and 4 sum to 101 in print; renormalise) and keep the wiki's table as a second case.

**Sample sizes (first-hand, added 2026-10-31).** The author's raw sheet ("3.25 Recomb Diary", tab "Aggregated Mod data", read in the browser; [sheet](https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg)) holds the counts behind Table 1. Final mods per side, by pooled count (N = events): pool 1: 0 mods 89, 1 mod 128 (N 217); pool 2: 196 / 84 (N 280); pool 3: 124 / 171 / 26 (N 321); pool 4: 47 / 241 / 136 (N 424); pool 5: 151 (two) / 194 (three) (N 345); pool 6: 82 / 219 (N 301). The sheet's own percentages (pool 4: 11/57/32; pool 5: 44/56; pool 6: 27/73) differ from the printed table by up to 2 points. The first posted version of Table 1 (archive snapshot of 2024-08-21) had pool 3 = 46/46/8, pool 4 = 15/55/30, pool 5 = 57/43 (two/three: reversed) and pool 6 = 18/82; the author edited it the same day with "a lot of additional 6 mod data" (comment, u/Butsicles, 2024-08-21), and the guide itself says pool 5 "has a somewhat small sample size". So the count rows carry about ±3 points of sampling error (binomial, N 217-424) and the pool-5 row was unstable. Patch 3.26: u/Butsicles, 2025-06-17, "For 1 + 1 -> 2 recombs with regular weighted mods, it looks to be OK. Same goes for most other recombinations (such as 3-6 total mods on one affix side)" and 2025-06-22, "So far from 30-40 datapoints, seems approximately where it was pre-patch" (3.26 sample 30-50). A 2026-09 route comment (R27) quotes "10%" for three prefixes from a pool of 3 and "30%" from a pool of 4, which both tables fit.

### 3.26 changes that make 3.25 recipes obsolete

- Official 3.26.0: "will result in fewer modifiers on the item on average if the input items were using many modifiers that cannot normally roll on the item, for example Veiled Modifiers or Essence Modifiers".
- Butsicles, 3.26 PSA (about 70 tests, "take what I say with a slight grain of salt"): exclusive mods count as at most one mod per side even if there are several; the 50/50 first-side rule "looks to no longer be the case" when one side has only exclusive mods; "no more easy triple prefix combinations with exclusive modifiers"; the PoE 1 count tables "seem to be largely the same".
- Consequence: the filler/"counterweight" strategy of the 3.25 guide (its sections 7 and 8) and route **R26** no longer work as written. **R25, R27, R28** (plain doubling and pooled counts) are unaffected. A new, narrower use survives: statistically-typed's guide, comment by Butsicles, says a 1p/0s + 0p/1s combine can add one exclusive crafted mod on each side because the two sides "don't see each other", which can lift that step above 50%.

### 3.29: Ducats bring NNN padding back (new, Reddit 2026-08)

Found in the second pass; the first version of this note missed it. In 3.29 (Allflame) Ducats can add mods that cannot roll naturally on a rare item, and players use them as padding:

- u/Waphlez, 2026-08-12, score 142, thread "New Belt Recomb Tech Is Wild" (u/Veritas1123, 101 comments): "With ducats we can augment NNMs straight onto items with T1 mods, allowing us to fill out mods on two items to maximize the odds 6 mods are kept on recomb. The NNMs aren't kept on the resulting item, meaning only the desired mods on each item will be used."
- u/VortexMagus, same thread: "most of the previous NNN mods were removed but it looks like the pantheon craft and the belt augment craft from the ducats are still NNN mods." u/tktytkty: "You can also use reroll attribute ducats to turn any attribute into NNN."
- u/OrcOfDoom (score 43) counts it with the published table: both belts hold 3 prefixes (one side real, rest padding), "72% chance at 3 mods"; suffixes pool of 5, "basically a 50% shot", so "3/8" for a perfect 6-mod belt. u/Blubberinoo: "Given the odds of 3/8 to get the perfect 6 mods … a realistic chance … for 10div". The belt prefix Ducat exists only for belts; other gear gets suffix padding (Pantheon mods).
- u/Keljhan: "I assume the tech here is that pantheon mods work like the old exclusive mods, but still count for mod slots even though they can't transfer? … they specifically patched that out in 3.26 for most exclusive mods."
- Counter-report, read in full: "Recomb BS Heads Up" (u/Intelligent-Candy659, 2026-08-18, 29 comments) claims the Ducats are "quite the opposite of a bullet proof method" after "well over 150 divs", saying a single mod "shouldn't be possible in a pool of 5 mods". The replies attribute it to the exclusive rule, not to the Ducats: u/FantaSeahorse (score 18) "Elevated mods are exclusive mods, and so is the horror essence mod, so recomb can only keep one of them"; u/XElitePheonix "You can only recomb 1 exclusive mod on the resulting base"; u/Kosgladx "while elevated mods are exclusive, normal influence mods aren't". Reading: the poster's inputs held three exclusive mods; his failures do not contradict the padding claim. "Repeated Recomb Fails..." (u/North_Specialist4042, 2026-08-24, 21 comments) lost to one mod three times at a 10% chance ("I should have ~30% chance to hit all 3 prefixes … ~10% to brick to 1 prefix"), answered as bad luck. These are single anecdotes (N = 3 and N = unknown).
- Also from that thread's neighbours: u/zelassin, 2026-08-02 (thread "Predictable Recomb 1s+1s natural+exclusive issue", u/pappa_sval): "Predictable recomb does not change the ilvl of the items, same as poe2 … the resulting item will not have some averaged ilvl"; u/notDvoiduRlooKin4, 2026-08-24: unpredictable output level is "average of both item levels plus two, capped at the higher of the two item levels" (agrees with the wiki). u/zygscarry, 2026-02-06 ("Did GGG changed the recomb again?"): "if there's multiple exclusive it counts as 1 mod in the pool now" (agrees with the 3.26 PSA).

Consequence for the model: NNN padding is an ordinary, cheap-to-model action in 3.29 (add a mod that counts in the pool and never transfers), distinct from the dead exclusive padding. It lifts the pooled count without lifting the kept mods, so a planner that only pools "real" mods under-values doubling-with-padding routes (R27 uses a Pantheon suffix). Whether the pooled count of a padded side obeys the same table is only supported by the counts quoted above (no controlled sample). Ducat prices and sources (a "Changeling Ducat", sulphur) are market inputs for the price layer.

### Selection of which mods: the unresolved rule

What the sources say, in date order:

| Date | Statement | Source |
|---|---|---|
| 2024-07, 3.25.0 | Kingsmarch upgrade "Rarer Modifiers are more likely to be retained" (the wiki says it was "likely removed" in 3.26). | W-rec history |
| 2024-08-13, 3.25.1 | "rarer Modifiers now have a much higher chance to be selected for the resulting item than before." | N-ver 3.25.1 |
| 2024-08-21, first posted version of R325 (archive snapshot; 8 days after 3.25.1) | "In the case where there are more eligible mods than the number of available mod 'slots', mod weighting is factored in. The specifics of this formula are not currently known, as much of my 'weighted' data was collected in standard." Also: "Mod weighting also does not seem to factor into the final number of modifiers"; tiers "do not seem to be a factor (thanks to testing from Forgotten Arbiter)". The author's tier test: "t9 life versus t1 life … only did 20 samples" (u/Butsicles, 2024-08-22). | R325 |
| 2024-08-21, same thread, comment | u/Butsicles: "Affix weights matter, but you want to avoid situations where they do, since those are definitely not in your favor for most valid use cases (e.g. +1 all spell skill gems, t1 flat ele, t1 % phys, etc.)". | R325 |
| 2024-08-22/23, same thread | u/Xyzzyzzyzzy asked about the league's "rarer modifiers are more likely to be retained" upgrade; u/Butsicles 2024-08-22: the "rare mods are much more likely to be retained" effect "is extremely difficult to calculate … we kind of ignore mod weighting with the way we set up recombinations"; "you would have to create very similar items and do tens to hundreds of recombs to even get a sense". u/Monetokuzuma 2024-08-23: the old line (equal chance) "was with regards to old recomb mechanics, now they still (seemingly) factor in weight for normal 1+1 recombinations". | R325 |
| 2024-08, sheet tab "Standard recombs on gloves" | In-league data by "PYCKS (reddit)": "when testing recombing chaos res (250 weight) vs other res's (1000) weight. chaos res was retained at a rate of 29% and the others at a rate of 75%." Context and N are not given in the tab. | sheet gid 49869311 |
| later edit of R325 (cached copy, edits dated 08/21 and 08/23/2024; not in the archive snapshot) | "In current league, the weights of these modifiers is also a factor, where modifiers with higher weights are more likely. This is probably to prevent players from making extremely overpowered items too easily." | R325 cached |
| 2025-06-17, 3.26 PSA | u/Butsicles: "I would approach recombs with some moderate caution for low weight mods until more testing is done"; PSA text: "we previously didn't have to figure out the relative 'save' chance for low weight modifiers". 2025-06-18: "I have a shaking feeling that low tier recombinations were changed but it might just be bad luck. For reference my friend failed 17 33% combines in a row with merciless + flaring … Higher weight combines seem to follow the trend I described." | R326 |
| 2025-06-20/2025-07-04, 3.26 analysis thread | u/Butsicles: for the exclusive trick "odds greater than 50%, but this is variable depending on mod weighting … For low weights it will be below this number"; worked example uses weights as proportional: "fire spell has 250, dot multi has 300. We assume all crafted mods have 1000 … If we assume the weights are not modified in any way … 33% + 66% * ~1/4.5". u/Itchy_Egg5520 (2025-07-04): 21 combines of +1 fire (250) with t2 fire dot multi (70): "lost fire dot multi 12 times, but lost +1 fire only 2 times" (small N, uncontrolled). u/statistically-typed (2025-06-20): "I wouldn't recommend doing recombs with low weight affixes". | R326 |
| now | "Higher weight modifiers are more likely to be selected, although the exact formula is unknown." | W-rec |
| 2024-08-13, 3.25.1 (official) | "rarer Modifiers now have a much higher chance to be selected for the resulting item than before." | N-ver 3.25.1 |

Reading, after the first-hand check: the author's working model, in every thread from 2024-08 to 2025-07, is that a mod's chance to be kept rises with its spawn weight (he computes with weights as proportional shares, and warns that rare/T1 targets "are definitely not in your favor"). The only measured contrast (chaos resistance 250 vs 1000: 29% against 75%) and the small 3.26 samples point the same way. Nobody states a formula, nobody has a controlled sample (the author: "hundreds more data points" needed), and the 3.25.1 note says only "than before". What the author never says is that rare mods are kept more often than common ones; nobody reports it. Weighted data in the first post came "mostly from standard", i.e. a different rule set than the league one, so the weight statements are weaker than the count table (N 217-424 per row).

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

**What the first-hand check changed (2026-10-31).** The conflict with ADR-0012 stands, but the evidence is weaker than I first wrote: it is a consistent qualitative direction (author's own model, one 29%/75% contrast, small 3.26 samples), not a fitted formula, and the sentence I quoted as "written after 3.25.1" came from a later edit of the guide, not its first version. The one contrast gives a crude exponent: retention ratio 29/75 = 0.39 for a weight ratio 0.25 suggests α near 0.7 if retention scaled like weight^α in comparable pools, but the pool sizes behind it are unknown, so I do not recommend using it as a point estimate. The family α in [0, 1] is therefore still the honest bound.

**How the family could be pinned down.** The author's raw sheet is public and readable; its weight-bearing tabs ("Standard recombs on gloves", wands, "Discord data on wands", "Practical use case combines") hold mod names and tiers per combine, with weights to be joined from `mods.json`. A fit of α from those rows is a small separate ticket (about 300 rows, mostly 3.25 and Standard); I did not do it here. A new measurement costs Dust and Gold at the rates in section 6, so it is not worth asking the owner for it.

## 6. Dust and Gold

- Wiki: the Recombinator "costs Gold and Thaumaturgic Dust"; the amount depends on item level and mods. 3.27.0 added a Dust counter to the window.
- PoEDB (datamined): `RecombinatorModDustCostMultiplier = 3`, `RecombinatorModDustCostExponentTimes100 = 75`. They suggest a per-mod cost of the form `3 × x^0.75` summed over mods, but the quantity `x` and the Gold formula are not in any source I found. Treat as a hint only.
- Dated player data points (Reddit, 3.26; N = single reports): u/pda898 2025-06-17, "the dust cost for high tier mods is insanely high this patch"; u/gandalfintraining 2025-06-17, from a Monte Carlo of about 300 recombinations to build a perfect item, "that'd be 30 million dust per item" (about 100 000 per combine); u/Godofdeathryuk 2025-06-17, 250 000 Dust for one armour because of an extra T1 suffix, "1-2 million dust on avg plus like 300 k gold"; u/g00fy_goober 2025-06-20, "wanted like 260k dust. crafted worst int roll on both and dropped to like 30k"; u/infectorAlex 2025-06-20, "step 1 used to cost 1500 dust, it now costs 40k dust even with 2 low tier mods crafted on"; u/ExiledYak 2025-07-15, "240k per try" for two 1p/1s rares; u/No-Razzmatazz7854 2025-06-18, a trash low-tier craft "can save you 50% on dust cost". The author's sheet, tab "Interesting Examples": "Influence increases recomb costs by 50%" (3.25 data). The cost therefore rises steeply with mod tier and falls when cheap low-tier mods sit on the item; the recorded cases fit a sum over mods of a steeply rising function of tier, as the datamined exponent suggests, but nobody published numbers per mod.
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
| R27 (3.29 chest) | count table, a "Pantheon" suffix from a Ducat | Counts consistent with the table. The Pantheon/Ducat mods are NNN padding (counted in the pool, never kept), per the August 2026 thread in the 3.29 section; not on the 3.25 exclusive list. |
| R28 (+2 amulet) | doubling, count table | Valid. |
| R29 (VLS dagger, 3.25) | influenced essence prefixes, doubling | Influenced mods need a base with that influence (both inputs are Shaper/Elder here). Valid for recombination; essence mods are exclusive so only one survives. |

## 9. Open points

1. Awakener group conflict (A6) and whether the kept mods count in the 4/5/6 total (A7).
2. The real selection rule: α is not measured. A fit to the author's raw sheet (public, read in the browser) would narrow it; not done. Until then every recombinator result is an interval (ADR-0012).
3. Which weight is used when the pool holds several tiers of one mod group, and how Craft of Exile's `weight` field maps onto the draw.
4. Exclusivity of the crafted mods "Upgraded", "of the Craft", Pantheon/boat suffixes; the guide's list is "non-exhaustive".
5. PoE 1 predictable mode: the formula, constants, the maximum number of selected mods, whether it works on every class, whether NNN and exclusive mods count as claimed.
6. The Dust and Gold formula (section 6); the unit prices.
7. Jewels: whether the bench accepts them (my reading: no).
8. Whether a recombinator output's catalyst quality is the chosen base's (W-rec says quality is copied, 50/50) matters for the catalyst-quality target of B2.
9. Any Reddit material from 3.27-3.29 (tool failed).
10. The prototype's `recombinators.md` and `awakener_orb.md` still hold Q9, Q12, Q16, Q20, Q21, Q22 as open; this note answers Q21 (use the guide table, wiki as second case) and narrows Q20 and Q22 to an interval; it does not close Q9.

### Reddit second pass: search log (2026-10-31)

Tools: `reddit_archive.py thread <id>` (read first-hand), `reddit_archive.py posts "<q>" --title`, and the GPT researcher (`gpt_research.py`, job `20261031-151159-0154`, terra, stopped). The archive was rate-limited machine-wide from about 15:25, which stopped the sweeps below; the main chat asked for no new sweeps, so those points stay "not found".

**Read in full, first-hand (id, author, date, comments):** `1exyavx` Butsicles 2024-08-21 (725 comment nodes); `1ldc3lz` Butsicles 2025-06-17 (127); `1lfyxxd` statistically-typed 2025-06-20 (190); `1vm0rxj` Veritas1123 2026-08-12 (101); `1vs26e1` Intelligent-Candy659 2026-08-18 (29); `1vwsw6q` North_Specialist4042 2026-08-24 (21); `1vd294s` pappa_sval 2026-08-01 (5); `1qx8y2z` BreadfruitWeak695 2026-02-06 (7); `1qxyhlk` PineTreeGod 2026-02-07 (3). Also the author's public sheet (14 tabs; 7 read). **Listed by title only, not read:** `1vuifg8` ("Hit an insane 1.5% chance recomb", NehcB, 2026-08-21: "11% chance for 4p to pick 1, 28% chance for 6s to pick 2, 50% … for the combined total of 1.5%", which agrees with the count table), `1vq0kvd`, `1vojjpu`, `1vm1hef`, `1vamkav`, `1syu4vc` (NNN ladder recomb tech question, 2026-04-29), `1rl2re8` ([PSA] Don't recomb legacy explode, 2026-03-05, score 324). Two threads ("recomb rules changed in 3.29?" `1vygl2m`, "Recomb item level affix transfer" `1w0kdir`) have a removed body.

| Open point | Status | Evidence / search |
|---|---|---|
| Selection rule (weights) | **Found, qualitative only** | Quotes, authors, dates and N in section 3; no fitted formula anywhere in `1exyavx`, `1ldc3lz`, `1lfyxxd`. A fit from the author's sheet is not done. |
| Count table | **Found, with N** | Sheet "Aggregated Mod data" (N 217-424 per row); 3.26 confirmation (30-50 samples) and 2026-08 anecdote (`1vuifg8`). |
| Exclusive rules, 3.26 and later | **Found** | 3.26 PSA; 2026-02-06 `1qx8y2z`; 2026-08-18 `1vs26e1`. |
| NNN padding in 3.29 | **Found** | `1vm0rxj` (2026-08-12). |
| Dust cost | **Found, anecdotes only** | `1ldc3lz`, `1lfyxxd`; no formula posted. Nothing for 3.27-3.29 read. |
| Predictable mode in PoE 1 | **Partly found** | `1vd294s` (2026-08-01): keeps the base item level; "1s+1s doesn't work" for a T1 mod on a lower-level result. No formula, no maximum number of selected mods, no displayed-percentage sample. Not found: searches `comments "predictable"` and the researcher's item 3 did not return. |
| Awakener group-conflict survivor | **Not found** | Only the 2020-2023 threads in `sources/raw/research/conflict-recomb-awakener-search.txt` (player reports, the 2020-03-27 case where the donor's mod survived). Searches `comments "awakener"` (2026-07..10) and the researcher's item 5 did not return (rate limit, then a 503 from the model service). |
| Kept mods inside the 4/5/6 total | **Not found** | Same searches. |
| Imprint consumed on restore / several per item | **Not found** | Same; the researcher's imprint sub-task answered (17 145 chars) but its final report failed with two 503s, so I could not read it. |
| Jewels in the recombinator | **Not found** | Same; the researcher's jewel sub-task answered (10 107 chars), unread for the same reason. Thread `1qyqv74` ("Best method for 3 mod idol recomb?") shows idols, not jewels, are the other accepted class. |
| 3.27-3.29 changes to counts/weights | **Not found** | Wiki version pages show none; 2026 threads above show no new table; `posts "recomb" --title --after 2025-07-20 --limit 40` returned 40 titles (read the ones listed). `posts "recombinator" --title --after 2024-08-01` and the `comments` sweeps never completed. |

## 10. Questions for the owner, each with my recommendation

1. **How should the system price Thaumaturgic Dust and Gold?** Neither is on the trade site or the currency exchange as far as I found; Dust comes only from disenchanting (which you dropped) or Possessed-monster gear. Options: (a) two numbers you set in the price file, with defaults taken from the cheapest-unique rate (about 150 000 Dust per Chaos) and a Gold value you pick; (b) ignore both; (c) treat Dust as the Chaos value of the cheapest item you would disenchant. **Recommended: (a)**, flagged as approximate in every report, because Gold may dominate the cost of a combine and only you know what an hour of Kingsmarch gold is worth to you.
2. **Do jewels go into the recombinator?** My reading of the wiki and the game data is no. **Recommended: treat jewels as ineligible** and drop jewel recombinator routes; if you ever saw a jewel accepted, tell us.
3. **Do you want predictable recombination in B3?** Its PoE 1 formula is unpublished, and no benchmark route uses it. **Recommended: ship B3 with the unpredictable mode only**, add the predictable one later as a flagged, unvalidated action if a route you care about needs it.
4. **Imprint behaviour that only the game shows:** is an imprint used up when it restores, and can one item carry more than one imprint (for example one from before and one after a regal)? **Recommended: assume one imprint is used up by one restore and an item carries one**, unless you can check in the game in two minutes.
5. **The rarity direction of the interval.** ADR-0012 was written on the belief that rare mods are kept as often as or more often than common ones; the evidence read first-hand (direction well supported, size not) says the reverse. **Recommended: amend ADR-0012 to the family of section 5** (weights to the power α, α from 0 to 1) and accept that intervals for routes with rare target mods will be very wide (a factor of ten or more). You decide whether such an interval is still useful or whether recombinators wait until someone measures α.
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

  - id: recombinator.ducat_nnn_padding
    statement: In 3.29 Ducat crafts add mods that cannot roll naturally (a belt prefix, Pantheon suffixes, an attribute reroll that makes a mod non-native) to a rare item; they count in the pooled count of their side but never reach the output, so they pad the pool without taking a kept slot. Player report, no controlled sample.
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1vm0rxj/_/p35v203/
    quote: "The NNMs aren't kept on the resulting item"
    patch_verified: "3.29"
    date_checked: 2026-10-31

  - id: recombinator.predictable_keeps_item_level
    statement: Predictable recombination does not average item levels; the output keeps the level of its base (so a mod needing a higher level than that base cannot appear).
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1vd294s/_/p16v61q/
    quote: "Predictable recomb does not change the ilvl of the items"
    patch_verified: "3.29"
    date_checked: 2026-10-31

  - id: recombinator.exclusive_counts_once_report_3_27
    statement: In February 2026 (3.27) several exclusive mods on one input still count as one mod in the pool.
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1qx8y2z/_/o3uqisv/
    quote: "if there's multiple exclusive it counts as 1 mod in the pool now"
    patch_verified: "3.27"
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
    statement: A later edit of the guide (after 3.25.1; not in the first posted version) says higher-weight mods are more likely and tiers are irrelevant at equal weight; the exact formula is not fleshed out.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/
    quote: "modifiers with higher weights are more likely"
    patch_verified: "3.25.1"
    date_checked: 2026-09-21

  - id: recombinator.rare_targets_disadvantaged
    statement: The guide's author says mod weights matter when more eligible mods than slots exist, and that this is not in the crafter's favour for rare or top-tier targets (+1 all spell skill gems, T1 flat elemental, T1 % physical). Direction only; no formula.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1exyavx/_/ljaltc5/
    quote: "Affix weights matter, but you want to avoid situations where they do"
    patch_verified: "3.25.1"
    date_checked: 2026-10-31

  - id: recombinator.weight_retention_contrast
    statement: One measured contrast from the author's data sheet (in-league data credited to PYCKS, sample size not stated): chaos resistance (weight 250) kept 29% of the time, other resistances (weight 1000) 75%. Crude exponent about 0.7 if retention scaled like weight^alpha, unverified.
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit#gid=49869311
    quote: "chaos res was retained at a rate of 29% and the others at a rate of 75%"
    patch_verified: "3.25.1"
    date_checked: 2026-10-31
    value: {low_weight: 250, high_weight: 1000, low_kept: 0.29, high_kept: 0.75}

  - id: recombinator.weights_as_proportional_shares
    statement: In 3.26 the guide's author computes recombination odds with spawn weights as proportional shares ("if we assume the weights are not modified in any way") and says the odds for low-weight mods fall below the equal-chance figure.
    source_kind: owner
    url: https://www.reddit.com/r/pathofexile/comments/1lfyxxd/_/n1bu3an/
    quote: "For low weights it will be below this number."
    patch_verified: "3.26"
    date_checked: 2026-10-31

  - id: recombinator.count_table_sample_sizes
    statement: Events behind the 3.25 count table (author's sheet "Aggregated Mod data", 2024-08-21), per pooled count, as [zero, one, two, three] final mods; use them for the sampling error of recombinator.count_table.
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit#gid=1624896422
    quote: "Aggregated Mod data"
    patch_verified: "3.25.1"
    date_checked: 2026-10-31
    value: {1: [89, 128, 0, 0], 2: [0, 196, 84, 0], 3: [0, 124, 171, 26], 4: [0, 47, 241, 136], 5: [0, 0, 151, 194], 6: [0, 0, 82, 219]}

  - id: recombinator.influence_raises_dust_cost
    statement: In the 3.25 data an influenced input raised the recombination cost by 50%.
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit#gid=1424748440
    quote: "Influence increases recomb costs by 50%"
    patch_verified: "3.25"
    date_checked: 2026-10-31
    value: 1.5

  - id: recombinator.reported_dust_costs
    statement: Reported Dust costs per combine in 3.26 (single reports, Reddit): 40 000 for a first step that cost 1 500 before (two low-tier mods crafted on), 240 000 for two 1p/1s rares, 250 000 for an armour with an extra T1 suffix, about 30 000 after crafting a worst-roll mod on both inputs of a pair that had cost 260 000, about 100 000 per combine in a 300-combine plan.
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/326_recomb_psas_a_few_useful_tipsconfirmations/
    quote: "it now costs 40k dust even with 2 low tier mods crafted on"
    patch_verified: "3.26"
    date_checked: 2026-10-31

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
