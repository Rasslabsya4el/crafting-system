"""The planner side of the goal-oracle comparison (ticket #411): probe items built by the planner's own path, and the verdicts.

The oracle (`tests/oracle/goal_oracle.py`) describes each probe as a mod id, its values and how a game gives it
(`natural`, `bench`, `essence`). This module turns that into a planner `Item` the way the planner itself would get one,
and never writes a tier by hand:

  * natural: `ExplicitMod(mod id, tier from the planner's tier table for that item, values)` and `Item.add_mod`, which is
    how every drawn mod enters an item (`actions/outcomes.py`);
  * essence: `retained_item(data, item, forced=mod)`, the planner's own path for an essence's forced mod;
  * bench: `BenchCraft(mod id).outcomes(data, item).sample(rng)`, the planner's bench action, with an rng that rolls the
    lowest or the highest value;
  * the target's own start item, as the target parser built it.

Then the planner's verdict is `Target.unmet(item)` (the goal check) for the node, and the oracle's is `Oracle.node_met` on
the same mods, given only as ids and values.
"""

import os
import random
from dataclasses import dataclass, replace
from pathlib import Path

from oracle import goal_oracle as g

from crafting_system.actions import BenchCraft
from crafting_system.actions.errors import ActionError, NotApplicableError, OutOfScopeError
from crafting_system.actions.outcomes import retained_item
from crafting_system.actions.pool import tiers_of
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity
from crafting_system.targets import load_target

REPO = Path(__file__).resolve().parents[1]
TARGETS = REPO / "examples" / "targets"
PIN_FILE = REPO / "src" / "crafting_system" / "data" / "PIN.json"


def cache_dir() -> Path:
    """`CRAFTING_CACHE_DIR`, or the project's default folder (`local/cache`) when it is not set, as the planner finds it."""
    return Path(os.environ.get("CRAFTING_CACHE_DIR") or REPO / "local" / "cache")


def load_export() -> g.Export:
    """The raw export of the pinned version from the cache; `FileNotFoundError` when it is not there."""
    return g.Export.from_cache(cache_dir(), pin_file=PIN_FILE)


class Extreme(random.Random):
    """An rng for `BenchOutcomes.sample` that rolls every stat at its lowest or at its highest value."""

    def __init__(self, high: bool) -> None:
        super().__init__(0)
        self.high = high

    def randint(self, a: int, b: int) -> int:
        return b if self.high else a


@dataclass(frozen=True)
class Disagreement:
    target: str
    path: str
    probe: str
    planner: bool
    oracle: bool

    @property
    def id(self) -> str:
        """A stable name for the probe: target, the top-level requirement, the probe."""
        return f"{self.target} :: {self.path} :: {self.probe}"

    @property
    def direction(self) -> str:
        return f"planner={'met' if self.planner else 'not-met'} oracle={'met' if self.oracle else 'not-met'}"


@dataclass
class Result:
    """Everything one target's comparison found."""

    target: str
    probes: int = 0
    met: int = 0  # probes both sides say meet the requirement
    disagreements: list[Disagreement] = None
    skipped: list[str] = None
    unjudged: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.disagreements = [] if self.disagreements is None else self.disagreements
        self.skipped = [] if self.skipped is None else self.skipped


KNOWN_FILE = REPO / "tests" / "fixtures" / "goal_oracle_known.txt"


def read_known() -> dict[str, dict[str, str]]:
    """The committed disagreements: target -> {probe id: direction}. One line each: id, a tab, the direction."""
    known: dict[str, dict[str, str]] = {}
    for line in KNOWN_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            probe_id, direction = line.split("\t")
            known.setdefault(probe_id.split(" :: ")[0], {})[probe_id] = direction
    return known


def target_stems() -> list[str]:
    return sorted(path.stem for path in TARGETS.glob("*.yaml"))


def probe_item(data, target, spec: g.ProbeSpec, fillers: tuple[ExplicitMod, ...] = ()) -> Item:
    """The planner `Item` for one probe; raises `ActionError` or `ItemError` when the planner cannot make such an item."""
    base = Item.build(
        data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=target.influences
    )
    if spec.kind == "natural":
        tier = tiers_of(data, base).get(spec.mod_id, 1)
        return base.add_mod(data, ExplicitMod(spec.mod_id, tier, spec.values, fractured=spec.fractured))
    if spec.kind == "essence":
        item = retained_item(data, base, forced=data.mods[spec.mod_id])
        if spec.values != tuple(min(s.min, s.max) for s in data.mods[spec.mod_id].stats):
            item = item.changed(data, mods=tuple(replace(m, values=spec.values) for m in item.mods))
        return item
    if spec.kind == "bench":
        high = spec.values == tuple(max(s.min, s.max) for s in data.mods[spec.mod_id].stats)
        refusal: ActionError = OutOfScopeError("no filler mod to stand on the item")
        for filler in fillers:  # the first filler that shares no family with the craft
            try:
                outcomes = BenchCraft(spec.mod_id).outcomes(data, base.add_mod(data, filler))
            except NotApplicableError as problem:
                refusal = problem
                continue
            return outcomes.sample(Extreme(high)).remove_mod(data, filler.mod_id)
        raise refusal
    raise ValueError(f"unknown probe kind {spec.kind}")


