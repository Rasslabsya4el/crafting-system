"""The generated-family benchmark of planning speed: its targets (ticket #824; research note `docs/research/2026-11-13-planning-speed.md`, section 10).

A benchmark route is a measurement, never the acceptance (#812). The acceptance of every planning-speed ticket of #822 is this family of
generated targets of growing size, one family per v1 method (batches B1 to B8, and the start options), each at three sizes. `cases(data, seed)`
returns them; `.github/scripts/family_bench.py` plans and measures them on runners.

**Deterministic from a seed.** Every random choice draws from `random.Random` seeded by a string made of the seed, the method family, the
size and the attempt (`random` seeds a string through SHA-512, so the draw is the same on every machine and under every `PYTHONHASHSEED`),
and every choice iterates sorted keys. The same seed gives the same cases, byte for byte (`Case.digest`).

**What a case is.** A target in the YAML of `examples/targets/` (parsed by the product's own parser, so a case that does not parse is
never emitted: the generator draws again), a start price and a price recipe:

- **Base**: the item classes in scope are read from the data (`item_classes`): the classes of released bases of domain `item` that have a mod
  pool at the case's item level. Each family visits them in its own seeded order, the families' filters applied (sockets on a class that
  has sockets, a catalyst on jewellery, ...).
- **Wanted mods**: `SIZES` gives the number of wanted families (1-2, 3-4, 5-6), their tiers (T3; T2-T3; T1-T2), and the scale of the method set
  (essences, fossils, strands); the prefix and suffix mix is drawn within three of each. Mods are drawn from the base's own pool.
- **Methods**: `METHODS`, one entry per v1 method family: the `actions:` it names and the target keys it needs. Every family names its
  actions, so the plan is the cheapest among the named ones (OR-13).
- **Prices**: the committed 3.29 snapshots (`SNAPSHOTS`), one of them drawn as the primary and the others filling the names it lacks; every
  currency but the Chaos Orb is scaled by its own seeded factor, log-uniform between 0.3 and 3 (prices decide where the near ties are: R04's
  expanded share moved from 78% to 94% between two snapshots). A family whose method set grows by size keeps only the essences or fossils it
  drew. The start item of a generated base has no price in a snapshot: `START_PRICE` (a measurement setting, not a route's number) times its
  own factor stands in for it.
- **Refused today**: a family the planner cannot plan yet is generated all the same, so the ticket that builds it finds its cases ready.
  `Case.refused` says why, read from the code, not from a list here: a named kind that the catalog does not have, or has with `planner=False`,
  or that needs Memory Strands; a target key that `make_plan` refuses (implicits, quality, sockets, enchantment); Memory Strands on the
  start item. The heavy run records what really happened, and its summary names every case whose outcome differs from this mark.

Nothing here reads a benchmark route's numbers, and there is no constant per route (OR-12, OR-26).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from crafting_system.actions.catalog import catalog, kinds
from crafting_system.actions.pool import pool_candidates, tiers_of
from crafting_system.data.model import GameData
from crafting_system.items.model import Influence, Item, Metamod, Rarity
from crafting_system.items.enchantments import POOL_FAMILIES, enchant_class, is_removed_enchant
from crafting_system.items.sockets import class_maximum
from crafting_system.items.spawn import spawn_weight
from crafting_system.items.vendor_recipes import RECIPES
from crafting_system.prices.price_file import PriceFile, load_price_file
from crafting_system.targets import parse_target
from crafting_system.targets.model import Target

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1  # bump when a case's meaning changes: a baseline is comparable only with cases of its schema
DEFAULT_SEED = 824

# The committed 3.29 (Allflame) snapshots, in date order (OR-21: today's snapshot; the owner keeps 3.29 until v1 is built).
SNAPSHOTS = (
    "tests/fixtures/prices/routes-allflame-2026-10-31.json",
    "tests/fixtures/prices/bases-allflame-2026-11-01.json",
    "tests/fixtures/prices/vendor-v01-2026-11-01.json",
    "tests/fixtures/prices/foresight-allflame-2026-11-02.json",
    "tests/fixtures/prices/routes-allflame-2026-11-10.json",
    "tests/fixtures/prices/veiled-r24-r07-2026-11-12.json",
)
PRICE_FACTOR = (0.3, 3.0)  # each currency's price is scaled by a factor drawn log-uniform in this range (ticket #824)
UNIT = "Chaos Orb"  # the unit: never scaled
START_PRICE = {"normal": 1.0, "magic": 2.0, "rare": 5.0}  # Chaos, times a seeded factor: a stand-in for a generated base's market price
ITEM_LEVEL = (75, 86)  # the case's item level is drawn in this range (inclusive)
ATTEMPTS = 40  # draws per case before the family moves to its next item class


@dataclass(frozen=True)
class Size:
    name: str
    wanted: tuple[int, int]  # how many wanted families, inclusive range
    tiers: tuple[int, int]  # the `min_tier` of each wanted family, inclusive range (1 is the best tier)
    scale: int  # 0, 1, 2: the index into a family's growing method set


SIZES = (
    Size("small", (1, 2), (3, 3), 0),
    Size("medium", (3, 4), (2, 3), 1),
    Size("large", (5, 6), (1, 2), 2),
)
ESSENCES_KEPT = (2, 6, 1000)  # essences priced, by size (1000: every essence the class takes)
FOSSILS_KEPT = (4, 7, 12)  # fossils priced, by size: up to 15, 98 and 793 sets of one to four fossils
STRANDS = (1, 50, 100)  # Memory Strands on the start item, by size (the strand families)
STRANDS_GROWING = (0, 50, 100)  # the same in the last growing method set: 0 to 100


@dataclass(frozen=True)
class Draw:
    """What one attempt at a case has drawn so far; a method's hooks read and extend it."""

    data: GameData
    rng: random.Random
    size: Size
    base_id: str
    item_level: int
    wanted: tuple[dict, ...]  # requirement entries of the target, in YAML form
    wanted_mods: tuple[str, ...]  # the top mod id of each wanted family (for a fractured or given start)


