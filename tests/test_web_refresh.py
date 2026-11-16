"""The site's scheduled price refresh (#1008, OR-9): the fetch runs on an interval of the injected clock, its new file replaces the live one in
one step, a failed or broken fetch keeps the old file and says why in the log, and two fetches never run at once. The fetch is a stand-in:
no test opens a network connection, reads the clock or sleeps."""

import dataclasses
import logging
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crafting_system.prices import load_price_file, write_price_file
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME, PRICE_FILE_NAME
from crafting_system.web import MIN_INTERVAL, FetchRun, PriceRefresh, fetch_arguments, fetch_command

FIXTURE = Path(__file__).parent / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
T0 = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
SIX_HOURS = timedelta(hours=6)
HAND_PRICES = '[prices]\n"Orb of Alteration" = 0.2\n'


class Clock:
    """The wall clock of a test: `wait` moves it on instead of sleeping, and says "stopped" after `waits` waits."""

    def __init__(self, now: datetime, waits: int = 1000) -> None:
        self.now = now
        self.waits = waits
        self.waited: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def wait(self, seconds: float) -> bool:
        if len(self.waited) >= self.waits:
            return True
        self.waited.append(seconds)
        self.now += timedelta(seconds=seconds)
        return False


def old_file(folder: Path, fetched_at: datetime = T0) -> Path:
    path = folder / PRICE_FILE_NAME
    write_price_file(path, dataclasses.replace(load_price_file(FIXTURE), fetched_at=fetched_at))
    return path


def writing_fetch(clock: Clock, calls: list, **changes):
    """A stand-in fetch that writes a price file fetched at the clock's time (with `changes`) into the folder it is given."""

    def fetch(data_dir: Path, league: str | None) -> FetchRun:
        calls.append((clock.now, league, data_dir))
        base = load_price_file(data_dir / PRICE_FILE_NAME) if (data_dir / PRICE_FILE_NAME).exists() else load_price_file(FIXTURE)
        write_price_file(data_dir / PRICE_FILE_NAME, dataclasses.replace(base, fetched_at=clock.now.replace(microsecond=0), **changes))
        return FetchRun(0, "League Allflame: prices written")

    return fetch


def refresher(tmp_path: Path, fetch, clock: Clock, **options) -> PriceRefresh:
    return PriceRefresh(tmp_path / PRICE_FILE_NAME, tmp_path / OVERRIDES_FILE_NAME, fetch, interval=SIX_HOURS, clock=clock, wait=clock.wait, **options)


def test_the_fetch_runs_when_the_file_is_due_and_then_every_interval(tmp_path):
    old_file(tmp_path, T0 - timedelta(hours=2))
    clock, calls = Clock(T0, waits=3), []
    refresh = refresher(tmp_path, writing_fetch(clock, calls), clock)

    refresh.run()

    assert [moment for moment, _, _ in calls] == [T0 + timedelta(hours=4), T0 + timedelta(hours=10), T0 + timedelta(hours=16)]
    assert clock.waited == [4 * 3600.0, 6 * 3600.0, 6 * 3600.0]  # the fourth wait is told to stop
    assert load_price_file(tmp_path / PRICE_FILE_NAME).fetched_at == T0 + timedelta(hours=16)
    assert [name for name in tmp_path.iterdir()] == [tmp_path / PRICE_FILE_NAME]  # the fetch's own folder is gone


def test_with_no_price_file_the_first_fetch_is_at_once_and_its_league_is_the_sources(tmp_path):
    clock, calls = Clock(T0, waits=0), []
    refresh = refresher(tmp_path, writing_fetch(clock, calls), clock)

    assert refresh.due() == T0
    refresh.run()

    assert [(moment, league) for moment, league, _ in calls] == [(T0, None)]  # no league configured, no file: poe.ninja's current one
    assert load_price_file(tmp_path / PRICE_FILE_NAME).league == "Allflame"


def test_the_league_is_the_configured_one_else_the_one_of_the_file_in_place(tmp_path):
    old_file(tmp_path)
    clock, calls = Clock(T0), []
    assert refresher(tmp_path, writing_fetch(clock, calls), clock).refresh()
    assert refresher(tmp_path, writing_fetch(clock, calls), clock, league="Allflame").refresh()
    assert [league for _, league, _ in calls] == ["Allflame", "Allflame"]


def test_a_failed_fetch_keeps_the_old_file_says_why_and_is_tried_again_after_the_retry(tmp_path, caplog):
    old_file(tmp_path, T0 - timedelta(days=1))
    before = (tmp_path / PRICE_FILE_NAME).read_bytes()
    clock, calls = Clock(T0, waits=2), []

    def failing(data_dir: Path, league: str | None) -> FetchRun:
        calls.append(clock.now)
        return FetchRun(1, "Error: the Currency prices failed: HTTP 503; no price file was written, the old price file was kept")

    refresh = refresher(tmp_path, failing, clock)
    with caplog.at_level(logging.ERROR, logger="crafting_system.web._refresh"):
        refresh.run()

    assert calls == [T0, T0 + timedelta(minutes=15), T0 + timedelta(minutes=30)]
    assert (tmp_path / PRICE_FILE_NAME).read_bytes() == before
    assert "wrote no file (exit code 1)" in caplog.text and "HTTP 503" in caplog.text


