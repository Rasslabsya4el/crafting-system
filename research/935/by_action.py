"""Where the kernels of one plan spend their time, per action kind (ticket #935). No `src/` change.

    python research/935/by_action.py --route r04 [--out DIR] [--tag .main]
    python research/935/by_action.py --case essences/medium ...

It plans as `research/881/profile_plan.py --mode plain` does and, around `Abstraction._build` (the item, the outcomes and the checks of one
prepared pair), counts per kind of action (its class name and whether its view erased the ordinary mods) the calls and the seconds, and of
them the seconds in `_item_of` and in `_outcomes`; `_splits_of` (the read-back of each part) is counted the same way. `_item_of` called from
elsewhere (the bound's `Pattern._ok`, the inputs) is counted under `outside`.
"""

import json
import runpy
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crafting_system.abstraction import _kernel as K  # noqa: E402

rows: dict = defaultdict(lambda: defaultdict(float))
current: list = []
clock = time.perf_counter
build, item_of, outcomes, splits_of = K.Abstraction._build, K.Abstraction._item_of, K.Abstraction._outcomes, K.Abstraction._splits_of


def _name(action, erasing) -> str:
    return f"{type(action).__name__}{'/erasing' if erasing else ''}"


def timed_build(self, view, erasing, action):
    name = _name(action, erasing)
    current.append(name)
    began = clock()
    try:
        return build(self, view, erasing, action)
    finally:
        rows[name]["build_s"] += clock() - began
        rows[name]["build_calls"] += 1
        current.pop()


def timed_item_of(self, *args, **kwargs):
    began = clock()
    try:
        return item_of(self, *args, **kwargs)
    finally:
        name = current[-1] if current else "outside"
        rows[name]["item_of_s"] += clock() - began
        rows[name]["item_of_calls"] += 1


def timed_outcomes(self, action, item):
    began = clock()
    try:
        return outcomes(self, action, item)
    finally:
        name = current[-1] if current else f"outside:{type(action).__name__}"
        rows[name]["outcomes_s"] += clock() - began


def timed_splits_of(self, prepared):
    began = clock()
    fresh = prepared.splits is None
    try:
        return splits_of(self, prepared)
    finally:
        if fresh and prepared.outcomes is not None:
            name = type(prepared.outcomes).__name__
            rows[f"splits:{name}"]["splits_s"] += clock() - began
            rows[f"splits:{name}"]["splits_calls"] += 1


K.Abstraction._build = timed_build
K.Abstraction._item_of = timed_item_of
K.Abstraction._outcomes = timed_outcomes
K.Abstraction._splits_of = timed_splits_of

out = None
for index, arg in enumerate(sys.argv):
    if arg == "--out":
        out = sys.argv[index + 1]
tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
name = (sys.argv[sys.argv.index("--case") + 1] if "--case" in sys.argv else sys.argv[sys.argv.index("--route") + 1]).replace("/", "__")
sys.argv = [str(ROOT / "research/881/profile_plan.py"), *sys.argv[1:], "--mode", "plain"]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    table = {key: {k: round(v, 2) for k, v in value.items()} for key, value in sorted(rows.items(), key=lambda kv: -sum(kv[1].get(k, 0) for k in ("build_s", "item_of_s", "splits_s")))}
    text = json.dumps(table, indent=1)
    print(text, flush=True)
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / f"{name}.by_action{tag}.json").write_text(text + "\n", encoding="utf-8")
