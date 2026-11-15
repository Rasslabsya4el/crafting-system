"""Profile one benchmark route's plan through the envelope search for a fixed time (ticket #828): where the bound's build spends it.

    uv run --no-sync python -u research/828/profile_route.py r07-minion-wand 900

Runs `make_plan` with no budget under cProfile, stops it after the given seconds, and prints the functions by cumulative and own time, the
time and calls of `Abstraction.kernel` and `kernel_key` per action, and the members per mode. Started only through the dispatcher.
"""

import collections
import cProfile
import pstats
import sys
import threading
import time
import _thread
from pathlib import Path

import crafting_system.cli  # noqa: F401  (names the page's presenter, #882)
from crafting_system.abstraction import _kernel as K
from crafting_system.abstraction import _pattern as P
from crafting_system.data import load_game_data
from crafting_system.planner import _packed
from crafting_system.planner._plan import make_plan
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
spent: collections.Counter = collections.Counter()
calls: collections.Counter = collections.Counter()


def timed(name, original):
    def wrapper(self, state, action, *rest, **kw):
        began = time.perf_counter()
        try:
            return original(self, state, action, *rest, **kw)
        finally:
            label = f"{name} {type(action).__name__} {str(getattr(action, 'label', action))[:70]}"
            spent[label] += time.perf_counter() - began
            calls[label] += 1

    return wrapper


def main() -> None:
    stem, seconds = sys.argv[1], float(sys.argv[2])
    K.Abstraction.kernel = timed("kernel", K.Abstraction.kernel)
    K.Abstraction.kernel_key = timed("key", K.Abstraction.kernel_key)
    members = P.Pattern.members

    def counted(self, key, mode):
        out = members(self, key, mode)
        calls[f"members {mode.value}"] += 1
        spent[f"members {mode.value} (count)"] += len(out)
        return out

    P.Pattern.members = counted
    began = time.perf_counter()
    _packed.PROGRESS = lambda line: print(f"[{time.perf_counter() - began:8.1f}s] {line[:300]}", flush=True)
    data = load_game_data()
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    prices = load_price_file(target.price_file)
    threading.Timer(seconds, _thread.interrupt_main).start()
    profile = cProfile.Profile()
    profile.enable()
    try:
        plan = make_plan(data, target, prices, with_risk=False)
        print("PLANNED", float(plan.mean_remaining), flush=True)
    except BaseException as error:  # noqa: BLE001  (the stop is a KeyboardInterrupt)
        print("ENDED", type(error).__name__, str(error)[:500], flush=True)
    profile.disable()
    print(f"seconds {time.perf_counter() - began:.1f}")
    for sort in ("cumulative", "tottime"):
        pstats.Stats(profile).sort_stats(sort).print_stats(45)
    for label, value in spent.most_common(40):
        print(f"{value:12.2f} {calls[label]:10d}  {label}")


if __name__ == "__main__":
    main()
