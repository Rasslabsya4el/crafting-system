"""Shared pytest setup: the network guard of the price tests, and the split of the suite over CI jobs (#165)."""

import importlib
import os
import socket
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

import pytest
import shard_support

import crafting_system.cli  # noqa: F401  (it names the page to the planner: a test that imports only `crafting_system.planner` still finishes its plans, issue #882)

os.environ.setdefault("CRAFTING_WORKERS", "1")  # ticket #250: the suite is serial inside a CI slot (4 slots run at once); a test of the pool sets its own size

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
PRICE_TEST_FILES = "test_prices_*.py"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    """Every place that defaults to the real clock reads `clock_support.FIXED_NOW` instead (ticket #542).

    The committed price fixtures age with the calendar (`MAX_AGE_DAYS` = 7), so a test must not read the age against the day it runs
    on. A test that passes `today` / `now` is unaffected. `CRAFTING_TEST_REAL_CLOCK=1` turns this off.
    """
    if os.environ.get("CRAFTING_TEST_REAL_CLOCK") == "1":
        return
    try:
        import clock_support  # imported here: the tests that copy this conftest into a bare project have no such module
    except ModuleNotFoundError:
        return
    for name in clock_support.CLOCK_READERS:
        monkeypatch.setattr(importlib.import_module(name), "datetime", clock_support.FrozenDatetime)


@pytest.fixture(autouse=True)
def progress_sink_restored(monkeypatch):
    """Where the planner says the phases of a long plan (`planner._packed.PROGRESS`) is put back after each test.

    A script run in the test's own process (`state_bloat.main`, `family_bench`, ...) sets it to a printer and leaves it set; a later test of
    the same shard then found those lines in what it captured (`test_planner_entry`, PR #944).
    """
    from crafting_system.planner import _packed

    monkeypatch.setattr(_packed, "PROGRESS", _packed.PROGRESS)


# The net of the suite's machine (#886, OR-39: a planner limit is a setting of the machine a run is on; docs/ci.md, "The suite's machine
# net"). It never changes what a test that passes computes: it turns a hang or a runner killed for memory into a named test failure.
# * A run that has a budget (the command's default, `Budget.default()`) takes `budget.MEMORY_SHARE` of the machine divided among the
#   pytest processes sharing it: `CRAFTING_TEST_SLOTS`, which `run_shard.py` sets to its `--procs` (1 when unset, as on a serial run). It
#   is set once for the whole process, module fixtures included; a module of the budget itself (`OWN_NET = True`) sees the undivided share.
# * Where the machine has `SIGALRM` (Linux, the CI runners), a watchdog wakes every `WATCH_SECONDS` during a test's setup, call and
#   teardown: past `SUITE_TEST_SECONDS` of wake-ups, or with the process's resident memory past `SUITE_DATA_MB`, the phase fails by name
#   (`pytest.fail`, a `BaseException` no `except Exception` or `except MemoryError` of the planner catches). It reads no clock (it counts its
#   wake-ups) and puts no cap on the process, so no allocation fails and no fallback of the planner on a MemoryError is taken because of it.
# The planner itself is not touched: a plan with no budget still runs its exact proof, and a test that passes its own budget keeps it.
# `CRAFTING_TEST_SECONDS` and `CRAFTING_TEST_DATA_MB` set other figures; 0 turns that net off.
SLOTS_PER_RUNNER = max(1, int(os.environ.get("CRAFTING_TEST_SLOTS", "1")))
SUITE_TEST_SECONDS = int(os.environ.get("CRAFTING_TEST_SECONDS", "300"))
SUITE_DATA_MB = int(os.environ.get("CRAFTING_TEST_DATA_MB", "3500"))
WATCH_SECONDS = 1
_MACHINE_SHARE: list[float] = []  # the undivided `budget.MEMORY_SHARE`, kept for the modules that test the budget itself


def pytest_configure(config):
    from crafting_system import budget as budget_module

    _MACHINE_SHARE.append(budget_module.MEMORY_SHARE)
    budget_module.MEMORY_SHARE = budget_module.MEMORY_SHARE / SLOTS_PER_RUNNER


@pytest.fixture(autouse=True)
def suite_net(request, monkeypatch):
    """A module of the budget itself (`OWN_NET = True`) sees the machine's share undivided (see `SLOTS_PER_RUNNER`)."""
    if getattr(request.module, "OWN_NET", False):
        from crafting_system import budget as budget_module

        monkeypatch.setattr(budget_module, "MEMORY_SHARE", _MACHINE_SHARE[0])


