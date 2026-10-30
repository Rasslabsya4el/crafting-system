## Research Report: “3.25 Updated Guide to Recombinators”

Primary source: [3.25 Updated Guide to Recombinators](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/), by `/u/Butsicles`, posted August 21, 2024.

The Reddit thread is available through its RSS feed rather than the normal Reddit page. The feed contained the submission and 193 comments/replies.

## 1. Who wrote the guide, when was it written, what patch did it target, and what changed?

### Source evidence

The post opens:

> “Hello Reddit, welcome to an updated 3.25 guide to recombinators. I'm one of the original co-authors on Iron's guide back in sentinel.”

It describes the 3.25 system as substantially different from Sentinel:

> “While some of the original recombinator rules have remained the same compared to Sentinel league, there has been an overhaul in mechanics across the board, leading to big nerfs in item outcome diversity, but a **buff** in *some cases*.”

The author gives the approximate experimental basis:

> “A moderate amount of data (500-800 recombines, almost all in-league) has been collected to derive the conclusions described in this post.”

The post’s TL;DR is:

> “Recombinator new use cases = GOOD.”

The linked earlier work is Iron’s [Complete Guide to Recombinators](https://www.reddit.com/r/pathofexile/comments/v0nm0c/the_complete_guide_to_recombinators/), originally written for Sentinel.

The post includes these edit notes at the end:

> “Note: 08/21/2024 3:50 p.m. Central. Edited Table 1 (mod distributions) thanks to more data from Rusty and Order”

> “Note: 08/23/2024 11:53 a.m. Central. Added step about 50/50 prefix/suffix selection odds”

The author also corrected the expected odds during the thread:

> “The odds have been updated (around 30-40%, will update as we get more data), they're worse than previously stated (we got a lot of additional 6 mod data, and I've updated accordingly. We also are going to do additional verification on exclusive affix selection).”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lj9vtzd/).

The post was informed by testing from the Prohibited Library Discord and credited contributors including `findar`, `Forgotten Arbiter`, `gdubrocks`, `n maku`, `Rusty`, `Olxinos`, `Monet`, and others.

### What this means

This is a community reverse-engineering guide for the 3.25 Settlers-era Recombinator, not an official GGG mechanic specification. It was initially written on August 21, revised the same day with more six-affix data, and updated on August 23 with the empirical 50/50 prefix-versus-suffix filling observation.

