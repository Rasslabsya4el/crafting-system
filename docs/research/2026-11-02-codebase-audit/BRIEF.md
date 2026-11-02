# Codebase audit: shared brief (ticket #396)

Repository: the repository root (Python, `src/crafting_system/`, tests in `tests/`, ADRs in `docs/adr/`, glossary `GLOSSARY.md`,
claims in `src/crafting_system/rules/**/*.yaml`, example targets/routes/buy specs in `examples/`). Read-only audit: change NO file
outside `.claude/scratch/audit/`. A crafting planner for Path of Exile: given a target item, it finds the cheapest policy of crafting
actions and shows it as a route page.

## Why this audit exists

The owner opened three route pages and found, in minutes, faults that ~30,000 green tests never caught:
- a bench-crafted mod counts as tier 1 of anything (`actions/bench.py:57 CRAFTED_TIER = 1`, a placeholder of the item model from #56,
  later compared as a real tier by the target check from #60), so R05 "finishes" Life T1 / Resistance T2 with bench crafts: mean 12 c
  against the guide's 135 c;
- the R05 buy spec searches any ring while its target is an Amethyst Ring (two hand-written descriptions of one start item);
- V01 shows eight identical "Regal Orb" steps: the state splits on which junk suffix an Augmentation added, which no later decision reads;
- "at least 1 of 4" drawn as four mod lines; internal claim ids on the page; crafted colour missing in a target.
These three are SEEDS, not the scope. Your job is to find what else is wrong in your area, with evidence, and how it got there.
Do not just restate the seeds.

## What counts as a fault

Anything where the system's meaning silently differs from:
1. **the game**, as the sources say (repoe-fork data 3.29.3.3, the PoE wiki, Craft of Exile, GGG notes, trusted player tests; the
   claims in `rules/` record what was admitted and from where), or
2. **the owner's rules** (below), or
3. **its own docs** (an ADR, the glossary, a docstring, a claim) —
and nothing marks it approximate or refuses. Also a fault: a value invented to satisfy a type (placeholder) that later code reads as
meaning; one fact written by hand in two places with nothing reconciling them; a default that decides a game question; a test whose
expected value comes from the code under test (circular oracle) or a golden file nobody could have judged; state or output detail that
no decision reads; an output that shows internals instead of what a player does.

## The owner's rules (what he means; from his notes)

- An unstated tier is the TOP tier the item level allows, rolled, not from the bench. "Any of 9 Life tiers" is meaningless.
- A mod forced by an essence or bench craft is exactly that mod/tier; a bought start item's mod is the tier priced on the trade site.
- Every mod line in one format. Show every in-game step; never hide one (a bought item drawn "empty", an essence that reforges a rare
  without Scouring must be said). Never show the same route twice; show the guide's route only where it differs.
- Trade: instant buyout only, any listing age, price = mean of the cheapest few. Prices refresh by the system itself on a schedule.
- Crafter-like search: detail no later decision sees is not tracked at all (an Alchemy before a fossil is one state); exact among
  realistic routes; no hard-coded cut-offs (no fixed 100k-uses or probability thresholds); cuts must say what they still guarantee.
  "Approximate with an interval" reads to him as useless.
- The system models all known evidence up front; it never asks him to check something in the game mid-plan; unknowns get the best
  estimate and an approximate mark.
- Sources: no fixed ranking; stale sources lose; every rule carries source, URL, quote, date.
- He is not a crafter: he writes no targets or routes; agents do.

## How to work

- Read the code of your area fully, not samples. Use `git log -S`, `git log -L`, `git blame` and `gh issue view N` / `gh pr view N`
  (repo `Rasslabsya4el/crafting-system`) to find where a fault came from: which ticket, which PR, what the brief or ADR said.
- You may run quick python snippets or single targeted tests (under a minute, one process; `PYTHONPATH=src python ...`). Nothing
  heavy: no full suites, no solves of real routes, no `-n`. Real game data cache: `local/cache/repoe-fork/3.29.3.3`.
- Prefer concrete, reproduced findings over suspicions; mark each as CONFIRMED (you reproduced or read it unambiguously) or SUSPECTED.
- Never commit Craft of Exile code; never print the token from `git credential fill`.

## Output

Write your full findings to `.claude/scratch/audit/<your-area>.md`, one entry per finding:

```
### <AREA>-<n>: <one-line title>   [CONFIRMED|SUSPECTED] [impact: high|medium|low]
- Where: file:line (and any other places)
- What it does: ...
- What it should do (and per which source / owner rule / ADR): ...
- Evidence: the snippet you ran or the lines you read, with results
- Impact: which outputs, routes or features it changes, and how much if you can tell
- Origin: commit / ticket / PR / ADR where it came in, and what the brief or ADR said at the time
- Pattern: in one line, the general mistake behind it (e.g. "a type placeholder read as game meaning")
```

End the file with a section "Patterns seen in this area": the general mistakes behind your findings, each with the finding ids.
Then reply with a SHORT summary (at most 40 lines): counts by impact, the top findings in one line each, and the patterns.
