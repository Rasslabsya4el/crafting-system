"""The tests' clock (ticket #542): one fixed instant for every place the code defaults to the real clock.

The committed trade prices are dated 2026-10-31 and 2026-11-01, and `MAX_AGE_DAYS` (7) calls them stale from 2026-11-07 / 2026-11-08.
A test that read the age against the real clock would change on those days. The code takes `today` / `now` as arguments wherever
it can; the four places that fall back to `datetime.now(UTC)` when the caller passes none are listed in `CLOCK_READERS`. The autouse
fixture `fixed_clock` of `conftest.py` replaces the `datetime` name in each of them with `FrozenDatetime`, so a call that passes
nothing reads `FIXED_NOW`, whatever day the suite runs on. `CRAFTING_TEST_REAL_CLOCK=1` switches the fixture off (a runner uses it to
show what the real clock would change).
"""

from datetime import UTC, datetime, tzinfo

FIXED_NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
FIXED_DAY = FIXED_NOW.date()

# Every module of the package that reads the clock when its caller gives none, found by `grep -rn "datetime.now" src`.
CLOCK_READERS = (
    "crafting_system.cli._main",
    "crafting_system.cli._benchmark",
    "crafting_system.cli._trade",
    "crafting_system.prices.__main__",
)


class FrozenDatetime(datetime):
    """`datetime` whose `now()` is `FIXED_NOW`; everything else (isinstance, arithmetic, parsing) is the real class."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "FrozenDatetime":
        instant = FIXED_NOW if tz is None else FIXED_NOW.astimezone(tz)
        return cls(instant.year, instant.month, instant.day, instant.hour, instant.minute, instant.second, instant.microsecond, instant.tzinfo)

