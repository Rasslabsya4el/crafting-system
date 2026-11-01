"""The one door for heavy runs (ticket #249): start `run.yml` only while merge CI keeps a buffer of runners.

    python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 4 --command 'uv run --no-sync python bench.py --part $RUNNER_INDEX/$RUNNER_COUNT --out $OUT_DIR'
    python .github/scripts/heavy_dispatch.py status

GitHub gives the repository 20 runner jobs at once. CI (`ci.yml`) takes 8 (Ubuntu) for about 7 minutes per pull request
push and 16 (Ubuntu and Windows) per dispatched run, the integration run; heavy runs (`run.yml`) take 1 to 16 for up to hours. This script waits on the developer's PC (no runner is used
while it waits), reads the live job counts of both workflows and dispatches only while

    heavy_in_flight + requested <= HEAVY_BUDGET,   HEAVY_BUDGET = max(HEAVY_FLOOR, 20 - CI_RESERVE - ci_jobs)

`HEAVY_FLOOR` (default 4) and `CI_RESERVE` (default 4) are GitHub Actions repository variables, so they can be turned
without a commit; `ci_jobs` is the CI jobs queued or running now. `--runners` is a maximum: with `--min-runners` below
it the run starts smaller when only that many fit (the command must then split its work by RUNNER_INDEX/RUNNER_COUNT
and still finish inside `--timeout-minutes`). Heavy jobs are kept short so runners free up: `--timeout-minutes` above
60 needs `--long`, which is for a single indivisible solve (one runner); split a long sweep into more, shorter parts.

`status` prints the budget, the runner jobs in use by kind, the queue with waiting times, and the runs that are older
than their own timeout or silent for 30 minutes (candidates to cancel).

The token comes from GH_TOKEN / GITHUB_TOKEN, else `gh auth token`, else `git credential fill`. Standard library only.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPO = "Rasslabsya4el/crafting-system"
TOTAL_RUNNERS = 20  # concurrent jobs the free plan gives the repository
CI_JOBS_PER_RUN = 16  # a dispatched CI run: 2 systems x 8 shards; counted for a CI run whose jobs are not created yet
CI_JOBS_PER_PR_RUN = 8  # a pull_request CI run is Ubuntu only (ticket #321)
DEFAULT_FLOOR = 4
DEFAULT_RESERVE = 4
MAX_RUNNERS = 16  # run.yml's own limit
SHORT_MINUTES = 60  # longest timeout without --long
LONG_MINUTES = 360
CI_TIMEOUT_MINUTES = 45  # a CI job times out at 30 minutes; a run older than this is stuck
SILENT_MINUTES = 30
ACTIVE = ("queued", "in_progress")  # job statuses that hold or wait for a runner
PENDING_RUN = ("pending", "waiting", "requested")  # run statuses before any job exists, e.g. held by a concurrency group
POLL_SECONDS = 60
STATE_DIR = Path(tempfile.gettempdir()) / "crafting-heavy-dispatch"  # shared by every session on this PC
LOCK_STALE_SECONDS = 300
LEDGER_HOURS = 7

LOG_STAMP = r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}[:][0-9]{2}[:][0-9]{2})"  # [:] keeps the drive-letter scan quiet
RUN_NAME = re.compile(r"^heavy (\d+)x (\S+) t(\d+)")


# ---- pure decisions (tested on recorded API responses) -------------------------------------------------------------


def heavy_budget(floor: int, reserve: int, ci_jobs: int, total: int = TOTAL_RUNNERS) -> int:
    """Runners heavy runs may hold at once: what CI and its reserve leave, but never below the floor."""
    return max(floor, total - reserve - ci_jobs)


def runners_to_start(heavy_in_flight: int, requested: int, minimum: int, budget: int) -> int:
    """How many runners to dispatch now: all `requested` if they fit, else as many as fit when that is at least
    `minimum`, else 0 (wait)."""
    room = budget - heavy_in_flight
    if room >= requested:
        return requested
    if room >= minimum:
        return room
    return 0


def parse_run_name(title: str) -> tuple[int, str, int] | None:
    """(runners, os, timeout minutes) from the run name `heavy 4x ubuntu-latest t60 ...` that run.yml sets."""
    found = RUN_NAME.match(title or "")
    return (int(found[1]), found[2], int(found[3])) if found else None


def parse_time(stamp: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None


def run_occupancy(run: dict, jobs: list[dict], ledger_runners: int = 0) -> dict:
    """Runner jobs one run holds: running, queued, and the total counted against the budget.

    A run whose matrix is not created yet (the `plan` job still queued or running) counts as the runners it asked for,
    read from its name or from the dispatcher's ledger, so a fresh heavy run is never invisible."""
    running = sum(1 for job in jobs if job["status"] == "in_progress")
    queued = sum(1 for job in jobs if job["status"] == "queued")
    is_ci = run["path"].endswith("ci.yml")
    matrix_made = any(job["name"].startswith(("tests (", "run (")) for job in jobs)
    expected = 0
    if not matrix_made:
        if is_ci:
            expected = CI_JOBS_PER_PR_RUN if run.get("event") == "pull_request" else CI_JOBS_PER_RUN
        else:
            named = parse_run_name(run.get("display_title", ""))
            expected = named[0] if named else ledger_runners
    return {"running": running, "queued": queued, "counted": max(running + queued, expected)}