The relevant contemporary official evidence is the [3.25.1 patch notes](https://www.pathofexile.com/forum/view-thread/3553263), which state:

> “When Recombinating items, rarer Modifiers now have a much higher chance to be selected for the resulting item than before.”

Therefore, the guide’s measurements and conclusions must be understood as 3.25-era observations, with weighting behavior already changing during the same patch cycle.

## 2. How are the prefix and suffix pools formed, and what are the exact kept-count tables?

### Notation

The guide uses:

- `2p/1s`: an item with two prefixes and one suffix.
- `2p/*s`: an item with two prefixes and any number of suffixes.
- `5TP/4TS`: five total prefixes and four total suffixes across both input items.
- `e`: an exclusive modifier, such as `1p1e/1s1e`.

The guide treats prefixes and suffixes as separate pools for most purposes.

### Sentinel-era recap

The guide says that in Sentinel:

> “All the prefixes and suffixes are put in separate pools, and for all intents and purposes, are considered independent from one another.”

Under the old system:

> “Mod weights were not a factor here.”

It gives the example that if a pool contained a Merciless modifier with weight 25 and Mana with weight 1000, they were equally likely when one modifier was selected. Duplicate modifiers were both included:

> “This means ‘doubling’ mods increased your odds at picking said mod.”

### 3.25 pool formation

The new guide states:

> “The prefixes and suffixes are put into different affix pools. The final number of prefix/suffix mods is dependent only on the initial number of total prefix/suffix modifiers respectively.”

For each side, the number of modifiers in the final item is determined by the total number of modifiers in that side’s combined pool. The guide says:

> “NNN (except fracture) and ‘exclusive’ modifiers also ‘add’ to the total affix pool.”

However:

> “Fracture modifiers only add to the pool if their own base is chosen.”

This is a critical distinction. A fractured modifier can pad the pool only when the item carrying the fracture is selected as the output base.

The guide also added an empirical ordering rule:

> “Prefixes or suffixes are filled first, with 50/50 odds.”

That 50/50 rule matters because exclusive modifiers can invalidate the other exclusive modifiers across both sides.

### Exact Table 1: conditional final affix-number distributions

The table in the Reddit post is:

| Final affixes / Initial pool | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|
| 0 mod | 41% | 0% | 0% | 0% | 0% | 0% |
| 1 mod | 59% | 67% | 39% | 11% | 0% | 0% |
| 2 mod | 0% | 33% | 52% | 59% | 43% | 28% |
| 3 mod | 0% | 0% | 10% | 31% | 57% | 72% |

The post explicitly warns:

> “All of the percentages in Table 1 have not been rounded to ‘nice’ numbers.”

The author’s example for a two-modifier pool is:

> “If the sum of prefixes in both input items is 2, then there is a 66% chance of keeping only one of those 1 prefixes, and a 33% chance of having both prefixes on the final item.”

The post also notes that five total prefixes produce a 57% chance of three final prefixes, while six total prefixes produce a 72% chance.

### Raw data behind Table 1

The linked [raw spreadsheet](https://docs.google.com/spreadsheets/d/10slavP-n-rCjnu5sVFi9DQTUybI2ZDoBbZsZ2UxM7Xg/export?format=csv) contains the following first table:

| Final / Initial | 1 mod | 2 mod | 3 mod | 4 mod | 5 mod | 6 mod |
|---|---:|---:|---:|---:|---:|---:|
| 0 mod | 89 | 0 | 0 | 0 | 0 | 0 |
| 1 mod | 128 | 196 | 124 | 47 | 0 | 0 |
| 2 mod | 0 | 84 | 171 | 241 | 151 | 82 |
| 3 mod | 0 | 0 | 26 | 136 | 194 | 219 |

The raw counts do not correspond exactly to the rounded percentages in every cell, because the sheet combines data from multiple experimenters and the post was revised after additional testing.

The sheet identifies sources including:

- `MY DATA`
- `n maku`
- `PYCKS`
- `OLXINOS`
- `Rusty`
- `Order`
- miscellaneous experiments

It includes separate “AFFIX IN POOL” tables for pools from one through six affixes. Representative aggregate counts include:

- Two-affix pool: 10 + 12 + 11 + 36 + 31 + 11 + 17 + 7 + 61 observations for one final affix, and 6 + 9 + 4 + 14 + 19 + 9 + 3 + 1 + 19 for two final affixes.
- Three-affix pool: multiple source columns, including 16/13/4 from the author’s data and substantial Rusty/Order additions.
- Four-, five-, and six-affix pools: heavily supplemented by Rusty and Order data, which explains the August 21 revision.

### Special exception: `1p/0s + 0p/1s`

The post says the normal independent prefix/suffix model has one exception:

> “The only exception to this distribution rule is the case with 1p/0s + 0p/1s.”

The author reports no observed white result:

> “There are no reports of a white item coming out of this recombination.”

Thus, only three outcomes are observed:

- `1p/0s`
- `0p/1s`
- `1p1s`

Each was measured at approximately 33%.

This is the specific situation where:

> “prefix/suffix are not independent, since 0p implies 1s and vice versa.”

### What this means

The initial prefix and suffix counts determine how many slots each side is likely to retain. The exact modifier identities are selected afterward from eligible candidates. Padding the pool can greatly increase the chance of retaining two or three modifiers, but padding with the wrong kind of modifier can also trigger exclusive-modifier conflicts or consume final slots.

## 3. How are modifiers selected, and how do weighting, tiers, families, crafted mods, fractures, influence, NNN mods, and Eldritch modifiers behave?

### Modifier selection and weighting

The guide’s new process is:

1. Select one of the two input bases with a 50/50 chance.
2. Calculate the final item level.
3. Separate prefixes and suffixes into their pools.
4. Determine the number of final prefix and suffix modifiers from the pool-size table.
5. Fill prefixes or suffixes first, empirically at 50/50.
6. Select eligible modifiers while trying to satisfy the required counts.
7. Apply exclusive-modifier and non-native restrictions.

The guide says that when there are more eligible modifiers than available slots:

> “the weights of these modifiers is also a factor, where modifiers with higher weights are more likely.”

But it also says:

> “the specifics of this formula are not currently not fully fleshed out.”

On tier weighting:

> “Mod tiers at least do not seem to be a factor if the weights are the same.”

The author later summarized the practical conclusion:

> “Affix weights matter, but you want to avoid situations where they do.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljaltc5/).

The author’s recommended strategy is to use exclusive modifiers to force a situation where the desired low-weight mods are the only eligible candidates for the predetermined slots. In that case, the original weight becomes much less important.

The author explains:

> “Essentially we kind of ignore mod weighting with the way we set up recombinations because we’re forcing even the rarest of modifiers to show up by fixing the final number of affixes.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljby0hr/).

