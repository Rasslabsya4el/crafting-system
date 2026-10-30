"""What changed between two versions of the game data (ADR-0017): a pure comparison of two `GameData`.

`compare_game_data` returns a `PatchDiff` (sections of entries) and `render_diff` turns it into
plain text; `diff_game_data` does both. Nothing here reads a file or the network. The text is
deterministic: ids are sorted, sets are compared as sets and shown sorted, and nothing depends on
the key order of the raw files. Lists whose order matters in the game (spawn weights, generation
weights) are compared per tag, and a pure re-ordering is reported as `order changed`.

Free text (mod names and texts) is shown in double quotes with newlines and backslashes escaped,
so every change stays on one line; non-ASCII letters are kept, and the command line prints them
with a safe fallback on consoles that cannot show them.

Section order: Mods, Spawn weights, Generation weights, Families, Tags, Bench options, Essences,
Fossils. A section with no change is left out. An added or removed mod is listed under Mods only,
not again in the sections after it.
"""

import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields

from .model import BaseItem, BenchOption, Essence, Fossil, GameData, Mod, Weight

ADDED = "+"
REMOVED = "-"
CHANGED = "~"
_KIND_ORDER = {ADDED: 0, REMOVED: 1, CHANGED: 2}
_KIND_WORDS = ((ADDED, "added"), (REMOVED, "removed"), (CHANGED, "changed"))

MODS = "Mods"
SPAWN_WEIGHTS = "Spawn weights"
GENERATION_WEIGHTS = "Generation weights"
FAMILIES = "Families"
TAGS = "Tags"
BENCH_OPTIONS = "Bench options"
ESSENCES = "Essences"
FOSSILS = "Fossils"


@dataclass(frozen=True, slots=True)
class Entry:
    """One thing that was added (`+`), removed (`-`) or changed (`~`), and the lines saying how."""

    kind: str
    head: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Section:
    """The entries of one topic: added first, then removed, then changed, each sorted by id."""

    title: str
    entries: tuple[Entry, ...]

    def count(self, kind: str) -> int:
        return sum(1 for entry in self.entries if entry.kind == kind)


@dataclass(frozen=True, slots=True)
class PatchDiff:
    """The differences of `old` -> `new`; only sections that have a change are present."""

    old_label: str
    new_label: str
    sections: tuple[Section, ...]


