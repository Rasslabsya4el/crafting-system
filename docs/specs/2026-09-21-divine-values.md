# Spec: bounded ordinary Divine integer-value rerolls

Dispatch after core and preceding stretch items are merged/green.
Worktree `.worktrees/divine-values`, branch `w-divine-values`.
Allowed `src/craftoracle/divine.py`, `tests/test_divine.py`, README usage paragraph only.
Budget20minutes. No parser framework or changes to item-model/actions APIs.

## Sources / lead rule
Existing mechanics/basic_currency.md Divine row and worked example5. Cached S3
poec_simRerollValues lines2529-2540, read2026-09-21: original side locks skip protected
affixes; each eligible integer range rerolled inclusively; fixed values and identities retained.
Confidence reimplemented-from-CoE, unbiased math per GOAL Q2. No implicit/quality/tier reroll.
Q9 rejects fractured/corrupted/influenced/synthesised/mirrored/split before any value processing.

PoB S24 ModExplicit.lua key IncreasedLife9 line56: +(130-144) maximumLife;
ChaosResist6 line1001: +(31-35)% chaos; FireResist8 line970: +(46-48)% fire.
Those are datamined ranges, not utility/DPS values. S11 bench728/729 side locks already known.

## Requirements
1. Expose a frozen `RolledItem(item:ItemState, values:tuple[tuple[str,int],...])` representing
   exactly one integer range value per supported ranged affix, canonical source-item order.
   `divine_distribution(rolled,data)` returns dict[RolledItem,float].
   `apply_divine(rolled,data,*,rng:random.Random)` returns a new RolledItem using the passed RNG.
   No global RNG, no prices needed for an action. Item identities/rarity/tier remain unchanged.
2. Validate concrete item through the accepted action validation (import helpers if needed,
   without refactor); rarity non-normal and at least one explicit. Validate values keys exactly
   match ranged affix IDs, no duplicates, integers without bool and within source range.
   Locked values are still validated and retained. Bench refs use data.bench index identity.
3. Bounded range extraction from PoB row stat_text: exactly one stat string containing exactly
   one parenthesized integer range `(lo-hi)` and no other numeric tokens. Non-numeric strings
   (e.g. bench locks) have no value. Accept signed endpoints if parsed unambiguously, lo<=hi.
   Fixed numeric/no-range, decimals, multiple ranges/lines and unrelated numeric tokens raise
   NotImplementedError('unsupported Divine value shape: <id>') rather than guessing semantics.
   This is an explicit implementation boundary, not a claim those game mods cannot be Divined.
4. Enumerate independent uniform integer choices for unprotected ranged affixes. Keep locked
   values unchanged; no ranged choices -> deterministic same RolledItem. Cap joint state count
   at100000 before allocating, raise NotImplementedError('Divine distribution work limit').
   Sampling stays available above that bound and draws each inclusive range via rng.randint.
   Identity-level action_distribution remains unchanged; callers use this value-specific API.
5. README short example and limitations, no CLI expansion or claims general stat parser works.

## Tests / numbers to report
- Synthetic range10..12 ->3 outcomes, mass1/3 each, Evalue11, tier/ID changeprobability0.
- Two synthetic ranges10..12 and1..2 ->6 outcomes, mass1/6 each; P(first12,second2)=1/6.
- Real RoyalBurgonet86 Life9 plusChaos6 ->75 outcomes, each1/75; Evalues137/33;
  P(life>=140 andchaos>=34)=5/15*2/5=2/15. Three values includingFire8 ->225 outcomes.
- Addbench728 suffix lock of prefixes: Life current132 unchanged, Chaos5 possiblevalues;
  addbench729 prefix lock of suffixes: Chaos current31 unchanged, Life15 values. Use separate
  legal items, not both crafts without multimod. Locks without ranged stats need no fakevalue.
- Same seed20260921 replay equality and correct ranges;5000 direct samples agree with event2/15
  under Hoeffding bound sqrt(log(2/.001)/(2*5000)). Never compare samples to a memorized sequence.
- Wrong rarity/Q9flags, duplicate/missing/out-of-range values rejected; unsupported decimal/
  multi-stat syntax rejects explicitly; a synthetic100001-point range exact fails before work
  but direct sample succeeds. Report exact counts, probabilities, focused pytest and commit.
