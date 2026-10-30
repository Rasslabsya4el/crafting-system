"""From YAML text to a validated `Target`: the schema checks, with `<file>:<line>: <key path>: <problem>` errors.

Only the first problem found is reported. Within one mapping, unknown keys are reported first, then
missing keys, then each value in the order of the schema. Key paths count list entries from 0.
"""

import difflib
from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Influence, Item, ItemError, Rarity

from .errors import TargetError
from .lines import LineList, LineMap, load_with_lines
from .model import KOfN, Node, Requirement, Target
from .resolve import Resolver, Unresolved, close_matches, quoted

TOP_KEYS = ("base", "item_level", "influence", "requirements", "start_item", "price_file")
REQUIREMENT_KEYS = ("family", "stat", "min_tier", "min_roll", "not_crafted")
GROUP_KEYS = ("at_least", "of")
START_ITEM_KEYS = ("rarity", "corrupted", "mods")
START_MOD_KEYS = ("mod", "tier", "values", "fractured", "crafted")
MIN_ITEM_LEVEL = 1
MAX_ITEM_LEVEL = 100


def parse_target_text(
    text: str, data: GameData, source: str, base_dir: Path | None
) -> Target:
    """Parse and resolve the YAML `text`; `source` names the file in error messages."""
    return _Reader(data, source, base_dir).read(load_with_lines(text, source))


