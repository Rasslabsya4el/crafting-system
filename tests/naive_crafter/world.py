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

from .craft import LOCKS, Crafter, Held, Item, Laws, Unsupported
from .fossils import FossilSet, read_fossils
from .rules import HARVEST_COST, HARVEST_TAGS

ORBS = {
    "Orb of Transmutation": "transmutation",
    "Orb of Alteration": "alteration",
    "Orb of Augmentation": "augmentation",
    "Regal Orb": "regal",
    "Chaos Orb": "chaos",
    "Exalted Orb": "exalted",
    "Orb of Annulment": "annulment",
    "Fracturing Orb": "fracturing",
}
BENCH = "Bench craft "
RESTART = "restart"

FOSSILS = "Fossils "  # the label of a resonator use: "Fossils Dense Fossil + Shuddering Fossil"
FOSSIL_SEPARATOR = " + "
HARVEST = "Harvest Reforge "  # "Harvest Reforge Lightning"
REMOVE_CRAFTED = "Remove Crafted Mods"
RESONATOR_SIZES = {1: "Primitive", 2: "Potent", 3: "Powerful", 4: "Prime"}  # sockets -> the resonator (rule `resonator_sockets`; the export names them DelveSocketableCurrencyReroll1 to 4)
# What a route names that this player cannot do yet, by the start of the action's label: the mechanic it lacks.
LACKING = (
    ("Harvest Reforge more", "Harvest reforge that is more or less likely to give the types the item holds"),
    ("Harvest Reforge less", "Harvest reforge that is more or less likely to give the types the item holds"),
    ("Harvest Reforge influence", "Harvest reforge of an influence modifier"),
    ("Essence of ", "an essence that is not in the export's record of essences by that name (a corrupted or unnamed tier)"),
)
LACKING_LOCKS = "metamods that lock a side (Prefixes Cannot Be Changed, Suffixes Cannot Be Changed): they protect a side from a reroll, which this player does not model"


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
    fossils: FossilSet | None = None
    tag: str | None = None


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
        self.fossil_records = read_fossils(raw.source)
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
        if label.startswith(FOSSILS):
            return self._fossils(label, tuple(label[len(FOSSILS):].split(FOSSIL_SEPARATOR)))
        if label.startswith(HARVEST) and label[len(HARVEST):].lower() in HARVEST_TAGS:
            return self._harvest(label, label[len(HARVEST):].lower())
        if label == REMOVE_CRAFTED:
            return self._remove_crafted(label)
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
        if LOCKS & set(self.raw.mods[mod_id].get("groups") or ()):
            raise Unsupported(f"{label!r}: this player lacks {LACKING_LOCKS}")
        return Priced(label, "bench", self._option_cost(option), mod_id=mod_id)

    def _option_cost(self, option: dict) -> float:
        """What one use of a bench option costs: its currencies at their prices (rule `bench_option_cost`)."""
        return sum(count * self.price(self.raw.bases[currency]["name"]) for currency, count in option["cost"].items())

    def _remove_crafted(self, label: str) -> Priced:
        item_class = self.export.item_class(self.oracle.base_id)
        found = [option for option in self.raw.bench_options if (option.get("actions") or {}).get("remove_crafted_mods") and item_class in option.get("item_classes", [])]
        if len(found) != 1:
            raise Unsupported(f"{label!r}: {len(found)} bench options of the base's class remove the crafted mods")
        return Priced(label, "remove_crafted", self._option_cost(found[0]))

    def _fossils(self, label: str, names: tuple[str, ...]) -> Priced:
        """A resonator of as many sockets as the set has fossils (rule `resonator_sockets`), with the fossils; one use costs the resonator and each fossil."""
        if len(names) not in RESONATOR_SIZES:
            raise Unsupported(f"{label!r}: no Chaotic resonator has {len(names)} sockets")
        fossils = FossilSet(names, self.fossil_records)
        cost = self.price(f"{RESONATOR_SIZES[len(names)]} Chaotic Resonator") + sum(self.price(name) for name in names)
        return Priced(label, "fossil", cost, fossils=fossils)

    def _harvest(self, label: str, craft: str) -> Priced:
        """A tagged Harvest reforge: its lifeforce at the prices of the file (rule `harvest_lifeforce_cost`)."""
        cost = sum(count * self.price(name) for name, count in HARVEST_COST[craft].items())
        return Priced(label, "harvest", cost, tag=HARVEST_TAGS[craft])


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