@dataclass(frozen=True)
class Method:
    """One v1 method family: what its cases name and need. `keys`, `start_item` and `keep` are hooks on the draw."""

    name: str
    batch: str
    rarity: str  # of the start item
    actions: tuple[str, ...]
    classes: Callable[[GameData, str], bool] = lambda data, item_class: True
    keys: Callable[[Draw], dict] = lambda draw: {}  # extra top-level target keys (implicits, sockets, ...)
    start_item: Callable[[Draw], dict] = lambda draw: {}  # extra `start_item:` keys (mods, strands)
    extra_actions: Callable[[Draw], tuple[str, ...]] = lambda draw: ()  # labels drawn from the data (metamod crafts)
    keep: Callable[[Draw, PriceFile], Callable[[str], bool]] | None = None  # which price names stay (a method set that grows by size)
    start: str = "bought"
    influenced: bool = False  # the base is influenced and one wanted mod is an influence mod
    roll_limit: bool = False  # one wanted family carries a `min_roll`
    veiled: bool = False  # one wanted mod is a veiled (unveiled-domain) mod
    vendor_starts: bool = False  # planned with the vendor-recipe start options (`plan_with_starts`)
    note: str = ""


@dataclass(frozen=True)
class Case:
    id: str  # "<method>/<size>"
    method: str
    batch: str
    size: str
    seed: int
    item_class: str
    base_id: str
    item_level: int
    wanted: int  # the number of wanted families
    actions: tuple[str, ...]
    target_yaml: str
    start: str  # bought or given
    start_price: float | None
    primary_snapshot: str
    price_seed: str
    keep: tuple[str, ...] | None  # the price names kept when the method set grows by size, else None (all)
    vendor_starts: bool
    refused: str | None  # why the planner refuses it today, read from the code; None when it is expected to plan
    note: str = ""

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(dataclasses.asdict(self), sort_keys=True).encode()).hexdigest()[:16]


# -- the data the generator reads ---------------------------------------------------------------------------------------------------


def item_classes(data: GameData, item_level: int = ITEM_LEVEL[1]) -> tuple[str, ...]:
    """The item classes in scope, read from the data: released bases of domain `item` whose pool at `item_level` is not empty."""
    found = set()
    for item_class, bases in sorted(bases_by_class(data).items()):
        for base_id in bases[:3]:
            try:
                if pool_candidates(data, Item(base_id, item_level, Rarity.RARE)):
                    found.add(item_class)
                    break
            except Exception:  # noqa: BLE001 - a base the model has no rule for is not in scope (OutOfScopeError, UnknownBaseError)
                continue
    return tuple(sorted(found))


