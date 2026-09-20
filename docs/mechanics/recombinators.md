# Recombinators

Craft of Exile exposes a recombination action and rejects bases it considers non-recombinable. The cached implementation is only an inventory pointer at this stage. The resulting modifier-selection, inheritance, fracture, and failure rules are not inferred from the JavaScript.

Source read 2026-09-20: S3 `package.js`, `poec_simRecombinate` line 1888 and base check
line 2028. Confidence: `reimplemented-from-CoE` for branch existence only. A complete rule sheet
needs interpretation of the cached algorithm and ruleset validation (Q3/Q9/Q12); no numerical
rule example is approved.
