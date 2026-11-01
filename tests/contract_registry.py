"""What a family adds to the contract suite's fixture, by registration (ticket #334).

A family of actions that needs something of its own in the contract suite's fixture does not edit `contract_support.py`: it
puts a module `tests/contract_fixtures_<family>.py` beside its tests, and that module calls

* `register_fixture_mods(source)`: `source()` returns a dict of mods (by id) that join the fixture data (`contract_support.CONTRACT_DATA`),
  for the family whose actions name mods the fixture pool lacks; or
* `register_extra_item(name, kinds, data, item)`: an item on a base of its own, asked about for the kinds named and no other kind;
  `data()` is the game data the item lives in and `item()` builds it, both with no argument and both run late, after
  `contract_support` is loaded, so they may import it.

`load_family_fixtures()` imports every such module once, in sorted order; `contract_support` calls it before it builds its data. A
module of this kind imports this one and its own family's support code, and must not import `contract_support` at its top.
The kind itself needs nothing here: it registers in the catalog and the suite finds it. An exemption is a declaration on the kind
(`applies_only_to`, `reads_item_state_while_not_planner`, `actions/catalog.py`).
"""

import importlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtraFixture:
    """An item of its own, with the data it lives in and the names of the kinds that are asked about it."""

    kinds: tuple[str, ...]
    data: object
    item: object


@dataclass(frozen=True)
class _Spec:
    name: str
    kinds: tuple[str, ...]
    data: Callable[[], object]
    item: Callable[[], object]


_MOD_SOURCES: list[Callable[[], dict]] = []
_EXTRA: dict[str, _Spec] = {}
_LOADED: list[str] = []


def register_fixture_mods(source: Callable[[], dict]) -> None:
    """Add the mods `source()` returns to the fixture data."""
    _MOD_SOURCES.append(source)


def register_extra_item(name: str, kinds: tuple[str, ...], data: Callable[[], object], item: Callable[[], object]) -> None:
    """Ask the kinds named about the item `item()` on `data()`, as `contract_support.extra_pairs` does."""
    if name in _EXTRA:
        raise ValueError(f"the extra fixture item {name!r} is registered twice")
    _EXTRA[name] = _Spec(name, tuple(kinds), data, item)


@contextmanager
def extra_item_registered(name: str, kinds: tuple[str, ...], data: Callable[[], object], item: Callable[[], object]) -> Iterator[None]:
    """`register_extra_item` for the length of a `with` block (a test's toy family), then take it out again."""
    register_extra_item(name, kinds, data, item)
    try:
        yield
    finally:
        _EXTRA.pop(name, None)


def fixture_mods() -> dict:
    """The mods of every registered source, merged in registration order."""
    found: dict = {}
    for source in _MOD_SOURCES:
        found.update(source())
    return found


def extra_items() -> dict[str, ExtraFixture]:
    """The registered extra items by name, built."""
    return {spec.name: ExtraFixture(spec.kinds, spec.data(), spec.item()) for spec in _EXTRA.values()}


def load_family_fixtures() -> list[str]:
    """Import every `contract_fixtures_*.py` beside this file once, in sorted order; the names loaded so far."""
    for path in sorted(Path(__file__).parent.glob("contract_fixtures_*.py")):
        if path.stem not in _LOADED:
            importlib.import_module(path.stem)
            _LOADED.append(path.stem)
    return list(_LOADED)