@pytest.mark.parametrize(
    ("write", "words"),
    [
        (lambda path: path.write_text("{ not json", encoding="utf-8"), "does not load"),
        (lambda path: write_price_file(path, dataclasses.replace(load_price_file(FIXTURE), league="Standard")), "the league 'Standard'"),
        (
            lambda path: write_price_file(path, dataclasses.replace(load_price_file(FIXTURE), prices={k: v for k, v in load_price_file(FIXTURE).prices.items() if k != "Divine Orb"})),
            "no price for Divine Orb",
        ),
    ],
    ids=["not-json", "other-league", "no-divine"],
)
def test_a_broken_file_is_not_used_and_the_old_one_stays(tmp_path, caplog, write, words):
    old_file(tmp_path)
    before = (tmp_path / PRICE_FILE_NAME).read_bytes()
    reloads: list[int] = []

    def broken(data_dir: Path, league: str | None) -> FetchRun:
        write(data_dir / PRICE_FILE_NAME)
        return FetchRun(0, "League ?: prices written")

    clock = Clock(T0)
    with caplog.at_level(logging.ERROR, logger="crafting_system.web._refresh"):
        assert not refresher(tmp_path, broken, clock, on_new_file=lambda: reloads.append(1)).refresh()

    assert (tmp_path / PRICE_FILE_NAME).read_bytes() == before
    assert words in caplog.text and reloads == []


def test_a_new_file_replaces_the_old_one_and_the_server_is_told(tmp_path):
    old_file(tmp_path, T0 - timedelta(days=3))
    (tmp_path / OVERRIDES_FILE_NAME).write_text(HAND_PRICES, encoding="utf-8")
    clock, calls, reloads = Clock(T0), [], []
    seen: list[set[str]] = []

    def fetch(data_dir: Path, league: str | None) -> FetchRun:
        seen.append({path.name for path in data_dir.iterdir()})  # the fetch reads the old file and the overrides from its own folder
        return writing_fetch(clock, calls)(data_dir, league)

    assert refresher(tmp_path, fetch, clock, on_new_file=lambda: reloads.append(load_price_file(tmp_path / PRICE_FILE_NAME).fetched_at)).refresh()

    assert seen == [{PRICE_FILE_NAME, OVERRIDES_FILE_NAME}]
    assert reloads == [T0]
    assert (tmp_path / OVERRIDES_FILE_NAME).read_text(encoding="utf-8") == HAND_PRICES  # the hand prices are never touched


def test_a_fetch_that_exits_with_an_error_after_writing_a_usable_file_is_used_and_logged(tmp_path, caplog):
    old_file(tmp_path, T0 - timedelta(days=1))
    clock, calls = Clock(T0), []
    write = writing_fetch(clock, calls)

    def incomplete(data_dir: Path, league: str | None) -> FetchRun:
        write(data_dir, league)
        return FetchRun(1, "Error: 3 names were not read on the trade site")

    with caplog.at_level(logging.WARNING, logger="crafting_system.web._refresh"):
        assert refresher(tmp_path, incomplete, clock).refresh()
    assert load_price_file(tmp_path / PRICE_FILE_NAME).fetched_at == T0
    assert "exit code 1 but wrote a usable file" in caplog.text


def test_two_fetches_never_run_at_once(tmp_path, caplog):
    old_file(tmp_path)
    clock, calls = Clock(T0), []
    inside, release = threading.Event(), threading.Event()
    write = writing_fetch(clock, calls)

    def slow(data_dir: Path, league: str | None) -> FetchRun:
        inside.set()
        release.wait()
        return write(data_dir, league)

    refresh = refresher(tmp_path, slow, clock)
    first = threading.Thread(target=refresh.refresh)
    first.start()
    inside.wait()
    with caplog.at_level(logging.WARNING, logger="crafting_system.web._refresh"):
        assert not refresh.refresh()  # skipped: the fetch is not called a second time
    release.set()
    first.join()

    assert len(calls) == 1 and "already running" in caplog.text


def test_the_interval_is_at_least_a_quarter_of_an_hour(tmp_path):
    clock = Clock(T0)
    assert MIN_INTERVAL == timedelta(minutes=15)
    with pytest.raises(ValueError, match="at most every"):
        PriceRefresh(tmp_path / PRICE_FILE_NAME, tmp_path / OVERRIDES_FILE_NAME, writing_fetch(clock, []), interval=timedelta(minutes=5), clock=clock)


def test_the_real_fetch_is_the_price_command_in_its_own_data_folder(tmp_path, monkeypatch):
    assert fetch_arguments(None, None, None) == ["fetch"]
    assert fetch_arguments("Allflame", Path("w.txt"), 5.0) == ["fetch", "--league", "Allflame", "--wanted-file", "w.txt", "--trade-below", "5.0"]
    ran: list = []

    def run(argv, **options):
        ran.append((argv, options["env"]["CRAFTING_DATA_DIR"], options["timeout"]))

        class Done:
            returncode, stdout, stderr = 0, "out\n", "err\n"

        return Done()

    monkeypatch.setattr("crafting_system.web._refresh.subprocess.run", run)
    done = fetch_command(wanted=["Chaos Orb", "Orb of Alteration"], timeout_seconds=120)(tmp_path, "Allflame")

    assert done == FetchRun(0, "out\nerr\n")
    argv, data_dir, timeout = ran[0]
    assert argv == [sys.executable, "-m", "crafting_system.prices", "fetch", "--league", "Allflame", "--wanted-file", str(tmp_path / "wanted.txt")]
    assert (data_dir, timeout) == (str(tmp_path), 120)
    assert (tmp_path / "wanted.txt").read_text(encoding="utf-8") == "Chaos Orb\nOrb of Alteration\n"