_BASES: dict[int, dict[str, list[str]]] = {}


def bases_by_class(data: GameData) -> dict[str, list[str]]:
    key = id(data)
    if key not in _BASES:
        grouped: dict[str, list[str]] = {}
        for base in sorted(data.base_items.values(), key=lambda b: b.id):
            # a gamble placeholder ("Random One Hand Sword", class HiddenItem, ids ending in Gamble) is no base a player crafts on
            real = base.release_state == "released" and base.domain == "item" and base.item_class != "HiddenItem" and not base.id.endswith("Gamble")
            if real and "Royale" not in base.id and "not_for_sale" not in base.tags:
                grouped.setdefault(base.item_class, []).append(base.id)
        _BASES[key] = grouped
    return _BASES[key]


def has_tag(data: GameData, item_class: str, tag: str) -> bool:
    return any(tag in data.base_items[b].tags for b in bases_by_class(data).get(item_class, ()))


ARMOUR = frozenset({"Body Armour", "Boots", "Gloves", "Helmet", "Shield"})
JEWELLERY = frozenset({"Amulet", "Ring", "Belt"})


def socketed(data: GameData, item_class: str) -> bool:
    return any((class_maximum(data.base_items[b]) or 0) >= 3 for b in bases_by_class(data).get(item_class, ()))


def with_recipe(data: GameData, item_class: str) -> bool:
    kind = item_class.lower().replace(" ", "_")
    return any(kind in recipe.base_kinds for recipe in RECIPES.values())


def single_family_mods(data: GameData, item: Item) -> dict[str, list[str]]:
    """The base's own pool, as family -> mod ids, of mods with one family that a draw can give (no essence-only mod)."""
    found: dict[str, list[str]] = {}
    for candidate in pool_candidates(data, item):
        mod = candidate.mod
        if len(mod.families) != 1 or mod.is_essence_only or mod.generation_type not in ("prefix", "suffix") or mod.domain != "item":
            continue
        found.setdefault(mod.families[0], []).append(mod.id)
    return {family: sorted(ids) for family, ids in sorted(found.items())}


def side_of(data: GameData, mod_ids: Sequence[str]) -> str | None:
    sides = {data.mods[m].generation_type for m in mod_ids}
    return sides.pop() if len(sides) == 1 else None


def top_mod(data: GameData, item: Item, mod_ids: Sequence[str]) -> str:
    tiers = tiers_of(data, item)
    return min(mod_ids, key=lambda m: (tiers.get(m, 99), m))


def mod_entry(data: GameData, mod_id: str, fractured: bool = False) -> dict:
    """A start item's mod at its best roll."""
    values = [max(s.min, s.max) for s in data.mods[mod_id].stats]
    entry = {"mod": mod_id, "values": values}
    if fractured:
        entry["fractured"] = True
    return entry


def tag_spawns(data: GameData, base_id: str, mod_id: str) -> bool:
    """Whether the mod has a positive spawn weight on the base's tags (`items.spawn.spawn_weight`, the game's first-match rule)."""
    return spawn_weight(data.mods[mod_id], data.base_items[base_id].tags) > 0


_CLASS_HAS: dict[tuple[int, str, str], bool] = {}


def class_has(generation_type: str):
    """A `classes` filter: the class has a base on which some mod of `generation_type` spawns (eldritch implicits: armour pieces only)."""

    def test(data: GameData, item_class: str) -> bool:
        key = (id(data), item_class, generation_type)
        if key not in _CLASS_HAS:
            _CLASS_HAS[key] = any(generated_mods(data, b, generation_type, ITEM_LEVEL[1]) for b in bases_by_class(data).get(item_class, ())[:1])
        return _CLASS_HAS[key]

    return test


def generated_mods(data: GameData, base_id: str, generation_type: str, item_level: int) -> list[str]:
    return sorted(
        m.id for m in data.mods.values()
        if m.generation_type == generation_type and m.required_level <= item_level and m.families and tag_spawns(data, base_id, m.id)
    )  # fmt: skip


# -- the method families ------------------------------------------------------------------------------------------------------------


