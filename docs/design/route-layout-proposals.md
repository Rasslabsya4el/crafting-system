# Route layout proposals — lead design, 2026-09-21

Owner requests DESIGN APPROVAL ONLY: compare visual layouts for the existing protected
Envy helmet route, with affix slots, event goals, transition odds, skips and paid resets.
Do not rerun planners, Monte Carlo, full tests or CoE. Do not change the recipe or renderer
used by production reports until the owner chooses a layout. Currency artwork can follow;
for this comparison use text action chips, not invented orb drawings or asset downloads.

## Fixed content and provenance

Saved input: out/reports/helmet/plan.json, route id suffix-protected-life; original
implementation/proof revision02bceff. Numbers also independently recorded in
docs/design/parameter-search.md, Preparation-grid reference. Sources for behavior:
docs/mechanics/essences.md, bench_metamods.md, basic_currency.md. Confidence remains
the accepted ordinary model/D14, not new empirical verification.

Base Royal Burgonet, ilvl86, supplied quality20. Required target: life T1
`+(130-144) to maximum Life`, chaos T1 `+(31-35)% to Chaos Resistance`, and at least
one of fire/cold/lightning T1 `+(46-48)% to [element] Resistance`.
Source: saved report.context.target labels; PoB ModExplicit keys IncreasedLife9,
ChaosResist6, FireResist8, ColdResist8, LightningResist8. Envy explicitly forces
ChaosResist6 on Helmet (data/pob_essences.json, Metadata/Items/Currency/CurrencyEssenceEnvy3;
PoB Essence.lua:104). Prefix bench729 Suffixes Cannot Be Changed is in
sources/pob/Data/ModMaster.lua:733 and data/pob_bench.json.

Saved fields (literal snapshot, not a new calculation):

| Event | Probability | Conditioning / field |
|---|---:|---|
| Envy immediately finishes target | 0.0025940606844434212 | Per Envy use, preparation_early_probability |
| Envy enters preparation branch | 0.0005495684166343902 | Per Envy use, preparation_cycle_probability; EXCLUDES finished targets |
| Envy repeats | 0.9968563708989222 | Complement of the two mutually exclusive saved events; display arithmetic only |
| Up to3 Exalts find T1 life | 0.06674609236085169 | Whole series from empty prefixes/full prepared suffixes, cycle_success_probability |
| All3 Exalts fail | 0.9332539076391483 | Whole series; full_prefix_failure_probability |
| First Exalt alone hits | 0.02546148949713558 | Optional source detail; first_hit_probabilities[0] |
| Finished items that completed during Envy | 0.9860565798144074 | Whole-policy completion share, NOT chance per Envy |

Mean1948.6031719508137 and p904450.5 are existing estimates at invented prices.
Do not optimize, reinterpret or recalculate these values. One decimal display, tiny
nonzero probabilities below0.1% show `<0,1% · ~1 из 1 820` for the preparation branch.
This reciprocal is display formatting, not another crafting calculation.
Envy per use5.0 chaos-equivalent; bench2 Divine (invented100 each); Scour0.5;
Exalt10.0 each. Costs per action and expected whole-route costs have distinct captions.

## State cards and four action steps (same in every variant)

Each state card has exactly6 labelled rows:3 prefixes, then3 suffixes. Logical slot
order is a visual convention, not the game's mod order. Use text+color, not color alone:
empty dashed; arbitrary muted; essence violet; required green; crafted gold. Stat text
must be literal above, with Russian explanations. A compact legend explains the styles.

1. **Спам Deafening Essence of Envy.** Goal: either finish immediately or obtain the
   exact preparation state. A finished target always wins before evaluating preparation.
   Three mutually exclusive outcome cards: `Готово → финиш (0,3% за эссенцию)`;
   `Подготовка готова → шаг2 (<0,1% · ~1/1820 за эссенцию)`;
   `Не подходит → повторить шаг1 (99,7% за эссенцию)`.
   Preparation requires exactly3 suffixes, at least2 desired T1 elemental resistances,
   at most1 prefix. For a representative preparation state show P1 arbitrary non-T1-life,
   P2 empty, P3 empty; S1 Envy chaos31-35, S2 fire46-48, S3 cold46-48. Caption fire/cold
   are one example; any2 different desired elements qualify. Unlike the owner's illustrative
   sketch, this actual selected policy has NO empty suffix. No silent recipe adjustment.
   Its before state may be ordinary empty base or a rejected rare item; distinguish labels.
