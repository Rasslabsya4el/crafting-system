"""Profile one plan (ticket #881): where kernel generation and the pattern bound spend their time. No `src/` change.

    python research/881/profile_plan.py (--route r04|r13|j01 | --case essences/medium) [--mode plain|timers|cprofile] [--out DIR] [--top 60]
    CRAFTING_SOURCE=DIR python research/881/profile_plan.py ...   # plan with the copy of the package in DIR (`build_cython.py source`)

It plans with the planner's own entry (`make_plan(..., solver="envelope", with_risk=False)` for a route; `solver="auto"`, the family
benchmark's call, for a generated case) and measures it in one of three ways:

- `plain`: the wall seconds only, and the search's own counters. The figure the other two are compared with.
- `timers` (default): a stopwatch around each function of `TIMED` (the stages of a kernel, of the bound's build and of the search), giving the
  calls, the seconds inside the function with what it calls (`total`) and without the other timed functions it calls (`own`). It costs about
  a microsecond a call, so the stages add up to nearly the plain wall time. It also counts, per kernel handed to the search, its outcomes and the
  bits of its largest integer weight and of the sum of its weights (what a fixed-width number would have to hold).
- `cprofile`: the standard profiler, every function; it slows Python-heavy code by a factor the run shows against `plain`. Read from it the
  share of `fractions.py`, `math.gcd` and `math.lcm` (the exact arithmetic that is visible as calls; big-integer `*`, `+`, `//` inside a
  function body are not calls and stay inside that function's own time).

Never run R04 on a PC: `python .github/scripts/heavy_dispatch.py run --ref <branch> --command '...' --no-wait`.
"""

import argparse
import cProfile
import io
import json
import os
import pstats
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
if os.environ.get("CRAFTING_SOURCE"):  # a copy of the package to plan with instead (`build_cython.py source`)
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])

# (module, class or None, name): the stages of a plan. A function is looked up where it is defined and replaced wherever a module of the
# package holds it by name.
TIMED = [
    ("crafting_system.planner._pattern_bound", None, "pattern_lower_bound"),
    ("crafting_system.abstraction._pattern", "PatternBuilder", "_offers_of_key"),
    ("crafting_system.abstraction._pattern", "Pattern", "members"),
    ("crafting_system.abstraction._pattern", "Pattern", "key"),
    ("crafting_system.abstraction._kernel", "Abstraction", "kernel"),
    ("crafting_system.abstraction._kernel", "Abstraction", "kernel_key"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_prepare"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_item_of"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_outcomes"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_splits_of"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_signatures_of"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_distribution"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_expanded_distribution"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_mixture_kernel"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_add_drawn"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_add_fixed"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_add_fractured"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_add_rerolled"),
    ("crafting_system.abstraction._kernel", "Abstraction", "compress"),
    ("crafting_system.abstraction._kernel", "Abstraction", "is_goal"),
    ("crafting_system.abstraction._kernel", None, "integer_weights"),
    ("crafting_system.abstraction._inputs", None, "input_kernel"),
    ("crafting_system.actions.draw", None, "exact_distribution"),
    ("crafting_system.solver._packed_solve", None, "solve_graph"),
    ("crafting_system.planner._envelope", "Search", "intern"),
    ("crafting_system.planner._envelope", "Search", "expand"),
    ("crafting_system.planner._envelope", "Search", "realize"),
    ("crafting_system.planner._envelope", "Search", "_kernel"),
    ("crafting_system.planner._envelope", "Search", "_fresh_equal"),
    ("crafting_system.planner._envelope", "Search", "_q"),
    ("crafting_system.planner._envelope", "Search", "_self_mass"),
    ("crafting_system.planner._envelope", "Search", "_graph"),
    ("crafting_system.planner._envelope", "Search", "run"),
    ("crafting_system.planner._envelope_plan", "CraftingProblem", "candidates"),
    ("crafting_system.planner._envelope_plan", "CraftingProblem", "lower"),
    ("crafting_system.planner._envelope_plan", "CraftingProblem", "kernel_key"),
    ("crafting_system.planner._envelope_plan", "CraftingProblem", "kernel"),
    ("crafting_system.planner._envelope_plan", None, "solve_walked"),
]
EXACT = re.compile(r"fractions\.py|built-in method math\.(gcd|lcm)")
BITS = (53, 63, 127, 255, 1023)  # a float's mantissa, int64, int128, and beyond


