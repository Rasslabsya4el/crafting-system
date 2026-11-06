"""The chance of each tier of a wanted mod at a step (OR-31, ticket #466).

A guide's "guarantee" is of a family, not of a tier: two Exalted Orbs force the Life and the Bow Skills damage prefixes, and the
chance that each comes at the top tier is 2 in 15 and 1 in 5 (the published odds, `_benchmark_outcomes.py`). So a step that can
add a mod of a family the target wants shows, per family, the chance of each tier: `tier_lines(ab, action, states, weights)`.

The chances are read from the game data for the item at the step, the way `published_outcomes` reads them for "any tier" against
"top tier": the action's own outcomes on the item a state stands for (`Abstraction._prepare`, the item the kernel itself acts on),
seen through a label that is the mod's id for a mod of the family and nothing for the rest (`Outcomes.distribution`, exact), plus
the mod an essence forces (it is kept, not drawn). The chance of tier t is the chance that the use adds that tier's mod. Over the
states of one step they are mixed as the chances of the step are (OR-20): the sum over its states of (weight x chance) divided by the
sum of the weights, the weight being the expected visits of the state from the start (`_route_flow`). "None" is what is left: the
use adds no mod of the family (it holds one already, the draw picked another family, or the action adds nothing). The tiers are the
table tiers of the base (`items.tier_table`, 1 is the best); the tiers the target accepts are marked (`Abstraction.passes`).

Two states with the same draw (the same pool on the same free slots) share one distribution, so a step of thousands of states asks
for as many distributions as it has pools.
"""

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import ActionError, Mixture, Outcomes
from crafting_system.actions.contract import Action
from crafting_system.items import tier_table

from ._route_card import _hashes, _own_text


@dataclass(frozen=True)
class TierShare:
    """The chance, per use, that the use adds the mod of tier `tier`; `wanted`: the target accepts that tier."""

    tier: int
    chance: float
    wanted: bool


@dataclass(frozen=True)
class TierLine:
    """One family the target wants: its text (the game's, ranges as `#`), the chance of each tier, the chance of none of them."""

    text: str
    tiers: tuple[TierShare, ...]
    none: float


@dataclass(frozen=True)
class _Family:
    text: str
    ladder: dict[str, int]  # mod id -> table tier, for every mod of the family that can spawn on the base
    wanted: frozenset[int]


def wanted_families(ab: Abstraction) -> list[_Family]:
    """The families the target wants, one per (families, side, domain): the ladder of the family and the tiers a leaf accepts."""
    data = ab.data
    tiers = tier_table(data, ab.base_id)
    found: dict[tuple, dict[str, int]] = {}
    accepted: dict[tuple, set[int]] = {}
    for index, leaf in enumerate(ab.goal.leaves):
        for mod_id in sorted(leaf.mod_ids):
            mod = data.mods.get(mod_id)
            # a mod the item level lets spawn: a higher tier of the table cannot come at all; a crafted mod is no draw
            if mod is None or mod_id not in tiers or mod.domain == "crafted" or mod.required_level > ab.item_level:
                continue
            key = (mod.families, mod.generation_type, mod.domain)
            found.setdefault(key, {})[mod_id] = tiers[mod_id]  # the ladder is the leaf's own mods: a family can hold other mods (a gem level of another skill)
            accepted.setdefault(key, set())
            if ab.passes(mod, index):
                accepted[key].add(tiers[mod_id])
    families = []
    for key, ladder in found.items():
        best = min(ladder, key=lambda mod_id: (ladder[mod_id], mod_id))
        families.append(_Family(_hashes(_own_text(data.mods[best])), ladder, frozenset(accepted[key])))
    return families


def _signature(outcomes) -> Hashable | None:
    """What decides an exact distribution of a pool draw (None when the outcomes are not made of pool draws)."""
    if isinstance(outcomes, Outcomes):
        return (
            outcomes.pool,
            tuple(sorted((side.value, free) for side, free in outcomes.free.items())),
            outcomes.tag,
            tuple(sorted(outcomes.totals.items())),
            len(outcomes.retained.mods),
            outcomes.guaranteed_blocked,
            outcomes.forced,
        )
    if isinstance(outcomes, Mixture):
        parts = tuple((p, _signature(part)) for p, part in outcomes.components)
        return None if any(part is None for _, part in parts) else (parts, outcomes.fractures)
    return None


def _added(outcomes, wanted_ids: frozenset[str]) -> dict[str, Fraction]:
    """For each id of `wanted_ids`, the exact chance that one use of the action adds that mod (drawn, or forced by an essence)."""
    shown = outcomes.distribution(lambda mod: mod.id if mod.id in wanted_ids else None)
    chance: dict[str, Fraction] = {}
    for outcome, each in shown.items():
        for label, _ in outcome:
            if isinstance(label, str):
                chance[label] = chance.get(label, Fraction(0)) + each
    for share, part in outcomes.components:
        forced = getattr(part, "forced", None)
        if forced in wanted_ids:
            chance[forced] = chance.get(forced, Fraction(0)) + share
    return chance


def tier_lines(
    ab: Abstraction, action: Action, states: Sequence[CompressedState], weights: Sequence[float]
) -> list[TierLine]:
    """The tier line of every wanted family that `action` can add at some of `states`, mixed by `weights`; none when it adds none.

    Raises nothing for a state the action refuses (`ActionError`): it contributes no chance.
    """
    families = wanted_families(ab)
    if not families:
        return []
    ids = frozenset(mod_id for family in families for mod_id in family.ladder)
    adds = action.adds(ab.data, None)
    if adds.named is not None and not adds.draws and not ids & set(adds.named):
        return []  # the action adds only the mods it names, and none of them is in a wanted family
    total = math.fsum(weights)
    sums: list[dict[int, list[float]]] = [{} for _ in families]
    seen: dict[Hashable, dict[str, Fraction]] = {}
    for state, weight in zip(states, weights, strict=True):
        if weight <= 0.0:
            continue
        try:
            outcomes = ab._prepare(state, action).outcomes
        except ActionError:
            continue
        finally:
            ab._prepared_by.clear()  # a policy of thousands of states must not keep a pool for each (the walk clears it after each state too)
        signature = _signature(outcomes)
        if signature is None:
            chance = _added(outcomes, ids)
        else:
            chance = seen.get(signature)
            if chance is None:
                chance = seen[signature] = _added(outcomes, ids)
        for k, family in enumerate(families):
            for mod_id, tier in family.ladder.items():
                if mod_id in chance:
                    sums[k].setdefault(tier, []).append(weight * float(chance[mod_id]))
    lines = []
    for family, per_tier in zip(families, sums, strict=True):
        if not per_tier:
            continue
        shares = {tier: math.fsum(each) / total for tier, each in per_tier.items()}
        shown = sorted(tier for tier in {*shares, *family.wanted} if shares.get(tier, 0.0) > 0.0 or tier in family.wanted)
        lines.append(
            TierLine(
                family.text,
                tuple(TierShare(tier, shares.get(tier, 0.0), tier in family.wanted) for tier in shown),
                max(0.0, 1.0 - math.fsum(shares.values())),
            )
        )
    return lines
