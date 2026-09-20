# A crafting oracle next to PoB: a brainstorm with the owner (2026-09-20). A frame, not a spec; nothing starts before the reset.

## The owner's idea (his terms)

Our gear rails are a hard-coded stand-in for the game's crafting. Example: a ring "T1 life + T1 flat accuracy" and a ring
"T1 life + T1 flat life regeneration", same tiers, same weights, the build wants both equally: the system sees them as equal,
while in the game the second is easy and the first may be a thousand times harder, because crafting is paths, not weights
(bench crafts that block mods before an Exalt, "cannot roll attack mods", essences, harvest reforges, fossils, recombinators,
awakener's orb...). Finding HOW to craft an item is a computation of its own. He always wanted a second system: what the build
system itemizes, the crafting system crafts -- or the two agree, so the build asks for items that are a bit weaker but
certainly craftable (not "hundreds of thousands of Chaos Orbs"). It must be as proficient in crafting as the build system is in
PoB, with its own runs and optimal strategies. His worry: a universe the size of PoB's with no PoB -- only Craft of Exile's web
emulator / simulator (data mostly from PoEDB's datamining; harvest weights of unknown origin; recombinators and double
influence maybe absent), and hammering a website is not an option. He noticed with delight that crafting METHODS lock behind
loadouts. A trade-price system is explicitly NOT of interest now.

## The lead's view

**Smaller than PoB.** PoB's size is its damage / defence engine; crafting has no such layer. It is (1) DATA -- mods, tiers,
spawn weights, tags, groups, bench crafts (we already hold PoB's copy: `random_rares` rolls rares with PoB's spawn weights,
`list_item_mods` returns tier ladders with weights; essences / fossils / veiled / eldritch data are believed to be in PoB's
data too -- VERIFY; the rest is datamined: PoEDB, RePoE); (2) about 50-60 ACTION RULES, each a small stochastic transition
"item state -> item states with probabilities" (chaos, exalt, annul, essence, fossil weight multipliers by tag, harvest
reforges, metamods, eldritch currency, fracture, recombinators, awakener's orb, veiled, beast crafts); (3) UNKNOWN NUMBERS
(how many mods a Chaos rolls, harvest weights, recombinator odds) = facts with sources, the D62 process (pending -> the
owner's approval). A few thousand lines; millions of rolls a second locally. Craft of Exile is a REFERENCE FOR TESTS (a few
dozen hand-checked probabilities), never a service in the loop.

**The mathematics in plain words:** solitaire with known odds -- every click has a price and a known outcome distribution; find
the click sequence that is cheapest on average. Single loops (chaos / essence / fossil spam, alt-aug-regal) are a formula
(price / probability, probability exact from the weights). Multi-step strategies = CoE's simulator with the flowchart found by
search over strategy TEMPLATES typed by mechanism ("essence -> prefixes cannot be changed -> reforge", "fracture -> spam",
"recombinator ladder"), each with an exact or Monte Carlo cost; a general solver (a Markov decision process) is research, the
template library is engineering -- start there.

**What it gives the build system (the real prize):** today obtainability is rails ("best of 200 rolls", "tier position
0.35 / 0.50 / 0.57") -- crude stand-ins for the COST OF GETTING the item. With an oracle `cost(item spec, loadout) -> expected
cost + plan`, the gear optimizer solves "maximum build value within the loadout's budget": per slot a frontier of value against
cost, then the budget split across slots as a knapsack -- the place where exact methods FIT (they did not on the tree).
Items that are uncraftable in the owner's sense price themselves out. Loadouts = the list of allowed actions + a budget; the
owner's rulebook matrix is exactly that table.

**Hard parts:** undatamined weights and hidden rules (some numbers will stay "player reports" at lower confidence); the
strategy space; validation without an oracle at scale (a known-answer set: CoE checks + the owner's "this takes about N tries");
per-league upkeep (data with PoB, rules from patch notes).

**Order:** (1) after the reset a GPT research brief: open engines and data (RePoE, GitHub simulators), whether CoE's code is
open, where its harvest weights come from; (2) a prototype oracle for DAY-1 methods only (bench, essences, alt spam) that
replaces the "best of 200" rail with an honest cost; (3) grow by loadout, like the builds. Trade pricing: parked.

## Craft of Exile runs in the visitor's browser (looked at 2026-09-20 from the Browser pane: page load only, no forms)

The page ships its whole application (`/packages/package.js`, ~330 KB compressed) and its data (`/json/data/main/poec_data.json`
with `bitems, bases, bgroups, modifiers, mgroups, mtypes, fossils, catalysts, essences, maeven, aliases, tiers, basemods,
modbases, mdefs`; `poec_affinities.json` ~1.3 MB; `poec_exdata.json`; `poec_common.json`; `poec_prices.json`), and the page holds
54 emulator / calculator functions (`poec_simRollAffix`, `poec_simApplyCraft`, `poec_simRerollItem`, `poec_simRecombinate`,
`poec_computeBestFossils`, `poec_simCheckHReroll`, ...). No web workers, no API calls at load: the computation is client-side
(the simulator tab itself was not clicked through). Recombinators ARE implemented there.

What follows: READING their code to understand each action's rule and the numbers they use (harvest, mod-count distributions)
is the fastest source for our ~50 action rules and a reference for tests. The owner's position (2026-09-20): everything made
for PoE is free to use non-commercially under GGG's policy. The lead's caveat: GGG's policy governs what tools may do with the
GAME, it does not hand a third party's own code to the public (no licence = the author's rights; CoE also runs ads). In
practice it hardly matters: PRIVATE reading and cross-checking is harmless; their JavaScript is tied to their interface, so our
Python engine is a rewrite either way; game facts come from PoB / open exports, numbers CoE derived itself are recorded as
facts with the source "CoE". The line is PUBLIC distribution of their code or compiled data: ask the author first. Task after the reset: read `package.js`, write down every action's rule
and the source of its numbers as a fact table (the D62 format), copying nothing.

