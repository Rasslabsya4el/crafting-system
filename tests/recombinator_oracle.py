"""A hand oracle for the recombinator (ticket #215), independent of `crafting_system.actions`.

It plays the unpredictable mode of ADR-0033 as plain code over the mods of a `GameData` and two `Item`s, with exact `Fraction`s: it
uses no pool builder, no `Finite`, no kernel. The only things it shares are the data (`Mod` fields: families, side, spawn weights)
and the item fields. The rules it plays:

* each input is the base with chance 1/2; its tags are those of its base (no influences in these cases);
* an entry is exclusive when it is crafted, essence-only or has no spawn weight on its own input's tags; a non-exclusive entry with
  no spawn weight on the base's tags cannot appear; a fractured entry appears only on its own base; an exclusive entry weighs 1000;
* the pooled count of a side is its number of non-exclusive entries plus one if it holds an exclusive entry; the number kept on a
  side comes from the renormalised row of the table, capped at 3; one mod on each input, on opposite sides, gives 1p, 1s or 1p1s;
* one side is filled first (1/2 each); a side is drawn one entry at a time with chance `weight ** alpha` among the entries that are
  eligible, of no closed family and not a second exclusive; a pick closes its families (and its own id); a dry pool stops the side.
"""

from fractions import Fraction
from itertools import product

EXCLUSIVE_WEIGHT = 1000
CAP = 3


def _weight_on(mod, tags) -> int:
    for entry in mod.spawn_weights:
        if entry.tag in tags:
            return entry.weight
    return 0


def _power(weight: int, alpha: Fraction) -> Fraction:
    return Fraction(weight) ** alpha.numerator if alpha.denominator == 1 else Fraction(float(weight) ** float(alpha))


def _rows(table: dict) -> dict:
    rows = {0: {0: Fraction(1)}}
    for pooled, row in table.items():
        total = sum(Fraction(str(v)) for v in row.values())
        rows[pooled] = {kept: Fraction(str(v)) / total for kept, v in row.items()}
    return rows


def _side_draw(pool: list[dict], count: int, blocked: frozenset, exclusive_taken: bool):
    """`{(picked ids, blocked, exclusive_taken): chance}` after `count` successive picks from `pool` (a dry pool stops early)."""
    states = {((), blocked, exclusive_taken): Fraction(1)}
    for _ in range(count):
        following: dict = {}
        for (picked, closed, taken), chance in states.items():
            live = [
                e
                for e in pool
                if e["eligible"]
                and e["key"] not in picked
                and not (e["id"] in closed or e["families"] & closed)
                and not (taken and e["exclusive"])
            ]
            if not live:
                following[(picked, closed, taken)] = following.get((picked, closed, taken), 0) + chance
                continue
            total = sum(e["w"] for e in live)
            for e in live:
                state = ((*picked, e["key"]), closed | e["families"] | {e["id"]}, taken or e["exclusive"])
                following[state] = following.get(state, 0) + chance * e["w"] / total
        states = following
    return states


def distribution(data, a, b, alpha, table: dict) -> dict:
    """`{frozenset of kept (input, mod id): chance}` over the choice of base, the counts, the side order and the draws."""
    alpha = Fraction(alpha)
    rows = _rows(table)
    inputs = (a, b)
    result: dict = {}
    for base_index in (0, 1):
        base_tags = set(data.base_items[inputs[base_index].base_id].tags)
        entries = []
        for source, item in enumerate(inputs):
            own_tags = set(data.base_items[item.base_id].tags)
            for mod in item.mods:
                found = data.mods[mod.mod_id]
                exclusive = mod.crafted or found.is_essence_only or _weight_on(found, own_tags) == 0
                weight = EXCLUSIVE_WEIGHT if exclusive else _weight_on(found, base_tags)
                eligible = weight > 0 and not (mod.fractured and source != base_index)
                entries.append(
                    {
                        "key": (source, mod.mod_id),
                        "id": mod.mod_id,
                        "side": found.generation_type,
                        "families": frozenset(found.families),
                        "exclusive": exclusive,
                        "eligible": eligible,
                        "w": _power(weight, alpha) if weight > 0 else Fraction(0),
                    }
                )
        pools = {side: [e for e in entries if e["side"] == side] for side in ("prefix", "suffix")}
        pooled = {
            side: sum(1 for e in pool if not e["exclusive"]) + (1 if any(e["exclusive"] for e in pool) else 0)
            for side, pool in pools.items()
        }
        sides = [{data.mods[m.mod_id].generation_type for m in item.mods} for item in inputs]
        if all(len(item.mods) == 1 for item in inputs) and sides[0] != sides[1]:
            counts = {(1, 0): Fraction(1, 3), (0, 1): Fraction(1, 3), (1, 1): Fraction(1, 3)}
        else:
            counts = {
                (kp, ks): rows[pooled["prefix"]][kp] * rows[pooled["suffix"]][ks]
                for kp, ks in product(rows[pooled["prefix"]], rows[pooled["suffix"]])
            }
        for (kp, ks), chance in counts.items():
            want = {"prefix": min(kp, CAP), "suffix": min(ks, CAP)}
            for first, second in (("prefix", "suffix"), ("suffix", "prefix")):
                for (p1, closed, taken), c1 in _side_draw(pools[first], want[first], frozenset(), False).items():
                    for (p2, _, _), c2 in _side_draw(pools[second], want[second], closed, taken).items():
                        key = frozenset((*p1, *p2))
                        result[key] = result.get(key, 0) + chance * c1 * c2 / 4
    return result


def chance_of_holding(data, a, b, alpha, table: dict, wanted: set) -> Fraction:
    """The chance that the output holds every mod id in `wanted`."""
    return sum(
        (chance for kept, chance in distribution(data, a, b, alpha, table).items() if wanted <= {mod_id for _, mod_id in kept}),
        Fraction(0),
    )
