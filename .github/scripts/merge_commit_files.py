"""The merge step of a heavy run that commits (ticket #711): put the files the runners passed on into a checkout.

    python .github/scripts/merge_commit_files.py COLLECTED_DIR CHECKOUT_DIR

COLLECTED_DIR holds one folder per runner (the downloaded artifacts `commit-1`, `commit-2`, ...), each with the file `runner-collected.txt` and the files that
runner's command changed, at their paths from the repository root. Every file is checked against the rules of
`heavy_dispatch.commit_path_problem` (only under tests/golden/ and tests/fixtures/, no `..`, no symlink), then copied to
the same path under CHECKOUT_DIR. Two runners that wrote the same path with different bytes make the script refuse, with
nothing copied. The copied paths are printed to stdout, one per line, sorted; everything else goes to stderr.
Exit 0 when it merged (even nothing), 1 on a refusal. Standard library only.
"""

import filecmp
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heavy_dispatch import commit_path_problem  # noqa: E402  (the one definition of the allowed paths)

MARKER = "runner-collected.txt"  # (not hidden: an artifact leaves hidden files out) each runner's folder holds it, so the artifact exists even when the command changed nothing


def merge(collected: Path, checkout: Path) -> tuple[list[str], list[str]]:
    """(copied relative paths, refusals). Nothing is copied when there is a refusal."""
    chosen: dict[str, tuple[str, Path]] = {}
    refusals: list[str] = []
    for runner in sorted(item for item in collected.iterdir() if item.is_dir()):
        for source in sorted(runner.rglob("*")):
            if source.is_symlink():
                refusals.append(f"{runner.name}/{source.relative_to(runner).as_posix()}: a symlink")
                continue
            if not source.is_file():
                continue
            relative = source.relative_to(runner).as_posix()
            if relative == MARKER:
                continue
            problem = commit_path_problem(relative)
            if problem:
                refusals.append(f"{runner.name}/{relative}: {problem}")
            elif relative in chosen and not filecmp.cmp(chosen[relative][1], source, shallow=False):
                refusals.append(f"{relative}: runners wrote different content ({chosen[relative][0]} and {runner.name})")
            else:
                chosen.setdefault(relative, (runner.name, source))
    if refusals:
        return [], refusals
    for relative, (_, source) in chosen.items():
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return sorted(chosen), []


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    collected, checkout = Path(argv[0]), Path(argv[1])
    if not collected.is_dir():
        print(f"merge_commit_files: no folder {collected} (no runner passed a file on)", file=sys.stderr)
        return 0
    copied, refusals = merge(collected, checkout)
    for line in refusals:
        print(f"merge_commit_files: refused: {line}", file=sys.stderr)
    for relative in copied:
        print(relative)
    return 1 if refusals else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
