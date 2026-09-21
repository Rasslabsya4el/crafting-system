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
