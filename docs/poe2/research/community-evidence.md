# PoE2 crafting: community experiments and player findings (Reddit)

- **Checked:** 2026-11-24/25 (UTC). All reads made in this window.
- **Patch the reader is on:** Path of Exile 2 0.5.x, game data 0.5.5.10. Leagues "Runes of Aldur" (0.5.0, launched 2026-05-29) and "Forbidden Rites" (0.5.5, early September 2026). GGG (Natalia_GGG, 2026-08-28): "Forbidden Rites will run until the 1.0 release and will end alongside Runes of Aldur." A tester post (1x3w97t, 2026-10-12) names 1.0 for **11 December 2026**; every number below may move then.
- **Method:** reddit.com refuses this server, so every post and comment was read through the Arctic Shift archive API (`https://arctic-shift.photon-reddit.com/api/`: `posts/search` by title, by `query` full text in a date window, by `author`; `posts/ids`; `comments/tree`; `comments/search`), with requests spaced at least 3 s apart and a 60 s wait on HTTP 429. The archive often answered full-text searches with HTTP 422 (query too heavy; also any query containing an apostrophe); those were retried with a narrower date window or other words, and the ones that never answered are listed in "Not found". Images (charts, screenshots) are not in the archive text, so a number that lives only in a picture is marked as such. Posts whose body was removed by moderators show only their title.
- **Subreddits read:** r/PathOfExile2 (main source), r/Poe2BudgetCraftGuide, r/pathofexile2crafting, r/pathofexile2builds. r/PoE2Crafting and r/poe2crafting have no posts in the archive.
- **Dates:** every date is the post's or comment's `created_utc` (UTC date).
- **Trust scale used:** **high** = large sample, method stated, raw data published, no contradicting replies; **medium** = real sample but small, or method partly stated, or one confirming/contradicting voice; **low** = anecdote, theory, or a claim with no data.

Thread URLs follow `https://www.reddit.com/r/<sub>/comments/<id>/`.

---

## 1. Explicit modifier weights (chaos, exalt) and how community tools get them

### 1.1 "I spent 250 divs chaosing boots - 1800 rolls" — poe2db weights checked by experiment
- URL: https://www.reddit.com/r/PathOfExile2/comments/1vsm9ip/ — 2026-08-19 — u/Civil-Bee-f (author of craftgaz.com)
- Patch: 0.5 (Runes of Aldur). Sample: **1,811 mod rolls** of Chaos Orbs on **ilvl 82 Int boots**. Raw CSV published: `craftgaz.com/files/` (`boots_chaos_rolling_09_08_26.csv`).
- Result: for every mod family but one, the poe2db-predicted share fell inside the experiment's 95% interval. Outlier: "`+X to maximum Mana` family is somewhere around 9,500–12,500. poe2db predicts a weight of 9,000". Author: "For int boots, poe2db weights look reliable enough to use. I expect the same for other bases."
- Replies: u/SirPharazon: with 17 families, about 58% chance that at least one falls outside its 95% interval by chance, so "the data is Overall very consistent with the expectations". u/beta_1457: poe2db weights "are not" datamined, "The weights come from testing using the recombiniator"; new mods are "weighed as 1 because we don't know".
- **Trust: high** (large sample, raw data, correct statistics, replies agree). Covers one base class.

