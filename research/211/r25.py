"""R25-shaped worlds: three target prefixes A, B, C on one item class, junk prefixes of several weights."""
import itertools
from world import Cls, World

COSTS = {"alt": 1, "exalt": 50, "annul": 20, "recomb": 140}


def r25(junk_classes, *, raw, targets=("A", "B", "C"), target_weight=100, costs=None, cap=3):
    """`junk_classes`: list of (weight, count). raw=True makes every junk mod its own class (names kept)."""
    classes = [Cls(t, "p", target_weight, named=True) for t in targets]
    for i, (weight, count) in enumerate(junk_classes):
        if raw:
            classes += [Cls(f"J{weight}_{k}", "p", weight) for k in range(count)]
        else:
            classes.append(Cls(f"J{weight}", "p", weight, size=count))
    goal_tokens = tuple(sorted(targets))
    w = World(classes, costs=costs or COSTS, caps={"p": cap, "s": 0}, goal=lambda s: s[1] == goal_tokens)
    return w


def all_states(world):
    """Every item the world can hold (multisets of classes, within the cap and the class sizes)."""
    names = sorted(world.classes)
    out = []
    for n in range(world.caps["p"] + 1):
        for combo in itertools.combinations_with_replacement(names, n):
            counts = {}
            for t in combo:
                counts[t] = counts.get(t, 0) + 1
            if all(counts[t] <= world.classes[t].size for t in counts):
                out.append(world.state(combo))
    return out
