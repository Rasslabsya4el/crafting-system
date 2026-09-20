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
