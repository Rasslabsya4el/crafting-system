"""Turning what the owner wrote into game data: stat text and family ids into mod ids, names into bases.

Stat text is compared after one normalisation applied to both sides: a numeric range such as
`(10-24)`, `(-9-9)` or `(1.5-2.5)` becomes `#`, `[X|Y]` markup becomes `Y` and `[X]` becomes `X`, and
each line is stripped (hybrid mods have two lines). The comparison is then exact and case-sensitive,
so `+# to maximum Life` and `+(10-24) to maximum Life` name the same mods, and a fixed text such as
`+1 to Level of all Lightning Skill Gems` matches literally. Only prefixes and suffixes with a text
take part; a family id selects every mod of the family, whatever its generation type.
"""

import difflib
import re
from collections.abc import Iterable
from functools import cached_property

from crafting_system.data import GameData

TEXT_GENERATION_TYPES = frozenset({"prefix", "suffix"})
RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
LINK_WITH_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
LINK = re.compile(r"\[([^\]|]*)\]")
SUGGESTIONS = 5
NOT_FOR_SALE_TAG = "not_for_sale"


class Unresolved(ValueError):
    """The owner's selector matches nothing in the game data; the message says what to write instead."""


def normalise_stat_text(text: str) -> str:
    """The comparison form of a stat text: ranges as `#`, markup removed, lines stripped and joined by newline."""
    text = LINK.sub(r"\1", LINK_WITH_LABEL.sub(r"\1", RANGE.sub("#", text)))
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def close_matches(wanted: str, known: Iterable[str]) -> list[str]:
    """Up to five of `known` that look like `wanted`, compared without regard to case."""
    by_lower: dict[str, str] = {}
    for name in known:
        by_lower.setdefault(name.lower(), name)
    found = difflib.get_close_matches(wanted.lower(), by_lower, n=SUGGESTIONS)
    return [by_lower[key] for key in found]


def one_line(text: str) -> str:
    r"""A stat text on one line, its line breaks written as `\n` as they are typed in a YAML string."""
    return text.replace("\n", r"\n")


def quoted(names: Iterable[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


class Resolver:
    """Looks up mods and bases in one `GameData`; the indexes are built on first use."""

    def __init__(self, data: GameData) -> None:
        self.data = data

    @cached_property
    def _mods_by_text(self) -> dict[str, frozenset[str]]:
        found: dict[str, set[str]] = {}
        for mod in self.data.mods.values():
            if mod.generation_type in TEXT_GENERATION_TYPES and mod.text is not None:
                found.setdefault(normalise_stat_text(mod.text), set()).add(mod.id)
        return {text: frozenset(ids) for text, ids in found.items()}

    @cached_property
    def _mods_by_family(self) -> dict[str, frozenset[str]]:
        found: dict[str, set[str]] = {}
        for mod in self.data.mods.values():
            for family in mod.families:
                found.setdefault(family, set()).add(mod.id)
        return {family: frozenset(ids) for family, ids in found.items()}

    def mods_for_stat(self, text: str) -> frozenset[str]:
        """Every mod whose normalised text equals the normalised `text`; `Unresolved` if there is none."""
        wanted = normalise_stat_text(text)
        found = self._mods_by_text.get(wanted)
        if found is not None:
            return found
        if text.strip() in self._mods_by_family:
            raise Unresolved(f"`{text.strip()}` is a family id; write `family: {text.strip()}`")
        near = close_matches(wanted, self._mods_by_text)
        if near:
            shown = ", ".join(f'"{one_line(match)}"' for match in near)
            raise Unresolved(
                f'no mod has the text "{one_line(wanted)}"; closest texts in the game data: {shown}'
                " (a range like (10-24) can be written as # or in full; a two-line mod text joins its lines with \\n)"
            )
        raise Unresolved(f'no mod in the game data has the text "{one_line(wanted)}"')

    def mods_for_family(self, family: str) -> frozenset[str]:
        """Every mod of any generation type that belongs to `family`; `Unresolved` if the id is unknown."""
        found = self._mods_by_family.get(family)
        if found is not None:
            return found
        near = close_matches(family, self._mods_by_family)
        hint = f"; did you mean {quoted(near)}?" if near else ""
        raise Unresolved(f"`{family}` is not a family id in the game data{hint}")

    def base_id(self, name: str) -> str:
        """The id of the base `name` (an id or an English name); `Unresolved` if none or several fit.

        A name shared by several bases picks the only released one; of several released ones it
        skips those tagged `not_for_sale` (the Battle Royale copies) and picks the only one left.
        """
        bases = self.data.base_items
        if name in bases:
            return name
        same_name = [base for base in bases.values() if base.name == name]
        if len(same_name) == 1:
            return same_name[0].id
        if same_name:
            released = [base for base in same_name if base.release_state == "released"]
            if len(released) == 1:
                return released[0].id
            for_sale = [base for base in released if NOT_FOR_SALE_TAG not in base.tags]
            if len(for_sale) == 1:
                return for_sale[0].id
            ids = quoted(base.id for base in same_name)
            raise Unresolved(f"several bases are named `{name}`; write the base id instead: {ids}")
        near = close_matches(name, {base.name for base in bases.values()})
        hint = f"; did you mean {quoted(near)}?" if near else ""
        raise Unresolved(f"no base is named `{name}`{hint}")