A later comment by `vins_is_back` proposed that the exclusive modifiers themselves appear to be treated as equally weighted rather than inheriting normal natural modifier weights:

> “the exclusives seem to be weighted equally (they don’t inherit their original weights if a natural equivalent mod exists)”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lk9ou3e/).

That should be treated as a community hypothesis, not a confirmed formula.

### Exclusive modifiers

The guide defines an exclusive modifier as:

> “A modifier that cannot appear with another exclusive modifier on a recombined item.”

The non-exhaustive list includes:

- Breach modifiers, such as Grasping Mail modifiers.
- Incursion modifiers.
- Essence modifiers that have no normal tier.
- Beast aspects.
- Elevated influenced modifiers.
- Delve modifiers, such as `of the Underground`.
- Veiled modifiers.
- Crafted modifiers, depending on the specific craft.
- Metacrafted modifiers.
- Named crafted suffixes, such as `of the Order`.
- Named crafted prefixes, such as `Chosen`, `Tora’s`, and `It’s`.

The guide warns that crafted modifiers named `UPGRADED` or `OF THE CRAFT` may not be exclusive:

> “If trying to craft exclusive mods, AVOID THEM and craft NAMED MODIFIERS.”

The author explicitly says the list was incomplete:

> “The exact list of exclusive/non-exclusive crafted prefixes and suffixes is currently not fleshed out.”

The guide’s core rule is:

> “Any of these modifiers cannot show up with other mods on this list on a final recombinated item.”

If one exclusive modifier is selected, the other exclusive modifiers in both prefix and suffix pools become ineligible.

This is why adding a crafted modifier can be harmful when the desired modifier is exclusive. As `iceman012` summarized:

> “If it is an exclusive affix, then adding crafted mods will reduce the chances of getting the targeted affix.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljaas8w/).

Conversely, non-exclusive crafted modifiers can safely be used for padding and doubling. The author’s post edit says:

> “Non-exclusive crafted modifiers are safe to use for mod doubling.”

The author later recommended using a resistance craft as a safe non-exclusive filler:

> “If you want to be safe, craft a resistance. It’s a non exclusive crafted modifier so you’re safe there.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lje44pm/).

### The 50/50 exclusive-side behavior

The guide reports that exclusive selection is not weighted by the number of exclusive modifiers on each side. It says:

> “the number of exclusive prefixes and suffixes doesn't actually change the odds of selecting either (i.e. it seems to be 50/50). As long as you have one exclusive suffix in the pool you should be good.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lj9xsnw/).

The author later clarified that this was an empirical observation, not initially a known implementation detail:

> “The coin flip observation is more of an empirical one, as we combined 1e/3e + 1e/3e many times and observed it being 50/50.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljaq6xz/).

