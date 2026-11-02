"""Run a slice of the mutation plan (ticket #399, step 5): one job of one round.

The plan (`mutation_plan.py`) numbers the mutants in priority order. A job takes the mutants that no earlier round
has recorded, in plan order, and keeps every `--jobs`-th of them starting at its own number (so the 16 jobs of a
round share the next mutants evenly and each works through its share in priority order). Whatever a job did not
reach before its stop time is simply still pending for the next round: nothing needs sizing in advance.

A job stops starting mutants at `min(deadline, start + minutes)`; a mutant that has started runs to its own time
limit, which is `max(60 s, 3 x the clean run of the same tests)` (a ceiling of `--max-limit` seconds). The clean run of a
test set is measured once per job and cached; a set whose clean run fails or takes over `--max-clean` seconds is
not used: its mutants end as `skipped`.

One mutant: the original text of the file is kept in memory, the mutated text is written over the file in the
checkout (the runner is thrown away after the job, and nothing is committed), the selected tests run with
`pytest -x -q -p no:cacheprovider`, and the original text is written back in a `finally` (SIGTERM from a cancelled
job is turned into an exception so that it runs too). The cached bytecode of the file is deleted before and after
every run, and the file gets a fresh modification time, so a run never imports the previous mutant's code.

Outcomes: killed (pytest exit 1: a test failed), survived (exit 0), timeout (over the limit), error (the tests did
not run: the mutated module does not import, a collection error, a usage error), skipped (see above).
"""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mutation_ops import Mutant, apply_mutant  # noqa: E402

MIN_LIMIT = 60.0
LIMIT_FACTOR = 3.0
PYTEST_ARGS = ["-x", "-q", "-p", "no:cacheprovider"]


@dataclass
class RunResult:
    code: int | None  # pytest's exit code; None when it timed out
    seconds: float
    tail: str = ""


Runner = Callable[[list[str], float], RunResult]


def load_done(folder: Path | None, before_round: int | None = None) -> set[int]:
    """The mutant numbers recorded by rounds before `before_round` (all rounds when None), from `*.jsonl` under `folder`.

    A job of the same round that started late must not see the results of a job that finished early, or the
    stripes of the round would no longer line up.
    """
    done: set[int] = set()
    if folder is None or not folder.exists():
        return done
    for path in sorted(folder.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if before_round is None or record.get("round", 0) < before_round:
                    done.add(int(record["id"]))
    return done


def slice_of(mutants: list[dict], done: set[int], job: int, jobs: int) -> list[dict]:
    """Job `job` (from 1) of `jobs`: every `jobs`-th pending mutant, in plan order."""
    pending = [mutant for mutant in mutants if mutant["id"] not in done]
    return pending[job - 1 :: jobs]


def make_runner(root: Path) -> Runner:
    """Run pytest on node ids in a child process of the repo, killing the whole process group after `timeout`."""

    def run(node_ids: list[str], timeout: float) -> RunResult:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write("\n".join(node_ids))
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, "-m", "pytest", *PYTEST_ARGS, f"@{handle.name}"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
            start_new_session=os.name == "posix",
        )  # fmt: skip
        try:
            output, _ = process.communicate(timeout=timeout)
            return RunResult(process.returncode, time.monotonic() - started, output[-600:])
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.communicate()
            return RunResult(None, time.monotonic() - started)
        finally:
            Path(handle.name).unlink(missing_ok=True)

    return run


def outcome_of(result: RunResult) -> str:
    if result.code is None:
        return "timeout"
    return {0: "survived", 1: "killed"}.get(result.code, "error")


class Mutated:
    """Context manager: the file holds the mutated text inside, the original text after, whatever happens."""

    clock = 0

    def __init__(self, path: Path, original: str, mutated: str):
        self.path, self.original, self.mutated = path, original, mutated

    def _drop_bytecode(self) -> None:
        cache = self.path.parent / "__pycache__"
        if cache.is_dir():
            for pyc in cache.glob(f"{self.path.stem}.*.pyc"):
                pyc.unlink(missing_ok=True)

    def __enter__(self):
        self._drop_bytecode()
        self.path.write_text(self.mutated, encoding="utf-8", newline="\n")
        Mutated.clock += 2
        stamp = time.time() + Mutated.clock  # a modification time no earlier bytecode can have
        os.utime(self.path, (stamp, stamp))
        return self

    def __exit__(self, *exc):
        self.path.write_text(self.original, encoding="utf-8", newline="\n")
        self._drop_bytecode()
        return False


def _raise_on_term(signum, frame):
    raise SystemExit(128 + signum)


