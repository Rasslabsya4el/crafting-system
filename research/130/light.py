"""A light, fast copy of the exact kernels of the seven orbs for the R14-like bow, validated against the real Abstraction.

State: (rarity, slots) with rarity in 0 normal, 1 magic, 2 rare and slots a sorted tuple of (side, kind, contrib)
(= Slot.key[:3]). Goal states are not expanded. Probabilities are floats or Fractions (set `num`).
"""
from common import *
from fractions import Fraction
from collections import Counter, defaultdict
from crafting_system.abstraction import Abstraction

NORMAL, MAGIC, RARE = 0, 1, 2
CAPS = {MAGIC: {"prefix": 1, "suffix": 1}, RARE: {"prefix": 3, "suffix": 3}}


class Light:
    def __init__(self, d, ab, num=float, merge=False):
        self.d, self.ab, self.num = d, ab, num
        pool = build_pool(d, Item.build(d, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE,
                                        influences=frozenset({Influence.HUNTER})))
        info = {}
        for f in pool:
            kind = ab.kind_of(f.mods[0].mod)
            classes = Counter()
            for pm in f.mods:
                c = tuple(int(x) for x in ab._drawn_contribution(pm.mod))
                classes[c] += pm.weight
            classes = tuple(sorted((c, int(w)) for c, w in classes.items()))
            if merge == "real":  # ADR-0009's family type: the side and the sorted (contribution, weight) of every mod
                per_mod = tuple(sorted((tuple(int(x) for x in ab._drawn_contribution(pm.mod)), int(pm.weight)) for pm in f.mods))
                kind = "R|" + f.side.value + "|" + repr(per_mod)
            elif merge:  # a coarser exact merge: the side and the total weight of each contribution
                kind = "T|" + f.side.value + "|" + repr(classes)
            if kind in info:
                assert info[kind]["classes"] == classes and info[kind]["side"] == f.side.value, kind
                info[kind]["N"] += 1
                info[kind]["names"].append(f.family)
            else:
                info[kind] = dict(side=f.side.value, N=1, classes=classes, names=[f.family])
        for v in info.values():
            v["W"] = sum(w for _, w in v["classes"])
        self.info = info
        self.width = len(ab.goal.leaves)

    # --- statuses ---------------------------------------------------------------------------------
    def status(self, slots):
        s = [0] * self.width
        for _, _, c in slots:
            for i, v in enumerate(c):
                if v > s[i]:
                    s[i] = v
        return tuple(s)

    def is_goal(self, state):
        return all(v == 2 for v in self.status(state[1]))

    # --- kernels ----------------------------------------------------------------------------------
    def _add(self, rarity, slots):
        cap = CAPS[rarity]
        n = {"prefix": 0, "suffix": 0}
        held = Counter()
        for side, kind, c in slots:
            n[side] += 1
            held[kind] += 1
        entries = []
        total = 0
        for kind, v in self.info.items():
            if n[v["side"]] >= cap[v["side"]]:
                continue
            avail = v["N"] - held[kind]
            if avail <= 0:
                continue
            for c, w in v["classes"]:
                entries.append(((v["side"], kind, c), avail * w))
                total += avail * w
        return entries, total

    def add(self, state, rarity_after, num=None):
        num = num or self.num
        r, slots = state
        entries, total = self._add(rarity_after, slots)
        if total == 0:
            return None
        out = defaultdict(num)
        for slot, w in entries:
            out[(rarity_after, tuple(sorted(slots + (slot,))))] += num(w) / num(total)
        return dict(out)

    def magic_roll(self, num=None):
        num = num or self.num
        out = defaultdict(num)
        e1, t1 = self._add(MAGIC, ())
        for s1, w1 in e1:
            p1 = num(w1) / num(t1)
            out[(MAGIC, (s1,))] += p1 / 2
            e2, t2 = self._add(MAGIC, (s1,))
            if t2 == 0:
                out[(MAGIC, (s1,))] += p1 / 2
                continue
            for s2, w2 in e2:
                out[(MAGIC, tuple(sorted((s1, s2))))] += p1 / 2 * num(w2) / num(t2)
        return dict(out)

    def kernel(self, state, name, num=None):
        """None where the real action is refused."""
        num = num or self.num
        r, slots = state
        if name == "transmute":
            return self.magic_roll(num) if r == NORMAL else None
        if name == "alter":
            return self.magic_roll(num) if r == MAGIC else None
        if name == "augment":
            return self.add(state, MAGIC, num) if r == MAGIC else None
        if name == "regal":
            return self.add(state, RARE, num) if r == MAGIC else None
        if name == "exalt":
            return self.add(state, RARE, num) if r == RARE else None
        if name == "annul":
            if r == NORMAL or not slots:
                return None
            out = defaultdict(num)
            for i in range(len(slots)):
                out[(r, slots[:i] + slots[i + 1:])] += num(1) / num(len(slots))
            return dict(out)
        if name == "scour":
            return {(NORMAL, ()): num(1)} if r != NORMAL else None
        raise KeyError(name)


NAMES = ["transmute", "alter", "augment", "regal", "annul", "exalt", "scour"]
ACTS = {"transmute": TransmutationOrb(), "alter": AlterationOrb(), "augment": AugmentationOrb(), "regal": RegalOrb(),
        "annul": AnnulmentOrb(), "exalt": ExaltedOrb(), "scour": ScouringOrb()}


def from_real(cs):
    r = {Rarity.NORMAL: NORMAL, Rarity.MAGIC: MAGIC, Rarity.RARE: RARE}[cs.flags.rarity]
    return (r, tuple((s.side.value, s.kind, tuple(int(x) for x in s.contribution)) for s in cs.slots))


def goal_of(d):
    if os.environ.get("GOAL") == "B":  # heavier-weight wanted mods: Physical damage (7000), T1 attack speed, critical multiplier (6000)
        return Goal((Wanted(fam_ids(d, "PhysicalDamage")), Wanted(fam_ids(d, "CriticalStrikeMultiplier")),
                     Wanted(fam_ids(d, "IncreasedAttackSpeed"), min_tier=1)))
    return Goal((Wanted(fam_ids(d, "IncreaseSocketedGemLevel")), Wanted(fam_ids(d, "ChaosDamageHybrid")),
                 Wanted(fam_ids(d, "IncreasedAttackSpeed"), min_tier=1)))


def make(num=float, merge=False):
    d = data()
    ab = Abstraction(d, goal_of(d), BASE, LEVEL, list(ACTS.values()))
    return d, ab, Light(d, ab, num, merge)
