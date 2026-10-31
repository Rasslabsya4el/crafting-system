"""Splitting the suite over CI jobs (ticket #165): which test goes to which shard, and how long each took.

The pieces are plain functions so that `tests/test_shard.py` can check them; `tests/conftest.py` wires them to
pytest (`--shard SLOT/TOTAL`, `--shard-durations FILE`, `--record-durations FILE`, `--shard-report FILE`).

A *group* is the unit that is never split: all tests of one module, or, when a module-scoped (or wider) fixture
is parametrized, all tests of one module and one value of that fixture. Such a fixture is where the expensive
part lives (a route solved, the game data read); with the group in one slot, one process, it is built once.
Every process computes the same plan from the same collected tests and the same durations file, so no
coordinator is needed: the groups go to slots longest first, each to the slot with the least time so far.
"""

import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

WIDE_SCOPES = frozenset({"module", "package", "session"})
UNKNOWN_SECONDS = 1.0  # one test's time when no durations file is given at all
SHARD_FORMAT = re.compile(r"(\d+)/(\d+)")


def parse_shard(text: str) -> tuple[int, int]:
    """`"3/8"` is shard 3 of 8, counted from 1."""
    found = SHARD_FORMAT.fullmatch(text.strip())
    if found is None:
        raise ValueError(f"--shard wants I/N such as 3/8, not {text!r}")
    index, count = int(found.group(1)), int(found.group(2))
    if not 1 <= index <= count:
        raise ValueError(f"--shard {text!r}: the shard number must be from 1 to {count}")
    return index, count


def group_name(nodeid: str, wide_params: Mapping[str, int]) -> str:
    """The group of a test: its module, and the index of each module-or-wider parametrized fixture.

    `wide_params` maps the argument name to the index of the value this test uses (not the value itself,
    which may print differently on two machines).
    """
    module = nodeid.split("::", 1)[0]
    if not wide_params:
        return module
    return module + "[" + ",".join(f"{name}#{wide_params[name]}" for name in sorted(wide_params)) + "]"


def read_durations(path: Path | None) -> dict[str, float]:
    """The seconds of each test by its node id; empty when no file is given."""
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {str(nodeid): float(seconds) for nodeid, seconds in document.items()}


def group_seconds(members: Mapping[str, Sequence[str]], durations: Mapping[str, float]) -> dict[str, float]:
    """Seconds per group: the sum of its tests; a test without a stored time costs the median of the stored ones."""
    known = [durations[nodeid] for nodeids in members.values() for nodeid in nodeids if nodeid in durations]
    if known:
        unknown = statistics.median(known)
    else:
        unknown = UNKNOWN_SECONDS
    return {
        group: sum(durations.get(nodeid, unknown) for nodeid in nodeids) for group, nodeids in members.items()
    }


def assign(seconds: Mapping[str, float], count: int) -> dict[str, int]:
    """Group -> shard number (from 1): longest group first, each to the shard with the least time so far.

    Ties break by group name and then by the lower shard number, so every shard gets the same answer.
    """
    loads = [0.0] * count
    plan: dict[str, int] = {}
    for group in sorted(seconds, key=lambda name: (-seconds[name], name)):
        shard = min(range(count), key=lambda index: (loads[index], index))
        loads[shard] += seconds[group]
        plan[group] = shard + 1
    return plan


def order_longest_first(groups: Iterable[str], seconds: Mapping[str, float]) -> list[str]:
    """The groups of one shard in the order they should start, so the long ones do not end the run alone."""
    return sorted(groups, key=lambda name: (-seconds[name], name))


def write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
