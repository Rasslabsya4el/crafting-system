"""A finished plan saved to a file and read back, so that its route page can be rendered again without planning again (#1442).

A heavy plan takes an hour to make; a change to the page's code is checked against it in minutes when the plan is kept. The
file is a pickle of the plan and its target with two exceptions, which are what kept a plain pickle from working:

- the game data is not written: it is the shared export the reader loads anyway, so the file names it and `load_plan` puts
  the reader's own `GameData` back in its place;
- a function made inside another (a closure, such as the abstraction's per-context profile) is written as its code, its
  defaults and the values it closes over, and is rebuilt from those.

The file is for the same Python and the same plan-making code that wrote it, and nothing reads it but the page tools. It is not a format
for users, and never one read from a user: reading a pickle runs code. Before the plan, the file holds a header of plain values: the
Python that wrote it, the game data's version and size, and a hash of the source of every module of this package whose classes or
functions the plan holds (the abstraction, the planner, ...: whatever the writer met). The reader checks the header before it reads the
plan and refuses, in words, a plan of another Python (its closures are bytecode), of other game data, or of changed plan-making code (a
pickled object of an old class takes its old fields, a rebuilt closure runs its old code). The page's own modules are not in the plan, so
a change of the page's code still draws an old plan again: that is what the file is for.

The recursion limit is raised to 100,000 while a plan is written or read: a stack setting for the depth of the plan's graph of objects,
not a limit of the planner (OR-12). A function that closes over itself is not supported (its cells are written before it exists).
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import marshal
import os
import pickle
import sys
import types
import uuid
from pathlib import Path
from typing import Any, NamedTuple

from ..data import GameData

GAME_DATA = "game-data"
MAGIC = "crafting-system saved plan, format 2"
PACKAGE = "crafting_system"


class PlanFileError(ValueError):
    """A saved plan that cannot be read: truncated, written by other code, or planned on other game data."""


def _identity(data: GameData) -> str:
    """What names the game data a plan was made on: its pinned version and its counts of mods and bases."""
    return f"{data.version}, {len(data.mods)} mods, {len(data.base_items)} bases"


def _python() -> tuple:
    """The Python a plan file is written by: its closures are written as this Python's bytecode."""
    return (sys.implementation.name, *sys.version_info[:3])


def _python_words(python) -> str:
    """A Python of `_python` in words, as "cpython 3.14.10"."""
    name, *version = python
    return f"{name} {'.'.join(map(str, version))}"


def _source_hash(module: str) -> str | None:
    """A hash of a module's source file (its line endings made alike), or None when the module is gone."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None or not os.path.isfile(spec.origin):
        return None
    return hashlib.sha256(Path(spec.origin).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _code_stamp(modules) -> dict[str, str | None]:
    """The hash of the source of each module named, by name: the plan-making code a plan file was written by."""
    return {module: _source_hash(module) for module in sorted(modules)}


def _rebuilt_function(code: bytes, module: str, name: str, qualname: str, defaults, kwdefaults, cells: tuple) -> types.FunctionType:
    """A function written by `_Writer.reducer_override`, made again with its module's globals and new cells of its values."""
    globals_ = vars(sys.modules[module]) if module in sys.modules else vars(__import__(module, fromlist=["_"]))
    closure = tuple(types.CellType(value) for value in cells) if cells else None
    function = types.FunctionType(marshal.loads(code), globals_, name, defaults, closure)
    function.__kwdefaults__ = kwdefaults
    function.__qualname__ = qualname
    return function


