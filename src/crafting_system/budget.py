"""One budget of time and memory for a whole plan, and one list of what bound (ticket #825; OR-12, OR-13, OR-32, OR-33).

A run of the planner is one `Budget`: the time it aims at (`aim_seconds`, about a minute: the point after which the exact proof gives way to the
stop at a proved 1%, OR-32), and a stop-and-say-so net of time and memory (`seconds`, `memory_mb`; OR-33's 10 minutes until every method family
has its bound). The figures are named settings (`AIM_SECONDS`, `NET_SECONDS`, `MEMORY_SHARE`), never route constants; the user sets them in the
planner settings or on the command line (#537).

**One clock.** `Budget.start()` gives the `Clock` of the run. Every stage reads the same clock: the search (a `Net` made from what is left,
`Clock.left`), the walks of the whole graph and the bound pruning (`checkpoint`, between two states), the Lock's check, the risk's attempt runs (the
time left, #745), the start options (one clock across them). No stage has a fixed share. The stages that make the answer (the walks, the bound
pruning, the search) may take the whole net: until a plan closes there is nothing to show. The stages that refine an answer already in hand (the
Lock's check, the percentiles, which OR-34 adds after the route) take what is left, and when nothing is left they say so and the answer is kept
(the plan without the Lock; the percentiles of a coarser step, or of the slower method). Inside the search, the bound's build takes what it
needs by its own measure (`cli._envelope_plan.build_stop`): it stops when the time left would no longer hold two of its largest pieces of work so
far, one for its own next step and one for a round of the search after it.

**What bound.** A stage that a limit stopped records it on the clock (`Clock.bind`), with the stage, the limit and its figures; the plan lists
them all in one limit of its answer (`cli._limits.budget_limit`, #378). A stop never passes silently (OR-12): a stage either finishes, or stops at a
point the answer states (OR-13).

**Where the clock is.** `running(clock)` makes it the run's clock for a block (`active()`), so a check deep in a walk needs no argument passed down
through every layer, and a plan inside another (a start option, a reading of a rule axis) shares the run's clock instead of starting its own. A
`checkpoint` past the net raises `BudgetExceeded`, which is a `BaseException`: the stage's own `except Exception` (a pool that fell back to a
serial run, a refused offer) must not swallow the stop and run on.

**Memory.** `process_mb` reads the resident memory of a process on Linux (`/proc`), Windows (`GetProcessMemoryInfo`, the working set) and macOS
(`proc_pidinfo`, the resident size) (#540); `physical_mb` the machine's memory, of which the default memory net is `MEMORY_SHARE`.
"""

import contextlib
import contextvars
import ctypes
import math
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

AIM_SECONDS = 60.0  # OR-32, OR-33: a plan aims at about a minute; past it the exact proof gives way to the stop at a proved 1% (#826)
NET_SECONDS = 600.0  # OR-33: the stop-and-say-so net of a plan, until every method family has its bound (#822, ticket 4)
MEMORY_SHARE = 0.8  # the default memory net: this share of the machine's physical memory (a runner of 16 GB stops at 12.8 GB, before it is killed)
MEMORY_POLL_SECONDS = 0.5  # a checkpoint reads the memory at most this often (the clock it reads every time)

NO_PLAN = "no plan found yet"  # what a stop leaves when the stage had no plan to keep (OR-33)

TIME = "time"
MEMORY = "memory"
STATES = "states"


@dataclass(frozen=True)
class Budget:
    """The time and memory one run may take (see the module text). None for a figure means no limit of that kind.

    `aim_seconds` is what the plan aims at (the forecast of `_decide` reads it, and #826's stop at a proved 1%); `seconds` and `memory_mb` are the
    net that stops the run and says so; `states` is a net on the states the envelope search knows (for tests and measurements).
    """

    aim_seconds: float | None = AIM_SECONDS
    seconds: float | None = NET_SECONDS
    memory_mb: float | None = None
    states: int | None = None

    def __post_init__(self) -> None:
        for name in ("aim_seconds", "seconds", "memory_mb"):
            value = getattr(self, name)
            if value is not None and not (value >= 0 and math.isfinite(value)):
                raise ValueError(f"the budget's {name} must be a number, zero or more, or None for no limit; got {value!r}")

    @classmethod
    def unlimited(cls) -> "Budget":
        """No aim and no net: every stage runs to its end (a library call, a measurement, a test of the exact answer)."""
        return cls(None, None, None, None)

    @classmethod
    def default(cls) -> "Budget":
        """OR-33's budget: about a minute aimed at, a net of 10 minutes, and `MEMORY_SHARE` of the machine's memory (none where it cannot be read)."""
        return cls(AIM_SECONDS, NET_SECONDS, default_memory_mb())

    def start(self) -> "Clock":
        return Clock(self)


def default_memory_mb() -> float | None:
    """`MEMORY_SHARE` of the machine's physical memory, in MB, or None where the machine does not say."""
    total = physical_mb()
    return None if total is None else MEMORY_SHARE * total


