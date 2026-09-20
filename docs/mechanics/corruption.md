# Corruption

Craft of Exile exposes a corruption action and a dedicated corruption outcome function. The action is item-state changing and must model each supported outcome explicitly. This phase records only that the branch exists; it does not assign outcome probabilities or eligibility from memory.

Source read 2026-09-20: S3 `package.js`, `poec_simCorrupt` line 2805 and
`poec_cmethods.currency.vaal` / `corruption_altar` line 5. Confidence: `reimplemented-from-CoE`
for branch existence only. Outcomes, eligibility, irreversibility and their weights remain
unsourced under Q3/Q9/Q12. No numerical rule example is approved.
