"""The Memory Strands count of an item and its line in a pasted item text (ADR-0040).

An item carries `Item.memory_strands`, a whole number from 0 to 100 (0 when the item has none). The game shows the count on an
item as one property line, `Memory Strands: 57`, and only when it is 1 or more; the planner reads that line from a pasted
item text and prints it back the same way. The cut and the spend of the count are rules of `actions`, not of this module.
"""

import re

from .errors import MemoryStrandsError

MAX_MEMORY_STRANDS = 100
STRANDS_LABEL = "Memory Strands"
_LINE = re.compile(rf"\s*{STRANDS_LABEL}:(.*)")
_WHOLE_NUMBER = re.compile(r"\s*[0-9]+\s*")


def memory_strands_line(count: int) -> str | None:
    """The line the game shows for `count` strands (`Memory Strands: 57`), or None for 0, which shows no line."""
    if type(count) is not int or not 0 <= count <= MAX_MEMORY_STRANDS:
        raise MemoryStrandsError(f"memory strands {count!r} is not a whole number from 0 to {MAX_MEMORY_STRANDS}")
    return f"{STRANDS_LABEL}: {count}" if count else None


def read_memory_strands(text: str) -> int:
    """The count of a pasted item text: the number on its `Memory Strands: N` line, 0 when the text has no such line.

    The line is found whatever the lines around it, so a whole pasted item and the single line both work. Raises
    `MemoryStrandsError` for a line that holds anything but a whole number from 0 to 100, and for two such lines.
    """
    found = [match for line in text.splitlines() if (match := _LINE.fullmatch(line))]
    if len(found) > 1:
        raise MemoryStrandsError(f"the item text has {len(found)} `{STRANDS_LABEL}:` lines, an item has one count")
    if not found:
        return 0
    value = found[0].group(1)
    if not _WHOLE_NUMBER.fullmatch(value):
        raise MemoryStrandsError(f"`{STRANDS_LABEL}:{value}` is not a whole number")
    count = int(value)
    if count > MAX_MEMORY_STRANDS:
        raise MemoryStrandsError(f"{count} memory strands is more than the {MAX_MEMORY_STRANDS} an item can hold")
    return count
