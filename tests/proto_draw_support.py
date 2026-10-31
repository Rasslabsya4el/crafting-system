"""Synthetic pools and event probabilities for the prototype's known answers on the exact draw engine (ticket #73).

The pools are built by hand: a `Mod` record per candidate, grouped into `PoolFamily` records. Nothing
here recomputes a draw; `chance` only adds up the probabilities `exact_distribution` returns.
"""

from collections.abc import Callable, Mapping
from fractions import Fraction

from crafting_system.actions.draw import Outcome, exact_distribution
from crafting_system.actions.pool import PoolFamily, PoolMod
from crafting_system.data import Mod
from crafting_system.items import Side

PREFIX, SUFFIX = Side.PREFIX, Side.SUFFIX
NO_CAP = {PREFIX: 3, SUFFIX: 3}


def synthetic_mod(mod_id: str, family: str, side: Side) -> Mod:
    """A hand-made mod: only its id, family and side matter to a draw."""
    return Mod(
        id=mod_id,
        name=mod_id,
        text=None,
        type=family,
        families=(family,),
        domain="item",
        generation_type=side.value,
        required_level=1,
        spawn_weights=(),
        generation_weights=(),
        adds_tags=(),
        implicit_tags=(),
        stats=(),
        is_essence_only=False,
    )


def family(name: str, side: Side, *weights: int | tuple[str, int]) -> PoolFamily:
    """A family of the given side; a plain weight is one mod named like the family, a `(mod id, weight)` pair adds a mod."""
    entries = []
    for weight in weights:
        mod_id, value = (name, weight) if isinstance(weight, int) else weight
        entries.append(PoolMod(synthetic_mod(mod_id, name, side), Fraction(value)))
    return PoolFamily(name, side, tuple(entries))


def draws(count: int) -> Mapping[int, Fraction]:
    """The totals of a reroll that always draws exactly `count` mods."""
    return {count: Fraction(1)}


def distribution(
    pool: tuple[PoolFamily, ...],
    free: Mapping[Side, int] = NO_CAP,
    totals: Mapping[int, Fraction] | None = None,
    label: Callable[[Mod], object] = lambda mod: mod.id,
) -> dict[Outcome, Fraction]:
    """`exact_distribution` with no guaranteed tag and no kept mod, after checking that it sums to exactly 1."""
    shown = exact_distribution(pool, free, None, totals if totals is not None else draws(1), 0, label)
    assert sum(shown.values()) == 1
    return shown


def drawn(outcome: Outcome) -> frozenset:
    """The labels an outcome holds, each counted once."""
    return frozenset(name for name, _ in outcome)


def chance(shown: Mapping[Outcome, Fraction], event: Callable[[frozenset], bool]) -> Fraction:
    """The probability that the set of drawn labels satisfies `event`."""
    return sum((value for outcome, value in shown.items() if event(drawn(outcome))), Fraction(0))
