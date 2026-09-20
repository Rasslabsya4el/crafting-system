# Basic currency: Transmutation through Divine

Status: first reviewed sheet for ordinary PoE 1 items; not a complete current-patch contract.
Confidence: `reimplemented-from-CoE`. Sources read 2026-09-20: S3 `poec_cmethods.currency`,
`poec_simApplyCraftGO` (lines 2254-2280), S12 `checkOmensForMethod` (false),
S13 Crafting Currency, S14 interaction table. Probabilities use [affix generation](affix_generation.md).

## Effect, preconditions and rule steps
Each row is its own action. Requirements are from S3's method metadata; normal/magic/rare
are rarity values, and `is_rare` is a base-support flag rather than a second rarity test.
The emulator also blocks ordinary actions on corrupted items in `poec_simCheckReasons`.
Full destroyed/mirrored/split applicability still needs a separate audit (Q9).

| action/key | preconditions | observed PoE 1 steps |
|---|---|---|
| Transmutation / `transmute` | normal | Set magic; reroll at magic caps; ordinary count 1 or 2 at 1/2 each. |
| Alteration / `alteration` | magic | Reroll magic; retain fractures and side locks through `metaprot=true`; ordinary target-count table as above. |
| Augmentation / `augmentation` | magic, open affix | Add 1 eligible weighted modifier, respecting available side and attack/caster blocks. |
| Regal / `regal` | magic, base `is_rare` | Set rare, then add 1 eligible modifier; keep existing modifiers. |
| Alchemy / `alchemy` | normal, base `is_rare` | Set rare and reroll; ordinary six-slot target counts 4/5/6 at 2/3,1/4,1/12. |
| Chaos / `chaos` | rare, base `is_rare` | Reroll rare with `metaprot=true`; count table is conditional on caps. |
| Exalted / `exalted` | rare, base `is_rare`, open affix | Add 1 eligible weighted modifier; error if no mod can be added. |
| Annulment / `annul` | non-normal, at least 1 affix | Remove 1 eligible non-fractured modifier; apply side locks and attack/caster removal protection. |
| Scouring / `scour` | non-normal | Clear unprotected explicits, preserve fractures and locked sides, then determine rarity from retained affixes. |
| Divine / `divine` | non-normal, at least 1 affix | Reroll numerical values within existing ranges; skip fractured, veiled placeholders and locked-side mods; retain mod identity and tier. |

## Exact shared numbers
Count distributions and their limitations are in `affix_generation.md`. Addition/removal calls
request 1 modifier in these ordinary branches (S3 dispatcher; S12 disables omen branches).
Annul candidate weights are 1000 each, and `poec_simCatToRWeight` returns that weight unchanged;
the intended probability is 1/N eligible candidates, subject to the literal RNG defect Q2.
Integer Divine ranges use `[low, high+1)` so both endpoints can occur (S3 `poec_simRerollValues`).
No currency exchange rates are asserted.

## Metamod interactions and exceptions
- A side lock preserves existing mods; it is not a blanket prohibition on adding to an empty slot
  of that side. Augment/Regal/Exalt rely on `poec_simRollAffix`, which filters attack/caster tags
  but not `nchg_pre`/`nchg_suf` for additions (S3; S14 marks side-lock columns not applicable).
- Chaos reconstructs metamods from retained affixes. A cannot-roll attack/caster suffix therefore
  affects the replacement pool only if retained; S14 specifies conjunction with suffixes cannot
  be changed. Do not apply a removed metamod to the new item.
- Scouring does not always produce normal rarity. S3 `poec_simClearItem`: retained counts above
  one on either side yield rare; otherwise normally magic; a fracture with one prefix and one
  suffix yields rare, and special-base handling has further exceptions.
- S3 `poec_remCatQuality(amount)` is empty in this snapshot. Calls containing 2 or 20 are not
  evidence that catalyst quality is consumed. The old-looking call sites alone establish no rule.
- Foulborn variants exist in the method tree and are outside this ordinary-currency sheet.
  Their higher-tier selection requires a separate sourced treatment, not an alias to normal orbs.

## Differences and worked examples
S13 describes Scouring/Chaos as removing all explicits. S3/S14 retain specific protected mods:
the prose is an unprotected-item explanation, not an override of the conditional rules above.
Current-game validation is pending (Q3/Q5/Q9); intended weighted probabilities must not copy Q2.

1. A magic item with 1 prefix and no suffix, ordinary 1+1 caps: Augment leaves 2 explicits,
   with the added mod a suffix. Source S3 `poec_simRollAffix` and caps in S13 Item rarity.
2. A magic item with 1 prefix and 1 suffix becomes a rare with 3 explicits after a successful
   ordinary Regal, assuming at least one legal candidate. Source S3 Regal dispatcher.
3. A rare with 2 prefixes plus the suffix "Prefixes Cannot Be Changed": Scour retains the
   2 prefixes, removes the lock and leaves rare rarity. Sources S11 and S3 `poec_simClearItem`.
4. Synthetic Annul input: 1 fracture and 3 eligible ordinary affixes. Exactly 1 of the eligible
   affixes is the desired removal: intended success 1/3; fracture removal 0. S3 candidate filter;
   equal-weight mathematical calculation, not literal CoE sampling.
5. Synthetic Divine range 10..12 without locks: 3 values, each 1/3 under the source's integer
   range sampler; tier changes 0. Range chosen for arithmetic, not a PoE modifier claim.

## Open questions
Q2, Q3, Q4, Q5 and Q9. Engine/test implementation waits for a bounded worker spec.
