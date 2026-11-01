"""From YAML text to a validated `Target`: the schema checks, with `<file>:<line>: <key path>: <problem>` errors.

Only the first problem found is reported. Within one mapping, unknown keys are reported first, then
missing keys, then each value in the order of the schema. Key paths count list entries from 0.
"""

import difflib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

from crafting_system.data import BaseItem, GameData
from crafting_system.items import (
    CATALYST_ITEM_CLASSES,
    MAX_MEMORY_STRANDS,
    MAX_PLAIN_QUALITY,
    MAX_QUALITY,
    MAX_SOCKETS,
    PLAIN_QUALITY_ITEM_CLASSES,
    CatalystType,
    ExplicitMod,
    ImplicitError,
    EnchantmentError,
    ImplicitMod,
    Influence,
    Item,
    ItemError,
    MemoryStrandsError,
    PlainQuality,
    Quality,
    QualityError,
    Rarity,
    SocketColour,
    SocketError,
    Sockets,
    VeilOfferError,
    class_maximum,
    eldritch_grade,
    eldritch_side,
    enchant_class,
    has_abyssal_socket,
    is_abyssal_socket_mod,
    has_memory_strands_line,
    read_memory_strands,
    spawn_weight,
    veiled_placeholder,
)

from .corrupted import CorruptedResolver, corruption_problem
from .enchantment import EnchantmentResolver
from .errors import TargetError
from .lines import LineList, LineMap, load_with_lines
from .model import (
    EnchantmentRequirement,
    ImplicitRequirement,
    KOfN,
    Node,
    PlainQualityRequirement,
    QualityRequirement,
    Requirement,
    SocketRequirement,
    Target,
)
from .resolve import Resolver, Unresolved, close_matches, quoted

TOP_KEYS = (
    "base",
    "item_level",
    "influence",
    "requirements",
    "implicits",
    "quality",
    "sockets",
    "enchantment",
    "start_item",
    "start_price",
    "price_file",
    "actions",
    "allow_corrupted",
    "item_level_floor",
    "tiers_top_at_item_level",
)
REQUIREMENT_KEYS = ("family", "stat", "mod", "min_tier", "min_roll", "not_crafted")
IMPLICIT_KEYS = ("family", "stat", "mod", "min_grade", "min_roll", "corrupted")
QUALITY_KEYS = ("type", "min_percent")
SOCKET_KEYS = ("count", "links", "colours")
SOCKET_COLOUR_KEYS = ("R", "G", "B")
START_SOCKET_KEYS = ("count", "colours", "links")
MIN_LINKS = 2
BUYABLE_QUALITY = 20
ENCHANTMENT_KEYS = ("any_of",)
GROUP_KEYS = ("at_least", "of")
START_ITEM_KEYS = (
    "rarity", "corrupted", "mods", "implicits", "quality", "sockets", "enchantment", "veil_offer", "memory_strands",
)  # fmt: skip
START_MOD_KEYS = ("mod", "tier", "values", "fractured", "crafted")
START_IMPLICIT_KEYS = ("mod", "values", "grade")
START_QUALITY_KEYS = ("type", "percent")
VEILED_DOMAIN = "veiled"
BASE_GRADE = 0
MIN_ELDRITCH_GRADE = 1
MAX_ELDRITCH_GRADE = 6
MIN_ITEM_LEVEL = 1
MAX_ITEM_LEVEL = 100
MAX_GROUP_DEPTH = 20
ONE_ENCHANTMENT = (
    "an item holds one enchantment, so a target cannot ask for two at once;"
    " list the enchants that would do under `any_of`"
)
UNREACHABLE_ENCHANTMENT = (
    "this enchantment cannot be reached by clicking orbs; give a start item that already has it, with its price"
)


def parse_target_text(
    text: str, data: GameData, source: str, base_dir: Path | None
) -> Target:
    """Parse and resolve the YAML `text`; `source` names the file in error messages."""
    try:
        return _Reader(data, source, base_dir).read(load_with_lines(text, source))
    except RecursionError:
        raise TargetError(f"{source}:1: the file is nested too deeply to read") from None


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


def blamed_mod(message: str, mods: tuple[ExplicitMod, ...]) -> int | None:
    """The index of the written mod whose id the item error `message` names first, if any."""
    return blamed_id(message, [mod.mod_id for mod in mods])


def blamed_id(message: str, ids: Iterable[str], *, last_written: bool = False) -> int | None:
    """The index of the written id the item error `message` names, if any.

    Of several named ids it is the one named first, or the one written last in the file when
    `last_written` is set (the entry that clashes with an earlier one). An id written twice counts
    as its first entry, or as its last one with `last_written`.
    """
    found = []
    for index, mod_id in enumerate(ids):
        match = re.search(rf"(?<!\w){re.escape(mod_id)}(?!\w)", message)
        if match:
            found.append((match.start(), index))
    if not found:
        return None
    if last_written:
        return max(index for _, index in found)
    return min(found)[1]


