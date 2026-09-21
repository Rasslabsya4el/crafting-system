# Night policy designs — lead-provisional 2026-09-20

Authority: docs/GOAL.md; ordinary rules in existing basic_currency, bench_metamods,
essences and affix_generation sheets. These are executable policy designs, not new fact sheets.
Prices are explicit caller inputs, never live market estimates. Exact means exact under the
declared provisional source model, evaluated with floating arithmetic.

## Helmet target
Choose ordinary Royal Burgonet (representative armour helmet from the validated class), ilvl86,
quality20 fixed input. Required IDs: IncreasedLife9; ChaosResist6; at least one of FireResist8,
ColdResist8, LightningResist8. They are the top eligible ordinary tiers for this base in S24;
explicit target-ID lists avoid a speculative general tier classifier. Tags do not include
influence or generated-mod tags. Quality is preserved metadata; no damage/defence valuation
or Armourer's Scrap probability model is implied.

Essence Greed7 maps to IncreasedLifeEssenceBootsGloves1 (91..105 life), below this ordinary
130..144 life target. It MUST have zero strict target chance. Deafening Envy3 maps to the exact
ChaosResist6 target; Hatred7/Anger6/Wrath5 map to Cold/Fire/LightningResist8 respectively.
Sources: accepted S22 Essence.lua keys and S24 ModExplicit keys, read 2026-09-21.

## (a) Independent reroll loops
Chaos: normal base first Alchemy, then repeat Chaos until target; to keep a simple geometric
stage with a fixed setup, the policy deliberately does not stop on the setup Alchemy outcome.
State that inefficiency in steps. Expected setup+chaos/p; cost p90 setup+chaos*n90.
Scour+Alchemy: first Alchemy on normal base, subsequent failures Scour then Alchemy.
Cost for N attempts = alchemy*N+scour*(N-1), plus base cost; no scour charged on success.
Essence: normal->rare directly on first attempt, repeat same tier>=5 essence until target.
Forced mod consumes a slot and removes its entire group from the random pool. All three use
the count-mixture distribution from the parameter file; every plan prints its assumption.

## (b) Magic core followed by Regal and Exalted additions
A bounded valid fixed-cycle template: first Transmute the normal base as setup. Each attempt
uses Alteration; if result has one mod, Augment to two; Regal; Exalt three times to six mods.
Then stop on target or Scour, Transmute back to magic and restart. For efficiency this is not claimed best, but it is a real template with explicit
decisions and no paid action after the final stop. The draw schedule is (2,1,1),(4,3,3).
The 1/2 augmentation coin from Alteration's count is independent of this final draw law:
the one-mod branch plus Augment makes the same two sequential capped draws as the two-mod
branch. Thus per-attempt costs are c0=alteration+regal+3*exalt or c0+augment, weights1/2 each,
independent of terminal success; failure additionally pays scour+transmute. Initial setup pays transmute once; the
policy deliberately replaces that setup roll with Alteration, an explicit inefficiency. Use a compound-geometric
cost distribution, not fixed mean cost multiplied by a geometric quantile. Setup/base cost once.
Optional bench finisher only if its concrete sourced modifier can satisfy the remaining
requirement and slot/group gates; never count a low bench life mod as ordinary T1 life.

## (c) Make suffixes, lock/scour, roll one prefix repeatedly
Stage1: repeat Deafening Envy until chaos plus >=1 T1 elemental suffix, exactly3 suffixes and
at most2 prefixes. The cap is necessary to leave space for Suffixes Cannot Be Changed (bench729).
Stage2: each attempt craft that prefix lock, Scour (retains all3 suffixes, removes lock and
all prefixes), then one Exalted Orb. Because all suffix slots are full, that draw is a prefix.
Stop on IncreasedLife9; otherwise exactly1 prefix remains, so the next prefix lock is legal.
There is no full-prefix dead end and no hidden destructive reset of accepted suffixes.
Before first stage2 attempt any existing natural T1 life is deliberately scoured; say so.
Final item has one target prefix and3 suffixes. No final bench is needed for the exact target;
an optional explicit unlocked bench may add utility only when requested and legal.

For Royal Burgonet86, prefix/suffix group intersection is empty in the selected pool; exact
stage2 probability is 1000/39275 (S24 first-match weights). Stage1 and stage2 costs are
independent given this model. Stage2 attempt cost2*divine+scour+exalt (S2 benchcosts2963b1,
S3 currency index10=divine, S11 bench729). Convolve independent geometric costs for p90;
do not add their separate 90th percentiles. Risk of irreversible item destruction is0 within
this ordinary bounded model; currency expenditure and budget exhaustion remain real risks.

## Output requirements
Each policy reports exact stage probabilities, expected attempts per stage, expected total
cost, p90 cost (method explicit), ordered actions and decisions, terminal expected utility,
irreversible risk, rare inputs and all provisional assumptions. Ranking by expected cost
does not erase distinct policies; frontier marking can remove dominated entries from frontier
without preventing the requested ranked table of at least3 available policies.
Loadout must actually allow every action and recipe used. Budget constraints are explicit,
not a promise that expectation guarantees affordability. No parent files or PoB process used.
