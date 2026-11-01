## Agent skills

### Issue tracker

Issues live in GitHub Issues for `Rasslabsya4el/crafting-system` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## How work is split

The main chat thinks and decides: the idea, the grill, the ticket, the plan, the verdict on a change. The doing goes to the helpers in `.claude/agents/`, each on its own model:

- `coder-light` (Haiku 5.5): a piece the main chat can spell out exactly: the files, the places in them (`file:line`), the result and the test that shows it. Plain code: a script, a config, a test, a case added by a pattern already in the code. The default once a ticket is cut into pieces.
- `coder` (Sonnet 5.5): a piece that needs its own judgement: subtle logic where a wrong detail breaks the result, a change across several modules, a defect whose cause is not yet known, or a piece `coder-light` handed back unclear or unfinished.
- `finder` (Haiku 5.5): wide reading and search; the main chat keeps only its facts.
- `checker` (Sonnet 5.5): every change, against its ticket, before it lands.

Each helper prompt names its ticket (`#N`), the files or worktree, and the result to reach. A `coder-light` prompt also carries the places to read with their line ranges; `finder` finds them when the main chat does not know them. Pieces that touch different files run in parallel, each coder with `isolation: "worktree"`.

Model of the main chat: Opus for ideas, grills and decisions; Sonnet 5.5 for a stretch of plain implementation. A session started for one ticket runs on Sonnet 5.5 with effort high.

Landing a ticket: its session opens the PR with `Closes #N`, turns Auto-fix on itself and never merges. The main chat merges the PR itself once the integration run (a `workflow_dispatch` of `ci.yml` on an `integ/...` branch holding `main` plus the PRs) is green on Ubuntu and Windows, the `checker` has passed it and its tests cover the ticket's "Done when"; a PR's own CI runs Ubuntu only and is feedback for its session, and a session that needs Windows early dispatches `ci.yml` on its branch; then it runs the tests on `main`, adds the ticket to the map's decisions and archives the session. Nobody asks the owner about Auto-fix or merging. A push to `main` starts no CI run: `main` is verified by the integration run, whose tree must equal `main` after landing (`gh workflow run ci.yml --ref main` tests it on demand; `docs/ci.md`).

One task per chat. The state of the work lives in the GitHub issues, so a `/clear` between tasks loses nothing.

Everything this repo needs lives inside this folder: worktrees in `.claude/worktrees/`, scratch files and run output in `.claude/scratch/`.

## Heavy runs

**Nothing heavy runs on the owner's PC.** Locally only quick, targeted tests (under a minute, one process); the full suite, sweeps, solves and measurements go to GitHub (CI, or a heavy run), because a local multi-process sweep pins his machine at 100%. Heavy runs go **only through the dispatcher**: `python .github/scripts/heavy_dispatch.py run --ref <branch> --runners N --command '...'`, never `gh workflow run run.yml`. The repo has 20 runner jobs at once; the dispatcher waits on the PC until merge CI keeps a buffer (`HEAVY_FLOOR` and `CI_RESERVE`, repository variables), and refuses a timeout over 60 minutes unless `--long` (one indivisible solve): split long sweeps into shorter parts. `python .github/scripts/heavy_dispatch.py status` shows the queue. Details: `docs/ci.md`.

## Talking to the owner

The owner is the product owner, not a developer: he decides what he wants and what he accepts, and he comes in cold between chats. Every reply to him:

- is in Russian; the first line answers what he asked or gives the result;
- says in plain words what physically happens: a path, a function name, a commit id becomes what it does;
- asks only what only he knows (what he wants, his taste, the money, time and risk he accepts), each question standing alone: the context, the options with their consequences, your recommendation; the rest you decide and say in one line with its reason;
- names what showed a thing is done: the test, the command, the file;
- writes time in minutes and hours;
- past three lines, ends with a short **TLDR**: what happened and what needs his answer.

He does no step you can do yourself: a command, a commit, a file edit, a merge.
