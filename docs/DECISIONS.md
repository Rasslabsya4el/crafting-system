# Decisions (one dated entry per design choice, with the alternatives rejected)

## 2026-09-20 D1. A local engine, not Craft of Exile as a service
The lead and the owner: crafting is data + about fifty action rules + a few sourced numbers; a local engine runs millions of
rolls a second, a website cannot be queried at that scale and must not be. Craft of Exile is read to learn the rules and is a
reference for a few dozen known-answer tests. Its code and compiled data are not copied.

## 2026-09-20 D2. Strategy TEMPLATES before any general solver
An optimal-policy solver over all item states is research. The prototype ranks a library of templates typed by mechanism
(spam, alt-aug-regal, protect-one-half, blocking, eldritch finishing, fracture-then-spam), each with an exact or Monte Carlo cost.

## 2026-09-20 D3. Freeze local evidence; do not execute downloaded JavaScript
Use the in-repository PoB snapshot only. Cache each public CoE URL once, record its size and SHA-256,
and read it locally. A `.json` suffix does not imply a JSON document: S2 is a JavaScript assignment.
Readers must parse supported data syntax, never evaluate third-party application code. Rejected:
reading the parent checkout, silently refreshing live data, or using CoE as a simulation service.

## 2026-09-20 D4. Prove delegation with a deliberately limited projection
The first worker gets one PoB row, eight projected fields, and two tests. This validates isolation,
source traceability and lead acceptance before a full data builder is specified. It does not establish
general Lua parsing or crafting eligibility. Workers use GPT-5.6 Terra with xhigh reasoning, with
at most two active workers, each in an ignored worktree contained in this repository.

## 2026-09-20 D5. Separate an observed CoE branch from a current-game claim
S3 is shared between games; S12 supplies PoE 1 overrides. Use named PoE 1 branches and keep
legacy/toggle conditions. CoE prose does not get the `documented` label reserved here for wiki/GGG:
reviewed CoE code/text uses `reimplemented-from-CoE`. PoB field facts use `datamined`.
Unknown current-patch behavior stays `unsourced`; the cache date alone proves no patch compatibility.

## 2026-09-20 D6. Do not reproduce apparent reference bugs in the future exact engine
Q2 records CoE's half-open random API combined with inclusive weighted intervals. Mathematical
weighted draws will use all weight units, with tiny hand-computed tests before implementation.
Reference implementation quirks must be reported separately from intended probabilities.
Q6 and Q7 show that the same site's prose and code/data can disagree; neither is silently discarded.

## 2026-09-20 D7. Outcome distributions precede target tests
Source: owner instruction and `docs/BRIEF.md` section 3b, read 2026-09-20. This is a design
requirement, not a game mechanic. Exact calculators and Monte Carlo summaries must expose an
outcome distribution over resulting mod sets or explicitly defined scored classes. Required-mod
predicates and utility thresholds consume that distribution; a scalar target probability alone
is not the calculator contract. A scoring table is supplied by the caller and is a fast estimate,
especially for weapon local-mod interactions; it is not an exact PoB evaluation.

A policy includes its stopping rule and decisions to continue, restart, or stop after failure.
Evaluation reports expected utility, expected cost, 90th-percentile cost, irreversible-failure
risk, and required rare inputs. The ranker returns a Pareto frontier among evaluated templates,
not a claim of globally optimal crafting. Cost quantiles are not confidence intervals.
Do not merge states merely because their scores match if future legal actions or transitions
differ. Any coarse distribution must state what information is lost before policies use it.

Rejected: designing a success-only engine and bolting utility onto the ranker later; treating
an additive value table as exact weapon damage; dropping failed outcomes and renormalizing
without reporting their probability. No parent-system integration or general policy solver
is introduced. Contract acceptance examples are in `docs/design/build_contract.md`.

## 2026-09-20 D8. A literal PoB projection before a resolver
The first full-file builder exports all 4310 ModExplicit rows, the existing eight projected
fields plus source_line, raw-byte hash and owner-supplied version provenance (S24). Keep weight
key/value arrays ordered and retain zero weights. It supplies neither inferred tiers nor an
item model, stat ranges, first-match weight resolution or influence rules. Rejected: advertising
this partial projection as an engine-ready mod pool, or filtering it for the helmet target.
Other PoB tables, base tags and cross-source comparisons remain separate phase-0 work.

