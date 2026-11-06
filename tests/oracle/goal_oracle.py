"""The goal oracle: an independent judge of "does this item meet this target" (ticket #411, rebuild step 2a).

Why it exists. Every other check of the goal compares the planner with itself: the tests of `Target.is_met_by`
use the planner's tier tables and its own reading of a bench craft, so R05's bench Life counted as "Life T1"
and `--verify` agreed (audit #396, class 6). This module has no part of the planner in it.

What it reads, and only this:
  * the target's YAML text (the keys `base`, `item_level`, `influence`, `requirements` with `family`, `stat`,
    `mod`, `min_tier`, `min_roll`, `not_crafted`, `at_least` / `of`);
  * the raw repoe-fork export, from `<CRAFTING_CACHE_DIR>/repoe-fork/<version>/` (`mods.json`,
    `base_items.json`, `crafting_bench_options.json`);
  * the owner's rules (`docs/owner-rules.md`), written below as code.

It imports the standard library, `yaml` and two shared modules, `independent/ladder.py` (ticket #419: the natural
ladder and the base-name rule) and `independent/export.py` (ticket #432: the loader of the raw export), both shared with
`tests/reconcile/`, and nothing from `crafting_system` (a test scans this file for that). The planner's `targets/parse.py` and `targets/model.py` were read only to learn the YAML keys.

The rules it implements
  * OR-1. A requirement with no tier, or with a `min_tier`, is judged on the natural ladder of its family on
    the target's base, at the target's item level. With no tier the item's mod must be the top tier of that
    ladder that the item level allows. A crafted mod meets a requirement only when the requirement names that
    craft exactly (`mod:`); otherwise its values are judged on the natural ladder (a crafted value counts as
    the best natural tier whose range holds it).
  * OR-2. `mod:` is exactly that mod, and no other tier of its family.
  * OR-4. `min_roll` is a roll with no tier: with a `min_roll` and no `min_tier` the tier is not asked.
    A `stat:` text that states its value (no `#`) is the guide's own wording, so it asks no top tier either (checker, #420).
  * k-of-n (`at_least` / `of`): at least that many of the members are met; members may be groups.

The natural ladder of a family on a base, worked out from the raw mods in `independent/ladder.py`
  * A mod is natural when its domain is the base's own domain (`item` for gear, `misc` for jewels), it is a prefix or a suffix, it is not essence-only, it is not a
    Battle Royale copy (its id holds "Royale"), and its spawn weight on the item's tags is above zero.
  * The spawn weight is the weight of the FIRST entry of the mod's `spawn_weights` whose tag the item has; a
    later entry is ignored. The item's tags are the base's tags, plus for each influence the base's tags with
    the influence's suffix (`belt` + hunter -> `belt_basilisk`).
  * The mods of one `type` (and one generation type) that are natural on the item form a ladder. In it, tier 1 is
    the highest required level, and a mod's tier is 1 plus the number of ladder mods of a strictly higher
    required level.
  * The top tier the item level allows is the lowest tier number among the ladder's mods whose required
    level is at most the item level.

Not judged yet (OR-29, ticket-filed): implicit requirements, quality, sockets, enchantment, corruption and the
start item's own text. `OracleTarget.unjudged` lists the keys of a target that it does not judge, and the
comparison says so; it never answers for them.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from independent import export as shared_export
from independent import ladder as shared

SIDES = shared.SIDES
CRAFTED_DOMAIN = "crafted"

# Top-level target keys the oracle does not judge (OR-29), with what each one asks for.
UNJUDGED_KEYS = {
    "implicits": "implicit requirements (an implicit mod, Eldritch grade, corrupted implicit)",
    "quality": "quality (catalyst or plain)",
    "sockets": "sockets (count, links, colours)",
    "enchantment": "enchantment",
    "allow_corrupted": "corruption (a corrupted item as the goal)",
}

_RANGE = re.compile(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)")
_LABELLED = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
_PLAIN = re.compile(r"\[([^\]|]*)\]")


def normal_text(text: str) -> str:
    """A mod text compared as a stat: every roll range as `#`, the [a|b] and [a] markup reduced to its words, lines trimmed."""
    text = _PLAIN.sub(r"\1", _LABELLED.sub(r"\1", _RANGE.sub("#", text)))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


# --- the raw export ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rung:
    """One mod of a ladder: its tier on that ladder, required level, and its stats as (stat id, low, high)."""

    mod_id: str
    tier: int
    level: int
    stats: tuple[tuple[str, int, int], ...]

    def holds(self, stat_ids: tuple[str, ...], values: tuple[int, ...]) -> bool:
        """Whether the values (one per stat id) all lie inside this rung's ranges, stat by stat."""
        if tuple(stat for stat, _, _ in self.stats) != stat_ids or len(values) != len(self.stats):
            return False
        return all(low <= value <= high for (_, low, high), value in zip(self.stats, values))


