# Hinekora's Lock in 3.29: the rules, and what the solver must model

**Status, 2026-11-01.** The owner answered in [#106](https://github.com/Rasslabsya4el/crafting-system/issues/106): the previews of different currencies are independent (Q1, from play, so the one-look ceiling of 6.4 is not built); the Lock does preview Exalted, Annulment and Regal (part of Q2: Transmutation, Alteration, Augmentation, Alchemy and Scouring stay previewed by item text only, marked approximate); essences and fossils are unknown, so blind; a second Lock on a foreseeing item is not possible; the Lock is used up. Burn and relock (Q3) is the main chat's decision, not an owner answer. The design is ADR-0054 to ADR-0057, and the draft claims of section 10 are amended there (`chaos_orb_previewed` no longer waits on Q2). The text below is the research as written on 2026-10-31.

Research ticket [#101](https://github.com/Rasslabsya4el/crafting-system/issues/101), inventory row M-80, for the design grill of batch B8 ([#106](https://github.com/Rasslabsya4el/crafting-system/issues/106)) and the last batch ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)). Written 2026-10-31 against patch 3.29.3.3. Scope as the owner set it in #81: equipment, jewellery and jewels; unique items are never a target.

## 1. The short answer

- **What it does.** The Lock is put on one item. From then on, hovering any currency over the item shows the exact result of using that currency next. Looking costs nothing and changes nothing. Using a currency applies the shown result and ends the preview.
- **The preview is a fixed result, not an estimate.** Every Chaos Orb you hover shows the same preview; applying it makes the item exactly what was shown. Different currencies each show their own result, all at once, from the same lock.
- **What ends it.** Any change to the item: any currency used, a bench craft, an Imprint, an anoint, a recombinator, a beast craft. Looking at previews does not end it. Incubators are said to keep it (a disputed line, section 3).
- **Kind of plan.** A plan with information: after the Lock is on, the best next move depends on what the previews show, not only on the item. That is a different shape from every other action in v1, where the action is chosen before the dice are thrown. The solver can model it **without adding any stored state, provided the previews of different currencies are independent draws** (not yet known, section 7): the Lock is one action whose value is the expected best reaction to the previews, minus the lock's price (section 6). Without independence the one-look bound in 6.4 still adds no state, but the exact best-of value cannot be computed.
- **Cost.** In the Allflame league the Lock sells for about 271 to 272 Divine Orbs (section 5). A plan will pick it only where the previews save more than that, so in most ordinary routes it will not appear.
- **What is not known.** The Reddit evidence is four threads, all from 3.22 and 3.23 (Oct to Dec 2023, when the Lock still previewed the Altar of Corruption); nothing from 3.24 to 3.29 was read. The list of crafts that are not previewed rests on one wiki page whose only reference is a YouTube video (33:00, not opened); Maxroll repeats it without being independent. Nothing read settles the points below. Whether the previews of different currencies on one lock are independent, whether essences, fossils, catalysts and Eldritch currency preview, and whether active Omens change a preview are all unsettled (section 7). Three questions for the owner come out of this (section 8).

## 2. Sources and what was and was not reachable

Every source was read on 2026-10-31 unless stated.

| Id | Source | Kind | Note |
|---|---|---|---|
| S1 | [Hinekora's Lock](https://www.poewiki.net/wiki/Hinekora%27s_Lock), live page in the built-in browser; last edit 2026-08-02 | wiki | The only full statement of the rules. |
| S2 | S1's [revision history](https://www.poewiki.net/index.php?title=Hinekora%27s_Lock&action=history&limit=100), with the diffs of 2026-03-29, 2026-08-01 and 2026-08-02 | wiki | Shows which sentences are recent and which are disputed. |
| S3 | [Trial of the Ancestors](https://www.poewiki.net/wiki/Trial_of_the_Ancestors) and [Version 3.23.0](https://www.poewiki.net/wiki/Version_3.23.0) on the wiki, which quote GGG's patch notes | official, via wiki | The 3.23.0 note on the Altar of Corruption. |
| S4 | A text scan of the wiki pages of every GGG version from 3.23.0 to 3.29.3b (71 pages) for "Hinekora", "foresee", "foresight" | official, via wiki | Only 3.23.0 touches the Lock. |
| S5 | [The Black Mórrigan](https://www.poewiki.net/wiki/The_Black_M%C3%B3rrigan) | wiki | The 3.28.0 note on the beast recipe. |
| S6 | Maxroll [Crafting Resources](https://maxroll.gg/poe/resources/crafting-resources) (undated) and [Trial of the Ancestors Meta Report 3](https://maxroll.gg/poe/news/trial-of-the-ancestors-meta-report-3) (Tenkiei, 2023-09-12) | community guide | Close to S1 in wording, so not independent of it. |
| S7 | [PoEDB](https://poedb.tw/us/Hinekoras_Lock) item page and the wiki's [Currency exchange market](https://www.poewiki.net/wiki/Currency_exchange_market) | datamined / wiki | Stack size 10, class Stackable Currency, 6,250 gold per exchange. |
| S8 | [Out of Games, Hinekora's Lock price](https://outof.games/realms/pathofexile/economy/currency/hinekoras-lock/) (poe.ninja data, hourly) | market snapshot | Price, section 5. |
| S9 | Prototype notes: `archive/prototype:docs/mechanics/beast_crafting.md` line 29, `docs/research/phase0-coverage.md` line 65 | owner's earlier notes | "Imprinting removes Hinekora's Lock foresight"; the Lock was only "catalogue-only". No model existed. |
| S10 | Craft of Exile (`sources/raw/coe/`) | coe | Has no Lock; nothing to read. |
| S11 | Reddit threads read first-hand through the Arctic Shift archive (`reddit_archive.py thread`), 2026-10-31: [16ywd1w](https://www.reddit.com/r/pathofexile/comments/16ywd1w/) "math to use hinekora's lock efficiently" (u/Bendooo, 2023-10-03, 10 comments); [170y99u](https://www.reddit.com/r/pathofexile/comments/170y99u/) "Any way to reset Hinekora's Lock on unique jewels without divining?" (u/Electrical-Cap-9925, 2023-10-06, 11 comments); [18ewhsi](https://www.reddit.com/r/pathofexile/comments/18ewhsi/) "Just dropped an Hinekora's lock!" (u/teraohmique, 2023-12-10, 13 comments); [177gbxj](https://www.reddit.com/r/pathofexile/comments/177gbxj/) "Double Corrupting Mageblood with 4x Hinekora's Lock" (u/Gustsouto, 2023-10-14, video post, body deleted) | player reports | All from the Ancestor league (3.22) and the weeks after 3.23.0; none from 3.24 to 3.29. |

**Reddit, second pass (2026-10-31, with the repaired tools).** The first pass failed (seven `gpt-research` runs timed out; reddit.com is refused in the built-in browser). In the second pass the Arctic Shift archive worked for a short time and four threads were read first-hand (S11). Then the archive answered `Too many requests` to every call for more than half an hour (about a dozen sessions share the limit), and the live GPT researcher job (`20261031-150819-9620`, terra, one brief with all eight points) stayed queued for 45 minutes behind three other sessions' jobs that held all three slots from 15:13. So the Reddit evidence below is four threads, all from the first weeks of the Lock (Oct to Dec 2023), and the other Reddit-dependent points are "not found", with the searches listed in section 3.2. The brief for the researcher is kept in section 9; the main chat can rerun it when a slot is free.

S1's one outside reference for the "does not preview" list is a YouTube video at 33:00 (`youtu.be/Z8g1068Q3QI`, at about 33 minutes; cited by S1, not opened). The "Awakener's Orb is an exception" sentence has no reference at all; S2 shows it was added by 2026-03-29 and kept through two later edits.

## 3. The rules, each with its provenance

**R1. The Lock puts an item into a foreseeing state.** The item description reads "Allows an item to foresee the result of the next Currency item used on it" and "Modifying the item in any way removes the ability to foresee". (S1, S7, S3 for the 3.23.0 item text; wiki and datamined agree.)

**R2. The preview is shown by hovering a currency over the item, and looking changes nothing.** S1: "Not applying the currency will not change the item in any way, including leaving the foreseeing state intact, thereby making it possible to check the outcomes of other currency items." So any number of currencies can be looked at on one lock.

**R3. The preview is the result.** S1: "Applying the currency will modify the item in accordance with the preview". The previewed item is what you get, including the mod rolls.

**R4. The preview is fixed per currency type.** S1: "All currency items of the same type (e.g., any given Chaos Orb) will show the same preview each time it is viewed." (An earlier wording, 2026-03-29, said "most currency items with the same name"; it was tightened to "all of the same type".) So a second hover over the same currency, or another Chaos Orb of the stack, cannot give a different result. *(Inference, not stated by any source:)* the dice are thrown once, either when the Lock goes on or when a currency is first hovered, and not again; the solver does not need to know which.

**R5. Using a currency ends the foresight and voids the other previews.** S1: "Applying the currency will modify the item in accordance with the preview, as well as remove the foreseeing state, which in turn makes the previews of all other currencies checked beforehand obsolete. This applies even if the currencies modify different aspects of the item, like sockets, explicit modifiers, quality, or enchantments." So one lock buys one applied currency. A second lock is a second purchase.

**R6. Currencies that change the item without touching its mods still end the foresight.** S1 (Strategies): "As using currencies which change an item's quality, socket number or colours, links, or implicit modifiers removes the foreseeing state, it allows for a low-risk method of rerolling other previewed outcomes." and "Re-anointing an item is the least destructive method to use up a preview on rings or amulets." So a player who dislikes every preview can spend a cheap neutral currency to drop the lock, and then lock again for a fresh set of previews. A jewel has no quality, sockets or anoint, so on a jewel no neutral currency is known.

**R7. Some crafts are not previewed, and doing one ends the foresight.** S1: "Foreseeing items cannot preview results of crafts done using the Crafting Bench, Horticrafting Station, Recombinator, beastcrafting, non-currency Betrayal Safehouse crafting benches, or preview the outcome of the Corruption Altar device in the Locus of Corruption. However, modifying the item with any of these methods (including creating an Imprint of the item), or anointing it, will remove the foreseeing state." The Altar part is official: Version 3.23.0, "Hinekora's Lock can no longer foresee the result of corrupting an item at the Altar of Corruption" (S3). Maxroll (S6) repeats the list in nearly the same words. The prototype note (S9) says an Imprint removes it, which agrees. So bench crafts, Harvest crafts, recombinators and beast crafts are "unpreviewed actions" in the model: available while the item is locked, applied blind, and they end the lock.

**R8. The Awakener's Orb is previewed, and its preview depends on the donor.** S1: "Awakener's Orb is an exception because its outcome will change based on the donor item used." One source (the wiki), no reference. Consequence for B3: each donor item is its own previewable option.

**R9. Refusals.** S1: "Hinekora's Lock cannot be used on gems or any items that are corrupted, mirrored or unmodifiable." The beast recipe that applies a Lock to a magic item "can no longer be used on Corrupted Items" since 3.28.0 (S5; the Version 3.28.0 page does not list it, so it is a wiki-only note).

**R10. Incubators do not end the foresight.** S1 currently says "Incubators do not remove the foreseeing state, and do not change the previews of other currency items." The sentence was removed on 2026-08-01 and restored the next day with the edit note "I think this is still accurate" (S2). Incubators were reworked in 3.29.0 (inventory section 4). The sentence is unconfirmed for 3.29; and incubators are not an action in any batch, so it costs nothing to leave out.

**R11. The foresight is a property of the item.** S1: "The foreseeing state is a property of the item and persists when traded." A bought start item can arrive already locked (section 7).

**R12. No change to the Lock's rules from 3.23.0 to 3.29.3b.** The scan S4 found the Lock in the notes only at 3.23.0 (the Altar change). The wiki's own version history for the Lock lists 3.22.0 (introduced), 3.23.0 (core drop pool, undocumented; the Altar change) and 3.24.0 (beast recipe, undocumented). The 3.23.0 patch notes also say "Hinekora's Locks will remain usable in Standard, but will no longer drop" (S3), which the wiki's undocumented core-drop-pool line contradicts; the 2023-12 Reddit post the wiki cites for it (u/teraohmique, "Just dropped an Hinekora's lock!", 2023-12-10, not opened) and the live market (section 5) show it drops.

**R13. Corruption by Vaal Orb was previewable in 3.22.** Maxroll, 2023-09-12 (Tenkiei): "Always lock your Headhunter/Mageblood Before Corruption!" The Altar part was removed in 3.23.0; whether a Vaal Orb is still previewed in 3.29 is not stated anywhere read. Vaal Orbs belong to the corruption batch (B4), not to B8.

### 3.1 Per currency: what a source says

"Previewed" means a source names the currency as shown by a Lock; "usable" means a source says the currency can be applied to a foreseeing item and ends the foresight (so its preview is unstated); "no statement" means nothing read mentions it.

| Currency | Status | Source |
|---|---|---|
| Chaos Orb | previewed | S1 names "any given Chaos Orb" as its example of a currency whose preview is the same each time it is viewed |
| Divine Orb | previewed | S1 Strategies ("preview the outcomes of a Divine Orb, Tailoring Orb, and Sacred Orb using the same lock"); u/pepegaklaus, 2023-10-04, thread 16ywd1w: "Now hover over with a divine." |
| Tailoring Orb, Sacred Orb | previewed | S1 Strategies, same sentence; u/pepegaklaus, 2023-10-04: "So use a sacred orb then lock again" |
| Awakener's Orb | previewed, depends on the donor | S1 (no reference) |
| Vaal Orb | previewed in 3.22; 3.29 not confirmed | S6, 2023-09-12 "Always lock your Headhunter/Mageblood Before Corruption!"; u/Bendooo, 2023-10-03, thread 16ywd1w: "what does the potential of also checking for the outcome of a vaal orb change in the equation?" (a question, not a report) |
| Whetstone, Armourer's Scrap (quality); Chromatic, Jeweller's (sockets); Orb of Fusing (links); Blessed Orb (implicits); anoint oils | usable, ends the foresight; their own preview unstated | S1 Strategies |
| Exalted, Annulment, Regal, Alchemy, Scouring, Transmutation, Alteration, Augmentation | no statement (S6 lists the Annulment, Exalted and Veiled orbs next to the Lock but says nothing about previews of them) | |
| Essences, fossils (resonators), catalysts, Eldritch ichors and embers, Orb of Conflict, Veiled orbs, Tempering Orb | no statement | |

Harvest crafts are the Horticrafting Station (R7) and are not previewed. So only Chaos, Divine, Tailoring, Sacred, Awakener's and (3.22) Vaal are named. The wiki's general rule, "the next Currency item", is the only basis for every other orb.

### 3.2 What the four Reddit threads say (S11)

- **Throwing a Lock away and locking again is what players do.** u/tuptain, 2023-10-03: "You can use another orb on it and apply a different lock for different results." u/pepegaklaus, 2023-10-04: "So use a sacred orb then lock again". This is the burn-and-relock of R6, from players.
- **The value of a Lock is the avoided loss.** u/OhHiHowIzYou, 2023-10-03: "What you really want to do is compare teh expected outcome if you don't use the lock versus if you do" (his example: a 1,000 Divine item, double-corrupt outcomes 25% each, Lock price 68 Divine); u/atlasgcx, 2023-10-03: "A lock will help you avoid a definitive loss (25% of the time)". The same idea as the toy in section 4, from players, with the Altar as the use case in 2023.
- **Price reason.** u/Veteran_But_Bad, 2023-12-10, thread 18ewhsi: the prices were absurd "because they could be used to double corrupt items safely and that is no longer the case". Locks "were added to the loot pool" (u/CondorSweep's question, 2023-12-10; u/B1ackadderr: "Yes. Check trade. Theyre trading for 2d currently."); u/orc_arn, 2023-12-10: "they are 120divs in standard". Prices have moved since (section 5).
- **A second Lock on an item: asked, not answered.** u/Munsie, 2023-10-06, thread 170y99u: "Can you use another Hinekora's Lock on it?" No reply answers it. The thread's own question is how to clear the lock on a unique jewel that no currency can be used on; the answers are "gotta divine it" (u/Sh0wTim3123) and a double-corruption altar check (u/beachteen; u/dart19: "That still won't reset the lock.").
- **Not in any thread read:** independence of previews, essences, fossils, Omens, mismatches, when the Lock is consumed. u/Bendooo posted an in-game screenshot (imgur) in thread 16ywd1w on 2023-10-03; it was not opened.

Searches run for this section: archive title search `Hinekora`, r/pathofexile, 2023-08-15 to 2023-10-15 (43 posts; the first 8,000 characters of the list read; later windows from 2023-10-07 and all windows to 2026-10-31 timed out or were rate-limited); direct reads of the four threads above (the wiki's own Reddit reference is 18ewhsi). No full-text comment search was possible.

A second live researcher job (terra, `20261031-160158-178d`, 16:02 to about 16:20, the brief of section 9) had a run slot but no shell tool: its web search answered 429, and its raw Arctic Shift requests (posts by title `Hinekora`, r/pathofexile, 2023-08-01..2023-12-31, 2023-08-15..2023-10-15, 2023-10-15..2023-12-31) all answered 429 over ten minutes with nothing opened, so I stopped it. The shared reader waits out 429s but only a session with a shell can use it; the rerun of the not-found points should run the reader from a shell session, not through the researcher.

### What the sources do not say (checked and absent)

- Whether the previews of two different currencies on one lock are **independent**. The wiki says only that each is fixed; none of the four Reddit threads read compares two previews (not found).
- Whether **essences, fossils (through a resonator), catalysts, Eldritch ichors and embers, Veiled orbs, Harvest-item currencies, Scouring or Vaal** are previewed. The wiki's rule is "the next Currency item"; the class on PoEDB is Stackable Currency. Fossils are used through a resonator and essences are Stackable Currency too, so by the class rule they should preview; no source confirms it.
- Whether an **Omen** that is active changes the preview, or is spent by hovering. Omens are not named anywhere on the page.
- Whether a second Lock can be applied to an item that is already foreseeing, and what that does (asked on Reddit by u/Munsie, 2023-10-06; no answer in the thread).
- Whether the Lock is **consumed** on use (not found in the Reddit threads either). The item is a stack of 10 that you apply ("Right click this item then left click an item to apply it"), the same shape as any currency; the wiki does not say it is consumed, the model assumes it is.
- Whether the shown result can ever differ from the applied one (no mismatch report was found; none could be searched for on Reddit).

## 4. What kind of plan this makes

Every other action in v1 is a gamble taken blind: the solver picks the action in a state, the dice are thrown, and the next state is a random draw. With the Lock the order changes. The player pays for the Lock, **the dice for every previewable currency are thrown at once and shown**, and only then the player picks: apply one of them (and get exactly that result), do something unpreviewed, or give the lock up and start again.

So the plan is a policy with a branch on information: "Lock the item; look at Chaos, Exalted, Annulment and Divine; if any of them shows a state worth at least X, use that one; otherwise burn the lock and lock again." The best reaction to each possible set of previews is computed from the values of the states the previews lead to. The preview itself cannot be fed into the existing action format `Action(label, cost, outcomes)` of the solver ([#17 interface](https://github.com/Rasslabsya4el/crafting-system/pull/37)), because there the outcome is a fixed random draw and the choice has already been made.

### A worked toy (checked by script)

One state s with two previewable currencies, A (price 1) and B (price 2), and the value of each next state already known (the cost still to pay from it): goal = 0, middle = 30, brick = 400.

| | goal | middle | brick | expected cost, no lock |
|---|---|---|---|---|
| A, price 1 | 20% | 50% | 30% | 1 + 0.5·30 + 0.3·400 = 136 |
| B, price 2 | 10% | 80% | 10% | 2 + 0.8·30 + 0.1·400 = **66** |

Without the Lock the best is B at 66. With the Lock the player sees both results first, takes the better one (if both are bad, throws the lock away at no further cost and plays B blind at 66), and the expected cost is **23.97** before paying for the Lock. So the Lock pays if its price is under 66 − 23.97 = 42.03. Looking at one currency only, B, gives 32.4, so looking at A as well is worth 8.4 more. The two numbers differ only because the second currency is looked at; section 6 returns to that.

The Lock is worth most where one outcome is a disaster: an Annulment that can remove the one good mod, an Exalt on an almost finished item. It is worth little where the gamble is cheap and repeatable.

## 5. Price and where it comes from

- **Market.** Allflame league: 100,999 Chaos Orbs, 272 Divine Orbs on the first read (271 on the main chat's re-read the same day); the page refreshes hourly (S8, poe.ninja data, read 2026-10-31). The other-league figures read at first (Hardcore Allflame 41,538, Standard 343,338, Hardcore 16,400 Chaos) did not reproduce on the re-read, so they are dropped; only the Allflame price is used. The aggregator is not the primary source; the price file ([#84](https://github.com/Rasslabsya4el/crafting-system/issues/84), ADR-0007) will carry the dated number, and the Lock needs an entry in it.
- **Trading.** It is on the Currency Exchange, 6,250 gold per item bought (S7): the highest fee on the exchange's list after the Mirror of Kalandra (25,000); the orbs the plans use cost 15 to 500 gold.
- **Other ways in.** Divination cards: The Slumbering Beast (5 cards) gives a Lock, History (5 cards) gives 2, Emperor's Luck (5 cards) gives 5 random currency items, The Void gives a random card set (S1). The beast recipe puts a Lock on a **magic** item for a Craicic Croaker and a Black Mórrigan (S1, S5); the Black Mórrigan is a rare beast from tier 14+ maps with Einhar. The beast route has no price in any source.
- **Drop.** "Can drop anywhere" (S1); no rate. The only sample on record is u/Frost__Raven, 2024-01-25, stale, from the earlier research run (inventory section 6).

At about 270 Divine Orbs the Lock is more expensive than the whole crafting budget of most routes in the reference set, so the solver will usually decline it. The owner should know that before he sees a plan with no Lock in it: that is the correct answer, not a gap.

## 6. What the solver must model, and how much larger the state gets

### 6.1 The Bellman equation

For a state s, let P(s) be the enabled previewable actions, each with its price c_a and its outcome distribution (the kernel it already has). Let L be the Lock's price. After the Lock goes on, each a in P(s) throws one outcome o_a from its kernel (assumption I: independent across a; section 7). The player then picks the cheapest of: apply some a (pay c_a, land in o_a, unlocked), or leave the lock, with value F(s). Then

V(s) = min( best plain action, L + E over (o_a) of min( min over a in P(s) of [c_a + V(o_a)], F(s) ) )

F(s) is the best way to give the lock up: an unpreviewed action (bench, Harvest, recombinator, beast craft) at its usual value, the restart by buying the start item, or burning the lock with a cheap neutral currency. If the burn leaves the compressed state unchanged (it changes only something no target and no enabled action reads: the sockets of a target that has no socket requirement, the implicit of a target that does not read it), the burn is c_burn + V(s) and V(s) appears on both sides: a self-loop whose probability is "no preview is good enough", which ADR-0010's exact self-loop elimination already handles. If the burn changes a dimension the state keeps, the burn is an ordinary unpreviewed action to the state s' it leads to, F(s) uses c_burn + V(s'), and there is no self-loop. That happens for quality when quality is a target (owner, #81: quality from catalysts is a target), for sockets and links once they are targets (B6), and for an anoint when enchants are targets (B7). A quality burn also runs out: once the item is at maximum quality the same currency can no longer be used, so burn and relock is then a finite chain of states, not a free loop. It is the sequential search the wiki calls "a low-risk method of rerolling": pay L, look, keep or burn and try again. The Lock's own price does not repeat for free: each relock pays L again.

### 6.2 The expectation without the product space

The previews of m currencies make a product of outcomes, thousands per currency. The expectation does not need it. If X_a = c_a + V(o_a) are independent, E[min(X_1..X_m, F)] is the integral of P(all X_a above t) up to F, which is the product over a of the tail P(X_a ≥ t). Sort the outcome values of all P(s) options once, sweep, and multiply the tails. The cost is O(K log K) with K the total outcomes of the previewable actions at s, against O(K) for a plain backup. The toy above was computed both by enumerating the product and by this sweep: both give 23.97.

### 6.3 What the policy looks like and how risk reads it

Given the converged values, the reaction to a set of previews is "take the option with the smallest c_a + V(o_a) if it is at most F(s), else give up". Fixed that way, the Lock action has an exact induced kernel over next states: the probability of landing in state z is a sum, over the options that can produce z as the winner, of products of tail probabilities, with ties broken by state id. ADR-0006's risk (success chance, p50, p90, CVaR on the fixed policy) can run on that kernel unchanged. The weights are exact integer products (denominators multiply: a few thousand per currency, so a few big integers per Lock state); the solver may convert to float64 once, as ADR-0010 says.

### 6.4 State size

- **No new stored state** (whether the burn stays on the same state or moves to another one, see 6.1: both are states the graph already has). The foreseeing flag is never stored: the Lock is applied and consumed inside one action (lock, look, react). The compressed state of ADR-0009 gets no new component. The previews are not state either: they are thrown inside the backup and their winner is the next state. The reachable states after a Lock are the states the previewable actions already reach, so the graph has no new nodes. **Growth of the state: none, if the previews are independent** (the best-of backup) **or if the plan looks at one currency only** (the one-look bound, true for any correlation). If the previews are tied by a shared draw and the tie is known, the exact value needs the joint draw and the sorted-tail sweep no longer applies; that case is not modelled.
- **More edges, from the Lock actions.** One Lock edge list per state where the Lock is enabled, with one edge per distinct next state of any previewable action: roughly the union of the previewable actions' successors, about K edges (the 2026-10-30 solver research uses 20 outcomes per action and up to 50 actions per state as its nominal case, so K is in the hundreds) against about K/m for one plain action. Backup work rises by the sort factor and the number of states that can lock.
- **What not to do, and its price.** Expanding the previews into explicit stored states (s, previews) is a product of the options' outcome counts: with three previewable currencies of 20 outcomes each that is 8,000 stored states per s, and a Chaos preview alone has thousands of outcomes. Expanding one currency at a time, (s, a, o_a), is K stored states per s, tens to hundreds of times the base state count. The base count is already 13,172 states for the R05 query with all 141 ring crafts told apart (#59 hand-over), and ADR-0009 measures about 1 million core states for the designs it rejected. Neither expansion is usable.
- **If previews are not independent** (assumption I fails) and are tied by a shared draw, the best-of formula overstates the Lock. A certified bound that needs no assumption is the one-look backup, L + E over o_a of min( c_a + V(o_a), F(s) ), for the one currency a that the player picks before looking. It also needs no product, only an expectation over the single kernel of a, and is true for any correlation. It is an upper bound on the true cost (toy: 32.4 against 23.97). The independent best-of is a lower bound on the true cost only if the previews are independent or positively tied (a shared draw): then the true cost lies between the two numbers. If the previews were negatively tied, the true cost would be lower still than the best-of figure; no mechanism suggests that, but no source rules it out. A report can carry both numbers.

### 6.5 What the solver interface needs

A new action kind, alongside `Action`: a `Peek` with the Lock's price, the list of options (label, price, outcomes) and the fallback F; its Bellman backup is the sorted-tail sweep above; its policy output is the induced kernel (and the ranking, for the route view). ADR-0010's component solver already iterates a backup to a fixed point per component, so a monotone, non-linear backup fits value iteration. Policy iteration needs the induced kernel recomputed from V at each iteration, which is what 6.3 gives. A policy that never accepts any preview would burn and lock again forever; the proper-policy check (Prob1E) has to see that as improper, and it does so as soon as some preview has positive probability of being accepted. How the backup plugs into the solver is for the B8 grill, not for now.

### 6.6 What the other modules see

- **Actions / rules.** Each previewable action needs a `previewable` flag in the registry, so an in-game finding can switch off one currency without changing the model. Unpreviewed actions (R7) need the opposite flag.
- **Items and abstraction.** The compressed state already decides the value of a result; the preview shows the exact roll values but the decision depends only on the compressed state of the result, which is an exact lumping (ADR-0009). So a Divine preview reduces to "passes the roll threshold or not". No new state field.
- **Route view and reports ([#78](https://github.com/Rasslabsya4el/crafting-system/issues/78)).** A Lock step is a decision on what the preview shows: "Lock, then hover Chaos / Exalted / Annulment; use the one whose result is a state on this list; if none is, burn the lock with <cheap currency> and lock again". The report has to print the acceptable result states, not just a currency.
- **Prices.** The Lock and each neutral burn currency need entries in the price file.
- **Awakener's Orb (B3).** One option per donor item; the donor is a second input, so it arrives with the branching solver.

## 7. Open points

1. **Independence of previews across currencies.** Not stated, not contradicted. It decides whether the best-of backup is exact.
2. **Which currencies preview.** The wiki rule is every currency item with the listed exceptions. Only the orbs the page names (Divine, Tailoring, Sacred, Chaos, Awakener's) are sourced; the plain orbs rest on the general rule alone. Essences, fossils through a resonator, catalysts, Eldritch currency and Veiled orbs are by class only.
3. **Omens.** If an Omen changes what a currency does, its preview is a different option from the plain currency, and its draw could be the same draw (correlated) or a separate one. Unknown whether hovering spends it.
4. **A second Lock on a foreseeing item.** If it re-throws the dice it is a burn-and-relock in one purchase; if it is refused, burning needs the neutral currency.
5. **No neutral currency on jewels.** Without one, a jewel with a disappointing preview has no way to throw the lock away except an unpreviewed action or buying a new start item.
6. **Locked start items.** A bought item can already be foreseeing (R11). v1 can treat a start item as not locked.
7. **The beast route** puts a Lock on a magic item only; useful only for Regal, Alteration, Augmentation and Transmutation previews. No price for the beast.
8. **Incubator sentence** (R10) is in dispute on the wiki and irrelevant to v1.
9. **Whether the Lock is a better buy than the plan it replaces** depends on the Lock's price at plan time; the price file must date it.

## 8. Questions for the owner

Each stands alone. The main chat asks them; none is asked from here.

**Q1. May the planner treat the previews of different currencies on one Lock as independent?** Context: a Lock shows the result of every currency at once, and the planner picks the best. If the game draws them with one shared random number, the results are tied together and the real gain is smaller than the planner says. No source says either way; checking in game needs a Lock, about 270 Divine Orbs. Options: (A) yes, admit it as the owner's rule; every route that uses several previews prints the safe "one look" number next to it; (B) no, build only the one-currency look, which needs no assumption; (C) test it in game first. Recommendation: **A**. The report shows both numbers: the one-look number is a certified ceiling on the cost for any tie between previews, and the best-of number is the floor if the previews are independent or positively tied. Only a negative tie would put the truth below the floor, which nothing suggests. B alone would hide the main reason to own a Lock (choosing between currencies).

What would settle it, and what it costs. The test is to compare two previews of two currencies that draw from the same pool on the same item, and see whether they pick the same mod. On a magic item with one mod, Augmentation and Regal both add one mod from the same pool, so the two previews of one Lock name the mod each would add. If the game used one shared draw, they would name the same mod every time; if the draws are independent they name the same mod only with the probability that two independent picks coincide, of the order of 5 to 10% for a pool of this size (to be computed from the real pool before the test). Three Locks that all match leave between 0.01% and 0.1% for independence (at 5 to 10% per Lock), four between 0.0006% and 0.01%; one Lock that does not match already refutes a shared draw. So 3 to 4 Locks decide it, which is about 800 to 1,100 Divine Orbs on the market. The cheaper route is the beast recipe that puts a Lock on a **magic** item (a Craicic Croaker and a Black Mórrigan, section 5): it needs no market Lock and can test Alteration, Augmentation, Regal and Transmutation previews against each other. It cannot test Chaos, Exalted or Annulment previews on a rare item, so it settles the shared-draw question for the magic-item orbs only; the beast prices are not in any source.

**Q2. Which currencies are shown as previewable in v1?** Context: the wiki says every currency item except the listed crafts; only the orbs are named. Options: (A) all currency-item actions except the listed ones; (B) only the currencies a source names as previewed (Chaos, Divine, Tailoring, Sacred, Awakener's; section 3.1) plus the plain orbs the wiki's "next Currency item" rule covers (Transmutation, Alteration, Augmentation, Regal, Alchemy, Exalted, Annulment, Scouring); essences, fossils, catalysts, Eldritch currency and Omen-modified uses stay blind until a source or a player check shows them. Property of B: it treats Exalted, Annulment, Regal, Alchemy, Scouring, Transmutation, Alteration and Augmentation as previewed although no source names them (section 3.1: "no statement"); it rests only on the wiki's general rule, "the next Currency item". If that rule fails for one of them, B overvalues the Lock for the routes that lean on that orb. A third option is (C) only the five currencies a source names (Chaos, Divine, Tailoring, Sacred, Awakener's), which cannot overvalue but leaves out Annulment and Exalted, the orbs a Lock is most worth having for, so it would make the Lock almost never appear in a plan. Recommendation: **B**, with two safeguards: a `previewable` flag per action, each marked "named by a source" or "by the general rule", and every report that uses a Lock step lists the currencies it assumed previewed and which of them rest on the general rule only. I do not recommend A: essences and fossils are used through a different mechanism (the essence's own reforge, the resonator), and nothing read shows that a preview covers them.

**Q3. May a plan throw a Lock away and lock again?** Context: the wiki lists spending a cheap quality, socket, link, implicit or anoint currency as the way to get fresh previews. It costs a second Lock each time, about 270 Divine Orbs, so in practice a plan would do it only for a cheap item; when the burn changes quality or sockets that the state keeps, it is a move to another state, not a loop (section 6.1). Options: (A) yes, as a plan step with the cheapest neutral currency priced from the price file; (B) no, one Lock per item, the previews are taken or the Lock is wasted. Recommendation: **A**. It is what the wiki says players do, it is a plain self-loop for the solver, and B understates the search the Lock allows.

## 9. The Reddit brief to rerun

Path of Exile 1, Hinekora's Lock. Find Reddit threads (r/pathofexile, r/PathOfExileCrafting) or GGG forum posts with player reports on: which currencies it previews (Chaos, Exalted, Annulment, Divine, Vaal, essences, fossils and resonators, Awakener's, Omens active); whether the preview equals the result, any mismatch; whether the previews of different currencies on one Lock are independent or tied (same random draw); what removes the foresight; price and strategies in 2025–2026. URL, author, date and a short quote per claim; "not found" is allowed.

## 10. Draft claims for `src/crafting_system/rules/claims/hinekora_lock.yaml`

Patch field "3.29.3.3": the live wiki page (last edit 2026-08-02) and the scan of every version page to 3.29.3b show no later change. The claims that rest on the wiki alone say so in `statement`.

```yaml
# Mechanic family: hinekora_lock (Hinekora's Lock, inventory row M-80, batch B8). Research ticket #101.
# Not admitted until the owner answers Q1 and Q2 of the resolution: the independence of previews across
# currencies, and which currencies other than the plain orbs preview (hinekora_lock.preview_independent_across_currencies
# and hinekora_lock.preview_covers_all_currency_items are deliberately NOT in this file).
rules:
  - id: hinekora_lock.foresees_next_currency
    statement: A Hinekora's Lock puts an item into a foreseeing state in which the result of the next currency item used on it can be previewed; any modification of the item removes the state.
    source_kind: datamined
    url: https://poedb.tw/us/Hinekoras_Lock
    quote: "Allows an item to foresee the result of the next Currency item used on it"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.looking_changes_nothing
    statement: Hovering a currency over a foreseeing item shows its preview and changes nothing, so any number of currencies can be looked at on one Lock.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "Not applying the currency will not change the item in any way, including leaving the foreseeing state intact"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.preview_fixed_per_currency_type
    statement: All currency items of one type show the same preview each time it is viewed, so the result of a currency on a foreseeing item is decided before it is used and cannot change by looking again.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "All currency items of the same type (e.g., any given Chaos Orb) will show the same preview each time it is viewed."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.applied_result_is_the_preview
    statement: Using a previewed currency makes the item exactly what the preview showed (mods and rolls), and removes the foreseeing state.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "Applying the currency will modify the item in accordance with the preview, as well as remove the foreseeing state"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.one_applied_currency_voids_other_previews
    statement: After a currency is applied, the previews of every other currency looked at before are obsolete, even when the currency changes a different aspect of the item (sockets, quality, enchantments). One Lock buys one applied currency.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "makes the previews of all other currencies checked beforehand obsolete"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.neutral_currency_removes_foresight
    statement: Changing the item's quality, socket number or colours, links or implicit modifiers, or anointing it, removes the foreseeing state; this is the way to discard a Lock whose previews are unwanted.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Strategies
    quote: "using currencies which change an item's quality, socket number or colours, links, or implicit modifiers removes the foreseeing state"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.unpreviewed_crafts_remove_foresight
    statement: The Crafting Bench, Horticrafting Station (Harvest crafts), Recombinator, beastcrafting (including Imprint), non-currency Betrayal benches and the Corruption Altar of the Locus of Corruption are not previewed; doing any of them (or anointing) removes the foreseeing state.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "modifying the item with any of these methods (including creating an Imprint of the item), or anointing it, will remove the foreseeing state"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.altar_of_corruption_not_foreseen
    statement: Since 3.23.0 the Lock no longer foresees the result of corrupting an item at the Altar of Corruption.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.23.0
    quote: "Hinekora's Lock can no longer foresee the result of corrupting an item at the Altar of Corruption."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.awakener_preview_depends_on_donor
    statement: The Awakener's Orb is previewed and its preview depends on the donor item used (wiki only, no reference).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "Awakener's Orb is an exception because its outcome will change based on the donor item used."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.refused_on
    statement: A Hinekora's Lock cannot be used on gems or on corrupted, mirrored or unmodifiable items.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "Hinekora's Lock cannot be used on gems or any items that are corrupted, mirrored or unmodifiable."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.stack_of_ten
    statement: The Lock is a stackable currency with a stack size of 10; its price comes from the dated price file, not from this registry.
    source_kind: datamined
    url: https://poedb.tw/us/Hinekoras_Lock
    quote: "Stack Size: 1 / 10"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.tradeable_on_currency_exchange
    statement: The Lock can be bought on the Currency Exchange (gold fee 6,250 per item), so a market price exists for it.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Currency_exchange_market#Gold_costs
    quote: "Hinekora's lock	6,250"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.chaos_orb_previewed
    statement: A Lock previews the Chaos Orb (the wiki's own example of a currency whose preview is the same each time it is viewed). The rest of the currency items are previewed only if the owner admits the general rule (Q2).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Mechanics
    quote: "All currency items of the same type (e.g., any given Chaos Orb) will show the same preview each time it is viewed."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: hinekora_lock.divine_tailoring_sacred_previewed
    statement: A Lock previews the Divine Orb, the Tailoring Orb and the Sacred Orb (the wiki's example of one lock previewing several currencies).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Hinekora%27s_Lock#Strategies
    quote: "preview the outcomes of a Divine Orb, Tailoring Orb, and Sacred Orb using the same lock"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```