def _watched(phase: str):
    """The watchdog of one phase of a test (its setup, a module's fixtures included, its call or its teardown), where `SIGALRM` is."""
    import signal

    if not hasattr(signal, "SIGALRM") or (SUITE_TEST_SECONDS <= 0 and SUITE_DATA_MB <= 0):
        yield
        return
    from crafting_system.budget import process_mb

    woken = [0]

    def wake(signum, frame):
        woken[0] += 1
        if SUITE_TEST_SECONDS > 0 and woken[0] * WATCH_SECONDS >= SUITE_TEST_SECONDS:
            pytest.fail(f"the {phase} ran past the suite's {SUITE_TEST_SECONDS} s (conftest.SUITE_TEST_SECONDS, #886)", pytrace=False)
        held = process_mb() if SUITE_DATA_MB > 0 else None
        if held is not None and held > SUITE_DATA_MB:
            pytest.fail(f"the {phase} held {held:.0f} MB, past the suite's {SUITE_DATA_MB} MB a process (conftest.SUITE_DATA_MB, #886)", pytrace=False)

    previous = signal.signal(signal.SIGALRM, wake)
    signal.setitimer(signal.ITIMER_REAL, WATCH_SECONDS, WATCH_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    yield from _watched("setup")
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    yield from _watched("test")
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    yield from _watched("teardown")
    return None


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


# Tests that every beta method on by default (#886) sends past the suite's machine net or to other numbers, and that wait for #1101 (a
# run counted in states, so that a real route plans in CI's time and memory, then its records taken again). fnmatch patterns on the node id.
# * `WAITS_FOR_1101`: real routes planned with the default offers. An xfail that is not run: run, each would hold its slot up to the
#   time net (300 s a phase) and leave memory that fails the next tests of its process. #1101 empties this list and runs them again.
# * `RERECORD_FOR_1101`: goldens whose numbers move with the defaults. A strict xfail that is run, so it shows the moment the golden is
#   recorded again (it then passes and turns red until its pattern leaves the list). Never edit a golden by hand.
WAITS_FOR_1101 = (
    "tests/test_abstraction_pattern_real.py::test_the_bound_is_never_above_the_exact_cost_on_the_walked_graph[[]r05-auto[]]",
    "tests/test_abstraction_pattern_real.py::test_the_bound_is_never_above_the_exact_cost_on_the_walked_graph[[]r13-*[]]",
    "tests/test_add_bound.py::test_through_the_entry_r12_with_the_exalted_orb_offered_gets_its_exact_plan_as_cheap_as_without",
    "tests/test_cli_envelope_real.py::*[[]R05[]]",
    "tests/test_cli_envelope_real.py::test_a_bound_raised_above_the_exact_cost_at_some_keys_is_caught",
    "tests/test_cli_r08_r09_real.py::*",
    "tests/test_cli_r13_real.py::*",
    "tests/test_cli_real.py::test_the_command_on_the_real_r12_amulet",
    "tests/test_cli_real.py::test_verify_agrees_with_the_computed_mean_on_the_real_amulet",
    "tests/test_cli_real.py::test_without_a_lifeforce_price_the_reforge_is_dropped_and_the_chaos_orb_policy_is_returned",
    "tests/test_cli_roll_real.py::*",
    "tests/test_cli_routes_real.py::*[[]R05[]]",
    "tests/test_cli_routes_real.py::*[[]R10[]]",
    "tests/test_cli_routes_real.py::*[[]R11[]]",
    "tests/test_measure_actions_key.py::test_a_small_real_route_is_measured_in_each_variant[[]removed[]]",
    "tests/test_naive_crafter_routes.py::*[[]R12[]]",
    "tests/test_packed_plan_real.py::*[[]R10[]]",
    "tests/test_planner_declared_bounds.py::*",  # R05 past the net; R12 also counts the sets in the winning round's offers (#1103)
    "tests/test_prune_bound.py::*[[]r05-strength-ring[]]",
    "tests/test_prune_bound.py::*[[]r10-fractured-boots[]]",
    "tests/test_prune_bound.py::*[[]r11-reservation-helmet[]]",
    "tests/test_prune_equal.py::test_r10_*",
)
RERECORD_FOR_1101 = ("tests/test_risk_unchanged_349.py::test_the_risk_reports_of_policies_without_a_free_action_are_the_ones_main_gave",)


def _mark_waits_for_1101(items) -> None:
    from fnmatch import fnmatchcase

    waits = pytest.mark.xfail(run=False, reason="#1101: a real route with every beta method on waits for the run counted in states")
    rerecord = pytest.mark.xfail(strict=True, raises=AssertionError, reason="#1101: the golden moves with every beta method on and waits for its re-record")
    for item in items:
        if any(fnmatchcase(item.nodeid, pattern) for pattern in WAITS_FOR_1101):
            item.add_marker(waits)
        elif any(fnmatchcase(item.nodeid, pattern) for pattern in RERECORD_FOR_1101):
            item.add_marker(rerecord)


def pytest_collection_modifyitems(config, items):
    _mark_waits_for_1101(items)
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