Ladder = tuple[Rung, ...]  # best tier first


class Export:
    """The raw repoe-fork files, read as plain dicts.

    `mods` and `base_items` are the files' own top-level dicts; `bench_options` is the bench file's list.
    """

    def __init__(self, mods: dict, base_items: dict, bench_options: list | None = None, essences: dict | None = None):
        self.mods = mods
        self.base_items = base_items
        self.bench_options = bench_options or []
        self.essences = essences or {}
        self._ladders: dict[tuple[str, frozenset[str]], dict[tuple[str, str], Ladder]] = {}

    @classmethod
    def from_cache(cls, cache_dir: Path | None = None, pin_file: Path | None = shared_export.PIN_FILE) -> "Export":
        """The export in `<cache dir>/repoe-fork/<version>/`, read by the loader shared with the reconciliation checks.

        The cache dir defaults to `CRAFTING_CACHE_DIR`, then `local/cache`; the version is the one the pin file names (the
        repo's by default); `pin_file=None` takes the only version folder there. `ExportMissing` (a `FileNotFoundError`) when
        the export, a file of it or the pin file is absent (`independent/export.py`).
        """
        return cls.from_raw(shared_export.load_export(cache_dir, pin_file))

    @classmethod
    def from_raw(cls, raw: "shared_export.RawExport") -> "Export":
        return cls(raw.mods, raw.bases, raw.bench_options, raw.essences)

    # -- bases and tags ------------------------------------------------------------------------------------------

    def base_id(self, base: str) -> str:
        """The id of a base given by id or by its English name, by the rule shared with the reconciliation checks.

        A Battle Royale copy of a name is never picked; where a name has bases on sale, one tagged `not_for_sale` is not
        picked either; of several bases left the first id counts (`independent/ladder.py`).
        """
        found = shared.base_ids_of(self.base_items, base)
        if not found:
            raise KeyError(f"no base named {base!r}")
        return found[0]

    def item_class(self, base_id: str) -> str:
        return self.base_items[base_id]["item_class"]

    def tags(self, base_id: str, influences: frozenset[str] = frozenset()) -> frozenset[str]:
        base = self.base_items[base_id]
        return shared.item_tags(base["tags"], influences, base["item_class"])

    @staticmethod
    def spawn_weight(mod: dict, tags: frozenset[str]) -> int:
        """The weight of the first spawn entry whose tag the item has; 0 when none."""
        return shared.spawn_weight(mod, tags)

    # -- the natural ladders ------------------------------------------------------------------------------------

    def is_natural(self, mod_id: str, mod: dict, tags: frozenset[str], domain: str) -> bool:
        return shared.is_natural(mod_id, mod, tags, domain)

    def ladders(self, base_id: str, influences: frozenset[str] = frozenset()) -> dict[tuple[str, str], Ladder]:
        """Every natural ladder on the base, by (mod type, generation type); each is best tier first.

        The tiers come from the ladder shared with the reconciliation checks (`independent/ladder.py`); this adds the
        required level and the stat ranges of each rung.
        """
        key = (base_id, influences)
        if key in self._ladders:
            return self._ladders[key]
        tiers_by_ladder = shared.natural_ladders(self.mods, self.tags(base_id, influences), self.base_items[base_id]["domain"])
        built: dict[tuple[str, str], Ladder] = {}
        for group_key, tiers in tiers_by_ladder.items():
            rungs = []
            for mod_id, tier in tiers.items():
                mod = self.mods[mod_id]
                stats = tuple((stat["id"], min(stat["min"], stat["max"]), max(stat["min"], stat["max"])) for stat in mod["stats"])
                rungs.append(Rung(mod_id, tier, mod["required_level"], stats))
            built[group_key] = tuple(sorted(rungs, key=lambda rung: (rung.tier, rung.mod_id)))
        self._ladders[key] = built
        return built

    def ladder_of_mod(self, base_id: str, influences: frozenset[str], mod_id: str) -> tuple[tuple[str, str], Rung] | None:
        """The ladder key and rung of a natural mod, or None when it is not natural on this item."""
        for group_key, ladder in self.ladders(base_id, influences).items():
            for rung in ladder:
                if rung.mod_id == mod_id:
                    return group_key, rung
        return None

    # -- selectors ----------------------------------------------------------------------------------------------

    def selects(self, mod_id: str, family: str | None, stat: str | None) -> bool:
        """Whether the mod is one the selector (a family id or a stat text) counts."""
        mod = self.mods.get(mod_id)
        if mod is None:
            return False
        if family is not None:
            return family in mod.get("groups", [])
        text = mod.get("text")
        return text is not None and normal_text(text) == normal_text(stat or "")

    def selected_mods(self, family: str | None, stat: str | None) -> list[str]:
        """Every prefix or suffix mod of the export the selector counts (any domain)."""
        return [
            mod_id
            for mod_id, mod in self.mods.items()
            if mod["generation_type"] in SIDES and self.selects(mod_id, family, stat)
        ]

    def selected_ladders(
        self, base_id: str, influences: frozenset[str], family: str | None, stat: str | None
    ) -> dict[tuple[str, str], Ladder]:
        """The ladders that hold at least one mod the selector counts, narrowed to those mods only when a stat text selects."""
        found = {}
        for group_key, ladder in self.ladders(base_id, influences).items():
            if any(self.selects(rung.mod_id, family, stat) for rung in ladder):
                found[group_key] = ladder
        return found


