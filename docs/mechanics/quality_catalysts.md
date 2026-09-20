# Quality and catalysts

Read 2026-09-20. Confidence: `documented` S46/S47; old increment implementation
`reimplemented-from-CoE` S3. Quality affects item value as well as later socket/link actions;
it must not be omitted from a policy state merely because an affix target ignores it.

## Effect, preconditions and steps
S46 catalysts apply a quality type to rings, amulets and belts, increasing matching implicit
and explicit modifier magnitudes according to mod tags. Ordinary cap is 20%. Switching catalyst
type discards previous quality and starts the new type from zero before the new application.
S46 also lists prefix/suffix-specific catalysts; their type is not a conventional mod tag.
Tainted Catalyst explicitly targets corrupted jewellery and randomises type and amount;
its probability distribution is unsourced here, so ordinary catalyst rules do not substitute.

1. Establish item class, item level, uniqueness, quality type and current quality (S46/S47).
2. For ordinary currency, determine the level-dependent quality increment and cap it.
   S47 says unique items always receive 1 percentage point. Its general formula/table has
   a probability distribution for fractional increments; that rounding distribution has
   not yet been independently established (Q23). Do not guess deterministic rounding.
3. Apply the magnitude effect to the appropriate local stats or tagged modifiers. S47 says
   weapon physical damage and armour defences use a separate multiplicative quality factor.
4. Harvest quality-replacement enchantments change what quality grants, not its effect on
   socket/link chances (S47). Full currency eligibility for special modifiable-corrupted
   items remains Q9.

## Numbers and worked examples
- S47's worked armour example: base 100, flat +50, increased armour 90%, quality 20% gives
  (100+50)*1.9*1.2 = 342. This is a documented example, not a full PoB stat evaluator.
- An ordinary unique at 18% needs 2 standard 1-point applications to reach 20%, subject to
  that currency's applicability (S47 Amount). This does not apply to Tainted Catalyst.
- S47: 20% weapon quality multiplies physical damage by 1.20. It is not an added 20 percentage
  points to another increased-damage sum. Other damage types require their own rule.
- S3 2319-2324 instead increments normal/magic/rare quality by 5/2/1 and caps at 20;
  its zero-to-cap counts are 4/10/20. These are **CoE-only legacy examples**, not current prices.

## Differences and unknowns
Q23 records level-based Wiki versus rarity-based CoE increments. The `refined_catalyst` shared
branch must not establish PoE1 availability. S3's quality-consumption function is empty; old
calls to it do not prove that adding/removing mods consumes catalyst quality.
Precise fractional quality rolls, magnitude rounding, tag overlap and Tainted Catalyst odds
remain unsourced. Source-specific examples above can be used as fixtures only at their stated scope.

Sources: S46 https://www.poewiki.net/index.php?title=Catalyst&oldid=1675910;
S47 https://www.poewiki.net/index.php?title=Quality&oldid=1673652, Amount/Effect on items;
S3 package.js:2318-2325. Read 2026-09-20.
