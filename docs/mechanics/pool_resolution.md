# Mod pool inputs: levels, ordered weights and groups

Status: partial sourced rules; not an implemented general resolver. Read 2026-09-20.
Confidence: `documented` for S26 Wiki mechanics; `datamined` for S1/S24/S27 literal fields.

## Effect and preconditions
For an ordinary random explicit roll, determine which modifiers can enter the draw and their
weights before applying action-specific changes. This sheet covers plain base tags and ordinary
mod-level gates. It does not establish influence, corruption, special-generation or metamod
eligibility. Base tags and modifier tags are separate inputs, not interchangeable labels.

## Sourced steps
1. Apply the mod-level gate to the item's level for ordinary random explicit modifiers. S26
   `Mod Level` explicitly exempts directly granted modifiers such as implicits/enchantments;
   essence-forced mods have their own rules. Character required level is a different quantity.
2. Match the base's active tags against the modifier's ordered spawn-weight entries. The first
   matching entry wins, including a zero. Do not sum weights of all matching tags. S26
   `Spawn weight tag`; PoB preserves this order in `weightKey` and `weightVal`.
3. A selected zero weight excludes that mod from this random pool. A positive weight is a
   relative weight, not a probability until the entire eligible pool is known (S26).
4. Exclude a candidate if it shares any exclusion family with an existing modifier. S26
   `Group/family` allows one or more families per modifier and only one member of a family on
   the object. A literal PoB `group` string has not yet been proven to preserve all game families.
5. Action rules can change weights/eligibility and existing mods can change item tags. The
   current limited projection omits generated tags and weight multipliers. It must not be used
   as a complete ordinary weapon pool without resolving Q16/Q17.

## Numbers and worked examples
These examples resolve one mod's raw spawn weight, not the probability of rolling it.

| Example | Result | Exact source |
|---|---|---|
| Iron Hat + Strength1 | `str_armour` wins: 1000; `default` 0 is not added | S27 `Bases/helmet.lua`, Iron Hat line 6; S24 Strength1 line 5 |
| Crude Bow + Strength1 | only `default` matches: 0 | S27 `Bases/bow.lua`, Crude Bow line 5; S24 Strength1 |
| Iron Gauntlets + IncreasedLife9 | `gloves` wins: 0, despite matching later `default` 1000 | S27 gloves line 6; S24 IncreasedLife9 line 56 |
| Simple Robe + LocalIncreasedEnergyShield11 | `int_armour` wins: 1000 | S27 body line 412; S24 LocalIncreasedEnergyShield11 line 139 |
| ColdResist8 at item level 83 / 84 | level gate excludes / permits consideration | S24 ColdResist8, level 84; S26 Mod Level. Other gates still apply |

Synthetic arithmetic fixture: eligible independent weights 1000 and 250 give probabilities
4/5 and 1/5. A weight multiplier of 10 on the first changes these to 40/41 and 1/41, not an
eightfold chance. This is invented arithmetic, not a two-mod game pool or a fossil rule.

## Conditions, interactions and source discrepancies
S26 distinguishes modifier tags (e.g. attack, life) from spawn tags used to select base weights.
An item's `influenceTags` map is a literal source field, not proof that every listed influence can
be applied together. Prefix/suffix caps and action eligibility remain in their own sheets.

Q16: the same stat/affix/level/weight rows have PoB group `LocalFireDamageTwoHand` versus
PoEDB/CoE `FireDamage`, and PoB `LocalEnergyShield` versus `BaseLocalDefences`. Do not silently
rename them or use the PoB group as the canonical game exclusion family. The cross-check must
report these differences separately from numerical agreement.

Q17: S24 LocalAddedFireDamageTwoHand1 (line 438) has `weightMultiplierKey/Val` and generated
`tags = { has_attack_mod }`, absent from our projection. Bow default multiplier is 100 in the
literal table; semantics/units for general use still require a source. A sample match for bows
does not validate other weapons or dynamic tag transitions.

## Open questions
Q3 target patch; Q8 upstream revision; Q9 eligibility; Q16 exclusion-family correspondence;
Q17 generated tags and weight multipliers. No no-match default, tier ranking, or general resolver
behavior is guessed here.
