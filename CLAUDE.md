## Agent skills

### Issue tracker

Issues live in GitHub Issues for `Rasslabsya4el/crafting-system` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## How work is split

One chat does one task, start to end, and starts no other session for it: an idea and its tickets, or one ticket, which it reads, codes, tests, opens as a PR and lands itself. That chat is "the main chat" in this file and in `docs/ci.md`. Its code is never cut into pieces for coder helpers, and no coders run in parallel: the owner wants the cheapest way of working, at the cost of time (#722). What an agent pays for is mostly reading, and a coder helper would read again the code the chat already read to brief it. Two helpers in `.claude/agents/` stay, because each reads much and hands back little, or reads little and saves a larger cost:

- `finder` (Haiku 5.5): wide reading and search; the chat keeps only its facts. It is used instead of the built-in Explore agent, since it answers in a short list of facts with `file:line`.
- `checker` (Sonnet 5.5): one review of a PR against its ticket before it lands.

A helper prompt names its ticket (`#N`) and the files, branch or worktree. A chat does one ticket at a time, within two limits (retro #712):
- At most five tickets with heavy runs at once. A ticket counts from the start of its code (or from its first heavy run, when the need shows late) until it lands; a sixth waits.
- PRs that change the recorded numbers of one route (goldens, fixtures, packed values) share a queue: the later one may build its code, but its heavy runs and re-records start after the earlier one has landed. The main chat names the route when it cuts the ticket.

A root fix that also changes data lands as two PRs: first the mechanism, with tests on hand-worked numbers; then the data (a new snapshot) and its re-records.

The owner's rules are in `docs/owner-rules.md` (`OR-1`, `OR-2`, ...). A ticket that touches targets, routes, prices or pages names the rules from that file it must follow (the main chat writes them into it), the main chat cites them in its PR, and the `checker` reviews every change against the file as well as against its ticket. A PR's open points (findings, placeholders, places that contradict a rule) are not left in its prose: the PR's author files them as issues before asking to land, the `checker` confirms they are filed, and the main chat lands nothing without them.

Model: every chat runs on Opus 5.5 with effort medium, a ticket's chat included (owner, 2026-11-10: one model, no hand-offs); the helpers keep their own models (`finder` Haiku 5.5, `checker` Sonnet 5.5).

Landing a ticket: review comes before the expensive part. Once the code and its quick tests pass, the main chat starts the `checker` on its branch, which reviews that head, and the main chat checks the fix round from its diff (a new mechanism in it goes to the `checker` again). Only then do the heavy runs and golden re-records run; a code change after them runs them again. The main chat opens the PR with `Closes #N`, turns Auto-fix on, and merges the PR itself once the integration run (a `workflow_dispatch` of `ci.yml` on an `integ/...` branch holding `main` plus the PRs) is green on Ubuntu and Windows, the `checker` has passed it, the main chat has checked its re-recorded numbers from the diff, and its tests cover the ticket's "Done when"; a PR's own CI runs Ubuntu only and is feedback while it works, and a chat that needs Windows early dispatches `ci.yml` on its branch; then it runs the tests on `main` and adds the ticket to the map's decisions, and the owner clears the chat (`/clear`). Nobody asks the owner about Auto-fix or merging. A push to `main` starts no CI run: `main` is verified by the integration run, whose tree must equal `main` after landing (`gh workflow run ci.yml --ref main` tests it on demand; `docs/ci.md`). A process-text PR, one whose every changed file is a `.md` file under `CLAUDE.md`, `README.md`, `docs/ci.md`, `docs/agents/`, `.claude/agents/`, `.claude/skills/`, lands with no integration run, since no test reads those files (owner, 2026-11-10); other `.md` files (owner rules, ADRs, research notes, goldens) are read by tests and take the full run. The `checker` still reviews it, and the main chat merges it once that passes; the next integration run tests that `main`. The check and the list: `docs/ci.md`, "Landing a pull request".

One task per chat. The state of the work lives in the GitHub issues, so a `/clear` between tasks loses nothing.

Everything this repo needs lives inside this folder: worktrees in `.claude/worktrees/`, scratch files and run output in `.claude/scratch/`.

The main folder (`C:\Coding\Crafting system` itself) stays on the branch `main`, because every new chat reads this file and `.claude/agents/` from it: a chat never checks out another branch or commit there (it reads one with `git show` or works in a worktree), and after merging a PR it runs `git pull --ff-only` there. From 2026-11-07 to 2026-11-10 it sat on an old commit, and new chats kept the coder helpers this file had already dropped (#722).

## Heavy runs

**Nothing heavy runs on the owner's PC.** Locally only quick, targeted tests (under a minute, one process); the full suite, sweeps, solves and measurements go to GitHub (CI, or a heavy run), because a local multi-process sweep pins his machine at 100%. Heavy runs go **only through the dispatcher**: `python .github/scripts/heavy_dispatch.py run --ref <branch> --runners N --command '...'`, never `gh workflow run run.yml`. The repo has 20 runner jobs at once; the dispatcher waits on the PC until merge CI keeps a buffer (`HEAVY_FLOOR` and `CI_RESERVE`, repository variables), and refuses a timeout over 60 minutes unless `--long` (one indivisible solve): split long sweeps into shorter parts. `python .github/scripts/heavy_dispatch.py status` shows the queue. Details: `docs/ci.md`.

Nobody polls a GitHub run inside a turn. The main chat dispatches with `--no-wait`; on exit 3 (no room now) it runs the command again later in the background. It waits with `python .github/scripts/wait_runs.py <run id>...` in the background, and Auto-fix wakes it on its PR's CI. A helper (`finder`, `checker`) starts no heavy run. A re-record dispatched with `--commit <paths>` commits its own files onto the branch.

## Talking to the owner

The owner is the product owner, not a developer: he decides what he wants and what he accepts, and he comes in cold between chats. Every reply to him:

- is in Russian; the first line answers what he asked or gives the result;
- says in plain words what physically happens: a path, a function name, a commit id becomes what it does;
- asks only what only he knows (what he wants, his taste, the money, time and risk he accepts), each question standing alone: the context, the options with their consequences, your recommendation; the rest you decide and say in one line with its reason;
- names what showed a thing is done: the test, the command, the file;
- writes time in minutes and hours;
- past three lines, ends with a short **TLDR**: what happened and what needs his answer.

He does no step you can do yourself: a command, a commit, a file edit, a merge.
