"""Bases and beasts from the poe.ninja stash overview (#40).

`GET .../stash/current/item/overview?league=L&type=BaseType|Beast` answers `{"lines": [...]}`. A base line
is one base at one item level and influence set (`levelRequired`, `variant`: "Hunter" or "Warlord/Hunter",
in no fixed order); a beast line is a beast. `count` is how many observations the price rests on. This
module only reads the answer: which lines are too thin to price is the fetcher's call (`MIN_COUNT`).
"""

from dataclasses import dataclass
from typing import Any

from .http_json import SourceError
from .poe_ninja import is_text
from .price_file import is_price
from .price_names import base_price_name

BASE_TYPE = "BaseType"
BEAST = "Beast"
STASH_TYPES = (BEAST, BASE_TYPE)


@dataclass(frozen=True)
class StashLine:
    key: str  # the price-file name: a base price name, or the beast's name
    chaos: float
    count: int
    line_id: int | None  # poe.ninja's numeric id, the key of the stash history
    kind: str  # "BaseType" or "Beast"


def parse_stash_overview(data: Any, kind: str) -> list[StashLine]:
    """The usable lines of a stash overview of `kind`; a changed shape or no usable line is a `SourceError`.

    A line without a text name, a real `chaosValue`, an int `count` (for a base also an int `levelRequired`)
    or with an influence the game does not have is skipped. Two lines with one key keep the one with the
    higher `count`.
    """
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list):
        raise SourceError("unexpected answer shape (no 'lines' list)")
    best: dict[str, StashLine] = {}
    for raw in lines:
        line = _stash_line(raw, kind)
        if line is not None and (line.key not in best or line.count > best[line.key].count):
            best[line.key] = line
    if not best:
        raise SourceError("no line with a usable price")
    return list(best.values())


def _stash_line(raw: Any, kind: str) -> StashLine | None:
    if not isinstance(raw, dict) or not is_text(raw.get("name")) or not is_price(raw.get("chaosValue")):
        return None
    count = raw.get("count")
    if isinstance(count, bool) or not isinstance(count, int):
        return None
    line_id = raw.get("id")
    line_id = line_id if isinstance(line_id, int) and not isinstance(line_id, bool) else None
    if kind == BASE_TYPE:
        level, variant = raw.get("levelRequired"), raw.get("variant")
        if isinstance(level, bool) or not isinstance(level, int):
            return None
        if variant is not None and not isinstance(variant, str):
            return None
        try:
            key = base_price_name(raw["name"], level, variant.split("/") if variant is not None else ())
        except ValueError:
            return None
    else:
        key = raw["name"]
    return StashLine(key, float(raw["chaosValue"]), count, line_id, kind)
