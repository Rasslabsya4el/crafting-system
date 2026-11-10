"""Wait for GitHub Actions runs (ticket #711): one script for any workflow (PR CI, integration run, heavy run).

    python .github/scripts/wait_runs.py 42446621133 42446621134 [--timeout-minutes 90] [--repo owner/name]

A session (the main chat or a ticket's session) starts it in the background and its exit is the notification; a helper
never waits on a run itself, it ends its turn when it hands work to a runner.

Cost to the API limit: the 5,000 calls an hour are one limit for every agent and session. When it starts the script
reads each run's documented `node_id` once (`gh api repos/R/actions/runs/ID --jq .node_id`, one call per run; a 404 means
the id is not a run of the repository and the script exits 2 at once). Then it makes **exactly one call per poll**
whatever the number of runs: a single GraphQL call over those node ids that reads, for every run, its status, its
conclusion and the conclusion of each of its jobs. Polls are at least 240 s apart (`--poll-seconds` below that is
refused). A rate-limit refusal, at start or in a poll, is reported on stderr and retried one poll interval later. A run
found completed is printed once, on one line:

    run 42446621133  claude/711-wait  Run a command  success  jobs: success 3

Exit code: 0 when every run concluded success, 1 when one did not (or GitHub kept failing), 2 for a bad argument
(including a run id GitHub does not know), 3 when `--timeout-minutes` ran out first (the last poll that finds the time
up ends it, so it can overshoot by one poll). The script never reads or prints a token: it calls `gh api`, which holds it.
"""

import argparse
import collections
import datetime as dt
import json
import re
import subprocess
import sys
import time

DEFAULT_REPO = "Rasslabsya4el/crafting-system"
MIN_POLL_SECONDS = 240  # the repository's rate rule: never poll a run more often than every 4 minutes
DEFAULT_TIMEOUT_MINUTES = 360
FAILURES_IN_A_ROW = 5  # failures that are not a rate limit, in a row, before the script gives up
JOBS_READ = 100

QUERY = (
    "query($ids:[ID!]!){nodes(ids:$ids){... on WorkflowRun{databaseId url workflow{name} "
    "checkSuite{status conclusion branch{name} checkRuns(first:%d){totalCount nodes{conclusion}}}}}}" % JOBS_READ
)


def now() -> float:
    """The clock of this script (seconds since the epoch); a seam so the tests run it on a fake clock."""
    return time.time()


def pause(seconds: float) -> None:
    """Every wait of this script goes through here, for the same reason."""
    time.sleep(seconds)


