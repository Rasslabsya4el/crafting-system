# Bench crafting and metamods

Status: reviewed identity/side facts and CoE interactions; current-patch exceptions incomplete.
Confidence: `datamined` for S11 fields; `documented` for S17 wiki corroboration below;
`reimplemented-from-CoE` for source-only behavior.
Read 2026-09-20. Sources: S11 `ModMaster.lua` lines 732-736; S3 `poec_simApplyBenchCraft`,
`poec_simRollAffix`, `poec_simRemoveAffix`, `poec_simRerollItem`; S13 Bench/Multimodding;
S14 cell classes **and accompanying notes**, not merely extracted text.

## Effect and preconditions
Bench operations select a crafted modifier instead of randomly selecting its identity.
Its class support, group conflict and available prefix/suffix slot must be checked. S3's
simulator helper can remove old bench crafts as part of executing a configured bench operation;
that helper's convenience behavior must not become an undocumented atomic game action.
Global corruption/mirroring and unlock availability remain Q9; unlocks belong in loadout inputs.

## Datamined identities
All five rows have a PoB `level` field of 1 and empty `modTags`; this is not a claim about
character level or recipe unlock level. Their `types` maps list supported equipment classes
including Helmet, Ring, Amulet and Belt; the accepted literal builder retains all maps in `data/pob_bench.json` (732 records, 8d49e8f).

| modifier | affix side | PoB group / source line |
|---|---|---|
| Prefixes Cannot Be Changed | suffix | ItemGenerationCannotChangePrefixes / 732 |
| Suffixes Cannot Be Changed | prefix | ItemGenerationCannotChangeSuffixes / 733 |
| Can have up to 3 Crafted Modifiers | suffix | ItemGenerationCanHaveMultipleCraftedMods / 734 |
| Cannot roll Attack Modifiers | suffix | ItemGenerationCannotRollAttackAffixes / 735 |
| Cannot roll Caster Modifiers | suffix | ItemGenerationCannotRollCasterAffixes / 736 |

## Observed rule steps
1. Check capacity and mod-group compatibility for the selected bench mod (S3
   `poec_simApplyBenchCraft`; S15 Blocking undesired mods by modgroup).
2. Treat the added crafted mod as occupying an affix slot and a group, just like other explicits.
3. Normal bench allowance is 1; multimod permits 3 crafted modifiers **including itself**
   (S13 Multimodding; S3 helper counts `bench==1` and multimod ID).
4. When a later action executes, apply its own interpretation of metamod flags. Side locks and
   attack/caster exclusions are not universal immunity; see the table below.
5. Rebuild flags when their carrier mod is removed or retained (S3 `poec_simUpdateMeta` and reroll).

## Selected interaction matrix
These are CoE observations, not independent game validation. Prefix/suffix columns are symmetric
except for the actual slot occupied by their carrier mod. A blank source cell means unknown.

| operation | side locks | cannot-roll attack/caster |
|---|---|---|
| Chaos | protect existing locked-side mods | apply when carrier retained, S14 says with suffix lock |
| Exalted | do not prevent additions to open slots | filter additions |
| Annulment | exclude protected side from removals | protect matching attack/caster mods from removal |
| Scouring / Divine | preserve protected-side mods / values | not applicable |
| Essence / fossil | usage prevented for these outcome-affecting locks | usage prevented; S17 explicitly exempts multimod alone |
| Awakener | S14 says not respected | S14 says not respected |
| Harvest add/remove | side locks apply to removal | apply to addition, not removal |
| Harvest reforge | preserves side locks | **conflict Q6**: S19 changed behavior in 3.27; exact later-draw condition still uncertain |
| Eldritch Chaos | S14/S17 say not respected | S17 says respected; S14 cells are blank |

## Numbers, conditions and differences
Multimod cost conflicts: S13 prose says 2 Exalted, S2/S3 mapping says 2 Divine (Q7).
Do not convert either to a market price. S14 explicitly warns that undocumented game changes
can make its matrix lag. PoB supplies modifier identity/side, not the whole interaction matrix.

S17 Overview and Basic Currencies table independently corroborate the ordinary side-lock,
addition and Annul protection behavior. Its Essence/Fossil example excludes multimod from the
usage prohibition. S19 official 3.27.0 notes establish that tagged Harvest reforges now respect
modifier-type restrictions; this does not supply the missing flag-retention algorithm (Q6).

## Worked examples for future tests
- Multimod occupies 1 suffix and 1 of the 3 crafted allowances; 2 further bench mods remain,
  provided there are matching free slots and no group conflicts (S11/S13).
- Synthetic eligible pool has target weight 2, blocked group weight 3 and other weight 5.
  A compatible bench craft occupying the unwanted group changes intended single-add chance
  from `2/10` to `2/7`. Source of exclusion: S15 and S3; weights are hand-chosen test inputs.
- The two-prefix + prefix-lock Scour example in `basic_currency.md` retains 2 prefixes and
  removes the suffix lock. The lock does not protect its own side (S11 plus S3).

## Open questions
Q6, Q7, Q9. No current-patch matrix or bench price table has been implemented.
