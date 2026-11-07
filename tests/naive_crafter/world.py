"""What the naive crafter reads: the export, the target file, the price file, and the actions a route names (ticket #555).

Everything here is read from files as plain data. The target file gives the base, the item level, the influences, the requirements (the
goal oracle `tests/oracle/goal_oracle.py` reads them and judges mods: it imports nothing of the planner either) and the start item. The price
file gives the chaos price of each currency, essence and start item by name (`prices[name].chaos`); the price of a bought start item is
under the key that `tests/reconcile/expected_keys.txt` holds for the target, which is written by hand and read here as text.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from independent import export as shared_export
from oracle import goal_oracle as g

from .craft import Crafter, Held, Item, Laws, Unsupported

ORBS = {
    "Orb of Transmutation": "transmutation",
    "Orb of Alteration": "alteration",
    "Orb of Augmentation": "augmentation",
    "Regal Orb": "regal",
    "Chaos Orb": "chaos",
}
BENCH = "Bench craft "
RESTART = "restart"

# What a route names that this player cannot do yet, by the start of the action's label: the mechanic it lacks.
LACKING = (
    ("Exalted Orb", "Exalted Orb: adds one mod to a rare item"),
    ("Orb of Annulment", "Orb of Annulment: removes a random mod"),
    ("Fracturing Orb", "Fracturing Orb: fractures a random mod"),
    ("Fossils ", "fossils: they change the weights of the pool"),
    ("Harvest ", "Harvest reforge: a reroll that keeps one mod type"),
    ("Remove Crafted Mods", "Remove Crafted Mods: the bench step that clears the crafted mods"),
    ("Essence of ", "an essence that is not in the export's record of essences by that name (a corrupted or unnamed tier)"),
)
METAMOD_GROUP = "ItemGeneration"  # the groups of the five metamods in the export (Cannot roll Attack Modifiers, Prefixes Cannot Be Changed, ...)
LACKING_METAMODS = "metamods: a bench craft that changes what later orbs do (Cannot roll Attack Modifiers, Can have up to 3 Crafted Modifiers)"


class UnpricedError(Exception):
    """A name the route spends that the price file has no price for."""


@dataclass(frozen=True)
class Priced:
    """An action of a route: its label, its kind, what one use costs in chaos, and what the kind needs (an essence record, a crafted mod id)."""

    label: str
    kind: str
    cost: float
    record: dict | None = None
    mod_id: str | None = None


def read_keys(path: Path) -> dict[str, str]:
    """The price key of the start item of each bought target, by target file stem (`tests/reconcile/expected_keys.txt`)."""
    keys = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            stem, _, key = line.partition("\t")
            keys[stem] = key
    return keys


class World:
    def __init__(self, raw: shared_export.RawExport, target_text: str, price_document: dict, start_key: str | None, laws: Laws | None = None):
        self.raw = raw
        self.export = g.Export.from_raw(raw)
        self.target = g.OracleTarget.from_text(target_text)
        if self.target.implicits or self.target.quality is not None or self.target.unjudged:
            raise Unsupported(f"the target asks for implicits, quality or {list(self.target.unjudged)}, which the goal oracle does not judge")
        self.oracle = g.Oracle(self.export, self.target)
        self.document = yaml.safe_load(target_text)
        self.crafter = Crafter(raw, self.oracle.base_id, self.target.item_level, sorted(self.target.influences), laws)
        self.prices = {name: entry["chaos"] for name, entry in price_document["prices"].items()}
        self.start_key = start_key
        self.bought = self.document.get("start") == "bought"
        self.start_item = self._start_item()
        self._actions: dict[str, Priced] = {}

    # -- the start item ---------------------------------------------------------------------------------------

    def _start_item(self) -> Item:
        """The start item of the target file: its rarity (rare when it lists mods, else normal) and its mods with their values."""
        block = self.document.get("start_item") or {}
        entries = block.get("mods") or []
        rarity = block.get("rarity") or ("rare" if entries else "normal")
        mods = []
        for entry in entries:
            if "values" not in entry:
                raise Unsupported(f"the start mod {entry.get('mod')} gives no values")
            mods.append(Held(entry["mod"], tuple(entry["values"]), fractured=bool(entry.get("fractured", False))))
        return Item(rarity, tuple(mods))

    @property
    def start_price(self) -> float:
        """What buying the start item again costs; a given start item is never bought again."""
        if not self.bought:
            raise Unsupported("the start item is given, so a route cannot restart")
        if self.start_key is None or self.start_key not in self.prices:
            raise UnpricedError(f"the price file has no price for the start item {self.start_key!r}")
        return self.prices[self.start_key]

    # -- the actions ------------------------------------------------------------------------------------------

    def price(self, name: str) -> float:
        if name not in self.prices:
            raise UnpricedError(f"the price file has no price for {name!r}")
        return self.prices[name]

    def action(self, label: str) -> Priced:
        if label not in self._actions:
            self._actions[label] = self._resolve(label)
        return self._actions[label]

    def _resolve(self, label: str) -> Priced:
        if label == RESTART:
            return Priced(label, "restart", self.start_price)
        if label in ORBS:
            return Priced(label, ORBS[label], self.price(label))
        record = self._essence(label)
        if record is not None:
            return Priced(label, "essence", self.price(label), record=record)
        if label.startswith(BENCH):
            return self._bench(label, label[len(BENCH):])
        for start, mechanic in LACKING:
            if label.startswith(start):
                raise Unsupported(f"{label!r}: this player lacks {mechanic}")
        raise Unsupported(f"{label!r}: this player does not know this action")

    def _essence(self, label: str) -> dict | None:
        found = [record for record in self.raw.essences.values() if record.get("name") == label]
        if len(found) > 1:
            raise Unsupported(f"{label!r}: {len(found)} essence records have this name")
        return found[0] if found else None

    def _bench(self, label: str, text: str) -> Priced:
        """The bench option of the item's class whose crafted mod reads `text`; its cost is the sum of its currencies at their prices."""
        found = []
        for option in self.raw.bench_options:
            mod_id = (option.get("actions") or {}).get("add_explicit_mod")
            if mod_id and self.export.item_class(self.oracle.base_id) in option.get("item_classes", []) and self.raw.mods[mod_id]["text"] == text:
                found.append((option, mod_id))
        if not found:
            raise Unsupported(f"{label!r}: no bench option of the base's class adds a mod with this text")
        if len(found) > 1:
            raise Unsupported(f"{label!r}: {len(found)} bench options add a mod with this text")
        option, mod_id = found[0]
        if any(group.startswith(METAMOD_GROUP) for group in self.raw.mods[mod_id].get("groups") or ()):
            raise Unsupported(f"{label!r}: this player lacks {LACKING_METAMODS}")
        cost = 0.0
        for currency, count in option["cost"].items():
            cost += count * self.price(self.raw.bases[currency]["name"])
        return Priced(label, "bench", cost, mod_id=mod_id)


def load_world(
    target_path: Path, prices_path: Path, keys_path: Path | None, root: Path | None = None, laws: Laws | None = None, pin_file: Path | None = shared_export.PIN_FILE
) -> World:
    """The world of a target file, a price file and the hand-written table of start price keys, on the export of the cache dir."""
    raw = shared_export.load_export(root, pin_file)
    keys = read_keys(keys_path) if keys_path is not None else {}
    return World(
        raw,
        target_path.read_text(encoding="utf-8"),
        json.loads(prices_path.read_text(encoding="utf-8")),
        keys.get(target_path.stem),
        laws,
    )
