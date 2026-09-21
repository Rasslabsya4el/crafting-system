# GOAL 2 (2026-09-21; written by the project lead after running the helmet plan: 9 policies, 248 tests, goal 1 accepted)

Re-read this file whenever you finish a task, lose track, or feel like stopping. It outranks your own plan.

## The goal in one sentence

Turn the working slice into an oracle whose numbers can be TRUSTED and whose policies are OPTIMISED, and line up the blocked
crafting families so that one sitting of the owner's yes / no answers unblocks them.

What the lead saw in goal 1's output (keep it in mind): the essence-spam number (p = 0.26% per Deafening Envy) is plausible;
the protected-life route is evaluated with ONE Exalted Orb per "suffixes cannot be changed" cycle, although after the Scour
three prefixes are open -- a player would slam up to three times per cycle; and the route a player would really use
(protect suffixes, then a harvest "reforge life") is blocked by Q6. Templates need PARAMETERS and an optimiser over them,
and the most valuable blocked families need their questions answered.

## Order of work

1. **External validation pack** `docs/validation/coe_cases.md`: 12 cases on real pools (helmet, body armour, ring, amulet,
   boots; Chaos, Alchemy, essence, Exalted on a prepared item, Alteration / Regal), each with OUR exact number and the exact
   inputs to click in Craft of Exile's calculator, and an empty column for its number (the owner fills 3-5 of them by hand; do
   not automate the site). If the cached code lets you reproduce Craft of Exile's formula offline for a case, add that number
   too and explain any relative difference above 5% (Q14) -- two correction rounds at most, then record and move on.
2. **The owner's question sheet** `docs/OWNER_QUESTIONS.md`: at most 15 yes / no (or one-number) questions, ordered by how
   much each unblocks: harvest reforges with metamods first, then fossils, fracturing, veiled mods, eldritch implicits,
   recombinators, Awakener's Orb. Per row: the question, what it unblocks, what you will assume if there is no answer. Tell the
   owner in chat that the sheet exists. Do NOT wait for the answers.
3. **Template parameters + an optimiser**: every template exposes its real choices (Exalted Orbs per protected cycle, the
   acceptance rule of each stage, which target mod is forced / left to the bench, the base's item level where it changes the
   pool); a small exhaustive or grid search picks the best instance per template; the plan prints the chosen parameters.
   Number to report: the protected-life route's expected cost before / after.
4. **Research test -- a general solver**: value iteration (or policy iteration) over the abstract state space (per target
   group none / tier class, junk prefix / suffix counts, rarity, crafted and metamod flags) using ONLY the implemented actions
   and the price table. Accept when, on the helmet and on three tiny synthetic cases with hand-checkable optima, its expected
   cost matches or beats the best template, and the policy it found prints as readable steps. Report the number of states,
   the run time, and where it differs from the templates. Two correction rounds; if it does not converge or explodes, park it
   with the findings -- a negative result with numbers is a result.
5. **The value-table path end to end** on the bow example (if any part is missing): one outcome distribution per stage, the
   stop threshold swept over it, the frontier table (expected value, expected cost, 90th-percentile cost per point).
6. **When the owner's answers arrive**: for each unblocked family, in the sheet's order: update the fact sheet -> spec ->
   worker -> hand-computed tests + exact-vs-Monte-Carlo -> a template that uses it -> the helmet / bow plans re-run, with the
   change in the best policy reported.

## DONE when

Items 1-5 are merged and green (`python -m pytest -q` under a minute), `docs/STATE.md` has a ten-line summary on top with the
numbers of items 3 and 4, everything is committed with explicit paths, and the owner got a short Russian message: what
changed, the two numbers, the question sheet's path. Item 6 continues whenever answers exist.

## STOP only when

DONE and no answered question is left to implement; or nothing in the order of work is unblocked (name the blocker); or the
owner says stop. Never stop because a task "feels finished" or to wait for a worker or for the owner.

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