# --- text ---------------------------------------------------------------------------------------


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _plain(text: str) -> str:
    """An id or tag as it is shown: the same escaping as `_quote`, without the quotes."""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _show(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _quote(value)
    return str(value)


def _ident(value: str | None) -> str:
    return "none" if value is None else _plain(value)


def _list_or_none(items: Iterable[str]) -> str:
    shown = ", ".join(_plain(item) for item in items)
    return shown or "none"


def _head(item_id: str, name: str) -> str:
    return f"{_plain(item_id)} {_quote(name)}" if name else _plain(item_id)


def _short(item_id: str) -> str:
    """The last part of a `Metadata/Items/...` id, which is what a person reads."""
    return _plain(item_id.rsplit("/", 1)[-1])


def _scalar_changes(old: object, new: object, names: Sequence[str]) -> list[str]:
    return [
        f"{name}: {_show(getattr(old, name))} -> {_show(getattr(new, name))}"
        for name in names
        if getattr(old, name) != getattr(new, name)
    ]


def _set_changes(label: str, old: Iterable[str], new: Iterable[str]) -> list[str]:
    """`label: + x` for what `new` has more than `old`, then `label: - y` for what it has less."""
    before, after = set(old), set(new)
    return [f"{label}: + {_plain(item)}" for item in sorted(after - before)] + [
        f"{label}: - {_plain(item)}" for item in sorted(before - after)
    ]


def _weight_changes(old: Sequence[Weight], new: Sequence[Weight], prefix: str = "") -> list[str]:
    """Per-tag differences of two (tag, weight) lists. A tag that occurs twice is told apart by `#n`."""

    def numbered(weights: Sequence[Weight]) -> list[tuple[tuple[str, int], int]]:
        seen: Counter[str] = Counter()
        keyed = []
        for entry in weights:
            seen[entry.tag] += 1
            keyed.append(((entry.tag, seen[entry.tag]), entry.weight))
        return keyed

    old_keyed, new_keyed = numbered(old), numbered(new)
    old_by_key, new_by_key = dict(old_keyed), dict(new_keyed)
    repeated = {tag for tag, number in (*old_by_key, *new_by_key) if number > 1}

    def label(key: tuple[str, int]) -> str:
        tag, number = key
        return f"{_plain(tag)} #{number}" if tag in repeated else _plain(tag)

    lines = [
        f"{prefix}{label(key)}: {old_by_key[key]} -> {new_by_key[key]}"
        for key in sorted(old_by_key.keys() & new_by_key.keys())
        if old_by_key[key] != new_by_key[key]
    ]
    lines += [f"{prefix}{ADDED} {label(key)}: {new_by_key[key]}" for key in sorted(new_by_key.keys() - old_by_key.keys())]
    lines += [f"{prefix}{REMOVED} {label(key)}: {old_by_key[key]}" for key in sorted(old_by_key.keys() - new_by_key.keys())]
    old_order = [key for key, _ in old_keyed if key in new_by_key]
    new_order = [key for key, _ in new_keyed if key in old_by_key]
    if old_order != new_order:
        lines.append(
            f"{prefix}order changed: {', '.join(map(label, old_order))} -> {', '.join(map(label, new_order))}"
        )
    return lines


def _stats(mod: Mod) -> str:
    return "; ".join(f"{_plain(stat.id)} ({stat.min} to {stat.max})" for stat in mod.stats) or "none"


# --- building sections ---------------------------------------------------------------------------

_Item = tuple[tuple, Entry]


def _section(title: str, items: Iterable[_Item]) -> Section | None:
    ordered = sorted(items, key=lambda item: (_KIND_ORDER[item[1].kind], item[0]))
    if not ordered:
        return None
    return Section(title, tuple(entry for _, entry in ordered))


def _added_removed_changed[V](
    old: Mapping[str, V],
    new: Mapping[str, V],
    added: Callable[[str, V], str],
    removed: Callable[[str, V], str],
    changes: Callable[[str, V, V], tuple[str, Sequence[str]]],
    group: int = 0,
) -> list[_Item]:
    """Entries for the ids only in `new` (added), only in `old` (removed), and in both with changes."""
    items: list[_Item] = []
    for key in new.keys() - old.keys():
        items.append(((group, key), Entry(ADDED, added(key, new[key]))))
    for key in old.keys() - new.keys():
        items.append(((group, key), Entry(REMOVED, removed(key, old[key]))))
    for key in old.keys() & new.keys():
        head, details = changes(key, old[key], new[key])
        if details:
            items.append(((group, key), Entry(CHANGED, head, tuple(details))))
    return items


def _changed_in_both[V](
    old: Mapping[str, V],
    new: Mapping[str, V],
    details: Callable[[V, V], Sequence[str]],
    head: Callable[[str, V], str],
    group: int = 0,
) -> list[_Item]:
    items: list[_Item] = []
    for key in old.keys() & new.keys():
        lines = details(old[key], new[key])
        if lines:
            items.append(((group, key), Entry(CHANGED, head(key, new[key]), tuple(lines))))
    return items


def _named_head(key: str, item: Mod | BaseItem | Essence | Fossil) -> str:
    return _head(key, item.name)


# mods


def _mod_summary(mod: Mod) -> str:
    return (
        f"text {_show(mod.text)}, level {mod.required_level}, domain {_ident(mod.domain)}, "
        f"generation_type {_ident(mod.generation_type)}, families {_list_or_none(mod.families)}"
    )


def _mod_field_changes(old: Mod, new: Mod) -> list[str]:
    lines = _scalar_changes(old, new, ("name", "text", "type", "domain", "generation_type", "required_level"))
    if old.stats != new.stats:
        lines.append(f"stats: {_stats(old)} -> {_stats(new)}")
    return lines + _scalar_changes(old, new, ("is_essence_only",))


def _mods_section(old: GameData, new: GameData) -> Section | None:
    return _section(
        MODS,
        _added_removed_changed(
            old.mods,
            new.mods,
            added=lambda key, mod: f"{_head(key, mod.name)}: {_mod_summary(mod)}",
            removed=lambda key, mod: f"{_head(key, mod.name)}: {_mod_summary(mod)}",
            changes=lambda key, a, b: (_plain(key), _mod_field_changes(a, b)),
        ),
    )


def _weights_section(title: str, attribute: str, old: GameData, new: GameData) -> Section | None:
    return _section(
        title,
        _changed_in_both(
            old.mods,
            new.mods,
            lambda a, b: _weight_changes(getattr(a, attribute), getattr(b, attribute)),
            _named_head,
        ),
    )


def _families_section(old: GameData, new: GameData) -> Section | None:
    def changes(a: Mod, b: Mod) -> list[str]:
        before, after = set(a.families), set(b.families)
        return [f"+ {_plain(f)}" for f in sorted(after - before)] + [f"- {_plain(f)}" for f in sorted(before - after)]

    return _section(FAMILIES, _changed_in_both(old.mods, new.mods, changes, _named_head))


# tags


def _tags_section(old: GameData, new: GameData) -> Section | None:
    def mod_tags(a: Mod, b: Mod) -> list[str]:
        return _set_changes("adds_tags", a.adds_tags, b.adds_tags) + _set_changes(
            "implicit_tags", a.implicit_tags, b.implicit_tags
        )

    def base_summary(key: str, base: BaseItem) -> str:
        return f"base item {_head(key, base.name)}: item_class {_ident(base.item_class)}"

    items = _changed_in_both(
        old.mods, new.mods, mod_tags, lambda key, mod: f"mod {_head(key, mod.name)}", group=0
    )
    items += _added_removed_changed(
        old.base_items,
        new.base_items,
        added=base_summary,
        removed=base_summary,
        changes=lambda key, a, b: (
            f"base item {_head(key, b.name)}",
            _set_changes("tags", a.tags, b.tags),
        ),
        group=1,
    )
    return _section(TAGS, items)


# bench options


def _option_actions(option: BenchOption, mods: Mapping[str, Mod]) -> str:
    parts = []
    for field in fields(option.actions):
        value = getattr(option.actions, field.name)
        if value is None:
            continue
        part = f"{field.name} {_show(value) if not isinstance(value, str) else _plain(value)}"
        mod = mods.get(value) if field.name.endswith("_mod") else None
        if mod is not None and mod.text is not None:
            part += f" ({_quote(mod.text)})"
        parts.append(part)
    return "; ".join(parts) or "no action"


def _option_identity(option: BenchOption, mods: Mapping[str, Mod]) -> str:
    return (
        f"{_plain(option.master)}: {_option_actions(option, mods)}; "
        f"item classes {_list_or_none(sorted(option.item_classes))}"
    )


def _option_full(option: BenchOption, mods: Mapping[str, Mod]) -> str:
    cost = ", ".join(f"{_short(entry.item_id)} x{entry.count}" for entry in sorted(option.cost, key=lambda e: e.item_id))
    return f"{_option_identity(option, mods)}; bench_tier {option.bench_tier}; cost {cost or 'none'}"


def _option_changes(old: BenchOption, new: BenchOption) -> list[str]:
    lines = _scalar_changes(old, new, ("bench_tier",))
    before = {entry.item_id: entry.count for entry in old.cost}
    after = {entry.item_id: entry.count for entry in new.cost}
    lines += [
        f"cost {_short(item)}: {before[item]} -> {after[item]}"
        for item in sorted(before.keys() & after.keys())
        if before[item] != after[item]
    ]
    lines += [f"+ cost {_short(item)}: {after[item]}" for item in sorted(after.keys() - before.keys())]
    lines += [f"- cost {_short(item)}: {before[item]}" for item in sorted(before.keys() - after.keys())]
    return lines


def _bench_section(old: GameData, new: GameData) -> Section | None:
    """Options have no id; one is identified by master, actions and the set of item classes."""

    def grouped(options: Sequence[BenchOption]) -> dict[tuple, list[BenchOption]]:
        found: dict[tuple, list[BenchOption]] = {}
        for option in options:
            found.setdefault((option.master, option.actions, frozenset(option.item_classes)), []).append(option)
        return found

    old_groups, new_groups = grouped(old.bench_options), grouped(new.bench_options)
    items: list[_Item] = []
    for key in old_groups.keys() | new_groups.keys():
        before, after = old_groups.get(key, []), new_groups.get(key, [])
        for position in range(max(len(before), len(after))):
            if position >= len(before):
                text = _option_full(after[position], new.mods)
                items.append((("", text, position), Entry(ADDED, text)))
            elif position >= len(after):
                text = _option_full(before[position], old.mods)
                items.append((("", text, position), Entry(REMOVED, text)))
            else:
                lines = _option_changes(before[position], after[position])
                if lines:
                    text = _option_identity(after[position], new.mods)
                    items.append((("", text, position), Entry(CHANGED, text, tuple(lines))))
    return _section(BENCH_OPTIONS, items)


# essences and fossils


def _essence_changes(old: Essence, new: Essence) -> list[str]:
    lines = _scalar_changes(
        old, new, ("name", "tier", "is_corruption_only", "level", "item_level_restriction", "spawn_level_min")
    )
    before = {entry.item_class: entry.mod_id for entry in old.mods}
    after = {entry.item_class: entry.mod_id for entry in new.mods}
    lines += [
        f"mod for {_plain(item_class)}: {_ident(before[item_class])} -> {_ident(after[item_class])}"
        for item_class in sorted(before.keys() & after.keys())
        if before[item_class] != after[item_class]
    ]
    lines += [
        f"+ mod for {_plain(item_class)}: {_ident(after[item_class])}" for item_class in sorted(after.keys() - before.keys())
    ]
    lines += [
        f"- mod for {_plain(item_class)}: {_ident(before[item_class])}"
        for item_class in sorted(before.keys() - after.keys())
    ]
    return lines


def _essences_section(old: GameData, new: GameData) -> Section | None:
    def summary(key: str, essence: Essence) -> str:
        return f"{_head(key, essence.name)}: tier {essence.tier}, level {essence.level}"

    return _section(
        ESSENCES,
        _added_removed_changed(
            old.essences,
            new.essences,
            added=summary,
            removed=summary,
            changes=lambda key, a, b: (_head(key, b.name), _essence_changes(a, b)),
        ),
    )


def _fossil_changes(old: Fossil, new: Fossil) -> list[str]:
    lines = _scalar_changes(
        old, new, ("name", "changes_quality", "rolls_lucky", "rolls_white_sockets", "mirrors", "corrupted_essence_chance")
    )
    for name in ("added_mods", "forced_mods", "allowed_tags", "forbidden_tags"):
        lines += _set_changes(name, getattr(old, name), getattr(new, name))
    for name in ("positive_mod_weights", "negative_mod_weights"):
        lines += _weight_changes(getattr(old, name), getattr(new, name), prefix=f"{name} ")
    return lines


def _fossils_section(old: GameData, new: GameData) -> Section | None:
    return _section(
        FOSSILS,
        _added_removed_changed(
            old.fossils,
            new.fossils,
            added=lambda key, fossil: _head(key, fossil.name),
            removed=lambda key, fossil: _head(key, fossil.name),
            changes=lambda key, a, b: (_head(key, b.name), _fossil_changes(a, b)),
        ),
    )


# --- public -------------------------------------------------------------------------------------


def compare_game_data(
    old: GameData, new: GameData, *, old_label: str | None = None, new_label: str | None = None
) -> PatchDiff:
    """Everything that differs between `old` and `new`; the labels default to each data's version."""
    sections = (
        _mods_section(old, new),
        _weights_section(SPAWN_WEIGHTS, "spawn_weights", old, new),
        _weights_section(GENERATION_WEIGHTS, "generation_weights", old, new),
        _families_section(old, new),
        _tags_section(old, new),
        _bench_section(old, new),
        _essences_section(old, new),
        _fossils_section(old, new),
    )
    return PatchDiff(
        old_label=old.version if old_label is None else old_label,
        new_label=new.version if new_label is None else new_label,
        sections=tuple(section for section in sections if section is not None),
    )


def render_diff(diff: PatchDiff) -> str:
    """The diff as plain text, lines separated by `\\n`, without a final newline."""
    lines = [f"Patch diff: {diff.old_label} -> {diff.new_label}"]
    if not diff.sections:
        lines.append("No changes.")
        return "\n".join(lines)
    lines.append("Summary: " + "; ".join(f"{section.title} {len(section.entries)}" for section in diff.sections))
    for section in diff.sections:
        counts = ", ".join(f"{section.count(kind)} {word}" for kind, word in _KIND_WORDS if section.count(kind))
        lines += ["", f"{section.title}: {counts}"]
        for entry in section.entries:
            lines.append(f"{entry.kind} {entry.head}")
            lines += [f"    {detail}" for detail in entry.details]
    return "\n".join(lines)


def diff_game_data(
    old: GameData, new: GameData, *, old_label: str | None = None, new_label: str | None = None
) -> str:
    """The text of `compare_game_data(old, new)`."""
    return render_diff(compare_game_data(old, new, old_label=old_label, new_label=new_label))
