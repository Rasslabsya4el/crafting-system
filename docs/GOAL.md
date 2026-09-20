# GOAL for the night of 2026-09-20 -> 21 (written by the project lead after reading STATE, TASKS, OPEN_QUESTIONS, WORKERS)

Re-read this file whenever you finish a task, lose track, or feel like stopping. It outranks your own plan for tonight.

## The goal in one sentence

By morning `python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json` prints a
ranked table of real crafting policies for the owner's helmet (item level 86: T1 life prefix, T1 chaos resistance and one T1
elemental resistance suffix) with EXACT stage probabilities, expected cost, 90th-percentile cost, steps and assumptions -- built
on an engine whose numbers are tested. A VERTICAL SLICE that works end to end beats any amount of further research.

Phase 0 is accepted. It was thorough; it also shows your risk: 30 open questions and a habit of re-verifying everything.
Tonight you BUILD. Research is allowed only when a task below needs one specific number, for at most 15 minutes, recorded as usual.

## Lead's provisional decisions (label them `lead-provisional 2026-09-20` in DECISIONS.md; they unblock the slice, the lead revisits them on Thursday)

- Q2: probabilities are mathematically exact weighted draws. Craft of Exile's random-integer boundary quirk is an
  implementation artifact, not a game rule.
- Q4: a rare reroll yields 4 / 5 / 6 mods with weights 8 / 3 / 1 -- accepted with the label `reimplemented-from-CoE`
  (it is also the long-standing community figure). It is DATA (a parameter file), never a constant in code; every plan prints
  it under "assumptions".
- Q7 and every other price: prices are inputs from the price table / loadout file, not facts. Use the cached bench costs as
  the example file's defaults and move on.
- Q9: tonight's engine accepts ONLY normal / magic / rare items that are not corrupted, influenced, fractured, synthesised,
  mirrored or split. Anything else raises `NotImplementedError("out of tonight's slice: Q9")`.
- Q16 / Q17: tonight the exclusion family of a mod is PoB's `group`, weights are PoB's `weightVal` by the base's tags;
  `weightMultiplier` and generated tags are NOT applied unless a fact sheet holds a sourced rule. The demo stays inside the item
  classes where your cross-check agreed 54 / 54. Printed under "assumptions".
- Q14: do not try to prove or disprove Craft of Exile's "exact" path tonight. OUR exact calculator is validated against OUR
  Monte Carlo and against hand-computed tiny pools; agreement with Craft of Exile is a later, separate check.
- Everything in the families that are blocked by questions (recombinators, Awakener's Orb, harvest, fossils, eldritch
  currency, corruption, beasts, veiled, fracturing, catalysts) stays OUT tonight: a stub that raises with the question id.

## Order of work (each line = one spec -> one worker -> your acceptance -> merge -> TASKS / WORKERS rows -> next)

1. **Item model + mod-pool resolver** for armour / jewellery bases: (base, item level, existing mods) -> legal prefixes and
   suffixes with weights; level gate, group exclusion, 3 / 3 limits for rares and 1 / 1 for magic. Numbers a test must
   reproduce: at least 10 spot checks of single-mod weights and pool totals against your own cross-check data.
2. **Outcome distributions, exact**: Transmutation, Alteration, Augmentation, Regal, Alchemy, Chaos, Exalted, Annulment,
   Scouring, essences (forced mod + the random rest), bench crafts (deterministic), the metamods "prefixes / suffixes cannot be
   changed" combined with Scouring and reroll actions. A calculator returns the DISTRIBUTION over outcome classes relevant
   to a target (BRIEF 3b), by dynamic programming over "target groups vs everything else", not by enumerating every mod set.
   Tiny synthetic pools (3-5 mods) with hand-computed answers are the first tests.
3. **Monte Carlo harness** with explicit seeds; it must agree with (2) within its stated sampling error on at least five
   real-pool cases. Where exact is infeasible, the plan says "estimated" and gives the error.
4. **Loop costs**: expected attempts, expected cost, 90th-percentile cost of a spam loop (geometric distribution), chaining of
   independent stages.
5. **Item spec, price table, loadout files**; the helmet example; the second example with an (invented, marked) value table.
6. **Policy templates** in this order: (a) one-action spam -- Chaos, Alchemy + Scouring, essence; (b) Alteration ->
   Augmentation -> Regal -> Exalted / bench; (c) make one half, protect it with a metamod, reroll the other half, finish with a
   bench craft. Then **the ranker and the CLI**.
7. Stretch, only after 1-6 are merged and green, in this order: 30+ known-answer tests with sources; the Pareto filter and
   the value-table threshold (BRIEF 3b) on the bow example; then the cheapest unblocked family from your own catalogue.

## DONE when (all true)

- the command in the first section prints at least three ranked policies for the helmet, each with per-stage probability,
  expected attempts, expected cost, 90th-percentile cost, steps, decision points and the assumptions used;
- `python -m pytest -q` is green and under a minute, and contains hand-computed exact cases AND exact-vs-Monte-Carlo cases;
- `docs/STATE.md`, `TASKS.md`, `WORKERS.md`, `DECISIONS.md` are current, and a morning summary for the owner exists in
  `docs/STATE.md` (top section, ten lines) and in chat in Russian: what works (commands), the helmet's numbers, what is parked
  and why, questions that need a yes / no.
If DONE is reached early, continue down the stretch list; do not stop.

## STOP only when

- DONE is reached and the stretch list has nothing unblocked left; or
- nothing in the order of work is unblocked (say exactly which question blocks what); or
- the owner tells you to.
Never stop because a task "feels finished", because a worker is running (write the next spec meanwhile), or to ask a question
that has a provisional answer above. A question without a provisional answer: write it to OPEN_QUESTIONS.md, take the most
conservative option, mark the code path, keep going.

## Token discipline (the owner pays for every one of them)

- One task = one spec = one worker, at most TWO correction rounds; after that park it in TASKS.md with the reason and move on.
- Acceptance = you run the tests, read the diff against the numbered requirements, check the reported numbers. Do NOT
  re-verify record by record what a test already proves; sample 20 rows and the edge cases. No "independent acceptance" of
  work that was already accepted.
- No refactors, no renames, no new abstractions, no new fact sheets, no catalogue expansion, no re-audits tonight.
- A test that still fails after three fix attempts: park the task, write what you learned, move on.
- A worker silent for 30 minutes or dead twice on one spec: the spec is too big -- split it once; if it dies again, do that
  piece yourself.
- Every hour, one line in `docs/STATE.md` under "Night log": time, task, merged / in progress / parked. No essays.
