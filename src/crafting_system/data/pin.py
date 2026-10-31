"""The pinned repoe-fork version: which files, and the sha256 and size each must have.

repoe-fork.github.io serves "latest" and overwrites it each patch, so the pin names a git
commit of the site's repository instead; a raw.githubusercontent.com URL on that commit never
changes. This is ruleset, not a user setting, which is why it lives here and not in
`crafting.toml`. The pin is the file `PIN.json` next to this module; `PIN` below is that file,
loaded once. To move to a new patch, run `python -m crafting_system.data pin` (it writes the file
after the cache holds the new files); nobody edits Python or pastes lines.

Only the five files the normalizer reads are pinned; the derived `mods_by_base`, `mod_types`
and `tags` dumps are not needed.
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PinFileError

PIN_FILE = Path(__file__).with_name("PIN.json")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


def is_commit(text: str) -> bool:
    """Whether `text` is a full git commit id the way a pin spells it: 40 lowercase hex digits."""
    return bool(_COMMIT.fullmatch(text))


_WINDOWS_DEVICE = re.compile(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", re.IGNORECASE)


def _is_plain_name(name: str) -> bool:
    """A single file or folder name: it cannot climb out of, or nest inside, the cache folder.

    Also refused, because Windows treats them specially: a `:` (an alternate data stream, or a
    drive), a trailing dot or space (silently dropped), and the device names CON, PRN, AUX, NUL,
    COM1-9 and LPT1-9 with or without an extension.
    """
    return (
        bool(name)
        and name not in (".", "..")
        and not any(c in name for c in ("/", "\\", "\0", ":"))
        and not name.endswith((".", " "))
        and not _WINDOWS_DEVICE.fullmatch(name)
    )


@dataclass(frozen=True)
class PinnedFile:
    """One file of the dump: its name in the site's `data` folder, sha256 (lowercase hex) and size in bytes."""

    name: str
    sha256: str
    size: int

    def __post_init__(self):
        if not _is_plain_name(self.name):
            raise ValueError(f"pinned file name must be a plain file name, got {self.name!r}")
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError(f"{self.name}: sha256 must be 64 lowercase hex digits, got {self.sha256!r}")
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size <= 0:
            raise ValueError(f"{self.name}: size must be a positive integer, got {self.size!r}")


@dataclass(frozen=True)
class RepoePin:
    """A repoe-fork patch: the folder name (`version`), the commit the files are read at, and the files."""

    version: str
    commit: str
    base_url: str
    files: tuple[PinnedFile, ...]

    def __post_init__(self):
        if not _is_plain_name(self.version):
            raise ValueError(f"pin version is used as a folder name, got {self.version!r}")
        if not _COMMIT.fullmatch(self.commit):
            raise ValueError(f"pin commit must be 40 lowercase hex digits, got {self.commit!r}")
        if not self.base_url.startswith("https://") or self.base_url.endswith("/"):
            raise ValueError(f"pin base_url must be an https URL without a trailing slash, got {self.base_url!r}")
        if not self.files:
            raise ValueError("pin lists no files")
        names = [file.name for file in self.files]
        if len(set(names)) != len(names):
            raise ValueError(f"pin lists a file twice: {sorted({n for n in names if names.count(n) > 1})}")

    def url_for(self, name: str) -> str:
        """Where a pinned file is downloaded from (the site's `data` folder at the pinned commit)."""
        return f"{self.base_url}/{self.commit}/data/{name}"


def load_pin(path: Path = PIN_FILE) -> RepoePin:
    """The pin written in `path` (`PIN.json`); a file that cannot be read or does not fit is a `PinFileError` naming it."""

    def bad(reason: str) -> PinFileError:
        return PinFileError(f"the pin file {path} cannot be used: {reason}")

    try:
        document: Any = json.loads(Path(path).read_bytes())
    except (OSError, ValueError, RecursionError) as error:  # ValueError: bad JSON or bad UTF-8
        raise bad(f"it cannot be read as JSON ({error})") from error
    if not isinstance(document, dict) or set(document) != {"version", "commit", "base_url", "files"}:
        raise bad("it must be an object with version, commit, base_url and files")
    entries = document["files"]
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) and set(entry) == {"name", "sha256", "size"} for entry in entries
    ):
        raise bad("files must be a list of objects with name, sha256 and size")
    try:
        return RepoePin(
            version=document["version"],
            commit=document["commit"],
            base_url=document["base_url"],
            files=tuple(PinnedFile(entry["name"], entry["sha256"], entry["size"]) for entry in entries),
        )
    except (ValueError, TypeError, AttributeError) as error:
        raise bad(str(error)) from error


def write_pin(pin: RepoePin, path: Path = PIN_FILE) -> None:
    """Write `pin` as the pin file: all of it or none of it (a temp file next to `path`, then `os.replace`)."""
    document = {
        "version": pin.version,
        "commit": pin.commit,
        "base_url": pin.base_url,
        "files": [{"name": file.name, "sha256": file.sha256, "size": file.size} for file in pin.files],
    }
    text = json.dumps(document, indent=2) + "\n"
    path = Path(path)
    try:
        descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".part")
    except OSError as error:
        raise PinFileError(f"could not write the pin file {path}: {error}") from error
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(temp, path)
    except OSError as error:
        raise PinFileError(f"could not write the pin file {path}: {error}") from error
    finally:
        temp.unlink(missing_ok=True)


PIN = load_pin()
