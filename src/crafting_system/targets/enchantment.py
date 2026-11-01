"""Turning the entries of `enchantment: {any_of: [...]}` into enchantment mod ids (ADR-0050).

An entry is, in this order: a mod id, the stat text of an enchant (two-line texts join their lines with a
newline, as everywhere), or a bare tag such as `Life`. Everything is resolved among the enchantments of
the target's base class only, since the extra crafted slot has one mod in each pool with the same text. A
tag alone stands for the **clean** enchants of that tag; an enchant with a socket rider or a downside is
accepted only by its own text or id.
"""

from functools import cached_property

from crafting_system.data import GameData
from crafting_system.items import EnchantClass, EnchantInfo, enchant_info

from .resolve import Unresolved, close_matches, normalise_stat_text, one_line, quoted


class EnchantmentResolver:
    """The enchantments of one base class in one `GameData`, looked up by id, text or tag."""

    def __init__(self, data: GameData, item_class: EnchantClass) -> None:
        self.data = data
        self.item_class = item_class

    @cached_property
    def infos(self) -> dict[str, EnchantInfo]:
        """Every enchantment of the class, by mod id."""
        found = (enchant_info(mod) for mod in self.data.mods.values())
        return {info.mod_id: info for info in found if info is not None and info.item_class is self.item_class}

    @cached_property
    def _by_text(self) -> dict[str, frozenset[str]]:
        found: dict[str, set[str]] = {}
        for mod_id in self.infos:
            text = self.data.mods[mod_id].text
            if text is not None:
                found.setdefault(normalise_stat_text(text), set()).add(mod_id)
        return {text: frozenset(ids) for text, ids in found.items()}

    @cached_property
    def _clean_by_tag(self) -> dict[str, frozenset[str]]:
        found: dict[str, set[str]] = {}
        for info in self.infos.values():
            if info.clean:
                for tag in info.tags:
                    found.setdefault(tag.casefold(), set()).add(info.mod_id)
        return {tag: frozenset(ids) for tag, ids in found.items()}

    @cached_property
    def _tag_names(self) -> dict[str, str]:
        return {tag.casefold(): tag for info in self.infos.values() if info.clean for tag in info.tags}

    def resolve(self, entry: str, *, allow_tag: bool = True) -> frozenset[str]:
        """The mod ids `entry` stands for; `Unresolved` with what to write instead when it names nothing.

        A bare tag is read only with `allow_tag`: an item holds one enchantment, so a start item names it by id or text."""
        name = entry.strip()
        if name in self.infos:
            return frozenset({name})
        elsewhere = enchant_info(self.data.mods[name]) if name in self.data.mods else None
        if elsewhere is not None:
            raise Unresolved(
                f"`{name}` is a {elsewhere.item_class.value} enchantment, but the base takes {self.item_class.value}"
                " enchantments"
            )
        wanted = normalise_stat_text(entry)
        if wanted in self._by_text:
            return self._by_text[wanted]
        tag = self._clean_by_tag.get(name.casefold()) if allow_tag else None
        if tag is not None:
            return tag
        raise Unresolved(self._unresolved_message(name, wanted))

    def _unresolved_message(self, name: str, wanted: str) -> str:
        who = self.item_class.value
        if not wanted:
            return "the entry is empty once markup such as [..] and blank lines are removed"
        known = [*self._tag_names.values(), *self._by_text]
        near = close_matches(wanted, known) or close_matches(name, known)
        if near:
            shown = ", ".join(f'"{one_line(match)}"' for match in near)
            hint = f"; closest {who} enchantments in the game data: {shown}"
        else:
            hint = f"; a {who} enchantment is written by its stat text, its mod id or a tag such as {quoted(sorted(self._tag_names.values())[:3])}"
        return f'no {who} enchantment is named "{one_line(wanted)}"{hint}'

    def extra_slot_ids(self, mod_ids: frozenset[str]) -> frozenset[str]:
        """Those of `mod_ids` that are the extra crafted slot."""
        return frozenset(mod_id for mod_id in mod_ids if self.infos[mod_id].extra_slot)