2. **Верстак: Suffixes Cannot Be Changed.** Goal: protect the accepted three suffixes
   for the following Scour. Add the craft into an empty prefix; display before→after
   state (P1 arbitrary, P2 craft, P3 empty; same3 suffixes). Cost2 Divine per application.
   `Защита установлена → шаг3 · 100,0% при показанных условиях`. No random roll.
3. **Orb of Scouring.** Goal: clear prefixes while keeping three suffixes. After state:
   all3 prefixes empty; same3 suffixes. Explain craft itself disappears with prefixes;
   protection was paid for this Scour. `Префиксы очищены → шаг4 · 100,0% при защите`.
4. **До3 Exalted Orb, проверка после каждой.** Goal: T1 life. Start with3 empty prefixes
   and3 accepted suffixes. Stop after first T1 life. Success branch `Готово · 6,7% за
   всю серию`; all3 fail branch `3 префикса заняты → шаг1 · 93,3% за всю серию`.
   Intermediate miss with free prefix continues to next Exalt; no separate conditional
   probability exists in this snapshot and it must NOT be assigned6.7% or100%.
   Show `промах + свободный префикс → следующая сфера` with explanation that6.7% is
   for the complete series. At3 failed prefixes, bench has no slot; return to Envy,
   losing the current suffix preparation. Do not offer bench/Scour after a full failure.

Final state example after first Exalt: P1 life130-144, P2/P3 empty; same3 suffixes.
For a third-miss snapshot use3 arbitrary non-target prefixes, same3 suffixes, then
reset. State patterns/examples are labelled, not a sampled simulation or exact item roll.

## Three visibly different review modes

A / **Карточки шагов** (recommended primary reading mode). Vertical numbered timeline.
Each card: exact action, why, expected state with6 slots, event transitions and probability
scope. Show branches adjacent to the action; deterministic operations visibly labelled.
Top compact4-step strip, jump links, goal skip and return labels. Avoid large generic prose.

B / **Карта переходов**. A real SVG/HTML directed graph, not another card list. Four
action nodes plus one green finished node. Explicit Envy self-loop, Envy→finished,
Envy→bench→Scour→Exalt, Exalt→finished and red Exalt→Envy return. Attach saved odds to
appropriate edges. Clicking/keyboard selecting a node opens its state/goal in a detail
panel below/alongside. Graph fits desktop; contained scroll on narrow screens.

C / **Во время крафта**. One active step and a large6-slot state card. User manually
chooses what happened: ready / preparation matches / reroll; deterministic next;
for Exalt hit / miss with remaining slot. These buttons navigate a scripted explanation,
never generate random outcomes. Show current step, Exalt use1/3..3/3 and a brief action
history; reset button. Mark `Демонстрация интерфейса: выберите результат вручную`.
If miss3, return step1 and explain why the previous suffixes are surrendered.

Use one standalone HTML with top mode switch, shared content and compact mode rationale.
Dark theme, one decimal, Russian UI with English currency/mod names. Polished intentional
spacing, visible arrows/badges, reasonable typography; useful at1222x1280 and390px.
No framework, CDN, fonts, external images, crafting code or network required.

## Evidence scope correction

In this mock, show a small `Проверка этого маршрута` section: full route NOT compared
against CoE; same-base action examples C01/C02/C03 are components, not proof of this
complete recipe. The C02 target differs from the whole requested item; do not call it a
route comparison. A separate CLOSED section `Общие тесты движка:12 случаев,5 баз`
explains why the earlier report contained body armour, ring, amulet and boots. Existing
423-test summary is historical at02bceff, not a newly executed UI verification badge.
No giant proof table in the primary crafting path. Sources/raw snapshot in collapsed details.

Why weak routes: finite template library, bounded parameter grid, unimplemented special
families and blocked source gates; the current target/invented price table affects ranking.
The selected protected route completes98.6% of successes during Envy. Show that insight
only in a compact route context panel; it does not establish optimality or say better
strategies cannot exist. Future policy expansion is deferred at the owner's request.

Owner approval question after delivery: choose A/B/C, or A with the small B overview.
