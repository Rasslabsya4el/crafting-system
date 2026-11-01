"""Shared pytest setup: the network guard of the price tests, and the split of the suite over CI jobs (#165)."""

import os
import socket
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

import pytest
import shard_support

os.environ.setdefault("CRAFTING_WORKERS", "1")  # ticket #250: the suite is serial inside a CI slot (4 slots run at once); a test of the pool sets its own size

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
PRICE_TEST_FILES = "test_prices_*.py"


@pytest.fixture(autouse=True)
def network_guard(request, monkeypatch):
    """Any connection (or name lookup) to a host other than loopback fails with AssertionError.

    Scoped to price tests: it runs for every `test_prices_*.py` module, with no import, and for no
    other module. The local `http.server` tests of the real transport still work; the pathofexile.com
    host never gets a packet, not even a DNS question.
    """
    if not fnmatch(request.node.path.name, PRICE_TEST_FILES):
        return

    def check(host) -> None:
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="replace")
        if host not in LOOPBACK_HOSTS:
            raise AssertionError(f"the test used the network: {host!r}")

    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_getaddrinfo, real_create_connection = socket.getaddrinfo, socket.create_connection

    def connect(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        check(address[0])
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", create_connection)


# --- the split over CI jobs (ticket #165) ---------------------------------------------------------------------
# `pytest --shard 3/32 --shard-durations tests/shard_durations.json` runs the third 32nd of the suite, whole groups
# of tests only (see `shard_support`). CI runs four such slots at once on a runner (`.github/scripts/run_shard.py`).
# Without `--shard` nothing here changes: a plain `pytest` runs every test, in order.

RECORDED: dict[str, float] = defaultdict(float)
GROUPS: dict[str, str] = {}  # node id -> group, kept for the recording


def pytest_addoption(parser):
    group = parser.getgroup("shard", "split the suite over CI jobs")
    group.addoption("--shard", metavar="I/N", help="run only slot I of N (from 1); every slot must see the same tests")
    group.addoption("--shard-durations", metavar="FILE", help="JSON file of seconds per node id that balances the slots")
    group.addoption("--record-durations", metavar="FILE", help="write the seconds of every test that ran to FILE")
    group.addoption("--shard-report", metavar="FILE", help="write how many tests were collected and selected to FILE")


def _wide_params(item) -> dict[str, int]:
    """Index of the value of each parametrized fixture of module scope or wider that the test uses."""
    callspec = getattr(item, "callspec", None)
    if callspec is None:
        return {}
    return {
        name: callspec.indices[name]
        for name, scope in callspec._arg2scope.items()
        if getattr(scope, "value", scope) in shard_support.WIDE_SCOPES
    }


def pytest_collection_modifyitems(config, items):
    option = config.getoption("shard")
    if config.getoption("record_durations"):
        GROUPS.update({item.nodeid: shard_support.group_name(item.nodeid, _wide_params(item)) for item in items})
    if option is None:
        return
    try:
        index, count = shard_support.parse_shard(option)
        durations = shard_support.read_durations(
            Path(config.getoption("shard_durations")) if config.getoption("shard_durations") else None
        )
    except (ValueError, OSError) as problem:
        raise pytest.UsageError(str(problem)) from problem

    group_of = {id(item): shard_support.group_name(item.nodeid, _wide_params(item)) for item in items}
    members: dict[str, list[str]] = defaultdict(list)
    for item in items:
        members[group_of[id(item)]].append(item.nodeid)
    seconds = shard_support.group_seconds(members, durations)
    plan = shard_support.assign(seconds, count)

    mine = [name for name, slot in plan.items() if slot == index]
    start = {name: place for place, name in enumerate(shard_support.order_longest_first(mine, seconds))}
    selected = sorted((item for item in items if group_of[id(item)] in start), key=lambda item: start[group_of[id(item)]])
    chosen = {id(item) for item in selected}
    dropped = [item for item in items if id(item) not in chosen]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
    items[:] = selected

    report = config.getoption("shard_report")
    if report:
        shard_support.write_json(
            Path(report),
            {
                "slot": index, "slots": count, "collected": len(dropped) + len(selected),
                "selected": len(selected), "groups": len(mine), "seconds": round(sum(seconds[name] for name in mine), 1),
            },
        )  # fmt: skip


def pytest_runtest_logreport(report):
    RECORDED[report.nodeid] += report.duration


def pytest_sessionfinish(session):
    target = session.config.getoption("record_durations")
    if target:
        shard_support.write_json(Path(target), shard_support.recording(RECORDED, GROUPS))
