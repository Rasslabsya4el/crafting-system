# Memory Strands in Path of Exile 1, Patch 3.29

**Research date:** 2026-10-30  
**Scope note:** I reviewed the primary post body, all three embedded tables, its linked Google Sheet, its linked PoE2 recombinator post, and the 74 comments exposed by Reddit's RSS feed. Reddit's server-rendered page reported 78 comments, so four comments were unavailable through the accessible RSS snapshot. The requested PoE Wiki page was blocked by its anti-bot challenge in this environment; its supplied formula is nevertheless reproduced verbatim below and compared to the primary post. Current structured item/cost data was accessible through [PoEDB's Memory Strands page](https://poedb.tw/us/Memory_Strands).

**Evidence classes used below:**
- **Primary author experiment:** Macookta's measurements and conclusions. These are not GGG-confirmed mechanics.
- **Structured item/cost data:** current PoEDB extraction of client/game data, useful for listed strand-cost ranges and currency descriptions.
- **Community report/speculation:** a player statement, explicitly labelled as such.
- **Official/GGG:** no direct GGG statement or staff reply was found in the accessible primary-thread material.

## 1. Author, date, patch, and later edits

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27, title | `"[3.29] Everything you need to know about memory strands"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"Some testing turned into a lot of testing, and I collected data from 18285 regular currency items used on items with strands, 9373 orbs of unravelling, and 2255 orbs of remembrance"` |
| [Primary-post update](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, edit dated 2026-09-27 | `"Edit 9/27: thanks to @nerdyjoe on the Prohibited Library discord for pointing out the cleaner explanation for the tier picked to upgrade to"` |
| [Primary-post update](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, edit dated 2026-09-27 | `"I had originally said that the weights are scaled by a multiplier applied to make lower tiers more likely. (1 for the highest tier, 2 for the second, 3 for the third, etc.)"` |
| [Primary-post update](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, edit dated 2026-09-27 | `"He pointed out that it's more likely that the effective weight for each mod is the sum of its weight and the weight of the tiers above."` |

**What changed in the edit:**
- The edit did **not** change the `rollable_tiers` formula.
- It replaced the author's original explanation for the destination tier after an Orb of Unravelling upgrade.
- Original model: assign a multiplier `1, 2, 3, ...` from highest eligible tier downward.
- Replacement model: each possible destination tier's effective weight is its own weight plus all higher eligible-tier weights.
- The author says the two models are equivalent when candidate tiers have uniform weights, and that the available data was insufficient to distinguish them confidently: `"the probabilities are so close that it would take quite a bit more data to be sure."`

**What it says:** The post was written by `/u/Macookta`, published on 2026-09-27 for patch 3.29; its only stated edit corrected the proposed **Orb of Unravelling destination-tier weighting explanation**, not the ordinary Memory Strand tier-culling formula.

## 2. What Memory Strands are, where they occur, how they are obtained, and the post's discovery

### Item source and amount

| Evidence | Passage |
|---|---|
| [PoEDB: Memory Strands](https://poedb.tw/us/Memory_Strands) — structured current game-data/community page, accessed 2026-10-30 | `"Items in Memory Influenced Maps can drop with Memory Strands. And will have a random amount up to 100."` |
| [PoEDB: Memory Strands](https://poedb.tw/us/Memory_Strands) — structured current game-data/community page, accessed 2026-10-30 | `"After defeating all three new pinnacle bosses, you’ll be able to find new Memory Influenced tier 16 maps."` |
| [PoEDB: Orb of Remembrance](https://poedb.tw/us/Orb_of_Remembrance) — item description, accessed 2026-10-30 | `"Randomises the number of Memory Strands on a normal equipment item"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"For identifying items with memory strands and using crafting methods which consume strands, the available tiers for each mod are restricted"` |
| [Author comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pccwv03/) — `/u/Macookta`, 2026-09-27 | `"I didn't do a ton with identifying items, but I also think it follows exactly the same rules."` |

### How they are gained or set

- **Found on equipment:** The accessible structured description says equipment in Memory Influenced Maps can drop with a random amount, up to 100.
- **Rerolled on a normal equipment item:** An Orb of Remembrance randomises the strand count. Its item text says it applies to a **normal equipment item**.
- **Atlas support:** [PoEDB: Memory Strands](https://poedb.tw/us/Memory_Strands) lists `Grasp the Past`: `"The number of Memory Strands on Equipment Items found in your Maps has 50% chance to be Lucky."`
- **Not established by the post:** Macookta did not claim a controlled, large identification/drop experiment. The identification statement is expressly tentative.

### The post's principal discovery

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"lower modifier tiers didn't seem to be possible to roll even at fairly low strand numbers"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"For a particular modifier, the number of rollable tiers is described by the formula"` |
| [Author comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcd1vqn/) — `/u/Macookta`, 2026-09-27 | `"This was the most surprising to me! ... I expected the effect to be weak at lower amounts"` |
| [Author comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcd1vqn/) — `/u/Macookta`, 2026-09-27 | `"I rolled pretty aggressively for 50+ strands on most crafts."` |

The new result is not merely that strands “improve” crafting. The post proposes that strand count creates a deterministic **eligible-tier floor for each modifier**, often excluding low tiers at surprisingly small counts. It separately proposes an Orb of Unravelling probability/destination-tier model based on modifier-pool weights.

**Conditions attached by the author:**
- The tier rule is evaluated **per modifier**.
- A modifier's own total number of tiers matters.
- The evidence includes ordinary crafting, identification observations, Foulborn Augment/Regal tests, and Orb of Unravelling tests; not every mechanic received the same level of testing.
- Identification behavior was not tested as extensively as the ordinary currency/Unravelling behavior.

**What it says:** Memory Strands are a random, up-to-100 item property found on equipment from Memory Influenced Maps or rerolled onto normal equipment with an Orb of Remembrance; the post's core discovery is that they sharply cull low modifier tiers on strand-interacting rolls, rather than supplying only a vague “better modifier” bonus.

## 3. Crafting actions affected, and strand consumption

### Interpreting the cost ranges

[PoEDB's Memory Strands cost table](https://poedb.tw/us/Memory_Strands) labels its values as `Cost /130` and gives a range for each listed currency. A range establishes that the cost is variable within that listed interval; the accessible material does **not** establish a uniform distribution, an exact roll algorithm, or whether every integer is equally likely.

The primary post tests the resulting tier-selection behavior, not a per-currency cost-distribution formula.

| Action | Does accessible structured data list it as strand-interacting? | Listed strand cost per use | Conditions and evidence |
|---|---:|---:|---|
| Chaos Orb | Yes | `0-50` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Chaos Orb 0-50`. |
| Exalted Orb | Yes | `0-16` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Exalted Orb 0-16`. |
| Regal Orb | Yes | `0-16` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Regal Orb 0-16`. |
| Orb of Alchemy | Yes | `0-50` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Orb of Alchemy 0-50`. |
| Orb of Augmentation | Yes | `0-8` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Orb of Augmentation 0-8`. |
| Orb of Alteration | Yes | `0-8` | [PoEDB cost table](https://poedb.tw/us/Memory_Strands) lists `Orb of Alteration 0-8`. |
| Essences | Yes | `0-80` | Every Essence entry visible in the structured list is `0-80`, including basic, Deafening, corruption, and special Essences. |
| Harvest reforges | No decisive structured listing found | Not found | Conflicting player reports exist; see below. |
| Fossils | No decisive structured listing found | Not found | Conflicting player reports exist; see below. |
| Crafting Bench, including “Reroll” options | No decisive structured listing found | Not found | No primary-post test or authoritative current cost entry found for the generic bench/Reroll category. Do not infer a number from a normal currency's range. |
| Fracturing Orb | Not in the strand cost table | Not found | The [Fracturing Orb description](https://poedb.tw/us/Fracturing_Orb) says it fractures a random modifier on a 4+ modifier rare item, but the accessible sources provide no direct statement that it spends strands. Its absence from the strand-cost table is evidence against a listed cost, not a proof of every interaction edge case. |
| Foulborn Orb of Augmentation | Yes | `0-32` | Listed in the [cost table](https://poedb.tw/us/Memory_Strands); separately tested by Macookta for its tier bias. |
| Foulborn Regal Orb | Yes | `0-48` | Listed in the [cost table](https://poedb.tw/us/Memory_Strands); separately tested by Macookta for its tier bias. |
| Foulborn Exalted Orb | Yes | `0-28` | Listed in the [cost table](https://poedb.tw/us/Memory_Strands). The post's specific equivalence testing covers Foulborn Augment and Regal, not Foulborn Exalted. |
| Orb of Remembrance | It changes the strand count itself | No listed “spend” range | It randomises the number of strands on a **normal equipment item**; it is not described as a craft that spends a listed amount of existing strands. |
| Orb of Unravelling | It consumes the entire existing amount | **All strands on the item** | Not named in the question's action list, but central to the post. See its explicit item text below. |

### Explicit Orb of Unravelling and Orb of Remembrance behavior

| Evidence | Passage |
|---|---|
| [PoEDB: Orb of Unravelling](https://poedb.tw/us/Orb_of_Unravelling) — item description, accessed 2026-10-30 | `"Consumes all Memory Strands on an item to attempt to upgrade the tier of explicit modifiers based on the number of Memory Strands consumed"` |
| [PoEDB: Orb of Remembrance](https://poedb.tw/us/Orb_of_Remembrance) — item description, accessed 2026-10-30 | `"Randomises the number of Memory Strands on a normal equipment item"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"Once I had the base strand mechanics mapped out, I wanted to see if I could figure out how orbs of unravelling work."` |

### Foulborn currency

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"From testing foulborn augments and regals on both sides of some of these breakpoints, I believe using foulborn currency on an item with memory strands does indeed just add 75 to the value in the denominator of the formula"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"acting as if the item had 30 extra strands."` |
| [PoEDB: Foulborn Orb of Augmentation](https://poedb.tw/us/Foulborn_Orb_of_Augmentation) — item description, accessed 2026-10-30 | `"Augments a magic item with a new random modifier with higher level modifiers being more likely"` |
| [PoEDB: Foulborn Regal Orb](https://poedb.tw/us/Foulborn_Regal_Orb) — item description, accessed 2026-10-30 | `"Upgrades a magic item to a rare item with higher level modifiers being more likely"` |
| [PoEDB: Foulborn Exalted Orb](https://poedb.tw/us/Foulborn_Exalted_Orb) — item description, accessed 2026-10-30 | `"Augments a rare item with a new random modifier with higher level modifiers being more likely"` |

The author labels the Foulborn conclusion `"I believe"` and reports tests only for Foulborn Augment and Regal. It should not be expanded into a proven formula for every Foulborn currency without further evidence.

### Community evidence and disagreement about Essences, Harvest, Fossils, and reforges

| Evidence | Passage |
|---|---|
| [Discussion post](https://www.reddit.com/r/pathofexile/comments/1lg6y7c/memory_strand_crafting/) — `/u/HockeyHocki`, 2025-06-20 | `"In SSF i typically need to spam essences to eventually get decent gear but that immediately eats the memory strand on the first try"` |
| [Same discussion post](https://www.reddit.com/r/pathofexile/comments/1lg6y7c/memory_strand_crafting/) — `/u/HockeyHocki`, 2025-06-20 | `"Harvest and delve dont"` |
| [Primary-thread comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcdz8wr/) — `/u/Hreaty`, 2026-09-27 | `"spam alterations/essences/fossils/reforges a million times until you get Y" step(s) that would consume all threads` |
| [Primary-thread comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcfglsz/) — `/u/lolfail9001`, 2026-09-27 | `"boat essence a high strand base and basically get a mostly complete item"` |
| [Primary-thread reply](https://www.reddit.com/r/pathofexile/comments/1lg6y7c/memory_strand_crafting/myu6f1f/) — `/u/PersonalityFar4436`, 2025-06-20 | `"Any evasion item with memory i Just thrown a life essence,most time It hit supress or good res on suffix"` |

**Disagreement:**
- `/u/HockeyHocki` reports that Essences consume the strand supply immediately but that `"Harvest and delve dont"`.
- `/u/Hreaty` says the commonly repeated `"alterations/essences/fossils/reforges"` steps consume all strands.
- Neither comment supplies controlled counts, an exact currency-cost range, or a GGG citation.
- The structured cost list corroborates that Essences can spend `0-80`, but it does not settle the Harvest/Fossil/bench-reforge dispute.

**What it says:** Ordinary listed currencies spend a variable documented range of strands, with the requested values shown above; Essences are listed at `0-80`; Foulborn Augment/Regal appear to add a tier-quality bias equivalent to 30 strands in the author's tests; an Orb of Unravelling spends all strands; and Harvest, Fossils, and generic bench Rerolls do not have a single reliably evidenced answer in the reviewed material.

## 4. Exact tier rule, formulas, and every primary-post table

### Ordinary tier eligibility

The post states that Memory Strands restrict **which tiers are eligible** for each modifier. It does not claim a new normal-roll weighting formula among otherwise eligible tiers.

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"For identifying items with memory strands and using crafting methods which consume strands, the available tiers for each mod are restricted using something similar to the Modifier Tier Rating system."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"The main difference between what I saw with strands and how MTR is described on the wiki is with rounding and the behavior when the value from the formula lies exactly on a tier boundary."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I'm not sure whether that means strands don't use MTR or we were slightly mistaken about the exact MTR mechanics back in Necropolis"` |

The formula reproduced in the post is exactly:

```text
rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1
```

The post's worked example is exactly:

```text
rollable_tiers = floor((100/(2.5 * 82 + 147.5)) * (8 - 1)) + 1 = floor((100/352.5) * 7) + 1 = 2
```

The author explains the result as:

> `"which means only T2 and T1 of this modifier are allowed to roll."`

### Strand breakpoints table

The post defines the table as:

> `"Each column header is the total number of tiers for the modifier, and the numbers in the cells are the lowest mod tier that can roll at that number of strands."`

| Strands | 13 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 13 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |
| 1 | 9 | 8 | 7 | 7 | 6 | 5 | 5 | 4 | 3 | 3 | 2 | 1 |
| 2 | 8 | - | - | 6 | - | - | 4 | - | - | 2 | - | - |
| 4 | - | 7 | - | - | - | - | - | - | - | - | - | - |
| 6 | - | - | - | - | 5 | - | - | - | - | - | - | - |
| 8 | - | - | 6 | - | - | - | - | 3 | - | - | - | - |
| 10 | 7 | - | - | - | - | - | - | - | - | - | - | - |
| 12 | - | - | - | - | - | 4 | - | - | - | - | - | - |
| 14 | - | - | - | 5 | - | - | - | - | - | - | - | - |
| 15 | - | 6 | - | - | - | - | - | - | - | - | - | - |
| 22 | 6 | - | 5 | - | 4 | - | 3 | - | 2 | - | 1 | - |
| 30 | - | 5 | - | - | - | - | - | - | - | - | - | - |
| 32 | - | - | - | 4 | - | - | - | - | - | - | - | - |
| 35 | - | - | - | - | - | 3 | - | - | - | - | - | - |
| 38 | 5 | - | - | - | - | - | - | - | - | - | - | - |
| 42 | - | - | 4 | - | - | - | - | 2 | - | - | - | - |
| 48 | - | - | - | - | 3 | - | - | - | - | - | - | - |
| 52 | - | 4 | - | - | - | - | - | - | - | - | - | - |
| 62 | 4 | - | - | 3 | - | - | 2 | - | - | 1 | - | - |
| 75 | - | - | 3 | - | - | - | - | - | - | - | - | - |
| 82 | - | - | - | - | - | 2 | - | - | - | - | - | - |
| 88 | - | 3 | - | - | - | - | - | - | - | - | - | - |
| 102 | 3 | - | - | - | 2 | - | - | - | 1 | - | - | - |
| 122 | - | - | - | 2 | - | - | - | - | - | - | - | - |

The post's explanatory text:

> `"For example, even at 1 strand, a mod with 13 total tiers can't roll tiers 10-13. At 62 strands, tiers 5-13 can't roll."`

### Foulborn tier-equivalence claim

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I noticed that the tier restricting behavior of foulborn currency exactly matched that of 10-11 memory strands, and 11 strands maps to a nice MTR number of 75."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I believe using foulborn currency on an item with memory strands does indeed just add 75 to the value in the denominator of the formula"` |

The claimed substitution is therefore:

```text
2.5 * strands + 147.5
```

becoming effectively:

```text
2.5 * strands + 147.5 + 75
```

This is equivalent to adding 30 strands because `75 / 2.5 = 30`. That algebraic restatement is implied by the author's `"acting as if the item had 30 extra strands"` wording; it remains an experimental conclusion, not an official formula.

### Orb of Unravelling: proposed chance formula and tier-selection rule

The post's exact proposed chance formula:

```text
upgrade_chance = (strands * total_upgrade_candidate_weight)/(2 * total_side_weight)
(total_upgrade_candidate_weight = sum of the weights of higher tiers of this modifier)
(total_side_weight = total mod weight for all mods on this side of the item (prefix or suffix))
```

The author’s asserted mechanics:

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"Each modifier on the item is calculated independently. Having multiple upgradable modifiers does not hurt the chances for an individual modifier to upgrade."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"The number of memory strands only determines the chance for a modifier to upgrade vs. not upgrade. The number of tiers upgraded is not affected by the number of strands."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"When a modifier is upgraded, the new tier is chosen by assigning each tier a weight consisting of the sum of its own weight and the eligible tiers above it."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"This makes lower tier modifiers much more likely to be chosen, and when the weights are uniform the ratio ends up being 1:2:3:4:etc, starting at the highest tier."` |

### Orb of Unravelling example

The post gives this T9 attribute-modifier example on an item-level 86 amulet:

```text
(32 * 8000)/(2 * 125250) = 1.02
```

The author concludes:

> `"so the upgrade should be guaranteed."`

Reported samples:

- At 32 strands: `310/310` T9 attribute modifiers upgraded at least one tier.
- At 31 strands: predicted 99%; `14/15` upgraded.
- At 15 strands: predicted 47.9%; `63/150 = 42%` upgraded.

### Upgrade-result table: T9 modifiers with at least one upgrade

| Final Tier | Expected | Observed |
|---:|---:|---:|
| 1 | 2.78% | 43/1611 = 2.67% |
| 2 | 5.56% | 88/1611 = 5.46% |
| 3 | 8.33% | 124/1611 = 7.70% |
| 4 | 11.11% | 166/1611 = 10.30% |
| 5 | 13.89% | 220/1611 = 13.66% |
| 6 | 16.67% | 275/1611 = 17.07% |
| 7 | 19.44% | 332/1611 = 20.61% |
| 8 | 22.22% | 363/1611 = 22.53% |

```text
(chi-squared 3.233, p=0.8627, difference not statistically significant)
```

### Upgrade-result table: T4 modifiers

| Final Tier | Expected | Observed |
|---:|---:|---:|
| 1 | 16.67% | 639/3825 = 16.71% |
| 2 | 33.33% | 1308/3825 = 34.20% |
| 3 | 50% | 1878/3825 = 49.10% |

```text
(chi-squared 1.480, p=0.4771, difference not statistically significant)
```

### Does the post confirm, correct, or replace the supplied wiki formula?

**It reproduces the supplied formula exactly. It does not replace it.**

- The primary post prints exactly:

  ```text
  rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1
  ```

- The post **qualifies/corrects the interpretation of the linked Modifier Tier Rating description**, specifically rounding and exact-boundary behavior.
- It does **not** present an alternate `rollable_tiers` equation.
- Its 9/27 correction concerns the **post-upgrade tier weighting for Orbs of Unravelling**, not normal rollable-tier eligibility.

**What it says:** The post confirms the supplied `rollable_tiers` formula verbatim, while warning that its observed strand behavior differs from the linked MTR description at rounding and exact tier boundaries; it separately proposes, rather than proves, a modifier-weight-based formula for Orb of Unravelling upgrades.

## 5. Method, evidence type, sample sizes, and confidence

### Evidence type

This is player-run in-game experimental work, not a GGG statement and not a direct datamine.

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"For the basic strand testing, I started out using transmutes with allflame crafting and manually recording the results."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"This was done with an AHK script that captured the before and after ctrl-C data to a file when I clicked currency. (Don't worry, all the rolling was still fully manual)."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I used a Python script to process the captured data, mainly leaning on pandas for the analysis."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"Once I managed to roll a talisman to 100 memory strands with orbs of remembrance, I could imprint as a checkpoint and make any combination of strands and mods I wanted from there."` |
| [Linked raw data spreadsheet](https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/) — linked by `/u/Macookta`, 2026-09-27 | The sheet contains raw before/after strand and modifier-tier observations; format varies by experiment, as the author warns. |

### Sample sizes

| Test family | Sample size stated by author | Notes |
|---|---:|---|
| Regular currency used on stranded items | 18,285 currency uses | Used for ordinary strand/tier behavior. |
| Orb of Unravelling | 9,373 orbs | The author also states this covers 36,598 total modifiers. |
| Orb of Remembrance | 2,255 orbs | Presented as a histogram using five-strand buckets; the source has an image rather than a numeric table. |
| Guaranteed-point check | 36,598 modifiers | No case where the author's formula predicted guaranteed upgrading but the modifier did not upgrade. |
| T9, 32-strand check | 310 Unravellings | 310/310 upgraded at least one tier. |
| T9, 31-strand check | 15 Unravellings | 14/15 upgraded. |
| T9, 15-strand check | 150 Unravellings | 63/150 upgraded. |
| T9 destination-tier table | 1,611 upgraded modifiers | Table reproduced above. |
| T4 destination-tier table | 3,825 upgraded modifiers | Table reproduced above. |

### Confidence and limitations stated by the author

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I'm not 100% confident the chance scales linearly"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I am confident in the breakpoints where the chance is guaranteed"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I don't have any instances where the formula predicts a guaranteed upgrade and the mod didn't upgrade."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"The correlation coefficient between the predicted upgrade chance and whether each mod actually upgraded is 0.796"` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I'm not confident enough with statistics to claim this is the only viable explanation."` |
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"It's entirely possible that I'm wrong about any part of this, so please do poke holes if something looks suspicious."` |

### Linked “predictable recombinator” source

The primary post links [Butsicles' PoE2 recombinator guide](https://www.reddit.com/r/PathOfExile2/comments/1jzu2py/poe_2_patch_020_guide_to_recombinators_part_1/), not as an official source, but because Macookta observed a structural similarity in the use of modifier weights.

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"This tracks closely with predictable recombinator mechanics."` |
| [Primary-thread comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcb2l1o/) — `/u/Butsicles`, 2026-09-27 | `"I did have some initial data connecting the unraveling mechanism to the predictable recombinator connection ... but it was only around 30-40 datapoints"` |
| [Author reply](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pccvrk8/) — `/u/Macookta`, 2026-09-27 | `"Glad for some confirmation on the link to predictable recombination"` |
| [Linked PoE2 guide](https://www.reddit.com/r/PathOfExile2/comments/1jzu2py/poe_2_patch_020_guide_to_recombinators_part_1/) — `/u/Butsicles`, 2025-04-15 | `"The recombination formula for two-mod combines has been figured out. Does not immediately extrapolate to recombinations involving 3 or more modifiers."` |

**What it says:** The report is a large in-game, manually rolled and scripted-data-capture experiment with raw data published by its author; it reports strong breakpoint evidence but explicitly does not claim an official statement, a datamine, or a uniquely proven linear probability model.

## 6. Remaining unknowns, corrections, contrary data, and GGG replies

### Author-identified unknowns and limitations

| Evidence | Passage |
|---|---|
| [Primary post](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, 2026-09-27 | `"I'm not sure whether that means strands don't use MTR or we were slightly mistaken about the exact MTR mechanics back in Necropolis"` |
| [Author comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pccwv03/) — `/u/Macookta`, 2026-09-27 | `"I didn't do a ton with identifying items, but I also think it follows exactly the same rules."` |
| [Primary-post update](https://www.reddit.com/r/pathofexile/comments/1wr9445/329_everything_you_need_to_know_about_memory/) — `/u/Macookta`, edit dated 2026-09-27 | `"the probabilities are so close that it would take quite a bit more data to be sure"` |
| [Author comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcd144t/) — `/u/Macookta`, 2026-09-27 | `"you can't get 100% chance to unravel most T2 mods, and unravelling a T3 to a T1 will be 1/3 at best."` |

The unresolved points are:
- Whether Memory Strands literally use MTR internally, versus a similar mechanism with different rounding/boundary handling.
- The precise identification/drop behavior, which the author believes follows the same rule but did not extensively test.
- Whether the proposed linear upgrade chance is the unique or exact model.
- How to distinguish the original multiplier model from the corrected cumulative-weight model with non-uniform candidate weights.
- Which non-currency craft systems interact with strands and how much they spend.

### Corrections and additional data from commenters

| Commenter, date, URL | Passage | Status |
|---|---|---|
| `/u/Butsicles`, 2026-09-27, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcb2l1o/) | `"I did have some initial data connecting the unraveling mechanism to the predictable recombinator connection ... but it was only around 30-40 datapoints"` | Corroborating preliminary data; not a competing formula. |
| `/u/sirgog`, 2026-09-29, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcrqc6i/) | `"The following formula fits your data almost perfectly."` | Alternative proposed model for Orb of Remembrance outcomes, not adopted or answered by the author in the visible thread. |
| `/u/sirgog`, 2026-09-29, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcrqc6i/) | `"Generate a random number via normal distribution, mean 35, standard deviation 25."` | Community hypothesis; not confirmed by GGG or Macookta. |
| `/u/sirgog`, 2026-09-29, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcrqc6i/) | `"If the number is 100, discard it and go back to step 1. Else, report the number."` | Community hypothesis; its proposed rounding behavior is expressly uncertain. |
| `/u/HockeyHocki`, 2025-06-20, [post](https://www.reddit.com/r/pathofexile/comments/1lg6y7c/memory_strand_crafting/) | `"Harvest and delve dont"` | Community mechanics claim, conflicting with the later “fossils/reforges consume” claim. |
| `/u/Hreaty`, 2026-09-27, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcdz8wr/) | `"alterations/essences/fossils/reforges a million times until you get Y" step(s) that would consume all threads` | Community contrary claim. It does not quantify costs or provide a controlled test. |
| `/u/PersonalityFar4436`, 2025-06-20, [comment](https://www.reddit.com/r/pathofexile/comments/1lg6y7c/memory_strand_crafting/myu6f1f/) | `"Any evasion item with memory i Just thrown a life essence,most time It hit supress or good res on suffix"` | Anecdotal player result consistent with strands filtering tiers, but not a probability estimate. |
| `/u/bkgn`, 2026-09-27, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pcci2c4/) | `"That's already been repeatedly stated by GGG since the start."` | Unsupported in the reviewed thread: no GGG link, quote, or staff response accompanies the claim. |
| `/u/Caosunium`, 2026-10-22, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/19rhw66s23469/) | `"if i unravel with 96 strands for example, will it upgrade 3 times atleast, and then roll for the rest of the tiers, or does it have some other formula?"` | An unanswered visible question, consistent with the post's statement that strand count controls upgrade chance, not an explicitly documented minimum number of separate upgrades. |
| `/u/Macookta`, 2026-09-27, [comment](https://www.reddit.com/r/pathofexile/comments/1wr9445/comment/pccx4fg/) | `"I'm not even choosing to read any negative tone here, but the serious answer is that I enjoy it so much that I made my own science league"` | No mechanics correction; included because it confirms the work's experimental/player-research nature. |

### GGG staff reply

- No GGG staff reply, `GrindingGearGames` account reply, developer badge, or official forum response appeared in the 74 accessible RSS comments for the primary post.
- Reddit's server-rendered page reported 78 comments, while RSS exposed 74. The conclusion is therefore limited to the accessible comment snapshot, not a claim that no hidden/deleted staff reply could possibly exist.
- The visible community assertion that GGG had “repeatedly stated” the behavior was not accompanied by an official citation.

**What it says:** The author explicitly leaves MTR equivalence, rounding, identification behavior, linearity, and some crafting-system interactions unresolved; the material comments add a tentative Orb of Remembrance distribution model and conflicting Harvest/Fossil/reforge reports, but no commenter supplies an authoritative correction to the post's core tier formula, and no accessible GGG staff reply appears.