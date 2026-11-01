"""R18-shaped world: a Crusader ring that must carry the Shaper suffix AM and its own T1 %ES prefix ES, joined by the Awakener's Orb."""
import itertools
from collections import Counter
from world import Cls, World

C, S = "C", "S"


def r18(*, junk_per_class=1, plain=2, weight_classes=1, price_am=400, costs=None):
    classes = [
        Cls("ES", "p", 100, infl=C, named=True),
        Cls("CJp", "p", 300, size=junk_per_class, infl=C),
        Cls("SJp", "p", 300, size=junk_per_class, infl=S),
        Cls("P500", "p", 500, size=plain),
        *([Cls("P1000", "p", 1000, size=plain)] if weight_classes > 1 else []),
        Cls("AM", "s", 100, infl=S, named=True),
        Cls("CJs", "s", 300, size=junk_per_class, infl=C),
        Cls("SJs", "s", 300, size=junk_per_class, infl=S),
        Cls("S500", "s", 500, size=plain),
        *([Cls("S1000", "s", 1000, size=plain)] if weight_classes > 1 else []),
    ]
    blank_s = ((S,), ())
    base_costs = {"chaos": 1, "exalt": 8, "annul": 4, "awk": 60,
                  "buys": {"buy_AM": (blank_s, ((S,), ("AM",)), price_am)}}
    if costs:
        base_costs.update(costs)
    goal = lambda s: set(s[0]) == {C, S} and "ES" in s[1] and "AM" in s[1]
    return World(classes, costs=base_costs, caps={"p": 3, "s": 3}, goal=goal)


def donors_for(world, state):
    """Every projection of a donor the Awakener could take at `state`: the other influence, one to several of its influenced mods."""
    if len(state[0]) != 1 or not any(world.classes[t].infl for t in state[1]):
        return []
    other = S if state[0][0] == C else C
    cls = [c for c in world.classes.values() if c.infl == other]
    out = []
    ranges = [range(0, min(c.size, 3) + 1) for c in cls]
    for counts in itertools.product(*ranges):
        if sum(counts) == 0:
            continue
        sides = Counter()
        tokens = []
        for c, n in zip(cls, counts):
            sides[c.side] += n
            tokens += [c.name] * n
        if any(sides[sd] > world.caps[sd] for sd in sides):
            continue
        out.append(((other,), tuple(sorted(tokens))))
    return out


def closure(world, starts, candidates):
    seen, stack = set(starts), list(starts)
    while stack:
        s = stack.pop()
        nxt = [j for _, _, dist in world.base_actions(s) for j in dist]
        for kind, d in candidates(s):
            dist = world.k_awakener(s, d) if kind == "awk" else world.k_recomb(s, d)
            nxt += list(dist or ())
        for j in nxt:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    return seen
