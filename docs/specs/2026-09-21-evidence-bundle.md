# Spec: fresh local test and CoE evidence bundle

Worktree `.worktrees/evidence-bundle`, branch `w-evidence-bundle`. May touch ONLY
tools/collect_evidence.py and tests/test_evidence.py. Bound30minutes. Terra high.
Read docs/design/route-report.md evidence schema. No game-rule or UI decisions.

1. `python -m tools.collect_evidence --output-dir out/evidence` runs in this repository
   synchronously: full pytest with --basetemp=.pytest_tmp and --junitxml=<output>/pytest.xml;
   then python -m tools.coe_validation --output-dir <output>/coe. Zero network. Use subprocess
   timeouts2minutes pytest/3minutes CoE, one process at a time, capture stdout/stderr to files.
   Never inspect or stop other processes. Paths must resolve within this repo/worktree.
2. Write proof.json schema from design, git revision/time/dirty flag and literal commands.
   Parse JUnit XML for every testcase/status, module path, failures/errors/skips/messages.
   Preserve valid failed-run evidence; nonzero command exit must not produce a green badge.
   CoE rows copied from its existing comparison JSON, max abs relative difference derived.
   Missing/timeout/unparseable results marked unavailable/failed with concrete reason.
   Return nonzero if a requested check failed, but always save the completed evidence.
3. Expose small pure parsers/builders for tests. Test synthetic JUnit:4 cases,2 passed,
   1 failure,1 skipped; error case separately; never count nested testsuite attributes twice.
   CoE fixture differences-.02/.03 givesmax .03,case_count2. Missing/invalid/stale output
   handling and a timed-out command must not reuse a prior successful artifact.
4. Collector must not read accepted outputs from another worktree. No full live command
   runs in your worker (ignored raw sources absent); test orchestration using fake commands/
   mocked subprocess and literal tiny artifacts, checking exit statuses and logs.

Report focused pytest summary, schema fields and fixture counts, commit/files; final report
starts `=== FINAL REPORT ===`. Lead runs the real bundle after all report code is merged.
