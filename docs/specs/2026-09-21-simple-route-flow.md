# Spec: replace rejected wordy prototype with one simple flow

Worktree `.worktrees/simple-route-flow`, branch `w-simple-route-flow`; Terra/high.
Bound 10 minutes. May touch ONLY `docs/prototypes/route-layouts.html`.
Read `docs/WORKER_RULES.md` first. This spec SUPERSEDES the former three-view layout.

## Why
Owner rejected the prototype: vague words such as preparation/state search, rules in
tiny subtitles, repeated before/after items, too much explanation. Make a single clear
flowchart with direct pass/repeat/finish conditions. No format-selection UI or essays.

## Requirements
1. Rewrite the standalone HTML around THREE numbered steps (four underlying actions):
   1 Deafening Essence of Envy; 2 bench Suffixes Cannot Be Changed THEN Orb of Scouring;
   3 up to3 Exalted Orb. All formulas/probabilities/recipe unchanged. No calculations,
   planner, simulations, pytest, network or icons. Only syntax check/browser checks.
2. Top header ONLY `Royal Burgonet · Envy → Exalted Orb`. No explanatory subtitle,
   no objective paragraph, tabs, mode pros/cons, legend essay or generic stage labels.
   Dark theme, comfortable16px primary text, probabilities/costs one decimal.
3. Step1 action title `Применяйте Deafening Essence of Envy`. Directly beneath/right
   show these branches IN THIS ORDER with explicit conditions, not generic captions:
   - `Закончить` (0,3% за Envy): `+(130-144) to maximum Life` AND
     `+(31-35)% to Chaos Resistance` AND at least one of Fire/Cold/Lightning Resistance
     at `+(46-48)%`. Show original English stat text, exact ranges, readable font.
   - `→ 2` (<0,1% за Envy, ~1 из1820): exactly3 suffixes = Envy ChaosResistance and
     two DIFFERENT elemental resistances T1; at most1 prefix. Display concrete
     six-slot item ON THIS CONNECTING BRANCH: prefix `любой / пусто / пусто`;
     suffix `+(31-35)% to Chaos Resistance`, `+(46-48)% to Fire Resistance`,
     `+(46-48)% to Cold Resistance`. Short caption `Fire + Cold показаны для примера;
     подходят любые два разных: Fire / Cold / Lightning.` Also `Не больше 1 prefix`.
     This ITEM IS THE INPUT OF STEP2. Do NOT draw it again inside step2.
   - `Повторить Envy` (99,7%): `Все остальные результаты`. Visible return arrow
     to step1; finish has priority if conditions overlap. No long probability essay.
4. Step2 ONLY two concrete operations: `Prefix: Suffixes Cannot Be Changed` (2 Divine),
   then `Orb of Scouring` (0,5 chaos). Arrow `→ 3 · 100,0%` followed by ONE shared
   result/input card:3 empty prefixes, same3 English suffixes. This card is the input
   of step3, not a duplicated before+after pair. If needed one short note `Scour удаляет
   все prefixes, включая Suffixes Cannot Be Changed.` No bench before/after card.
5. Step3 `Exalted Orb — проверять после каждой` (10,0 chaos/Orb):
   - `+(130-144) to maximum Life` -> `Закончить`.
   - `Нет Life T1, есть пустой prefix` -> `Ещё Exalted Orb` (loop).
   - `Нет Life T1, все3 prefixes заняты` -> `Повторить с1: Envy` (return).
   One plain line here `За серию до3 Orbs:6,7% закончить;93,3% вернуться к Envy.`
   Do not assign whole-series odds to an individual roll or invent per-roll odds.
6. Main flow no words `подготовка`, `поиск состояния`, `точная подготовка`, `образец`,
   `репрезентативный`, `снимок`, no proof paragraphs. Information meaningful to choosing
   an action only. Results are shared edges feeding the next action. No A/B/C tabs.
   Buttons/links scroll to destination, selected branch can highlight downstream action.
   At most TWO six-slot item cards in the whole main flow, each appears exactly once.
7. Footer SINGLE CLOSED disclosure `Стоимость и проверка` with preserved historical
   mean1948.6/p904450.5, prices invented, entire route not validated vsCoE, same-base
   C01..C03 components vs global12/5. Add source references to prior design doc; all
   provenance/rationale goes here, not sprinkled over main instructions.
8. Original English modifier text throughout (D26). Russian instructions okay.
   Full literal English stat lines from docs/design/route-layout-proposals.md; no new
   game facts. Freeze saved odds from that document. No other files, no dependencies.

## Checkable acceptance
3 numbered steps,4 named actions; exactly2 six-slot cards (12 rows total); one closed
details element;0 before/after pairs;0 tabs. Original English modifiers only.
Step1 branch odds0.3%,<0.1%,99.7%; step2conditional100%; whole Exalt6.7%/93.3%.
Dark and readable at desktop and390px. Lead checks whole diff and browser personally.
Commit explicit HTML path. Report syntax check, counts, commit; final starts
`=== FINAL REPORT ===`. Do not spend time on new calculations or automated tests.