def keep_some(marker: Callable[[GameData, str, str], bool], counts: Sequence[int], always: Sequence[str] = ()):
    """A `keep` hook: of the price names `marker` picks (essences for this class, fossils), keep a seeded `counts[scale]` of them, `always` among them."""

    def hook(draw: Draw, prices: PriceFile) -> Callable[[str], bool]:
        item_class = draw.data.base_items[draw.base_id].item_class
        pool = sorted(name for name in prices.prices if marker(draw.data, item_class, name) and name not in always)
        kept = set(draw.rng.sample(pool, min(counts[draw.size.scale] - len(always), len(pool)))) | set(always)
        return lambda name: not marker(draw.data, item_class, name) or name in kept

    return hook


def is_essence_for(data: GameData, item_class: str, name: str) -> bool:
    return any(e.name == name and e.mod_for(item_class) for e in data.essences.values())


def is_fossil(data: GameData, item_class: str, name: str) -> bool:
    return name.endswith(" Fossil") and any(f.name == name for f in data.fossils.values())


def metamod_labels(draw: Draw) -> tuple[str, ...]:
    item = Item(draw.base_id, draw.item_level, Rarity.RARE)
    metamods = {m.value for m in Metamod}
    labels = []
    for action in catalog(draw.data, item, planner_only=True, names={"bench-craft"}):
        mod_id = getattr(action, "mod_id", None)
        if mod_id and set(draw.data.mods[mod_id].families) & metamods:
            labels.append(action.label(draw.data))
    labels = sorted(set(labels))
    return tuple(draw.rng.sample(labels, min(1 + draw.size.scale, len(labels))))


