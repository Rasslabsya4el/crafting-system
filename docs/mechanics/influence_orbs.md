# Influence Exalted orbs and influence state

Read 2026-09-20. Confidence: `documented` S48/S49; algorithm details `reimplemented-from-CoE` S3.
An influence orb adds its influence and one modifier from that influence's pool. Influence
state must be retained separately from whether the item currently has an influenced modifier.

## Preconditions and steps
1. S48's Crusader orb requires high-level rare equipment with no influence; it excludes
   synthesised, fractured and eldritch-implicit items. A free legal affix slot is required
   by S3 method metadata and shared addition logic. A precise numerical ilvl gate needs an
   independently verified current tooltip; S48 itself says high-level, not a number.
2. S49 lists the six influence types and their corresponding orbs, including Shaper/Elder.
   Do not turn S49's broad 'different influence' sentence into permission to add the same
   influence again: S48's item-specific wording is stricter. This wording conflict is Q27.
3. S3 2279 sets influence, restricts the draw to its mod group and adds exactly one mod:
   Shaper=2, Elder=3, Crusader=4, Hunter=5, Warlord=6, Redeemer=7. These numbers are CoE IDs.
   It uses existing group/capacity/level filters and attack/caster blocks. Side locks do not
   grant extra capacity or prevent filling otherwise open slots.
4. S49: Scouring preserves influence; later rerolls do not guarantee an influenced explicit.
   Ordinary items have one influence; Awakener gives two. Astrolabe Amulets are an explicit
   six-influence exception, not permission to model every item with the ordinary two-cap rule.

## Examples, conditions and comparison
- S49's six ordinary influence types permit C(6,2)=15 unordered dual combinations. This
  count does not cover Astrolabe's exception or give relative acquisition probabilities.
- Under S3 addition, 4 existing legal affixes become 5; a synthetic restricted pool with
  weights 1 and 3 gives intended added-mod probabilities 1/4 and 3/4. Q2 forbids copying
  the literal weighted RNG endpoint bug. No real mod weight is invented in this example.
- A Scoured influenced item has 0 ordinary explicits but retains its influence (S49).
- S3's catalyst-consumption call at 2279 is a no-op in this snapshot; do not charge lost quality.

Q9/Q12 cover remaining item flags and influence mappings; Q27 covers the Wiki wording and
exact orb gates. Frozen metadata alone is insufficient to declare all six current item-specific
eligibility matrices identical. Pool_resolution.md covers ordered weights and exclusions.

Sources: S48 https://www.poewiki.net/index.php?title=Crusader%27s_Exalted_Orb&oldid=1683018;
S49 https://www.poewiki.net/index.php?title=Influenced_item&oldid=1635654; S3 package.js:2279,
2558-2559 and method metadata line 5. Read 2026-09-20.
