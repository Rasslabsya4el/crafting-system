"""The scheduled price refresh of the site (OR-9, #1008): the service fetches its own prices; nobody copies a price file in.

**What runs.** The price command itself, `python -m crafting_system.prices fetch` (`fetch_command`), in a child process of the server: the
same fetch, pacing and trade limiter as the command (`prices.paced`, `prices.RateLimiter`), never a second fetch. It is given a folder of
its own as its data folder (`CRAFTING_DATA_DIR`), beside the live price file and holding a copy of it and of the overrides, so the fetch
reads the old prices it keeps and merges exactly as it does at the command line, and writes its new file there, not over the live one.

**What is kept.** The new file replaces the live one (`os.replace`, one step, the same folder) only when the fetch wrote one and it loads
with its overrides, is of the league the site serves and prices the Chaos and the Divine Orb. Otherwise the old file stays, and why goes to
the server's log with the command's own output. The server's world is reloaded on its next request when the file changed (#968);
`on_new_file` lets the caller load it at once.

**When.** One refresh at a time (`refresh` never runs two fetches at once: a second call while one runs is skipped and logged). `run`
refreshes when the live file is older than `interval` (at once when it is missing or unreadable), then every `interval` (never waiting longer than that, even for a file
stamped ahead of the clock); a refresh that failed at any step is logged and tried again after `retry`, and the schedule lives on. A fetch's
folder left by a server killed during it is removed by the next refresh. The interval is a setting of the machine (`CRAFTING_PRICE_REFRESH_HOURS`, off by default), at least
`MIN_INTERVAL`, so the site never asks the sources more often than their own rows change.

**Time.** `clock` (the wall clock, timezone-aware) and `wait(seconds) -> stopped` are the caller's, so a test gives its own: nothing waits
or reads the clock otherwise. The default clock is the only place here that reads it.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crafting_system.prices import CHAOS_ORB, DIVINE_ORB, PriceFile, PriceFileNotFound, load_price_file, load_prices

MIN_INTERVAL = timedelta(minutes=15)  # poe.ninja's overviews change about hourly; the site never asks more often than this
RETRY = timedelta(minutes=15)  # a failed refresh is tried again after this, not at the next interval
STAGING_PREFIX = ".price-refresh-"  # the fetch's own data folder, beside the live price file (one per refresh)
WANTED_NAME = "wanted.txt"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchRun:
    """What one run of the fetch gave: its exit code and its output (both streams), for the log."""

    code: int
    output: str


Fetch = Callable[[Path, str | None], FetchRun]  # (its data folder, the league or None for poe.ninja's current) -> its run
Clock = Callable[[], datetime]
Wait = Callable[[float], bool]  # waits up to that many seconds; True when the refresh is being stopped


def _utc_now() -> datetime:
    return datetime.now(UTC)


def fetch_arguments(league: str | None, wanted_file: Path | None, trade_below: float | None) -> list[str]:
    """The arguments of the price command for one refresh (after `python -m crafting_system.prices`)."""
    arguments = ["fetch"]
    if league is not None:
        arguments += ["--league", league]
    if wanted_file is not None:
        arguments += ["--wanted-file", str(wanted_file)]
    if trade_below is not None:
        arguments += ["--trade-below", repr(trade_below)]
    return arguments


def fetch_command(*, wanted: Sequence[str] = (), trade_below: float | None = None, timeout_seconds: float = 3600.0) -> Fetch:
    """The real fetch: the price command in a child process with `data_dir` as its data folder, cut off after `timeout_seconds`.

    `wanted` are the names priced beyond the overviews (the command's `--wanted-file`, written into the fetch's folder); `trade_below`
    is its `--trade-below` (the trade site's offers read for thin names, within its limiter's budget), off when None.
    """

    def fetch(data_dir: Path, league: str | None) -> FetchRun:
        wanted_file = None
        if wanted:
            wanted_file = data_dir / WANTED_NAME
            wanted_file.write_text("".join(f"{name}\n" for name in wanted), encoding="utf-8")
        argv = [sys.executable, "-m", "crafting_system.prices", *fetch_arguments(league, wanted_file, trade_below)]
        env = {**os.environ, "CRAFTING_DATA_DIR": str(data_dir)}
        try:
            done = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds)
        except subprocess.TimeoutExpired as expired:
            return FetchRun(-1, f"the fetch was stopped after {timeout_seconds:.0f} s\n{_text(expired.stdout)}{_text(expired.stderr)}")
        return FetchRun(done.returncode, done.stdout + done.stderr)

    return fetch


def _text(stream: str | bytes | None) -> str:
    if stream is None:
        return ""
    return stream if isinstance(stream, str) else stream.decode("utf-8", "replace")


class PriceRefresh:
    """The site's price refresh (see the module text): `refresh` once, or `start` the schedule in a thread and `stop` it."""

    def __init__(
        self,
        price_path: Path,
        overrides_path: Path,
        fetch: Fetch,
        *,
        interval: timedelta,
        league: str | None = None,
        retry: timedelta = RETRY,
        clock: Clock = _utc_now,
        wait: Wait | None = None,
        on_new_file: Callable[[], object] | None = None,
    ) -> None:
        if not interval >= MIN_INTERVAL:
            raise ValueError(f"the price refresh runs at most every {MIN_INTERVAL}, not every {interval}")
        if league is not None and not league.strip():
            raise ValueError("the league of the price refresh must not be blank")
        self.price_path = Path(price_path)
        self.overrides_path = Path(overrides_path)
        self.interval = interval
        self.retry = retry
        self._fetch = fetch
        self._league = league
        self._clock = clock
        self._stopping = threading.Event()
        self._wait = wait if wait is not None else self._stopping.wait
        self._on_new_file = on_new_file
        self._busy = threading.Lock()  # one fetch at a time
        self._thread: threading.Thread | None = None

    # --- one refresh --------------------------------------------------------------------------------------------------------------

    def refresh(self) -> bool:
        """Fetch once and put the new file in place; False (the old file kept, the reason logged) when it failed or one is running."""
        if not self._busy.acquire(blocking=False):
            _log.warning("a price refresh is already running; this one is skipped")
            return False
        try:
            return self._refresh()
        except Exception:  # noqa: BLE001  (a full or read-only volume, an unreadable overrides file: the schedule lives on and tries again)
            _log.exception("the price refresh failed; the old price file stays")
            return False
        finally:
            self._busy.release()

    def _refresh(self) -> bool:
        old = _readable(self.price_path)
        league = self._league if self._league is not None else (old.league if old is not None else None)
        self.price_path.parent.mkdir(parents=True, exist_ok=True)
        for left in self.price_path.parent.glob(STAGING_PREFIX + "*"):  # a fetch's folder left by a server killed during it
            shutil.rmtree(left, ignore_errors=True)
        staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=self.price_path.parent))
        try:
            staged = staging / self.price_path.name
            staged_overrides = staging / self.overrides_path.name
            if old is not None:
                shutil.copy2(self.price_path, staged)  # the fetch keeps and merges the old prices as the command does
            if self.overrides_path.exists():
                shutil.copy2(self.overrides_path, staged_overrides)
            before = _identity(staged)
            try:
                run = self._fetch(staging, league)
            except Exception:  # noqa: BLE001  (a refresh that cannot even start never takes the site down)
                _log.exception("the price refresh could not run the fetch; the old price file stays")
                return False
            words = run.output.strip()
            if _identity(staged) == before:
                _log.error("the price fetch wrote no file (exit code %s); the old price file stays. Its output:\n%s", run.code, words)
                return False
            problem = _broken(staged, staged_overrides, league)
            if problem is not None:
                _log.error("the price fetch wrote a file that is not used (%s); the old price file stays. Its output:\n%s", problem, words)
                return False
            new = load_price_file(staged)
            os.replace(staged, self.price_path)  # one step: the server reads the old file or the new one, never half of one
            if run.code != 0:
                _log.warning("the price fetch ended with exit code %s but wrote a usable file, now in use. Its output:\n%s", run.code, words)
            else:
                _log.info("the price fetch wrote a new file. Its output:\n%s", words)
            _log.info(
                "new prices in use: league %s, fetched %s, %d prices",
                new.league,
                new.fetched_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                len(new.prices),
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        if self._on_new_file is not None:
            try:
                self._on_new_file()
            except Exception:  # noqa: BLE001  (the file is in place; the server loads it at its next request in any case)
                _log.exception("the new price file is in place, but loading it at once failed")
        return True

    # --- the schedule -------------------------------------------------------------------------------------------------------------

    def due(self) -> datetime:
        """When the next refresh is due: the live file's fetch time plus the interval, or now when there is no readable file."""
        old = _readable(self.price_path)
        if old is None:
            return self._clock()
        return old.fetched_at + self.interval

    def run(self) -> None:
        """Refresh on the schedule until `stop` (or the injected `wait` says the refresh is being stopped)."""
        due = self.due()
        while not self._stopping.is_set():
            delay = min((due - self._clock()).total_seconds(), self.interval.total_seconds())  # a file stamped ahead of the clock
            if delay > 0 and self._wait(delay):
                return
            if self._stopping.is_set():
                return
            if self.refresh():
                due = self._clock() + self.interval
            elif self.wait_retry():
                return
            else:
                due = self._clock()

    def wait_retry(self) -> bool:
        """Wait the time after which a failed refresh is tried again; True when the refresh is being stopped meanwhile."""
        return self._wait(self.retry.total_seconds()) or self._stopping.is_set()

    def start(self) -> None:
        """Run the schedule in a daemon thread of the server."""
        self._thread = threading.Thread(target=self.run, name="price-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Ask the schedule to end: it ends at once while it waits, and after the fetch that runs otherwise (not waited for here)."""
        self._stopping.set()


def _readable(path: Path) -> PriceFile | None:
    """The price file at `path`, or None when it is missing or does not load."""
    try:
        return load_price_file(path)
    except (PriceFileNotFound, ValueError, OSError):
        return None


def _identity(path: Path) -> tuple[int, int, int] | None:
    """How a file stands (its file number, write time and size), or None when it is missing: a file the fetch wrote differs."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (status.st_ino, status.st_mtime_ns, status.st_size)


def _broken(path: Path, overrides_path: Path, league: str | None) -> str | None:
    """Why the price file at `path` must not replace the live one, or None when it may."""
    try:
        new = load_prices(path, overrides_path)
    except (PriceFileNotFound, ValueError, OSError) as error:
        return f"it does not load: {error}"
    if league is not None and new.league != league:
        return f"it is of the league {new.league!r}, and the site serves {league!r}"
    missing = [name for name in (CHAOS_ORB, DIVINE_ORB) if name not in new.prices]
    if missing:
        return f"it has no price for {' and '.join(missing)}"
    if not new.chaos_per_divine > 0:
        return f"its Divine Orb rate is {new.chaos_per_divine!r}"
    return None
