"""A finished plan saved to a file and read back, so that its route page can be rendered again without planning again (#1442).

A heavy plan takes an hour to make; a change to the page's code is checked against it in minutes when the plan is kept. The
file is a pickle of the plan and its target with two exceptions, which are what kept a plain pickle from working:

- the game data is not written: it is the shared export the reader loads anyway, so the file names it and `load_plan` puts
  the reader's own `GameData` back in its place;
- a function made inside another (a closure, such as the abstraction's per-context profile) is written as its code, its
  defaults and the values it closes over, and is rebuilt from those.

The file is for the same code and Python that wrote it: a plan written by another version of the planner may not load, and
nothing reads it but the page tools. It is not a format for users, and never one read from a user: reading a pickle runs code. The file
holds the game data's version and size and the reader refuses a plan made on other data.

The recursion limit is raised to 100,000 while a plan is written or read: a stack setting for the depth of the plan's graph of objects,
not a limit of the planner (OR-12). A function that closes over itself is not supported (its cells are written before it exists).
"""

from __future__ import annotations

import marshal
import pickle
import sys
import types
from pathlib import Path
from typing import Any, NamedTuple

from ..data import GameData

GAME_DATA = "game-data"


class PlanFileError(ValueError):
    """A saved plan that cannot be read: truncated, written by other code, or planned on other game data."""


def _identity(data: GameData) -> str:
    """What names the game data a plan was made on: its pinned version and its counts of mods and bases."""
    return f"{data.version}, {len(data.mods)} mods, {len(data.base_items)} bases"


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

    def persistent_id(self, obj: Any) -> str | None:
        return GAME_DATA if obj is self._data or isinstance(obj, GameData) else None

    def reducer_override(self, obj: Any):
        if type(obj) is types.FunctionType and "<locals>" in obj.__qualname__:
            cells = tuple(cell.cell_contents for cell in obj.__closure__) if obj.__closure__ else ()
            return _rebuilt_function, (
                marshal.dumps(obj.__code__), obj.__module__, obj.__name__, obj.__qualname__,
                obj.__defaults__, obj.__kwdefaults__, cells,
            )  # fmt: skip
        return NotImplemented


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
        part = path.with_name(path.name + ".part")  # a save that fails or is stopped leaves no file that reads as a plan
        try:
            with part.open("wb") as file:
                _Writer(file, data).dump((_identity(data), *SavedPlan(plan, target, target_name)))
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
    finally:
        sys.setrecursionlimit(limit)
    return path


def load_plan(path: Path, data: GameData) -> SavedPlan:
    """The plan, target and target name `save_plan` wrote to `path`, read against `data` (the same game data they were planned on)."""
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 100_000))
    try:
        with path.open("rb") as file:
            try:
                identity, *fields = _Reader(file, data).load()
            except Exception as error:  # truncated, or written by other code: whatever the unpickler raises
                raise PlanFileError(f"{path} is not a plan this code can read ({error!r})") from error
    finally:
        sys.setrecursionlimit(limit)
    if identity != _identity(data):
        raise PlanFileError(f"{path} was planned on other game data ({identity}) than this one ({_identity(data)})")
    return SavedPlan(*fields)