### 1.2 Where poe2db / Craft of Exile weights come from (community consensus)
- 1ua9sgo "Can GGG officially release all modifier weights?" — 2026-06-19 — u/Earthboundplayer: "The modifier weights you can find on poe2db.tw are only known because some players did a ton of work using recombinator odds". Gaps named: "desecrated modifiers", "jewel modifiers", "modifiers allowed by socketables (e.g. marksman modifiers on gloves from Kolr's Hunt)", genesis-tree-only modifiers, some unique modifiers.
- 1uva5fc comment, u/HappyHopping, 2026-07-14: "The 1 weighting for desecrated mods is a placeholder value that we know is inaccurate. The mod pool weighting was generated from the chance of success from the recombinator ... Now that the recombinator is not in the game we will have no knowledge on mod weights on anything new."
- 1uw7oiu comment, u/hkidnc, 2026-07-14: weights "acquired via trial/error testing using Recombinators", link `poe2db.tw/us/weightings`; any change to the pool now makes them unreliable.
- 1v98y5j comments, 2026-07-28/29: u/ultrakorne (theoryofcraft.com) uses poe2db and guesses socketable-only mods "based on the ilvl of the modifier against similar ilvl"; u/Shamatix: "The weights are from 0.4 ... the weights for cast speed on ring is also 'fucked'". u/Fine_Fishing7506: jewel mods "arent equally weighted" but could never be recombined.
- 1u5cklr comments, 2026-06-14: poe2db shows `#% increased cast speed` on amulets at weight 6 ("0.006%"), which replies call implausible.
- 1k11fxf, 2025-04-17 (patch 0.2): u/butsicles' recombinator guide first showed "recombinator chances are directly tied to modifier roll weights"; e.g. merciless-tier prefixes on spears near "0.05%".
- 1pwgx1c (r/Poe2BudgetCraftGuide), 2025-12-26, u/Exoskeleton78: in 0.4 the recombinator's "weight multiplier" was "secretly buffed by 3 points" against the community sheet.
- Tools that publish odds all name the same sources: poe2craft.xyz "Mod weights come from poe2db and Craft of Exile" (1y0a0nx, 2026-11-19); optimalexile "community-estimated modifier weights and the fallback weights used where no data is available" (1v34srj, 2026-07-22); theoryofcraft (1v98y5j).
- **Trust: high** for the provenance (many independent voices, poe2db's own page says so). Consequence: weights of mods added in 0.5 or later (Kolr's Hunt / hunter mods, rune-bound mods, Verisium-era mods, new weapon bases) and all desecrated-only mods are **not known**; tools fill them with 1 or guesses.

### 1.3 Player estimates for mods with no known weight
- 1v98y5j comment, u/negjo, 2026-07-28: from crafting many gloves, "+2 proj and +4 markman are the same as +2 melee", other hunter T1 suffixes "somewhere around 500-1000 weight"; T1 projectile speed/damage "somewhere around 500-1000". **Trust: low** (impression, no counts).
- 1ulc1w2 comment, u/Erisymum, 2026-07-02, average Chaos Orbs per hit: "~3000c t1 %phys; ~2000c T1 spirit sceptre, t1 spell damage staff, +6 spell staff; ~1000c T1 spirit body armour, specific +3 level amulet, t1 phys hybrid/flat, +4 minion sceptre, +7 staff; ~600c +2 melee gloves, specific T1 element gloves/rings, +2 minion helm, spirit amulet, +2 focus; ~100-200c every other t1". **Trust: low–medium** (rules of thumb, consistent with poe2db ratios).
- 1y2ygzo comment, 2026-11-23: "3900 chaos orb (on average) for t1 phys %" on weapons. 1xtpbqn comment, 2026-11-11: Runefather's "+ to all spells" "something like 1/20k chaos orbs ... a guy that spent over 170k chaos". 1xlrnqi (u/SamiSch, 2026-11-02): "Chaosing on 6 mods for around 178k times to hit +1"; same post: "we dont have any weights online so far, i guessed and guessed wrong". **Trust: low** (single crafts).
- 1wsbu13, u/c-lati, 2026-09-28 (ring crafter, "over a mirror" of sales): on rings "T1 flat phys ... has twice the weight as the elemental" flat damage; "do not use cold [quality] as it can roll 1 lower tier when using perfect exalts". **Trust: medium** (experienced crafter, matches poe2db).

### 1.4 Omen-targeting edge case: "lowest level" means modifier level, not tier
- 1vicm56, 2026-08-07: Omen of Whittling + Sinistral Erasure targeted T1 life, not T2 evasion. Replies (several, agreeing): "Tiers are not levels", "It is the lowest level requirement of modifier not it's tier", "T1 max life is requires a lower level to find than T2 flat evasion". **Trust: high** (mechanic matches game text; many agreeing replies).
- 1ty4enx (title only, 2026-06-06): Chaos Orb with Whittling hit a crafted mod.

---

## 2. Desecration (Abyss bones) and the Well of Souls reveal

