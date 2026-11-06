"""A target text with the line a target file must carry since #505: `start: given` or `start: bought` (OR-6).

Most tests are about something else (a mod, a tier, an action) and write a target from a few lines. `with_start(text)` closes such a text with
`start: given` unless it says how the start item is had, at the END of the text so that no line number of the text moves. A test of the key
itself writes it by hand.
"""

import re

__all__ = ["with_start"]

_HAS_START = re.compile(r"(?m)^start\s*:")


def with_start(text: str, start: str | None = "given") -> str:
    """`text` plus a final `start: <start>` line, unless it has a `start:` line already or `start` is None (the key left out)."""
    if start is None or _HAS_START.search(text) or not any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines()):
        return text  # nothing to close: the key is there, left out on purpose, or the file is empty (or only comments)
    return f"{text}{'' if text.endswith(chr(10)) else chr(10)}start: {start}\n"
