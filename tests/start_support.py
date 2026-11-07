"""A target text with the lines a target file must carry: `start: given` or `start: bought` (OR-6, #505) and a `start_item:` with its `rarity:` (#545).

Most tests are about something else (a mod, a tier, an action) and write a target from a few lines. `with_start(text)` closes such a text with
`start: given` unless it says how the start item is had, at the END of the text so that no line number of the text moves. It also states the
start item the way the files must: a text with no `start_item:` gets one with `rarity: normal` at the end, and a `start_item:` block with no
`rarity:` gets one at the end of the block (`rare` when the block lists `mods:`, else `normal`, the guesses the parser used to make). A text
that asks for `sockets:` gets `sockets: any` in its start item unless the block states its own. A test of a key itself writes it by hand, or
passes `start=None` / `item=False` / `sockets=None` to leave it out.
"""

import re

__all__ = ["with_start"]

_HAS_START = re.compile(r"(?m)^start\s*:")
_START_ITEM = re.compile(r"^start_item\s*:\s*(#.*)?$")
_RARITY = re.compile(r"^\s+rarity\s*:")
_MODS = re.compile(r"^\s+mods\s*:")
_SOCKETS = re.compile(r"^\s+sockets\s*:")
_ASKS_SOCKETS = re.compile(r"(?m)^sockets\s*:")


def _is_a_mapping(text: str) -> bool:
    """Whether `text` starts like one YAML mapping (a first line `key:`, and no second document); other texts are tests of that refusal."""
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return bool(lines) and re.match(r"[A-Za-z_]\w*\s*:", lines[0]) is not None and not any(line.startswith("---") for line in lines)


def _states_start_item(text: str, sockets: str | None) -> str:
    """`text` with a `start_item:` block that carries a `rarity:` (and `sockets`, when the text asks for them), adding what is missing."""
    lines = text.split("\n")
    where = next((i for i, line in enumerate(lines) if _START_ITEM.match(line)), None)
    asks = sockets is not None and _ASKS_SOCKETS.search(text) is not None
    if where is None:
        if any(re.match(r"start_item\s*:", line) for line in lines):
            return text  # a flow-style block (`start_item: {…}`) is left as written
        added = "  rarity: normal\n" + (f"  sockets: {sockets}\n" if asks else "")
        return f"{text}{'' if text.endswith(chr(10)) else chr(10)}start_item:\n{added}"
    end = where + 1
    last = where
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t"):
        if lines[end].strip():
            last = end
        end += 1
    block = lines[where + 1 : last + 1]
    indent = re.match(r"\s*", next((line for line in block if line.strip()), "  ")).group()  # the keys of the block, however far in
    added = []
    if not any(_RARITY.match(line) for line in block):
        added.append(f"{indent}rarity: {'rare' if any(_MODS.match(line) for line in block) else 'normal'}")
    if asks and not any(_SOCKETS.match(line) for line in block):
        added.append(f"{indent}sockets: {sockets}")
    lines[last + 1 : last + 1] = added
    return "\n".join(lines)


def with_start(text: str, start: str | None = "given", *, item: bool = True, sockets: str | None = "any") -> str:
    """`text` plus a final `start: <start>` line and a stated start item, unless it has them already or they are left out.

    `start=None` leaves out the `start:` line, `item=False` the start item and `sockets=None` its sockets (a test of that refusal); an empty
    text, or one of only comments, is returned as it is.
    """
    if not any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines()):
        return text  # nothing to close: the file is empty (or only comments)
    if item and _is_a_mapping(text):
        text = _states_start_item(text, sockets)
    if start is None or _HAS_START.search(text):
        return text  # the key is there, or left out on purpose
    return f"{text}{'' if text.endswith(chr(10)) else chr(10)}start: {start}\n"
