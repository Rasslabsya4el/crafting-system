# PoE2 crafting research: progress log

## Итог для владельца (2026-11-25)

**Собрано всё, что известно о крафте в Path of Exile 2, в том же виде, в каком у нас хранятся знания о PoE1.** Версия игры, на которую проверен каждый факт: PoE2 0.5.5 (данные игры 0.5.5.10, лиги Runes of Aldur и Forbidden Rites). Код, данные, тесты и документы PoE1 не тронуты; всё лежит только в ветке `claude/research-poe2-crafting-c00c9f`, она отправлена на GitHub, PR не открыт.

Что есть:
- **468 правил крафта** в 54 файлах (`docs/poe2/claims/`), в точности в формате наших правил PoE1: правило, ссылка на источник, точная цитата, версия игры, дата проверки, что было до изменения патчем. Наш загрузчик правил PoE1 читает их без единой ошибки, то есть при переносе их можно просто подключить. 112 правил помечены «приблизительно» (источник — модель Craft of Exile или выборка игроков, а не текст игры).
- **Проверка полноты**: все 604 предмета для крафта из списка официального сайта торговли и из данных игры (валюта, 45 знамений, 82 эссенции, руны, ядра душ, идолы, кости Бездны, катализаторы, эмоции, сплавы, предметы Экспедиции) названы хотя бы одним правилом (`docs/poe2/COMPLETENESS.md`).
- **Каталог методов** (`docs/poe2/METHODS.md`): 52 способа крафта, у каждого условия, результат, цена одного применения и предложенная очередь, как наши B1–B3.
- **План переноса** (`docs/poe2/PORT-PLAN.md`): каждый из 83 методов PoE1 сопоставлен с PoE2. 7 остаются как есть, 33 изменились, 43 в PoE2 нет. Там же: какие наши классы действий годятся, что в модели планировщика PoE2 ломает, и неизвестные по важности.
- **Данные игры закреплены** так же, как у PoE1: выгрузка repoe-fork для PoE2 и 42 таблицы клиента игры, по хешам. Скрипт скачивания отдельный, путь PoE1 не тронут (`research/poe2/data/`). Плюс снимок списков официального сайта торговли.
- **Словарь терминов PoE2**, **план данных** (что откуда брать, чего нет), **история патчей** с 0.1 по 0.5.5 и сырые заметки исследования со всеми источниками (`docs/poe2/research/`).

Главное, что меняет перенос:
1. **Настоящих весов модов в PoE2 нет нигде.** В данных игры у каждого мода вес 1. Есть только оценки сообщества (poe2db и Craft of Exile; источник у них один), и у тысяч модов оценки нет. Значит, почти каждый план для PoE2 будет с честной пометкой «лучший найденный, не доказан».
2. **В PoE2 нет Scouring и Alteration.** Chaos Orb меняет один мод, а не все. Вместо этого есть «Greater/Perfect» сферы с нижней границей уровня мода (44/70 и 35/50), знамения (omens), которые меняют следующую сферу, и осквернение костями Бездны с выбором 1 из 3.
3. **Рекомбинатор выключен с 0.5.0.**
4. **11 декабря 2026 выходит PoE2 1.0 с новой системой крафта** (Crimson Iron: замена ненужных модов на закреплённые). Перед переносом это исследование надо освежить по патчноутам 1.0. Как это сделать, написано в `docs/poe2/README.md`.

Чего найти не удалось: точные веса модов (и вариантов при раскрытии осквернения); шансы исходов Vaal Orb и Architect's Orb; сколько качества даёт одна сфера качества; шансы Orb of Chance; что руноковка делает с модами. Все такие места перечислены в `docs/poe2/notes/` как проверки в игре.

Сайты, которые отказали серверу (не обходились): poe.ninja (веб-страница; его API отвечает), форум pathofexile.com (часть страниц), poe2wiki.net (защита от ботов), mobalytics, reddit.com (читался через архив Arctic Shift).

**TLDR:** знания о крафте PoE2 собраны: 468 правил, каталог методов, план переноса, закреплённые данные игры. Всё в ветке, PR нет, PoE1 не тронут. Главный риск — веса модов в PoE2 скрыты. 11 декабря выходит 1.0 с новым крафтом, после неё всё надо освежить. От вас ничего не требуется.

## Log (newest first)

### 2026-11-25

- Reddit evidence in (`research/community-evidence.md`, through the Arctic Shift archive): the reveal window always holds at least one desecrated-only option (563 windows), desecrated mods have unequal weights, poe2db's weights were checked by 1,811 Chaos Orbs on one base, Whittling targets the lowest modifier level, catalyst drop shares. Five of these became claims (`claims/community_samples.yaml`).
- Completeness pass: 604 of 604 crafting items named by a claim (`COMPLETENESS.md`, `research/poe2/data/completeness.py`); the Expedition items and the Cryptic Key got their claims (`claims/expedition_items.yaml`); `claims/market.yaml` covers the Currency Exchange, the unit of account and the price sources.
- Totals: 468 claims in 54 families, 112 approximate, all loading with the PoE1 registry loader.

### 2026-11-24

- Inventory of the PoE1 formats (`research/poe1-formats.md`); paths chosen so no PoE1 test reads them.
- Current version found: game data 0.5.5.10 (repoe-fork/poe2 export of 2026-11-19), patch line 0.5.5h, leagues Runes of Aldur and Forbidden Rites. 1.0 announced for 2026-12-11.
- Data pinned: 12 repoe-fork/poe2 files, 42 repoe-fork/dat-export tables, Craft of Exile beta data (cache only), by commit, sha256 and size (`research/poe2/data/PIN.json`, `fetch_poe2.py`).
- Finding: every positive spawn weight in the PoE2 client data is 1 (7,933 of 7,933).
- Readable extracts (`research/poe2/data/derived/`): datamined text of 771 trade-listed items, Greater/Perfect minimum levels, 178 essence rows, 12 bones, 313 socketables, 23 temple benches, 30 recombinable classes, 718 Verisium crafts, 687 exchange items, a mod census per class.
- Research notes: patch history, currency and omens, essences/augments/corruption/abyss, items and modifiers, data sources (`research/`).
- Claims written from the notes (203 currency and omens, 105 item rules, 145 essences and augments), each family with a notes file of confidence and in-game checks (`notes/`).
- METHODS, DATA-PLAN, PORT-PLAN, GLOSSARY-POE2, README.

### Sources that refused this server (not worked around)

- poe.ninja web page (`/poe2/economy`): 403. Its JSON API answers.
- pathofexile.com forum: 403 to curl for some pages; patch notes read through WebFetch. The trade API answers.
- www.poe2wiki.net: "Access Denied" bot protection on every page; wiki text only from search snippets, marked low confidence.
- mobalytics.gg, sportskeeda, vulkk, game8: 403.
- reddit.com: refuses; read through the Arctic Shift archive. The `gpt-research` MCP server was not connected in this session. Some archive searches always failed (HTTP 422), listed in `research/community-evidence.md`.

### Next (when the work resumes)

1. After 1.0 (2026-12-11): read the 1.0 patch notes, re-pin the data, re-derive, re-run the completeness pass, update the claims with `history` entries, add the Crimson Iron Reforging.
2. The in-game checks of `notes/*.md`, in the order of `PORT-PLAN.md` section 5.
3. A weight source decision for the port (Craft of Exile beta `classmods` or poe2db `DropChance`), with a stand-in rule for unmeasured mods.
