"""The disagreements that exist today, each named with its issue, its owner rule and the two values that differ.

A key is `(target file stem, slot)`; the slot names are listed in `checks.py`. The real-data test marks the slot
`xfail(strict=True)`, so it fails when a NEW disagreement appears (the slot is not here) and when a known one
DISAPPEARS (the slot is here and now agrees): the fix then deletes its line from this file. A second test pins
the two values (`value_a`, `value_b` of each disagreement of the slot) to the ones written here, so a known
disagreement that CHANGES also fails.

Every entry names the issue that holds the work (OR-29: a finding is an issue, not prose) and the rule of
`docs/owner-rules.md` that the places break: OR-3 for places that must agree, OR-16 where an Alchemy is hidden
in a start price (R08, R09), OR-7 where a stand-in stands for a trade price.

    #403  owner-rules contradictions: tier default (the R12 start amulet)
    #417  the buy spec and the target describe different start items
    #418  the start price is keyed by base name, not base id
    #425  R04's price is for item level 85 against 81; V01's hand price records no level
    #426  R04, R13, V01 start prices are poe.ninja or hand stand-ins
    #427  targets with no start price or no buy spec
    #428  the spec and the price accept bases with another mod pool
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Known:
    issue: str  # "#403"
    rule: str  # "OR-3"
    why: str
    value_a: str  # the target's side (or the first place), as the check prints it
    value_b: str  # the other place

    @property
    def values(self) -> tuple[str, str]:
        return (self.value_a, self.value_b)


_ATLAS = "Metadata/Items/Armours/Boots/"
_RING = "Metadata/Items/Rings/"
_QUIVER = "Metadata/Items/Quivers/"


def _known(rows: dict[tuple[str, str], tuple[str, str, str, str, str]]) -> dict[tuple[str, str], Known]:
    return {key: Known(*row) for key, row in rows.items()}


KNOWN: dict[tuple[str, str], Known] = _known(
    {
        ("j01-cobalt-life-attack-speed", "start_price.written"): ("#427", "OR-3", "no start_price: the start item is counted free", "none", "free"),
        ("j01-cobalt-life-attack-speed", "buy_spec.exists"): ("#427", "OR-3", "no start price, so no buy spec", "none", "no buy spec"),
        ("r03-avoid-shock-boots", "start_price.written"): ("#427", "OR-3", "no start_price: the start item is counted free", "none", "free"),
        ("r03-avoid-shock-boots", "buy_spec.exists"): ("#427", "OR-3", "no start price, so no buy spec", "none", "no buy spec"),
        ("r06-strength-heavy-belt", "start_price.written"): ("#427", "OR-3", "no start_price: the start item is counted free", "none", "free"),
        ("r06-strength-heavy-belt", "buy_spec.exists"): ("#427", "OR-3", "no start price, so no buy spec", "none", "no buy spec"),
        ("r13-life-resist-belt", "buy_spec.exists"): ("#427", "OR-3", "a price, but no buy spec: the start item is described once", "Leather Belt (ilvl 86)", "no buy spec"),
        ("v01-minion-helmet", "buy_spec.exists"): ("#427", "OR-3", "a price, but no buy spec: the start item is described once", "Lion Pelt (ilvl 84)", "no buy spec"),
        ("r04-penetrating-quiver", "price.base"): ("#418", "OR-3", "the price entry names the base by a name that two bases share", f"{_QUIVER}QuiverNew5", f"{_QUIVER}Quiver12, {_QUIVER}QuiverNew5"),
        ("r04-penetrating-quiver", "price.item_level"): ("#425", "OR-3", "the poe.ninja line the price was read from is item level 85, labelled 81", "81", "85"),
        ("r04-penetrating-quiver", "price.source"): ("#426", "OR-7", "the start price is a poe.ninja stand-in", "trade-api", "poe.ninja"),
        ("r05-strength-ring", "buy.base"): ("#417", "OR-3", "the spec names no base: it prices any ring", "Amethyst Ring", "any accessory.ring"),
        ("r05-strength-ring", "buy.pool"): ("#428", "OR-3", "the spec accepts the Unset Ring and the Bone Ring, which roll other mods", "Amethyst Ring", f"{_RING}Ring15 (+3 -0); {_RING}Ring16 (+23 -0)"),
        ("r05-strength-ring", "price.base"): ("#418", "OR-3", "the price entry is a search by category only: it prices any ring", "Amethyst Ring", "any accessory.ring"),
        ("r05-strength-ring", "price.pool"): ("#428", "OR-3", "the price entry accepts the Unset Ring and the Bone Ring", "Amethyst Ring", f"{_RING}Ring15 (+3 -0); {_RING}Ring16 (+23 -0)"),
        ("r08-energy-shield-boots", "buy.rarity"): ("#417", "OR-16", "the target starts rare, the spec buys a normal base: the Alchemy is hidden in the price", "rare", "normal"),
        ("r09-life-boots", "buy.rarity"): ("#417", "OR-16", "the target starts rare, the spec buys a normal base: the Alchemy is hidden in the price", "rare", "normal"),
        ("r09-life-boots", "buy.pool"): ("#428", "OR-3", "the type Two-Toned Boots is also BootsAtlas2 and BootsAtlas3, other pools", "Two-Toned Boots", f"{_ATLAS}BootsAtlas2 (+45 -62); {_ATLAS}BootsAtlas3 (+45 -45)"),
        ("r09-life-boots", "price.base"): ("#418", "OR-3", "the price entry names the base by a name that three bases share", f"{_ATLAS}BootsAtlas1", f"{_ATLAS}BootsAtlas1, {_ATLAS}BootsAtlas2, {_ATLAS}BootsAtlas3"),
        ("r09-life-boots", "price.pool"): ("#428", "OR-3", "the price entry accepts BootsAtlas2 and BootsAtlas3", "Two-Toned Boots", f"{_ATLAS}BootsAtlas2 (+45 -62); {_ATLAS}BootsAtlas3 (+45 -45)"),
        ("r12-lightning-amulet", "buy.base"): ("#417", "OR-3", "the spec names no base: it prices any amulet", "Paua Amulet", "any accessory.amulet"),
        ("r12-lightning-amulet", "buy.item_level"): ("#417", "OR-3", "the spec prices item level 75, the target plans 84", "84", "75"),
        ("r12-lightning-amulet", "start_mod.LightningResist2.tier"): ("#403", "OR-3", "written tier 3, the data says tier 7 of 8", "3", "7"),
        ("r12-lightning-amulet", "start_mod.LightningResist2.buy_minimum"): ("#403", "OR-3", "the spec has no minimum for the fractured resistance", "tier 7: minimum above 11 and up to 14", "no minimum"),
        ("r12-lightning-amulet", "price.base"): ("#418", "OR-3", "the price entry is a search by category only: it prices any amulet", "Paua Amulet", "any accessory.amulet"),
        ("r12-lightning-amulet", "price.item_level"): ("#418", "OR-3", "the price entry is for item level 75, the target plans 84", "84", "75"),
        ("r13-life-resist-belt", "price.source"): ("#426", "OR-7", "the start price is a poe.ninja stand-in", "trade-api", "poe.ninja"),
        ("r14-hunter-bow", "buy.rarity"): ("#417", "OR-3", "the target starts normal, the spec prices any non-unique item", "normal", "nonunique"),
        ("v01-minion-helmet", "price.item_level"): ("#425", "OR-3", "the hand price records no item level: the check cannot tell", "84", "cannot tell (label 84)"),
        ("v01-minion-helmet", "price.source"): ("#426", "OR-7", "the start price is a hand stand-in", "trade-api", "hand"),
    }
)
