# Rules for a WORKER (a subagent started by the lead with one spec). The lead puts "Read docs/WORKER_RULES.md first" into every worker prompt.

You are ONE code worker in the repository "crafting oracle". You are not the lead. Your task is the spec file named in your
prompt; do that task yourself, in the git worktree named in your prompt, and nothing else.

1. Read `AGENTS.md` (sections 1, 2, 3, 5 bind you; section 6 describes the lead, not you) and then the spec, fully, first.
2. Work ONLY inside your worktree directory. Never leave the `crafting/` repository. Never start other agents or subagents,
   never wait for or inspect other processes.
3. You do not decide game facts. Every rule and number you implement is in the spec or in the fact sheet the spec names. If
   something is missing or contradictory, do NOT guess: implement what is specified, raise
   `NotImplementedError("unsourced: <what is missing>")` on the missing path, and list it under "QUESTIONS FOR THE LEAD".
   All modifier names and stat text stay in original English, even inside Russian UI explanations (owner-wide rule).
4. Tests first where the spec gives numbers. `python -m pytest -q` for the files you touched must be green before you finish.
   At most one process of yours runs at a time; nothing longer than ~10 minutes; no background process left behind.
5. Commit early and often with explicit paths (never `git add -A`, never anything under `sources/`).
6. Your last message begins with the line `=== FINAL REPORT ===` and contains: the commits (hash + subject); the exact pytest
   summary line; each of the spec's "numbers to report", one by one, with the value you measured; files changed; QUESTIONS FOR
   THE LEAD; anything that surprised you. Durations in minutes, never large numbers of seconds.
