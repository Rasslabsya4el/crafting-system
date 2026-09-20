# Rules of work in this repository (read fully before doing anything; they outrank your habits)

This folder is its OWN git repository ("the crafting oracle"), nested inside `C:\Coding\poe-junkroan-v2` (the parent: a machine
search for Path of Exile builds with Path of Building as the judge). You work ONLY here. The mission and the phases are in
`docs/BRIEF.md`. You are building a prototype that a stronger model (the lead) will take over in a few days: EVERYTHING you
learn, decide or leave unfinished must be findable in the docs without asking you.

## 1. Boundaries

- Never create, edit, move or delete anything outside `crafting/`. The parent repository is READ-ONLY for you, and only these
  parts of it: `vendor/pob/source/src/Data/` (Path of Building's data files: `ModExplicit.lua`, `ModMaster.lua` (bench),
  `ModVeiled.lua`, `ModEldritch.lua`, `ModCorrupted.lua`, `ModDelve.lua`, `ModSynthesis.lua`, `ModJewel*.lua`, `ModFlask.lua`,
  `Essence.lua`, `ClusterJewels.lua`, `Bases/*.lua`), `docs/research/2026-09-20-crafting-oracle-brainstorm.md` (why this exists)
  and `CLAUDE.md` (the parent's principles, for context). Do NOT read `reference/legacy/`: it is unverified machine-written
  material and must not become a source of anything.
- Never touch the parent's `var/`, `artifacts/`, `vendor/` contents, `.claude/worktrees/` or any running process. Never run Path
  of Building, the parent's scripts or its tests. Never run `git` commands against the parent repository.
- Git here: commit early and often with a message that says what changed and why. Never `git add -A` / `git add .` -- add
  explicit paths. Never rewrite history. Nothing under `sources/raw/` is ever committed (it is third-party material, see 3).
- The machine is the owner's working PC and the parent project's benchmark queue uses 5 of its 12 cores around the clock:
  at most 2 worker processes of yours at a time, no job longer than ~10 minutes without a reason written in `docs/STATE.md`,
  no background process left behind when you stop. Every wait loop has a deadline.

## 2. Truth discipline (the reason the parent project works)

- **A number or a rule without a source does not exist.** Every mechanic, probability, weight, limit or exception you write
  into code or docs carries its source: a URL with the date you read it, or a file + function / line of cached material, or
  "PoB data: <file>, key <id>". Sources are ranked: the game's own datamined data (PoB's data files, PoEDB, RePoE) > the
  community wiki (poewiki.net) > Craft of Exile's code and texts > forum / Reddit posts by GGG staff > other player reports.
  When sources disagree, record BOTH and the disagreement in `docs/OPEN_QUESTIONS.md`; do not pick silently.
- **Never type a game fact from your own memory.** Your memory of Path of Exile is a hypothesis generator, not a source. If
  you cannot find a source, the item goes to `docs/OPEN_QUESTIONS.md` with status `unsourced` and the code path that needs it
  raises `NotImplementedError("unsourced: <question id>")` -- it never silently guesses.
- Confidence labels on every fact sheet: `datamined`, `documented` (wiki / GGG), `reimplemented-from-CoE` (we read how Craft
  of Exile does it), `player-report`, `unsourced`.
- Keep the CONDITIONS a source attaches ("only on influenced items", "before 3.19", "item level 68+"). A digested fact that
  lost its condition is worse than no fact.

## 3. Third-party material (Craft of Exile and others)

- You may download Craft of Exile's public files ONCE each and cache them under `sources/raw/coe/` (gitignored) to READ them:
  how each crafting action is implemented, which numbers it uses, what its guides say. Polite fetching only: one request per
  file, a pause between requests, no loops against the site, no automation of its UI at scale, never in a test or a benchmark.
- You do NOT copy their code or their compiled data files into `src/` or `data/`. You read, understand, write a fact sheet
  that cites the place you learned it from, and implement it yourself in Python. Game facts (weights, tiers, tags) come from
  the datamined sources; where only Craft of Exile has a number (harvest weights, mod-count distributions), it is recorded as
  a fact with the source "CoE" and its confidence label.

## 4. Documentation you keep current (the lead will start from these files)

- `docs/STATE.md` -- rewrite at the END OF EVERY WORKING SESSION: what works today (with the command that proves it), what is
  in progress, what is blocked and on what, the next three actions. Newest state only, not a diary.
- `docs/TASKS.md` -- the checklist of the brief's phases broken into tasks: `[x]` done (with the commit), `[~]` in progress,
  `[ ]` not started, `[!]` blocked (with the question id). Add tasks you discover; never delete a task, strike it with a reason.
- `docs/SOURCES.md` -- one row per source: id, URL or path, date read, what it was used for, where the cached copy is.
- `docs/mechanics/<action>.md` -- one fact sheet per crafting action / rule family (format in the brief).
- `docs/DECISIONS.md` -- one dated entry per design choice that a newcomer would otherwise have to guess (why this data
  source, why this item model, why this formula), with the alternatives you rejected.
- `docs/OPEN_QUESTIONS.md` -- numbered questions for the lead / the owner: unsourced facts, contradictions, judgement calls.
  The owner is an expert player: questions to him are concrete ("does X work on fractured items: yes / no?"), never essays.
- Docs and code comments in English. Reports to the owner in chat: Russian, short, tables with numbers, plain language.
  Durations for humans in minutes / hours, never large numbers of seconds.

## 5. Code

- Python 3.12, standard library + `pytest`; `numpy` is allowed for Monte Carlo. No web framework, no database, no async.
- Small pure functions; the item and the action are plain data; all randomness through an explicit `random.Random(seed)` /
  `numpy.random.Generator` passed in -- every simulation is reproducible from its seed.
- Tests first for every rule: a fact sheet's examples become tests. `python -m pytest -q` in `crafting/` must stay green and
  under a minute. Exact calculators are tested against hand-computed cases; Monte Carlo against the exact calculator.
- No speculative architecture: no plugin systems, no config frameworks, no abstract base classes "for later". The prototype
  is judged by whether its numbers are right and its docs are honest, not by its size.
