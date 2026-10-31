# Does the crafting bench enforce a crafted mod's item level?

Research ticket [#76](https://github.com/Rasslabsya4el/crafting-system/issues/76) of map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1). Written 2026-10-31 against the pinned patch 3.29.3.3.

## Answer

**No source shows a gate, and every source that speaks to it says the bench does not refuse a craft because the item's level is below the crafted mod's level.** `BenchCraft` stays as landed in [PR #74](https://github.com/Rasslabsya4el/crafting-system/pull/74): no item-level check. An item level 78 bow takes `+2 to Level of Socketed Support Gems` (mod level 80), and a belt of any level takes the damage prefixes (72, 81).

What the mod's `required_level` does instead: it raises the finished item's **wearing level requirement** to 80 % of the mod level (80 → 64, 81 → 65, rounded as the wiki says). That is a property of the item, not a refusal of the craft. The model does not track wearing levels, so nothing is added.

Confidence: moderate-to-good. The evidence is one working implementation (Craft of Exile's code), the wiki's explicit list of bench rules, and three player reports from 2020–2021 (one of them a direct test: an item level 80 item took a craft that Craft of Exile lists at 81). Nobody tested the exact case (item level 78 bow, `+2` support gems) in 3.25–3.29. The ticket's quick in-game check is at the end; it is a confirmation, not a blocker.

## Evidence

Under the map's evidence rule, per source kind.

### Craft of Exile's code (kind `coe`): no check

Local copy `sources/raw/coe/package.js` (git-ignored, in the main checkout, fetched 2026-09-20).

1. **The bench-craft step checks only slots, family and duplicates.** `poec_simApplyBenchCraft` refuses a craft with exactly three error kinds: `prefix`/`suffix` ("No … left to add benchcraft"), `modgroup` ("Modgroup conflict for benchcraft"), `id` ("Benchcraft already there"). It reads the mod's tier (`poecd.tiers[id][base][tier]`) only to get the value ranges and weight. It never reads the item's level. Quote: `if(openaff[atype]>0||crsim_bypass.rarity=="normal"){ … if(mconflict){errtype="modgroup"} else {if(strids.indexOf("|"+bench[i].id+"|")>-1){errtype="id"} else {…push the mod…}}} else {errtype=atype}`.
2. **The mod pool exempts bench mods from the item-level cut.** Every place that builds the pool for an item level keeps a tier only if `htilvl<=iLvl||mod.id_mgroup==11||mod.id_mgroup==13||mod.id_mgroup==10` (simulator pool at `crsim_settings.ilvl`, the calculator pool at `simulator_settings.ilvl`, the graveyard pool). Group 11 is `poec_constants.refs.bench_mgroup`; 10 and 13 are the veiled groups. So Craft of Exile offers the bench list for every item level.
3. **The data still carries the level.** `poec_data.json` gives the bench mod `+# to Level of Socketed Support Gems` (id 2913, group 11) tiers `ilvl 60 → [1]` and `ilvl 80 → [2]` with weight 0. The level is kept as a label (the 2020 thread below calls Craft of Exile's displayed levels "the minimum ilvl the mod can spawn on"), and the code deliberately skips it for group 11.

Reading: a working implementation that the owner admits as the default where documentation is incomplete treats the bench as ungated. It is a design choice of that tool, not a proof of the game; it agrees with the player reports below.

### The PoE wiki (kind `wiki`): two rules, no level rule

Read 2026-10-31 in the built-in browser (Anubis check passed).

- [Crafting Bench](https://www.poewiki.net/wiki/Crafting_Bench), "Using the crafting bench": "Crafting a mod follows the normal affix rules. Specifically: The item cannot already have a mod of that type. The item must have a prefix or suffix slot open as appropriate." The page has no mention of item level, `ilvl` or required level anywhere (searched the whole page text, 100,880 characters). The craft tables have no level column.
- [Modifier](https://www.poewiki.net/wiki/Modifier), "Mod level": "The required level of the relevant entity. For example, this can be the required item level or a monster level. However, there are cases where this is not respected: in particular this is the case for any mods that are directly given to other entities, such as implicit mods including enchantments or monsters with innate mods." and "The mod level is also a factor in calculating the level requirement of items; raising the level requirement up to 80% requirement of the mod". Domain 9 "Crafted" is described as "Options offered by the crafting bench to add modifiers to items". The page does not list the bench among the places where the mod level is the item-level gate, and it is not in the exception list either; it neither supports nor contradicts a gate by itself. Read with the bench page's two-rule list it points to no gate.
- [Item level](https://www.poewiki.net/wiki/Item_level): "the Crafting Bench can be used to roll a specific number of sockets to an item regardless of ilvl." That is about sockets only; it shows the bench is not ruled by item level in general, no more.

### repoe-fork 3.29.3.3 (kind `datamined`): nothing besides `required_level`

Files `crafting_bench_options.json` (765 options, 732 with `add_explicit_mod`) and `mods.json`, in `.claude/scratch/real-cache/repoe-fork/3.29.3.3/`.

- A bench option has only these fields: `actions`, `item_classes`, `bench_tier`, `cost`, `master`. No level field.
- The mod it adds (domain `crafted`) has `required_level`, `spawn_weights` (all weight 0 for the item tags), `generation_weights` (empty), `stats`, `text`, `groups`, `type`, `name`, `gold_value` and tag lists. Nothing there says "item level of the item".
- `required_level` of the 732 bench mods runs 1, 15, 20, 24, 25, 30, 40, 50, 60, 68, 72, 75, 80, 81 and follows the craft's price tier: the life crafts are 15 / 40 / 68 at `bench_tier` 1 / 2 / 3; `+1` and `+2` support gems are 60 (8 Chaos) and 80 (4 Exalted); the damage prefixes are 72 (4 Chaos) and 81 (4 Exalted). It is the mod's own level, the same field the wiki says raises the wearing requirement.

The data therefore does not say a gate exists; it also cannot rule one out, since a gate would be an engine rule. A third-party site reports the same fields (below).

### Player reports and GGG notes (via the `gpt-research` skill, model Terra)

Reddit opens only through that skill; the quotes are the skill's, not re-read by me. Report kept at `C:\Users\user\.gpt-research\jobs\20261031-123312-ec4a\report.md`.

| Source | Date | Case | Quote |
|---|---|---|---|
| [r/pathofexile "BV crafting question for a newb"](https://www.reddit.com/r/pathofexile/comments/jlai3a/bv_crafting_question_for_a_newb/), answer by u/alzhang8 | 2020-10-31 | Item level 50 bow; the OP saw in Craft of Exile that `+2 to socketed support gems` "wasn't able to be crafted due to ilvl" | "Ilvl is ignored in crafting table. +1 socketed gems can be forced on, so all you need is spell damage/fire damage." |
| [r/pathofexile "does crafting bench mods have no ilvl reqs? …"](https://www.reddit.com/r/pathofexile/comments/i8skww/does_crafting_bench_mods_have_no_ilvl_reqs_why/), OP u/ffxivbtw; replies u/alzhang8, u/sirgog | 2020-08-13 | **Direct test**: a craft Craft of Exile lists at item level 81, done on an item level 80 item | OP: "shows t1 dmg while leeching needs ilvl 81, and i can craft it on ilvl 80 just fine". alzhang8: "It will raise the level required to wear the item". sirgog: "Those are the minimum ilvl the mod can spawn on." |
| [r/pathofexile "How does iLvl affect mods from crafting bench?"](https://www.reddit.com/r/pathofexile/comments/l2fp7c/how_does_ilvl_affect_mods_from_crafting_bench/), answer by u/Nottrak | 2021-01-22 | Asked whether item level 80 is needed for the top spell damage craft | "No, doesn't matter. You can craft t3 life onto iLvl 2 gloves, all it does is raise the items level req." (one other reply, "Yep", has no reasoning) |
| [GGG 3.16 notes](https://www.pathofexile.com/forum/view-thread/3184944), Community_Team | 2021-10-05 | Rank 1 Ailment, Stun and Curse Mitigation crafts moved to the campaign | "The modifier level of existing modifiers in the Rank 1 Ailment, Stun and Curse Mitigation category have been lowered (so the item level requirement of the item is appropriate if you use this craft during the campaign)." |

The 3.16 sentence says "item level requirement of the item". Read with the wiki ("raising the level requirement up to 80% … of the mod") that is the wearing requirement of the finished item, which is why GGG lowered the mod level for campaign crafts: so the item can still be worn early. It does not describe a refusal, and does not name the +2 gems or the belt crafts. No 3.25–3.29 note found that gates or ungates the bench by item level.

Not found: any thread, post or note saying the bench refused or greyed out a craft for low item level; any Craft of Exile FAQ on the point.

Third-party data pages ([poeref.com](https://poeref.com/crafting-bench/record-706/), "RequiredLevel is retained separately from modifier level and is not presented as an item-level eligibility test") agree, but that site labels its bench records "availability unverified", so this is only a data echo, not counted.

### What is not settled

- The exact case (item level 78 bow, `+2` support gems) has no direct report. The nearest are a direct item level 80 / listed 81 test (2020) and two general answers (2020, 2021). Small samples, five years old, but none conflicts with them and the engine did not change the bench in the notes found (3.26 changed how recipes unlock and which slots some crafts roll on, not their level handling).
- The R14 guide's item level 78 is given by the research report that cites it (`docs/research/2026-10-30-5-reference-routes.md`, R14: "Thicket Bow", `item_level: 78`); R15 (a different guide) uses an item level 82 bow for the same craft. If 78 there is only the item level the guide's author started from, it does not test the question either. The guide's own text was not re-read here.

## What changes in the project

- `BenchCraft` stays without an item-level check; nothing to implement for R13 and R14, #66 and #70 are unblocked on this point.
- Recording the finding as a rule is optional: a registry claim that records the absence is useful so the next reader does not reopen it.

```yaml
  - id: bench_craft.no_item_level_gate
    statement: A bench craft is not refused because the item's level is below the crafted mod's `required_level`; `required_level` raises the finished item's wearing level requirement instead. The crafted mod's level is not an item-level condition of the craft.
    source_kind: coe
    url: https://www.craftofexile.com/
    quote: "htilvl<=iLvl||mod.id_mgroup==11||mod.id_mgroup==13||mod.id_mgroup==10 (bench group 11 skips the item-level cut); poec_simApplyBenchCraft refuses only on prefix/suffix, modgroup, id"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

(Backed by the wiki's rule list and the 2020 test; `source_kind` takes one source, so the code is the one cited. If the owner's in-game check below is done, it becomes kind `owner` and replaces this one.)

## Quick in-game check (optional confirmation)

Needs: one bow of item level 78 or lower, the craft unlocked and 4 Exalted Orbs. Steps:

1. Make or buy any white or magic bow with item level 78 or lower (hover the item, hold Alt; "Item Level" is in the second block). A plain rare bow with a free prefix also works.
2. Open the Crafting Bench, pick the bow, choose "+2 to Level of Socketed Support Gems" (4 Exalted Orbs). Check that the item has a free prefix slot and no `+# to Level of Socketed Support Gems` already.
3. Say whether the craft button is available and works, and what the item's "Requires Level" becomes (expected 64). If the button is greyed out or the bench says the item level is too low, this ticket is wrong and the claim above is replaced by the rule it names.

Cheaper variant: any item level 30 belt, "(12-14)% increased Damage" (4 Chaos Orbs), same two things to report.
