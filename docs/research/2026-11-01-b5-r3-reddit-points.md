# B5 R3: the six Reddit points of #98, second sweep, and the emulator that models strands

Research ticket [#273](https://github.com/Rasslabsya4el/crafting-system/issues/273) of map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1), batch B5. It fills the table "Reddit-dependent open points" of [the #98 note](2026-10-31-memory-strands.md) (the filled table is there, with quotes and links), checks each point against Craft of Exile first, and drafts the claims that change an ADR default. Written 2026-11-01 against the pinned patch 3.29.3.3. Design: [ADR-0040](../adr/0040-the-strand-count-and-the-tier-cut.md) to [ADR-0044](../adr/0044-the-orb-of-unravelling.md). Nothing here changes `src/`.

## Answer in brief

1. **Craft of Exile has a second emulator that models strands, and it is current.** `beta.craftofexile.com` (code built 2026-10-31 20:50 UTC, data 3.29.3.3; its changelog adds "Memory strand behavior", "Orb of Remembrance" and "Orb of Unravelling" on 2026-09-30) implements the cut, the spend table, Remembrance, Unravelling, the Foulborn orbs and imprint restore. The copy in `sources/raw/coe/` and the main site's emulator (code built 2026-08-07, the one the headless harness of [#198](https://github.com/Rasslabsya4el/crafting-system/issues/198) drives) do not. The sentence "Craft of Exile's emulator models no strand craft" in ADR-0041 and in the B5 comment on [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182) is true of that older copy only. I read the beta's public code; I did not run it, because the harness is built for the main site (a follow-up for #198: point it at the beta).
2. **Players and the emulator agree with every ADR-0041 default that was an inference.** Fossils and Harvest neither spend nor are cut (players, 2025; the emulator cuts only the methods that have a spend row). Annulment, Scouring and Divine leave the count (recipes of players, 3.26 and 3.29, no counted tests; the emulator: no row, no reset). The spend ceilings are the wiki's. A recombination hands over either input's count (a guide, 3.26; nobody says whether the inputs' strands are spent). Nothing found contradicts them. Not found: Vaal outcomes (the wiki already says the corrupted item keeps its strands), non-guaranteed essence mods, identification.
3. **One ADR default changes: the Foulborn Exalted ceilings.** The emulator holds the whole row by the number of mods before the craft: 46, 46, 52, 56, 60, 62 (0 to 5 mods; 62 at 5 mods is also the wiki's). ADR-0041 and ADR-0043 scaled the plain Exalted row and got 29, 40, 47, 58, 62; PoEDB lists one figure, 28. Draft claim `foulborn.exalted_spend_by_mod_count`, `approximate` (the emulator against PoEDB; nobody tested the orb).
4. **The 0-strand Foulborn case gets a little more support.** The first sweep quoted only the "both sides of some of these breakpoints" sentence. Section 1.1 of the post also says Foulborn's restriction "exactly matched that of 10-11 memory strands", and 11 strands is D = 175 (100 + 75), the ADR's value. The sentence reads as Foulborn alone but does not say the compared item had no strands, so the 0-strand reading is still mine. The AMA's cluster-jewel advice (no strands on a jewel) gives the same cuts at 2 and 3 tiers as D = 175, and also as the emulator's rating of 100, so it does not choose between them. The case stays `approximate`.
5. **Two conflicts with the emulator, both for the in-game list, neither changes the plan.** The emulator rates Foulborn at 100 (not 75) and uses the larger of the Foulborn cut and the strand cut instead of the sum: alone it gives kept-tier lists that differ from the wiki's at 8, 10, 12, 14 and 15 eligible tiers, and with strands it keeps more tiers than the post's additive rule in 800 of 1,500 cells. The post fits 491 Foulborn rows to the additive rule, so ADR-0040 stands. Two other emulator rules lose to data: its Remembrance distribution (chi-square 370 on 17 degrees of freedom against 7.2 for the ADR's) and its plain-weight Unravelling destination (p = 0.007 on the wand test of ADR-0044).
6. **Weights of the kept tiers (point 1) are still untested** and no thread, post or emulator separates the readings of ADR-0042; the emulator is reading 3, as the older copy. Jewels and Remembrance, special mods under Unravelling, Divine and Vaal under a player's eye: not found (details in the table).

## How the sweep ran

- **Archive** (Arctic Shift, `reddit_archive.py`): 22 threads read by id (list below). Title searches over 2026-07-20..2026-11-02 and 2025-06-15..2026-07-20 returned posts for `foulborn` and `unravelling`; these windows timed out and are **not** searched: `unravel` 2026-07-20..2026-09-23 and 2026-10-06..2026-11-02 (2026-09-23..2026-10-06 answered with no post), `memory strand` 2026-10-06..2026-11-02, `strands` 2026-03-29..2026-04-23, `unravelling` 2026-02-20..2026-05-06, `remembrance orb` 2025-06-15..2025-08-04 and 2025-12-07..2025-12-19. `remembrance` over 2026-07-20..2026-11-02 returned no post. So a thread titled without the words searched, or in a timed-out window, was not seen.
- **Researcher** (`gpt-research`): `terra` is refused by the tool today ("model 'terra' is not allowed ... Allowed: luna=gpt-6-luna and gpt-6.1-terra"), so two luna runs (`20261101-135433-75bf`, `20261101-140356-361f`, 3 and 3.5 minutes) gave thread ids. Their quotes were not trusted: I opened every thread through the archive and kept only what I read there. Dropped as unverified: a forum guide (br.pathofexile.com thread 3882365), the PoE Dust Calculator's sample summary, a claimed PoEDB "official" text (the PoEDB page itself says "We don't have fossils and harvest and stuff do it", which is unclear), and the Craft of Exile changelog line quoted by the researcher, which I read myself on the changelog page.
- **Craft of Exile:** `https://beta.craftofexile.com/` (index, changelog, `packages/files/package_poe1.js` v=1793479842 SHA256 `5d3b96d7...a60c`, `json/poe1/3.29.3.3/data.json` SHA256 `6f5083e8...1598`), read-only, kept in the session's scratch folder, **not committed**. The older copy's pins are in the README of [#254](https://github.com/Rasslabsya4el/crafting-system/pull/254).
- **Wiki and PoEDB:** the wiki answers "Access Denied" (Anubis) to a plain fetch; PoEDB's Memory Strands page was read (spend table, "Foulborn Exalted 0-28", Remembrance "normal equipment item").

Threads read first-hand (id, topic): 1wr9445 the post; 1lre3w4 usages (2025-07); 1logzeb crafted mods and Unravelling (2025-06); 1oqpunf rarity bench craft now spends (2025-11); 1liwnwd claw craft; 1lg6y7c "Memory Strand Crafting" (HTTP 422 on the first sweep, answered now; nothing on the six points); 1lcxuwz 80-strand Unravelling that did nothing; 1les71e crafted mods raised by Unravelling (the 3.26.0d fix); 1m1tefo, 1m4z9mk, 1lhuzlo Unravelling reports; 1lpceet, 1lrigzv, 1mq4l3y, 1m01psj, 1t815pc crafting guides; 1v6az4j, 1v969f8 (removed), 1w84ljt, 1vooz14, 1ved7x1, 1vkf12u Allflame and Foulborn threads; 1vc1e72 the crafting AMA of 3.29.

## What Craft of Exile's beta does (read from its code, 2026-11-01)

| Rule | The emulator | Against ours |
|---|---|---|
| Strand cut | `kept = floor(100 / (2.5 s + 147.5) * (w - 1)) + 1` of the `w` tiers eligible at the item level, the lowest removed | the wiki's formula and ADR-0040; floats and our exact integers give the same kept count in all 1,600 cells (w 1..16, s 1..100: 0 mismatches) |
| Which methods cut | only those with a row in the spend table | ADR-0041's table, including fossils, Harvest, beasts, bench: not cut |
| Weights after the cut | removed tiers are skipped, kept tiers keep their weights | reading 3 of ADR-0042 |
| Spend | uniform whole number 0..ceiling; ceiling by explicit mods before the craft | the wiki's ceilings: 8 / 16 / 50 / 80 / 60 / 100; Exalted `[16, 16, 22, 26, 32, 34]`; tainted Exalted `[18, 18, 24, 28, 32, 34, 38]`; Foulborn Augmentation 32, Regal 48, Foulborn Exalted `[46, 46, 52, 56, 60, 62]`. No row for Orb of Binding, Orb of Chance, the bench rerolls (ADR-0041 gives them 50 from the wiki) |
| Foulborn | a tier rating of 100: alone `kept = w - floor(w / 2)`; with strands the larger of the two cuts | ADR-0040: rating 75 (D = 175), added to the strand denominator. Conflict (below) |
| Remembrance | any class but a strongbox; sets the count to `round(10 + 12.1 * G)`, G a gamma(2.6) draw, redrawn above 100 | ADR-0043: normal(35, 25) in 10..100. The sheet rejects the emulator's law (below) |
| Unravelling | per explicit, non-fractured, non-veiled mod: chance `min(1, s * W_up / (2 * W_side))` (essence and influenced mods: `min(1, s / 25 * W_up / W_group)`), `W_side` the whole side pool of the item emptied of its mods; destination by the plain weights of the higher tiers; the count goes to 0 | chance and `W_side` as ADR-0044; the destination is a third reading that fails the wand test (below) |
| Scouring, Annulment, Divine, Vaal, Fracturing, fossils, Harvest | no row, nothing resets the count | ADR-0041 |
| Imprint restore | returns the stored item copy, strands included | ADR-0034 |
| Recombinator | none | |
| Other details | Remembrance needs a normal-rarity item; Unravelling treats a tier of weight 0 as weight 1; the Foulborn cut counts `N + 1` (the position of the last eligible tier), which equals the number of eligible tiers only when no lower tier is ineligible | ADR-0043 already requires a normal item; the other two are small and untested |

`2026-11-01-b5-r3-checks.py` (standard library, no network) reproduces the three comparisons; its output on 2026-11-01:

- **Remembrance** on the 2,255 results of the sheet: ADR-0043's normal(35, 25), lower bound 10: mean 41.84, chi-square 7.2 on 17 df (p = 0.98); the emulator's law: mean 40.55, chi-square 370 on 17 df; it puts 1.6 % of results at 10..14 (6.0 % observed); log-likelihood −9,702 against −9,914.
- **Foulborn alone**, kept tiers for N = 1..15: wiki / D = 175: 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7, 8, 9; emulator: 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8. They differ at N = 8, 10, 12, 14, 15.
- **Foulborn with strands**: the emulator keeps more tiers than the post's additive rule in 800 of 1,500 cells (N 1..15, s 1..100), fewer in none; for example 13 tiers and 11 strands: 7 against 5.
- **Unravelling wand test** (257 cases, T1 / T2 / T3 observed 2.72 / 16.73 / 80.54 %): rank multipliers 2.03 / 16.89 / 81.08 %, chi-square 0.62 (p = 0.73); cumulative 4.05 / 20.95 / 75.00 %, 4.36 (p = 0.11); plain weights 5.41 / 22.52 / 72.07 %, 9.81 (p = 0.0074).

The emulator's rules are the implementer's reading, not a test; where the post's sheet or the wand data speak, they win. Its table of spend ceilings agrees with the wiki cell by cell wherever the wiki shows one, which is why its Foulborn Exalted row is taken for the cells the wiki hides.

## Draft claims

[`2026-11-01-b5-r3-claims/`](2026-11-01-b5-r3-claims/): eleven claims, checked with `load_registry(Path("docs/research/2026-11-01-b5-r3-claims"))` (11 rules load). The build session that promotes `memory_strands.yaml` and `foulborn.yaml` of #98 copies them with those files.

| Claim | Source | Changes |
|---|---|---|
| `foulborn.exalted_spend_by_mod_count` | coe | **ADR-0041 and ADR-0043 default**: 29, 40, 47, 58, 62 becomes 46, 46, 52, 56, 60, 62 |
| `foulborn.zero_strand_cut_matches_eleven_strands` | experiment (the post) | ADR-0040: "D = 175 on a 0-strand item rests on the wiki alone" gains the author's observation |
| `memory_strands.fossil_harvest_not_cut` | experiment | ADR-0041: "not cut" is no longer an inference alone |
| `memory_strands.cut_follows_spend_table` | coe | ADR-0041: Scouring, Annulment, Divine, Vaal, Fracturing: a stated source |
| `memory_strands.annulment_keeps_strands`, `memory_strands.scouring_keeps_strands`, `memory_strands.divine_keeps_strands` | experiment | same (recipes, no counted tests) |
| `memory_strands.recombinator_strands_from_either_base` | experiment | ADR-0033 and ADR-0041: the count rule becomes a guide's statement; "nothing spent" stays the author's play |
| `memory_strands.unravelling_skips_fractured_and_veiled` | coe | ADR-0044: "fractured excluded ... in the claim the build writes" now has its claim |
| `memory_strands.unravelling_side_weight_is_whole_pool` | coe | ADR-0044 and open point 7 of #98: the `W_side` definition |
| `memory_strands.remembrance_classes_observed` | experiment | ADR-0043: "other equipment classes rest on the wiki's word" |

Every claim but `foulborn.exalted_spend_by_mod_count` keeps the planner's number; they replace "an inference" or "silence" by a stated source. All are `approximate` with a reason. The ADR sentences that say "Craft of Exile's local copy models no strand craft" (ADR-0041, "Unknowns and the in-game list") are for the build session to update.

## Lines for the in-game list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182))

Posted as one comment there (see the PR for its link). Summary:

- **Answered by the emulator and the players, both agreeing with the default** (the claims stay `approximate`, so the checks are optional and the main chat may drop them): check 1 (Scouring, Annulment, Divine keep the count; Fracturing and Vaal are the emulator's and the wiki's word), check 2 (fossil and Harvest are not cut), check 6 (Unravelling skips fractured and veiled mods). Check 4 (essence respects the cut) is answered the same way for the emulator (essence has a row) and stays optional for the non-guaranteed mods.
- **Changes:** check 5 (Foulborn Exalted on 1 to 4 mods): the default is now the emulator's row 46, 46, 52, 56, 60, 62 instead of 29, 40, 47, 58, 62; PoEDB's 28 conflicts; the tooltip settles it.
- **Stays:** check 3 (Remembrance on a jewel): the wiki says equipment, the emulator allows jewels; default "jewels no".
- **New, optional, expensive:** the Foulborn cut on an item with no strands and on one with strands: the post and wiki (rating 75, sum with the strand cut) against the emulator (rating 100, larger of the two). Default: the post and wiki. The first needs only a mod type with exactly 8 eligible tiers on a 0-strand magic item and about 40 Foulborn Augmentations (whether the 5th best tier ever appears: yes under the wiki, never under the emulator); the second the sheet-fit ticket can close from the post's 491 Foulborn rows before anyone spends a coin.

## Still open after R3

- Weights of the kept tiers (ADR-0042): no thread or emulator separates the three readings; the raw sheet is the only evidence that can.
- Foulborn rating 75 against 100, the sum against the larger cut (above).
- Remembrance on jewels and on rings, weapons and flasks; the dependence of the result on the old count (the emulator makes it independent; no thread tests it).
- Unravelling of enchanted and metamod-protected mods, and above 32 strands; an independent large sample; Vaal outcomes; the second use of a Foulborn orb after the strands are spent; identification.
