# Phase 0 coverage and remaining uncertainty

Read/assembled 2026-09-20. This checklist evaluates the knowledge-harvest exit in BRIEF,
not whether a full crafting engine exists. A researched sheet may explicitly leave an
unsourced branch unsupported; its existence never certifies exact current probabilities.

## Required action sheets
All 20 named required actions/families in the exit paragraph have effect, preconditions,
source-qualified steps/numbers, conditions/metamods, CoE comparison, numeric examples and
question IDs. The ten basic currencies share one sheet; eleven sheet files cover the twenty.

| required coverage | evidence | unresolved before dependent implementation |
|---|---|---|
| 10 basic currencies | mechanics/basic_currency.md + affix_generation.md | current special-item flags, count-table corroboration Q4/Q9 |
| Bench + five metamods | mechanics/bench_metamods.md | Harvest retention Q6, historical cost mismatch Q7 |
| Essence | mechanics/essences.md | special essences / complete eligibility Q9/Q12 |
| Fossil/resonator | mechanics/fossils_resonators.md | disputed stacking Q13, special outcomes Q12 |
| Current Harvest reforge/add-remove | mechanics/harvest.md | post-3.27 exact flag retention Q6; additional tags Q26 |
| Eldritch | mechanics/eldritch_currency.md | Conflict relative-tier probabilities Q11 |
| Awakener | mechanics/awakener_orb.md | conflicting selected-mod survivor Q20 |
| Fracture | mechanics/fracturing.md | full eligibility / independent equal-selection proof Q9/Q12 |
| Veiled/unveil | mechanics/veiled.md | current curated offers/weights Q12 |
| Recombinator | mechanics/recombinators.md | internally inconsistent count table Q21, CoE differences Q22 |
| Corruption | mechanics/corruption.md | detailed implicit/socket outcomes, exception flags Q9/Q12/Q18 |

Additional sheets cover beast crafting, Dominance, influence orbs, Blessed, synthesis and
quality/catalysts. Shared sheets cover pool resolution and 3.29 changes. INDEX links them all.
Q23-Q25/Q27 retain source conflicts found during this expansion.

## Cached material and data work
- 12 public CoE files fetched once (S2-S9,S12-S15); later work used only the cached bytes.
  No scripts from those files were executed and none of their code/compiled data entered src/data.
- Frozen method inventory: 95 nodes, 84 leaves, 13 custom subsets. Its method names and
  restrictions are source-local, not a claim all methods exist in the current game.
- CoE calculator exact/extrapolated branches and simulator routing/batch/result/cost paths
  are described in coe-calculator-and-policies.md. Q2/Q14/Q28 constrain future calculators.
- S7 guides file is a directory of 52 external references: 37 video, 15 written, dated
  2022-01-23 through 2023-09-26. Lead read its full JSON structure and titles. It has metadata
  fields (including source URL and league), not article bodies or verified recipes. No fact was
  inferred from a linked title; external content has not been represented as read evidence.
- Base data: five target/sample classes, 375 source occurrences/371 names. This is the selected
  scope needed for the helmet/bow demo and five-class cross-check, not all PoB Bases files.
- Cross-check: 54 modifiers over five classes, all numeric/side comparisons agree; 21 group
  label differences remain separate question rows. Raw PoB single group is not canonical proof.
- Weighted families accepted in 375528a: 10555 records / six tables, all 15 fields independently
  checked by the lead. Literal stat strings, optional tags/multipliers and fractional statOrder
  retained; full stat/range interpretation and group semantics remain future resolver work.
- Bench/essence accepted in 8d49e8f: 732 bench rows, 105 essence rows, 2310 class-to-mod links;
  622 distinct referenced ModExplicit IDs, none missing. Every record independently checked.
- Combined main suite: 78 tests passed in under one minute. Worker reports and acceptance are
  recorded in WORKERS/STATE. Ignored snapshots are required for the snapshot checks.

## Catalogue expansion from the Wiki Crafting overview
S57 https://www.poewiki.net/index.php?title=Crafting&oldid=1697718, read 2026-09-20.
This is an inventory source only: more specific pages contain conflicting eligibility wording
(Q29). The entries below are discoverable research backlog, not approved executable rules.

| family found beyond the original core | treatment |
|---|---|
| Chance/Binding, Foulborn currency, Ancient/Mirror and unique transformations | catalogue-only; require action-specific sheets before use |
| Sockets/links/colours, relevant Omens, tainted socket currency | catalogue-only; loadout friction is not yet modelled |
| Sacred Orb and base defence percentile | catalogue-only; preserve distinction from affix rolls |
| Oils, Heist/flask enchantments, Refracting Fog, gem/map crafts | catalogue-only; outside the initial ordinary-equipment distribution slice |
| Memory strands, Remembrance/Unravelling | catalogue-only; future state transitions need full sources |
| Reflecting Mist and Hinekora's Lock | catalogue-only; irreversible branching/preview information must be explicit |
| Allflame currencies/Ducats and Intangibility | catalogue-only; current league availability is not permission to guess ghost-copy odds |
| Rog, Genesis Tree and reward generation | catalogue-only; broader search/template work |
| Historic Harvest, Scourge, Necropolis, Crucible and removed synthesis/splitting | preserve inventory/version provenance; never silently enable from cached labels |

The brief explicitly prefers depth and honest unknowns over a complete-looking guess.
Research closure therefore means the required sheets/data are reviewable and unknown branches
have named blockers. It does not mark all optional families or source contradictions resolved.
Before Phase 1, any used rule receives a bounded tests-first spec with the BRIEF 3b distribution
contract; uncertain paths must raise NotImplementedError with their question ID.

## Exit review
Phase 0 knowledge-harvest exit met on 2026-09-20: 20 fact sheets plus INDEX, 62 registered
sources, the required named families, deterministic selected-data builders and the 54-mod /
five-class comparison. Target ordinary PoE 3.29 confirmed by the owner (Q3/D11). The original
54-row comparison still uses the initial narrow explicit projection; the new literal family
projection adds fields without retroactively claiming new cross-source agreement.

This is a reviewed research baseline. Optional catalogue expansion and unresolved rules stay
visible in TASKS/OPEN_QUESTIONS; no general item resolver or crafting calculator is implemented.