@dataclass(frozen=True)
class Binding:
    """A limit that stopped a stage: which stage, which limit (`TIME`, `MEMORY`, `STATES`), its figure and what was reached when it stopped.

    `what` says in words what the stage gave up or kept (OR-13), e.g. "no plan found yet" or "the coarser step was kept"."""

    stage: str
    limit: str
    given: float
    reached: float
    what: str = ""

    def words(self) -> str:
        """The binding in a player's words: "the search stopped at the time limit of 600 s (601 s spent): no plan found yet"."""
        if self.limit == TIME and self.reached < self.given:  # a stage that stopped early to leave room for what follows it (the bound's build)
            figure = f"{self.given - self.reached:,.0f} s before the time limit of {self.given:,.0f} s, to leave room for what follows ({self.reached:,.0f} s spent)"
        elif self.limit == TIME:
            figure = f"the time limit of {self.given:,.0f} s ({self.reached:,.0f} s spent)"
        elif self.limit == MEMORY:
            figure = f"the memory limit of {self.given:,.0f} MB ({self.reached:,.0f} MB held)"
        else:
            figure = f"the limit of {self.given:,.0f} {self.limit} ({self.reached:,.0f} reached)"
        early = self.limit == TIME and self.reached < self.given
        return f"{self.stage} stopped {'' if early else 'at '}{figure}" + (f": {self.what}" if self.what else "")


class BudgetExceeded(BaseException):
    """A checkpoint past the net: the stage stops at once. A `BaseException`, so that no `except Exception` of a stage runs on past it."""

    def __init__(self, binding: Binding) -> None:
        super().__init__(binding.words())
        self.binding = binding

    def __reduce__(self):  # a pool worker that meets the net hands the stop back to its parent, which unpickles it
        return (BudgetExceeded, (self.binding,))


@dataclass
class Clock:
    """The clock of one run: when it began, what it may take, and the limits that bound (`bindings`, in the order they bound)."""

    budget: Budget
    began: float = field(default_factory=lambda: time.perf_counter())
    bindings: list[Binding] = field(default_factory=list)
    stage: str = "the plan"  # the stage running now (`stage`), named in a binding a checkpoint meets
    what: str = NO_PLAN  # what a stop of that stage leaves, as the answer says it (OR-13)
    stops: bool = True  # whether a checkpoint stops the stage; False for a stage that stops itself at its own net and keeps what it found (the search)
    _memory_read: float = field(default=-math.inf, repr=False)
    _memory: float | None = field(default=None, repr=False)

    def elapsed(self) -> float:
        return time.perf_counter() - self.began

    def left(self) -> float | None:
        """The seconds left to the net, never below 0; None with no time net."""
        given: Budget = self.budget
        if given.seconds is None:
            return None
        return max(given.seconds - self.elapsed(), 0.0)

    def memory(self, fresh: bool = False) -> float | None:
        """The memory this process holds, in MB, read at most every `MEMORY_POLL_SECONDS` unless `fresh`."""
        now = time.perf_counter()
        if fresh or now - self._memory_read >= MEMORY_POLL_SECONDS:
            self._memory, self._memory_read = process_mb(), now
        return self._memory

    def over(self, stage: str, what: str = "", held: float | None = None) -> Binding | None:
        """The binding a stage meets now, if the time or the memory net is reached; nothing is recorded (`bind` does that).

        `held` is the memory to compare with the net when the caller read it itself (a pool: this process and its workers); else this process's."""
        given: Budget = self.budget
        seconds = given.seconds
        if seconds is not None:
            spent = self.elapsed()
            if spent >= seconds:
                return Binding(stage, TIME, seconds, spent, what)
        if given.memory_mb is not None:
            if held is None:
                held = self.memory()
            if held is not None and held >= given.memory_mb:
                return Binding(stage, MEMORY, given.memory_mb, held, what)
        return None

    def bind(self, binding: Binding) -> Binding:
        """Record that `binding` stopped its stage (once: a stop seen again by an outer stage is not listed twice)."""
        if binding not in self.bindings:
            self.bindings.append(binding)
        return binding

    def check(self, stage: str, what: str = "") -> None:
        """Raise `BudgetExceeded` (and record the binding) when the net is reached; otherwise nothing."""
        found = self.over(stage, what)
        if found is not None:
            raise BudgetExceeded(self.bind(found))


_active: contextvars.ContextVar[Clock | None] = contextvars.ContextVar("crafting_system_budget_clock", default=None)  # per thread and task: two plans at once (the website service) each have their own


def active() -> Clock | None:
    """The clock of the run in progress, or None outside one (a library call with no budget)."""
    return _active.get()


@contextlib.contextmanager
def running(clock: Clock | None) -> Iterator[Clock | None]:
    """Make `clock` the run's clock for the block; a block inside a run that already has one keeps the run's (one clock per run)."""
    outer = _active.get()
    if outer is not None or clock is None:
        yield outer
        return
    token = _active.set(clock)
    try:
        yield clock
    finally:
        _active.reset(token)


