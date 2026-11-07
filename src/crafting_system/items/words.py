"""The game's words for a mod and a base: what a person reads where the code holds an id (tickets #557, #618, OR-13).

A mod and a base are keyed by an id in the data (`IncreasedLifeEssence6`, `Metadata/Items/...`). A sentence a person reads never carries the id:
it says a mod by its text as the route page prints it, and a base by its game name. This module is the one place that decides those words, so the page
(`cli._route_card.mod_text`) and the causes that exceptions write (`OutOfScopeError`, `EstimateRefused`) say the same thing.

* `mod_text(mod)`: the text of a mod as the page prints it, the markup of the data stripped and the lines of a hybrid joined with ` / `; a mod with no
  text is its name, a veiled placeholder "veiled prefix" or "veiled suffix".
* `mod_words(mod)` and `mod_words_of(data, mod_id)`: `mod_text`, for a sentence. A mod the data lacks, or that has no text and no name, is "a mod the game data gives no text", not its id.
* `base_words(data, base_id)`: the base's name in the game; a base the data lacks is "an item base the game data does not hold".
"""

import re

from crafting_system.data import GameData, Mod

from .model import VEILED_DOMAIN

__all__ = ["base_words", "clean_text", "mod_text", "mod_words", "mod_words_of"]

_LINK_WITH_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
_LINK = re.compile(r"\[([^\]|]*)\]")

NO_TEXT = "a mod the game data gives no text"
NO_BASE = "an item base the game data does not hold"


def clean_text(text: str) -> str:
    """The data's text of a mod with its markup stripped (`[Resistances|Lightning Resistance]` is `Lightning Resistance`), a hybrid's line break as ` / `."""
    text = _LINK.sub(r"\1", _LINK_WITH_LABEL.sub(r"\1", text))
    return " / ".join(line.strip() for line in text.split("\n"))


def mod_text(mod: Mod) -> str:
    """The text of `mod` as the page prints it; a mod with no text and no name is its id (the page's own fallback, `mod_words` does not use it)."""
    if mod.text:
        return clean_text(mod.text)
    if mod.name:
        return mod.name
    return f"veiled {mod.generation_type}" if mod.domain == VEILED_DOMAIN else mod.id  # a placeholder has no text


def mod_words(mod: Mod) -> str:
    """`mod` as a person reads it in a sentence: its text on the page; a mod with no text and no name is not named by its id."""
    return mod_text(mod) if (mod.text or mod.name or mod.domain == VEILED_DOMAIN) else NO_TEXT


def mod_words_of(data: GameData, mod_id: str) -> str:
    """The mod with the id `mod_id` as `mod_words` says it; an id the data lacks is not named either."""
    mod = data.mods.get(mod_id)
    return NO_TEXT if mod is None else mod_words(mod)


def base_words(data: GameData, base_id: str) -> str:
    """The base `base_id` by its name in the game."""
    base = data.base_items.get(base_id)
    return base.name if base is not None and base.name else NO_BASE