# --- the target ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OReq:
    """One wanted mod, as the YAML wrote it. `path` locates it in the file, like `requirements[2].of[0]`."""

    path: str
    family: str | None = None
    stat: str | None = None
    mod: str | None = None
    min_tier: int | None = None
    min_roll: tuple[int | None, ...] | None = None
    not_crafted: bool = False


@dataclass(frozen=True)
class OGroup:
    """A k-of-n entry: at least `at_least` of `members` are met."""

    path: str
    at_least: int
    members: tuple["ONode", ...]


ONode = OReq | OGroup


def _read_node(entry: dict, path: str) -> ONode:
    if not isinstance(entry, dict):
        raise ValueError(f"{path}: a requirement must be a mapping")
    if "at_least" in entry or "of" in entry:
        members = tuple(_read_node(member, f"{path}.of[{i}]") for i, member in enumerate(entry["of"]))
        return OGroup(path, int(entry["at_least"]), members)
    roll = entry.get("min_roll")
    if roll is not None:
        roll = tuple(roll) if isinstance(roll, list) else (roll,)
    return OReq(
        path=path,
        family=entry.get("family"),
        stat=entry.get("stat"),
        mod=entry.get("mod"),
        min_tier=entry.get("min_tier"),
        min_roll=roll,
        not_crafted=bool(entry.get("not_crafted", False)),
    )


def leaves(node: ONode):
    """Every single requirement under `node`, in file order."""
    if isinstance(node, OReq):
        yield node
    else:
        for member in node.members:
            yield from leaves(member)


@dataclass(frozen=True)
class OracleTarget:
    """What the oracle needs of a target: the base, the item level, the influences and the requirement tree."""

    base: str
    item_level: int
    influences: frozenset[str]
    requirements: tuple[ONode, ...]
    unjudged: tuple[str, ...] = field(default=())

    @classmethod
    def from_text(cls, text: str) -> "OracleTarget":
        document = yaml.safe_load(text)
        return cls(
            base=document["base"],
            item_level=int(document["item_level"]),
            influences=frozenset(document.get("influence") or ()),
            requirements=tuple(_read_node(entry, f"requirements[{i}]") for i, entry in enumerate(document["requirements"])),
            unjudged=tuple(key for key in UNJUDGED_KEYS if key in document),
        )


# --- the item -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OMod:
    """An explicit mod on an item: its id and its rolled values. Whether it was crafted is read from the export (domain `crafted`)."""

    mod_id: str
    values: tuple[int, ...]
    fractured: bool = False


@dataclass(frozen=True)
class OItem:
    mods: tuple[OMod, ...]


# --- the judge ------------------------------------------------------------------------------------------------------