def run_gh(arguments: list[str]) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of `gh <arguments>`; the one place the script touches the network, so the tests
    replace it by a fake gh."""
    try:
        done = subprocess.run(["gh", *arguments], capture_output=True, text=True, encoding="utf-8", timeout=120)
    except FileNotFoundError:
        return 127, "", "gh is not installed or not on the PATH"
    except subprocess.TimeoutExpired:
        return 124, "", "gh timed out after 120 s"
    return done.returncode, done.stdout, done.stderr


def stamp() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


def say(text: str) -> None:
    print(f"{stamp()} {text}", file=sys.stderr, flush=True)


# ---- pure parts -------------------------------------------------------------------------------------------------------


def parse_ids(texts: list[str]) -> list[int]:
    ids = []
    for text in texts:
        if not re.fullmatch(r"[0-9]{1,19}", text):
            raise ValueError(f"'{text}' is not a run id (digits only)")
        if int(text) not in ids:
            ids.append(int(text))
    return ids


def read_run(node: dict) -> dict:
    """What one poll says about a run: id, branch, workflow, whether it is completed, its conclusion, its jobs counted."""
    suite = node.get("checkSuite") or {}
    runs = suite.get("checkRuns") or {}
    jobs = collections.Counter((job.get("conclusion") or "pending").lower() for job in runs.get("nodes") or [])
    return {
        "id": node["databaseId"],
        "branch": ((suite.get("branch") or {}).get("name")) or "?",
        "workflow": (node.get("workflow") or {}).get("name") or "?",
        "done": suite.get("status") == "COMPLETED",
        "conclusion": (suite.get("conclusion") or "unknown").lower(),
        "jobs": dict(jobs),
        "jobs_total": runs.get("totalCount", sum(jobs.values())),
    }


def describe(run: dict) -> str:
    counted = ", ".join(f"{name} {count}" for name, count in sorted(run["jobs"].items(), key=lambda item: (-item[1], item[0])))
    if run["jobs_total"] > sum(run["jobs"].values()):
        counted += f" (first {sum(run['jobs'].values())} of {run['jobs_total']})"
    return f"run {run['id']}  {run['branch']}  {run['workflow']}  {run['conclusion']}  jobs: {counted or 'none'}"


def is_rate_limit(code: int, out: str, err: str) -> bool:
    text = f"{out}\n{err}".lower()
    return "rate limit" in text or "rate_limited" in text or "http 429" in text or ("secondary" in text and "limit" in text)


# ---- the calls --------------------------------------------------------------------------------------------------------


def lookup(repo: str, run_id: int) -> tuple[str, str]:
    """One REST call: ('ok', the run's node id) or ('missing', reason) for a 404 or ('rate', reason) or ('error', reason)."""
    code, out, err = run_gh(["api", f"repos/{repo}/actions/runs/{run_id}", "--jq", ".node_id"])
    if code == 0 and out.strip():
        return "ok", out.strip()
    reason = (err.strip() or out.strip() or f"gh exited {code}")[:300]
    if is_rate_limit(code, out, err):
        return "rate", reason
    said = f"{err} {out}".lower()
    if "404" in said or "not found" in said:
        return "missing", reason
    return "error", reason


def poll(ids: list[str]) -> tuple[str, list[dict] | str]:
    """One call: ('ok', nodes) or ('rate', reason) or ('error', reason)."""
    arguments = ["api", "graphql", "-f", f"query={QUERY}"]
    for node_id in ids:
        arguments += ["-f", f"ids[]={node_id}"]
    code, out, err = run_gh(arguments)
    try:
        answer = json.loads(out) if out.strip() else {}
    except ValueError:
        answer = {}
    errors = answer.get("errors") or []
    if code != 0 or errors and not (answer.get("data") or {}).get("nodes"):
        reason = (err.strip() or json.dumps(errors)[:300] or out.strip()[:300] or f"gh exited {code}")[:300]
        if "could not resolve to a node" in f"{err} {out}".lower():
            return "missing", reason
        return ("rate" if is_rate_limit(code, out, err + json.dumps(errors)) else "error"), reason
    nodes = (answer.get("data") or {}).get("nodes")
    if not isinstance(nodes, list) or len(nodes) != len(ids):
        return "error", f"unexpected answer: {out.strip()[:200]}"
    return "ok", nodes


# ---- the wait ---------------------------------------------------------------------------------------------------------


def resolve(repo: str, run_ids: list[int], deadline: float, poll_seconds: float, timeout_minutes: float) -> list[str] | int:
    """The node id of each run (one REST call each), or the exit code: 2 for a run that is not one of the repository's,
    1 when GitHub keeps failing, 3 on the timeout. A rate-limit refusal waits one poll interval and asks again."""
    node_ids: list[str] = []
    failing = 0
    for run_id in run_ids:
        while True:
            kind, answer = lookup(repo, run_id)
            if kind == "ok":
                node_ids.append(answer)
                failing = 0
                break
            if kind == "missing":
                say(f"wait_runs: run {run_id} is not a run of {repo}: {answer}")
                return 2
            if kind == "rate":
                say(f"wait_runs: GitHub refused the call (rate limit): {answer}; trying again in {poll_seconds:g} s")
            else:
                failing += 1
                say(f"wait_runs: GitHub call failed ({failing} in a row): {answer}")
                if failing >= FAILURES_IN_A_ROW:
                    say("wait_runs: giving up")
                    return 1
            if now() >= deadline:
                say(f"wait_runs: timeout after {timeout_minutes:g} min before the runs could be looked up")
                return 3
            pause(poll_seconds)
    return node_ids


def wait(repo: str, run_ids: list[int], timeout_minutes: float, poll_seconds: float) -> int:
    deadline = now() + timeout_minutes * 60
    node_ids = resolve(repo, run_ids, deadline, poll_seconds, timeout_minutes)
    if isinstance(node_ids, int):
        return node_ids
    finished: dict[int, dict] = {}
    failing = 0
    while True:
        waiting = [(run_id, node_id) for run_id, node_id in zip(run_ids, node_ids) if run_id not in finished]
        kind, answer = poll([node_id for _, node_id in waiting])
        if kind == "missing":
            say(f"wait_runs: GitHub no longer knows one of the runs: {answer}")
            return 2
        if kind == "ok":
            failing = 0
            for (run_id, _), node in zip(waiting, answer):
                if node is None or not node.get("databaseId"):
                    say(f"wait_runs: run {run_id} is not a run of {repo}")
                    return 2
                run = read_run(node)
                if run["done"]:
                    finished[run_id] = run
                    print(describe(run), flush=True)
            if len(finished) == len(run_ids):
                return 0 if all(run["conclusion"] == "success" for run in finished.values()) else 1
        elif kind == "rate":
            say(f"wait_runs: GitHub refused the call (rate limit): {answer}; trying again at the next poll")
        else:
            failing += 1
            say(f"wait_runs: GitHub call failed ({failing} in a row): {answer}")
            if failing >= FAILURES_IN_A_ROW:
                say("wait_runs: giving up")
                return 1
        if now() >= deadline:
            open_runs = ", ".join(str(run_id) for run_id in run_ids if run_id not in finished)
            say(f"wait_runs: timeout after {timeout_minutes:g} min; still open: {open_runs}")
            return 3
        pause(poll_seconds)


def find_repo() -> str:
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return DEFAULT_REPO
    found = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    return found[1] if found else DEFAULT_REPO


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits with 2 already; say it on stderr the way the rest of the script does
        self.print_usage(sys.stderr)
        say(f"wait_runs: {message}")
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_ids", nargs="+", metavar="RUN_ID", help="database id of a workflow run (the number in its URL)")
    parser.add_argument("--timeout-minutes", type=float, default=DEFAULT_TIMEOUT_MINUTES, help="give up (exit 3) after this long")
    parser.add_argument("--poll-seconds", type=float, default=MIN_POLL_SECONDS, help=f"seconds between polls, at least {MIN_POLL_SECONDS}")
    parser.add_argument("--repo", default=None, help=f"owner/name (default: the git remote, else {DEFAULT_REPO})")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse (--help, a malformed option) ends with its own code, 2 for a bad argument
        return int(stop.code or 0)
    try:
        ids = parse_ids(args.run_ids)
    except ValueError as error:
        say(f"wait_runs: {error}")
        return 2
    if args.poll_seconds < MIN_POLL_SECONDS:
        say(f"wait_runs: --poll-seconds must be at least {MIN_POLL_SECONDS} (the rate rule), not {args.poll_seconds:g}")
        return 2
    if args.timeout_minutes <= 0:
        say("wait_runs: --timeout-minutes must be positive")
        return 2
    repo = args.repo or find_repo()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        say(f"wait_runs: '{repo}' is not owner/name")
        return 2
    return wait(repo, ids, args.timeout_minutes, args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
