"""A digest of everything the fossil sets without a Bloodstained Fossil answer, to show they did not change (ticket #261).

`digest()` walks sets of one to three fossils of the world of `test_actions_fossil.py` (a Hollow and a Glyphic Fossil together are
out of scope and skipped, the Bloodstained Fossil is left out) on three boots, and writes down in a canonical text what each set
answers: its label and resources, `reads`, `adds`, `twin_key` and claims; its refusal when it refuses the item; otherwise every
component of its outcomes (probability, retained item, forced mod, pool with the exact weights, totals), whether it fractures, the
distribution of the new mods by generation type, the chance of the joint sets of the test world; and, on the empty boots, the exact
kernel of the compressed state for a goal of the fossil layer-1 test. The text is hashed with SHA-256.

Which sets: on the empty boots every set of one or two fossils and every seventeenth set of three; on the other two boots every
single fossil and every pair that holds a Scorched Fossil.

The expected value in `test_actions_fossil_unchanged.py` was taken from the code BEFORE the Bloodstained Fossil was lifted from
`OutOfScopeError`, so the test is a byte comparison with what the ticket calls "the existing fossil kernels". Nothing here depends
on the hash seed: sets, influences and dicts are written in a fixed order.
"""

import hashlib
from dataclasses import fields, is_dataclass
from fractions import Fraction
from itertools import combinations

from test_actions_fossil import BOOTS, DATA, JOINT, boots, roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ActionError, ApplyFossils

BLOODSTAINED = "Bloodstained Fossil"
GOAL = Goal((Wanted(frozenset({"FireA", "FireB"}), min_tier=1), Wanted(frozenset({"LifeA", "LifeB"})), Wanted(frozenset({"FireResA"}))))
TRIPLE_STEP = 17

ITEMS = {
    "empty": lambda: boots(),
    "fractured": lambda: boots(roll("CasterA", fractured=True), roll("LifeA")),
    "junk": lambda: boots(roll("CasterA"), roll("LifeA"), roll("FireResA")),
}


def canon(value):
    """`value` with every set and dict in sorted order and every dataclass as name and fields, so its `repr` is the same in every run."""
    if isinstance(value, (set, frozenset)):
        return sorted((canon(entry) for entry in value), key=repr)
    if isinstance(value, dict):
        return sorted(((canon(key), canon(entry)) for key, entry in value.items()), key=repr)
    if isinstance(value, (list, tuple)):
        return [canon(entry) for entry in value]
    if is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, [(field.name, canon(getattr(value, field.name))) for field in fields(value)])
    return value


# the declarations the contract had before the ticket; a field added later is not part of what "unchanged" compares
READS_FIELDS = (
    "junk families pool_weight needs_crafted block_invariant variants fractures rerolls_values implicits quality offer input_mods".split()
)
ADDS_FIELDS = (
    "named crafted draws tag single_draw keeps_crafted wanted_only fractures needs_roll_limit implicits quality offer corrupts keeps_mods".split()
)


def declared(declaration, names) -> list:
    """The fields `names` of a `Reads` or an `Adds`, in a fixed order."""
    return [(name, canon(getattr(declaration, name))) for name in names]


def item_text(item) -> str:
    """An item written in a fixed order (the influences of a frozenset are sorted)."""
    return repr(
        (
            item.base_id,
            item.item_level,
            item.rarity.value,
            [(m.mod_id, m.tier, m.values, m.fractured, m.crafted) for m in item.mods],
            sorted(i.value for i in item.influences),
            item.corrupted,
            item.implicits,
            item.quality,
            item.veil_offer,
            item.enchantment,
            item.memory_strands,
        )
    )


def state_text(state) -> str:
    flags = state.flags
    return repr(
        (
            flags.rarity.value, flags.corrupted, sorted(i.value for i in flags.influences),
            state.fractured, [int(s) for s in state.status], state.slots, state.implicits, state.quality, state.offer,
        )
    )  # fmt: skip


def part_text(share: Fraction, part) -> str:
    pool = [(f.family, f.side.value, [(e.mod.id, e.weight) for e in f.mods]) for f in part.pool]
    return repr((share, item_text(part.retained), part.forced, part.tag, sorted(part.totals.items()), pool, part.rolls_lucky, sorted(part.guaranteed_blocked)))


def sets_for(name: str) -> list[ApplyFossils]:
    names = sorted(record.name for record in DATA.fossils.values() if record.name and record.name != BLOODSTAINED)
    found = []
    for size in (1, 2, 3):
        for number, chosen in enumerate(combinations(names, size)):
            if {"Hollow Fossil", "Glyphic Fossil"} <= set(chosen):
                continue
            if name == "empty":
                keep = size < 3 or number % TRIPLE_STEP == 0
            else:
                keep = size == 1 or (size == 2 and "Scorched Fossil" in chosen)
            if keep:
                found.append(ApplyFossils(chosen))
    return found


def one_set(item, action: ApplyFossils) -> list[str]:
    lines = [action.label(DATA), repr(sorted(action.resources(DATA).items())), repr(declared(action.reads(DATA), READS_FIELDS)), repr(declared(action.adds(DATA, item), ADDS_FIELDS))]
    lines.append(repr(declared(action.adds(None), ADDS_FIELDS)))
    lines.append(repr(sorted(action.claims(DATA))))
    try:
        lines.append(repr(canon(action.twin_key(DATA, item))))
        outcomes = action.outcomes(DATA, item)
    except ActionError as refusal:
        lines.append(f"refused {type(refusal).__name__}: {refusal}")
        return lines
    lines.append(repr(outcomes.fractures))
    for share, part in outcomes.components:
        lines.append(part_text(share, part))
    lines.append(repr(canon(dict(outcomes.distribution(lambda mod: mod.generation_type)))))
    lines.append(repr([outcomes.chance_all(joint) for joint in JOINT]))
    return lines


def kernel_text(item, action: ApplyFossils) -> str:
    ab = Abstraction(DATA, GOAL, BOOTS, 86, [])
    kernel = ab.kernel(ab.compress(item), action)
    return repr(sorted((state_text(state), chance) for state, chance in kernel.items()))


def digest() -> tuple[str, int]:
    """The SHA-256 of the text of every answer, and how many (item, set) pairs it covers."""
    text = []
    pairs = 0
    for name, make in ITEMS.items():
        item = make()
        for action in sets_for(name):
            pairs += 1
            text.append(f"{name} | " + " | ".join(one_set(item, action)))
            if name == "empty":
                try:
                    text.append(kernel_text(item, action))
                except ActionError as refusal:
                    text.append(f"kernel refused {type(refusal).__name__}")
    return hashlib.sha256("\n".join(text).encode("utf-8")).hexdigest(), pairs


if __name__ == "__main__":
    print(*digest())
