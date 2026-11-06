"""The disagreements that exist today, each named with its issue and its owner rule.

A key is `(target file stem, slot)`; the slot names are listed in `checks.py`. The real-data test marks
the slot `xfail(strict=True)`, so it fails when a NEW disagreement appears (the slot is not here) and when
a known one DISAPPEARS (the slot is here and now agrees): the fix then deletes its line from this file.

Every entry names the issue that holds the work (OR-29: a finding is an issue, not prose) and the rule
of `docs/owner-rules.md` that the places break.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Known:
    issue: str  # "#403"
    rule: str  # "OR-3"
    why: str


# #403  owner-rules contradictions: tier default (the R12 start amulet)
# #417  the buy spec and the target describe different start items (filed by #412)
# #418  the start price is keyed by base name, not base id (filed by #412; related: #406 prices)
_NO_BASE = "the spec names no base: it prices any item of the category"
_CATEGORY_ONLY = "the price entry is a search by category only: it prices any item of the category"
_SHARED_NAME = "the price entry names the base by a name that several bases share"

KNOWN: dict[tuple[str, str], Known] = {
    ("r04-penetrating-quiver", "price.base"): Known("#418", "OR-6", _SHARED_NAME),
    ("r05-strength-ring", "buy.base"): Known("#417", "OR-6", _NO_BASE),
    ("r05-strength-ring", "price.base"): Known("#418", "OR-6", _CATEGORY_ONLY),
    ("r08-energy-shield-boots", "buy.rarity"): Known("#417", "OR-6", "the target starts rare, the spec buys a normal base"),
    ("r09-life-boots", "buy.rarity"): Known("#417", "OR-6", "the target starts rare, the spec buys a normal base"),
    ("r09-life-boots", "price.base"): Known("#418", "OR-6", _SHARED_NAME),
    ("r12-lightning-amulet", "buy.base"): Known("#417", "OR-6", _NO_BASE),
    ("r12-lightning-amulet", "buy.item_level"): Known("#417", "OR-6", "the spec prices item level 75, the target plans 84"),
    ("r12-lightning-amulet", "start_mod.LightningResist2.tier"): Known("#403", "OR-3", "written tier 3, the data says tier 7 of 8"),
    ("r12-lightning-amulet", "start_mod.LightningResist2.buy_minimum"): Known("#403", "OR-3", "the spec has no minimum for the fractured resistance"),
    ("r12-lightning-amulet", "price.base"): Known("#418", "OR-6", _CATEGORY_ONLY),
    ("r12-lightning-amulet", "price.item_level"): Known("#418", "OR-6", "the price entry is for item level 75, the target plans 84"),
    ("r13-life-resist-belt", "price.base"): Known("#418", "OR-6", _SHARED_NAME),
    ("r14-hunter-bow", "buy.rarity"): Known("#417", "OR-6", "the target starts normal, the spec prices any non-unique item"),
}