### 2.1 "I desecrated more than 500 rings. Here is what I found - Part 1"
- URL: https://www.reddit.com/r/PathOfExile2/comments/1uslcts/ — 2026-07-10 — u/Civil-Bee-f — score 340, 102 comments. Cross-posted r/Poe2BudgetCraftGuide 1usmqeb.
- Patch 0.5. Method (comment): rings ilvl ≥ 65, Preserved Collarbone; prefix group = 3 suffixes filled + 1–2 prefixes, suffix group the mirror image; 573 rings, **563 valid reveal windows = 1,689 options**.
- Numbers: "roughly **37%** of the shown options were desecrated modifiers ... roughly **63%** were natural"; "**no cases with 0 desecrated modifiers**".
  - Prefix reveals (236): 1 desecrated 198 (83.9%), 2: 37 (15.7%), 3: 1 (0.4%), 0: 0.
  - Suffix reveals (327): 1: 282 (86.2%), 2: 41 (12.5%), 3: 4 (1.2%), 0: 0.
- Author: position of the desecrated option in the window looks random ("lines are likely random", 2026-07-13). Replies: Omen of Abyssal Echoes can show "the exact same mod twice in a row", same mod and tier again (u/W00psiee, u/rude_ooga_booga). u/krakenbul: the at-least-one rule "has been known since the first days of 0.3" (imgur link).
- **Trust: high** (563 windows, method stated, agreeing replies). Rings only.

### 2.2 "... Part 2" — desecrated-mod frequencies and blocking
- URL: https://www.reddit.com/r/PathOfExile2/comments/1uva5fc/ — 2026-07-13 — u/Civil-Bee-f. (The asked-for 1uufj2z and 1uufape are the same Part 2 reposted then removed; only the methodology comment survives there.)
- Numbers in the text: 15 desecrated ring suffixes; uniform would be ~6.7% each, observed "from about **11.8% for Strength + Dexterity** down to about **1.2% for Cooldown Recovery Rate**". Per-mod charts for prefixes and suffixes are **images only** (not in the archive).
- Blocking: "an existing Strength modifier ... appears to remove the shared attribute group from the Desecrate pool, including Dexterity and Intelligence variants"; elemental and mixed resistances do **not** block each other. Author: sample "not enough to recover the true weights, but it's enough to say with confidence that some mods are statistically more likely".
- Replies: u/convolutionsimp: non-uniform desecrated weights "well known ... ever since abyss came out", low ones "Cooldown recovery, spirit reservation efficiency". u/Exoskeleton78: the blocking group is visible on poe2db's mod page. u/coffealake: rune-bound mods are also unequal (boots "15% chance to not consume charges" rare).
- **Trust: medium-high** for "non-uniform" and the attribute block; **medium** for the exact shares (≈1,000 suffix options, wide intervals).