## 2026-09-20 D9. Preserve base source occurrences, not unique display names
S27 ring.lua contains Two-Stone Ring assignments at 105/114/123 and Shadowed Ring at
312/321/330: 48 ring records but 44 names, 375 records / 371 names across the five files.
The literal projection identifies an occurrence by (source.path, source.line), retains all,
and does not execute Lua or claim which variant would be live after runtime evaluation.
Rejected: silently overwriting variants by name, dropping them, or inventing game IDs. The
first spec incorrectly required unique names; worker stopped and lead corrected it before
acceptance. Full base identity and availability remain future resolver work.

## D10 — 2026-09-20 — Cache freshness does not establish one ruleset
Official 3.29 notes (S39) disagree with frozen CoE action labels/paths for corruption sockets,
synthesis, beast splits and Fractured Fossils. Keep the mechanical inventory as historical
source evidence; classify version deltas in patch_3_29.md and per-action sheets. Rejected:
silently refreshing CoE, deleting old inventory entries, or treating every cached path as
current. Q3 still determines target; scoped 3.29 facts can be documented before that answer.
Awakener group-conflict resolution is an additional non-version-resolved disagreement (Q20),
so its implementation remains unsupported rather than inheriting CoE receiver preference.


## D11 — 2026-09-20 — Target ordinary PoE 3.29 and retain epistemic boundaries
Owner explicitly answered yes to PoE 3.29 / ordinary mode (not Ruthless). Q3 is resolved.
Use the official 3.29 changes when classifying current actions; retain legacy source notes as
historical evidence. This supersedes D10's pending-target sentence, not its source discipline.
Choosing a patch does not settle disputed odds, complete missing eligibility matrices, or
convert CoE algorithms into datamined facts. Reject silent compatibility with every cached mode.

Phase 0 closes against the BRIEF's researched-sheet/data criteria, with unsupported branches
listed by question ID. It does not promise a simulator for every catalogue entry. BRIEF 3b
remains binding for the next implementation slice; CoE rounding/action-count shortcuts Q28
are not acceptable substitutes for exact mean and p90 cost.

## D12 — 2026-09-20 — Preserve source literals before interpreting stats
The six-table projection adds stat_text/statOrder and optional tag/multiplier arrays to the
fields needed for future resolver work. Source ranges remain strings; fractional statOrder
values stay numeric literals (S24 SpiritMinionEssence1 [774,774.1], S11 bench line 308
[857,857.1]). They are not invented integer game stat IDs. Missing fields stay null, empty
weight arrays stay empty, and record identities include the source file.

Keep the accepted initial explicit projection for the existing comparison tool; new family
data is the fuller source projection, not a second canonical ruleset. A future refactor may
share parsing primitives after a separate spec. Rejected: silently changing the comparison
schema during acceptance, rounding ordering values, deriving tiers from display affixes, or
treating retained multipliers as understood percentage rules (Q17).

## D13 — 2026-09-21 — Provisional ordinary pool boundary for the vertical slice
The night goal uses the accepted PoB literal projection with first matching base-tag weight,
PoB group exclusion, level gates and ordinary prefix/suffix caps. Generated tags and weight
multipliers remain retained data but are not applied (Q16/Q17). Non-ordinary flags raise the
exact Q9 error. Rejected: silently modelling blocked action families, inferred tier parsing,
or a resolver that treats all cached modifier tables as one pool.

## D14 — lead-provisional 2026-09-20 — Night goal overrides unresolved research gates
Authority: owner-authored docs/GOAL.md. Use unbiased exact weighted draws (Q2); rare
reroll counts 4/5/6 with weights 8/3/1 in a sourced parameter file, printed in assumptions
(Q4, reimplemented-from-CoE); prices are caller inputs, cached bench costs only example
defaults (Q7). Restrict flags to ordinary uncorrupted/uninfluenced/unfractured/unsynthesised/
unmirrored/unsplit items (Q9). PoB group and first base-tag weight are provisional exclusions
and weights; omit generated-tag/multiplier effects (Q16/Q17), print that assumption.
Validate exact math against hand cases and independent seeded Monte Carlo, not CoE Q14.
Blocked special families remain explicit question-ID stubs. These decisions supersede
the old requirement to settle every research question before the ordinary vertical slice.

