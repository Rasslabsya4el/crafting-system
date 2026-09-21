# Owner-facing route report — lead design, 2026-09-21

The owner requests a usable view of actual routes and observable proof, superseding the
brief's previous no-UI scope for this bounded report. Produce a standalone Russian HTML
report from real planner output, with no server, dependencies or network needed to read it.
Code comments/docs remain English. Rendering and evidence capture are delegated; all
mechanical interpretations in this document are lead decisions from accepted implementations.

## Surface and data contract

Show the target/base/ilvl/quality first, a conspicuous invented-price notice, generation
time/commit and a compact comparison table of EVERY ranked policy. Columns: route, stop
threshold when present, exact mean, p90, exact/estimated label, expected utility and frontier.
Selecting a row opens its full instructions, stage probabilities, expected materials/costs,
repeat/reset branches and supporting evidence. Search/filter and keyboard-accessible details
must work offline. Include unavailable routes with their actual reasons, not hidden omissions.
Default to the cheapest route open. Use a light readable layout, restrained teal accents,
tabular numbers, comfortable spacing and a print stylesheet. No generic landing-page filler.

Every number comes from the plan or the accounting derivations below, never a canned demo.
Preserve raw JSON as a sibling downloadable file. An evidence area lists real pytest cases
(searchable, grouped by module), failure/skip counts, commands/logs and all12 CoE comparison
rows. Test success verifies this model/implementation; it does not prove the whole strategy
against the game or live CoE. Per-route links identify component tests explicitly.

Mean cost is an expectation, not guaranteed budget. Explain p90 as the model's cost threshold
covering90% of completed runs; an estimated p90 is marked approximate. Its99% DKW bracket
is uncertainty of the estimate, not a player's90% cost interval. No currency icon downloads.
Full metadata, sources, sample size/seed, parameter audit and terminal distributions may be
collapsed below the player instructions. The original JSON remains available for inspection.

## Accounting from accepted policy output

Use source prices and bench recipes, not fixed numbers. Base price is supplied separately.
For every supported route provide currency name, expected count, unit price, expected
spend. Sum should match expected_cost within relative1e-9/absolute1e-7. A mismatch must be
visible as incomplete accounting, never disguised as zero or an invented balancing row.
Unknown future routes may show raw steps/stages and an explicit missing-translation note.

- Essence: expected count is essence stage expected_attempts. Base once.
- Alchemy/Scour: N=Alchemy expected_attempts; Alchemy N, Scour N-1, base once.
- Chaos: Alchemy once; Chaos count from its stage expected_attempts; base once.
- Fossils: Alchemy once; selected fossil IDs and matching resonator each expected_resonators;
  base once. Read ordinary fossil names from data/rules/fossils.json.
- Fracture: use expected_action_counts including bases. Map envy to supplied Envy ID.
- Protected Exalt: use recovery.expected_envy_applications and expected_prefix_cycles C.
  Lock729 and Scour C each. If d_j=recovery.first_hit_probabilities and k=max_exalts,
  Exalts=C*sum(1-sum(d_1..d_j) for j=0..k-1). Bench finish131 once if selected.
  This is the sum of per-cycle survival probabilities from design/parameter-search.md.
- Protected Harvest: Envy count from recovery; lock729 and Life reforge each C. Base once.
- Magic: T=transmute setup/reset expected_attempts, Transmute T, Alteration T,
  Augmentation T*P(one-mod Alteration) using supplied action_rules.magic_count_weights,
  Scour T-1, Regal from its stage expected_attempts, Exalts=sum its Exalt stages' counts.
  Base once. This is the same D14 augmentation coin/correlated attempt law used by optimizer.
  If required action rules or recipes are absent, mark the affected accounting unavailable.

Fixture: Envy at price5/count385.4959932113379 gives1927.4799660566896. Reprice to10
must give3854.959932113379, not a hardcoded old price. Tiny protected k2,d=(.25,.25),C2
consumes3.5 Exalts. Tiny Magic T4,Regal2,Exalts1,one-mod probability.5 consumes
Transmute4,Alteration4,Augmentation2,Scour3,Regal2,Exalt1.

## Instruction text and stage probability meaning

Names are English in-game currency names inside otherwise Russian instructions. Render
explicit selected parameter values, not raw Python dictionaries. Source basis: mechanics/
basic_currency.md, bench_metamods.md, essences.md, fossils_resonators.md, harvest.md,
fracturing.md; design/night-policies.md, parameter-search.md, family-policies.md.