### 2.3 Part 3: "Calculating the chance to hit T1 Added Fire Damage with Desecrate"
- URL: https://www.reddit.com/r/PathOfExile2/comments/1uw7oiu/ — 2026-07-14 — u/Civil-Bee-f.
- Model: P(success) = P1·(1−(1−a)^2) + P2·a, with P1 = 198/236, P2 = 37/236 from Part 1, a = 200/69,500 (T1 fire weight / total ring prefix weight from poe2db). Result **0.527% per reveal (~190 tries)**, **1.05% with Omen of Abyssal Echoes (~95)**; ignoring the desecrated slots would give 0.861% (~116), "underestimates the expected number of attempts by about 63%". 95% CI from the slot data alone: 185–195 tries.
- Notes: a dearer bone raises the minimum modifier level, removing low-level mods from the natural pool.
- **Trust: medium-high** (sound arithmetic on 2.1's data; treats each natural option as an independent draw by poe2db weight, which nobody has tested directly).

### 2.4 Earlier hypotheses on the reveal (superseded by 2.1)
- 1o10ean (r/Poe2BudgetCraftGuide), 2025-10-08 (0.3), u/Exoskeleton78, 100 focus + 30 ES body armour desecrations: "it has a 50% chance to pick from either set ... if it picked the desecrated only set ... every modifier there has a 1 in x chance". Minion-skill on focus seen 4/100 vs model 1/22. **Trust: low** (small sample; equal desecrated weights refuted by 2.2).
- 1uk0zhp, 2026-06-30, comments: u/PUR3SK1LL "50% chance to appear ... per slot" (hypothesis); u/Exoskeleton78: per row, "number of desecrated only mods / total number of rollable mods", otherwise normal weights. Part 1's 37% with a guaranteed minimum of one fits neither model exactly; the author did not publish a fitted model.
- 1u7jtrn comments, 2026-06-16: u/mukhaliniov recalls "always 2 regular modifiers and one abyss unless abyss omens are used" and "it never gives two of the same mod but in different tiers" (within one window); u/vprogram: Ancient Jawbone = min mod level 40, cutting the natural pool (worked example 375/13,975 = 2.5% for %phys T4+). u/ravenousglory (1uk0zhp, 2026-07-02): Mark of the Abyssal Lord + Prismatic Alloy reset took "roughly 300 tries with omen of echoes to hit t1 attack speed" on a spear. **Trust: low.**

### 2.5 Craft of Exile has no desecration odds
- 1urz8ca, 2026-07-09: user asks how to get desecration odds in CoE; workaround guessed (Preserved Rib ≈ Greater Chaos, divide by 6 with Echoes). 1qdtekn, 2026-01-15: CoE lacked Omen of Catalysing Exaltation. **Trust: medium** (tool gap, several reports).

---

## 3. Catalysts (Breach Genesis Tree, Wombgifts, reforging)

### 3.1 "Data from 1,000 Lavish Wombgifts (Catalyst Weights)"
- URL: https://www.reddit.com/r/PathOfExile2/comments/1uczobt/ — 2026-06-22 — u/life_without_pants — score 199, 66 comments. Spreadsheet and video linked.
- Patch 0.5. Sample: **1,000 Lavish Wombgifts (ilvl 79–80)**, "Only drop catalysts" node, +240% additional items → **3,411 catalysts** (3.4 per gift, matches the expected value).
- Shares: Adaptive 330 (9.7%), Carapace 410 (12.0%), Chayula's 160 (4.7%), Esh's 253 (7.4%), Flesh 417 (12.2%), Necrotic 189 (5.5%), Neural 425 (12.5%), Reaver 168 (4.9%), Sibilant 203 (6.0%), Skittering 102 (3.0%), Tul's 235 (6.9%), Uul-Netol's 238 (7.0%), Xoph's 281 (8.2%).
- Replies: refined-catalyst chance is a tree node (10% notable + 4% small = 14%); the three ~12% catalysts sit on one exclusion node. Exoskeleton78 later compared ilvl 80 vs 65 wombgifts (1vc5l7k, r/Poe2BudgetCraftGuide, 2026-07-31; image only).
- **Trust: high** (3,411 draws, method stated, spreadsheet). Speaks for drop weights, not for crafting.

### 3.2 Reforging bench on catalysts (3 → 1)
- 1uihd0p "Why you should be reforging your catalysts", https://www.reddit.com/r/PathOfExile2/comments/1uihd0p/ — 2026-06-29 — u/ferdinono. Sample: **5,760 catalysts → 1,920 reforges**.
- Output: sibilant 86 (4.48%), reaver 97 (5.05%), skittering 51 (2.66%), xoph 148 (7.71%), neural 240 (12.50%), esh 139 (7.24%), tul 155 (8.07%), necrotic 95 (4.95%), chayula 81 (4.22%), carapace 275 (14.32%), uul-netol 136 (7.08%), flesh 229 (11.93%), adaptive 188 (9.79%).
- Input mix not controlled (mostly cheap "junk" kinds), yet the output matches the wombgift shares of 3.1 within a point or two, which suggests the bench draws from the same catalyst weights regardless of input. **Trust: high** for the output shares; **medium** for "independent of input" (inference, not tested).

### 3.3 Catalyst quality and weights
- 1u89hwn, 2026-06-17: does catalyst quality change chaos/exalt weights without the omen? Replies: no; the PoE1 behaviour "was even removed from poe1 about 5 years ago". Anecdote: chaos for tagless spirit 40 div, then swapping to phys catalysts hit "in about 5 div". **Trust: low** (no data).
- Omen of Catalysing Exaltation: u/ultrakorne (1v98y5j, 2026-07-28) quotes "5x weights at 20% quality, 7.4x at 40%" and asks for the curve; u/Skaugy (1u5cklr) guessed "10x". Nobody posted data. **Trust: low.**
- 1nhk2l2 (title, 2025-09-15, 0.3): desecrated mods are not raised by catalyst quality.

---

## 4. Essences

- 1qgsg0i "Feeding thousands of Perfect Essences into the reforge bench", https://www.reddit.com/r/PathOfExile2/comments/1qgsg0i/ — 2026-01-19 (0.4) — u/ferdinono. ~5,000 perfect essences (~80 div) reforged until only kept kinds remained; kept: 72 Alacrity, 86 Battle, 68 Haste, 122 Sorcery, 192 Mind, 97 Abrasion; ended with ~154 div. Output counts are of the kept kinds only; the full spread is not given. **Trust: medium** (large sample, but only partial counts, and 0.4).
- No 0.5 post measured what an essence adds (tier spread) on items. 1xlrnqi: "Hit Zarokhs after 666 essences" (one craft, Delirium essence). 1k11fxf (0.2): Essence of Torment only adds physical-tagged mods; with poe2db weights the top tiers were ~1.2% per slam.
- 1u2r6ic (title, 2026-06-11): a perfect flux upgraded an amulet's CoC skill without adding a socket. 1v3xvge / 1uee5h2 (titles): questions whether a perfect essence replaces an existing essence mod; no answer with data.

---

## 5. Vaal Orb, corruption, sanctification

### 5.1 Unique items: 0.5 changed the corruption roll
- 1u9mh81 "Did corrupting change? From 99% to 54% ...", 2026-06-18, comments: "Vaal orbs don't divine anymore, they only apply the corruption stat multiplier" (u/velthari); "Prior to this league Vaals would also divine an item before adjusting their values within the 0.78-1.22 range. This league they specifically changed it to no longer do this" (u/Savingseanbean). OP's 99→54 is outside 0.78× and was called "gotta be a bug". u/HappyHopping (1u8g9od): "Now it only rolls values based upon the current stat rather than any within the range." u/_plusone (1u8g9od): outcomes seen "adds implicit, rerolls values in [0.8, 1.2], does nothing". **Trust: medium** (several agreeing players; matches 0.5 notes as players report them; the 0.78 vs 0.8 bound is disputed, see 5.3).

### 5.2 Socket and outcome odds players use
- 1u8g9od "Just did the math... Now that omen of corruption is gone", 2026-06-17, u/StrikingCupcake899: on bows/spears "soc with omen: 1/3", "soc without omen: 1/4"; sanctify +4→+5 chance (4·1.2−4.5)/((1.2−0.8)·4) = 0.1875 assuming a uniform 0.8–1.2 multiplier. **Trust: low** (stated odds, no counts). In 0.5.5 the omen's effect came back as a glove soul core/rune ("They made omen of corruption into an Soul Core", 1w0a0tw, 2026-08-27; wording "guaranteed change" when corrupting; whether it applies only to the item it sits in is disputed in replies).
- 1uq66db "+12 Wand", 2026-07-07, u/CompetitiveLeading79: Vaal for a 3rd wand socket "only had 5 wands get a 3rd socket out of i don't know how many"; "7% chance for the correct one if it doesnt poof" (Architect's Orb, element-specific +1); "around 225 attempts starting at the corruption stage". **Trust: low.**
- 1vcqpxz, 2026-08-01: amulet gem-level sanctify +5→+6 "pretty sure its still ~1/8"; "8 locks to miss". **Trust: low.**
- 1uhadux "1 in 192 corrupt (0,52%)" (title + image only, 2026-06-27).
- 1whjd8u, 2026-09-16: a Vaal Orb that added a socket also removed 20% quality (bug or rule unclear). **Trust: low.**

### 5.3 Waystones
- 1wy4cnz "Results of 232 t15 way stone corruption after fully exalting (0.5.5)", 2026-10-05, u/blablabla2384: **232 corruptions: 29 downgrades (12.5%), 23 upgrades to T16 (9.9%)**; rest in an image. **Trust: medium** (232 trials, one person, partial table).

### 5.4 Sanctification range
- Disputed: 0.78–1.22 (1u9mh81 comments) vs 0.8–1.2 (1u8g9od, and u/ultrakorne asking which, 1v98y5j). u/negjo (1v98y5j): "corruption on uniques multiples by ..." (cut off). u/CaptainAgnarr (1vcqpxz): "sanctifying you have the exact probabilities". No sample posted. **Trust: low** for the bound.

---

## 6. Architect's Orb (double corruption)
- Player rule of thumb: "architect orb them for a 50% chance of poof-ing them, or getting the +1" (u/gennciiq, comment in 1y1wzhk, 2026-11-21). 1x5q7b8 (2026-10-14): sellers price in "the Architect's Orb causing the item to vanish". 1ridvqj, 2026-03-02 (0.4): "destroyed me around 8 items in row"; replies: luck.
- 1urzsgk (+13 staff, 2026-07-09): if Vaal misses the +1 implicit, "use an architects orb to try again ... the item is either gone or you can just sell it".
- **No sample of Architect's Orb outcomes was found.** **Trust: low.**

---

## 7. Orb of Chance
- 1u690fh, 2026-06-15: "about **1,700 belts**, and about **90 unique belts**" (≈5.3% unique), no Headhunter or Mageblood. 1u95q62, 2026-06-18: Mageblood "in 30 or so", then "800 more and still no Mageblood". A PoE1 comparison "1/28k" (PoE1, not PoE2). 1xpjn27 comment (2026-11-06): "the vast majority of chance orbs result in deleting the base". 1wv95b1 (2026-10-01) asks GGG to show odds; the "utility belt odds" in its images are the poster's illustration, not data.
- **Trust: low–medium** (one 1,700-belt count with no breakdown by base or by which uniques).
- Ritual omen rate for Omen of Chance: 0.07% of omens (see 9.1).

---

## 8. Fracturing Orb and Hinekora's Lock
- Fracture: no outcome sample found. 1vgjm77 "Fracture odds are mod weighted in 0.5" (2026-08-05) is labelled "Tinfoil Hat Theory" and was removed. 1tkohya (2026-05-22, 0.4): "20, yes TWENTY, locks to hit the fracture" on a 1/3 target, "1 in 3,325"; the poster assumes the fracture is uniform over mods. 1ugqkqe (2026-06-27): "fractured twice" was one hybrid mod. 1y2a8jx (u/Civil-Bee-f, 2026-11-21): in his boots simulation "the fracture landed on an ES mod in only 15–23% of finished items". 1tx8los (2026-06-05, removed): "Runeforge can apparently RESET fracture mod". 1u79ray (title): a fractured crafted mod no longer shows as crafted.
- Hinekora's Lock: GGG, 2026-06-05 (Natalia_GGG, thread 1txwgq6): "The Hinekora's Lock remnant crafting option has been temporarily disabled." Players use Lock to preview corruption, sanctification and fracture (1xlrnqi: "Lock 13 times and check exalt, greater ex, perfect ex, chaos ..."; "Getting the %spirit is 25 locks + on average"). No posted test of Lock edge cases (e.g. with omens).
- **Trust:** GGG quote high; the rest low.

---

## 9. Omens

### 9.1 "Data from 3,000 Omens" (Ritual drop weights)
- URL: https://www.reddit.com/r/PathOfExile2/comments/1wpyc72/ — 2026-09-25 (0.5.5) — u/life_without_pants. **3,000 omens** from Ritual windows, untabletted; 1.56 omens per window on average.
- Shares (% of omens): Chaotic Rarity 3.27, Chaotic Monsters 2.73, Chaotic Quantity 3.37, Chaotic Effectiveness 2.73, Bartering 12.3, Gambling 12.37, Sinistral Exaltation 5.43, Dextral Exaltation 6.47, Greater Exaltation 11.53, Catalysing Exaltation 2.2, Ancients 5.63, Chance 0.07, Sinistral Crystallisation 0.63, Dextral Crystallisation 0.9, Sanctification 0.2, Blessed 0.7, Amelioration 3.97, Refreshment 11.77, Resurgence 12.3, Whittling 0.9, Sinistral Erasure 0.2, Dextral Erasure 0.07, Sinistral Annulment 0.07, Dextral Annulment 0.2.
- Replies: u/phadej: Wilson intervals overlap for Sinistral vs Dextral Exaltation (163 vs 194), so "Their chance to appear could be the same"; the rare ones (2–27 hits) are too few to rank. u/blaza192 quotes 0.5.1 hotfix 6: Erasure/Annulment/Blessed/Sanctification omens "can now generate in Rituals in level 79 and above". u/CraftyXII: map mods and tablets were not controlled.
- **Trust: high** for common omens, **low** for the rare ones (counts 2–27). Drop data, not crafting.

### 9.2 Omen behaviour edge cases
- Whittling targets lowest modifier **level** (1.4). Abyssal Echoes can repeat the same mod and tier (2.1). Catalysing Exaltation raises weights only, "It doesnt guarantee anything" (1u5cklr). Omen of Light, Liege farming threads (1vvtjd9, 1vr1wpr "nerfed?") are about drop rates, no crafting numbers. 1vnnkvk (title, 2026-08-13): Omen of Dextral Crystallisation + Transcendent Alloy + unrevealed mod interaction (body not readable). 1u6sy84 (title): "Mystic alloy + Sinistral crystallization do not work?".

---

## 10. Divine Orb (perfect-roll math)
- 1y2a8jx "Found optimal divining", https://www.reddit.com/r/PathOfExile2/comments/1y2a8jx/ — 2026-11-21 (Forbidden Rites prices of 19 November) — u/Civil-Bee-f. Pure probability: a Divine "rerolls the numbers of every mod. Tiers stay the same"; T1 %ES 92–100 = 9 values, T1 flat ES 48–60 = 13 values → both max 1 in 117 (**116 Divines** on average after the current roll). Total-ES thresholds on Sekhema Sandals: 388 ≈ 1, 400 ≈ 4, 404 ≈ 10, 408 ≈ 28, 412 ≈ 116 Divines. Optimal stop 406–408 ES. Assumes each integer value equally likely. **Trust: high** for the counting (follows from uniform integer rolls, which matches the game's roll rule); prices are a snapshot.

---

## 11. Recombinator (Expedition) and the reforging bench
- Removed in 0.5.0: "Removed in 0.5 patch" (u/DiamondBrine, 1wtfno3, 2026-09-29), many threads from 2026-05-22 (1tkcocr, 1tkh1uu, 1tk2da9). No odds can be gathered in 0.5.
- Pre-0.5 data: 1q57u75 (2026-01-06, 0.4): 35 gloves at a shown 5.2% (with Omen of Recombination) all failed; 30 at 20.8% gave 1 hit — far below the shown odds (one person; replies not checked). 1nd9cco (2025-09-10, 0.3): base selection "seems very weighted ... same item with fracture 5 time in a row". 1qjd75w (2026-01-21): recombination-odds spreadsheet by u/bstakenborg. **Trust: low** (and no longer applies).
- Naming trap: 1x9rlpy "Recombinator is a hassle" (2026-10-19) is about putting **3 jewels** in to make one (the reforging bench); replies call it "reforge". Jewel item level "has 0 influence", per u/Santi-Emite checked on CoE.

---

## 12. Verisium, alloys, runes (Runes of Aldur) and Forbidden Rites
- Liquid Verisium: threads are about Expedition remnant rerolls, not item crafting (1ujr28j "Liquid Verisium Reroll Cheat Sheet", 2026-06-30; hotfix 0.5.4b reverted a change, 1um7323, 2026-07-03).
- Alloys: Transcendent Alloy "can no longer be applied to Foci and Wands" mid-league (1u3fpuw, 2026-06-12); Celestial Alloy "+1 level of all spells" used with Astrid's Creativity (+1 crafted modifier limit) in +12 wand/+13 staff guides (1uq66db, 1urzsgk). Kalguuran Aldur Rune cannot convert an alloy suffix (1wsvdcm, title). Runeforging a Duality Staff has 3 outcomes; asker suspects unequal weights (1w8i5zr, 2026-09-06, no data). Rune-bound mods unequal (2.2, u/coffealake).
- New Vaal currencies of 0.5 (Yaomac's / Kopec's / Kamasa's Orb of Sacrifice) upgrade a Vaal implicit and remove a random mod; guides quote "essentially a 2/6 chance" to lose a wanted mod on a 6-mod item (1urzsgk) — i.e. uniform over mods, assumed, not measured.
- Forbidden Rites (0.5.5): no crafting-odds post found; ritual omen rates in 9.1 are from this league.
- **Trust: low** for any number here.

---

## 13. GGG staff statements
- Only staff comments found in r/PathOfExile2 since 2025-12-01 are from Natalia_GGG (community team): league end date (Forbidden Rites ends with Runes of Aldur at 1.0, 2026-08-28) and "Hinekora's Lock remnant crafting option has been temporarily disabled" (2026-06-05). Accounts Bex_GGG, Kieren_GGG, Jonathan_GGG, Mark_GGG have no archived comments there in that window.
- No staff comment on modifier weights was found. Players report GGG does not publish weights (1wv95b1: "Even if GGG has explicitly said they don't want to show weighting" — the explicit statement itself was not found).

---

## Conflicts with official/datamined facts

1. **Desecrated mod weights.** poe2db (and tools using it) list desecrated-only mods at weight 1 or equal weights; Reddit data (2.2) shows them strongly unequal (11.8% vs 1.2% of ring suffix draws) and with a shared attribute block group. The weight-1 is a placeholder, not data (u/HappyHopping, section 1.2).
2. **Desecrate reveal model.** Folk models ("50% per slot", "per row = desecrated-only count / pool size") predict reveals with zero desecrated options; the 563-window sample has none, and averages 37% desecrated options (2.1). Any planner that draws the three options independently is wrong.
3. **poe2db weights for 0.5+ mods.** Weights were derived from recombinator odds, the recombinator was disabled in 0.5.0, so mods added in 0.5/0.5.5 (Kolr's Hunt hunter mods, rune-bound mods) carry placeholder weights (1) or guesses; poe2db's amulet cast-speed weight 6 is disputed. For pre-0.5 mods on Int boots, an 1,811-roll test agrees with poe2db except `+maximum Mana` (observed ~9,500–12,500 vs 9,000) (1.1).
4. **Vaal on uniques.** Players report 0.5 removed the "divine first" step and the multiplier applies to the current value (5.1); older guides (Maxroll 0.4) describe the old behaviour. Bound 0.78–1.22 vs 0.8–1.2 is disputed among players.
5. **"Recombinator" in 0.5.5.** The official notes say disabled; a 2026-10 thread uses the word for the reforging bench (3 jewels → 1). Not a conflict once read; a search on the word will mislead.
6. **Catalyst reforge vs drop weights.** No official weights exist; the two community samples (3.1, 3.2) agree, so a single catalyst weight table fits both drop and reforge.

## Not found

- **Architect's Orb outcome sample** (share of items destroyed vs each outcome): only the "50%" rule of thumb.
- **Vaal Orb outcome sample on rares/weapons in 0.5** (share of no change / enchant / socket / reroll / brick): only stated fractions (1/4 socket without omen) and a 232-waystone table. Thread 1uf4qeb "Vaal Orb Outcomes" (2026-06-25) and Vaal Cultivation Orb odds threads (1qkzbq9, 1qganxl, 1twrmxk) were removed; their bodies are not in the archive.
- **Orb of Chance unique-vs-destroy rate by base**, and Mageblood/Headhunter odds: no sample beyond 1,700 belts / ~90 uniques.
- **Fracturing Orb weighting** (uniform over mods or not): no data; the one theory post was removed.
- **Hinekora's Lock edge cases with omens**: none.
- **Essence outcome distribution in 0.5** (tier spread of an essence-added mod): none.
- **Greater / Perfect Exalted, Chaos, Regal minimum modifier levels**: no community measurement (only indirect remarks, e.g. "do not use cold [quality], it can roll 1 lower tier when using perfect exalts"). These come from data, not Reddit.
- **Omen of Catalysing Exaltation multiplier curve**: only an unsourced "5x at 20%, 7.4x at 40%".
- **Verisium / Runeforging outcome weights, Forbidden Rites crafting odds**: none.
- **GGG staff comment on weights**: none.
- Searches that never returned (archive HTTP 422 even when narrowed): titles "orb of chance odds", "essence tier", "perfect exalted orb", "chaos orb removes", "fracturing orb chance", "whittling", "runeforg", "kalguuran", "runeshape", "abyssal echoes", "omen of light", "poe2db", "reforg"; any comment search with an apostrophe ("architect's orb", "hinekora's lock").
- Images not read: per-mod desecration charts (1uva5fc gallery), wombgift ilvl comparison (1vc5l7k), waystone corruption table (1wy4cnz), boots chaos plot (1vsm9ip; the CSV link is the better source).