A lead spec arithmetic error counted extra tables; corrected BEFORE implementation to only
ModExplicit rows: Royal Burgonet level 86 prefix/suffix 41/84, weights 39275/78400.
Existing duplicate base display names use explicit source occurrence identities (D9), not
a loader that rejects the accepted snapshot. No earlier accepted projection is re-audited.

## D15 — 2026-09-21 — Terminal projection, concrete policies and input tiers
Use an exact grouped-draw DP retaining every group's removal effect internally, then project
to labelled target/scored classes and affix counts only at terminal output. Exchangeable
groups share side, totalweight and full label-weight histogram; all junk is never pooled into
a reusable weight. Arbitrary later transitions cannot consume these lossy classes. Fixed
magic-to-rare schedules keep group state through the full schedule. Sources: GOAL/BRIEF3b
and mathematical spec 2026-09-21-exact-distributions.md.

Policy designs live in docs/design/night-policies.md. In particular suffix protection requires
three suffixes and a free prefix, then lock/scour/one-exalt loops to avoid a full-prefix dead
end. Costs include every paid reset; chain p90 is convolved, never sum of stagequantiles.
Strict helmet tier IDs are explicit base-qualified source mappings. Greed essence91..105life
is below ordinary target130..144 and cannot count as T1 success. Envy guarantees ChaosResist6.
Example utility/price values are invented caller inputs. JSON-compatible YAML avoids an
extra dependency; unsupported YAML syntax fails clearly. No inferred general tier framework.

## D16 — 2026-09-21 — Exact means and explicit bounded p90 estimation
The fixed magic sequence can require millions of lattice cost points because Augmentation
is conditionally paid. Keep exact mean/attempts and exact stage probabilities. If the exact
compound-cost convolution reaches its documented work limit, an explicit seeded Monte Carlo
samples geometric attempt count then the binomial count of extra Augmentation charges.
Report estimated p90 with a99% DKW quantile interval, sample count and seed. Never multiply
mean attempt cost by geometric p90 or silently label sampled p90 exact. Ordinary fixed-price
loops and affordable independent-chain convolutions retain exact quantiles. This is GOAL's
permitted labelled estimation for an infeasible exact calculation, not a different policy.

## D17 — 2026-09-21 — Provable bench finish and bounded Divine stretch
The protected helmet policy's final prefix identity is known (Life9); only suffix junk is lost.
A compatible ordinary prefix bench craft can therefore be proved legal by excluding every
possible suffix group, without pretending the terminal class contains full item identities.
Offer an additional bench131 armour variant with sourced recipe2chaos (S2 benchcosts2775b52
tier index2, S3 currency index2, S4 range56..74 matching S11 index131). Keep the unbench-finished
policy because the target itself needs no armour craft. Reject guessed finishes on spam results.

Focused cached-source lookup on2026-09-21 took under15minutes and addressed this one required
finish quantity plus Divine's existing range sampler, not a Phase0 re-audit. Stretch family
selection is ordinary Divine: existing sheet already sources integer rerolls. Implement one
integer range per affix with side locks, explicit unsupported shapes and an enumeration limit;
do not infer all numeric stat semantics or add a general parser. New spec records75 real
Life9/Chaos6 outcomes and hand event2/15. Other special families remain question-ID stubs.

## D18 — 2026-09-21 — Frontier compares completed policies and explicit stopping rules
BRIEF3b requires both value and cost. Compare expected terminal utility (conditional on
completion), expected cost, cost p90 and irreversible item-destruction risk. A dominating
candidate is no worse in every dimension and strictly better in at least one; identical
points both remain. Rare-input permissions constrain candidates before comparison, without
inventing a numeric ordering on input names. Keep dominated policies visible in the full
ranked table and mark frontier membership separately, so the helmet demo retains its recipes.

