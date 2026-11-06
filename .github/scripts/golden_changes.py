"""The readable before/after of every golden file a branch changes against `main` (ticket #436, `docs/ci.md`).

    python3 .github/scripts/golden_changes.py [--base origin/main] [--head HEAD] [--out golden-changes.md] [--summary]
                                              [--lines 150] [--dir tests/golden]

It lists the files under `tests/golden/` that differ between the merge base of `--base` and `--head` and the head (added, changed,
deleted), and for each writes the same readable view the failing golden tests print (`tests/golden_diff.py`): HTML as its visible
text and structure, one block per line; JSON pretty-printed with sorted keys; text line by line. `--lines` cuts each file's diff;
the whole report stays under the 1 MiB that GitHub allows a job summary. `--summary` appends the report to `$GITHUB_STEP_SUMMARY`.

Standard library and git only: it imports no game code and needs no game data. It always exits 0 when the report was made
(a golden change is something to read, not a failure); a git error is an error.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

import golden_diff  # noqa: E402  (the one place the readable view is defined, shared with the golden tests)

SUMMARY_LIMIT = 900_000  # bytes; a job summary may hold 1 MiB
STATUS = {"A": "added", "M": "changed", "D": "deleted", "T": "changed"}
FENCE = "````"  # a golden file may hold three backticks


def git(*args: str, root: Path = ROOT) -> bytes:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def merge_base(base: str, head: str, root: Path = ROOT) -> str:
    """The commit the branch left `base` at; `base` itself when the history is too shallow to know (a PR checkout of depth 1)."""
    try:
        return git("merge-base", base, head, root=root).decode().strip()
    except RuntimeError:
        return base


def changed_files(base: str, head: str, directory: str, root: Path = ROOT) -> list[tuple[str, str]]:
    """(status, path) of each file under `directory` that differs between `base` and `head`, in path order."""
    out = git("diff", "--name-status", "--no-renames", base, head, "--", directory, root=root).decode()
    rows = [line.split("\t", 1) for line in out.splitlines() if line.strip()]
    return sorted((STATUS.get(status[0], "changed"), path) for status, path in rows)


def read_at(ref: str, path: str, root: Path = ROOT) -> str:
    return git("show", f"{ref}:{path}", root=root).decode("utf-8", errors="replace").replace("\r\n", "\n")


def section(status: str, path: str, before: str, after: str, lines: int) -> str:
    """The Markdown of one changed file."""
    kind = golden_diff.kind_of(path)
    head = f"### `{path}`: {status}\n\n"
    if status == "added":
        shown = golden_diff.readable_lines(after, kind)
        body = [f"+{line}" for line in shown[:lines]]
        note = f"new file, {len(shown)} readable lines" + (f", the first {lines} shown" if len(shown) > lines else "")
    elif status == "deleted":
        shown = golden_diff.readable_lines(before, kind)
        body = [f"-{line}" for line in shown[:lines]]
        note = f"file removed, {len(shown)} readable lines" + (f", the first {lines} shown" if len(shown) > lines else "")
    else:
        text = golden_diff.readable_diff(before, after, kind, f"main: {path}", f"this branch: {path}", limit=lines)
        body, note = text.splitlines(), ""
    block = f"{FENCE}diff\n" + "\n".join(body) + f"\n{FENCE}\n"
    return head + (f"{note}\n\n" if note else "") + block + "\n"


def report(base: str, head: str, directory: str, lines: int, root: Path = ROOT) -> str:
    """The whole Markdown report for the golden files changed between `base` and `head`."""
    start = merge_base(base, head, root)
    files = changed_files(start, head, directory, root)
    title = "## Golden files changed against main\n\n"
    if not files:
        return title + f"No file under `{directory}` changed.\n"
    out = [title, f"{len(files)} file(s) under `{directory}` changed. Each diff is the readable view: HTML as visible text and structure, one block per line; "
           "JSON pretty-printed with sorted keys; text line by line. `-` is main, `+` is this branch.\n\n"]
    size = sum(len(piece) for piece in out)
    for status, path in files:
        before = "" if status == "added" else read_at(start, path, root)
        after = "" if status == "deleted" else read_at(head, path, root)
        piece = section(status, path, before, after, lines)
        if size + len(piece) > SUMMARY_LIMIT:
            out.append(f"### `{path}`: {status}\n\n(left out: the report would pass the size a job summary may hold; run this script on the branch to read it)\n\n")
            continue
        out.append(piece)
        size += len(piece)
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="origin/main", help="the branch to compare with (default origin/main)")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--dir", default="tests/golden", help="the folder of golden files, relative to the repository root")
    parser.add_argument("--lines", type=int, default=150, help="the most diff lines shown for one file")
    parser.add_argument("--out", help="also write the report to this file")
    parser.add_argument("--summary", action="store_true", help="also append the report to $GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)

    text = report(args.base, args.head, args.dir, args.lines)
    sys.stdout.buffer.write(text.encode("utf-8"))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.summary and summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
