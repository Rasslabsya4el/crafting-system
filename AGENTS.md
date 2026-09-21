# Rules of work in this repository (read fully before doing anything; they outrank your habits)

This folder is its OWN git repository ("the crafting oracle"), nested inside `C:\Coding\poe-junkroan-v2` (the parent: a machine
search for Path of Exile builds with Path of Building as the judge). You work ONLY here. The mission and the phases are in
`docs/BRIEF.md`. You are building a prototype that a stronger model (the lead) will take over in a few days: EVERYTHING you
learn, decide or leave unfinished must be findable in the docs without asking you.

## 1. Boundaries

- Never create, edit, move, delete OR READ anything outside `crafting/` (the harness denies external directories on purpose).
  What you need from the parent is already copied in: `sources/pob/Data/` = Path of Building v2.67.2 (PoE 3.29) data files,
  MIT-licensed, not committed here (`ModExplicit.lua`, `ModMaster.lua` (bench), `ModVeiled.lua`, `ModEldritch.lua`,
  `ModCorrupted.lua`, `ModDelve.lua`, `ModSynthesis.lua`, `ModJewel*.lua`, `ModFlask.lua`, `ModItemExclusive.lua`,
  `Essence.lua`, `ClusterJewels.lua`, `Crucible.lua`, `Bases/*.lua`); `docs/background/` = why this project exists. The
  parent's `reference/legacy/` is unverified machine-written material and must never become a source of anything.
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
  Its calculator runs in the visitor's browser: for VALIDATION you may execute the cached files offline (zero load on the
  site), or, failing that, enter a dozen cases by hand-like browser actions in one session. That is cross-checking, not copying.
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

## 6. You are the LEAD; code that is not crafting logic goes to workers (no third party in between)

You work the way the parent project's lead works: YOU read the sources, decide what a rule is, write fact sheets, design the
strategy templates, write specs, review and merge. WORKERS (subagents you start in the Codex desktop app, with model and
reasoning chosen by you under the rule below) write code from your written spec. There is
no reviewer between you and them: you verify their work yourself. If you ARE a worker (your prompt names a spec and a
worktree), this section does not apply to you: `docs/WORKER_RULES.md` does.

- **Worker model and reasoning:** use GPT-5.6 Terra for ordinary worker tasks. For very light tasks where Terra would be
  excessive, use GPT-5.6 Luna instead. You choose the reasoning level yourself for each task, according to its scope and
  complexity; any reasoning level supported by the chosen model is allowed. Workers need not match the lead's model or
  reasoning level, and extra-high reasoning is not mandatory.
- **Delegate:** data builders and parsers (PoB's Lua tables -> our JSON), mechanical extraction from cached files ("list every
  crafting method in package.js with its options and the function that implements it" -- a TABLE with pointers, no
  interpretation), calculators and simulators from a formula or a fact sheet you wrote, tests, refactors, command-line glue.
- **Never delegate:** what a rule IS (reading a source and deciding), confidence labels, resolving contradictions between
  sources, the design of a strategy template, anything the owner asked you personally, `docs/STATE.md` / `TASKS.md` /
  `DECISIONS.md` / `OPEN_QUESTIONS.md`.
- **The spec** (`docs/specs/<date>-<slug>.md`, template in `docs/specs/TEMPLATE.md`): why; the files the worker may touch;
  numbered requirements; the fact sheets it implements; the NUMBERS A TEST MUST REPRODUCE (a spec without checkable numbers is
  not ready); what to report. One spec = one worker = at most ~90 minutes of work; bigger means split it.
- **Isolation:** one git worktree per worker: `git worktree add .worktrees/<slug> -b w-<slug>` (`.worktrees/` is ignored).
  Leftover worktrees cost nothing: after the merge use `git worktree remove .worktrees/<slug>` WITHOUT `--force`, and never
  delete a worktree directory by hand or recursively.
- **How to start a worker:** with the Codex desktop app's own way of starting a subagent / parallel task. The worker's prompt
  is always exactly this shape: "You are a WORKER. Read docs/WORKER_RULES.md first, then AGENTS.md sections 1, 2, 3, 5. Spec:
  docs/specs/<file>. Your worktree: .worktrees/<slug> (branch w-<slug>) -- work only there." Save each worker's final report
  to `out/workers/<slug>.md`. The FIRST delegation is a smoke test: a five-minute spec (for example "a function that parses
  one row of `sources/pob/Data/ModExplicit.lua` into a dict + two tests") to prove that a subagent starts, works in its
  worktree, commits and reports. If subagents cannot be started in your environment, say so in `docs/STATE.md`, tell the
  owner in one line, and do the code yourself under the same spec-and-tests discipline -- never stop the project for it.
- **Network:** if your sandbox blocks web access, do not fight it: write the exact list of URLs you need into
  `docs/OPEN_QUESTIONS.md` and ask the owner in chat to allow the network or to drop the files into `sources/raw/coe/`.
- **At most 2 workers at a time** (the owner works on this PC and the parent project's benchmark queue owns 5 of its 12
  cores; a worker's tests are light, its process is not free). Non-overlapping files only.
- **Acceptance is yours, item by item:** (1) the worker's tree is committed (commit leftovers as "WIP (lead)" on its branch);
  (2) run the tests on its branch YOURSELF -- never trust a reported summary line; (3) read the WHOLE diff against the spec's
  numbered requirements; (4) check every "number to report" against the value the spec asked for; (5) a fact that appeared
  in code without a source = rejected, send it back or fix the fact sheet first; (6) merge with `git merge --no-ff w-<slug>`
  and a message that carries the numbers; (7) one row in `docs/WORKERS.md`. A worker that died twice on one spec means the
  spec is too big or too vague: rewrite it, do not retry a third time.