Compare bow thresholds60/100 by reusing caller-owned raw distributions and recalculating
stopping probability, conditional utility and cost for each threshold. Do not reuse a score
projection as a transition state or turn threshold100 into the user's minimum requirement60.
Single-threshold IDs stay stable; comparison IDs include their stopping threshold. Rejected:
one scalar value/cost ratio, dropping all but the cheapest helmet policy, and a global cache
whose result could survive changed pool weights. Risk remains distinct from overspending.

The real bow baseline exposed constant utility100 as99.99999999999999 for one mechanism
and100 for another. Center the conditional weighted mean on one observed utility before
summing differences: constant values then remain exactly constant. Do not invent a risk/
cost/utility comparison epsilon that could hide genuine small differences. This bounded
integration correction belongs to the frontier spec, not a general numerical refactor.

## D19 — 2026-09-21 — Lead selects worker model and reasoning per task
Owner instruction in chat supersedes the earlier fixed Terra/xhigh worker setting and the
requirement to match the lead's model. Use GPT-5.6 Terra for ordinary tasks and GPT-5.6 Luna
for very light tasks where Terra would be excessive. The lead independently chooses any
reasoning level supported by that model according to task scope and complexity. The earlier
workers' recorded settings remain historical facts; no completed work is rerun. Isolation,
written specs, direct lead acceptance and the two-worker limit remain the governing workflow.

## D20 — 2026-09-21 — Apply owner answers and authoritative behaviour sources
Official GGG behaviour statements resolve the question they actually address. S19 establishes
type-restriction support for tagged Harvest reforges in3.27; side protection also has S14/S17/S42
and owner row1. Do not keep the entire family blocked over the narrower first/later-draw gap.
Owner row2 authorizes S14's first-only interpretation, printed as an assumption, until better
evidence resolves it. The alternative all-draws branch is a sensitivity model only.
Rare4/5/6 weights8/3/1 and multimod2 Divine now have owner confirmation in addition to CoE.
S21 and S63 resolve the essence boundary: Screaming+ adds rare eligibility while retaining
normal eligibility; magic is never allowed. Preserve the owner's uncertain recollection in
OWNER_QUESTIONS rather than silently rewriting what was answered.

## D21 — 2026-09-21 — Preserve CoE observations and separate input prices
The owner explicitly requests all132 S14 interaction cells, their notes and patch-lag warning.
The JSON is our factual observation schema with source pointers, not a copied compiled CoE
database or a universal executable permission matrix. Historical rows and source typos remain.
The latest owner instruction selects CoE's default additive positive fossil-factor model
where stronger sources do not decide the question; retain multiplicative sensitivity evidence.
Example prices are invented inputs: use harvest_reforge:<tag> as atomic craft price keys,
normal tagged reforge1, Sacred add/remove placeholder100, and minion/elemental/attribute/mana
100 each. The latter equality and availability are owner-provisional (row3); no exchange rate
or actual Sacred price is claimed. The planner must disclose these assumptions.

## D22 — 2026-09-21 — Search legal cycles and price every replacement
Parameter design lives in design/parameter-search.md. A failed third Exalt leaves no slot
for a prefix suffix-lock: restart preparation and charge it. Retain concrete group state
through gates; a target-label/junk-count abstraction is not generally Markov. Reject free
relocks and independent cost/target approximations. Item-level search requires caller opt-in.

Answered family designs are in design/family-policies.md. Fossil adapter supports18 ordinary
fossils; policy enumerates a caller allowlist of at most4 (15 subsets), initially1/12/13/14.
This availability bound keeps exhaustive search reviewable without claiming global coverage.
Example fossil prices1 each, resonator prices1/2/3/4 and Fracturing1000 are invented inputs.
Fracture-Life then Envy pays each failed base and preparation, salvage0 explicitly. Comparing
early completion off/on preserves useful already-complete Alchemy results. Catalyst policy
finishes a supplied jewellery item; no inferred damage value or whole-jewellery craft added.

