# Veiled modifiers

PoB's `ModVeiled.lua` is the datamined source for veiled modifier definitions. Craft of Exile's method inventory includes Veiled and Veiled Chaos actions and represents an unselected veiled prefix or suffix in its simulator. The exact unveiling choice distribution and item-state restrictions are not yet documented here.

Sources read 2026-09-20: S25 `ModVeiled.lua` lines 5-6, S3 `poec_cmethods.currency.veiled`,
`currency.veiledchaos`, `modunveil` (line 5), `poec_simApplyCraftGO` lines 2294-2298.
Confidence: `datamined` for definitions and `reimplemented-from-CoE` for action inventory.
Selection weights and bench interaction remain Q3/Q9/Q12; no probability example is approved.

S25 key `JunMasterAvoidStunAndElementalStatusAilments1` is a Prefix, level field 1, with
weightKey [body_armour, default] and weightVal [0,0]. Those zeros are data, not evidence that
the corresponding unveil can never be offered: the unveil-pool construction is not yet sourced.
