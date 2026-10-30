"""Download the pinned repoe-fork files into the cache folder and check them against the pin.

The cache folder is `<cache_dir>/repoe-fork/<version>/`; `cache_dir` defaults to the configured
cache directory (ADR-0014). Nothing is trusted until its size and sha256 match the pin: a
download goes into a temporary file in the destination folder, is hashed while it streams in,
and only a file that matches is moved into place (`os.replace` is atomic, so two runs that
overlap cannot leave a half file). A failed download leaves no file behind.

After the first fetch nothing here is needed again: `verify_cache` and the loader read the
cache only, and `fetch` itself makes no network call for a file that is already cached and
correct.
"""

import hashlib
import http.client
import os
import tempfile
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from ..config import load_config
from .errors import FetchError, HashMismatchError, MissingDataError
from .pin import PIN, PinnedFile, RepoePin

FETCH_COMMAND = "python -m crafting_system.data fetch"
CHUNK_SIZE = 1024 * 1024
USER_AGENT = "crafting-system"
TIMEOUT_SECONDS = 60

OpenUrl = Callable[[str], AbstractContextManager[BinaryIO]]
Status = Literal["cached", "downloaded", "repaired"]


@dataclass(frozen=True)
class FetchResult:
    """What `fetch` did with one file: `cached` (already there and correct, no network call),
    `downloaded`, or `repaired` (the cached file was wrong and was downloaded again)."""

    name: str
    status: Status
    sha256: str
    size: int


