# Spec: explicit item specifications, prices and loadouts

Worktree `.worktrees/plan-inputs`, branch `w-plan-inputs`.
Allowed `src/craftoracle/plan_inputs.py`, `tests/test_plan_inputs.py`,
`examples/helmet_life_chaos_res.yaml`, `examples/bow_value_table.yaml`,
`data/prices.example.json`, `data/loadouts/endgame.json`.
Budget25 minutes. Existing engine modules read-only. Standard library only.

## Requirements
1. Files ending .yaml use the JSON-compatible YAML subset: parse with json, explain unsupported
   YAML features in ValueError (no home-grown general YAML parser). `load_spec(path, mod_rows)`
   validates and returns plain `ItemSpec`; `load_loadout(path)` returns `Loadout` including
   price data path resolved relative to loadout. Reject unknown schema_version (use1), unknown
   top-level keys, nonfinite/noninteger/boolean counts, unsupported flags and unknown mod IDs.
   Both data paths must resolve under the repository root determined from this module; reject
   ../ escapes and symlink escapes before read. No external filesystem or network access.
2. Spec fields: schema_version, name, base, item_level, quality, flags (optional six Q9 bools),
   tier_ids (group -> list of lists of IDs, first list tier1), required_mods (list of objects
   group/max_tier), any_of (list of lists of group/max_tier), value_table (group -> map of tier
   integer-as-string to finite value), threshold, values_note, sources. Either required_mods/
   any_of mode OR value_table/threshold mode, never both. Empty/no target is invalid. ID groups
   must agree with source rows, one ID cannot be assigned two tiers/groups. ItemSpec exposes
   `labels: dict[mod_id,str]`, `matches(outcome)`, `utility(outcome)`, and raw fields. Use label
   `group:tier` (split from right); only criteria/value-relevant tiers need labels. Missing
   value-table entry has value0, a stated design assumption. Required-mode utility is1 for
   target and0 for failure; utility-mode sums caller values, not actual PoB DPS. No score-only
   state passed back into transitions. Negative utility allowed; nonfinite rejected.
3. Loadout fields schema_version,name,allowed_actions,allowed_essences,allowed_bench,
   prices_file,budget,base_cost. Price file schema_version,unit,values,bench_recipes,note,sources.
   Finite nonnegative prices/base_cost/budget; missing requested price raises ValueError,
   never0. bench_recipes maps string source_index to currency/quantity maps. Loadout methods
   price(currency), bench_cost(index), permits(actions,essence_id=None,bench_index=None).
   No inference of permission from presence of a price. Ignore no unknown currency silently.
4. Helmet example Royal Burgonet86 quality20, no special flags; required IncreasedLife tier1,
   ChaosResistance tier1, any one FireResistance/ColdResistance/LightningResistance tier1.
   tier_ids: IncreasedLife[[IncreasedLife9]], ChaosResistance[[ChaosResist6]], FireResistance
   [[FireResist8]], ColdResistance[[ColdResist8]], LightningResistance[[LightningResist8]].
   Sources S24 IDs, S27 base, owner's BRIEF. Exact-ID tiers are source-qualified for this base,
   not a general game tier inference. No bench substitute for required T1s.
5. Bow example Crude Bow86 quality20, invented additive utility. Groups LocalFireDamageTwoHand
   tiers [[LocalAddedFireDamageTwoHand10],[LocalAddedFireDamageTwoHand9]], values60,40;
   LocalIncreasedAttackSpeed tiers [[LocalIncreasedAttackSpeed5],[LocalIncreasedAttackSpeed4]],
   values40,25. threshold60; alternate thresholds60/100 used in tests. Values_note explicitly
   invented, not DPS and not exact PoB local-mod multiplication. Source IDs from accepted S24.
6. Example prices are invented chaos-equivalent inputs: chaos1, alchemy.5, scour.5,
   transmute.1, alteration.1, augmentation.1, regal.5, exalted10, divine100;
   essence CurrencyEssenceEnvy3=5, Hatred7/Anger6/Wrath5=3 (price keys full ID allowed).
   bench recipe728/729/730 cost2divine,731/732 cost1divine (S2 benchcosts2962/2963/2964/
   2965/2966, S3 currency index10=divine, mechanics/bench_metamods.md, read2026-09-21).
   A bench40 life recipe is optional only with an explicit sourced quantity; do not invent it.
   Endgame budget100000,base_cost0 (invented placeholder), allowed ordinary actions including
   bench, all listed four Deafening essences, bench728..732. Unsupported families not allowed.
   Names in allowed_essences use full Metadata/Items/Currency/... IDs from data.

## Tests / numbers
- Load committed helmet, outcome(labels IncreasedLife:1,ChaosResistance:1,ColdResistance:1)
   ->true, missinglife/chaos/elemental ->false; all flags false andquality20.
- Bow onlyfireT1 ->60, bothT1 ->100, bothT2 ->65, absentlabels ->0; threshold60 passes
   firstandbothT2; threshold100 onlybothT1. Exactly same outcomes, different predicate.
- bench729 atdivine100 ->200; change input divine2 ->4; missingprice raises; disallowed
   action remains disallowed even if itspriceexists. Scope flags Q9 reject.
- Invalid schema, wronggroup mapping, unknowntier/ID, mixedmodes, nonfiniteprice/threshold,
   ambiguous target, traversal paths fail explicitly. Temporary fixtures inside .pytest_tmp.

Report commit, focused pytest, file paths, numbers, input limitations. No CLI in this task.
