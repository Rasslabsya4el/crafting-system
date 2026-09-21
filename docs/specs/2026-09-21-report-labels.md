# Spec: player wording and final audit labels

Worktree `.worktrees/report-labels`, branch `w-report-labels`. Luna medium, bound15minutes.
Read docs/design/route-report.md. This is presentation only: preserve all probabilities,
counts, branching conditions, sources, algorithms and raw fields. No new game rules.
May touch ONLY src/craftoracle/reporting.py, src/craftoracle/report_assets/template.html,
tests/test_report.py and tests/test_report_template.py.

1. Translate route titles by existing IDs: suffix-protected-life = "Envy → защита суффиксов → Exalted Orb";
   suffix-protected-harvest-life = "Envy → защита суффиксов → Harvest Life"; protected bench
   variant = "Envy → защита суффиксов → Exalted Orb → верстак"; fracture = "Фрактура здоровья T1 → Envy";
   fossils = "Fossil: " + actual selected fossil names; magic = "Alteration → Regal → Exalted Orb";
   alchemy-scour = "Alchemy → Scouring"; chaos = "Alchemy → Chaos Orb". Essence names unchanged.
   Search must include displayed title and original identifiers. Unknown route keeps raw name.
2. In instructions replace internal words while retaining their CONDITIONS: Life9 ->
   "здоровье T1" plus existing source stat text; gate -> "условие отбора"; elemental suffixes ->
   "суффиксов сопротивления стихиям из цели"; ordinary explicit -> "обычных явных модификатора";
   normal-базе -> "обычной базе"; salvage0 -> "без выручки от продажи в этом расчёте";
   Exalt Orb -> Exalted Orb; slam -> "применений"; lock -> "защиту суффиксов"; setup -> "подготовка".
   Harvest player step simply applies Harvest reforge Life with Suffixes Cannot Be Changed;
   keep first_only technical assumption in raw metadata, remove it and recipe729 from player steps.
   Every Harvest/Exalt success condition uses sourced life label. No instructions lose early_stop,
   max_exalts, selected prefix/suffix gates or reset paths. For Magic early_stop=false, Regal
   instruction must not claim an intermediate target check unless Regal is the last stage(k0).
3. Template labels: Utility -> "Ценность", Frontier -> "Лучший обмен цены и ценности" with
   concise explanation; target tier -> "тир"; expected payments -> "Среднее число применений";
   material heading simply "Материалы", price/spend headers carry price unit. Risk discarded bases
   -> "Среднее число отложенных баз" (still FORMAT AS COUNT, not probability). Translate
   dirty tree/pass/fail/unavailable and test summary labels, CoE headers, raw audit heading.
   Full commit/time belongs in collapsed source/evidence details, not the top item meta line.
4. Route audit must render route.audit (terminal_distribution/parameter_audit), not undefined
   route.outcome. Include evidence.proof_link as an actual safe local proof.json link. Keep
   all escaping/path guards. One decimal/dark style intact; normalize negative rounded zero
   to 0,0 (e.g. numeric(-1e-12)). Raw numbers stay unchanged.
5. Run existing focused tests; adjust string assertions to new words only. Extend existing
   JS formatting test with numeric(-1e-12)=0,0 and Russian title search coverage if practical.
   No new crafting tests required. Existing numbers must stay1927.479966→1927,5 and tiny
   probability0.000024282→<0,1% (~1/41183). Do not run full plans/full suite.

Final report: commit, focused test line, requirement checklist, files, questions. Commit
explicit paths. Do not modify lead docs. Report starts === FINAL REPORT ===.