def totals(occupancies: list[tuple[dict, dict]]) -> tuple[int, int]:
    """(ci jobs, heavy jobs) counted against the budget, from (run, occupancy) pairs."""
    ci = sum(occ["counted"] for run, occ in occupancies if run["path"].endswith("ci.yml"))
    heavy = sum(occ["counted"] for run, occ in occupancies if run["path"].endswith("run.yml"))
    return ci, heavy


def stale_reason(run: dict, jobs: list[dict], now: dt.datetime, last_output: dt.datetime | None) -> str | None:
    """Why a run is a candidate to cancel (older than its own timeout, or silent for 30 minutes), else None."""
    is_ci = run["path"].endswith("ci.yml")
    named = parse_run_name(run.get("display_title", ""))
    limit = CI_TIMEOUT_MINUTES if is_ci else (named[2] if named else LONG_MINUTES)
    started = parse_time(run.get("run_started_at") or run["created_at"])
    # a heavy run may wait in the queue; only time since its first job began counts
    began = [parse_time(job.get("started_at")) for job in jobs if job.get("started_at")]
    if not is_ci and began:
        started = min(began)
    elif not is_ci:
        started = None
    if started is not None:
        age = (now - started).total_seconds() / 60
        if age > limit + 5:
            return f"running {age:.0f} min, its timeout is {limit} min"
    if last_output is not None and any(job["status"] == "in_progress" for job in jobs):
        silent = (now - last_output).total_seconds() / 60
        if silent > SILENT_MINUTES:
            return f"no log output for {silent:.0f} min"
    return None


# ---- GitHub API ----------------------------------------------------------------------------------------------------


def find_token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    attempts = (
        (["gh", "auth", "token"], None, lambda out: out.strip()),
        (["git", "credential", "fill"], "protocol=https\nhost=github.com\n\n", lambda out: next((line[9:] for line in out.splitlines() if line.startswith("password=")), "")),
    )
    for command, stdin, parse in attempts:
        if shutil.which(command[0]) is None:
            continue
        try:
            done = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        token = parse(done.stdout)
        if done.returncode == 0 and token:
            return token
    sys.exit("heavy_dispatch: no GitHub token (set GH_TOKEN, or log in with `gh auth login`)")


def find_repo() -> str:
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return DEFAULT_REPO
    found = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    return found[1] if found else DEFAULT_REPO


