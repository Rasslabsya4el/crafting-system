# Port plan: the PoE1 planner to PoE2

Date: 2026-11-24. PoE1 side: `main` at 58bd5ad7 (3.29.3.3). PoE2 side: game data 0.5.5.10, patch 0.5.5h. A proposal for a later port, not a decision: no owner rule covers PoE2 yet. **PoE2 1.0 ships on 2026-12-11 with a new crafting system ("Reforging": Crimson Iron replaces unwanted mods with fractured ones; blood materials); the port should start from the 1.0 data, after this research is refreshed against the 1.0 patch notes** (re-pin and re-derive: `DATA-PLAN.md`, last section).

Inputs: `docs/poe2/METHODS.md` (P2 rows), `docs/research/2026-10-30-crafting-methods-inventory.md` (M rows), `src/crafting_system/actions/`, the claims in `docs/poe2/claims/`.

## 1. PoE1 method → PoE2 counterpart

Kinds: **same** (one action class can serve with PoE2 data), **changed** (a counterpart exists, the rule differs), **gone** (no counterpart in 0.5), **new** rows are in section 2.

| PoE1 | Method | PoE2 | Kind | How |
|---|---|---|---|---|
| M-01 | Transmutation | P2-01 | changed | three grades; the Greater/Perfect have a lowest modifier level; always 1 mod (PoE1: 1 or 2) |
| M-02 | Alchemy | P2-04 | changed | takes normal **or magic**; exactly 4 mods (PoE1: 4/5/6 at 8:3:1) |
| M-03 | Regal | P2-03 | changed | three grades with a lowest level |
| M-04 | Alteration | – | gone | no magic reroll; a magic item is rerolled only by Annulment + Augmentation |
| M-05 | Augmentation | P2-02 | changed | three grades |
| M-06 | Exalted | P2-05 | changed | three grades; omens change side and count |
| M-07 | Chaos | P2-06 | changed | **one mod out, one mod in**, not a full reroll; three grades; Whittling/Erasure omens pick the removed mod |
| M-08 | Annulment | P2-07 | same | omens restrict the side or to desecrated |
| M-09 | Scouring | – | gone | nothing returns a rare to normal; a failed rare is bought again or reworked mod by mod |
| M-10 | Divine | P2-08 | same | + Blessed (implicits) and Sanctification (×0.78–1.22, locks) omens |
| M-11 | Essences | P2-10, P2-11 | changed | Lesser–Greater: magic → rare keeping the magic mods (PoE1: normal → rare with a fresh fill); Perfect and corrupted: on a rare, remove 1 random + add the essence mod (PoE1: a full reforge) |
| M-12 | Fossils | – | gone | |
| M-13 | Harvest reforges | – | gone | the closest is Catalysing Exaltation (tag-weighted add) |
| M-14 | Fracturing Orb | P2-09 | same | ≥ 4 mods, 1 random; 1.0 adds fracture-by-Reforging |
| M-15 | Bench crafted mods | – | gone | PoE2's "crafted" mods (emotions on jewels, some runes) are not a bench; at most 1 crafted mod per item |
| M-16 | Bench metamods | – | gone | omens play their part (side locks per action instead of a mod on the item) |
| M-17 | Bench rerolls | – | gone | Chaos Orb is already a one-mod reroll |
| M-18 | Bench remove crafted / rarity reroll | – | gone | |
| M-19 | Buy item | P2-18 | same | prices in Exalted/Divine; the trade site and the Currency Exchange |
| M-20 | Blessed Orb | P2-23 | changed | an omen on a Divine Orb |
| M-21 | Influence Exalts | – | gone | |
| M-22 | Dominance | – | gone | |
| M-23 | Eldritch Embers/Ichors | – | gone | |
| M-24 | Eldritch currency | – | gone | |
| M-25 | Orb of Conflict | – | gone | |
| M-26 | Veiled orbs and unveil | P2-20, P2-21 | changed | desecration: a bone adds one unrevealed mod; the reveal is pick 1 of 3; omens shape both |
| M-27 | Orb of Chance | P2-46 | changed | uniques only; out of scope as in PoE1 |
| M-28 | Catalysts | P2-25 | changed | quality also feeds Catalysing Exaltation's weights |
| M-29 | Harvest add/remove by tag | – | gone | |
| M-30, M-31 | Harvest element swaps | P2-28 | changed | Fluxes convert every resistance mod of an item to one element |
| M-32 | Harvest influence | – | gone | |
| M-33 | Beast add prefix remove suffix | – | gone | Chaos + Erasure/side omens come close |
| M-34 to M-40 | Other beasts | – | gone | |
| M-41 | Vendor recipes | P2-30 | changed | reforging bench 3-to-1 (essences, runes, emotions, waystones) is an input source |
| M-42 | Sacred Orb | – | gone | |
| M-43 | Awakener's Orb | – | gone | |
| M-44 | Recombinators | P2X-01 | gone (disabled 0.5.0) | the data remains (`RecombinableClasses`); ADR-0033 would apply if it returns |
| M-45 | Beast imprint | – | gone | Hinekora's Lock gives a preview instead (P2-19) |
| M-46 | Kingsmarch disenchanting | – | gone | |
| M-47 | Vaal Orb | P2-32, P2-33 | changed | outcomes differ (augment socket, value multiply on uniques); odds unpublished |
| M-48 | Locus double corruption | P2-34 | changed | Architect's Orb, destroys or modifies |
| M-49 to M-56 | Tainted currency | P2-35, P2-36 | changed | Orbs of Sacrifice and Vaal Infusers are the corrupted-item crafts |
| M-57 | Bench on corrupted | – | gone | |
| M-58 to M-63 | Memory Strands, Foulborn | – | gone | the lowest modifier level of Greater/Perfect orbs and Ancient bones is the PoE2 "tier tilt" |
| M-64 | Genesis Tree | P2-25 (source) | changed | gives jewellery, catalysts and currency: a start-item and input source |
| M-65 to M-71 | Sockets, links, colours, socket omens | P2-40, P2-41 | changed | augment sockets (Artificer's Orb, max 1–2) and augments; no links or colours |
| M-72 | Safehouse bench | – | gone | |
| M-73 | Hollow fossil socket | – | gone | |
| M-74 | Quality currency | P2-26 | same | |
| M-75, M-76 | Tempering, Tailoring | – | gone | corruption enchantments and Orbs of Sacrifice are the nearest |
| M-77 | Harvest quality enchants | – | gone | |
| M-78 | Flask enchants | – | gone | |
| M-79 | Anointing | P2-45 | changed | instilling amulets with three Liquid Emotions |
| M-80 | Hinekora's Lock | P2-19 | same | |
| M-81 | Mirror | P2-48 | same | out of the planner |
| M-82 | Reflecting Mist | – | gone | |
| M-83 | Rog | – | gone | |

**Count:** of the 83 PoE1 methods M-01 to M-83, 7 map **same** (M-08, M-10, M-14, M-19, M-74, M-80, M-81), 33 **changed** and 43 are **gone** (the recombinator, M-44, counted as gone while disabled). PoE2 adds the methods of section 2 with no PoE1 counterpart.

## 2. New in PoE2 (no PoE1 row)

P2-12 Alloys; P2-13 to P2-17 omens of the core orbs and essences; P2-22 desecration omens; P2-24 Sanctification; P2-27 Liquid Emotions on jewels; P2-29 reforging bench (equipment); P2-31 Verisium runeforging; P2-35 Orbs of Sacrifice; P2-36 Vaal Infusers; P2-37 Vaal Cultivation Orb; P2-38 Vaal Siphoner; P2-39 Essence of Insanity; P2-42 Core Destabiliser; P2-43 Orb of Extraction; P2-44 Jeweller's Orbs on skills; and in 1.0 the Crimson Iron Reforging.

## 3. Which action classes can be reused

| Class in `src/crafting_system/actions/` | PoE2 use | Change needed |
|---|---|---|
| `magic.py` (Transmutation, Augmentation, Regal) | P2-01 to P2-03 | a lowest-level filter with the top-tier exception; Transmutation always 1 mod; Alteration removed |
| `alchemy.py` | P2-04 | input rarity normal or magic; fixed 4 mods |
| `exalted.py` | P2-05, P2-13 | grade parameter; omen parameters (side, two mods, same type, catalyst weight) |
| `chaos.py` | P2-06, P2-15 | **rewrite**: remove 1 (uniform, or lowest level, or one side) then add 1 |
| `annul.py` | P2-07, P2-16 | side and desecrated filters |
| `divine.py`, `blessed.py` | P2-08, P2-23, P2-24 | add Sanctify (a multiplicative value change and a lock) |
| `fracture.py` | P2-09 | same rule (≥ 4 mods); exclude unrevealed mods |
| `essence.py` | P2-10, P2-11, P2-12, P2-17, P2-27 | **rewrite** to two shapes: magic → rare + 1 fixed mod; rare: remove 1 + add 1 fixed mod. Alloys and jewel emotions use the second shape |
| `veiled.py` + the unveil design of ADR-0026 | P2-20 to P2-22 | desecration: add 1 unrevealed (removing 1 if full), reveal = chance node (3 options drawn) then choice node; omens on both |
| `catalyst.py`, `quality_currency.py` | P2-25, P2-26 | catalyst quality as a weight multiplier on the next Exalted Orb |
| `corruption.py`, `corrupted_pool.py`, `locus.py` | P2-32 to P2-36 | new outcome lists; Architect's Orb as a double corruption with destruction; Orbs of Sacrifice |
| `hinekora_lock.py` | P2-19 | likely the same peek design (ADR-0054) |
| `socket_orbs.py` | P2-40 | augment sockets: count only, no colours or links |
| `pool.py`, `rolls.py`, `outcomes.py`, `draw.py`, `scope.py`, `catalog.py`, `contract.py`, `errors.py`, `listing.py` | all | the generic machinery stays; `pool.py` gains the lowest-level filter and the weight source |
| `fossil*.py`, `harvest*.py`, `bench.py`, `metamods.py`, `beast*.py`, `influence.py`, `eldritch.py`, `awakener.py`, `recombinator.py`, `imprint.py`, `remembrance.py`, `unravelling.py`, `strand_use.py`, `foulborn.py`, `bloodstained.py`, `burn.py`, `cut.py`, `enchant.py`, `socket_colours.py`, `mixture.py`, `finite.py`, `add.py` | – | not used by PoE2 (keep for PoE1; `recombinator.py` waits for its return) |

New classes: `omen` handling as action parameters (not actions of their own: an omen is bought and consumed with the orb, so the cost of the action is orb + omen); `desecrate` and `reveal`; `sanctify`; `alloy`/`essence_replace`; `augment` (socket an augment); `reforge_bench` (three inputs, like ADR-0022's two-input actions).

## 4. What PoE2 breaks in the planner's model

1. **Hidden weights.** PoE1's exact odds come from datamined weights (ADR-0003, ADR-0006). PoE2 has none: every outcome over random mods rests on community estimates with holes. Every answer would be "approximate" in ADR-0028's sense, and OR-59's honest label would apply to almost every plan. A weight source becomes a rule axis (ADR-0042 is a precedent) with a stand-in policy for unmeasured mods.
2. **No reset.** No Scouring or Alteration, and the Chaos Orb changes one mod. Routes become sequences of add/remove on one item, and a bad outcome is rarely undone cheaply: buying a new base is the usual reset. The state graph is deeper and the "buy again" edge carries more weight.
3. **Omens as modifiers of actions.** An omen changes the next orb's pool or removal rule. The action set becomes orb × omen combinations (Exalted × {none, Sinistral, Dextral, Greater, Greater+side, Catalysing, ...}); stacking rules (several active omens, mutually exclusive pairs) must be claims.
4. **A lowest modifier level.** Draws are cut from below (Greater/Perfect orbs, Ancient bones) with a per-family top-tier exception. The tier cut of ADR-0040 (strands) is the nearest existing design.
5. **One crafted and one desecrated mod per item**, and **one unrevealed mod with a choice at reveal**: item state gains a desecrated flag and an unrevealed slot (ADR-0026's veiled state is the precedent).
6. **Removal-then-add actions** (Chaos, Perfect essences, alloys, emotions on jewels, Orbs of Sacrifice) replace PoE1's full reforges: the distribution is over which mod leaves times which enters.
7. **Currency of account.** PoE2 prices are in Exalted or Divine Orbs; Chaos is a crafting orb. ADR-0007's price file and every displayed cost change unit.
8. **Item classes and tags.** New classes (Spear, Flail, Crossbow, Focus, Buckler, Talisman, Warstaff/Quarterstaff, Sceptre, Charm, Relic, Tablet) and attribute tags per armour base; PoE1 class lists in claims (`affix_pool.influence_tags` and others) do not carry over.
9. **Fixed counts.** Magic is 1+1, rare 3+3; Alchemy gives exactly 4. PoE1's 4/5/6 = 8:3:1 (`affix_count`) is gone.
10. **The game moves.** PoE2 changes crafting in every content patch (0.3, 0.4, 0.5 each reworked omens, essences or Vaal crafting; 1.0 adds a new system). The claims carry `patch_verified` and `history`; the port needs the patch-update skill's discipline from day one.

## 5. Unknowns, ranked by how much of the planner they block

| # | Unknown | Blocks | Best lead |
|---|---|---|---|
| U1 | Spawn weights of every mod, and of the reveal options | every random add | Craft of Exile beta `classmods` and poe2db `DropChance` (Krakenbul estimates); a large-sample measurement of our own |
| U2 | 1.0's crafting (Crimson Iron Reforging, blood materials) and what 1.0 changes in the rules above | the whole method list | 1.0 patch notes (expected 2026-12-11) |
| U3 | The top-tier exception to the lowest modifier level (per family? per tag group?) | Greater/Perfect orbs, Ancient bones | Craft of Exile code (implements it), a forum thread; no game text |
| U4 | Omen interactions: Greater Exaltation with one open slot; Homogenising "same type"; Whittling ties; Necromancy on a full side; several omens at once | omen actions | Craft of Exile code; in-game checks |
| U5 | Vaal Orb and Architect's Orb outcome odds | corruption (P4) | Craft of Exile (25% each), Maxroll; a sample |
| U6 | Reveal: always 3 options? weights of ordinary vs lords' mods; Echoes' reroll | desecration (P2) | Craft of Exile (`veiledPicksNumber: 3`); the 500-item Reddit experiment |
| U7 | Essence on an item whose item level is below the essence mod's level | essences | in-game check |
| U8 | Does an essence or alloy mod count as the one crafted mod? | essences, alloys | 0.5.0 notes are silent; in-game check |
| U9 | Catalysing Exaltation's weight multiplier (1 + 0.2·Q per Craft of Exile) and quality per catalyst | jewellery | Craft of Exile; catalyst Reddit sample (1,000 Wombgifts) |
| U10 | Reforging bench equipment recipes; runeforging's effect on mods | P2-29, P2-31 | poe2db recipe pages; in-game check |
| U11 | Quality per use of quality currency | quality | Craft of Exile formula vs guides |

Confidence and open questions per claim are in `docs/poe2/notes/`; the community numbers are in `docs/poe2/research/community-evidence.md`.

## 6. Owner rules that would carry over

OR-35/OR-36 (the site), OR-46 (the emulator as the reference of one action: Craft of Exile has a PoE2 emulator, beta), OR-59 (the honest label: every PoE2 plan would carry it while weights are estimates), OR-24 (the owner is asked last). Which methods form the PoE2 beta is the owner's call; a proposal by the PoE1 batch logic: P1 core (P2-01 to P2-19), then desecration (P2-20 to P2-22), then the rest of P2, then corruption.
