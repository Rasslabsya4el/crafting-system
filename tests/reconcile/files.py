"""The target, the buy spec and the price entry, read as written (YAML and JSON, standard library and `yaml`).

Formats (learned from `src/crafting_system/targets/` and `.../prices/`, not imported):

- target: `base`, `item_level`, `influence`, `start` (`bought` or `given`, #505), `start_item` (`rarity`, `mods`: `mod`, `tier`,
  `values`, `fractured`), `price_file`. A target without `start_item` starts from a normal item; a `start_item` without `rarity` is
  rare when it lists mods, else normal. A target file no longer names its price (#474): `start_price` is the price key of the
  start item, taken from the hand-written table `expected_keys.txt` by the target's file stem (`read_expected_keys`). A bought
  start item has a row in it, a given one has none (J01).
- buy spec: `name`, `base_type`, `category`, `rarity`, `item_level_min`, `influence`, `mods` (`stat`, `minimum`,
  `fractured`). The planner computes it from the target; `derived_specs/<target>.yaml` is that result written down
  (`tests/test_start_buy_real.py` holds the folder equal to it), so the reconciliation can read it without importing the
  planner and checks it against the target, the game data and the price entry.
- price file: `prices` by name; an entry made from a trade search holds its query in `detail.query`.
"""

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from .export import REPO_ROOT

TARGETS_DIR = REPO_ROOT / "examples" / "targets"
BUY_DIR = REPO_ROOT / "tests" / "reconcile" / "derived_specs"
KEYS_FILE = REPO_ROOT / "tests" / "reconcile" / "expected_keys.txt"
PRICES_DIR = REPO_ROOT / "tests" / "fixtures" / "prices"


class FileFormatError(Exception):
    """A file does not have the shape this package reads; the message names the file and the key."""


@dataclass(frozen=True)
class StartMod:
    mod: str
    tier: int | None
    values: tuple
    fractured: bool


@dataclass(frozen=True)
class Target:
    name: str  # the file stem
    path: Path
    base: str  # as written: an English name or a base id
    item_level: int
    influence: frozenset
    rarity: str  # the rarity of the start item
    start_mods: tuple[StartMod, ...]
    start_price: str | None
    price_file: Path | None
    start: str | None = None  # "bought" or "given" as the file says it; None when the file does not say (the planner refuses such a file)


@dataclass(frozen=True)
class BuyMod:
    stat: str
    minimum: float | None
    fractured: bool
    own: bool = False  # the base's own implicit: it tells bases of one name apart, it is not a bought mod


@dataclass(frozen=True)
class BuySpec:
    name: str
    path: Path
    base_type: str | None
    category: str | None
    rarity: str | None
    item_level_min: int | None
    influence: frozenset
    mods: tuple[BuyMod, ...]


@dataclass(frozen=True)
class PriceEntry:
    file: Path
    key: str
    chaos: float | None
    source: str | None
    note: str = ""
    query: dict = field(default_factory=dict)  # the trade query, {} when the entry was not made from one