## D23 — 2026-09-21 — Bound regression fixtures and measure complete plans separately
Adding full fossil and Magic grids to every real CLI regression would exceed the under-one-
minute pytest contract without increasing each assertion's evidence. Routine real CLI tests
therefore use explicit smaller loadouts: helmet fossil1, bow fossil13, Magic permissions
disabled. They retain the real action kernels and protected/Harvest/bench assertions.
Small synthetic exhaustive grids cover combination choice and Magic cost/seed/terminal
behavior. The existing fixed Magic real benchmark is retained. Complete default helmet
and bow commands, including all15 fossils and96 Magic variants, are still mandatory
outside pytest; save their complete outputs and report their separate timings. Rejected:
calling a bounded-loadout result the default plan, dropping numerical assertions, or
weakening the production search domain merely to make regression faster.

## D24 — 2026-09-21 — Show executable routes and evidence to the owner
The owner requests readable step-by-step routes, costs and probabilities plus visible
proof of system execution. This authorizes a bounded local HTML report despite the
brief's earlier no-UI scope. Generate it from actual planner output, keep every route and
unavailable reason, and retain the raw JSON. Russian player instructions use the exact
selected policy gates; no new craft mechanics are inferred during translation.

Mean material counts derive from accepted stage/renewal outputs and reconcile to total
mean cost. Magic stage reach probabilities are labelled as reach, not success; p90 and
its estimation interval remain distinct. Evidence comes from fresh pytest JUnit/logs and
the offline CoE comparison, with revision/time and scope visible. Tests establish model/
implementation behavior, not empirical whole-route game odds. See design/route-report.md.
Rejected: screenshots of a claimed green summary, manually typed demonstration prices/
probabilities, a framework/server requirement or a dashboard that hides unsupported routes.

## D25 — 2026-09-21 — Approve a state-and-transition layout before integration

Owner requests visible3-prefix/3-suffix states, action purpose, successful results,
stop/skip/retry branches and event-conditioned odds. Prepare three standalone views of
the SAME saved protected Envy route: step cards, directed map and manual execution
guide. Use historical02bceff output and sourced slot/metamod behavior; do not rerun
craft calculations or change strategies. Recommended composition: main cards plus a
compact map. Selection is the owner's design approval(Q31), not a crafting truth gate.

Preparation follows the actual selected gate(all3 suffixes occupied,2 desired elemental
T1 suffixes, at most1 prefix), not the owner's illustrative empty-suffix sketch. Early
target completion takes precedence.6.7% belongs to the whole up-to3 Exalt series;
no per-sphere conditional odds are invented.

Evidence distinguishes whole-route validation, same-base component checks and global
regressions. C01..C03 use the helmet but do not validate the entire route; C04..C12 are
other-base engine cases. The latter belong in a separate collapsed section. Do not
expand policy coverage while output is under review. Currency artwork is deferred;
text action chips suffice to choose layout. No external skills used.

## D26 — 2026-09-21 — Preserve original English modifiers everywhere

Owner explicitly requires all modifier names and stat descriptions in original English
throughout the project. Russian instructions and UI explanations remain acceptable;
modifier text must come from existing English source labels, never a translation.
Apply to the prototype and current report formatter, and refresh saved presentation
from existing plan/context/evidence without rerunning craft calculations. Rejected:
localized modifier descriptions or a Russian-only option for modifier text.

## D27 — 2026-09-21 — Owner rejected the verbose layout; use direct branches

D25's three-view prototype failed owner review despite passing technical checks. The
owner could not identify what to hit, what passes and what repeats: generic words
such as preparation/state search and tiny rule subtitles obscured those conditions.
Repeated before/after item cards also made the flow harder to follow. Technical
acceptance must not be recorded as product approval.

Replace with ONE compact flow: Envy -> bench plus Scour -> Exalt. Every branch states
its actual condition and destination. Two item states lie on connecting edges and
serve as the next step's input; never repeat before/after pairs. Conditional finish
comes first. Details about costs, assumptions and evidence live in one closed footer.
Original English modifiers required byD26. No new craft calculations or strategy work.
Implementation contract:docs/specs/2026-09-21-simple-route-flow.md. Q31 remains output
review, but the rejected A/B/C format-selection question is superseded.
