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

Model of the main chat: Opus for ideas, grills and decisions; Sonnet 5.5 for a stretch of plain implementation.

One task per chat. The state of the work lives in the GitHub issues, so a `/clear` between tasks loses nothing.

Everything this repo needs lives inside this folder: worktrees in `.claude/worktrees/`, scratch files and run output in `.claude/scratch/`.

## Talking to the owner

The owner is the product owner, not a developer: he decides what he wants and what he accepts, and he comes in cold between chats. Every reply to him:

- is in Russian; the first line answers what he asked or gives the result;
- says in plain words what physically happens: a path, a function name, a commit id becomes what it does;
- asks only what only he knows (what he wants, his taste, the money, time and risk he accepts), each question standing alone: the context, the options with their consequences, your recommendation; the rest you decide and say in one line with its reason;
- names what showed a thing is done: the test, the command, the file;
- writes time in minutes and hours;
- past three lines, ends with a short **TLDR**: what happened and what needs his answer.

He does no step you can do yourself: a command, a commit, a file edit.