def default_open_url(url: str) -> AbstractContextManager[BinaryIO]:
    """Open `url` for reading bytes (GitHub wants a User-Agent); the real network lives only here."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)


def cache_folder(pin: RepoePin = PIN, cache_dir: Path | None = None) -> Path:
    """Where the files of `pin` are cached; `cache_dir` defaults to the configured cache directory."""
    return version_folder(pin.version, cache_dir)


def version_folder(version: str, cache_dir: Path | None = None) -> Path:
    """The cache folder named `version` (a pin's version, or the commit of a candidate)."""
    base = Path(cache_dir) if cache_dir is not None else load_config().cache_dir
    return base / "repoe-fork" / version


def fetch(
    pin: RepoePin = PIN,
    cache_dir: Path | None = None,
    *,
    open_url: OpenUrl | None = None,
) -> tuple[FetchResult, ...]:
    """Make the cache hold every pinned file, downloading only what is missing or wrong.

    Raises `HashMismatchError` when a download is not the pinned file (nothing is kept) and
    `FetchError` when the network fails or the disk does (the cache folder cannot be created,
    a cached file cannot be read, a download cannot be moved into place).
    """
    if open_url is None:
        open_url = default_open_url
    folder = cache_folder(pin, cache_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FetchError(
            f"could not create the cache folder {folder} (is there a file with that name in the way?): {error}"
        ) from error

    results = []
    for pinned in pin.files:
        target = folder / pinned.name
        existed = target.is_file()
        if existed and _hash_file(target) == (pinned.size, pinned.sha256):
            results.append(FetchResult(pinned.name, "cached", pinned.sha256, pinned.size))
            continue
        _download(pin.url_for(pinned.name), pinned, target, open_url)
        status: Status = "repaired" if existed else "downloaded"
        results.append(FetchResult(pinned.name, status, pinned.sha256, pinned.size))
    return tuple(results)


def verify_cache(pin: RepoePin = PIN, cache_dir: Path | None = None) -> None:
    """Re-hash the cached files; raises `MissingDataError`, `HashMismatchError` or (a file that
    cannot be read) `FetchError`, else returns."""
    folder = cache_folder(pin, cache_dir)
    _require_present(pin, folder)
    for pinned in pin.files:
        path = folder / pinned.name
        size, digest = _hash_file(path)
        if (size, digest) != (pinned.size, pinned.sha256):
            raise _cache_mismatch(pinned, path, size, digest)


def read_verified_files(pin: RepoePin = PIN, cache_dir: Path | None = None) -> dict[str, bytes]:
    """The bytes of every cached file, each checked against the pin (offline: no network is opened).

    The check runs on the very bytes returned, so a file cannot change between check and use.
    """
    folder = cache_folder(pin, cache_dir)
    _require_present(pin, folder)
    contents = {}
    for pinned in pin.files:
        path = folder / pinned.name
        try:
            data = path.read_bytes()
        except OSError as error:
            raise _unreadable(path, error) from error
        digest = hashlib.sha256(data).hexdigest()
        if (len(data), digest) != (pinned.size, pinned.sha256):
            raise _cache_mismatch(pinned, path, len(data), digest)
        contents[pinned.name] = data
    return contents


def _require_present(pin: RepoePin, folder: Path) -> None:
    missing = [pinned.name for pinned in pin.files if not (folder / pinned.name).is_file()]
    if missing:
        raise MissingDataError(
            f"not in the cache folder {folder}: {', '.join(missing)}. "
            f"Run `{FETCH_COMMAND}` to download the pinned data."
        )


def _cache_mismatch(pinned: PinnedFile, path: Path, size: int, digest: str) -> HashMismatchError:
    return HashMismatchError(
        f"{pinned.name}: the cached file {path} does not match the pin: "
        f"expected sha256 {pinned.sha256} ({pinned.size} bytes), "
        f"actual sha256 {digest} ({size} bytes). "
        f"Delete it and run `{FETCH_COMMAND}` to download it again."
    )


def _hash_file(path: Path) -> tuple[int, str]:
    """(size, sha256 hex) of a file, read in chunks; an unreadable file raises `FetchError`."""
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise _unreadable(path, error) from error
    return size, digest.hexdigest()


def _unreadable(path: Path, error: OSError) -> FetchError:
    # One error class for every disk failure in this module, read or write: `FetchError`.
    return FetchError(
        f"could not read the cached file {path}: {error}. "
        "Check that it is not open in another program, then retry."
    )


def _download(url: str, pinned: PinnedFile, target: Path, open_url: OpenUrl) -> None:
    """Stream `url` into a temporary file next to `target`, check it against the pin, and move it into place."""

    def check(received: int, digest: str) -> None:
        if received != pinned.size or digest != pinned.sha256:
            raise _download_mismatch(pinned, url, f"{received} bytes with sha256 {digest}")

    download_file(
        url,
        target,
        open_url,
        name=pinned.name,
        limit=pinned.size,
        too_big=lambda: _download_mismatch(pinned, url, f"more than {pinned.size} bytes"),
        check=check,
    )


def download_file(
    url: str,
    target: Path,
    open_url: OpenUrl,
    *,
    name: str,
    limit: int,
    too_big: Callable[[], Exception],
    check: Callable[[int, str], None],
) -> tuple[int, str]:
    """Stream `url` into a temporary file next to `target`, hashing as it arrives; return (size, sha256 hex).

    The stream is cut off as soon as it goes past `limit` bytes (`too_big()` is raised), and
    `check(size, sha256)` may raise to refuse the finished download. Only an accepted download is
    moved into place (`os.replace`); any failure removes the temporary file, so nothing is left.
    """
    descriptor, temp_name = tempfile.mkstemp(dir=target.parent, prefix=f"{name}.", suffix=".part")
    temp = Path(temp_name)
    try:
        digest = hashlib.sha256()
        received = 0
        with os.fdopen(descriptor, "wb") as out:
            try:
                with open_url(url) as response:
                    while chunk := response.read(CHUNK_SIZE):
                        received += len(chunk)
                        if received > limit:
                            raise too_big()
                        digest.update(chunk)
                        out.write(chunk)
            except (OSError, http.client.HTTPException) as error:
                raise FetchError(f"could not download {url}: {error}") from error
        check(received, digest.hexdigest())
        try:
            os.replace(temp, target)
        except OSError as error:
            raise FetchError(
                f"could not store {name} (from {url}) as {target}: {error}. "
                "Another fetch may be running, or the file may be open in another program; "
                "close it and retry."
            ) from error
        return received, digest.hexdigest()
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _download_mismatch(pinned: PinnedFile, url: str, actual: str) -> HashMismatchError:
    return HashMismatchError(
        f"{pinned.name}: the download from {url} is not the pinned file: "
        f"expected {pinned.size} bytes with sha256 {pinned.sha256}, got {actual}. "
        "The download was thrown away; nothing was kept."
    )