Essence variants: "Возьмите обычную базу. Применяйте {essence} и проверяйте цель после
каждого применения. Готово — остановитесь; иначе повторите ту же эссенцию." Read essence
name from accepted recipe data (or the known IDs' exact names). Never invent a forced
modifier effect from its name; show forced target only if the data explicitly provides it.

Alchemy: "Примените Orb of Alchemy. Если цель выполнена — остановитесь. Иначе примените
Orb of Scouring и вернитесь к Alchemy." Scour is only paid after a failure.
Chaos: first Alchemy; follow selected alchemy_early_stop (if false its result is deliberately
discarded). Then repeat Chaos until target. No Scour between Chaos uses.
Fossils: Alchemy and immediate target check; otherwise fill one Chaotic resonator of the
selected socket count with exactly the selected fossils and apply to the rare item. Repeat
the full recipe, checking target after each. Do not add Scour or multiply resonators by sockets.

Protected preparation: use Envy repeatedly. If preparation_early_stop=true, a completed
target stops even outside the preparation gate. Otherwise accept exactly3 suffixes,
at least selected minimum_desired_elemental_suffixes desired elemental suffixes and no
more than max_prefixes prefixes. Other Envy outcomes repeat.
Exalt finish: craft "Suffixes Cannot Be Changed"(729), Scour, then up to max_exalts slams;
stop after the first Life9 success. If the configured slams fail with a free prefix slot,
repeat lock+Scour; when three prefixes fill, return to Envy preparation. Every lock costs
again. Bench131 variant then adds its actual armour craft, not a substitute for required Life9.
Harvest finish: after accepted suffix preparation, craft729 then Harvest reforge Life.
Life9 succeeds; failure with a free prefix returns to paid lock+reforge, failure with3
prefixes returns to Envy preparation. No added Scour in this Harvest route. Display
first_only assumption and note this route has no attack/caster blocker.
Show recovery early_completion_probability separately: fraction of finished runs that
actually end during Envy. Do not mislabel stage preparation u+v as whole-target probability.

Fracture: fresh normal base each trial; Alchemy, early target stop when selected; otherwise
Scour+Alchemy until exactly4 ordinary explicits include Life9. Apply Fracturing Orb.
If wrong mod fractures, set item aside at salvage0 and buy another base; never free undo.
If Life9 fractures, repeat Deafening Envy until target. Report discarded bases and0 item
destruction separately. Stage Alchemy probability is entry to a preparation/early-stop
gate; fracture probability is desired Life9; finish probability is full target per Envy.

Magic: Transmute is paid setup and deliberately not checked. Alteration, then Augmentation
only if the roll has one modifier. If early_stop is true and target matches, stop. Otherwise
require at least magic_min_desired desired modifiers; failure resets with Scour+Transmute.
Regal, the analogous regal_min_desired gate, then up to max_exalts Exalts. Respect early_stop
at each stage; if false, check target only at the last configured stage. Failure/exhaustion
resets with Scour+Transmute. A desired modifier means a required target label, or positive-
value tier from the caller's utility table, NOT any high tier. If max_exalts=0 do not invent
an Exalt step. Stage probabilities in optimized Magic are REACH probabilities from the
start of one attempt, not success chances. Label "Шанс дойти до этапа"; total attempt
success is1/T. Counts are expected paid executions across the whole craft.

Other stage probabilities: simple spam = target per action; protected cycle = conditional
target per cycle; preparation = gate/early stop. Display the conditioning explicitly.
Quality20 is a supplied input, not a priced preparation step. Never say the route pays for
quality, base acquisition or sockets when the input cost is zero/fixed instead.

## Evidence JSON schema (version1)

The evidence worker produces proof.json with schema_version1, generated_at, git_commit,
working_tree_dirty, commands:[{name,argv,exit_code,duration_minutes,stdout_file,stderr_file}],
pytest:{status,tests,failures,errors,skipped,passed,duration_minutes,cases:[{name,classname,
file,status,duration_minutes,message}]}, coe:{status,case_count,cases:[...original comparison
rows...],max_abs_relative_difference,source_hashes}, artifacts:{pytest_xml,pytest_log,
coe_json}. Status is passed/failed/unavailable, never inferred from a missing artifact.
Paths are relative to the evidence directory. Renderer copies needed evidence artifacts
into report output directory, with source commit/time visible. A commit mismatch against
the report says "Проверки другой ревизии"; never claim current green based on old logs.

## Suggested module ownership

Report worker: src/craftoracle/reporting.py (pure build/render functions), optional
report assets in src/craftoracle/report_assets/, cli.py report subcommand, tests/test_report.py.
Evidence worker: tools/collect_evidence.py and tests/test_evidence.py only.
Lead runs complete fresh evidence after integration, generates helmet and bow reports,
reads every route's selected instructions/cost accounting and checks browser rendering.
