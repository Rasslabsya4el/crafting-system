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
    #417  the buy spec and the target describe different start items (left: R08, R09, the hidden Alchemy; the spec is computed from
          the target since #474, so the other rows are gone)
    #418  the start price is keyed by base name, not base id (the key says the base since #474; rows moved to #483 and #486)
    #425  R04's price is for item level 85 against 81; V01's hand price records no level
    #426  R04, R13, V01 start prices are poe.ninja or hand stand-ins
    #427  targets with no start price (J01, R03, R06); the buy spec of the others is computed since #474
    #428  the spec and the price accept bases with another mod pool (rows moved to #483 and #486)
    #483  the exact start item of R05, R10, R11, R12, R14 has no trade market, so the committed price is for a wider item
    #486  the trade site cannot tell bases of one name apart (R09 Two-Toned Boots, R04 quivers)

Since #474 the buy spec is not a hand-written file: `derived_specs/<target>.yaml` is what the planner computes from the target, written
down by `tests/test_start_buy_real.py` (which holds it equal to the planner's result), and the price key of each target is the table
`expected_keys.txt`. So the buy rows below compare the computed spec with the target and the game data.
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
        ("r04-penetrating-quiver", "price.base"): ("#486", "OR-3", "the price entry is by a name that two bases share, and neither the trade site nor poe.ninja can tell them apart", f"{_QUIVER}QuiverNew5", f"{_QUIVER}Quiver12, {_QUIVER}QuiverNew5"),
        ("r04-penetrating-quiver", "price.item_level"): ("#425", "OR-3", "the poe.ninja line the price was read from is item level 85, labelled 81", "81", "85"),
        ("r04-penetrating-quiver", "price.source"): ("#426", "OR-7", "the start price is a poe.ninja stand-in", "trade-api", "poe.ninja"),
        ("r05-strength-ring", "price.base"): ("#483", "OR-3", "the price entry is a search by category only: it prices any ring; the exact item has no market (0 listings)", "Amethyst Ring", "any accessory.ring"),
        ("r05-strength-ring", "price.pool"): ("#483", "OR-3", "the price entry accepts the Unset Ring and the Bone Ring; the exact item has no market", "Amethyst Ring", f"{_RING}Ring15 (+3 -0); {_RING}Ring16 (+23 -0)"),
        ("r08-energy-shield-boots", "buy.rarity"): ("#417", "OR-16", "the target starts rare, the spec buys a normal base: the Alchemy is hidden in the price", "rare", "normal"),
        ("r09-life-boots", "buy.rarity"): ("#417", "OR-16", "the target starts rare, the spec buys a normal base: the Alchemy is hidden in the price", "rare", "normal"),
        ("r09-life-boots", "buy.pool"): ("#486", "OR-3", "the trade site has one type Two-Toned Boots for BootsAtlas2 and BootsAtlas3 too, other pools: it cannot tell them apart", "Two-Toned Boots", f"{_ATLAS}BootsAtlas2 (+45 -62); {_ATLAS}BootsAtlas3 (+45 -45)"),
        ("r09-life-boots", "price.base"): ("#486", "OR-3", "the price entry is by a name that three bases share, and the trade site cannot tell them apart", f"{_ATLAS}BootsAtlas1", f"{_ATLAS}BootsAtlas1, {_ATLAS}BootsAtlas2, {_ATLAS}BootsAtlas3"),
        ("r09-life-boots", "price.pool"): ("#486", "OR-3", "the price entry accepts BootsAtlas2 and BootsAtlas3", "Two-Toned Boots", f"{_ATLAS}BootsAtlas2 (+45 -62); {_ATLAS}BootsAtlas3 (+45 -45)"),
        ("r12-lightning-amulet", "start_mod.LightningResist2.tier"): ("#403", "OR-3", "written tier 3, the data says tier 7 of 8", "3", "7"),
        ("r12-lightning-amulet", "price.base"): ("#483", "OR-3", "the price entry is a search by category only: it prices any amulet; the exact item has 1 listing", "Paua Amulet", "any accessory.amulet"),
        ("r12-lightning-amulet", "price.item_level"): ("#483", "OR-3", "the price entry is for item level 75, the target plans 84; the exact item has 1 listing", "84", "75"),
        ("r13-life-resist-belt", "price.source"): ("#426", "OR-7", "the start price is a poe.ninja stand-in", "trade-api", "poe.ninja"),
        ("v01-minion-helmet", "price.item_level"): ("#425", "OR-3", "the hand price records no item level: the check cannot tell", "84", "cannot tell (label 84)"),
        ("v01-minion-helmet", "price.source"): ("#426", "OR-7", "the start price is a hand stand-in", "trade-api", "hand"),
    }
)
