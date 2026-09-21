# Spec: three interactive crafting instruction layout proposals

Worktree `.worktrees/route-layout-prototype`, branch `w-route-layout-prototype`.
Terra high, bound30minutes. May touch ONLY `docs/prototypes/route-layouts.html`.

## Why
Owner wants to approve the visual instruction contract before another renderer change.
Read docs/design/route-layout-proposals.md FULLY. It is the complete content and numerical
contract. Design/recipe decisions are made there; you implement its three different views.

## Requirements
1. Produce one polished standalone HTML, Russian, dark, one decimal, top A/B/C switch.
   A is structured step cards with6 affix slots and branch buttons; B is a directed
   SVG/HTML graph with labelled jump/loop edges and selectable node detail; C is manual
   step guidance with a6-slot card, branch navigation, Exalt1..3 and reset/history.
2. Use ONLY the sourced literal snapshot/numbers and four action steps in the design.
   No planner, Monte Carlo, CoE, network, asset download, production code/test changes.
   Do not run full pytest or any real craft. Currency actions use text chips for now.
3. Show actual gate: all3 suffixes occupied,2 elemental T1 plus forced Envy chaos;
   <=1 prefix. Show crafted prefix at bench and all prefixes cleared after Scour.
   Failed3-Exalt block returns to Envy, not an impossible bench craft on full prefixes.
   Success checks skip all later steps. Do not mislabel6.7% per Exalt or98.6% per Envy.
4. Correct scope of evidence in this prototype: full route unvalidated versus CoE,
   same-base COMPONENT cases3, separate collapsed global12 cases/5 bases. Do not embed
   all423 tests or rerun them. Keep source/provenance details and historical revision.
5. No external dependencies/resources. SVG arrows are inline. Accessible buttons/labels,
   text and color together, keyboard focus, mobile layout/contained graph overflow.
   The primary screen must let owner compare templates; no premature choice persistence
   or production integration. Show concise pros/tradeoffs for each mode.
6. Code comments English. Keep implementation simple and data-driven within the HTML.
   Avoid random demo simulation. No new game facts or calculations beyond formatting.

## Checkable values / acceptance
-4 actions; every state card exactly6 slots (3 prefix/3 suffix).
-Envy branches .0025940606844434212 / .0005495684166343902 / .9968563708989222.
-Exalt block .06674609236085169 / .9332539076391483;3 misses must return to1.
-Bench and Scour100% conditional; prices5/2Divine/.5/10 per action, labelled invented.
-Mean1948.6031719508137→1948,6; p904450.5→4450,5; route stats are historical snapshot.
-C ready from step1 goes to finished; C preparation goes2→3→4; miss1→miss2→miss3→1;
  hit at any Exalt goes finished. Buttons reset and modes all work.

No new automated tests required for this reversible layout proposal. Run an inline-JS
syntax check using installed Node; lead verifies all paths in browser and reads full diff.
Report commit, syntax check, counts, file path, limitations and questions. No outside reads
or skills. Commit explicit path. Final report starts `=== FINAL REPORT ===`.
