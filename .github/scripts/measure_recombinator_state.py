"""Count the compressed states of the recombinator on the R25-sized world of ADR-0062 (ticket #217; run by the `Run a command` workflow).

    python .github/scripts/measure_recombinator_state.py [--junk 500:3,1000:3,1500:3] [--donors all|isolated] [--out DIR]

The world is three target prefixes of weight 100 and nine junk prefixes in three weight classes of three (every mod its own family), on
boots, with three prefix slots: the items are the sets of up to three prefixes of distinct families, magic with one mod and rare with more. One
line of JSON, printed and written to `<out>/recombinator_state.json`:

* `items`: the number of such items, and `states_by_class` / `states_by_name` the compressed states they make with the recombinator's class
  state (this ticket) and with every mod told apart by name (the state the recombinator had before: the multiset of mods, the families' tiers
  lost);
* the closure of the recombinator over the class state: from every state of an item, with one recombinator for each state as its donor
  (`--donors all`; `isolated` keeps the donors made of target mods alone, the seed of ADR-0062), the states reached, the (state, donor) pairs,
  the transitions (outcomes of a kernel) and the seconds. It runs the real kernel of the real action on every pair at the plan's exponent.

It prints what the code does and asserts nothing; `tests/test_abstraction_recombinator.py` holds the item counts. Never run it on a PC: the closure
builds 3,900 kernels, each an exact enumeration of the draws over every placement of the names (docs/ci.md).
"""

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from item_state_support import BOOTS, LEVEL  # noqa: E402
from recombinator_world import r25_world  # noqa: E402

from crafting_system.abstraction import Abstraction  # noqa: E402
from crafting_system.actions import ActionError, Reads, Recombinator  # noqa: E402
from crafting_system.items import ExplicitMod, Item, Rarity  # noqa: E402


class NamedRecombinator(Recombinator):
    """The recombinator before ticket #217: every family told apart by name."""

    def reads(self, data):
        return Reads(junk=True, families=None, input_mods=True, implicits=True, quality=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junk", default="500:3,1000:3,1500:3")
    parser.add_argument("--donors", choices=("all", "isolated"), default="all")
    parser.add_argument("--out")
    args = parser.parse_args()
    junk = tuple((int(weight), int(count)) for weight, count in (part.split(":") for part in args.junk.split(",")))
    data, goal, targets, junk_ids = r25_world(junk)
    prefixes = (*targets, *junk_ids)

    def make(chosen: tuple[str, ...]) -> Item:
        mods = tuple(ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats)) for mod_id in chosen)
        return Item.build(data, base_id=BOOTS, item_level=LEVEL, rarity=Rarity.MAGIC if len(chosen) == 1 else Rarity.RARE, mods=mods)

    items = [make(chosen) for size in range(1, 4) for chosen in itertools.combinations(prefixes, size)]
    probe = Abstraction(data, goal, BOOTS, LEVEL, [Recombinator(items[0])])
    by_class = {probe.compress(each) for each in items}
    by_name = {Abstraction(data, goal, BOOTS, LEVEL, [NamedRecombinator(items[0])]).compress(each) for each in items}
    representative: dict = {}
    for each in items:
        representative.setdefault(probe.compress(each), each)
    donors = [each for each in representative.values() if args.donors == "all" or set(mod.mod_id for mod in each.mods) <= set(targets)]
    actions = [Recombinator(donor) for donor in donors]
    ability = Abstraction(data, goal, BOOTS, LEVEL, [actions[0]])
    began = time.perf_counter()
    seen = {ability.compress(each) for each in items}
    queue = list(seen)
    pairs = transitions = refused = 0
    while queue:
        state = queue.pop()
        for action in actions:
            try:
                kernel = ability.kernel(state, action)
            except ActionError:
                refused += 1
                continue
            pairs += 1
            transitions += len(kernel)
            for found in kernel:
                if found not in seen:
                    seen.add(found)
                    queue.append(found)
    line = {
        "junk": args.junk,
        "items": len(items),
        "states_by_class": len(by_class),
        "states_by_name": len(by_name),
        "donors": len(actions),
        "closure_states": len(seen),
        "pairs": pairs,
        "refused_pairs": refused,
        "transitions": transitions,
        "kernels_seconds": round(time.perf_counter() - began, 1),
    }
    print(json.dumps(line))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "recombinator_state.json").write_text(json.dumps(line, indent=2))


if __name__ == "__main__":
    main()