def checkpoint() -> None:
    """Stop the running stage (`BudgetExceeded`) when the run's net is reached; nothing outside a run. Cheap enough for every state of a walk:
    it reads the clock every time and the memory at most every `MEMORY_POLL_SECONDS`."""
    clock = _active.get()
    if clock is not None and clock.stops:
        clock.check(clock.stage, clock.what)


@contextlib.contextmanager
def stage(name: str, what: str = NO_PLAN, *, stops: bool = True) -> Iterator[Clock | None]:
    """Name the stage that runs in the block and what a stop inside it leaves (a binding met there says both); nothing outside a run.

    With `stops` False the checkpoints inside the block do nothing: the stage is given the net (`Clock.left`) and stops itself between two of its
    rounds, keeping the best it found (the envelope search), where a checkpoint deep inside a round would throw that away."""
    clock = _active.get()
    if clock is None:
        yield None
        return
    saved = clock.stage, clock.what, clock.stops
    clock.stage, clock.what, clock.stops = name, what, stops
    try:
        yield clock
    finally:
        clock.stage, clock.what, clock.stops = saved


# ---- memory --------------------------------------------------------------------------------------------------------------------------


def process_mb(pid: int | None = None) -> float | None:
    """The resident memory of a process (this one when `pid` is None) in MB, or None where it cannot be read (#540).

    Linux: `VmRSS` of the status file of the process under proc. Windows: the working set (`GetProcessMemoryInfo`). macOS: the resident size (`proc_pidinfo`). These are
    the memory the process holds now, not its peak, so a net read twice sees it fall as well as rise.
    """
    if sys.platform == "win32":
        return _windows_mb(pid)
    found = _proc_mb(pid)
    if found is not None:
        return found
    if sys.platform == "darwin":
        return _darwin_mb(pid)
    return None


def _proc_mb(pid: int | None) -> float | None:
    try:
        with open(os.path.join(os.sep, "proc", "self" if pid is None else str(pid), "status"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (OSError, ValueError):
        pass
    return None


class _Counters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_QUERY = 0x1000 | 0x0010  # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ


def _windows_mb(pid: int | None) -> float | None:
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Counters), ctypes.c_uint32]
        handle = kernel.GetCurrentProcess() if pid is None else kernel.OpenProcess(_QUERY, 0, pid)
        if not handle:
            return None
        try:
            counters = _Counters()
            counters.cb = ctypes.sizeof(_Counters)
            if not kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return None
            return counters.WorkingSetSize / (1024 * 1024)
        finally:
            if pid is not None:
                kernel.CloseHandle(handle)
    except (AttributeError, OSError):
        return None


class _TaskInfo(ctypes.Structure):  # struct proc_taskinfo of <sys/proc_info.h>
    _fields_ = [
        ("virtual_size", ctypes.c_uint64),
        ("resident_size", ctypes.c_uint64),
        ("total_user", ctypes.c_uint64),
        ("total_system", ctypes.c_uint64),
        ("threads_user", ctypes.c_uint64),
        ("threads_system", ctypes.c_uint64),
        ("policy", ctypes.c_int32),
        ("faults", ctypes.c_int32),
        ("pageins", ctypes.c_int32),
        ("cow_faults", ctypes.c_int32),
        ("messages_sent", ctypes.c_int32),
        ("messages_received", ctypes.c_int32),
        ("syscalls_mach", ctypes.c_int32),
        ("syscalls_unix", ctypes.c_int32),
        ("csw", ctypes.c_int32),
        ("threadnum", ctypes.c_int32),
        ("numrunning", ctypes.c_int32),
        ("priority", ctypes.c_int32),
    ]


def _darwin_mb(pid: int | None) -> float | None:
    try:
        libproc = ctypes.CDLL(os.path.join(os.sep, "usr", "lib", "libproc.dylib"))
        info = _TaskInfo()
        size = ctypes.sizeof(info)
        if libproc.proc_pidinfo(os.getpid() if pid is None else pid, 4, ctypes.c_uint64(0), ctypes.byref(info), size) != size:  # PROC_PIDTASKINFO
            return None
        return info.resident_size / (1024 * 1024)
    except (AttributeError, OSError):
        return None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def physical_mb() -> float | None:
    """The machine's physical memory in MB, or None where it cannot be read; on Linux no more than the limit of the process's container (cgroup)."""
    if sys.platform == "win32":
        try:
            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                return status.ullTotalPhys / (1024 * 1024)
        except (AttributeError, OSError):
            pass
        return None
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 * 1024)
    except (AttributeError, OSError, ValueError):
        return None
    limit = _cgroup_mb()
    return total if limit is None else min(total, limit)


CGROUP_FILES = (
    os.path.join(os.sep, "sys", "fs", "cgroup", "memory.max"),
    os.path.join(os.sep, "sys", "fs", "cgroup", "memory", "memory.limit_in_bytes"),
)  # cgroup v2, then v1


def _cgroup_mb() -> float | None:
    """The memory limit of the container this process runs in, in MB, or None when it has none (`max`) or there is no such file."""
    for path in CGROUP_FILES:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read().strip()
        except OSError:
            continue
        if text.isdigit():
            return int(text) / (1024 * 1024)
        return None
    return None
