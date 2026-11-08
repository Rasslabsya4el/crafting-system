"""The merge step of a heavy run that commits (ticket #711): put the files the runners passed on into a checkout.

    python .github/scripts/merge_commit_files.py COLLECTED_DIR CHECKOUT_DIR

COLLECTED_DIR is where the artifacts `commit-1`, `commit-2`, ... were downloaded. The action's own layout is not relied on
(download-artifact puts a single matching artifact straight into the folder and several into one folder each). Instead,
each runner's root is the folder that holds the file `runner-collected.txt`: COLLECTED_DIR itself (one artifact) or a
child of it (several). The runner's name is the root's folder name, or, when the root is COLLECTED_DIR itself, the
content of its marker file. The runner's files sit under its root at their paths from the repository root; a file that
sits under no root is refused. Every file is checked against the rules of `heavy_dispatch.commit_path_problem` (only
under tests/golden/ and tests/fixtures/, no `..`, no symlink), then copied to the same path under CHECKOUT_DIR. Two
runners that wrote the same path with different bytes make the script refuse, with nothing copied. The copied paths are
printed to stdout, one per line, sorted; everything else goes to stderr.
Exit 0 when it merged (even nothing), 1 on a refusal. Standard library only.
"""

import filecmp
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heavy_dispatch import commit_path_problem  # noqa: E402  (the one definition of the allowed paths)

MARKER = "runner-collected.txt"  # not hidden (an artifact leaves hidden files out); every runner's artifact holds it, even when nothing changed


def runner_roots(collected: Path) -> dict[Path, str]:
    """Each folder under (or equal to) `collected` that holds the marker file, with the name of its runner."""
    roots = {}
    for marker in sorted(collected.rglob(MARKER)):
        if marker.is_file() and not marker.is_symlink():
            root = marker.parent
            named = marker.read_text(encoding="utf-8", errors="replace").strip()
            roots[root] = named if root == collected and named else root.name
    return roots


def merge(collected: Path, checkout: Path) -> tuple[list[str], list[str]]:
    """(copied relative paths, refusals). Nothing is copied when there is a refusal."""
    roots = runner_roots(collected)
    chosen: dict[str, tuple[str, Path]] = {}
    refusals: list[str] = []
    for source in sorted(collected.rglob("*")):
        shown = source.relative_to(collected).as_posix()
        if source.is_symlink():
            refusals.append(f"{shown}: a symlink")
            continue
        if not source.is_file():
            continue
        owner = next((parent for parent in source.parents if parent in roots), None)  # the deepest root above it
        if owner is None:
            refusals.append(f"{shown}: under no runner folder (no {MARKER} above it)")
            continue
        relative = source.relative_to(owner).as_posix()
        if relative == MARKER:
            continue
        runner = roots[owner]
        problem = commit_path_problem(relative)
        if problem:
            refusals.append(f"{runner}/{relative}: {problem}")
        elif relative in chosen and not filecmp.cmp(chosen[relative][1], source, shallow=False):
            refusals.append(f"{relative}: runners wrote different content ({chosen[relative][0]} and {runner})")
        else:
            chosen.setdefault(relative, (runner, source))
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