def implicit_keys(generation_type: str, corrupted: bool = False):
    def hook(draw: Draw) -> dict:
        mods = generated_mods(draw.data, draw.base_id, generation_type, draw.item_level)
        if not mods:
            raise Unsuitable(f"no {generation_type} mod on this base")
        chosen = draw.rng.sample(mods, min(1 + draw.size.scale // 2, len(mods)))
        entries = []
        for mod_id in chosen:
            entry = {"family": draw.data.mods[mod_id].families[0], "mod": mod_id}
            if corrupted:
                entry["corrupted"] = True
            entries.append(entry)
        return {"implicits": entries}

    return hook


def enchant_keys(draw: Draw) -> dict:
    """An enchantment of the base's pool (`items.enchantments`: the heist groups of weapons and body armour), by mod id."""
    held = enchant_class(draw.data.base_items[draw.base_id])
    mods = sorted(
        m.id for m in draw.data.mods.values()
        if held is not None and any(POOL_FAMILIES.get(f) is held for f in m.families) and not is_removed_enchant(m)
    )  # fmt: skip
    if not mods:
        raise Unsuitable("no enchantment on this base")
    return {"enchantment": {"any_of": draw.rng.sample(mods, min(1 + 2 * draw.size.scale, len(mods)))}}


def socket_keys(draw: Draw) -> dict:
    most = class_maximum(draw.data.base_items[draw.base_id]) or 0
    if most < 3:
        raise Unsuitable("fewer than three sockets on this class")
    count = (3, max(3, most - 1), most)[draw.size.scale]  # three sizes within the class maximum (`items.sockets.class_maximum`)
    return {"sockets": {"count": count, "links": (2, count - 1, count)[draw.size.scale]}}


def strands_item(draw: Draw) -> dict:
    return {"memory_strands": STRANDS[draw.size.scale]}


def growing_strands_item(draw: Draw) -> dict:
    count = STRANDS_GROWING[draw.size.scale]
    return {"memory_strands": count} if count else {}


def keep_all(*hooks):
    """A `keep` hook that keeps a price name when every hook keeps it (a method set with essences and fossils draws both)."""

    def hook(draw: Draw, prices: PriceFile) -> Callable[[str], bool]:
        tests = [h(draw, prices) for h in hooks]
        return lambda name: all(test(name) for test in tests)

    return hook


def fractured_item(draw: Draw) -> dict:
    return {"mods": [mod_entry(draw.data, draw.wanted_mods[0], fractured=True)]}


def given_item(draw: Draw) -> dict:
    return {"mods": [mod_entry(draw.data, draw.wanted_mods[0])]}


BASIC = ("transmutation-orb", "alteration-orb", "augmentation-orb", "regal-orb", "chaos-orb", "exalted-orb", "annulment-orb")
REROLL = ("chaos-orb", "exalted-orb", "annulment-orb")
GROWING = (  # (name, the actions this step adds)
    ("basic", BASIC),
    ("essences", ("essence",)),
    ("fossils", ("fossil-set", "bench-craft", "remove-crafted-mods")),
    ("harvest", ("harvest-reforge", "harvest-add-remove", "harvest-resistance-swap")),
    ("unveil", ("veiled-chaos-orb", "unveil", "pick")),
    ("lock", ("hinekora-lock",)),
    ("donors", ("recombinator", "awakeners-orb")),
    ("strands", ("foulborn-exalted-orb",)),
)

METHODS: tuple[Method, ...] = (
    # B1
    Method("basic-orbs", "B1", "normal", BASIC),
    Method("alchemy-scouring", "B1", "normal", ("alchemy-orb", "scouring-orb", *REROLL)),
    Method("essences", "B1", "normal", ("essence", "annulment-orb", "exalted-orb"), keep=keep_some(is_essence_for, ESSENCES_KEPT)),
    Method("fossil-sets", "B1", "rare", ("fossil-set", "bench-craft", "remove-crafted-mods"), keep=keep_some(is_fossil, FOSSILS_KEPT)),
    Method("bench-metamods", "B1", "rare", (*REROLL, "bench-craft", "remove-crafted-mods"), extra_actions=metamod_labels),
    Method("fracturing", "B1", "rare", ("fracturing-orb", *REROLL)),
    Method("divine-roll-limits", "B1", "rare", ("divine-orb", *REROLL), roll_limit=True),
    # B2
    Method("harvest", "B2", "rare", ("harvest-reforge", "harvest-add-remove", "harvest-resistance-swap", "harvest-damage-swap", "annulment-orb", "exalted-orb")),
    Method("beasts", "B2", "rare", ("aspect-beast", "talisman-fracture", "beast-side-swap", "wild-bristle-matron", *REROLL)),
    Method("eldritch", "B2", "rare", ("eldritch-implicit-currency", *REROLL), keys=implicit_keys("searing_exarch_implicit"),
           classes=class_has("searing_exarch_implicit")),
    Method("influence", "B2", "rare", ("harvest-reforge-influence", *REROLL), influenced=True),
    Method("veiled", "B2", "rare", ("veiled-chaos-orb", "unveil", "pick", "annulment-orb", "exalted-orb"), veiled=True),
    Method("quality", "B2", "rare", ("quality-currency", *REROLL), classes=lambda d, c: c in ARMOUR or has_tag(d, c, "weapon"),
           keys=lambda draw: {"quality": {"min_percent": (10, 15, 20)[draw.size.scale]}}),
    Method("catalysts", "B2", "rare", ("catalyst", *REROLL), classes=lambda d, c: c in JEWELLERY,
           keys=lambda draw: {"quality": {"type": "intrinsic", "min_percent": (10, 15, 20)[draw.size.scale]}}),
    # B3
    Method("imprints", "B3", "magic", ("imprint", "restore", "alteration-orb", "augmentation-orb", "regal-orb")),
    Method("awakener", "B3", "rare", ("awakeners-orb", *REROLL), influenced=True),
    Method("recombinators", "B3", "rare", ("recombinator", *REROLL)),
    # B4
    Method("vaal", "B4", "rare", (*REROLL, "vaal"), keys=lambda draw: {"allow_corrupted": True}),
    Method("locus", "B4", "rare", (*REROLL, "locus"), keys=lambda draw: {"allow_corrupted": True}),
    Method("bloodstained", "B4", "rare", ("fossil-set",), keys=lambda draw: {"allow_corrupted": True, **implicit_keys("corrupted", corrupted=True)(draw)},
           keep=keep_some(is_fossil, FOSSILS_KEPT, always=("Bloodstained Fossil",)), classes=class_has("corrupted")),
    # B5
    Method("strands", "B5", "rare", REROLL, start_item=strands_item),
    Method("remembrance", "B5", "rare", ("remembrance-orb", *REROLL), start_item=strands_item),
    Method("unravelling", "B5", "rare", ("unravelling-orb", *REROLL), start_item=strands_item),
    Method("foulborn", "B5", "magic", ("foulborn-exalted-orb", "foulborn-augmentation-orb", "foulborn-regal-orb", "exalted-orb"), start_item=strands_item),
    # B6, B7, B8
    Method("sockets", "B6", "rare", ("jewellers-orb", "orb-of-fusing", "bench-socket-count", "bench-socket-links", *REROLL), classes=socketed, keys=socket_keys,
           start_item=lambda draw: {"sockets": {"count": 2}}),
    Method("enchants", "B7", "rare", ("tempering", "tailoring", *REROLL), keys=enchant_keys,
           classes=lambda d, c: any(enchant_class(d.base_items[b]) for b in bases_by_class(d).get(c, ()))),
    Method("hinekora-lock", "B8", "rare", ("hinekora-lock", *REROLL)),
    # start options
    Method("start-bought", "start", "normal", BASIC),
    Method("start-fractured", "start", "rare", REROLL, start_item=fractured_item),
    Method("start-vendor-recipe", "start", "normal", BASIC, classes=with_recipe, vendor_starts=True),
    Method("start-given", "start", "rare", REROLL, start="given", start_item=given_item),
    # method sets growing by batch (research note, section 10): basic orbs; plus essences; plus fossil sets; plus Harvest; plus unveil;
    # plus the Lock; plus donors; plus strands 0 to 100. Each set holds the one before it, so a ticket sees what a method costs inside a set
    *(
        Method(f"growing-{index + 1}-{name}", "growing", "normal", tuple(a for step in GROWING[: index + 1] for a in step[1]),
               keep=(keep_all(keep_some(is_essence_for, ESSENCES_KEPT), keep_some(is_fossil, FOSSILS_KEPT)) if index >= 2 else keep_some(is_essence_for, ESSENCES_KEPT) if index == 1 else None),
               veiled=index >= 4, start_item=growing_strands_item if index >= 7 else (lambda draw: {}))
        for index, (name, _) in enumerate(GROWING)
    ),
)


class Unsuitable(Exception):
    """This draw cannot make a case of this family (a base with no such mod, a pool too small): the generator draws again."""


# -- the generator --------------------------------------------------------------------------------------------------------------------


def cases(data: GameData, seed: int = DEFAULT_SEED, methods: Sequence[Method] = METHODS, sizes: Sequence[Size] = SIZES) -> list[Case]:
    """Every (method family, size) case of the seed, in `methods` and `sizes` order. Raises `RuntimeError` when a family finds no class."""
    classes = list(item_classes(data))
    random.Random(f"{seed}:classes").shuffle(classes)  # one seeded order of the classes for the whole list
    prices = merged_snapshots()
    out = []
    for method in methods:
        for size in sizes:
            # the case's slot in the full list (`METHODS` x `SIZES`) picks where in that order it starts, so the cases visit every class in
            # turn (93 cases over 24 classes) and a family generated alone gets the same case as in the full list
            slot = METHODS.index(method) * len(SIZES) + [s.name for s in SIZES].index(size.name)
            order = classes[slot % len(classes) :] + classes[: slot % len(classes)]
            order = [c for c in order if method.classes(data, c)]
            if not order:
                raise RuntimeError(f"no item class in scope suits {method.name}")
            out.append(make_case(data, seed, method, size, order, prices))
    return out


def make_case(data: GameData, seed: int, method: Method, size: Size, order: Sequence[str], prices: Mapping[str, PriceFile]) -> Case:
    why = []
    for item_class in order:
        for attempt in range(ATTEMPTS):
            rng = random.Random(f"{seed}:{method.name}:{size.name}:{item_class}:{attempt}")
            try:
                return draw_case(data, seed, method, size, item_class, rng, prices)
            except Unsuitable as error:
                why.append(f"{item_class}: {error}")
    raise RuntimeError(f"no case for {method.name}/{size.name} on any class: {why[-3:]}")


def draw_case(data: GameData, seed: int, method: Method, size: Size, item_class: str, rng: random.Random, prices: Mapping[str, PriceFile]) -> Case:
    base_id = rng.choice(bases_by_class(data)[item_class])
    item_level = rng.randint(*ITEM_LEVEL)
    influences = [rng.choice(sorted(i.value for i in Influence))] if method.influenced else []
    item = Item(base_id, item_level, Rarity.RARE, influences=frozenset(Influence(i) for i in influences))
    try:
        pool = single_family_mods(data, item)
    except Exception as error:  # noqa: BLE001 - a base the model refuses (OutOfScopeError)
        raise Unsuitable(f"no pool: {error}") from None
    wanted_count = rng.randint(*size.wanted)
    prefixes = rng.randint(max(0, wanted_count - 3), min(3, wanted_count))
    by_side = {side: [f for f, ids in pool.items() if side_of(data, ids) == side] for side in ("prefix", "suffix")}
    if method.influenced:  # one wanted mod is an influence mod: in the influenced pool, not in the plain one
        plain = single_family_mods(data, Item(base_id, item_level, Rarity.RARE))
        special = sorted(f for f, ids in pool.items() if f not in plain or set(ids) - set(plain[f]))
        if not special:
            raise Unsuitable("no influence mod")
        first = [rng.choice(special)]
    else:
        first = []
    chosen: list[tuple[str, list[str]]] = [(f, pool[f]) for f in first]
    sides = ["prefix"] * prefixes + ["suffix"] * (wanted_count - prefixes)
    rng.shuffle(sides)
    for f, _ in chosen:
        side = side_of(data, pool[f])
        if side in sides:
            sides.remove(side)
        else:
            raise Unsuitable("the influence mod's side is full")
    for side in sides[: wanted_count - len(chosen)]:
        options = sorted(set(by_side[side]) - {f for f, _ in chosen})
        if not options:
            raise Unsuitable(f"too few {side} families")
        f = rng.choice(options)
        chosen.append((f, pool[f]))
    requirements = []
    tiers = tiers_of(data, item)
    for f, ids in chosen:
        ladder = max(tiers.get(m, 1) for m in ids)
        entry = {"family": f, "min_tier": min(rng.randint(*size.tiers), ladder), "not_crafted": True}
        requirements.append(entry)
    wanted_mods = tuple(top_mod(data, item, ids) for _, ids in chosen)
    if method.roll_limit:
        candidates = [i for i, (f, ids) in enumerate(chosen) if len({len(data.mods[m].stats) for m in ids}) == 1 and len(data.mods[wanted_mods[i]].stats) == 1]
        if not candidates:
            raise Unsuitable("no single-stat family for a roll limit")
        i = rng.choice(candidates)
        stat = data.mods[wanted_mods[i]].stats[0]
        low, high = sorted((stat.min, stat.max))
        requirements[i] = {"family": chosen[i][0], "min_roll": [low + (high - low) * (1 + size.scale) // 4], "not_crafted": True}
    if method.veiled:
        veiled = sorted(m for m in generated_mods(data, base_id, "prefix", item_level) + generated_mods(data, base_id, "suffix", item_level) if data.mods[m].domain == "unveiled")
        veiled = [m for m in veiled if data.mods[m].families[0] not in {f for f, _ in chosen}]
        if not veiled:
            raise Unsuitable("no veiled mod")
        mod_id = rng.choice(veiled)
        requirements[-1] = {"family": data.mods[mod_id].families[0], "mod": mod_id}
    draw = Draw(data, rng, size, base_id, item_level, tuple(requirements), wanted_mods)
    start_item = {"rarity": method.rarity, **method.start_item(draw)}
    actions = (*method.actions, *method.extra_actions(draw))
    doc = {
        "base": base_id, "item_level": item_level, "influence": influences, "actions": list(actions), "requirements": list(requirements),
        **method.keys(draw), "start_item": start_item, "start": method.start,
    }  # fmt: skip
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000)
    try:
        target = parse_target(text, data, source=f"<{method.name}/{size.name}>")
    except Exception as error:  # noqa: BLE001 - TargetError, or what the parser's resolvers raise: draw again
        raise Unsuitable(f"does not parse: {str(error)[:160]}") from None
    primary = rng.choice(SNAPSHOTS)
    price_seed = f"{seed}:{method.name}:{size.name}:prices"
    keep = None
    if method.keep is not None:
        merged = merge(prices, primary)
        test = method.keep(draw, merged)
        keep = tuple(sorted(name for name in merged.prices if test(name)))
    start_price = None if method.start == "given" else round(START_PRICE[method.rarity] * factor(price_seed, "<start item>"), 4)
    return Case(
        id=f"{method.name}/{size.name}", method=method.name, batch=method.batch, size=size.name, seed=seed, item_class=item_class,
        base_id=base_id, item_level=item_level, wanted=len(requirements), actions=tuple(actions), target_yaml=text, start=method.start,
        start_price=start_price, primary_snapshot=primary, price_seed=price_seed, keep=keep, vendor_starts=method.vendor_starts,
        refused=refusal_today(data, target, actions), note=method.note,
    )  # fmt: skip


def refusal_today(data: GameData, target: Target, actions: Sequence[str]) -> str | None:
    """Why `make_plan` refuses this case today, read from the code (the kind catalog and the target keys it refuses); None when it plans."""
    import crafting_system.actions  # noqa: F401 - registers every kind

    registered = {entry.name: entry for entry in kinds()}
    labels_or_kinds = [a for a in actions if a != "hinekora-lock"]
    reasons = []
    strands = target.start_item.memory_strands >= 1
    if strands:
        reasons.append("Memory Strands on the start item")
    for name in labels_or_kinds:
        entry = registered.get(name)
        if entry is None:
            if not any(ch in name for ch in " "):  # a label has spaces; a kind name never has
                reasons.append(f"{name}: no such kind yet")
        elif not entry.planner:
            reasons.append(f"{name}: planner=False")
        elif entry.needs_strands and not strands:
            reasons.append(f"{name}: needs Memory Strands")
    for key in ("implicits", "sockets", "enchantment"):
        if getattr(target, key):
            reasons.append(f"target asks for {key}")
    if target.quality is not None:
        reasons.append("target asks for quality")
    return "; ".join(reasons) or None


# -- prices ---------------------------------------------------------------------------------------------------------------------------


_SNAPSHOT_CACHE: dict[str, PriceFile] = {}


def merged_snapshots() -> dict[str, PriceFile]:
    if not _SNAPSHOT_CACHE:
        for name in SNAPSHOTS:
            _SNAPSHOT_CACHE[name] = load_price_file(ROOT / name)
    return dict(_SNAPSHOT_CACHE)


def merge(snapshots: Mapping[str, PriceFile], primary: str) -> PriceFile:
    """The primary snapshot, with every name it lacks taken from the latest other snapshot that has it."""
    base = snapshots[primary]

    def merged(field_name: str) -> dict:
        found: dict = {}
        for name in SNAPSHOTS:  # date order: a later snapshot overwrites an earlier one, the primary last of all
            if name != primary:
                found.update(getattr(snapshots[name], field_name))
        found.update(getattr(base, field_name))
        return dict(sorted(found.items()))

    return dataclasses.replace(base, prices=merged("prices"), ninja=merged("ninja"), deep=merged("deep"), markets=merged("markets"))


def factor(price_seed: str, name: str) -> float:
    low, high = PRICE_FACTOR
    u = random.Random(f"{price_seed}:{name}").random()
    return math.exp(math.log(low) + u * (math.log(high) - math.log(low)))


def prices_for(case: Case) -> PriceFile:
    """The case's prices: the merged snapshots, every currency but the unit scaled by its seeded factor, only `keep` when it is set."""
    merged = merge(merged_snapshots(), case.primary_snapshot)
    kept = None if case.keep is None else set(case.keep)

    def scale(name: str, record):
        if name == UNIT or getattr(record, "chaos", None) is None:
            return record
        return dataclasses.replace(record, chaos=record.chaos * factor(case.price_seed, name))

    def table(entries: Mapping) -> dict:
        return {name: scale(name, entry) for name, entry in entries.items() if kept is None or name in kept}

    # every table a price can be read from (the trade or poe.ninja price, the poe.ninja row beside a trade price, the last deep reading, a
    # thin market's mean) takes the same factor per name, and the Divine Orb's rate takes the Divine Orb's
    return dataclasses.replace(
        merged, prices=table(merged.prices), ninja=table(merged.ninja), deep=table(merged.deep), markets=table(merged.markets),
        chaos_per_divine=merged.chaos_per_divine * factor(case.price_seed, "Divine Orb"),
    )  # fmt: skip


def target_of(case: Case, data: GameData) -> Target:
    return parse_target(case.target_yaml, data, source=f"<{case.id}>")


def write_cases(found: Sequence[Case], path: Path) -> None:
    path.write_text(json.dumps([dataclasses.asdict(c) for c in found], indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_cases(path: Path) -> list[Case]:
    return [Case(**{**row, "actions": tuple(row["actions"]), "keep": None if row["keep"] is None else tuple(row["keep"])}) for row in json.loads(path.read_text(encoding="utf-8"))]