class _Reader:
    def __init__(self, data: GameData, source: str, base_dir: Path | None) -> None:
        self.data = data
        self.source = source
        self.base_dir = base_dir
        self.resolver = Resolver(data)
        self.corrupted = CorruptedResolver(self.resolver)

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
        implicits = (
            self.read_implicits(root["implicits"], root.key_lines["implicits"], base_id, item_level) if "implicits" in root else ()
        )
        quality = None
        if "quality" in root:
            quality = self.read_quality(root["quality"], root.key_lines["quality"], base_id)
            if isinstance(quality, QualityRequirement):
                self.check_catalyst_base(base_id, root.key_lines["quality"])
        sockets = None
        if "sockets" in root:
            sockets = self.read_sockets(root["sockets"], root.key_lines["sockets"], base_id)
        enchantment = None
        if "enchantment" in root:
            enchantment = self.read_enchantment(root["enchantment"], root.key_lines["enchantment"], base_id)
        stated = "start_item" in root and isinstance(root["start_item"], LineMap) and "sockets" in root["start_item"]
        assumed = sockets is not None and not stated
        start_item = self.read_start_item(root, base_id, item_level, influences, assume_socket=assumed)
        if isinstance(quality, PlainQualityRequirement):
            self.check_plain_quality_reachable(root["quality"], quality, start_item)
        if enchantment is not None:
            self.check_enchantment_reachable(root["enchantment"], enchantment, base_id, start_item)
        price_file = self.read_price_file(root)
        start_price = self.text(root, "start_price", "start_price") if "start_price" in root else None
        actions = self.read_actions(root["actions"], root.key_lines["actions"]) if "actions" in root else None
        allow_corrupted = self.read_allow_corrupted(root) if "allow_corrupted" in root else False
        self.check_corruption(root, base_id, item_level, implicits, allow_corrupted, start_item, start_price, actions)
        item_level_floor = self.read_item_level_floor(root, item_level) if "item_level_floor" in root else None
        tiers_top = self.read_tiers_top(root) if "tiers_top_at_item_level" in root else False
        if sockets is not None:
            self.check_socket_scope(root, requirements, start_item)
        return Target(
            base_id, item_level, influences, requirements, start_item, price_file, start_price, implicits, quality,
            actions, enchantment, allow_corrupted, sockets, assumed, item_level_floor, tiers_top,
        )  # fmt: skip

    def read_item_level_floor(self, root: LineMap, item_level: int) -> int:
        value = root["item_level_floor"]
        if not is_whole(value) or not MIN_ITEM_LEVEL <= value <= item_level:
            self.fail(
                root.key_lines["item_level_floor"],
                "item_level_floor",
                f"must be a whole number from {MIN_ITEM_LEVEL} to the item level ({item_level}), got {describe(value)}",
            )
        return value

    def read_tiers_top(self, root: LineMap) -> bool:
        value = root["tiers_top_at_item_level"]
        if not isinstance(value, bool):
            self.fail(root.key_lines["tiers_top_at_item_level"], "tiers_top_at_item_level", f"must be true or false, got {describe(value)}")
        return value

    def read_allow_corrupted(self, root: LineMap) -> bool:
        value = root["allow_corrupted"]
        if not isinstance(value, bool):
            self.fail(root.key_lines["allow_corrupted"], "allow_corrupted", f"must be true or false, got {describe(value)}")
        return value

    def check_corruption(
        self,
        root: LineMap,
        base_id: str,
        item_level: int,
        implicits: tuple[ImplicitRequirement, ...],
        allow_corrupted: bool,
        start_item: Item,
        start_price: str | None,
        actions: tuple[str, ...] | None,
    ) -> None:
        """Refuse a target whose corrupted implicits, corrupted start item or `actions:` make the goal impossible (ADR-0036).

        A target buys its item when it prices the start item (`start_price`) or the start item is corrupted itself.
        """
        buys = start_price is not None or start_item.corrupted
        problem = corruption_problem(
            self.data, base_id, item_level, implicits, allow_corrupted, start_item, buys, actions
        )
        if problem is None:
            return
        if problem.index is not None:
            self.fail(root["implicits"].item_lines[problem.index], f"implicits[{problem.index}]", problem.message)
        start = root["start_item"]
        self.fail(start.key_lines["corrupted"], problem.key, problem.message)

    def read_actions(self, names: object, line: int) -> tuple[str, ...]:
        if not isinstance(names, LineList) or not len(names):
            self.fail(line, "actions", f"must be a non-empty list of action kinds such as [chaos-orb] (or action labels), got {describe(names)}")
        found: dict[str, int] = {}
        for index, name in enumerate(names):
            path = f"actions[{index}]"
            if not isinstance(name, str) or not name.strip():
                self.fail(names.item_lines[index], path, f"must be the name of an action kind or the label of an action (non-empty text), got {describe(name)}")
            if name.strip() in found:
                self.fail(names.item_lines[index], path, f"{describe(name)} is listed twice (first at actions[{found[name.strip()]}])")
            found[name.strip()] = index
        return tuple(found)

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
        first_seen: dict[Influence, int] = {}
        for index, name in enumerate(names):
            path = f"influence[{index}]"
            allowed = [influence.value for influence in Influence]
            if not isinstance(name, str) or name.lower() not in allowed:
                self.fail(names.item_lines[index], path, f"must be one of {quoted(allowed)}, got {describe(name)}")
            influence = Influence(name.lower())
            if influence in first_seen:
                self.fail(
                    names.item_lines[index],
                    path,
                    f"{describe(name)} is listed twice (first at influence[{first_seen[influence]}])",
                )
            first_seen[influence] = index
        return frozenset(first_seen)

    def read_price_file(self, root: LineMap) -> Path | None:
        if "price_file" not in root:
            return None
        name = self.text(root, "price_file", "price_file")
        if "\x00" in name:
            self.fail(root.key_lines["price_file"], "price_file", "is not a valid path (it contains a NUL character)")
        path = Path(name)
        return self.base_dir / path if self.base_dir is not None else path

    # -- requirements ------------------------------------------------------------------------------

    def read_requirements(self, entries: object, path: str, line: int) -> tuple[Node, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, path, f"must be a list of requirements, got {describe(entries)}")
        if not entries:
            self.fail(line, path, "must hold at least one requirement")
        return tuple(
            self.read_node(entry, f"{path}[{index}]", entries.item_lines[index], 0)
            for index, entry in enumerate(entries)
        )

    def read_node(self, entry: object, path: str, line: int, depth: int) -> Node:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping (`family:` or `stat:` or `at_least:` and `of:`), got {describe(entry)}")
        if "at_least" in entry or "of" in entry:
            return self.read_group(entry, path, depth)
        return self.read_requirement(entry, path)

    def read_group(self, entry: LineMap, path: str, depth: int) -> KOfN:
        if depth >= MAX_GROUP_DEPTH:
            self.fail(
                entry.line, path, f"at_least groups are nested too deeply; at most {MAX_GROUP_DEPTH} levels are allowed"
            )
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
            self.read_node(member, f"{of_path}[{index}]", members.item_lines[index], depth + 1)
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

        if "mod" in entry:  # one mod of the selector: exactly that tier of it
            mod_id = self.text(entry, "mod", f"{path}.mod")
            if mod_id not in mod_ids:
                self.fail(entry.key_lines["mod"], f"{path}.mod", f"`{mod_id}` is not a mod of the {selector} `{text}`")
            mod_ids = frozenset({mod_id})
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

    # -- implicits and quality -----------------------------------------------------------------------

    def read_implicits(self, entries: object, line: int, base_id: str, item_level: int) -> tuple[ImplicitRequirement, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, "implicits", f"must be a list of implicit requirements, got {describe(entries)}")
        if not entries:
            self.fail(line, "implicits", "must hold at least one implicit requirement")
        return tuple(
            self.read_implicit(entry, f"implicits[{index}]", entries.item_lines[index], base_id, item_level)
            for index, entry in enumerate(entries)
        )

    def read_implicit(self, entry: object, path: str, line: int, base_id: str, item_level: int) -> ImplicitRequirement:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping (`family:` or `stat:`, then `mod`, `min_grade`, `min_roll`), got {describe(entry)}")
        self.check_keys(entry, path, IMPLICIT_KEYS)
        if "family" in entry and "stat" in entry:
            self.fail(entry.line, path, "give either `family` or `stat`, not both")
        if "family" not in entry and "stat" not in entry:
            self.fail(entry.line, path, 'name the implicit with `family: <family id>` or `stat: "<English stat text>"`')

        corrupted = False
        if "corrupted" in entry:
            corrupted = entry["corrupted"]
            if not isinstance(corrupted, bool):
                self.fail(
                    entry.key_lines["corrupted"], f"{path}.corrupted", f"must be true or false, got {describe(corrupted)}"
                )
        family = stat = None
        selector = "family" if "family" in entry else "stat"
        text = self.text(entry, selector, f"{path}.{selector}")
        try:
            if selector == "family":
                family = text
                if corrupted:  # among the corrupted pool of the base at the target's item level, and only there
                    mod_ids = every_mod = self.corrupted.for_family(base_id, item_level, text)
                else:
                    mod_ids = self.resolver.implicit_mods_for_family(text)
                    every_mod = self.resolver.implicit_mods_for_family(text, with_presence=True)
            else:
                stat = text
                if corrupted:
                    mod_ids = every_mod = self.corrupted.for_stat(base_id, item_level, text)
                else:
                    mod_ids = self.resolver.implicit_mods_for_stat(text)
                    every_mod = self.resolver.implicit_mods_for_stat(text, with_presence=True)
        except Unresolved as problem:
            self.fail(entry.key_lines[selector], f"{path}.{selector}", str(problem))

        if "mod" in entry:  # one mod of the selector, a presence variant included: exactly that one
            mod_id = self.text(entry, "mod", f"{path}.mod")
            if corrupted and mod_id not in every_mod:
                try:
                    reason = self.corrupted.explain_mod(base_id, item_level, mod_id, selector, text)
                except Unresolved as problem:
                    reason = str(problem)
                self.fail(entry.key_lines["mod"], f"{path}.mod", reason)
            if mod_id not in every_mod:
                self.fail(
                    entry.key_lines["mod"],
                    f"{path}.mod",
                    f"`{mod_id}` is not an implicit mod of the {selector} `{text}`; `mod` may name any mod it"
                    " selects, and a target on a \"Presence\" variant (one that needs a Unique Enemy or a Pinnacle"
                    " Boss in your Presence) must name the variant that way",
                )
            mod_ids = frozenset({mod_id})
        if not corrupted:
            self.check_implicit_possible(base_id, mod_ids, entry.key_lines[selector], f"{path}.{selector}")
        min_grade = None
        if "min_grade" in entry:
            min_grade = self.read_min_grade(entry, f"{path}.min_grade", mod_ids)
        min_roll = None
        if "min_roll" in entry:
            min_roll = self.read_min_roll(entry, f"{path}.min_roll", mod_ids)
        return ImplicitRequirement(family, stat, mod_ids, min_grade, min_roll, corrupted)

    def check_implicit_possible(self, base_id: str, mod_ids: frozenset[str], line: int, path: str) -> None:
        """Refuse an implicit selector none of whose mods can be on the base: it could never be met.

        A mod can be there if the base lists it as its own implicit, or it is an Eldritch implicit with a
        spawn weight above 0 on the base's tags (any grade or variant of it counts).
        """
        base = self.data.base_items[base_id]
        if any(self.can_be_implicit_of(base, mod_id) for mod_id in mod_ids):
            return
        kinds = []
        if base.implicits:
            kinds.append(f"its own implicit {quoted(base.implicits)}")
        if any(self.can_be_implicit_of(base, mod.id) for mod in self.data.mods.values() if eldritch_side(mod)):
            kinds.append("Eldritch implicits")
        self.fail(
            line,
            path,
            f"no implicit this selector chooses can be on {base.name} ({base.item_class}), so it could never"
            f" be met; this base can have {' and '.join(kinds) if kinds else 'no implicits'}",
        )

    def can_be_implicit_of(self, base: BaseItem, mod_id: str) -> bool:
        if mod_id in base.implicits:
            return True
        mod = self.data.mods[mod_id]
        return eldritch_side(mod) is not None and spawn_weight(mod, base.tags) > 0

    def check_catalyst_base(self, base_id: str, line: int) -> None:
        """Refuse `quality:` on a base whose item class takes no catalyst: it could never be met."""
        base = self.data.base_items[base_id]
        if base.item_class not in CATALYST_ITEM_CLASSES:
            self.fail(
                line,
                "quality",
                f"{base.name} is a {base.item_class}, and catalyst quality can only be put on"
                f" {', '.join(sorted(CATALYST_ITEM_CLASSES))}, so it could never be met"
                + ("; a weapon or armour has plain quality: leave `type` out" if base.item_class in PLAIN_QUALITY_ITEM_CLASSES else ""),
            )

    def read_min_grade(self, entry: LineMap, path: str, mod_ids: frozenset[str]) -> int:
        line = entry.key_lines["min_grade"]
        value = entry["min_grade"]
        if not is_whole(value) or not MIN_ELDRITCH_GRADE <= value <= MAX_ELDRITCH_GRADE:
            self.fail(
                line,
                path,
                f"must be a whole number from {MIN_ELDRITCH_GRADE} (Lesser) to {MAX_ELDRITCH_GRADE} (Perfect), got {describe(value)}",
            )
        plain = sorted(mod_id for mod_id in mod_ids if eldritch_side(self.data.mods[mod_id]) is None)
        if plain:
            shown = quoted(plain[:3]) + (", ..." if len(plain) > 3 else "")
            self.fail(
                line,
                path,
                f"only an Eldritch implicit has a grade, but this selector also chooses {shown}, which is not one;"
                " narrow the selector (for example with `mod`) or leave `min_grade` out",
            )
        try:
            best = max(eldritch_grade(self.data.mods[mod_id]) or 0 for mod_id in mod_ids)
        except ImplicitError as problem:
            self.fail(line, path, str(problem))
        if value > best:
            self.fail(line, path, f"{value} is above the best grade any of these mods has, which is {best}")
        return value

    def read_quality(self, entry: object, line: int, base_id: str) -> QualityRequirement | PlainQualityRequirement:
        plain_class = self.data.base_items[base_id].item_class in PLAIN_QUALITY_ITEM_CLASSES
        if not isinstance(entry, LineMap):
            keys = "`min_percent` (a weapon or armour has plain quality, no `type`)" if plain_class else "`type` and `min_percent`"
            self.fail(line, "quality", f"must be a mapping with {keys}, got {describe(entry)}")
        self.check_keys(entry, "quality", QUALITY_KEYS)
        if plain_class and "type" not in entry:
            return self.read_plain_quality(entry)
        if plain_class:  # a `type` on a weapon or armour is the catalyst form, which only jewellery takes: say so before any number
            self.check_catalyst_base(base_id, line)
        for key in QUALITY_KEYS:
            if key not in entry:
                self.fail(entry.line, f"quality.{key}", "this key is required but missing")
        catalyst = self.read_catalyst(entry, "quality.type")
        percent = entry["min_percent"]
        if not is_whole(percent) or not 1 <= percent <= MAX_QUALITY:
            self.fail(
                entry.key_lines["min_percent"],
                "quality.min_percent",
                f"must be a whole number from 1 to {MAX_QUALITY}, got {describe(percent)}",
            )
        return QualityRequirement(catalyst, percent)

    def read_plain_quality(self, entry: LineMap) -> PlainQualityRequirement:
        """`quality: {min_percent}` of a weapon or armour (ADR-0049): whole 1 to 30; the currencies stop at 20, which is checked against the start item later."""
        if "min_percent" not in entry:
            self.fail(entry.line, "quality.min_percent", "this key is required but missing")
        percent = entry["min_percent"]
        if not is_whole(percent) or not 1 <= percent <= MAX_PLAIN_QUALITY:
            self.fail(
                entry.key_lines["min_percent"],
                "quality.min_percent",
                f"must be a whole number from 1 to {MAX_PLAIN_QUALITY}, got {describe(percent)}",
            )
        return PlainQualityRequirement(percent)

    def check_plain_quality_reachable(self, entry: LineMap, wanted: PlainQualityRequirement, start_item: Item) -> None:
        """Refuse a plain quality above what Whetstones and Scraps give unless the start item already holds it: no orb is planned above 20%."""
        held = start_item.quality.percent if isinstance(start_item.quality, PlainQuality) else 0
        if wanted.min_percent > BUYABLE_QUALITY and held < wanted.min_percent:
            self.fail(
                entry.key_lines["min_percent"],
                "quality.min_percent",
                f"{wanted.min_percent}% is more than the {BUYABLE_QUALITY}% that Blacksmith's Whetstones and Armourer's Scraps raise"
                " quality to, so only a start item that already holds that much can meet it; ask for"
                f" {BUYABLE_QUALITY} or less, or give `start_item.quality.percent` of {wanted.min_percent} or more",
            )

    def read_catalyst(self, entry: LineMap, path: str) -> CatalystType:
        allowed = [catalyst.value for catalyst in CatalystType]
        value = entry["type"]
        if not isinstance(value, str) or value.strip().lower() not in allowed:
            self.fail(entry.key_lines["type"], path, f"must be one of {quoted(allowed)}, got {describe(value)}")
        return CatalystType(value.strip().lower())

    # -- the sockets -----------------------------------------------------------------------------------

    def read_sockets(self, entry: object, line: int, base_id: str) -> SocketRequirement:
        """`sockets: {count, links, colours: {R, G, B}}` (ADR-0046): the shape, then the base, then how the keys fit together and the class maximum."""
        if not isinstance(entry, LineMap):
            self.fail(line, "sockets", f"must be a mapping with `count`, `links` and `colours`, got {describe(entry)}")
        self.check_keys(entry, "sockets", SOCKET_KEYS)
        if not len(entry):
            self.fail(line, "sockets", "name at least one of `count`, `links` and `colours`; an empty mapping asks for nothing")
        base = self.data.base_items[base_id]
        most = class_maximum(base)
        if most is None:
            self.fail(line, "sockets", self.no_socket_table(base))
        count = self.read_socket_number(entry, "count", "sockets.count", 1)
        links = self.read_socket_number(entry, "links", "sockets.links", MIN_LINKS)
        colours = self.read_socket_colours(entry["colours"], entry.key_lines["colours"]) if "colours" in entry else (0, 0, 0)
        wanted = SocketRequirement(count, links, *colours)
        self.check_socket_fit(entry, wanted)
        sizes = {
            "count": (wanted.count, f"{wanted.count} sockets"),
            "links": (wanted.links, f"a linked group of {wanted.links}"),
            "colours": (wanted.coloured or None, f"{wanted.coloured} coloured sockets"),
        }
        for key, (value, what) in sizes.items():
            if value is not None and value > most:
                self.fail(
                    entry.key_lines[key],
                    f"sockets.{key}",
                    f"{what} is more than the class maximum of {most} sockets: {base.name} is of item class {base.item_class},"
                    f" and none of that class can have more than {most}",
                )
        return wanted

    def read_socket_number(self, entry: LineMap, key: str, path: str, low: int) -> int | None:
        if key not in entry:
            return None
        value = entry[key]
        if not is_whole(value) or not low <= value <= MAX_SOCKETS:
            meaning = " (a group of one socket is no link)" if low > 1 else ""
            self.fail(
                entry.key_lines[key], path, f"must be a whole number from {low} to {MAX_SOCKETS}{meaning}, got {describe(value)}"
            )
        return value

    def read_socket_colours(self, entry: object, line: int) -> tuple[int, int, int]:
        if not isinstance(entry, LineMap):
            self.fail(line, "sockets.colours", f"must be a mapping with `R`, `G` and `B` counts, got {describe(entry)}")
        self.check_keys(entry, "sockets.colours", SOCKET_COLOUR_KEYS)
        if not len(entry):
            self.fail(line, "sockets.colours", "name at least one of `R`, `G` and `B`; an empty mapping asks for nothing")
        counts = []
        for key in SOCKET_COLOUR_KEYS:
            if key not in entry:
                counts.append(0)
                continue
            value = entry[key]
            if not is_whole(value) or not 1 <= value <= MAX_SOCKETS:
                self.fail(
                    entry.key_lines[key],
                    f"sockets.colours.{key}",
                    f"must be a whole number from 1 to {MAX_SOCKETS} (leave the colour out to ask for none), got {describe(value)}",
                )
            counts.append(value)
        return counts[0], counts[1], counts[2]

    def check_socket_fit(self, entry: LineMap, wanted: SocketRequirement) -> None:
        """Refuse keys that cannot hold together: links above count, colours above links (or above count when no links are given)."""
        if wanted.count is not None and wanted.links is not None and wanted.links > wanted.count:
            self.fail(
                entry.key_lines["links"],
                "sockets.links",
                f"a linked group of {wanted.links} does not fit in `count` {wanted.count} sockets; ask for a smaller group"
                " or more sockets",
            )
        shown = f"{wanted.coloured} coloured sockets (R {wanted.red}, G {wanted.green}, B {wanted.blue})"
        if wanted.links is not None and wanted.coloured > wanted.links:
            self.fail(
                entry.key_lines["colours"],
                "sockets.colours",
                f"{shown} do not fit in one linked group of {wanted.links} (`links`), where they are counted;"
                " ask for fewer colours or a bigger group",
            )
        if wanted.links is None and wanted.count is not None and wanted.coloured > wanted.count:
            self.fail(
                entry.key_lines["colours"],
                "sockets.colours",
                f"{shown} are more than the {wanted.count} sockets of `count`; ask for fewer colours or more sockets",
            )

    @staticmethod
    def no_socket_table(base: BaseItem) -> str:
        if base.item_class in CATALYST_ITEM_CLASSES:
            return (
                f"{base.name} is of item class {base.item_class}, and the sockets of jewellery are out of scope (the one socket of an Unset Ring"
                " cannot change), so a socket target on it is refused (ADR-0046)"
            )
        return (
            f"{base.name} is of item class {base.item_class}, which has no socket table; sockets are planned for weapons and armour only"
            " (ADR-0046)"
        )

    def check_socket_scope(self, root: LineMap, requirements: tuple[Node, ...], start_item: Item) -> None:
        """Refuse a socket target on a corrupted start item and on an item with an Abyssal Socket (ADR-0046): both are out of scope."""
        line = root.key_lines["sockets"]
        if start_item.corrupted:
            self.fail(
                line,
                "sockets",
                "the start item is corrupted (`start_item.corrupted`), and a corrupted item takes no socket orb;"
                " the Tainted orbs and the bench crafts that cost Vaal Orbs are batch B4's (ADR-0046)",
            )
        held = tuple(entry.mod_id for entry in (*start_item.mods, *start_item.implicits))
        if has_abyssal_socket(self.data, start_item.base_id, held):
            self.fail(
                line,
                "sockets",
                "the start item has an Abyssal Socket (a mod or an implicit of the base), and the sockets of such an item are out of"
                " scope: nothing says how an Abyssal Socket counts toward the total (ADR-0046)",
            )
        for index, node in enumerate(requirements):
            if self.names_abyssal_socket(node):
                self.fail(
                    root["requirements"].item_lines[index],
                    f"requirements[{index}]",
                    "this requirement can put an Abyssal Socket on the item, and a target with sockets on such an item is out of"
                    " scope: nothing says how an Abyssal Socket counts toward the total (ADR-0046)",
                )

    def names_abyssal_socket(self, node: Node) -> bool:
        if isinstance(node, KOfN):
            return any(self.names_abyssal_socket(member) for member in node.of)
        return any(is_abyssal_socket_mod(self.data.mods[mod_id]) for mod_id in node.mod_ids)

    def read_start_sockets(self, entry: object, line: int) -> Sockets:
        """The `sockets:` of a start item: `colours` (a list of W, R, G, B, one per socket), `count` and `links` (group sizes in order)."""
        path = "start_item.sockets"
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping with `colours`, `count` and `links`, got {describe(entry)}")
        self.check_keys(entry, path, START_SOCKET_KEYS)
        if not len(entry):
            self.fail(line, path, "name at least one of `count`, `colours` and `links`; an empty mapping states no sockets")
        colours = self.read_start_colours(entry["colours"], f"{path}.colours", entry.key_lines["colours"]) if "colours" in entry else None
        count = self.read_socket_number(entry, "count", f"{path}.count", 1)
        links = self.read_start_links(entry["links"], f"{path}.links", entry.key_lines["links"]) if "links" in entry else None
        if colours is not None and count is not None and len(colours) != count:
            self.fail(
                entry.key_lines["count"], f"{path}.count", f"is {count}, but `colours` lists {len(colours)} sockets; they must agree"
            )
        sockets = len(colours) if colours is not None else count if count is not None else sum(links)
        if sockets > MAX_SOCKETS:
            self.fail(line, path, f"{sockets} sockets is more than the {MAX_SOCKETS} any item can have")
        if links is not None and sum(links) != sockets:
            self.fail(
                entry.key_lines["links"],
                f"{path}.links",
                f"the groups {list(links)} add up to {sum(links)} sockets, but the item has {sockets}"
                " (one group size per run of linked sockets, in socket order, unlinked sockets as 1)",
            )
        shades = colours if colours is not None else (SocketColour.WHITE,) * sockets
        return Sockets(shades, links if links is not None else (1,) * sockets)

    def read_start_colours(self, entry: object, path: str, line: int) -> tuple[SocketColour, ...]:
        if not isinstance(entry, LineList) or not len(entry):
            self.fail(line, path, f"must be a non-empty list of socket colours such as [R, G, B, W], got {describe(entry)}")
        names = {colour.name.lower(): colour for colour in SocketColour} | {colour.value.lower(): colour for colour in SocketColour}
        found = []
        for index, name in enumerate(entry):
            colour = names.get(name.strip().lower()) if isinstance(name, str) else None
            if colour is None:
                self.fail(
                    entry.item_lines[index],
                    f"{path}[{index}]",
                    f"must be one of {quoted([colour.value for colour in SocketColour])} (or red, green, blue, white), got {describe(name)}",
                )
            found.append(colour)
        return tuple(found)

    def read_start_links(self, entry: object, path: str, line: int) -> tuple[int, ...]:
        if not isinstance(entry, LineList) or not len(entry):
            self.fail(line, path, f"must be a non-empty list of link group sizes such as [3, 2, 1], got {describe(entry)}")
        for index, size in enumerate(entry):
            if not is_whole(size) or not 1 <= size <= MAX_SOCKETS:
                self.fail(
                    entry.item_lines[index],
                    f"{path}[{index}]",
                    f"must be a whole number from 1 to {MAX_SOCKETS}, got {describe(size)}",
                )
        return tuple(entry)

    # -- the enchantment -----------------------------------------------------------------------------

    def enchantment_resolver(self, base_id: str, line: int, path: str) -> EnchantmentResolver:
        base = self.data.base_items[base_id]
        held = enchant_class(base)
        if held is None:
            self.fail(
                line,
                path,
                f"{base.name} is a {base.item_class}, and only weapons and body armour hold an enchantment,"
                " so the enchantment could never be met",
            )
        return EnchantmentResolver(self.data, held)

    def read_enchantment(self, entry: object, line: int, base_id: str) -> EnchantmentRequirement:
        if not isinstance(entry, LineMap):
            hint = f"; {ONE_ENCHANTMENT}" if isinstance(entry, LineList) else ""
            self.fail(line, "enchantment", f"must be a mapping with `any_of`, got {describe(entry)}{hint}")
        if "all_of" in entry:
            self.fail(entry.key_lines["all_of"], "enchantment.all_of", f"`all_of` cannot be met: {ONE_ENCHANTMENT}")
        self.check_keys(entry, "enchantment", ENCHANTMENT_KEYS)
        if "any_of" not in entry:
            self.fail(entry.line, "enchantment.any_of", "this key is required but missing")
        entries = entry["any_of"]
        any_line = entry.key_lines["any_of"]
        if not isinstance(entries, LineList) or not entries:
            got = "an empty list" if isinstance(entries, LineList) else describe(entries)
            self.fail(
                any_line,
                "enchantment.any_of",
                f"must be a non-empty list of enchantments (a stat text, a mod id or a tag), got {got}",
            )
        resolver = self.enchantment_resolver(base_id, any_line, "enchantment")
        found: dict[str, int] = {}
        mod_ids: set[str] = set()
        for index, name in enumerate(entries):
            path = f"enchantment.any_of[{index}]"
            line_of = entries.item_lines[index]
            if not isinstance(name, str) or not name.strip():
                self.fail(line_of, path, f"must be an enchantment (non-empty text), got {describe(name)}")
            if name.strip() in found:
                first = found[name.strip()]
                self.fail(line_of, path, f"{describe(name)} is listed twice (first at enchantment.any_of[{first}])")
            found[name.strip()] = index
            try:
                mod_ids |= resolver.resolve(name)
            except Unresolved as problem:
                self.fail(line_of, path, str(problem))
        return EnchantmentRequirement(tuple(found), frozenset(mod_ids))

    def check_enchantment_reachable(
        self, entry: LineMap, wanted: EnchantmentRequirement, base_id: str, start_item: Item
    ) -> None:
        """Refuse an entry that is the extra crafted slot when the start item does not hold it: no orb is planned for it (ADR-0053)."""
        resolver = self.enchantment_resolver(base_id, entry.line, "enchantment")
        for index, name in enumerate(wanted.entries):
            slot = resolver.extra_slot_ids(resolver.resolve(name))
            if slot and start_item.enchantment not in slot:
                self.fail(entry["any_of"].item_lines[index], f"enchantment.any_of[{index}]", UNREACHABLE_ENCHANTMENT)

    def read_start_enchantment(self, value: object, line: int, base_id: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self.fail(
                line, "start_item.enchantment", f"must be an enchantment mod id or its exact stat text, got {describe(value)}"
            )
        resolver = self.enchantment_resolver(base_id, line, "start_item.enchantment")
        try:
            found = resolver.resolve(value, allow_tag=False)
        except Unresolved as problem:
            self.fail(line, "start_item.enchantment", str(problem))
        return next(iter(found))

    # -- the start item ----------------------------------------------------------------------------

    def read_start_item(
        self, root: LineMap, base_id: str, item_level: int, influences: frozenset[Influence], *, assume_socket: bool = False
    ) -> Item:
        line = root.key_lines.get("start_item", root.key_lines["base"])
        fields: dict[str, object] = {"rarity": Rarity.NORMAL}
        mods: tuple[ExplicitMod, ...] = ()
        mod_lines: list[int] = []
        implicits: tuple[ImplicitMod, ...] = ()
        implicit_lines: list[int] = []
        offer: tuple[str, ...] = ()
        offer_lines: list[int] = []
        quality_line = line
        sockets_line = line
        enchantment_line = line
        if "start_item" in root:
            start = root["start_item"]
            line = root.key_lines["start_item"]
            if not isinstance(start, LineMap):
                self.fail(
                    line,
                    "start_item",
                    "must be a mapping with `rarity`, `corrupted`, `mods`, `implicits`, `quality`, `sockets`, `enchantment`,"
                    " `veil_offer` and `memory_strands`,"
                    f" got {describe(start)}",
                )
            self.check_keys(start, "start_item", START_ITEM_KEYS)
            if "mods" in start:
                mods = self.read_start_mods(start["mods"], start.key_lines["mods"])
                mod_lines = start["mods"].item_lines
            if "implicits" in start:
                implicits = self.read_start_implicits(start["implicits"], start.key_lines["implicits"], base_id)
                implicit_lines = start["implicits"].item_lines
            if "quality" in start:
                item_class = self.data.base_items[base_id].item_class
                fields["quality"] = self.read_start_quality(start["quality"], start.key_lines["quality"], item_class)
                quality_line = start.key_lines["quality"]
            if "sockets" in start:
                fields["sockets"] = self.read_start_sockets(start["sockets"], start.key_lines["sockets"])
                sockets_line = start.key_lines["sockets"]
            if "enchantment" in start:
                enchantment_line = start.key_lines["enchantment"]
                fields["enchantment"] = self.read_start_enchantment(start["enchantment"], enchantment_line, base_id)
            if "veil_offer" in start:
                offer = self.read_veil_offer(start["veil_offer"], start.key_lines["veil_offer"])
                offer_lines = start["veil_offer"].item_lines
            if "memory_strands" in start:
                fields["memory_strands"] = self.read_start_strands(start["memory_strands"], start.key_lines["memory_strands"])
            fields["rarity"] = self.read_rarity(start, bool(mods))
            if "corrupted" in start:
                if not isinstance(start["corrupted"], bool):
                    self.fail(
                        start.key_lines["corrupted"],
                        "start_item.corrupted",
                        f"must be true or false, got {describe(start['corrupted'])}",
                    )
                fields["corrupted"] = start["corrupted"]
        if assume_socket and "sockets" not in fields:
            fields["sockets"] = Sockets.unlinked((SocketColour.WHITE,))  # a target with sockets assumes one white socket (ADR-0046)
        try:
            return Item.build(
                self.data,
                base_id=base_id,
                item_level=item_level,
                mods=mods,
                influences=influences,
                implicits=implicits,
                veil_offer=offer,
                **fields,
            )
        except ItemError as problem:
            message = str(problem)
            if isinstance(problem, QualityError):
                self.fail(quality_line, "start_item.quality", message)
            if isinstance(problem, SocketError):
                self.fail(sockets_line, "start_item.sockets", message)
            if isinstance(problem, EnchantmentError):
                self.fail(enchantment_line, "start_item.enchantment", message)
            if isinstance(problem, VeilOfferError):
                index = blamed_id(message, offer, last_written=True)
                if index is None:
                    self.fail(root["start_item"].key_lines["veil_offer"], "start_item.veil_offer", message)
                self.fail(offer_lines[index], f"start_item.veil_offer[{index}]", message)
            if isinstance(problem, ImplicitError):
                index = blamed_id(message, [entry.mod_id for entry in implicits], last_written=True)
                if index is not None:
                    self.fail(implicit_lines[index], f"start_item.implicits[{index}]", message)
            else:
                index = blamed_mod(message, mods)
                if index is not None:
                    self.fail(mod_lines[index], f"start_item.mods[{index}]", message)
                index = blamed_id(message, [entry.mod_id for entry in implicits])
                if index is not None:
                    self.fail(implicit_lines[index], f"start_item.implicits[{index}]", message)
            self.fail(line, "start_item", message)

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
        veiled = self.is_veiled(entry.get("mod"))  # a veiled placeholder needs neither tier nor values
        for key in ("mod",) if veiled else ("mod", "tier", "values"):
            if key not in entry:
                self.fail(entry.line, f"{path}.{key}", "this key is required but missing")
        mod_id = self.known_mod_id(entry, f"{path}.mod")
        if veiled:
            placeholder = veiled_placeholder(self.data, mod_id)
            tier = entry["tier"] if "tier" in entry else placeholder.tier
        else:
            tier = entry["tier"]
        if not is_whole(tier) or tier < 1:
            self.fail(entry.key_lines["tier"], f"{path}.tier", f"must be a whole number of 1 or more, got {describe(tier)}")
        if "values" in entry:
            values = self.read_values(entry["values"], f"{path}.values", entry.key_lines["values"])
        else:
            values = placeholder.values
        flags = {}
        for key in ("fractured", "crafted"):
            if key in entry:
                if not isinstance(entry[key], bool):
                    self.fail(entry.key_lines[key], f"{path}.{key}", f"must be true or false, got {describe(entry[key])}")
                flags[key] = entry[key]
        return ExplicitMod(mod_id, tier, values, **flags)

    def is_veiled(self, mod_id: object) -> bool:
        """Whether `mod_id` is written as the id of a veiled placeholder."""
        mod = self.data.mods.get(mod_id.strip()) if isinstance(mod_id, str) else None
        return mod is not None and mod.domain == VEILED_DOMAIN

    def known_mod_id(self, entry: LineMap, path: str) -> str:
        """The game-data mod id written under `mod`; an unknown one is an error with close matches."""
        mod_id = self.text(entry, "mod", path)
        if mod_id not in self.data.mods:
            near = close_matches(mod_id, self.data.mods)
            hint = f"; did you mean {quoted(near)}?" if near else ""
            self.fail(entry.key_lines["mod"], path, f"`{mod_id}` is not a mod id in the game data{hint}")
        return mod_id

    def read_start_implicits(self, entries: object, line: int, base_id: str) -> tuple[ImplicitMod, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, "start_item.implicits", f"must be a list of implicit mods, got {describe(entries)}")
        return tuple(
            self.read_start_implicit(entry, f"start_item.implicits[{index}]", entries.item_lines[index], base_id)
            for index, entry in enumerate(entries)
        )

    def read_start_implicit(self, entry: object, path: str, line: int, base_id: str) -> ImplicitMod:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping with `mod`, `values` and optionally `grade`, got {describe(entry)}")
        self.check_keys(entry, path, START_IMPLICIT_KEYS)
        for key in ("mod", "values"):
            if key not in entry:
                self.fail(entry.line, f"{path}.{key}", "this key is required but missing")
        mod_id = self.known_mod_id(entry, f"{path}.mod")
        values = self.read_values(entry["values"], f"{path}.values", entry.key_lines["values"])
        if "grade" in entry:
            grade = entry["grade"]
            if not is_whole(grade) or not BASE_GRADE <= grade <= MAX_ELDRITCH_GRADE:
                self.fail(
                    entry.key_lines["grade"],
                    f"{path}.grade",
                    f"must be a whole number from {BASE_GRADE} (a base implicit) to {MAX_ELDRITCH_GRADE}, got {describe(grade)}",
                )
            return ImplicitMod(mod_id, grade, values)
        # No grade written: it follows from the mod. One that is neither an implicit of the base nor
        # Eldritch gets grade 0 here and is refused by the item with its own reason.
        mod = self.data.mods[mod_id]
        base = self.data.base_items.get(base_id)
        if base is not None and mod_id in base.implicits or eldritch_side(mod) is None:
            return ImplicitMod(mod_id, BASE_GRADE, values)
        try:
            return ImplicitMod(mod_id, eldritch_grade(mod) or BASE_GRADE, values)
        except ImplicitError as problem:
            self.fail(line, path, str(problem))

    def read_start_quality(self, entry: object, line: int, item_class: str) -> Quality | PlainQuality:
        plain_class = item_class in PLAIN_QUALITY_ITEM_CLASSES
        if not isinstance(entry, LineMap):
            keys = "`percent` (a weapon or armour has plain quality, no `type`)" if plain_class else "`type` and `percent`"
            self.fail(line, "start_item.quality", f"must be a mapping with {keys}, got {describe(entry)}")
        self.check_keys(entry, "start_item.quality", START_QUALITY_KEYS)
        if plain_class and "type" not in entry:
            return self.read_start_plain_quality(entry)
        for key in START_QUALITY_KEYS:
            if key not in entry:
                self.fail(entry.line, f"start_item.quality.{key}", "this key is required but missing")
        catalyst = self.read_catalyst(entry, "start_item.quality.type")
        percent = entry["percent"]
        if not is_whole(percent) or not 0 <= percent <= MAX_QUALITY:
            self.fail(
                entry.key_lines["percent"],
                "start_item.quality.percent",
                f"must be a whole number from 0 to {MAX_QUALITY}, got {describe(percent)}",
            )
        return Quality(catalyst, percent)

    def read_start_plain_quality(self, entry: LineMap) -> PlainQuality:
        """`start_item.quality: {percent}` of a weapon or armour (ADR-0049): whole 0 to 30, a random drop reaching 30."""
        if "percent" not in entry:
            self.fail(entry.line, "start_item.quality.percent", "this key is required but missing")
        percent = entry["percent"]
        if not is_whole(percent) or not 0 <= percent <= MAX_PLAIN_QUALITY:
            self.fail(
                entry.key_lines["percent"],
                "start_item.quality.percent",
                f"must be a whole number from 0 to {MAX_PLAIN_QUALITY}, got {describe(percent)}",
            )
        return PlainQuality(percent)

    def read_start_strands(self, value: object, line: int) -> int:
        """The Memory Strands count of the start item: a whole number from 0 to 100, or a pasted item text holding the line `Memory Strands: N`."""
        path = "start_item.memory_strands"
        if isinstance(value, str):
            if not has_memory_strands_line(value):  # a count that is not on a line of its own would otherwise read as 0, silently
                self.fail(
                    line,
                    path,
                    'a text must hold the line "Memory Strands: N" of the pasted item, on a line of its own'
                    f" (a folded text joins its lines), got {describe(value)}",
                )
            try:
                return read_memory_strands(value)
            except MemoryStrandsError as problem:
                self.fail(line, path, str(problem))
        if not is_whole(value) or not 0 <= value <= MAX_MEMORY_STRANDS:
            self.fail(
                line,
                path,
                f"must be a whole number from 0 to {MAX_MEMORY_STRANDS} or a pasted item text with a"
                f' "Memory Strands: N" line, got {describe(value)}',
            )
        return value

    def read_veil_offer(self, entries: object, line: int) -> tuple[str, ...]:
        if not isinstance(entries, LineList):
            self.fail(line, "start_item.veil_offer", f"must be a list of mod ids, got {describe(entries)}")
        offered = []
        for index, entry in enumerate(entries):
            path = f"start_item.veil_offer[{index}]"
            if not isinstance(entry, str) or not entry.strip():
                self.fail(entries.item_lines[index], path, f"must be a mod id (non-empty text), got {describe(entry)}")
            mod_id = entry.strip()
            if mod_id not in self.data.mods:
                near = close_matches(mod_id, self.data.mods)
                hint = f"; did you mean {quoted(near)}?" if near else ""
                self.fail(entries.item_lines[index], path, f"`{mod_id}` is not a mod id in the game data{hint}")
            offered.append(mod_id)
        return tuple(offered)

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
        return value.strip()

    def check_keys(self, mapping: LineMap, path: str, allowed: Iterable[str]) -> None:
        allowed = tuple(allowed)
        for key in mapping:
            if key in allowed:
                continue
            near = difflib.get_close_matches(key, allowed, n=1)
            hint = f"did you mean `{near[0]}`?" if near else f"the keys allowed here are {quoted(allowed)}"
            where = f"{path}.{key}" if path else key
            self.fail(mapping.key_lines[key], where, f"unknown key `{key}`; {hint}")