def filler_mods(data, export: g.Export, target, spec: g.OracleTarget) -> tuple[ExplicitMod, ...]:
    """Natural prefixes no requirement of the target counts, to stand on the item a bench craft is made on.

    The planner refuses a bench craft on a rare item with no mod, so the craft is made on an item that holds one of these and
    the mod is taken off again; the probe item holds the crafted mod alone. Up to eight, of different families, so that a
    craft that shares a family with the first can use the next.
    """
    chosen = {mod_id for node in spec.requirements for leaf in g.leaves(node) for mod_id in export.selected_mods(leaf.family, leaf.stat)}
    groups = {family for mod_id in chosen for family in export.mods[mod_id]["groups"]}
    base = Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=target.influences)
    found: list[ExplicitMod] = []
    taken: set[str] = set()
    for mod_id, tier in tiers_of(data, base).items():
        mod = data.mods[mod_id]
        if mod.domain != "item" or mod.generation_type != "prefix" or mod_id in chosen or groups & set(mod.families):
            continue
        if taken & set(mod.families):
            continue
        taken.update(mod.families)
        found.append(ExplicitMod(mod_id, tier, tuple(stat.min for stat in mod.stats)))
        if len(found) == 8:
            break
    return tuple(found)


def combine(data, first: Item, second: Item) -> Item:
    """One item holding the mods of both (the second's mods added to the first)."""
    item = first
    for mod in second.mods:
        item = item.add_mod(data, mod)
    return item


def oracle_item(item: Item) -> g.OItem:
    """The item as the oracle sees it: mod ids, values and the fractured flag; no tier, no crafted flag."""
    return g.OItem(tuple(g.OMod(m.mod_id, m.values, m.fractured) for m in item.mods))


def compare_target(data, export: g.Export, stem: str) -> Result:
    """Every probe of the target `stem`: the planner's verdict against the oracle's, per top-level requirement."""
    path = TARGETS / f"{stem}.yaml"
    text = path.read_text(encoding="utf-8")
    target = load_target(path, data)
    spec = g.OracleTarget.from_text(text)
    oracle = g.Oracle(export, spec)
    result = Result(stem, unjudged=spec.unjudged)
    specs = g.probe_specs(export, spec)
    built: dict[tuple, Item | None] = {}

    fillers = filler_mods(data, export, target, spec)

    def make(probe: g.ProbeSpec) -> Item | None:
        key = (probe.kind, probe.mod_id, probe.values, probe.fractured)
        if key not in built:
            try:
                built[key] = probe_item(data, target, probe, fillers)
            except (ActionError, ItemError) as problem:
                built[key] = None
                result.skipped.append(f"{probe.path} {probe.label}: the planner cannot make it ({type(problem).__name__})")
        return built[key]

    def judge(node_index: int, label: str, item: Item) -> None:
        node, onode = target.requirements[node_index], spec.requirements[node_index]
        wanted = onode.path
        planner = not any(condition is node for condition in target.unmet(item))
        verdict = oracle.node_met(onode, oracle_item(item))
        result.probes += 1
        result.met += planner and verdict
        if planner != verdict:
            result.disagreements.append(Disagreement(stem, wanted, label, planner, verdict))

    for index, onode in enumerate(spec.requirements):
        members = list(g.leaves(onode))
        mine = [probe for probe in specs if probe.path in {leaf.path for leaf in members}]
        for probe in mine:
            item = make(probe)
            if item is not None:
                judge(index, f"{probe.path} | {probe.label}", item)
        if isinstance(onode, g.OGroup):  # k-of-n: pair every probe with the top tier of each other member
            tops = {leaf.path: next((p for p in mine if p.path == leaf.path and p.role == "top"), None) for leaf in members}
            for probe in mine:
                for other_path, anchor in tops.items():
                    if anchor is None or other_path == probe.path:
                        continue
                    first, second = make(anchor), make(probe)
                    if first is None or second is None:
                        continue
                    try:
                        item = combine(data, first, second)
                    except (ActionError, ItemError):
                        continue
                    judge(index, f"{probe.path} | {probe.label} + {other_path} | {anchor.label}", item)
        if target.start_item.mods:
            judge(index, "start item", target.start_item)
    return result
