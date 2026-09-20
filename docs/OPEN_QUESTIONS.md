# Open questions (numbered; for the lead and the owner; concrete, answerable)

| id | question | why it matters | status |
|---|---|---|---|
| Q1 | Does Craft of Exile implement Awakener's Orb and the eldritch currencies (the owner doubts it)? | decides where those rules are sourced from | resolved yes: S3 `poec_cmethods.currency.woke` and `poec_cmethods.eldritch`; dispatch in `poec_simApplyCraftGO`; availability is not proof of accuracy |
| Q2 | Should exact calculators use unbiased integer draws instead of CoE's apparent upper-end exclusion? | S3 `poec_rand` line 992 returns integers in [min,max), but `poec_simRollAffix` lines 2489-2490 and `poec_simRemoveAffix` use (1,total,true) with inclusive cumulative ranges. A two-unit pool selects only the first unit; a weight-1 last entry is unreachable for total > 1. | discrepancy; lead decision: do not reproduce the apparent bug; no game probability accepted from this behavior |
| Q3 | Is PoE 3.29 the target ruleset for this prototype (yes/no)? | S1 snapshot is labelled 3.29; S3 contains PoE 1/2, legacy Harvest and recombinator modes. Cache date alone cannot select a ruleset. | open; initial sheets explicitly scope to observed CoE PoE 1 paths, current-patch claims blocked |
| Q4 | Are CoE's normal rare reroll counts 4/5/6 with weights 8/3/1 independently verified? | S3 `numOfAffixes[3]`, line 993; proportions are CoE-derived, not datamined. | unsourced independent corroboration; usable only as `reimplemented-from-CoE` with conditions |
