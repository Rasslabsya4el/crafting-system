# Recombinator Dust and Gold cost, and the crafted-mod discount

Research ticket [#177](https://github.com/Rasslabsya4el/crafting-system/issues/177), for the B3 grill ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94), answers 2 and 4e). It continues section 6 of `2026-10-31-recombinators-awakener-imprints.md` (the note of [#90](https://github.com/Rasslabsya4el/crafting-system/issues/90), branch `research/recombinators-awakener`). Read on 2026-11-01 against patch 3.29.3.3.

## Answer in brief

1. **No formula for the Dust or Gold of a recombination exists in any source I could reach.** The two datamined constants (PoEDB: multiplier 3, exponent 0.75) are the only numbers the game files give; the public client-table schema (`dat-schema`, 3.25 to 3.29 files) holds only a table of named integers (`VillageSharedConstants`: `Id`, `Value`) and the list of eligible item classes, so the calculation is not a recoverable table. The constants do not say what `x` is.
2. **One first-hand data set exists, and nobody had used it: the screenshots in the 3.25 guide author's public sheet.** Tab "Recomb costs" and tab "Interesting Examples" hold eleven recombinator windows with both prices visible (section 2). From them: **Gold is a straight line in the total number of mods on the two inputs** (wands, 0 / 2 / 3 / 4 / 6 mods: 3,237 / 3,884 / 4,207 / 4,531 / 5,178, about +323 per mod) **and does not depend on mod tiers**; **Dust does not add up over mods** (a pair with two mods cost 438; adding two more mods made it 512, adding two more 696) and the same two-mod pair costs 217 or 438 depending on which mods it is. These are August 2024 numbers on a scale far smaller than the player reports of 2025 (tens to hundreds of times, section 3), so they give the shape, not the size.
3. **The crafted-mod discount is not a property of "crafted".** What the data supports: Dust depends on the *kind* of mod (how high and rare it is), and on the pair as a whole in a way that is lowered by adding low mods; being crafted is neither necessary nor sufficient (3.25 screenshot: six crafted "of the Order" and "Upgraded" mods cost 876 Dust; two crafted multimod "of Crafting" mods cost 51, barely above the 42 of an empty pair). The only explicit statement of a rule is a player's (u/Mangalorien, 2025-09-12, 3.26): "item level and average tier of all the mods on each item", with a testable recipe; one earlier guess says average required level (u/ZerkerChoco, 2025-03-04, "I believe"). Five 3.25 points fit "Dust grows with the *average* of a per-mod quality over both items, not the sum" about as well as anything I tried (section 4), but the fit has a free choice of transform and is **not** accepted as a formula.
4. **Gold does not follow the discount.** In 3.25 Gold depends on the mod *count* only, so a junk crafted mod adds one unit of Gold (about +8% at ten units, more on a small pair) while it lowers Dust. At the owner's default prices (150,000 Dust per Chaos, 500 Chaos per million Gold) Gold is about 85% to 95% of the cost of one combine, so the discount saves at most about 1 Chaos and costs about 1 Chaos in extra Gold plus the craft: **"craft a cheap mod first" is not worth offering at the defaults.** It becomes worth it only if Dust is priced several times dearer (section 6).
5. **Cost rule for the planner (approximate, marked as such, interval from reports):** Gold 12,000 per combine (8,000 to 20,000); Dust 100,000 per combine (25,000 to 250,000), times 0.5 (0.11 to 0.5) when each input carries a low-tier crafted mod. At the defaults that is about 7 Chaos per combine (4 to 12). Section 5 gives it as a table with the evidence per number.
6. **One in-game session settles it.** Section 7 lists ten item pairs the owner reads off the recombinator window (two bench crafts of about 1 Chaos each).

## How this was read

Evidence rule of map #1's Notes: best information available today; each claim says where it comes from and how strong it is. Strength words: **datamined** (game files), **screenshot** (a game window in the author's sheet, N = one reading), **player report** (a Reddit or forum comment, N = one unless stated), **guess** (the commenter says "I believe").

| Tag | Source | Read |
|---|---|---|
| PDB | [poedb.tw/us/Kingsmarch](https://poedb.tw/us/Kingsmarch), constants table; [poedb.tw/us/Recombinator](https://poedb.tw/us/Recombinator) (no cost text) | 2026-11-01, by a fetch agent |
| SCH | `poe-tool-dev/dat-schema`, files `3_25_Settlers_of_Kalguur.gql` and the 3.26 to 3.29 files: `VillageSharedConstants`, `RecombinableClasses` | 2026-11-01, `3_25` file read by me; the 3.26 to 3.29 files were read by the GPT researcher (no cost field either) |
| SHEET | Butsicles' public sheet of the 3.25 guide (thread `1exyavx`, link in the post), downloaded as `.xlsx` into `.claude/scratch/t177-sheet/`, 14 tabs; the screenshots on tabs "Recomb costs" (6) and "Interesting Examples" (20) viewed by me | 2026-11-01 |
| R-PSA | Reddit `1ldc3lz` (3.26 PSA, Butsicles, 2025-06-17; 127 comments), `1lfyxxd` (3.26 analysis, 190 comments) | read in full via the archive reader, 2026-11-01 |
| R-1j2 | Reddit `1j2up5k`, "Why is this simple Recombination Step over 150k Dust?", 2025-03-03 (56 comments) | read in full |
| R-SSF | Reddit `1nf9z35` (r/PathOfExileSSF), 2025-09-12 | read in full |
| R-oyb | Reddit `1oybm71`, "recomb solitaire with async trade", 2025-11-16 (159 comments); Reddit `1qs1qao`, `1qs6b5h` (Phrecia idol cost threads, 2026-01-31); Reddit `1rw4tl0` (2026-03-17) | read in full; only passages with Dust or Gold used |
| GPT | GPT researcher job `20261101-012814-5af3` (terra), run live: started, watched about 20 minutes of steps, two follow-ups, stopped. It found the forum thread `3925127` rows and the 3.27.0g idol note; its quotes of forum posts are **second-hand** (the forum answers me with a 403) | 2026-11-01 |
| MAX | [Maxroll recombination guide](https://maxroll.gg/poe/resources/recombination-guide) (Nov 2024) and a 3.29 retail-currency site's guide (unsigned, sells currency; one sentence there that crafted mods *raise* cost is not supported by anything else and is set aside) | 2026-11-01, by a fetch agent |
| CALC | Esm's calculator `recomb.rngissue.org` (its JavaScript bundle searched for "dust" and "gold": no hit; it is a mod-chance calculator) and the two Dust calculators (disenchant yield only) | 2026-11-01 |

Not reachable: the PoE forum (Cloudflare 403), Reddit itself (403; archive reader used), the GGPK. The archive reader's title search skipped many weeks (the archive timed out), so threads between 2025-07 and 2026-10 that were not already known were not swept; the claims below say so.

## 1. What the game files and calculators give

- **Constants (datamined, PDB):** `RecombinatorModDustCostMultiplier` = 3 and `RecombinatorModDustCostExponentTimes100` = 75, in the Kingsmarch constants table (nine constants; the other seven are shipment and recruit values). The page gives no unit, formula or use. No Gold constant exists in the table.
- **Client tables (datamined, SCH):** `VillageSharedConstants { Id: string, Value: i32 }` carries the two constants; `RecombinableClasses` lists item classes. No table with a per-mod cost column exists in the schema for 3.25 to 3.29. The number the window shows is therefore computed by code the files do not reveal (likely on the server), from the constants and from the inputs.
- **Wiki (W-rec in #90):** "costs Gold and Thaumaturgic Dust", depending on "item level and modifiers"; a bench rank 4 upgrade lists "25% reduced Recombination Cost" (Maxroll; applies to Gold, Dust or both is not stated). The 3.27.0 Dust counter in the window is in the wiki's history table.
- **Official, 3.27.0g (GPT, second-hand from forum thread `3910167`):** Idol recombination Dust lowered by 75% and Gold by 50%. This is the only official cost change I found after 3.26; the 3.28 and 3.29 launch notes show none. It is for idols; equipment is untouched.
- **Calculators:** none computes the cost. The only formulas on the web are disenchant yields.

So the sentence "`3 × x^0.75` per mod" in #90 stays a hint: the exponent 0.75 may sit on the whole pair, on each mod, or on an average; the data below favours "not a plain sum".

## 2. The 3.25 screenshots (first-hand; SHEET)

All are 3.25 (August 2024, Sentinel-era window with white items still accepted), one pair per window, Gold and Dust read from the bottom bar. Wands: Profane Wand, implicit 14% cast speed. Mod levels are the 3.29 `mods.json` required levels (they have not moved for these mods; the 3.25 tier numbers are as the window printed them).

| # | Left input (item level) | Right input (item level) | n mods | Gold | Dust |
|---|---|---|---|---|---|
| 0 | no mods (83) | no mods (84) | 0 | 3,237 | **42** |
| 1 | suffix "of Expertise" T5 (level 30) (83) | prefix "Polished" T7 (level 21) (84) | 2 | 3,884 | **217** |
| 2 | no mods (83) | prefix "Bitter" T8 (level 2) + suffix "of the Magma" T2 (level 72) (84) | 2 | 3,884 | **438** |
| 3 | prefix "Glaciated" T3 (51) + suffix "of the Salamander" T7 (12) (83) | prefix "Polished" T7 (21) (84) | 3 | 4,207 | **281** |
| 4 | "Sparking" T5 (33) + "of Puncturing" T3 (44) (83) | "Bitter" T8 + "of the Magma" T2 (84) | 4 | 4,531 | **512** |
| 5 | "Sparking" T5, "Empowering" T4 (30), "of Puncturing" T3 (83) | "Bitter" T8, "of the Magma" T2, "of Ruin" T2 (59) (84) | 6 | 5,178 | **696** |
| 6 | crafted multimod "of Crafting" only (84) | crafted multimod "of Crafting" only (86) | 2 | 4,377 | **51** |
| 7 | crafted "Upgraded" rank 2 (cold to spells), "Upgraded" rank 2 (physical), "of Crafting" (84) | "Upgraded" rank 2 (spell damage), "Upgraded" rank 1 (fire to spells), "of Crafting" (84) | 6 | 5,499 | **326** |
| 8 | Eagle Cry (71): "of Crafting", two "of the Order" crafts | Demon's Horn (70): "of Crafting", two "of the Order" crafts | 6 | 2,288 | **876** |
| 9 | Phantom Mitts (85): 6 mods, one "Upgraded" rank 3 | Phantom Mitts (86): 6 mods, one "Upgraded" rank 3 | 12 | 8,025 | **1,796** |
| 10 | Phantom Mitts (86): 6 mods, one "Upgraded" rank 3 | Phantom Mitts (86): 5 mods, one "Upgraded" | 11 | 8,131 | **1,086** |

Also from the same sheet, tab "Interesting Examples", cell A13 (text, no window): "Influence increases recomb costs by 50%" (3.25).

What the table shows (strength: screenshot, N = 11 windows, one author, one patch):

- **Gold.** Rows 0 to 5 (same wands, same item levels): Gold = 3,237 + 323.5 per mod, exactly linear (3,884 twice for two different two-mod pairs, so it does not see tiers). 3,237 is ten units of 323.7, so Gold = 323.7 × (10 + n) there. The unit changes with item level (rows 6 to 10: 143 at levels 70/71 for row 8, 344 for 84/84 in row 7, 365 for 84/86 in row 6 and for the 85/86 mitts in row 9) and is not exactly the same for all pairs (row 10 gives 387 per unit), so the "ten" is not safe outside the wands. Rows 6 and 7 are crafted-mod pairs and sit on the same line as natural mods.
- **Dust, base.** A pair with no mods costs 42, which equals 1.5 × 84^0.75 (41.7) to rounding; that is the one place the datamined exponent shows (a match of one number, not a proof).
- **Dust is not a sum over mods.** Row 2 (two mods on one input) costs 438; row 4 adds two mods on the other input and costs 512 (+74); row 5 adds two more and costs 696 (+184); row 1 (two mods, one per input) costs 217. A sum of per-mod terms must give row 4 − row 2 = value of "Sparking" + "of Puncturing" = 74, but "Polished" + "of Expertise" (row 1, lower levels 21 and 30) = 175. Mod count alone does not explain it either (row 7: six mods, 326).
- **Crafted is not cheap by nature.** Row 6: two crafted multimod mods add 9 Dust to the empty pair; row 7: six crafted mods cost 284 above the empty pair; row 8: six crafted mods cost 876 (the empty-pair base at item level 70/71 is not known; it is 42 at 83/84). The "Upgraded" and "of the Order" crafts are the high-level bench mods; the multimod is not.
- **Scale.** The same author's pages and Reddit give much bigger numbers a few months later (section 3). The 3.25 windows are a small-scale copy of the same shape at best. Which patch or hotfix rescaled Dust is not recorded; the 3.26 patch is the first for which player reports say "way higher".

## 3. The 3.26 to 3.29 numbers (player reports)

Each row: author, date, patch, N = 1 unless stated. All are Dust unless Gold is named.

| Report | Pair | Dust | Gold | Source |
|---|---|---|---|---|
| u/Soleil06, 2025-03-03, 3.25 Standard | two magic items, one T1 mod each (1p0s + 0p1s) | over 150,000 ("most recombs cost around 5k") | | R-1j2 |
| u/Tabernaster, 2025-03-04 | two magic 1-mod items, same level: T1 cold + T1 lightning prefixes / T1 attack speed + T1 crit multiplier suffixes | about 50,000 / about 5,000 | | R-1j2 |
| u/HockeyHocki, 2025-03-04 | T1 flat evasion/armour + life / T2 % evasion/armour + life | about 5,000 / about 40,000 | | R-1j2 |
| Butsicles, 2025-06-17, 3.26 | two T1 mods on magic items | "easily over 100,000"; "as low as 50k or less" with two low crafted mods | | R-PSA |
| u/Godofdeathryuk, 2025-06-17 | rare armour with an extra T1 suffix | 250,000 | about 300,000 for a whole long craft | R-PSA |
| u/g00fy_goober, 2025-06-20 | "2 mod + 2 mod" | about 260,000, then about 30,000 after crafting "worst int roll" on both | | `1lfyxxd` |
| u/infectorAlex, 2025-06-20 | a first step | was 1,500 in 3.25, now 40,000 "even with 2 low tier mods crafted on" | | R-PSA |
| u/ExiledYak, 2025-07-15 | two 1p/1s rares | 240,000 | | R-PSA |
| u/Mangalorien, 2025-09-12, 3.26 | magic inputs, T1 prefix and no suffix | "100~200k per try" is the asker's; the answer says a junk suffix lowers it | | R-SSF |
| durian_in_my_asshole, 2025-11-16, 3.27 | 2p + 3p shit bases, about 10 combines | 1.5 million total (about 150,000 each) | 200,000 total (about 20,000 each) | R-oyb |
| u/Any-Replacement-5645, 2026-03-17 | rare 2p2s daggers | "100-150,000 per attempt" | | R-oyb |
| u/lolfail9001, 2026-01-31, 3.27 | idols, predictable mode | 25,000 per attempt | | R-oyb |
| `Spacecom#5362`, forum thread `3925127`, 2026-03-28 (GPT, second-hand) | magic prefix item + magic suffix item, mods and levels not stated | predictable 27,000 / unpredictable 25,000 | 10,000 / 12,000 | GPT |
| u/bladomas, `1rxnycg`, 2026-03-19 (GPT, second-hand) | an item-level transfer pair, donor 86+ | about 12,000 | about 8,000 | GPT |
| forum thread `3791340`, 2025-06-15 (GPT, second-hand) | two magic items | 50,000 | | GPT |

Reading them together (strength: player reports, many authors, wide spread): a typical 3.26+ combine costs 25,000 to 250,000 Dust and 8,000 to 20,000 Gold; Dust moves by a factor of ten between pairs of the same kind (Tabernaster, HockeyHocki), Gold stays in a narrow band. Gold per unit of the 3.25 line (ten plus mods) is 830 to 1,300 for the three 3.26+ pairs (n = 2, 2 and about 5 to 8), about 2.3 to 3.6 times the 3.25 unit of about 365 at item level 86. N = 3, mod counts partly guessed.

Prices in the same threads (single comments, for the unit-price question): u/anraiki 2026-05-13 "15 divine for a 5 million gold rota" (#90); a 2025-11-16 comment in R-oyb, "Gold is 2.5d/1M and dust is ~0.5d/1M"; u/Pjatteri 2025-03-04 "buy binos for 50c … 1,3mil dust" (26,000 Dust per Chaos); durian 2025-11-16 "100k+ dust 1-5c uniques" (20,000 to 100,000 per Chaos).

## 4. Why a crafted mod lowers Dust: what is supported

Statements of the discount (all player reports):

- Butsicles, 2025-06-17: crafting "regular modifiers on the side of the item you don't care about … two low-tier affixes of mods that normally exist" lowers Dust "by at least a factor of 2, the more crappy mods you have the better"; on a 4-T1 item "two low tier crafted modifiers (non-exclusive)" on the unwanted side; "as low as 50k or less".
- u/No-Razzmatazz7854, 2025-06-18: "can save you 50% on dust cost … garbage early act craft".
- u/g00fy_goober: 260,000 to about 30,000 (a factor of 8.7), the only before/after pair.
- u/Mangalorien, 2025-09-12 (3.26): the rule is "item level and average tier of all the mods on each item"; "use as low ilvl items as you can"; lowest-tier bench craft such as 16-20% fire resistance; you can test by putting in two T1 prefix magic items, reading the Dust, crafting a junk suffix, reading again. No reply challenges it; nobody posts numbers for it. u/ZerkerChoco (2025-03-04): "I believe it's based on average ilvl requirement of the mods" (a guess, no data).
- Earlier threads (R-1j2, 3.25): "magic items have an insane dust multiplier", cost is "mod rarity" (u/Aromatic-Grape8516, "IIRC"), "scale on weighting. T1 cold/lightning damage have an insanely low weighting at t1 (108 vs 1200 for the lower ranks)" (u/Moneypouch), required level 79 versus 84 for two mods "of the same weight" (u/Qancho). Nobody tested these. The data of R-1j2 is: same-level magic pairs, Dust ten times apart (rare T1 prefixes versus common T1 suffixes), and T1 flat (level 79) 5,000 versus T2 percent (level 84) 40,000.
- Contradicting: one retail-currency guide says unwanted crafted mods raise the cost. It is unsigned, sells currency, and no player says it; I set it aside. It may be a garbled form of the true statement that a crafted *high-level* mod (the "of the Order" crafts, row 8) is expensive.

What this adds up to:

1. **Which property.** Not "crafted". Dust depends on how high and how rare a mod is (level, tier or weight: the threads are split, and the three move together for most mods), and a low-tier mod does *not* add its own small cost: it lowers the cost of the pair. A crafted low-tier mod works because it is low-tier, and because bench crafts are cheap and always available; a natural T7 mod lowers the cost the same way (Mangalorien, "you can also use natural dog shit tier mods"). Crafted high-level mods raise it (row 8).
2. **Sum or average.** The 3.25 rows 1 to 5 reject a sum. A search over simple families on the five two-sided wand rows (value = level, tier, 1/tier or 9 − tier; aggregate = sum, mean of all mods, mean per item summed, sum of powers, power of the sum, count times mean; power 0.1 to 4) ranks "mean of the value over all mods of both inputs, to a power near 2.5, times a constant, plus 42" first: with value 9 − tier it reproduces the five Dust values within 7% (223, 413, 277, 539, 689 against 217, 438, 281, 512, 696); with required level it is within 17% (row 2, 512 against 438, is the worst). Sum-type families are 13 to 23 times worse in squared relative error. This is a fit of two parameters (constant and power) to five points with a free choice of value function among five: it shows "mean-like" is the better family, nothing more. The constant 9 in "9 − tier" is not a property of the game (it equals the ladder length of the wands' mods used here) and the 2.5 is not the datamined 0.75. **Not a formula; not for the planner.**
3. **Size of the discount.** From the reports: a factor of 2 (Butsicles' minimum; one more player says 50%), up to 8.7 (g00fy_goober). If Dust grows like a power near 2.5 of a mean, two junk mods added to four T1 mods lower the mean to about two thirds to three quarters and the cost by a factor of 2.3 to 2.8, below the 8.7 reported; so either the true power is larger, or the value function is steeper than 9 − tier near the top (the 3.25 "T1 flat, level 79" against "T2 percent, level 84" pair, a factor of 8, suggests a steep top end). I do not resolve this.
4. **Does it work for any crafted mod, on either input, on both?** Reports say any low-tier non-exclusive craft, on either input (Butsicles: both inputs for a prefix pair; on the side you do not care about for a mixed pair). Nothing says one input is enough; "on both" is the repeated advice and the measured pair (g00fy) had it on both. The 3.25 sheet's only one-sided data (row 2 against row 4) does not test it. This is on the in-game list (section 7, pairs 3 and 4).
5. **Side effects the planner must know.** A bench craft needs an open slot of its side; a prefix craft on a prefix-recombination hurts the success odds ("crafting prefixes for triple prefix combines makes your odds worse", R-PSA); for a prefix target the craft goes on the suffix side. Exclusive crafts (aspects, "of the Order"-type metamod-adjacent mods) change the pool and are not "regular" mods; the author's list of non-exclusive crafts is the sheet's tab 2 (Life, resistances, attributes, and so on). The junk craft can be removed with the bench for one Scouring Orb or a "Remove Crafted Mods" (R-oyb and `1vm0rxj`).

## 5. The cost rule for the planner

Approximate; every report below is a Reddit or forum report; the planner marks the answer approximate and shows the interval (ADR-0028, as for #175).

| Quantity | Point | Interval | Evidence |
|---|---|---|---|
| Gold per combine | 12,000 | 8,000 to 20,000 | forum `3925127` (10,000 predictable and 12,000 unpredictable for two magic items), `1rxnycg` (8,000), R-oyb (about 20,000 each for rare 2p + 3p bases); Gold per unit 830 to 1,300 times (10 + mods) in 3.26+ against 365 in 3.25 |
| Gold change for one extra mod | + 1 unit of about (10 + n) | | 3.25 wands, exact (rows 0 to 5); not measured in 3.26+ |
| Dust per combine, pair of magic or rare inputs, at least one high-level (T1-like) mod | 100,000 | 25,000 to 250,000 | section 3, eleven reports from five authors in 3.26 and 3.27 |
| Dust per combine, pair of low-tier mods only | 30,000 | 5,000 to 50,000 | 3.25 (HockeyHocki 5,000, Tabernaster 5,000), g00fy_goober (30,000), Butsicles (50,000) |
| Dust factor with a low-tier non-exclusive craft on each input | 0.5 | 0.11 to 0.5 | Butsicles (at least 2), No-Razzmatazz (50%), g00fy_goober (1 ÷ 8.7) |
| Influence on an input | + 50% | | 3.25 sheet, one line, no window |
| Idols | Dust × 0.25 and Gold × 0.5 against the equipment rule | | 3.27.0g (official, second-hand); B3 has no idol route |

At the owner's prices (150,000 Dust per Chaos, 500 Chaos per million Gold) one combine costs:

| | Dust | Gold | Total |
|---|---|---|---|
| point | 0.67 Chaos | 6 Chaos | about 7 Chaos |
| low | 0.17 (25,000) | 4 (8,000) | about 4 |
| high | 1.7 (250,000) | 10 (20,000) | about 12 |

Gold is 85% to 95% of the cost in all three rows. With the discount at the point (factor 0.5) Dust saves 0.33 Chaos (best case: 0.6 Chaos at the 0.11 factor and 100,000 Dust); the craft adds one Gold unit (+14% at n = 2 pairs: +0.8 Chaos on 6) and costs a bench craft and its later removal. **At the default prices the junk craft does not pay; the planner should not offer it unprompted.** The step still belongs in the action list, as an optional action ("craft the cheapest non-exclusive mod on the open side of each input", Dust × 0.5), because the owner may set a dearer Dust: break-even is about when Dust per combine (after discount) in Chaos exceeds the extra Gold plus the craft, roughly 1.5 Chaos, that is Dust priced at or below about 35,000 per Chaos for the 100,000 point (the market notes of section 3 range from 10,000 to 100,000 per Chaos, so it flips inside the market's own spread).

**Owner's note on the default.** The owner's default of 150,000 Dust per Chaos is at or beyond the cheap end of the market comments read here (10,000 to 100,000 per Chaos, five single comments from 2025-03 to 2025-11), while the Gold default (500 Chaos per million) matches the 2.5 Divine per million of the one 2025-11 comment at about 200 Chaos per Divine. Nothing is changed here; the price file is the owner's.

**What the planner stores.** `recombinator_cost` as a table in the price or rule data: `gold_per_combine` and `dust_per_combine` with point and interval, `junk_craft_dust_factor` with point and interval, `bench_rank_discount` unset until read from the game (rank 4 "25% reduced Recombination Cost"; it may already be inside every report above or in none), and `source: reports, approximate`. It does not compute Dust from mods: no formula supports it.

## 6. Whether Gold follows the discount

3.25 sheet: no. Gold read the same for two different two-mod pairs (rows 1 and 2) and moved only with the mod count, crafted or not (rows 6 and 7 sit on the line). 3.26+: no data with a before and after for Gold; the one pair with both modes (forum `3925127`) shows the unpredictable mode with a lower Dust and a higher Gold than the predictable mode (25,000 and 12,000 against 27,000 and 10,000), which only says Gold and Dust are separate functions. Not settled for 3.26+: pair 3 of section 7 reads both numbers.

## 7. For the owner: in-game readings, no crafting beyond two bench crafts

Read the Gold and Dust off the window; no recombination is run. One item class for all pairs (a cheap one-handed weapon, wand or sceptre, so the bench crafts cost about 1 Chaos), two copies at item level 84 or above unless said otherwise, both in the window, mode set to unpredictable. Note the bench rank (shown on the bench) and take a screenshot with both item tooltips and both numbers in view; the main chat reads it.

| # | Left input | Right input | Settles |
|---|---|---|---|
| 1 | magic, one prefix of the lowest tier | magic, one prefix of the lowest tier | the low baseline |
| 2 | magic, one T1 prefix | magic, one different T1 prefix | the high baseline (the 3.26 reports say about 100,000) |
| 3 | pair 2, plus the cheapest low-tier craft (for example the lowest "+ to strength" suffix) on each | | the discount factor; also whether Gold moves (one more mod each) |
| 4 | pair 2, craft on the left only | | whether one input is enough |
| 5 | pair 2, with a *natural* lowest-tier suffix on each instead of a crafted one (alteration and augment until it appears) | | crafted against natural |
| 6 | pair 2, with the *highest* bench craft you can afford on each (for example a top attribute or a multimod-free "Upgraded"-style craft) | | whether a high-level crafted mod raises the cost |
| 7 | pair 1 at item level 68 and 68, against the same at 84 and 84 | | item level |
| 8 | pair 2 with one T1 prefix of high weight (for example attack speed on the suffix side) on both, against a T1 prefix of low weight (for example T1 cold damage on a wand) at the same level | | weight against level (the 5,000 against 50,000 report) |
| 9 | pair 2, mode switched to predictable | | the mode difference for Dust and Gold |
| 10 | a rare pair, 3 mods each: three T1 / three T1, then the same with the lowest-tier mod replaced (alteration, no crafting) | | mean against sum for a larger pair |

Ten windows are enough to choose between "mean of a per-mod value" and "sum" and to see whether the value follows level, tier or weight; two bench crafts (pairs 3 and 6 reuse them) cost about 2 Chaos in all. If the owner holds no suitable items, pairs 1 to 4 and 9 settle the planner's rule and are the minimum.

## 8. What was not found and what changed my confidence

- **Not found:** a formula; the Gold formula for 3.26+; any 3.27 to 3.29 measurement with a before and after; the meaning of `x` in the constants; the bench rank discount's target. The archive reader skipped about twenty weeks of titles (timeouts), so a 2025-07 to 2026-10 thread with a measured table could exist; two removed threads (`1w0kdir`, `1vygl2m`) have no body.
- **Not trusted:** the 3.29 retail-currency guide (unsigned, sells currency), the researcher's second-hand forum quotes beyond what is marked (I could not open the forum myself), the fit of section 4.2.
- **Dismissed:** "underflow" (R-1j2): disproved in-thread by arithmetic of the numbers (no 2^15 or 2^16 boundary); a deliberate extra rule for single-mod magic pairs ("insane multiplier", 48 upvotes, u/SingleInfinity says deliberate) is a player claim and fits the 150,000 report, but no one measured the multiplier; this note takes it as one more reason for the Dust interval to be wide for 1-mod magic pairs.

## 9. Draft claims for `src/crafting_system/rules/claims/recombinator_cost.yaml`

Seven fields as in the existing files (`id`, `statement`, `source_kind`, `url`, `quote`, `patch_verified`, `date_checked`), plus `value` where there is a number. Reddit and forum reports are `source_kind: experiment` with "UNVERIFIED" in the statement (the same convention as #90). Quotes are fragments. No claim is a formula.

```yaml
# Mechanic family: recombinator_cost (Thaumaturgic Dust and Gold of one recombination).
# Research ticket #177. No formula is published; the rules below are constants, a first-hand
# 3.25 data set and player reports, each marked.
rules:
  - id: recombinator_cost.currencies
    statement: 'A recombination costs Gold and Thaumaturgic Dust; the amount depends on the item level and the modifiers of the two inputs.'
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Recombinator
    quote: "depends on the item level and modifiers of the input items"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: recombinator_cost.datamined_constants
    statement: 'The game files hold two Dust constants for the recombinator, a multiplier of 3 and an exponent times 100 of 75 (0.75). No Gold constant, no use and no formula is given with them; the quantity they apply to is not known.'
    source_kind: datamined
    url: https://poedb.tw/us/Kingsmarch
    quote: "RecombinatorModDustCostMultiplier 3; RecombinatorModDustCostExponentTimes100 75"
    value: {multiplier: 3, exponent_times_100: 75}
    patch_verified: "3.29.3.3"
    date_checked: 2026-11-01

  - id: recombinator_cost.no_client_table
    statement: 'The public client-table schema holds no recombinator cost table; `VillageSharedConstants` is a list of named integers and `RecombinableClasses` lists eligible item classes. The cost is computed by code the data files do not expose.'
    source_kind: datamined
    url: https://raw.githubusercontent.com/poe-tool-dev/dat-schema/main/dat-schema/3_25_Settlers_of_Kalguur.gql
    quote: "type VillageSharedConstants { Id: string Value: i32 }"
    patch_verified: "3.25.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.gold_linear_in_mod_count_3_25
    statement: 'In 3.25, with the same two wands, Gold rose in a straight line with the total number of mods on the two inputs (0, 2, 3, 4, 6 mods gave 3,237; 3,884; 4,207; 4,531; 5,178; about 323.5 per mod, ten units at no mods) and two different two-mod pairs gave the same Gold, so it did not depend on mod tiers. Crafted mods counted as ordinary mods.'
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit?usp=sharing
    quote: "tab Recomb costs: 3,237 / 3,884 / 4,207 / 4,531 / 5,178 gold"
    value: {gold_at_zero_mods: 3237, gold_per_mod: 323.5}
    patch_verified: "3.25.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.dust_not_a_sum_3_25
    statement: 'In 3.25 the Dust of a pair did not add up over mods. Two wands with no mods cost 42 Dust; one mod on each input (T5 suffix and T7 prefix) 217; two mods on one input (T8 prefix and T2 suffix) 438; adding two mods on the other input 512; two more mods 696. A sum of per-mod terms cannot give both 217 and 74 for the added mods.'
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit?usp=sharing
    quote: "tab Recomb costs: 42, 217, 438, 281, 512, 696 dust"
    value: {dust: [42, 217, 438, 281, 512, 696]}
    patch_verified: "3.25.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.crafted_multimod_cheap_3_25
    statement: 'In 3.25 two wands each holding only the crafted multimod "of Crafting" cost 51 Dust (42 with no mods); six crafted high-level mods ("of the Order") cost 876. A crafted mod is cheap or dear by its own level, not because it is crafted.'
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit?usp=sharing
    quote: "tab Interesting Examples: 4,377 gold 51 dust; 2,288 gold 876 dust"
    value: {dust_multimod_pair: 51, dust_six_order_crafts: 876}
    patch_verified: "3.25.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.influence_plus_50_percent_3_25
    statement: 'UNVERIFIED (one line in the author''s sheet, no window): influence on an input raises the recombination cost by 50%.'
    source_kind: experiment
    url: https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/edit?usp=sharing
    quote: "Influence increases recomb costs by 50%"
    value: 0.5
    patch_verified: "3.25.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.junk_craft_halves_dust_3_26
    statement: 'Butsicles (author of the 3.25 and 3.26 guides, about 500 to 800 combines in 3.25) advises crafting low-tier non-exclusive mods on the side of the item you do not care about; he says it lowers Dust by at least a factor of 2, and costs can be 50,000 or less with two low-tier crafted mods. One more player reports 50%, one reports about 260,000 to about 30,000 (a factor of 8.7, uncontrolled). Read on 3.26 on 2025-06-17 to 2025-06-20.'
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/
    quote: "lower the dust cost by at least a factor of 2"
    value: {factor_point: 0.5, factor_low: 0.11, factor_high: 0.5}
    patch_verified: "3.26.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.dust_rule_average_tier_report
    statement: 'UNVERIFIED player assertion (u/Mangalorien, 2025-09-12, 3.26, nobody contradicted it, nobody posted numbers for it): the Dust cost is calculated from item level and the average tier of all the mods on each item; a low-tier bench craft lowers it, and two T1 prefix magic items can be tested before and after a junk suffix. An earlier guess (u/ZerkerChoco, 2025-03-04) says average required level of the mods.'
    source_kind: experiment
    url: https://www.reddit.com/r/PathOfExileSSF/comments/1nf9z35/_/ndv8ogk/
    quote: "item level and average tier of all the mods on each item"
    patch_verified: "3.26.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.dust_per_combine_reports_3_26
    statement: 'UNVERIFIED (reports, N about 11 from five authors, 2025-06 to 2026-03): one combine of magic or rare inputs holding a T1-like mod costs 25,000 to 250,000 Dust (typically about 100,000 to 150,000); pairs of low-tier mods only cost 5,000 to 50,000; the same kind of pair can cost ten times more for a rare, high-level mod than for a common one.'
    source_kind: experiment
    url: https://www.reddit.com/r/pathofexile/comments/1ldc3lz/
    quote: "easily give costs over 100,000"
    value: {point: 100000, low: 25000, high: 250000}
    patch_verified: "3.26.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.gold_per_combine_reports_3_26
    statement: 'UNVERIFIED (three reports, 2025-11 to 2026-03; two from forum or Reddit threads read second-hand): one combine costs 8,000 to 20,000 Gold; two magic items cost 10,000 (predictable) or 12,000 (unpredictable) Gold with 27,000 or 25,000 Dust; about 20,000 Gold and 150,000 Dust each for ten rare 2p and 3p combines.'
    source_kind: experiment
    url: https://www.pathofexile.com/forum/view-thread/3925127
    quote: "Unpredictable says 100% for 12k gold and 25k dust"
    value: {point: 12000, low: 8000, high: 20000}
    patch_verified: "3.26.0"
    date_checked: 2026-11-01

  - id: recombinator_cost.idol_cost_cut_3_27
    statement: 'UNVERIFIED (read second-hand from the official forum by the GPT researcher; not opened by me): the 3.27.0g hotfix lowered the Dust of idol recombination by 75% and its Gold by 50%. It is the only official recombinator cost change found after 3.26; equipment is not mentioned.'
    source_kind: official
    url: https://www.pathofexile.com/forum/view-thread/3910167
    quote: "lowered Idol recombination Dust by 75% and Gold by 50%"
    patch_verified: "3.27.0g"
    date_checked: 2026-11-01

  - id: recombinator_cost.bench_rank_discount
    statement: 'A Kingsmarch bench upgrade (rank 4 in the Maxroll table of November 2024) lists "25% reduced Recombination Cost". Which of Gold and Dust it applies to, and whether it is inside the reported numbers, is not known.'
    source_kind: wiki
    url: https://maxroll.gg/poe/resources/recombination-guide
    quote: "25% reduced Recombination Cost"
    patch_verified: "3.25.0"
    date_checked: 2026-11-01
```

Source kind note: `wiki` is used for the Maxroll page because it is a published guide table, not a player report; if the claim-file rules want a stricter reading, move it to `experiment`.