class Oracle:
    """Judges the requirements of one target against items, on one export."""

    def __init__(self, export: Export, target: OracleTarget):
        self.export = export
        self.target = target
        self.base_id = export.base_id(target.base)

    # -- tiers --------------------------------------------------------------------------------------------------

    def is_crafted(self, mod: OMod) -> bool:
        return self.export.mods[mod.mod_id]["domain"] == CRAFTED_DOMAIN

    def top_tier(self, ladder: Ladder) -> int | None:
        """The best tier of the ladder that the item level allows, or None when no rung is that low a level."""
        allowed = [rung.tier for rung in ladder if rung.level <= self.target.item_level]
        return min(allowed) if allowed else None

    def tier_of(self, req: OReq, mod: OMod) -> tuple[int, int | None] | None:
        """(tier, top tier at the item level) of the item's mod on the natural ladder of the requirement, or None.

        A natural mod is read off its ladder by id. Any other mod (a crafted one, an essence-only one, a mod that
        does not spawn here) is read by its values: the best tier among the ladder's rungs, of a level the item
        level allows, whose ranges hold every value.
        """
        export, influences = self.export, self.target.influences
        own = export.ladder_of_mod(self.base_id, influences, mod.mod_id)
        if own is not None:
            group_key, rung = own
            return rung.tier, self.top_tier(export.ladders(self.base_id, influences)[group_key])
        stat_ids = tuple(stat["id"] for stat in export.mods[mod.mod_id]["stats"])
        best: tuple[int, int | None] | None = None
        for ladder in export.selected_ladders(self.base_id, influences, req.family, req.stat).values():
            for rung in ladder:
                if rung.level <= self.target.item_level and rung.holds(stat_ids, mod.values):
                    if best is None or rung.tier < best[0]:
                        best = (rung.tier, self.top_tier(ladder))
        return best

    # -- the judgement ------------------------------------------------------------------------------------------

    def counts(self, req: OReq, mod: OMod) -> bool:
        """Whether this one explicit mod satisfies the single requirement."""
        export = self.export
        if req.mod is not None:
            if mod.mod_id != req.mod:  # OR-2: exactly that mod
                return False
        elif not export.selects(mod.mod_id, req.family, req.stat):
            return False
        if req.not_crafted and self.is_crafted(mod):
            return False
        # OR-4: a stat text that states its value ("+1 to Level of all Minion Skill Gems", no `#`) is the guide's own wording of
        # the mod, not an unstated tier, so it asks no top tier; its text picks the mod.
        states_value = req.stat is not None and "#" not in normal_text(req.stat)
        if req.min_tier is not None or (req.mod is None and req.min_roll is None):
            found = self.tier_of(req, mod)
            if found is None:
                return False
            tier, top = found
            if req.min_tier is not None:
                if tier > req.min_tier:
                    return False
            elif not states_value and (top is None or tier > top):  # OR-1: no tier means the top tier the item level allows
                return False
        # OPEN POINT (#416, not settled by docs/owner-rules.md): with a `min_roll` and no tier, nothing below asks where the mod
        # came from, so a crafted mod that no requirement names counts by its roll alone (it is not judged on the ladder,
        # which OR-1 says for a crafted mod). `not_crafted: true` is the only thing that keeps it out. Behaviour kept as is.
        if req.min_roll is not None:
            if len(mod.values) != len(req.min_roll):
                return False
            if any(wanted is not None and got < wanted for wanted, got in zip(req.min_roll, mod.values)):
                return False
        return True

    def node_met(self, node: ONode, item: OItem) -> bool:
        if isinstance(node, OGroup):
            return sum(self.node_met(member, item) for member in node.members) >= node.at_least
        return any(self.counts(node, mod) for mod in item.mods)

    def requirements_met(self, item: OItem) -> bool:
        """Whether the item meets every top-level requirement (the only part of a target the oracle judges)."""
        return all(self.node_met(node, item) for node in self.target.requirements)


# --- probes -----------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbeSpec:
    """A mod to put on a probe item, described without any planner type.

    `kind` says how a game gives the mod: `natural` (rolled, any domain but crafted and not essence-only), `bench`
    (a bench craft) or `essence` (forced by an essence). `role` is `top` for the highest natural tier the item
    level allows at its highest roll, the mod a requirement should be met by. The planner side builds the item.
    """

    path: str
    label: str
    kind: str
    mod_id: str
    values: tuple[int, ...]
    fractured: bool = False
    role: str = ""


def _kind_of(export: Export, mod_id: str) -> str:
    mod = export.mods[mod_id]
    if mod["domain"] == CRAFTED_DOMAIN:
        return "bench"
    if mod.get("is_essence_only"):
        return "essence"
    return "natural"


def _low(mod: dict) -> tuple[int, ...]:
    return tuple(min(stat["min"], stat["max"]) for stat in mod["stats"])


