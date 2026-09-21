# Quality and catalysts

Read 2026-09-20. Confidence: `documented` S46/S47; old increment implementation
`reimplemented-from-CoE` S3. Quality affects item value as well as later socket/link actions;
it must not be omitted from a policy state merely because an affix target ignores it.

Ordinary jewellery quality-state API and finite finishing policy accepted14be5e9.
It implements the S47 law below, with an independent direct sampler and exact application,
final-state and cost distributions. `python -m craftoracle quality --base "Paua Amulet"
--item-level 86 --catalyst fertile --target-quality 20 --price 2 --json` exposes the policy.
Special flags, unique/Tainted/side-specific catalysts and modifier-magnitude evaluation
remain outside that implementation; supplied prices are not game or market facts.

## Effect, preconditions and steps
S46 catalysts apply a quality type to rings, amulets and belts, increasing matching implicit
and explicit modifier magnitudes according to mod tags. Ordinary cap is 20%. Switching catalyst
type discards previous quality and starts the new type from zero before the new application.
S46 also lists prefix/suffix-specific catalysts; their type is not a conventional mod tag.
Tainted Catalyst explicitly targets corrupted jewellery and randomises type and amount;
its probability distribution is unsourced here, so ordinary catalyst rules do not substitute.

1. Establish item class, item level, uniqueness, quality type and current quality (S46/S47).
2. For ordinary currency, determine the level-dependent quality increment and cap it.
   S47 says unique items always receive 1 percentage point. Its formula and full probability
   table were read2026-09-21; the documented adjacent-integer distribution is recorded below.
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
Magnitude rounding, tag overlap and Tainted Catalyst odds remain unsourced. Source-specific
examples can be fixtures only at their stated scope.

## Current increment distribution (read2026-09-21)
Official S74,3.25 Item Quality rework, explicitly lists Catalysts and removes rarity dependence
for non-unique items in favour of ilvl. This resolves owner14 without an in-game test.
S47 Amount gives `f(i)=max(1,min(30*exp(-i/30)-0.3,20))`. Its table documents the two adjacent
integer increments: floor(f) with probability ceil(f)-f, ceil(f) with probability f-floor(f).
At integer f there is one outcome with probability1. This formula/table is `documented`,
not a datamined probability function. Cap resulting quality at20; switching ordinary
catalyst type first resets existing quality, and unique items still receive exactly1.
Examples from the table: ilvl1..11 ->20 always; ilvl45 ->6/7 with rounded probabilities
0.6061/0.3939; ilvl86 ->1/2 with0.5934/0.4066; ilvl95..100 ->1 always.
Use the formula, not the four-decimal printed probabilities, for calculations. Quality gain
rounding and subsequent modifier-magnitude rounding are distinct; the latter remains Q23.
S3's5/2/1 rarity increments are a historical discrepancy, not an alternative current default.

S46 re-read at the same revision1675910 on2026-09-21. Its3.15 version note states that
catalyst quality no longer changes modifier-generation chances and is no longer removed
by the formerly consuming currency actions. Therefore current ordinary rolls preserve this
quality metadata without a weight boost. Its regular catalyst list is: Abrasive(Attack),
Accelerating(Speed), Fertile(Life/Mana), Imbued(Caster), Intrinsic(Attribute),
Noxious(Physical/Chaos Damage), Prismatic(Resistance), Tempering(Defence),
Turbulent(Elemental Damage), Unstable(Critical). Dextral/Sinistral target suffixes/prefixes
and have separate Mirage acquisition conditions. These displayed effect descriptions do
not establish exact stat-magnitude rounding or every internal tag mapping.
Full rendered text cached at `sources/raw/research/wiki-catalyst-2026-09-21.txt`.

Lead-derived policy arithmetic from S47 (2026-09-21): at ilvl86, increment mean
1.4066471503830453; P(+1)=0.5933528496169547, P(+2)=0.40664715038304533. Repeatedly apply
the same type from quality0 to20, clipping at20. A backward finite recurrence on quality
states gives expected14.423723570517014 applications and exact p90 of16. At quality19,
one application certainly reaches20. These are formula-derived results, not player tests.
With price c, expected spend is14.423723570517014*c and p90 spend16*c; the price is an input.

Sources: S46 https://www.poewiki.net/index.php?title=Catalyst&oldid=1675910;
S47 https://www.poewiki.net/index.php?title=Quality&oldid=1673652, Amount/Effect on items;
S3 package.js:2318-2325. Read 2026-09-20.
