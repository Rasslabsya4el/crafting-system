## PoE1 3.29 Crafting Bench Partial Rerolls

Scope: the two new default bench crafts added in 3.29.0:

- `Reroll 3 random Modifiers on a Rare Item` for 3 Chaos Orbs.
- `Reroll a random Modifier on a Rare Item` for 8 Chaos Orbs.

No repository files were created or changed.

### Official Baseline

| Source | Evidence | What it says |
|---|---|---|
| [3.29.0 Patch Notes](https://www.pathofexile.com/forum/view-thread/3985332), Stacey_GGG / Grinding Gear Games, 16 Jul 2026 | “Added 2 new crafting bench options, unlocked by default. Reroll 3 random Modifiers on a Rare Item for a cost of 3 Chaos Orbs, and Reroll a random Modifier on a Rare Item for a cost of 8 Chaos Orbs” | The crafts were introduced in **3.29.0**, not 3.28; they are default-unlocked and have the stated Chaos costs. |
| [3.29.1 Patch Notes](https://www.pathofexile.com/forum/view-thread/3991672), Grinding Gear Games, 30 Jul 2026 | “Fixed a bug where the crafts ... could not be used on Maps, Invitations, Contracts, Blueprints, Logbooks or Charts.” | These crafts were later explicitly enabled for those eligible rare item categories. |
| [PoEDB Crafting Bench](https://poedb.tw/us/Crafting_Bench), current game-data display | Lists both labels, costs, and eligible category display including equipment, flasks, jewels, maps, tinctures, fishing rods, and map-like items. | Current data corroborates the labels/costs, but does not document the selection algorithm or special-modifier interactions. |

### 1. How are modifiers selected and replaced?

**Official evidence**

- The 3.29.0 patch note says only “Reroll 3 random Modifiers” and “Reroll a random Modifier.”
- It does not say whether the selection is uniform among explicit modifiers, whether selection is with or without replacement, or how replacement affixes are generated.

**Player evidence**

- [“Reroll a Modifier/3 Modifiers on a Rare Item”](https://www.reddit.com/r/pathofexile/comments/1vk6ob6/reroll_a_modifier3_modifiers_on_a_rare_item/), `nsfw_repost_bot`, 10 Aug 2026, player testing “on std for a bit”:
  - “can remove a prefix and add a suffix or vice versa”
  - “reroll +life into +life”
- Conditions: the author did not publish a sample size, item-level controls, complete affix inventories, or raw outcome counts.

**What it says:** the available player report supports that a selected explicit modifier can be replaced by an affix on the opposite side and can be replaced by another roll of the same modifier family. It does **not** establish uniform selection probability, affix weights, tier weights, or the exact internal sequence.

### 2. Does the three-modifier craft preserve prefix/suffix distribution?

**Player evidence**

- [Same Reddit post](https://www.reddit.com/r/pathofexile/comments/1vk6ob6/reroll_a_modifier3_modifiers_on_a_rare_item/), `nsfw_repost_bot`, 10 Aug 2026:
  - The three-modifier craft “doesn't keep the same 3p0s etc”
  - It “can remove a prefix and add a suffix or vice versa.”
- Conditions: unquantified player testing; this is not a GGG specification.

**What it says:** no, the reported behavior is that the three-modifier craft does not preserve the old prefix/suffix count. No official source found states otherwise.

### 3. Do crafted or fractured modifiers participate?

**Official evidence**

- No 3.29 patch note or staff response located describes whether a crafted explicit modifier is an eligible reroll target.
- No source located tests these bench crafts directly on a fractured modifier.

**Background evidence, not bench-craft-specific**

- Fractured-modifier sources generally describe fractured affixes as locked against normal removal/reroll operations. That general rule is not a direct documented confirmation for this newly added bench craft.

**What it says:** **not established for the partial-reroll bench crafts.** There is no attributable 3.29 test or official statement found that demonstrates whether crafted modifiers can be selected, or that directly demonstrates fractured-modifier behavior under either craft. General fractured-modifier rules should not be treated as a documented answer for these specific crafts.

### 4. How do meta-crafts and “Cannot roll” restrictions interact?

**Reported player behavior**

- [GGG bug report: “New Reroll crafting option follows meta mods while removing but not when adding”](https://www.pathofexile.com/forum/view-thread/3994482), `V4civity#0369`, 5 Aug 2026:
  - “Easiest seen in crafting on wand bases with Cannot Roll Caster Modifiers implicit”
  - “Using the craft will eventually add a caster modifier that cannot be removed”
  - The author’s stated interpretation is that meta-modifiers are followed during removal but not addition.
- [“The chaos orb bench crafting reroll options”](https://www.reddit.com/r/pathofexile/comments/1vw2bh6/the_chaos_orb_bench_crafting_reroll_options/), `Kaier_Reign`, 23 Aug 2026:
  - Title claim: the options “ignore Cannot Roll Caster/Attack Modifier implicits.”
  - This is a player video post, rather than an official mechanic statement.

**GGG response**

- [Same GGG bug-report thread](https://www.pathofexile.com/forum/view-thread/3994482), `Jatin_GGG` / Grinding Gear Games, 5 Aug 2026:
  - “Thanks for your report, I'll pass this on.”
- Conditions: this acknowledges escalation of the report. It does not confirm the reported mechanic, say it is intended, or document a later fix.

**No direct evidence found for**

- `Prefixes Cannot Be Changed`
- `Suffixes Cannot Be Changed`
- whether either lock protects a modifier from the selection/removal step
- whether either lock constrains the added replacement modifier
- whether crafted meta-modifiers themselves can be selected by these crafts

**What it says:** the available reports indicate `Cannot Roll Caster Modifiers` / `Cannot Roll Attack Modifiers` may not restrict **added** modifiers. GGG acknowledged the report but did not publicly confirm the behavior or a fix in the sources checked. Prefix/suffix-lock interactions remain unsupported.

### 5. Do the crafts consume Memory Strands?

**Player evidence**

- [“Reroll a Modifier/3 Modifiers on a Rare Item”](https://www.reddit.com/r/pathofexile/comments/1vk6ob6/reroll_a_modifier3_modifiers_on_a_rare_item/), `nsfw_repost_bot`, 10 Aug 2026:
  - “the new crafts consume memory strands.”
- [“Vaal Gloves finished - What do you guys think ;)?”](https://www.reddit.com/r/pathofexile/comments/1x0mnuw/), `Sparkling1337`, 8 Oct 2026:
  - “the new bench craft ‘Reroll 1/3 Modifiers on a Rare Item’ removes Strands....”
- Conditions: both are player observations, not controlled published testing or official documentation.

**Official evidence**

- The 3.29.0 and 3.29.1 notes do not mention Memory Strands for these bench crafts.

**What it says:** two player reports corroborate that these bench crafts remove/consume Memory Strands. No official explanation was found for whether consumption is intended, how the quantity is calculated, or whether it differs by item type or reroll outcome.

### Influence and Eldritch Implicits

- No qualifying source was found that tests either partial-reroll craft on influenced rare items.
- No qualifying source was found that tests whether the crafts alter, remove, preserve, or otherwise interact with Eldritch implicits.
- The official craft text refers to “Modifiers,” but the available sources do not define whether that label includes anything beyond the targeted explicit modifier operations.

**What it says:** influence and Eldritch-implicit interactions are **not documented by the gathered evidence**.

### Comparison with Harvest Reforges

- No direct source found compares the new bench crafts’ algorithm with a Harvest reforge.
- The available player evidence distinguishes them behaviorally from a whole-item reroll: the partial craft reportedly targets one or three existing explicit modifiers and may replace a selected prefix with a suffix or the reverse.
- That is insufficient to establish shared weighting, meta-craft handling, fractured-modifier rules, or Memory Strand rules.

**What it says:** they are partial modifier rerolls, not documented as Harvest reforges or as using Harvest’s rules.

### Evidence Limits

- GGG officially documents the crafts’ introduction, cost, default availability, and later compatibility with maps and similar item categories.
- Player reports supply the only located evidence for prefix/suffix redistribution, same-family replacement, Strand consumption, and `Cannot Roll` behavior.
- No reliable, attributable experiment with sample size and outcomes was found for uniformity, fracturing, crafted-affix targeting, prefix/suffix locks, influence, Eldritch implicits, or a formal Harvest comparison.
- Where those claims matter, the defensible conclusion is **unknown**, not an extrapolation from tooltip wording or analogous crafting systems.