def process_slice(
    plan: dict,
    mine: list[dict],
    root: Path,
    runner: Runner,
    out_file: Path,
    stop_at: float,
    round_number: int,
    job: int,
    max_clean: float,
    max_limit: float,
    now: Callable[[], float] = time.time,
) -> dict:
    """Run `mine` in order until `stop_at` (epoch seconds); one JSON line per mutant goes to `out_file`."""
    sources: dict[str, str] = {}
    clean: dict[str, tuple[float | None, str]] = {}  # set -> (clean seconds, "" or the reason it is unusable)
    done = 0
    reached = 0
    for mutant in mine:
        if now() >= stop_at:
            break
        reached += 1
        file = mutant["file"]
        if file not in sources:
            sources[file] = (root / file).read_text(encoding="utf-8").replace("\r\n", "\n")
        tests = plan["sets"][mutant["set"]]["tests"]
        if mutant["set"] not in clean:
            first = runner(tests, max_clean)
            if first.code == 0:
                clean[mutant["set"]] = (first.seconds, "")
            else:
                why = "the clean run took too long" if first.code is None else f"the clean run failed (exit {first.code})"
                clean[mutant["set"]] = (None, why)
        clean_seconds, why = clean[mutant["set"]]
        record = {
            "id": mutant["id"], "file": file, "line": mutant["line"], "operator": mutant["operator"],
            "original": mutant["original"], "mutated": mutant["mutated"][:400], "tier": mutant["tier"],
            "set": mutant["set"], "tests": len(tests), "source": plan["sets"][mutant["set"]]["source"],
            "cut": plan["sets"][mutant["set"]]["cut"], "round": round_number, "job": job,
        }  # fmt: skip
        if clean_seconds is None:
            record |= {"outcome": "skipped", "seconds": 0.0, "detail": why}
        else:
            fields = {key: mutant[key] for key in Mutant.__dataclass_fields__}  # the plan's fields are the Mutant's
            changed = apply_mutant(sources[file], Mutant(**fields))
            limit = min(max(MIN_LIMIT, LIMIT_FACTOR * clean_seconds), max_limit)
            with Mutated(root / file, sources[file], changed):
                result = runner(tests, limit)
            record |= {"outcome": outcome_of(result), "seconds": round(result.seconds, 2), "detail": ""}
            if record["outcome"] == "error":
                record["detail"] = result.tail[-300:]
        with out_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        done += 1
    return {"taken": len(mine), "done": done, "not_reached": [m["id"] for m in mine[reached:]]}


def stop_time(started: float, minutes: float, deadline: str, trial: bool) -> float:
    """Epoch seconds after which no mutant starts: the job's own minutes, or the deadline when that is earlier."""
    stop = started + minutes * 60
    if deadline and not trial:
        stop = min(stop, datetime.fromisoformat(deadline.replace("Z", "+00:00")).timestamp())
    return stop


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--done", type=Path, help="folder holding the results of the earlier rounds")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--round", type=int, required=True, dest="round_number")
    parser.add_argument("--job", type=int, required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--minutes", type=float, default=320)
    parser.add_argument("--deadline", default="")
    parser.add_argument("--trial", action="store_true")
    parser.add_argument("--max-clean", type=float, default=200)
    parser.add_argument("--max-limit", type=float, default=600)
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _raise_on_term)
    root = args.repo.resolve()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    for file, expected in plan["hashes"].items():  # a leftover mutant or another commit would make every result wrong
        text = (root / file).read_text(encoding="utf-8").replace("\r\n", "\n")
        if hashlib.sha1(text.encode()).hexdigest() != expected:
            print(f"{file} differs from the plan: refusing to run", file=sys.stderr)
            return 2

    mine = slice_of(plan["mutants"], load_done(args.done, args.round_number), args.job, args.jobs)
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    stop_at = stop_time(started, args.minutes, args.deadline, args.trial)
    out_file = args.out / "results.jsonl"
    out_file.touch()
    print(f"round {args.round_number} job {args.job}/{args.jobs}: {len(mine)} mutants in the slice, stop in {(stop_at - started) / 60:.0f} min")
    status = process_slice(
        plan, mine, root, make_runner(root), out_file, stop_at, args.round_number, args.job, args.max_clean, args.max_limit
    )
    status |= {"round": args.round_number, "job": args.job, "seconds": round(time.time() - started)}
    (args.out / "status.json").write_text(json.dumps(status), encoding="utf-8")
    print(f"done {status['done']} of {status['taken']}; {len(status['not_reached'])} not reached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
