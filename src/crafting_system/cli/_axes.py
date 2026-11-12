"""The rule axes in a player's words: the one table every sentence about an axis reads (ticket #618, OR-13).

A rule axis is a rule the sources leave open, with the values it may take (the glossary's "rule axis"). The id of an axis
(`elemental_cap`, `awakener.group_conflict`) and of its values (`coe`, `wiki_developer_table`) is for the JSON answer and for the
code; the text report and the route page say the axis and each value in the words of this table, and nowhere else. An axis with no
entry here cannot be worded: `AXIS_WORDS[axis]` raises, and `tests/test_cli_player_words.py` fails for every axis the code defines
(an `Axis` of the `actions` package or the axis of a vendor recipe) that has no entry or lacks the words of one of its values.
"""

from collections.abc import Hashable
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class AxisWords:
    """What a player reads for one axis: `name` in a `name = value` line, `what` as the rule's own sentence and `values` as the words of
    each value (None for an axis whose values are numbers, which are shown as they are)."""

    name: str
    what: str
    values: dict[str, str] | None = None


AXIS_WORDS: dict[str, AxisWords] = {
    "recombinator.alpha": AxisWords(
        "alpha",
        "the recombinator's mod selection exponent alpha (a mod is kept in proportion to its weight to the power alpha)",
    ),
    "awakener.group_conflict": AxisWords(
        "group conflict",
        "which mod survives when the Awakener's Orb meets a group conflict",
        {"receiver": "the receiver's mod is kept", "donor": "the donor's mod is kept"},
    ),
    "chromatic_forced_colour": AxisWords(
        "forced socket colour",
        "the colour of the socket a Chromatic Orb forces when every socket rolled white",
        {
            "siveran_weights": "the weights of a natural socket",
            "flatter_second_reading": "a flatter split than the natural weights",
        },
    ),
    "jeweller_table": AxisWords(
        "Jeweller's Orb socket odds",
        "the odds of each socket count a Jeweller's Orb rolls",
        {
            "wiki_developer_table": "the wiki's item-generation weights",
            "chris_wilson_2014": "the 2014 table of a Grinding Gear Games staff member",
        },
    ),
    "corruption.vaal_brick": AxisWords(
        "Vaal brick",
        "what a Vaal Orb keeps when it turns the item into a rare with six random mods",
        {
            "wiki": "the fractured mods and a side locked by a bench craft stay (the wiki)",
            "coe": "every mod goes, fractured ones too, and no lock holds (Craft of Exile)",
        },
    ),
    "elemental_cap": AxisWords(
        "elemental recipe cap",
        "the best tier the vendor recipes that raise an elemental damage mod can reach (tier 1 is the best)",
        {"wiki": "the wiki's tier 3", "coe": "Craft of Exile's tier 2"},
    ),
}


def axis_name(axis: str) -> str:
    """The axis as a player reads it in a `name = value` line."""
    return AXIS_WORDS[axis].name


def axis_what(axis: str) -> str:
    """The rule an axis stands for, in a phrase."""
    return AXIS_WORDS[axis].what


def value_text(axis: str, value: Hashable) -> str:
    """A value of an axis in words: a number as it is (whole numbers without a decimal point), the others from the table."""
    words = AXIS_WORDS[axis]
    if words.values is None:
        number = float(value) if isinstance(value, int | float | Fraction) else None
        if number is None:
            raise ValueError(f"the axis {axis} takes numbers, got {value!r}")
        return f"{number:,.0f}" if number.is_integer() else f"{number:g}"
    return words.values[str(value)]


def reading_pair(axis: str, value: Hashable) -> str:
    """`alpha = 1`, `elemental recipe cap = Craft of Exile's tier 2`: one axis at one value."""
    return f"{axis_name(axis)} = {value_text(axis, value)}"
