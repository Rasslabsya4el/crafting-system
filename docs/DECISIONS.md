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