The post’s exclusive-modifier strategy relies on this behavior:

- Put desired non-exclusive prefixes in the prefix pool.
- Add at least one exclusive suffix as a counterweight.
- If the exclusive suffix is selected, exclusive prefixes are removed.
- The remaining prefix slots can then be filled by the desired prefixes.

The author describes a representative setup with six total prefixes and one exclusive suffix:

> “Because there are 6TP ... we have an ~72% chance at 3 mods.”

The approximate chance of forcing the desired three prefixes is:

> “1/2 * 0.72 ~= 35%.”

The 50% is the chance that the suffix side is filled first and the exclusive suffix is selected; the 72% is the chance of retaining three prefixes from six total prefix inputs.

### Non-native natural modifiers, or NNNs

The guide defines “non-native, natural” modifiers as modifiers that are not necessarily drop-exclusive, but only function on certain bases.

Examples include:

- Influenced modifiers.
- Defence modifiers.
- Attribute-specific affixes.
- Life regeneration or Energy Recharge Rate modifiers.
- Suppression modifiers.
- Fractured modifiers.

The guide explains:

> “They’re called non-native because they cannot appear on the final item if it violates their ‘native’ condition.”

For example:

- An influenced modifier cannot appear on a non-influenced final item.
- Armour-related modifiers cannot appear on a pure Energy Shield base.
- Attribute-specific modifiers may not appear on the wrong attribute base.
- A fractured modifier cannot transfer if its originating base is not selected.

If the wrong base is selected, NNN modifiers become ineligible. The recombinator then tries to satisfy the predetermined prefix/suffix counts using the remaining eligible modifiers.

The guide gives this example:

> “if you pick a strength glove base and have mana in your prefix pool, it cannot be picked.”

### Influence

Influence itself is not described as exclusive:

> “Influence (of course, influence and fractured cannot co-exist, but they are not exclusive with the other mods on the above list).”

However, influenced modifiers are NNN. They require the correct influenced base to survive.

This creates a useful single-mod transfer technique. The guide’s Grasping Mail example adds an influenced prefix to a breach item, then combines it with a blank desired base. If the ordinary item base is selected, the influenced modifier cannot transfer, leaving the breach modifier as the only eligible prefix.

The guide estimates a 50% total success rate:

> “Because the chance of picking the white item is 50%, the overall transfer success rate is also 50%.”

The author later warned:

> “elevated influence won’t work with this since it’s exclusive.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lj9vtzd/).

### Fractured modifiers

The guide classifies fractured modifiers as:

- Not exclusive.
- NNN.
- Base-dependent.

The guide says:

> “Fracture modifiers only add to the pool if their own base is chosen! Avoid them if possible.”

A fractured modifier cannot transfer to another base if the fractured item’s base is not selected. The author gave the direct reply:

> “Fractured suffixes can't transfer.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljamd4l/).

Another community response summarized the practical consequence:

> “You cannot transfer the mod if it is fractured already, but you can fracture it after moving it.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljcbg5y/).

### Item level and modifier tiers

The guide preserves the Sentinel item-level formula:

> “Item level : (item1 + item2) / 2 + 2, capped the max(item1,item2).”

In mathematical form:

```text
final item level = min(max(input item levels), floor((ilvl1 + ilvl2) / 2) + 2)
```

The post does not explicitly say “floor,” but the game’s item-level calculation requires an integer result.

The final base is selected from either input with a 50/50 chance. The selected base determines inherited properties, but the item level is recalculated.

The 3.25 guide states:

> “All attributes are inherited except defence percentile, which seems to be rerolled.”

It further reports:

> “The rerolled defence percentile also seems to have no correlation with the input defence percentiles.”

The inherited properties include, according to the Sentinel recap:

- Item influence.
- Enchants.
- Tags.
- Anoints.
- Quality.
- Other base-bound properties.

The guide says modifiers can move to a lower-level final item:

> “Item mods can move onto items with lower item level than they exist on.”