class Timers:
    """Calls, total seconds and own seconds (without the timed functions called inside) per timed function."""

    def __init__(self) -> None:
        self.calls: Counter = Counter()
        self.total: Counter = Counter()
        self.own: Counter = Counter()
        self.stack: list[list] = []  # [name, seconds of timed children]
        self.active: Counter = Counter()  # a recursive call counts its seconds in `total` once

    def wrap(self, name: str, function):
        clock, stack, calls, total, own, active = time.perf_counter, self.stack, self.calls, self.total, self.own, self.active

        def timed(*args, **kwargs):
            frame = [name, 0.0]
            stack.append(frame)
            active[name] += 1
            began = clock()
            try:
                return function(*args, **kwargs)
            finally:
                spent = clock() - began
                stack.pop()
                active[name] -= 1
                calls[name] += 1
                if not active[name]:
                    total[name] += spent
                own[name] += spent - frame[1]
                if stack:
                    stack[-1][1] += spent

        timed.__wrapped__ = function
        return timed

    def install(self) -> list[str]:
        import importlib

        missing = []
        for module_name, class_name, name in TIMED:
            module = importlib.import_module(module_name)
            holder = getattr(module, class_name) if class_name else module
            label = f"{class_name}.{name}" if class_name else name
            original = holder.__dict__.get(name) if class_name else getattr(module, name, None)
            if original is None:
                missing.append(f"{module_name}:{label}")
                continue
            if isinstance(original, staticmethod):
                missing.append(f"{module_name}:{label} (static, not timed)")
                continue
            wrapped = self.wrap(label, original)
            if class_name:
                setattr(holder, name, wrapped)
                continue
            for other in list(sys.modules.values()):  # every module of the package that imported the function by name
                if getattr(other, "__name__", "").startswith("crafting_system") and getattr(other, name, None) is original:
                    setattr(other, name, wrapped)
        return missing

    def rows(self) -> list[dict]:
        return [
            {"function": name, "calls": self.calls[name], "total_s": round(self.total[name], 2), "own_s": round(self.own[name], 2)}
            for name in sorted(self.calls, key=lambda n: -self.own[n])
        ]


class KernelShapes:
    """Per kernel handed to the search: its outcomes, and the bits of its largest weight and of the sum of its weights."""

    def __init__(self) -> None:
        self.kernels = 0
        self.outcomes = 0
        self.outcome_sizes: Counter = Counter()
        self.weight_bits: Counter = Counter()
        self.sum_bits: Counter = Counter()
        self.max_weight_bits = 0
        self.max_sum_bits = 0
        self.max_outcomes = 0

    @staticmethod
    def bucket(bits: int) -> str:
        for edge in BITS:
            if bits <= edge:
                return f"<={edge}"
        return f">{BITS[-1]}"

    def install(self) -> None:
        from crafting_system.planner import _envelope_plan

        original = _envelope_plan.integer_weights

        def counted(kernel):
            weights = original(kernel)
            if weights:
                values = weights.values()
                most, whole = max(values).bit_length(), sum(values).bit_length()
                self.kernels += 1
                self.outcomes += len(weights)
                size = len(weights)
                self.outcome_sizes["1" if size == 1 else "2-9" if size < 10 else "10-99" if size < 100 else "100-999" if size < 1000 else ">=1000"] += 1
                self.weight_bits[self.bucket(most)] += 1
                self.sum_bits[self.bucket(whole)] += 1
                self.max_weight_bits = max(self.max_weight_bits, most)
                self.max_sum_bits = max(self.max_sum_bits, whole)
                self.max_outcomes = max(self.max_outcomes, size)
            return weights

        _envelope_plan.integer_weights = counted

    def row(self) -> dict:
        return {
            "kernels_built": self.kernels, "outcomes": self.outcomes, "mean_outcomes": round(self.outcomes / self.kernels, 1) if self.kernels else None,
            "max_outcomes": self.max_outcomes, "outcome_sizes": dict(self.outcome_sizes), "largest_weight_bits": dict(self.weight_bits),
            "sum_of_weights_bits": dict(self.sum_bits), "max_weight_bits": self.max_weight_bits, "max_sum_bits": self.max_sum_bits,
        }  # fmt: skip