def describe(value: object) -> str:
    """How a value is named in an error message: text in quotes, numbers as they are, others by kind."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nothing (an empty value)"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return type(value).__name__


def is_whole(value: object) -> bool:
    return type(value) is int


class _Reader:
    def __init__(self, data: GameData, source: str, base_dir: Path | None) -> None:
        self.data = data
        self.source = source
        self.base_dir = base_dir
        self.resolver = Resolver(data)

    def fail(self, line: int, path: str, problem: str) -> NoReturn:
        where = f"{path}: " if path else ""
        raise TargetError(f"{self.source}:{line}: {where}{problem}")

    # -- reading blocks of the schema -------------------------------------------------------------

    def read(self, root: object) -> Target:
        if root is None:
            self.fail(1, "", "the file is empty; a target needs at least `base`, `item_level` and `requirements`")
        if not isinstance(root, LineMap):
            self.fail(1, "", f"the file must be a mapping of keys such as `base:`, not {describe(root)}")
        self.check_keys(root, "", TOP_KEYS)
        for key in ("base", "item_level", "requirements"):
            if key not in root:
                self.fail(root.line, key, "this key is required but missing")

        base_id = self.read_base(root)
        item_level = self.read_item_level(root)
        influences = self.read_influences(root)
        requirements = self.read_requirements(root["requirements"], "requirements", root.key_lines["requirements"])
        start_item = self.read_start_item(root, base_id, item_level, influences)
        price_file = self.read_price_file(root)
        return Target(base_id, item_level, influences, requirements, start_item, price_file)

    def read_base(self, root: LineMap) -> str:
        name = self.text(root, "base", "base")
        try:
            return self.resolver.base_id(name)
        except Unresolved as problem:
            self.fail(root.key_lines["base"], "base", str(problem))

    def read_item_level(self, root: LineMap) -> int:
        value = root["item_level"]
        if not is_whole(value) or not MIN_ITEM_LEVEL <= value <= MAX_ITEM_LEVEL:
            self.fail(
                root.key_lines["item_level"],
                "item_level",
                f"must be a whole number from {MIN_ITEM_LEVEL} to {MAX_ITEM_LEVEL}, got {describe(value)}",
            )
        return value

    def read_influences(self, root: LineMap) -> frozenset[Influence]:
        if "influence" not in root:
            return frozenset()
        line = root.key_lines["influence"]
        names = root["influence"]
        if not isinstance(names, LineList):
            self.fail(line, "influence", f"must be a list such as [shaper, elder], got {describe(names)}")
        found = set()
        for index, name in enumerate(names):
            path = f"influence[{index}]"
            allowed = [influence.value for influence in Influence]
            if not isinstance(name, str) or name.lower() not in allowed:
                self.fail(names.item_lines[index], path, f"must be one of {quoted(allowed)}, got {describe(name)}")
            found.add(Influence(name.lower()))
        return frozenset(found)

    def read_price_file(self, root: LineMap) -> Path | None:
        if "price_file" not in root:
            return None
        name = self.text(root, "price_file", "price_file")
        path = Path(name)
        return self.base_dir / path if self.base_dir is not None else path

    # -- requirements ------------------------------------------------------------------------------

    def read_requirements(self, entries: object, path: str, line: int) -> tuple[Node, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, path, f"must be a list of requirements, got {describe(entries)}")
        if not entries:
            self.fail(line, path, "must hold at least one requirement")
        return tuple(
            self.read_node(entry, f"{path}[{index}]", entries.item_lines[index])
            for index, entry in enumerate(entries)
        )

    def read_node(self, entry: object, path: str, line: int) -> Node:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping (`family:` or `stat:` or `at_least:` and `of:`), got {describe(entry)}")
        if "at_least" in entry or "of" in entry:
            return self.read_group(entry, path)
        return self.read_requirement(entry, path)

    def read_group(self, entry: LineMap, path: str) -> KOfN:
        self.check_keys(entry, path, GROUP_KEYS)
        for key in GROUP_KEYS:
            if key not in entry:
                self.fail(entry.line, f"{path}.{key}", "a k-of-n entry needs both `at_least` and `of`; this key is missing")
        members = entry["of"]
        of_path = f"{path}.of"
        if not isinstance(members, LineList):
            self.fail(entry.key_lines["of"], of_path, f"must be a list of requirements, got {describe(members)}")
        if not members:
            self.fail(entry.key_lines["of"], of_path, "must list at least one requirement")
        count = entry["at_least"]
        if not is_whole(count) or not 1 <= count <= len(members):
            self.fail(
                entry.key_lines["at_least"],
                f"{path}.at_least",
                f"must be a whole number from 1 to {len(members)} (the number of entries in `of`), got {describe(count)}",
            )
        nodes = tuple(
            self.read_node(member, f"{of_path}[{index}]", members.item_lines[index])
            for index, member in enumerate(members)
        )
        return KOfN(count, nodes)

    def read_requirement(self, entry: LineMap, path: str) -> Requirement:
        self.check_keys(entry, path, REQUIREMENT_KEYS)
        if "family" in entry and "stat" in entry:
            self.fail(entry.line, path, "give either `family` or `stat`, not both")
        if "family" not in entry and "stat" not in entry:
            self.fail(entry.line, path, 'name the mod with `family: <family id>` or `stat: "<English stat text>"`')

        family = stat = None
        selector = "family" if "family" in entry else "stat"
        text = self.text(entry, selector, f"{path}.{selector}")
        line = entry.key_lines[selector]
        try:
            if selector == "family":
                family, mod_ids = text, self.resolver.mods_for_family(text)
            else:
                stat, mod_ids = text, self.resolver.mods_for_stat(text)
        except Unresolved as problem:
            self.fail(line, f"{path}.{selector}", str(problem))

        min_tier = None
        if "min_tier" in entry:
            min_tier = entry["min_tier"]
            if not is_whole(min_tier) or min_tier < 1:
                self.fail(
                    entry.key_lines["min_tier"],
                    f"{path}.min_tier",
                    f"must be a whole number of 1 or more, got {describe(min_tier)}",
                )
        not_crafted = False
        if "not_crafted" in entry:
            not_crafted = entry["not_crafted"]
            if not isinstance(not_crafted, bool):
                self.fail(
                    entry.key_lines["not_crafted"],
                    f"{path}.not_crafted",
                    f"must be true or false, got {describe(not_crafted)}",
                )
        min_roll = None
        if "min_roll" in entry:
            min_roll = self.read_min_roll(entry, f"{path}.min_roll", mod_ids)
        return Requirement(family, stat, mod_ids, min_tier, min_roll, not_crafted)

    def read_min_roll(self, entry: LineMap, path: str, mod_ids: frozenset[str]) -> tuple[int | None, ...]:
        line = entry.key_lines["min_roll"]
        value = entry["min_roll"]
        counts = sorted({len(self.data.mods[mod_id].stats) for mod_id in mod_ids})
        if len(counts) > 1:
            self.fail(
                line,
                path,
                "the mods chosen by this selector have different numbers of stats"
                f" ({', '.join(map(str, counts))}), so one list of minimum rolls cannot fit them all;"
                " choose a selector whose mods all have the same stats",
            )
        stats = counts[0]
        if isinstance(value, LineList):
            if len(value) != stats:
                self.fail(
                    line,
                    path,
                    f"the mod has {stats} stat(s), so the list needs exactly {stats} entr{'y' if stats == 1 else 'ies'}"
                    f" (a whole number or null for each), got {len(value)}",
                )
            rolls = tuple(
                self.read_roll(item, f"{path}[{index}]", value.item_lines[index])
                for index, item in enumerate(value)
            )
        else:
            if not is_whole(value):
                self.fail(line, path, f"must be a whole number or a list with one number or null per stat, got {describe(value)}")
            if stats != 1:
                self.fail(
                    line,
                    path,
                    f"the mod has {stats} stats, so give a list with one whole number or null per stat,"
                    f" for example [{', '.join(['null'] * stats)}]",
                )
            rolls = (value,)
        for index, wanted in enumerate(rolls):
            if wanted is None:
                continue
            best = max(
                max(self.data.mods[mod_id].stats[index].min, self.data.mods[mod_id].stats[index].max)
                for mod_id in mod_ids
            )
            if wanted > best:
                where = f"{path}[{index}]" if isinstance(value, LineList) else path
                self.fail(line, where, f"{wanted} is above the best roll any of these mods can give, which is {best}")
        return rolls

    def read_roll(self, value: object, path: str, line: int) -> int | None:
        if value is not None and not is_whole(value):
            self.fail(line, path, f"must be a whole number or null, got {describe(value)}")
        return value

    # -- the start item ----------------------------------------------------------------------------

    def read_start_item(
        self, root: LineMap, base_id: str, item_level: int, influences: frozenset[Influence]
    ) -> Item:
        line = root.key_lines.get("start_item", root.key_lines["base"])
        fields: dict[str, object] = {"rarity": Rarity.NORMAL}
        mods: tuple[ExplicitMod, ...] = ()
        if "start_item" in root:
            start = root["start_item"]
            line = root.key_lines["start_item"]
            if not isinstance(start, LineMap):
                self.fail(line, "start_item", f"must be a mapping with `rarity`, `corrupted` and `mods`, got {describe(start)}")
            self.check_keys(start, "start_item", START_ITEM_KEYS)
            if "mods" in start:
                mods = self.read_start_mods(start["mods"], start.key_lines["mods"])
            fields["rarity"] = self.read_rarity(start, bool(mods))
            if "corrupted" in start:
                if not isinstance(start["corrupted"], bool):
                    self.fail(
                        start.key_lines["corrupted"],
                        "start_item.corrupted",
                        f"must be true or false, got {describe(start['corrupted'])}",
                    )
                fields["corrupted"] = start["corrupted"]
        try:
            return Item.build(
                self.data, base_id=base_id, item_level=item_level, mods=mods, influences=influences, **fields
            )
        except ItemError as problem:
            self.fail(line, "start_item", str(problem))

    def read_rarity(self, start: LineMap, has_mods: bool) -> Rarity:
        if "rarity" not in start:
            return Rarity.RARE if has_mods else Rarity.NORMAL
        allowed = [rarity.value for rarity in Rarity]
        value = start["rarity"]
        if not isinstance(value, str) or value.lower() not in allowed:
            self.fail(start.key_lines["rarity"], "start_item.rarity", f"must be one of {quoted(allowed)}, got {describe(value)}")
        return Rarity(value.lower())

    def read_start_mods(self, entries: object, line: int) -> tuple[ExplicitMod, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, "start_item.mods", f"must be a list of mods, got {describe(entries)}")
        return tuple(
            self.read_start_mod(entry, f"start_item.mods[{index}]", entries.item_lines[index])
            for index, entry in enumerate(entries)
        )

    def read_start_mod(self, entry: object, path: str, line: int) -> ExplicitMod:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping with `mod`, `tier` and `values`, got {describe(entry)}")
        self.check_keys(entry, path, START_MOD_KEYS)
        for key in ("mod", "tier", "values"):
            if key not in entry:
                self.fail(entry.line, f"{path}.{key}", "this key is required but missing")
        mod_id = self.text(entry, "mod", f"{path}.mod")
        if mod_id not in self.data.mods:
            near = close_matches(mod_id, self.data.mods)
            hint = f"; did you mean {quoted(near)}?" if near else ""
            self.fail(entry.key_lines["mod"], f"{path}.mod", f"`{mod_id}` is not a mod id in the game data{hint}")
        tier = entry["tier"]
        if not is_whole(tier) or tier < 1:
            self.fail(entry.key_lines["tier"], f"{path}.tier", f"must be a whole number of 1 or more, got {describe(tier)}")
        values = self.read_values(entry["values"], f"{path}.values", entry.key_lines["values"])
        flags = {}
        for key in ("fractured", "crafted"):
            if key in entry:
                if not isinstance(entry[key], bool):
                    self.fail(entry.key_lines[key], f"{path}.{key}", f"must be true or false, got {describe(entry[key])}")
                flags[key] = entry[key]
        return ExplicitMod(mod_id, tier, values, **flags)

    def read_values(self, value: object, path: str, line: int) -> tuple[int, ...]:
        if is_whole(value):
            return (value,)
        if not isinstance(value, LineList):
            self.fail(line, path, f"must be a whole number or a list of whole numbers, got {describe(value)}")
        for index, number in enumerate(value):
            if not is_whole(number):
                self.fail(value.item_lines[index], f"{path}[{index}]", f"must be a whole number, got {describe(number)}")
        return tuple(value)

    # -- small checks -------------------------------------------------------------------------------

    def text(self, mapping: LineMap, key: str, path: str) -> str:
        value = mapping[key]
        if not isinstance(value, str) or not value.strip():
            self.fail(mapping.key_lines[key], path, f"must be non-empty text, got {describe(value)}")
        return value

    def check_keys(self, mapping: LineMap, path: str, allowed: Iterable[str]) -> None:
        allowed = tuple(allowed)
        for key in mapping:
            if key in allowed:
                continue
            near = difflib.get_close_matches(key, allowed, n=1)
            hint = f"did you mean `{near[0]}`?" if near else f"the keys allowed here are {quoted(allowed)}"
            where = f"{path}.{key}" if path else key
            self.fail(mapping.key_lines[key], where, f"unknown key `{key}`; {hint}")
