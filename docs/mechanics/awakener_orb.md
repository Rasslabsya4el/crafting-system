# Awakener's Orb

Craft of Exile's method inventory contains an Awakener action and describes the action as combining two influenced items. The cached basics page states that the result can carry up to one influenced modifier from each input. Those observations establish the action family and a high-level invariant only; they do not establish the complete selection, base, or influence eligibility algorithm.

The exact influenced-mod pool, duplicate-group handling, base selection, and failure cases are open. No calculator may claim a probability for this action until those rules are sourced.

Sources read 2026-09-20: S3 `package.js`, `poec_cmethods.currency.woke` line 5 and
`poec_simApplyCraftGO` lines 2299-2301; S13 CoE basics prose. Confidence:
`reimplemented-from-CoE` only; CoE prose is not `documented` under D5. Open Q3/Q9/Q12.

The observed dispatch calls `poec_simAwaken` for the supplied donor, records the second influence,
sets rare rarity and calls the reroll routine with the selected influenced modifiers. The helper's
selection algorithm is still unaudited. No numerical probability example is approved; do not
implement this placeholder as if it were a completed rule sheet.