def _mapping(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise FileFormatError(f"{path.name}: the top level is not a mapping")
    return document


def read_target(path: Path) -> Target:
    document = _mapping(path)
    for key in ("base", "item_level"):
        if key not in document:
            raise FileFormatError(f"{path.name}: no `{key}`")
    start = document.get("start_item")
    mods = ()
    rarity = "normal"
    if isinstance(start, dict):
        mods = tuple(
            StartMod(
                mod=entry["mod"],
                tier=entry.get("tier"),
                values=tuple(entry.get("values") or ()),
                fractured=bool(entry.get("fractured", False)),
            )
            for entry in (start.get("mods") or ())
        )
        rarity = start.get("rarity") or ("rare" if mods else "normal")
    price_file = document.get("price_file")
    return Target(
        name=path.stem,
        path=path,
        base=document["base"],
        item_level=document["item_level"],
        influence=frozenset(document.get("influence") or ()),
        rarity=rarity,
        start_mods=mods,
        start_price=document.get("start_price"),
        price_file=(path.parent / price_file).resolve() if price_file else None,
        start=str(document["start"]).strip().lower() if "start" in document else None,
    )


def read_buy_spec(path: Path) -> BuySpec:
    document = _mapping(path)
    if "name" not in document:
        raise FileFormatError(f"{path.name}: no `name`")
    return BuySpec(
        name=document["name"],
        path=path,
        base_type=document.get("base_type"),
        category=document.get("category"),
        rarity=document.get("rarity"),
        item_level_min=document.get("item_level_min"),
        influence=frozenset(document.get("influence") or ()),
        mods=tuple(
            BuyMod(stat=entry["stat"], minimum=entry.get("minimum"), fractured=bool(entry.get("fractured", False)), own=bool(entry.get("own", False)))
            for entry in (document.get("mods") or ())
        ),
    )


def read_expected_keys(path: Path = KEYS_FILE) -> dict[str, str]:
    """The price key of the start item of each bought target, by target file stem (tab-separated lines; `#` lines are comments)."""
    keys = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        stem, tab, key = line.partition("\t")
        if not tab or not stem or not key or stem in keys:
            raise FileFormatError(f"{path.name}:{number}: expected `<target stem>`, a tab and a key, once per target")
        keys[stem] = key
    return keys


def read_targets(directory: Path = TARGETS_DIR, keys: dict[str, str] | None = None) -> list[Target]:
    """The targets of a folder, each with the price key of its start item from `keys` (default: `expected_keys.txt`)."""
    table = read_expected_keys() if keys is None else keys
    return [replace(target, start_price=table.get(target.name, target.start_price)) for target in map(read_target, sorted(directory.glob("*.yaml")))]


def read_buy_specs(directory: Path = BUY_DIR) -> list[BuySpec]:
    return [read_buy_spec(path) for path in sorted(directory.glob("*.yaml"))]


def buy_spec_of(target: Target, specs: list[BuySpec]) -> BuySpec | None:
    """The buy spec whose `name` is the target's `start_price` (the one link between the two files)."""
    if target.start_price is None:
        return None
    named = [spec for spec in specs if spec.name == target.start_price]
    if len(named) > 1:
        raise FileFormatError(f"{len(named)} buy specs are named {target.start_price!r}")
    return named[0] if named else None


def price_files_of(target: Target, directory: Path = PRICES_DIR) -> list[Path]:
    """The committed price files that hold the target's `start_price` key.

    The target's own `price_file:` when it names one (that file only); else every file of the price
    folder that holds the key.
    """
    if target.start_price is None:
        return []
    if target.price_file is not None:
        return [target.price_file] if target.price_file.is_file() else []
    found = []
    for path in sorted(directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if target.start_price in document.get("prices", {}):
            found.append(path)
    return found


def read_price_entry(path: Path, key: str) -> PriceEntry | None:
    document = json.loads(path.read_text(encoding="utf-8"))
    raw = document.get("prices", {}).get(key)
    if raw is None:
        return None
    detail = raw.get("detail") or {}
    query = (detail.get("query") or {}).get("query") or {}
    return PriceEntry(file=path, key=key, chaos=raw.get("chaos"), source=raw.get("source"), note=raw.get("note") or "", query=query)


_KEY_BASE = re.compile(r"^(?P<base>.+?)(?: \[[^\]]*\])?, (?:(?:normal|magic|rare), )?item level (?P<ilvl>\d+)")


def priced_base_name(entry: PriceEntry) -> str | None:
    """The base name the price was taken for: the trade query's `type`, else the name in the key (`Lion Pelt, normal, item level 84`).

    A base id in brackets after the name (`Two-Toned Boots [BootsAtlas1]`) is a label of the key, not a fact about the price: a
    poe.ninja line and a trade search are both by name, so it is left out here.
    """
    typed = entry.query.get("type")
    if typed:
        return typed
    if entry.query:
        return None  # a search with no base type prices every base of its category, whatever the key says
    match = _KEY_BASE.match(entry.key)
    return match.group("base") if match else None


def priced_rarity(entry: PriceEntry) -> str | None:
    """The rarity of the entry's trade query, or None when it has none (a poe.ninja or hand line is a price of a normal base)."""
    filters = ((entry.query.get("filters") or {}).get("type_filters") or {}).get("filters") or {}
    return (filters.get("rarity") or {}).get("option")


def priced_category(entry: PriceEntry) -> str | None:
    """The trade category of the entry's query, when it has one."""
    filters = ((entry.query.get("filters") or {}).get("type_filters") or {}).get("filters") or {}
    return (filters.get("category") or {}).get("option")


_NOTE_LEVELS = (re.compile(r"\(item level (\d+)"), re.compile(r"\bof item level (\d+)(?! or more)"))


def priced_item_level(entry: PriceEntry) -> tuple[int | None, str]:
    """The item level the price was taken for, and where that is recorded: (level, "query" | "note" | "label").

    "query": the trade query's `ilvl.min`. "note": the line the price was read from, as the entry's note
    records it (a poe.ninja line has its own level, which can be above the one in the key). "label": only
    the `item level N` in the key, which is a name, not a record; the check cannot tell from it. (None, "") when the
    entry has no level at all.
    """
    filters = ((entry.query.get("filters") or {}).get("misc_filters") or {}).get("filters") or {}
    minimum = (filters.get("ilvl") or {}).get("min")
    if minimum is not None:
        return minimum, "query"
    for pattern in _NOTE_LEVELS:
        found = pattern.search(entry.note)
        if found:
            return int(found.group(1)), "note"
    match = re.search(r"\bitem level (\d+)", entry.key)
    return (int(match.group(1)), "label") if match else (None, "")
