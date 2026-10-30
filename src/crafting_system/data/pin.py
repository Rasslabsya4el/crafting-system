"""The pinned repoe-fork version: which files, and the sha256 and size each must have.

repoe-fork.github.io serves "latest" and overwrites it each patch, so the pin names a git
commit of the site's repository instead; a raw.githubusercontent.com URL on that commit never
changes. This is ruleset, not a user setting, which is why it lives here and not in
`crafting.toml`. To move to a new patch, edit `PIN` below and nothing else.

Only the five files the normalizer reads are pinned; the derived `mods_by_base`, `mod_types`
and `tags` dumps are not needed.
"""

import re
from dataclasses import dataclass

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


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


PIN = RepoePin(
    version="3.29.3.3",
    # "Export 3.29.3.3", 2026-10-19, of repoe-fork/repoe-fork.github.io
    commit="ee2084dec1f17180a132b5d133082af5b3136ace",
    base_url="https://raw.githubusercontent.com/repoe-fork/repoe-fork.github.io",
    files=(
        PinnedFile("mods.json", "defbba31b60f9191080c78197278057f834f7f927c1a2a080a7ca6ed3ea686b5", 34279067),
        PinnedFile("base_items.json", "48afb07a5f40eb51552f90c17d53186469db282a2e759dab7b46e7f9d2a0f58b", 8025343),
        PinnedFile("essences.json", "01c6ad55866df673dd25a9b08577ee22802ad3b8f0671b019cb4cf523b9bd700", 141722),
        PinnedFile("fossils.json", "e171c119f874b4f2be2a98366af61c5a2091ca26f508b2f5b9d6b551bb9df181", 364524),
        PinnedFile(
            "crafting_bench_options.json",
            "0fe51ab1657cea69c533bb0610e393f10401156140de88edf686120483cd2845",
            489342,
        ),
    ),
)