def inputs(args):
    """`(data, target, prices, start_price, solver)` of the route or the generated case."""
    import packed_routes as P
    from crafting_system.data import load_game_data
    from crafting_system.targets import load_target

    if args.case:
        import family_bench as B
        import family_bench_support as F

        data = load_game_data()
        case = B.case_by_id(F.DEFAULT_SEED, args.case, data)
        return data, F.target_of(case, data), F.prices_for(case), case.start_price, "auto"
    extra = {"j01": "j01-cobalt-life-attack-speed"}
    if args.route in extra:
        data = load_game_data()
        return data, load_target(ROOT / "examples" / "targets" / f"{extra[args.route]}.yaml", data), P.load_price_file(P.PRICES), None, "envelope"
    return (*P.inputs(args.route), "envelope")


def short(text: str) -> str:
    """The report with the folders of the project, the standard library and the installed packages cut from each path."""
    text = text.replace(str(ROOT / "src" / "crafting_system") + os.sep, "")
    text = re.sub(r"\S*site-packages[\\/]", "", text)
    return re.sub(r"[^\s(]*[\\/][Ll]ib[\\/](?:python3\.\d+[\\/])?", "", text)


def exact_share(profile: cProfile.Profile) -> dict:
    """The own seconds of the exact arithmetic that shows as calls (`Fraction` methods, `math.gcd`, `math.lcm`), of hashing and comparing, and of everything."""
    stats = pstats.Stats(profile).stats  # {(file, line, name): (calls, primitive calls, own, cumulative, callers)}
    whole = sum(row[2] for row in stats.values())
    exact = sum(row[2] for (file, _, name), row in stats.items() if EXACT.search(f"{file} {name}"))
    hashing = sum(row[2] for (_, _, name), row in stats.items() if name in ("__hash__", "<built-in method builtins.hash>", "__eq__"))
    return {"own_seconds_all": round(whole, 2), "own_seconds_fraction_gcd_lcm": round(exact, 2), "own_seconds_hash_eq": round(hashing, 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route")
    parser.add_argument("--case")
    parser.add_argument("--mode", choices=("plain", "timers", "cprofile"), default="timers")
    parser.add_argument("--out")
    parser.add_argument("--top", type=int, default=60)
    parser.add_argument("--tag", default="", help="added to the name of the files written")
    args = parser.parse_args()
    from crafting_system.cli import make_plan
    from crafting_system.planner import _envelope

    data, target, prices, start_price, solver = inputs(args)
    name = f"{(args.case or args.route).replace('/', '__')}.{args.mode}{args.tag}"
    found: dict = {}
    out = {"name": name, "mode": args.mode, "platform": sys.platform, "python": sys.version.split()[0], "source": os.environ.get("CRAFTING_SOURCE")}
    timers, shapes, profile = Timers(), KernelShapes(), cProfile.Profile()
    if args.mode == "timers":
        out["not_timed"] = timers.install()
        shapes.install()
    run = _envelope.Search.run

    def kept_run(self):  # the search's own counters, read when it ends
        try:
            return run(self)
        finally:
            found["stats"] = {k: v for k, v in vars(self.stats).items() if k != "lower_history"}
            found["states_known"] = len(self.states)
            found["shared_kernel_hits"] = self.hits

    _envelope.Search.run = kept_run
    began = time.perf_counter()
    if args.mode == "cprofile":
        profile.enable()
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver=solver, with_risk=False)
    profile.disable()
    out.update(seconds=round(time.perf_counter() - began, 2), mean_remaining=plan.mean_remaining, search=found)
    loaded = [m for n, m in sys.modules.items() if n.startswith("crafting_system") and getattr(m, "__file__", None)]
    out["modules_loaded"] = len(loaded)
    out["modules_compiled"] = sum(not m.__file__.endswith(".py") for m in loaded)
    report = ""
    if args.mode == "timers":
        out["timers"] = timers.rows()
        out["kernel_shapes"] = shapes.row()
    if args.mode == "cprofile":
        out["exact_arithmetic"] = exact_share(profile)
        stream = io.StringIO()
        stats = pstats.Stats(profile, stream=stream)
        stats.sort_stats("tottime").print_stats(args.top)
        stats.sort_stats("cumulative").print_stats(args.top)
        report = short(stream.getvalue())
    text = json.dumps(out, indent=1, default=str)
    print(text, flush=True)
    print(report, flush=True)
    if args.out:
        folder = Path(args.out)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.json").write_text(text + "\n", encoding="utf-8")
        if report:
            (folder / f"{name}.profile.txt").write_text(report, encoding="utf-8")
            profile.dump_stats(folder / f"{name}.prof")


if __name__ == "__main__":
    main()