Its example is a tier 1 chaos resistance modifier whose normal minimum item level is 82 being recombined onto an item with a lower final item level.

The guide’s data suggested modifier tier was not a strong independent selection factor when modifier weights were equal, but this was explicitly marked as needing more testing.

### Modifier families

The official [3.19.0 patch notes](https://www.pathofexile.com/forum/view-thread/3293287) state:

> “Fixed a bug where Recombinators were ignoring modifier families in certain situations.”

The 3.25 Reddit guide does not provide a new independent family-selection model. It assumes normal modifier-family eligibility applies, and its pool descriptions refer to “specific overlapping mod groups” and duplicate/doubled modifiers.

Thus:

- Modifier families remain an eligibility constraint.
- Duplicate copies can increase the pool count.
- Two copies of the same mod cannot normally both occupy separate final slots if the game treats them as the same family/modifier.
- Doubling can increase the chance of retaining that modifier while not necessarily consuming two final slots.

The earlier Sentinel guide explains this with duplicated mods: a duplicated mod counts toward pool size but cannot appear twice on the final item.

### Eldritch modifiers

The 3.25 Reddit guide does not discuss Eldritch implicits or Eldritch modifiers specifically. There is no occurrence of “Eldritch,” “Exarch,” or “Eater” in the extracted post body.

Therefore, the guide provides no direct 3.25-era rule for whether an Eldritch modifier is exclusive, NNN, inherited, or eligible for transfer. Any claim that Eldritch modifiers behave like essence, influenced, fractured, or crafted modifiers would be an extrapolation and should not be attributed to the guide.

### What this means

The important distinction is not simply “rare versus common mod.” It is:

1. Is the modifier eligible on the selected final base?
2. Is it exclusive with other special modifiers?
3. How many final slots were predetermined by the combined pool?
4. Among eligible modifiers, how do weights influence the remaining choices?

The guide’s strongest strategy is to engineer steps 1–3 so that modifier weight has little opportunity to hurt the desired outcome.

## 4. What evidence, sample sizes, and official patch history support these conclusions?

### Data sample

The author states:

> “A moderate amount of data (500-800 recombines, almost all in-league) has been collected.”

The raw spreadsheet shows that the data was pooled from several contributors rather than collected under one single controlled experiment. The source columns include the author, `maku`, `pycks`, `olxinos`, `Rusty`, `Order`, and miscellaneous experiments.

The first aggregate count table contains 1,? observations when summed across all cells. More importantly, its distribution is uneven:

- Lower pool sizes have large numbers of observations.
- Five- and six-affix pools were initially sparse.
- Additional Rusty and Order experiments heavily increased the five- and six-affix sample sizes.
- That additional data caused the August 21 revision to Table 1.

The post itself acknowledges the uncertainty:

> “the conditional affix distributions are not set in stone since our sample sizes are still relatively small compared to the dataset collected in Sentinel league.”

### Official patch evidence

The relevant official changes are:

#### Sentinel-era baseline

The [3.19.0 patch notes](https://www.pathofexile.com/forum/view-thread/3293287) contain the historical Recombinator section and a bug fix:

> “Fixed a bug where Recombinators were ignoring modifier families in certain situations.”

This supports the guide’s comparison against Sentinel and the importance of modifier families.

#### 3.25 launch

The [3.25.0 patch notes](https://www.pathofexile.com/forum/view-thread/3531661) introduced the Settlers league, including the Kingsmarch/Recombinator context.

#### 3.25.1 weighting change

The [3.25.1 patch notes](https://www.pathofexile.com/forum/view-thread/3553263) state:

> “When Recombinating items, rarer Modifiers now have a much higher chance to be selected for the resulting item than before.”

This is the official basis for the guide’s claim that modifier weights matter in 3.25.

### Evidence quality and limitations

The author’s evidence is useful but not definitive because:

- The sample was only hundreds of recombinations.
- Several experimenters contributed data under potentially different conditions.
- The post was revised while experiments were still ongoing.
- The exact weighting formula was unknown.
- Exclusive-modifier ordering was initially inferred from outcomes rather than confirmed from game data.
- Standard and league Recombinators may not have behaved identically.

A relevant Standard-league comment from `Monetokuzuma` said:

> “They kind of use the new mechanics, we found the weightings for how exclusion blocking works to be a bit different however (he got 1/8 to hit the prefixes in the 1p/3s situation, while it was 50/50 in league).”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljbv2vw/).

That is an important warning against treating the 3.25 guide as universally applicable to every Recombinator source or league environment.

### What this means

The post is best treated as a strong experimental model for the 3.25 league Recombinator, not as a mathematically complete specification. The high-level rules are well supported; exact percentages, weighting, and exclusive-selection ordering were still provisional.

## 5. What caveats, corrections, open questions, and later-version obsolescence were identified?

### In-thread corrections and caveats

#### Essence modifiers

The guide treats essence modifiers without normal tier numbers as exclusive. A comment clarified that not every essence-produced modifier is necessarily exclusive:

> “most essences have a special named tier instead of being true t1, so your finished item can literally never give you 3 t1 if the additional desired mods came from essences and don't say ‘t1’ when you hold alt.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljd1tgm/).

The same commenter clarified:

> “if the modifier has a normal tier (t3 in this case) you're all good. Even deafening essences sometimes generate normal tier modifiers.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljdcfuh/).

The practical test is to hold Alt and check whether the modifier has a normal tier number or a named essence tier.

#### Crafted filler

The simplistic TL;DR was:

> “aside from your targeted affixes, try to have as many affixes as possible, by filling empty affix spots with garbage crafted mods.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lja20gu/).

That was immediately qualified:

> “That's only if your targeted affix isn't an ‘exclusive’ affix.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljaas8w/).

The correct rule is therefore:

- Use non-exclusive crafted modifiers as padding.
- Avoid unconfirmed or exclusive crafts when the target is itself exclusive.
- Use named exclusive crafts intentionally only when exploiting the exclusive-counterweight strategy.

#### The `of Control` correction

A later comment corrected one crafted-mod classification:

> “‘of control’ is not exclusive (same with normal craft mana mod)”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lkkcfwo/).