class _Writer(pickle.Pickler):
    def __init__(self, file, data: GameData) -> None:
        super().__init__(file, protocol=pickle.HIGHEST_PROTOCOL)
        self._data = data
        self.modules: set[str] = set()  # the modules of this package whose classes or functions the plan holds

    def persistent_id(self, obj: Any) -> str | None:
        return GAME_DATA if obj is self._data or isinstance(obj, GameData) else None

    def reducer_override(self, obj: Any):
        if isinstance(obj, (type, types.FunctionType)):  # an instance is written with its class, which comes here too
            module = obj.__module__ or ""
            if module == PACKAGE or module.startswith(PACKAGE + "."):
                self.modules.add(module)
        if type(obj) is types.FunctionType and "<locals>" in obj.__qualname__:
            cells = tuple(cell.cell_contents for cell in obj.__closure__) if obj.__closure__ else ()
            return _rebuilt_function, (
                marshal.dumps(obj.__code__), obj.__module__, obj.__name__, obj.__qualname__,
                obj.__defaults__, obj.__kwdefaults__, cells,
            )  # fmt: skip
        return NotImplemented


class _HeaderReader(pickle.Unpickler):
    """Reads the header: plain values only, so a file of another format or code is refused before any of it runs."""

    def find_class(self, module: str, name: str):
        raise pickle.UnpicklingError(f"the header of a saved plan names {module}.{name}")


class _Reader(pickle.Unpickler):
    def __init__(self, file, data: GameData) -> None:
        super().__init__(file)
        self._data = data

    def persistent_load(self, pid: Any) -> GameData:
        if pid != GAME_DATA:
            raise pickle.UnpicklingError(f"unknown reference in a saved plan: {pid!r}")
        return self._data


class SavedPlan(NamedTuple):
    plan: Any  # the planner's `Plan`
    target: Any  # the `Target` it was planned for
    target_name: str  # the target file's name, which the page is titled with


def save_plan(path: Path, plan: Any, target: Any, data: GameData, target_name: str = "") -> Path:
    """Write `plan` and `target` (planned on `data`) to `path` and return `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 100_000))  # a plan's graph of states is deep
    try:
        body = io.BytesIO()
        writer = _Writer(body, data)
        writer.dump(SavedPlan(plan, target, target_name))
        header = (MAGIC, _python(), _identity(data), _code_stamp(writer.modules))
        # a save that fails or is stopped leaves no file that reads as a plan; two saves to one path at once write two temp files
        part = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.part")
        try:
            with part.open("wb") as file:
                pickle.dump(header, file, protocol=pickle.HIGHEST_PROTOCOL)
                file.write(body.getbuffer())
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
    finally:
        sys.setrecursionlimit(limit)
    return path


def load_plan(path: Path, data: GameData) -> SavedPlan:
    """The plan, target and target name `save_plan` wrote to `path`, read against `data` (the same game data they were planned on)."""
    with path.open("rb") as file:
        try:
            header = _HeaderReader(file).load()
        except Exception as error:  # truncated, of the first format (no header), or of a newer pickle: whatever the unpickler raises
            raise PlanFileError(f"{path} is not a plan this code can read: an older version of --save-plan or a damaged file, plan again ({error!r})") from error
        if not (isinstance(header, tuple) and len(header) == 4 and header[0] == MAGIC and isinstance(header[3], dict)):
            raise PlanFileError(f"{path} was saved by an older version of --save-plan: plan again")
        _, python, identity, stamp = header
        if python != _python():
            raise PlanFileError(f"{path} was saved by another version of the program's interpreter ({_python_words(python)}) than this one ({_python_words(_python())}): plan again")
        if not all(isinstance(module, str) and module.startswith(PACKAGE + ".") for module in stamp):  # never look up a name read from a file outside it
            raise PlanFileError(f"{path} is not a plan this code can read: its code stamp names modules of no planner")
        if identity != _identity(data):
            raise PlanFileError(f"{path} was planned on other game data ({identity}) than this one ({_identity(data)})")
        if changed := [module for module, digest in _code_stamp(stamp).items() if digest != stamp[module]]:
            raise PlanFileError(f"{path} was planned by other code than this one ({', '.join(changed)} changed since): plan again")
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(limit, 100_000))
        try:
            return SavedPlan(*_Reader(file, data).load())
        except Exception as error:  # truncated after the header
            raise PlanFileError(f"{path} is not a plan this code can read ({error!r})") from error
        finally:
            sys.setrecursionlimit(limit)