class Api:
    def __init__(self, repo: str, token: str):
        self.base = f"https://api.github.com/repos/{repo}"
        self.token = token

    def call(self, path: str, method: str = "GET", body: dict | None = None, tries: int = 4):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        for attempt in range(1, tries + 1):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as error:
                if error.code == 404 and method == "GET":
                    return None
                if error.code < 500 and error.code != 429 or attempt == tries:
                    raise RuntimeError(f"{method} {path}: HTTP {error.code} {error.read()[:300]!r}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == tries:
                    raise
            time.sleep(3 * attempt)

    def variable(self, name: str, default: int) -> int:
        found = self.call(f"/actions/variables/{name}")
        try:
            return int(found["value"]) if found else default
        except (KeyError, ValueError):
            return default

    def active_runs(self) -> list[dict]:
        runs = []
        for workflow in ("ci.yml", "run.yml"):
            for status in (*ACTIVE, *PENDING_RUN):
                page = self.call(f"/actions/workflows/{workflow}/runs?status={status}&per_page=100")
                runs.extend(page["workflow_runs"] if page else [])
        unique = {run["id"]: run for run in runs}
        return list(unique.values())

    def jobs(self, run_id: int) -> list[dict]:
        page = self.call(f"/actions/runs/{run_id}/jobs?per_page=100&filter=latest")
        return page["jobs"] if page else []

    def last_output(self, job_id: int) -> dt.datetime | None:
        """Time of the newest log line of a running job, if GitHub serves the log of a running job. The log lives
        behind a redirect to another host, which must not get the token."""

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        try:
            request = urllib.request.Request(f"{self.base}/actions/jobs/{job_id}/logs")
            request.add_header("Authorization", f"Bearer {self.token}")
            try:
                with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
                    text = response.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as error:
                if error.code not in (301, 302, 303, 307, 308) or not error.headers.get("Location"):
                    return None
                with urllib.request.urlopen(error.headers["Location"], timeout=60) as response:
                    text = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None
        stamps = re.findall(LOG_STAMP, text, re.MULTILINE)
        return parse_time(stamps[-1] + "Z") if stamps else None


def snapshot(api: Api, ledger: dict[str, int]) -> list[tuple[dict, list[dict], dict]]:
    """(run, jobs, occupancy) of every queued or running run of ci.yml and run.yml."""
    seen = []
    for run in api.active_runs():
        jobs = api.jobs(run["id"])
        seen.append((run, jobs, run_occupancy(run, jobs, ledger.get(str(run["id"]), 0))))
    return seen


# ---- state shared by the sessions on this PC -----------------------------------------------------------------------


def read_ledger() -> dict[str, int]:
    """Runners of the runs this script dispatched, for the minutes before their matrix jobs exist."""
    try:
        entries = json.loads((STATE_DIR / "ledger.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    cutoff = time.time() - LEDGER_HOURS * 3600
    return {run_id: item["runners"] for run_id, item in entries.items() if item["at"] > cutoff}


def write_ledger(run_id: int, runners: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = STATE_DIR / "ledger.json"
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = {}
        entries[str(run_id)] = {"runners": runners, "at": time.time()}
        path.write_text(json.dumps(entries), encoding="utf-8")
    except OSError:
        pass  # the ledger only covers a few minutes; the run name covers the same ground


class DispatchLock:
    """Two sessions on this PC must not both see free runners and both dispatch: one holds this lock from the
    decision until its run shows up in the API. The lock is a directory in the PC's temp folder; it belongs to the
    process that made it (a token file inside) and is taken over only when older than LOCK_STALE_SECONDS."""

    def __init__(self):
        self.path = STATE_DIR / "dispatch.lock"
        self.token = f"{os.getpid()}-{time.time_ns()}"

    def __enter__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                os.mkdir(self.path)
                (self.path / "owner").write_text(self.token, encoding="utf-8")
                return self
            except OSError:  # FileExistsError, or PermissionError while another process removes it (Windows)
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_SECONDS:
                        shutil.rmtree(self.path, ignore_errors=True)
                        continue
                except OSError:
                    pass
                time.sleep(2)

    def __exit__(self, *exc):
        try:
            if (self.path / "owner").read_text(encoding="utf-8") == self.token:
                shutil.rmtree(self.path, ignore_errors=True)
        except OSError:
            pass


# ---- commands ------------------------------------------------------------------------------------------------------


def stamp() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


def check_args(args) -> None:
    if not 1 <= args.runners <= MAX_RUNNERS:
        sys.exit(f"--runners must be 1 to {MAX_RUNNERS}, not {args.runners}")
    if args.min_runners is None:
        args.min_runners = args.runners
    if not 1 <= args.min_runners <= args.runners:
        sys.exit(f"--min-runners must be 1 to --runners ({args.runners}), not {args.min_runners}")
    if not 1 <= args.timeout_minutes <= LONG_MINUTES:
        sys.exit(f"--timeout-minutes must be 1 to {LONG_MINUTES}, not {args.timeout_minutes}")
    if args.timeout_minutes > SHORT_MINUTES:
        if not args.long:
            sys.exit(
                f"--timeout-minutes {args.timeout_minutes} is over {SHORT_MINUTES}: long jobs hold a runner for hours. "
                f"Split the sweep into more, shorter parts (--runners, RUNNER_INDEX/RUNNER_COUNT); --long is only for a "
                f"single indivisible solve on one runner."
            )
        if args.runners != 1:
            sys.exit("--long is for a single indivisible solve: it needs --runners 1")


def cmd_run(api: Api, args) -> int:
    check_args(args)
    floor = api.variable("HEAVY_FLOOR", DEFAULT_FLOOR)
    reserve = api.variable("CI_RESERVE", DEFAULT_RESERVE)
    if args.min_runners > TOTAL_RUNNERS - reserve and args.min_runners > floor:
        sys.exit(
            f"{args.min_runners} runners can never fit: the most heavy runs ever get is "
            f"{max(floor, TOTAL_RUNNERS - reserve)} (CI_RESERVE={reserve}, HEAVY_FLOOR={floor}). Ask for fewer."
        )
    deadline = time.time() + args.max_wait * 60 if args.max_wait else None
    while True:
        try:
            with DispatchLock():
                decided = decide(api, args)
                if decided["count"] and not args.dry_run:
                    print(f"{stamp()} {decided['line']} -> starting {decided['count']} runner(s)", flush=True)
                    return dispatch(api, args, decided["count"])
        except (RuntimeError, urllib.error.URLError, TimeoutError, OSError) as error:
            decided = {"count": 0, "line": f"GitHub API error ({str(error)[:120]}), will retry"}
        if decided["count"]:
            print(f"{stamp()} {decided['line']} -> would start {decided['count']} runner(s); dry run: nothing dispatched")
            return 0
        line = decided["line"]
        if deadline and time.time() > deadline:
            print(f"{stamp()} {line} -> gave up after {args.max_wait} min of waiting", flush=True)
            return 2
        if args.no_wait:
            print(f"{stamp()} {line} -> does not fit now", flush=True)
            return 3
        print(f"{stamp()} {line} -> waiting", flush=True)
        time.sleep(POLL_SECONDS)


def decide(api: Api, args) -> dict:
    """One look at the live counts: how many runners to start now (0 = wait) and the status line."""
    floor = api.variable("HEAVY_FLOOR", DEFAULT_FLOOR)
    reserve = api.variable("CI_RESERVE", DEFAULT_RESERVE)
    seen = snapshot(api, read_ledger())
    ci_jobs, heavy = totals([(run, occ) for run, _, occ in seen])
    budget = heavy_budget(floor, reserve, ci_jobs)
    count = runners_to_start(heavy, args.runners, args.min_runners, budget)
    line = (
        f"CI jobs {ci_jobs}, heavy in flight {heavy}, budget {budget} "
        f"(HEAVY_FLOOR={floor}, CI_RESERVE={reserve}), wanted {args.runners}"
        + (f" (at least {args.min_runners})" if args.min_runners != args.runners else "")
    )
    return {"count": count, "line": line}


def dispatch(api: Api, args, count: int) -> int:
    before = {run["id"] for run in find_runs(api, args.ref)}
    started = dt.datetime.now(dt.timezone.utc)
    inputs = {
        "command": args.command,
        "runners": str(count),
        "os": args.os,
        "timeout_minutes": str(args.timeout_minutes),
    }
    api.call("/actions/workflows/run.yml/dispatches", "POST", {"ref": args.ref, "inputs": inputs})
    # From here the run exists: never raise, or the caller would dispatch it a second time.
    for _ in range(30):  # the run shows up within seconds; holding the lock until then keeps the next session honest
        time.sleep(4)
        try:
            fresh = [run for run in find_runs(api, args.ref) if run["id"] not in before]
        except (RuntimeError, urllib.error.URLError, TimeoutError, OSError):
            continue
        fresh = [run for run in fresh if parse_time(run["created_at"]) >= started - dt.timedelta(seconds=30)]
        if fresh:
            run = max(fresh, key=lambda item: item["id"])
            write_ledger(run["id"], count)
            print(f"dispatched run {run['id']} on {args.ref} with {count} runner(s): {run['html_url']}")
            return 0
    print("dispatched, but the run did not show up in 2 minutes; check `heavy_dispatch.py status`")
    return 0


def find_runs(api: Api, branch: str) -> list[dict]:
    page = api.call(f"/actions/workflows/run.yml/runs?event=workflow_dispatch&per_page=30&branch={urllib.request.quote(branch)}")
    return page["workflow_runs"] if page else []


def minutes_since(stamp_text: str | None, now: dt.datetime) -> float:
    moment = parse_time(stamp_text)
    return (now - moment).total_seconds() / 60 if moment else 0.0


def cmd_status(api: Api, args) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    floor = api.variable("HEAVY_FLOOR", DEFAULT_FLOOR)
    reserve = api.variable("CI_RESERVE", DEFAULT_RESERVE)
    seen = snapshot(api, read_ledger())
    ci_jobs, heavy = totals([(run, occ) for run, _, occ in seen])
    budget = heavy_budget(floor, reserve, ci_jobs)
    in_use = sum(occ["running"] for _, _, occ in seen)
    print(f"Runner jobs: {in_use} running of {TOTAL_RUNNERS}; CI {ci_jobs} (running or queued), heavy {heavy}")
    print(f"Heavy budget {budget} = max(HEAVY_FLOOR={floor}, {TOTAL_RUNNERS} - CI_RESERVE={reserve} - CI jobs {ci_jobs}); room for {max(0, budget - heavy)} more")
    print("\nIn use / queued, by kind:")
    if not seen:
        print("  nothing running or queued")
    for run, jobs, occ in sorted(seen, key=lambda item: (item[0]["path"], item[0]["id"])):
        is_ci = run["path"].endswith("ci.yml")
        kind = "CI   " if is_ci else "heavy"
        what = f"PR {run['pull_requests'][0]['number']} " if is_ci and run.get("pull_requests") else ""
        label = f"{what}{run['head_branch']}"
        if not is_ci:
            named = parse_run_name(run.get("display_title", ""))
            if named:
                label += f" ({named[0]} runners, {named[1]}, timeout {named[2]} min)"
        waited = f"; oldest queued job waited {max((minutes_since(job['created_at'], now) for job in jobs if job['status'] == 'queued'), default=0):.0f} min" if occ["queued"] else ""
        print(f"  {kind} {label}: {occ['running']} running, {occ['queued']} queued, {occ['counted']} counted, run {run['id']}{waited}")
    queued_runs = [(run, occ) for run, _, occ in seen if occ["queued"] or (occ["counted"] and not occ["running"])]
    print("\nQueue (waiting for a runner):")
    if not queued_runs:
        print("  empty")
    for run, occ in sorted(queued_runs, key=lambda item: item[0]["created_at"]):
        print(f"  {run['path'].split('/')[-1]} {run['head_branch']}: {occ['queued'] or occ['counted']} job(s), run created {minutes_since(run['created_at'], now):.0f} min ago")
    print("\nCandidates to cancel (older than their timeout, or silent for 30 minutes):")
    flagged = 0
    for run, jobs, _ in seen:
        running = [job for job in jobs if job["status"] == "in_progress"]
        output = api.last_output(running[0]["id"]) if running and not args.no_logs else None
        reason = stale_reason(run, jobs, now, output)
        if reason:
            flagged += 1
            print(f"  run {run['id']} ({run['path'].split('/')[-1]}, {run['head_branch']}): {reason}  ->  gh run cancel {run['id']}")
    if not flagged:
        print("  none")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run", help="wait for room, then dispatch run.yml")
    run.add_argument("--ref", required=True, help="branch whose code runs")
    run.add_argument("--command", required=True, help="bash command (see docs/ci.md); write results into $OUT_DIR")
    run.add_argument("--runners", type=int, default=1, help="most runners to use, 1 to 16")
    run.add_argument("--min-runners", type=int, help="start smaller than --runners when only this many fit (default: --runners, never smaller)")
    run.add_argument("--os", default="ubuntu-latest", choices=["ubuntu-latest", "windows-latest"])
    run.add_argument("--timeout-minutes", type=int, default=SHORT_MINUTES, help="over 60 needs --long")
    run.add_argument("--long", action="store_true", help="allow a timeout over 60 minutes: one runner, one indivisible solve")
    run.add_argument("--max-wait", type=int, default=0, help="give up after this many minutes of waiting (default: wait for ever)")
    run.add_argument("--no-wait", action="store_true", help="exit with 3 instead of waiting when it does not fit now")
    run.add_argument("--dry-run", action="store_true", help="decide and print, dispatch nothing")
    status = commands.add_parser("status", help="show the runner queue")
    status.add_argument("--no-logs", action="store_true", help="skip the log check for silent runs")
    for sub in (run, status):
        sub.add_argument("--repo", default=None, help=f"owner/name (default: the git remote, else {DEFAULT_REPO})")
    args = parser.parse_args(argv)
    api = Api(args.repo or find_repo(), find_token())
    return cmd_run(api, args) if args.action == "run" else cmd_status(api, args)


if __name__ == "__main__":
    sys.exit(main())