This demonstrates why the guide’s exclusive-craft list should not be treated as complete.

#### Essence doubling

The author said:

> “Yes, you can double up mod essences on A&B. I expect them to both add towards the total mod pool, but some preliminary testing ... seems to suggest something funky is going on.”

The recommendation was:

> “I would simply avoid doubling essences unless you’re willing to take on risk, as I don’t have that data yet.”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljby0hr/).

The author also confirmed:

> “Regarding essence and incursion, yes they both cannot simultaneously exist.”

#### Veiled, elevated, and special modifiers

The guide lists veiled and elevated modifiers as exclusive. The author specifically corrected an attempted strategy:

> “elevated influence won’t work with this since it’s exclusive”

Source: [author comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/lj9vtzd/).

#### Fractures

The guide and comments make clear that fractured modifiers are not a reliable transfer method. They are base-dependent and only contribute to the pool if the fractured base is selected.

#### 1p/0s plus 0p/1s

The post gives a special 33/33/33 model for this combination. A later commenter reported a video where both input mods disappeared and an affix tier changed:

> “Recombinator removed both input mods and upgraded a tier of an affix.”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/ljierpk/).

This is evidence that the special case may have had additional outcomes or that the observation involved another mechanic. It should not be treated as disproving the guide’s measured rule, but it is a reason to avoid assuming the 33/33/33 result is a complete implementation specification.

### Open questions explicitly left by the guide

The post concludes with:

> “Things that are still unknown and will be updated in the following days:
>
> * Weighting formulas
> * Dust/gold cost (don't count on it, this is really hard)”

It also says:

> “Not stated in this guide are rules regarding selective ‘annulling’.”

The author did not feel confident recommending annul strategies because the weighting formula was unknown.

### 3.26 and later changes

The major official change arrived in 3.26.0. The [3.26.0 patch notes](https://www.pathofexile.com/forum/view-thread/3787013) introduced two Recombinator modes:

> “You are able to decide which modifiers on the two items you input into the Recombinator you would like to try to merge together (with a chance of success displayed to you). This new method of Recombinating can result in the items being destroyed.”

They also state:

> “Isla's previous method of Recombinating is still available if you'd prefer to leave it up to fate, combining two items randomly (with no risk of destroying your items), though this is the less predictable method.”

In the same patch notes, the old method is explicitly called **Unpredictable Recombination**, and GGG changed it:

> “The Recombinator, when using the now Unpredictable Recombination method will result in fewer modifiers on the item on average if the input items were using many modifiers that cannot normally roll on the item, for example Veiled Modifiers or Essence Modifiers.”

The notes explain the intention:

> “This should result in the very top-end becoming less optimal for creating the best items, without affecting the average use cases.”

This directly targets the 3.25 guide’s most powerful technique: filling input items with many special/exclusive modifiers that normally cannot all roll on the final base.

A 2025 comment on the Reddit thread recognized the impact:

> “RIP, killed by patch notes :(.
> Hopefully there's a new exploit for 3.26 :(”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/mxbjp1z/).

Another commenter asked whether the 3.26 change had effectively destroyed the guide’s exclusive-modifier strategy:

> “What I understand is they basicaly nuked the ‘Exclusive mod shenanigans’ method. But the rest remains the same. Right?”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/mxbxar4/).

There is no official reply in the captured thread confirming that every remaining rule was unchanged. The safe conclusion is:

- The 3.26 change specifically nerfed the top-end use of many non-native modifiers, including essence and veiled modifiers.
- It did not necessarily invalidate all ordinary recombination or single-mod-transfer use cases.
- The 3.25 probability table should not be assumed to remain valid for 3.26 onward.
- The 3.25 exclusive-modifier filler strategy is materially less reliable under the new Unpredictable Recombination behavior.

### 3.27 evidence

A later user reported:

> “i can confirm that in 3.27 the method that use multimod does not work anymore i got 1 prefix out of 5 multiple times, so save your div”

Source: [comment](https://www.reddit.com/r/pathofexile/comments/1exyavx/325_updated_guide_to_recombinators/nqydo55/).

This is anecdotal rather than controlled testing, but it supports the conclusion that the 3.25 multimod/exclusive-padding method was not portable to 3.27.

### 3.28 and 3.29

The official [3.28.0 patch notes](https://www.pathofexile.com/forum/view-thread/3913392) and [3.29.0 patch notes](https://www.pathofexile.com/forum/view-thread/3985332) do not contain a new dedicated Recombinator mechanics section comparable to the 3.26 change.

That does not prove that every internal mechanic stayed identical, but it means:

- There is no official 3.28 or 3.29 patch-note statement restoring the 3.25 behavior.
- There is no official patch-note confirmation that the 3.25 table still applies.
- Later community experience should take precedence over blindly applying the 3.25 guide.

### Final assessment

The guide remains valuable as historical documentation of how players reverse-engineered the 3.25 league Recombinator. Its durable ideas are:

- Separate prefix and suffix pool accounting.
- Base selection and item-level recalculation.
- NNN/base eligibility constraints.
- The danger of fractures and incompatible bases.
- The value of doubling ordinary modifiers.
- The existence of exclusive-modifier conflicts.
- The importance of controlling eligibility before worrying about weighting.

Its most version-sensitive material is:

- The exact Table 1 probabilities.
- The 50/50 exclusive-side behavior.
- The multimod and named-craft filler strategy.
- The claim that six total modifiers can reliably force roughly 72% three-mod outcomes in practical crafts.
- Any strategy relying heavily on essence, veiled, or other modifiers that cannot normally roll on the output base.

As of the later evidence examined here, the 3.25 guide should be cited and used as a **3.25-specific experimental guide**, not as current Recombinator instructions for 3.26–3.29.