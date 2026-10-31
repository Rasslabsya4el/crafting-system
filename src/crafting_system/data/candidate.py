"""A repoe-fork commit that is not the active pin: learn its files once, then check them like a pin.

The active `PIN` carries its hashes in code. For any other commit (the new patch being compared
to the pinned one) the hashes are not known yet, so the first use downloads the five files at
that commit (same URL scheme as the pin: `base_url`, commit, `data/<name>`), measures their size
and sha256, stores them in `<cache>/repoe-fork/<commit>/` and writes a manifest `pin.json` there.
Every later use loads the manifest into a `RepoePin`, and the ordinary `fetch` and
`load_game_data` check every file against it: a corrupt file is downloaded again and must match
the manifest, and nothing is downloaded while the files are intact.

What this trusts: the commit id (a git commit names its content, and the download is HTTPS) on
the first use, and the manifest after that. It does not change what the active pin means; to
move the pin to a commit, run `python -m crafting_system.data pin`, which starts from what is
learned here.

The manifest is written last and atomically, so its presence means the files were all stored.
Each learned file must parse as JSON before anything is recorded, so an error page served with
status 200 cannot poison the commit. Files without a manifest (an interrupted first use) are
learned again. A manifest that cannot be read or does not fit (wrong commit, other file names, bad hash, not an https URL) is a
`FetchError` naming the file; it is never replaced silently, so a tampered one cannot go
unnoticed. Delete `pin.json` to learn the commit again.
"""

import dataclasses
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import FetchError, RawFormatError
from .fetch import OpenUrl, default_open_url, download_file, version_folder
from .pin import PIN, PinnedFile, RepoePin, is_commit

MANIFEST_NAME = "pin.json"
# Per file. The biggest real file (mods.json) is about 34 MB; this leaves room to grow and
# keeps a wrong URL from filling the disk (at most five files of this size).
MAX_FILE_BYTES = 128 * 1024 * 1024


def candidate_pin(
    commit: str,
    template: RepoePin = PIN,
    cache_dir: Path | None = None,
    *,
    open_url: OpenUrl | None = None,
) -> RepoePin:
    """The pin of `commit`: loaded from its manifest, or learned (downloaded and hashed) if there is none.

    `template` gives the base URL and the file names (the five files the normalizer reads). The
    returned pin's version is the commit, which is also the cache folder's name. The files are
    verified or repaired afterwards by `fetch`, as for any pin.
    """
    if not is_commit(commit):
        raise ValueError(f"commit must be 40 lowercase hex digits, got {commit!r}")
    if commit == template.commit:
        raise ValueError(f"commit {commit} is the active pin: ask for 'pinned', whose hashes come from code")
    folder = version_folder(commit, cache_dir)
    manifest = folder / MANIFEST_NAME
    if manifest.exists():
        return _read_manifest(manifest, commit, template)
    return _learn(commit, template, folder, open_url or default_open_url)


def _learn(commit: str, template: RepoePin, folder: Path, open_url: OpenUrl) -> RepoePin:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FetchError(
            f"could not create the cache folder {folder} (is there a file with that name in the way?): {error}"
        ) from error
    probe = dataclasses.replace(template, version=commit, commit=commit)  # only for its URLs
    stored: list[Path] = []
    learned = []
    try:
        for file in template.files:
            target = folder / file.name
            url = probe.url_for(file.name)
            size, digest = download_file(
                url,
                target,
                open_url,
                name=file.name,
                limit=MAX_FILE_BYTES,
                too_big=lambda url=url, file=file: FetchError(
                    f"{file.name}: the download from {url} is larger than {MAX_FILE_BYTES} bytes; "
                    "it was stopped and nothing was kept."
                ),
                check=lambda size, digest, url=url, file=file: _refuse_empty(file.name, url, size),
            )
            stored.append(target)
            _require_json(target, file.name, commit, url)
            learned.append(PinnedFile(file.name, digest, size))
        pin = dataclasses.replace(probe, files=tuple(learned))
        _write_manifest(folder / MANIFEST_NAME, pin)
    except BaseException:
        for path in stored:
            path.unlink(missing_ok=True)
        raise
    return pin


def _require_json(path: Path, name: str, commit: str, url: str) -> None:
    """A download that is not JSON (an HTML error page with status 200, say) must never be recorded."""
    try:
        json.loads(path.read_bytes())
    except (ValueError, RecursionError) as error:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise RawFormatError(
            f"{name}: the download from {url} (commit {commit}) is not valid JSON: {error}. "
            "Nothing was kept, so the commit can be tried again."
        ) from error
    except OSError as error:
        raise FetchError(f"could not read back {path}: {error}") from error


def _refuse_empty(name: str, url: str, size: int) -> None:
    if size == 0:
        raise FetchError(f"{name}: the download from {url} is empty; nothing was kept.")


def _write_manifest(path: Path, pin: RepoePin) -> None:
    document = {
        "commit": pin.commit,
        "base_url": pin.base_url,
        "files": [{"name": file.name, "sha256": file.sha256, "size": file.size} for file in pin.files],
    }
    text = json.dumps(document, indent=2) + "\n"
    try:
        descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".part")
    except OSError as error:
        raise FetchError(f"could not write the manifest {path}: {error}") from error
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(temp, path)
    except OSError as error:
        raise FetchError(f"could not write the manifest {path}: {error}") from error
    finally:
        temp.unlink(missing_ok=True)


def _read_manifest(path: Path, commit: str, template: RepoePin) -> RepoePin:
    def bad(reason: str) -> FetchError:
        return FetchError(
            f"the manifest {path} cannot be used: {reason}. "
            f"Delete {path.name} (and the files next to it if in doubt) to learn the commit again."
        )

    try:
        document: Any = json.loads(path.read_bytes())
    except (OSError, ValueError, RecursionError) as error:  # ValueError: bad JSON or bad UTF-8
        raise bad(f"it cannot be read as JSON ({error})") from error
    if not isinstance(document, dict) or set(document) != {"commit", "base_url", "files"}:
        raise bad("it must be an object with commit, base_url and files")
    if document["commit"] != commit:
        raise bad(f"it is for commit {document['commit']!r}, not {commit}")
    entries = document["files"]
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) and set(entry) == {"name", "sha256", "size"} for entry in entries
    ):
        raise bad("files must be a list of objects with name, sha256 and size")
    wanted = [file.name for file in template.files]
    if sorted(str(entry["name"]) for entry in entries) != sorted(wanted):
        raise bad(f"it must list exactly {', '.join(wanted)}")
    by_name = {entry["name"]: entry for entry in entries}
    try:
        return RepoePin(
            version=commit,
            commit=commit,
            base_url=document["base_url"],
            files=tuple(PinnedFile(name, by_name[name]["sha256"], by_name[name]["size"]) for name in wanted),
        )
    except (ValueError, TypeError, AttributeError) as error:
        raise bad(str(error)) from error
