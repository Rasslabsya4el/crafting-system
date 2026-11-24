"""Fetch the pinned PoE2 game-data export (repoe-fork/poe2) and the official trade site's static lists.

A research tool for the later PoE2 port; it is NOT part of the PoE1 package and no PoE1 code or
test imports it. It mirrors what `crafting_system.data fetch` does for PoE1 (ADR-0003): every
file is named in `PIN.json` next to this script with its size and sha256, downloaded into a cache
folder, and trusted only when both match.

    python -I research/poe2/data/fetch_poe2.py fetch          # download what is missing, check all
    python -I research/poe2/data/fetch_poe2.py verify         # check the cache only, no network
    python -I research/poe2/data/fetch_poe2.py pin <commit>   # re-pin: hash the files of a new export

The cache folder is `$CRAFTING_CACHE_DIR/repoe-fork-poe2/<version>/` (the PoE1 cache keeps its own
`repoe-fork/<version>/`, so the two never share a file). Without the variable it is
`.claude/scratch/crafting-cache` under the repository root. Standard library only.
"""

import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "PIN.json"
REPO_ROOT = HERE.parents[2]
USER_AGENT = "crafting-system-research"
TIMEOUT_SECONDS = 120
CHUNK = 1024 * 1024
RAW_BASE = "https://raw.githubusercontent.com/repoe-fork/poe2"


def cache_root() -> Path:
    configured = os.environ.get("CRAFTING_CACHE_DIR")
    base = Path(configured) if configured else REPO_ROOT / ".claude" / "scratch" / "crafting-cache"
    return base / "repoe-fork-poe2"


def load_pin() -> dict:
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))


def file_url(pin: dict, entry: dict) -> str:
    if "url" in entry:
        return entry["url"]
    return f"{RAW_BASE}/{pin['commit']}/data/{entry['path']}"


def local_path(pin: dict, entry: dict) -> Path:
    return cache_root() / pin["version"] / entry["path"]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path) -> tuple[str, int]:
    """Stream `url` into a temporary file beside `target`; return (sha256, size) and move it into place."""
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest, size = hashlib.sha256(), 0
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".part-")
    try:
        with os.fdopen(handle, "wb") as out, urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            for block in iter(lambda: response.read(CHUNK), b""):
                digest.update(block)
                size += len(block)
                out.write(block)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return digest.hexdigest(), size


def check(entry: dict, path: Path) -> str | None:
    if not path.is_file():
        return "missing"
    if path.stat().st_size != entry["size"]:
        return f"size {path.stat().st_size} != pinned {entry['size']}"
    if sha256_of(path) != entry["sha256"]:
        return "sha256 differs from the pin"
    return None


def fetch() -> int:
    pin, failures = load_pin(), 0
    for entry in pin["files"]:
        path = local_path(pin, entry)
        if check(entry, path) is None:
            print(f"cached      {entry['path']}")
            continue
        download(file_url(pin, entry), path)
        problem = check(entry, path)
        if problem:
            failures += 1
            path.unlink(missing_ok=True)
            print(f"MISMATCH    {entry['path']}: {problem} (the live file changed: re-pin on purpose)")
        else:
            print(f"downloaded  {entry['path']}")
    return 1 if failures else 0


def verify() -> int:
    pin, failures = load_pin(), 0
    for entry in pin["files"]:
        problem = check(entry, local_path(pin, entry))
        print(f"{'ok' if problem is None else 'BAD':<11} {entry['path']}{'' if problem is None else ': ' + problem}")
        failures += problem is not None
    return 1 if failures else 0


def repin(commit: str) -> int:
    """Hash every repoe file of the current pin at `commit` and rewrite PIN.json (trade files keep their URL)."""
    pin = load_pin()
    version_url = f"{RAW_BASE}/{commit}/exported-version.txt"
    request = urllib.request.Request(version_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        version = response.read().decode().strip()
    pin["commit"], pin["version"] = commit, version
    for entry in pin["files"]:
        path = cache_root() / version / entry["path"]
        sha, size = download(file_url(pin, entry), path)
        entry["sha256"], entry["size"] = sha, size
    PIN_FILE.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"pinned {version} at {commit}")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["fetch"]:
        return fetch()
    if argv[:1] == ["verify"]:
        return verify()
    if argv[:1] == ["pin"] and len(argv) == 2:
        return repin(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
