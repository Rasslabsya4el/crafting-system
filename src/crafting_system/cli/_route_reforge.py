"""A bought Normal start whose first step reforges a Rare one alike: the player may buy either (#1673, OR-43, OR-16).

A target may start from a Normal base nobody lists, an influenced Heavy Belt for one (R06), while the market sells Rare ones. When the plan's
first step reforges the item whatever it holds, on a Normal and on a Rare item alike (an essence of level 5 or higher), the Rare one is the
same start: the step removes its mods and draws the same item from the same pool. The route page then tells the player to buy a Normal or a
Rare one, and its trade link searches both (the trade site's "any rarity but unique"; a Magic one, which the step refuses, is excluded by the
page's words only). The plan itself is planned from the Normal base: a Rare start's draw of the bought mods widens the search for nothing
(#1685).

The rule is read from the action itself, not from a list of names: the step is used on the start, and again on the Rare item it made; when the
second use keeps the same item, with the same counts of new mods from the same pool, the step is a full reforge of a Rare item (Alchemy,
Transmutation and Chaos refuse one of the two; an Exalted Orb or a bench craft changes what the second use keeps).
"""

from dataclasses import replace

from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.data import GameData
from crafting_system.items import Rarity
from crafting_system.planner import Plan
from crafting_system.prices import BuySpec

__all__ = ["NORMAL_OR_RARE", "either_rarity", "link_spec", "reforged_start"]


def reforged_start(data: GameData, plan: Plan) -> str | None:
    """The label of the plan's first step when it reforges the bought Normal start and a Rare one alike, else None."""
    price, item = plan.start_price, plan.target.start_item
    if not price.bought or price.made is not None or price.searched is not None or item.rarity is not Rarity.NORMAL or item.mods:
        return None
    if plan.start.flags.unopened:  # a listing opened by a draw is the market's own item already
        return None
    first = plan.policy.get(plan.start)
    if first is None:
        return None
    try:
        action = plan.offer_of(first).offer.action
        made = action.outcomes(data, item)
        retained = getattr(made, "retained", None)
        if retained is None or retained.rarity is not Rarity.RARE:
            return None
        again = action.outcomes(data, retained)
    except (NotApplicableError, OutOfScopeError):  # the step refuses the Normal start or the Rare item it makes: no reforge of both
        return None
    same = getattr(again, "retained", None) == retained and dict(getattr(again, "totals", {})) == dict(made.totals)
    return first.label if same and getattr(again, "pool", None) == made.pool else None


NORMAL_OR_RARE = "Normal or Rare"


def either_rarity(accepts: list[str], name: str | None, step: str) -> tuple[list[str], str | None]:
    """The buy step's Accepts lines and item name for a start the first step reforges at either rarity: "Normal or Rare" in place of the
    rarity word, and one line that says why, naming the step."""
    head, *rest = accepts or [""]
    for prefix in ("Any rarity but unique", "Normal"):  # the link's search (`link_spec`), or the start item's own card ("Normal" alone)
        if head == prefix or head.startswith(f"{prefix} "):
            head = f"{NORMAL_OR_RARE}{head.removeprefix(prefix)}"
            break
    why = (
        f"a Normal or a Rare one with no fractured or crafted mod and no other influence, the cheaper: the first step, {step}, reforges "
        "either alike, with no Orb of Scouring"
    )
    if name is not None:
        name = name.replace(", normal,", f", {NORMAL_OR_RARE},", 1) if ", normal," in name else f"{name} ({NORMAL_OR_RARE})"
    return [head, *rest, why], name


def link_spec(spec: BuySpec) -> BuySpec:
    """The search of a start the first step reforges at either rarity: the same item at any rarity but unique (the trade site has no
    "Normal or Rare"; the Accepts line leaves a Magic one out), so the link finds what the player is told to buy."""
    return replace(spec, rarity="nonunique")