def _high(mod: dict) -> tuple[int, ...]:
    return tuple(max(stat["min"], stat["max"]) for stat in mod["stats"])


def bench_mods(export: Export, base_id: str) -> list[str]:
    """The crafted mods the bench adds to an item of this base's class (an option with an `add_explicit_mod`)."""
    item_class = export.item_class(base_id)
    found = []
    for option in export.bench_options:
        mod_id = (option.get("actions") or {}).get("add_explicit_mod")
        if mod_id is not None and item_class in option.get("item_classes", []):
            found.append(mod_id)
    return found


def probe_specs(export: Export, target: OracleTarget) -> list[ProbeSpec]:
    """The probes of every single requirement of the target (see the ticket #411 list)."""
    oracle = Oracle(export, target)
    base_id, influences, level = oracle.base_id, target.influences, target.item_level
    specs: list[ProbeSpec] = []
    for node in target.requirements:
        for req in leaves(node):
            specs.extend(_leaf_probes(export, oracle, req, base_id, influences, level))
    return specs


def _leaf_probes(export: Export, oracle: Oracle, req: OReq, base_id: str, influences: frozenset[str], level: int) -> list[ProbeSpec]:
    out: list[ProbeSpec] = []
    seen: set[tuple] = set()

    def add(spec: ProbeSpec) -> None:
        key = (spec.kind, spec.mod_id, spec.values, spec.fractured)
        if key not in seen:
            seen.add(key)
            out.append(spec)

    ladders = export.selected_ladders(base_id, influences, req.family, req.stat)
    selector_mods = export.selected_mods(req.family, req.stat)
    stat_ids = {stat["id"] for mod_id in selector_mods for stat in export.mods[mod_id]["stats"]}

    # each natural tier of the family at its lowest and highest roll (only tiers the item level allows)
    top_specs = []
    for ladder in ladders.values():
        top = oracle.top_tier(ladder)
        for rung in ladder:
            if rung.level > level or not export.selects(rung.mod_id, req.family, req.stat):
                continue
            mod = export.mods[rung.mod_id]
            tag = f"natural T{rung.tier} {rung.mod_id}"
            add(ProbeSpec(req.path, f"{tag} low", "natural", rung.mod_id, _low(mod)))
            role = "top" if rung.tier == top else ""
            high = ProbeSpec(req.path, f"{tag} high", "natural", rung.mod_id, _high(mod), role=role)
            add(high)
            if role:
                top_specs.append(rung)
    # a fractured copy of the top tier
    for rung in top_specs:
        mod = export.mods[rung.mod_id]
        add(ProbeSpec(req.path, f"fractured natural T{rung.tier} {rung.mod_id} high", "natural", rung.mod_id, _high(mod), fractured=True))
    # a roll one below and at each min_roll, on every rung whose range holds the roll
    if req.min_roll is not None:
        for ladder in ladders.values():
            for rung in ladder:
                if rung.level > level or not export.selects(rung.mod_id, req.family, req.stat):
                    continue
                for index, wanted in enumerate(req.min_roll):
                    if wanted is None:
                        continue
                    _, low, high = rung.stats[index]
                    for value, name in ((wanted, "at"), (wanted - 1, "below")):
                        if low <= value <= high:
                            values = tuple(value if i == index else hi for i, (_, _, hi) in enumerate(rung.stats))
                            add(ProbeSpec(req.path, f"natural T{rung.tier} {rung.mod_id} roll {name} min_roll[{index}]={wanted}", "natural", rung.mod_id, values))
    # the mod a requirement names, whatever its origin (an essence mod, a bench craft, an influence or unveiled mod)
    if req.mod is not None:
        mod = export.mods[req.mod]
        kind = _kind_of(export, req.mod)
        add(ProbeSpec(req.path, f"named {kind} {req.mod} low", kind, req.mod, _low(mod)))
        add(ProbeSpec(req.path, f"named {kind} {req.mod} high", kind, req.mod, _high(mod), role="named"))
    # every bench craft whose stats overlap the requirement's
    for mod_id in bench_mods(export, base_id):
        mod = export.mods[mod_id]
        if {stat["id"] for stat in mod["stats"]} & stat_ids:
            add(ProbeSpec(req.path, f"bench {mod_id} low", "bench", mod_id, _low(mod)))
            add(ProbeSpec(req.path, f"bench {mod_id} high", "bench", mod_id, _high(mod)))
    return out
