# Questions for the owner (yes / no or one number; answer in the last column or in chat; "не знаю" is a valid answer)

First version written by the project lead on 2026-09-21 from `OPEN_QUESTIONS.md`; the agent corrects wording where the lead
misread a question and appends what is missing. Ordered by how much an answer unblocks. Target: ordinary PoE 3.29.

| # | question (Russian, as asked) | unblocks | assumed if unanswered | answer |
|---|---|---|---|---|
| 1 | Харвест-рефордж (например «reforge life») на предмете с бенч-крафтом «Suffixes cannot be changed»: суффиксы гарантированно сохраняются в 3.29? (Q6) | the route players actually use: protect one half, reforge the other with a tag | family stays blocked | |
| 2 | Харвест-рефордж на предмете с «Cannot roll Attack Modifiers»: атак-моды исключаются из ВСЕХ модов рефорджа, а не только из первого гарантированного? (Q6) | harvest + metamod blocking | only the first mod is filtered (Craft of Exile's text) | |
| 3 | Доступны ли в обычной 3.29 (не Ruthless, не легаси) дополнительные харвест-рефорджи по тегам minion / elemental / attribute / mana? (Q26) | which harvest tags the loadouts may use | only the classic tags | |
| 4 | Хаос / алхимка дают рару 4, 5 или 6 модов с шансами примерно 2/3, 1/4, 1/12 -- это сходится с твоим опытом? (Q4) | every reroll number in the oracle | yes (8 / 3 / 1) | |
| 5 | Мультимод («Can have up to 3 Crafted Modifiers») на бенче стоит 2 Divine Orb? (Q7) | default price file | yes | |
| 6 | Можно ли применить резонатор с фоссилами к белому (normal) предмету в обычной 3.29? (Q30) | fossil routes from a white base | no: rare items only | |
| 7 | Два фоссила, оба увеличивающие шанс одного тега: их множители перемножаются (а не складываются)? (Q13) | fossil-combination calculator | blocked | |
| 8 | Эссенцию уровня Screaming и выше можно применить к magic-предмету (она сделает его раром)? (Q29.01) | essence routes after an Alteration stage | no: normal or rare only | |
| 9 | Fracturing Orb: нужен рар минимум с 4 модами, без инфлюенса, фрактурится один случайный мод -- всё верно? (Q12) | fracture-then-spam routes | blocked | |
| 10 | Veiled Orb в 3.29: снимает случайный мод и добавляет veiled-мод (префикс или суффикс случайно)? Работает ли с «prefixes / suffixes cannot be changed»? (Q12) | veiled finishing | blocked | |
| 11 | Influence Exalted Orb (Crusader's и т.п.) можно применить ТОЛЬКО к предмету без инфлюенса? (Q27) | influence routes | yes, only without influence | |
| 12 | Awakener's Orb: если выбранные моды двух предметов конфликтуют по группе, остаётся мод предмета-получателя (а не случайный)? (Q20) | double-influence routes | blocked | |
| 13 | Orb of Conflict при разных тирах двух имплицитов: шансы повышения / понижения зависят от тиров (не 50 / 50)? (Q11) | eldritch implicit routes | blocked | |
| 14 | Катализаторы: прирост качества за один катализатор зависит от уровня предмета (ilvl), а не от его редкости? (Q23) | jewellery quality steps | item level (the wiki) | |
| 15 | Рекомбинаторы в 3.29: какому источнику по шансам ты доверяешь (ссылка или «70% на 3 мода из пула в 6»)? (Q21 / Q22) | recombinator ladders | blocked | |

## The owner's answers, 2026-09-21 (verbatim sense, recorded by the lead; label facts taken from here `owner-confirmed`)

| # | answer | what to do |
|---|---|---|
| 1 | YES. "They did this in 3.27; I do not understand why the source where she read it is not 100%." | The official 3.27 patch notes are decisive (see the corrected source ranking in AGENTS.md 2). Harvest reforges respect "prefixes / suffixes cannot be changed": UNBLOCK the protect-one-half + tagged-reforge routes now. |
| 2 | Does not know; wants to know the result. | Research (official forum, wiki, PoEDB, Reddit), 30 minutes at most; until answered keep Craft of Exile's reading (only the first forced mod is filtered) as the assumption, printed in the plan. |
| 3 | YES, available, but expensive. No price idea: "price them like the expensive harvest crafts (the add / remove kind, the white = Sacred lifeforce ones) and we will see later". | Add the tags to the endgame loadout; price = the same placeholder as the Sacred-lifeforce crafts in the example price table, flagged `owner-provisional`. |
| 4 | YES, true. "Is it not on the wiki?" | 4 / 5 / 6 mods at 8 / 3 / 1 stays as data with the label `owner-confirmed` + `reimplemented-from-CoE`; look for the wiki line once (10 minutes), then stop asking. |
| 5 | YES, 2 Divine. | Default price file. |
| 6 | Thinks NO for the larger resonators: "some small resonators work on white items, from some size on only on rares; it should be on the wiki or PoEDB. I can check in game." | Research wiki / PoEDB per resonator type and socket count; if still unclear, put ONE precise in-game test request for the owner into this file. |
| 7 | Does not know. "Is it even possible to have two fossils with the same positive effect? All fossils are different." | Explain in one paragraph in the fossil fact sheet when it happens (one MOD carrying two tags boosted by two different fossils), then research how the multipliers combine (PoEDB, Craft of Exile's default mode, Reddit); 30 minutes; otherwise keep blocked with both variants computed side by side. |
| 8 | NO. "Below Screaming essences are used on white items only, from there up only on rares, I think; this must be on the wiki or PoEDB -- check the exact tier." | Magic items are never a legal essence target. Verify the tier boundary against the wiki's Essence page you already hold (S21) and PoEDB; fix the fact sheet. |
| 9 | YES, "but research the influence cases; there may be cases I do not remember. Eldritch counts as an influence, yet fracturing under it seems possible." | Research the exact eligibility list (influenced, eldritch implicits, synthesised, already fractured, mod count) on the wiki / PoEDB / official notes; then unblock fracture-then-spam. |
| 10 | "This must be in https://www.craftofexile.com/?page=metamods -- I will be very sad if she has not parsed that data, it is VERY important. If she is unsure about this exact case: PoEDB / Reddit research. I am not a pro crafter." | The metamod interaction table (S14) must be FULLY represented as data with tests: every action x metamod cell, with Craft of Exile's notes and its patch-lag warning. Report how many cells are encoded. Veiled Orb specifics: PoEDB / wiki / Reddit. |
| 11 | Thinks YES, not sure. | Keep "only on items without influence" (the item's own tooltip, S48) as documented. |
| 12 | Does not know: research PoEDB / Reddit. | Research, 30 minutes; else stays blocked with both variants noted. |
| 13 | Does not know: research PoEDB / Reddit. | Same. |
| 14 | No idea; "probably depends on the quality rework a few leagues ago. I can run tests later, but my currency is not infinite." | Research the rework's patch notes + wiki; only if nothing is found, write ONE cheap in-game test for the owner. |
| 15 | Trusts ONE source: a big Reddit post explaining recombinators ("NNN" notation etc.) that links to a post on another site with many pictures of circles and arrows showing probabilities. "Find it and save it in the repo as a source." ALSO: PoE 1 has TWO recombinator modes -- the classic one and the one the community calls the "PoE 2 recombinator": you pick mods on the two items, the recombinator itself SHOWS the success chance, a failure destroys the items. "There seems to be research on it too; I do not know whether it is from PoE 1 or PoE 2 and whether it applies." The owner could test, but it would take a huge number of tests. | Find and cache that Reddit post and the linked resource (S-rows, screenshots / text of the diagrams into `sources/raw/`), rebuild the recombinator fact sheet on it, and add a second sheet for the pick-your-mods mode: what is known, from which game, what is unknown. Do not ask the owner for tests yet. |

