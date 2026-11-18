"""#1315: what the fewest-junk lead would cost to get.    python ledreach.py DUMP.pkl [DROPPED]   (default tags,counts)

ledmin.py counts that the least complete value inside a coarse key sits (nearly always) at its member with the fewest junk mods. Such a
lead needs the exact value of those members. This counts how many keys a blind build of those members alone works out: the keys reachable
from them under every offer (their closure in the complete dump), and the same from the members of the fewest junk with no junk at all.
A count on a complete dump; no argument, no build."""
import pickle, sys
from collections import defaultdict
from crafting_system.abstraction._pattern import ChoiceNode

d = pickle.load(open(sys.argv[1], "rb"))
drop = tuple((sys.argv[2] if len(sys.argv) > 2 else "tags,counts").split(","))
keys, goal, actions, kernels = d["keys"], d["goal"], d["actions"], d["kernels"]
n = len(keys)
groups = defaultdict(list)
for i, k in enumerate(keys):
    if not goal[i] and not isinstance(k, ChoiceNode):
        groups[k._replace(**{f: None for f in drop})].append(i)
members = []
for g in groups.values():
    few = min(sum(keys[i].counts) for i in g)
    members += [i for i in g if sum(keys[i].counts) == few]


def closure(seed):
    seen, stack = set(seed), list(seed)
    while stack:
        i = stack.pop()
        for _, kid in actions[i]:
            for s in kernels[kid][0]:
                if s >= 0 and s not in seen:
                    seen.add(s)
                    stack.append(s)
    return sum(1 for i in seen if not goal[i])


total = sum(1 for i in range(n) if not goal[i])
c = closure(members)
z = [i for i in members if sum(keys[i].counts) == 0]
cz = closure(z)
print(f"RESULT {sys.argv[1].split('/')[-1]} dropped {','.join(drop)}: coarse keys {len(groups)}; fewest-junk members {len(members)}; keys reachable from them {c} of {total} ({100 * c / total:.2f}%); "
      f"members with no junk {len(z)}, keys reachable from those {cz} ({100 * cz / total:.2f}%); start key's junk {sum(keys[0].counts)}", flush=True)
