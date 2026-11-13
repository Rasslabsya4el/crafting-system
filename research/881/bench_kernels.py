"""Today's Python against compiled candidates on the hot loop of kernel generation, on the inputs of one real plan (ticket #881). No `src/` change.

    python research/881/bench_kernels.py (--route r04|r13|j01 | --case essences/medium) [--sample-every 8] [--max-samples 60000] [--repeat 5] [--out DIR]

**What is measured.** The profile (`profile_plan.py`) puts most of a plan in making the key of a kernel: the state becomes an item, the action
gives its outcomes on it, and each pool of candidate mods is grouped by family (`actions.pool.group_pool`) and read into a signature
(`Abstraction._pool_signature`: per family its side and the sorted label, weight and guaranteed flag of its mods). That last pair is the loop
prototyped here. The script plans with the planner's own entry and, while it plans:

1. times the stages of a kernel per kind of action (the class of the action): `kernel_key`, `kernel`, and inside them `_prepare`, `_item_of`,
   `_outcomes`, `_signatures_of`, `_splits_of` (seconds with what each calls);
2. times every `group_pool` and `_pool_signature` call, and keeps every K-th pool with the seconds today's Python took for it (the `group_pool`
   call that made the pool, and its `_pool_signature`) and the signature it got;
3. times every `exact_distribution` call made in exact fractions, runs it again in floats (`actions.draw.floating`, the planner's own float
   mode) and compares each chance, and counts the bits of the exact numerators and denominators.

Then it turns the kept pools into flat arrays and gives the same pools to each candidate: plain Python on the flat arrays (`flat_python`),
Numba (`flat_numba`) and Cython (`flat_cython`, when `build_cython.py flat` has built it). The flat form of one pool is the list of its
candidates in data order, each an id whose static columns are its family and side, its label id, its weight id and its guaranteed flag (labels
and weights are interned by equality, so no number is rounded or even read); the head of the pool (tag, blocked tags, kept mods, free slots,
totals) is one more id. A candidate returns a signature id per pool, and the script checks that the ids split the pools exactly as today's
signatures do (two pools share an id exactly when today's signatures are equal). A pool with a family on both sides (jewels) is not kept: its
signature has a part this prototype leaves out, and the count says how many.

What the flat form moves out of the loop, and today's Python pays inside it: the label of each mod (a dict lookup today), the weight times the
fossil factor, the `PoolMod` and `PoolFamily` objects. What neither side pays in the span: finding which candidates the item blocks
(`pool_candidates`), building the item, and the rest of `outcomes`.

Never run R04 on a PC: `python .github/scripts/heavy_dispatch.py run --ref <branch> --command '...' --no-wait`.
"""

import argparse
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if os.environ.get("CRAFTING_SOURCE"):
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])

import numpy as np  # noqa: E402

import profile_plan  # noqa: E402  (the inputs of a route or a case)

GROUP_SHIFT, LABEL_SHIFT = 42, 21
BITS = (53, 63, 127, 255, 1023)


def bucket(bits: int) -> str:
    for edge in BITS:
        if bits <= edge:
            return f"<={edge}"
    return f">{BITS[-1]}"


class Capture:
    """The hooks of one plan: stage seconds per kind of action, the kept pools, the exact draws."""

    def __init__(self, every: int, most: int) -> None:
        self.every, self.most = every, most
        self.kind = "(outside a kernel)"
        self.stage_seconds: Counter = Counter()  # (kind, stage) -> seconds, with what the stage calls
        self.stage_calls: Counter = Counter()
        self.group_calls = self.sig_calls = 0
        self.group_seconds = self.sig_seconds = 0.0
        self.recent: dict[int, tuple] = {}  # id(pool) -> (pool, seconds of the `group_pool` that made it)
        self.two_sided = 0
        self.unlinked = 0
        # the flat tables
        self.families: dict[str, int] = {}
        self.labels: dict = {}
        self.weights: dict = {}
        self.entry_ids: dict[tuple, int] = {}
        self.entry_keys: list[int] = []
        self.heads: dict[tuple, int] = {}
        self.order: dict[str, int] | None = None
        self.today_ids: dict = {}
        self.sample_entries: list[list[int]] = []
        self.sample_head: list[int] = []
        self.sample_today: list[int] = []
        self.sample_seconds = 0.0  # today's Python on the kept pools: their `group_pool` and their `_pool_signature`
        self.sample_signature_seconds = 0.0
        # the exact draws
        self.draws = {"exact_calls": 0, "exact_seconds": 0.0, "float_seconds_same_calls": 0.0, "float_calls_by_planner": 0, "outcomes": 0, "worst_relative_error": 0.0,
                      "worst_total_error": 0.0, "keys_differ": 0, "denominator_bits": Counter(), "numerator_bits": Counter(), "max_denominator_bits": 0}  # fmt: skip

    # ---- stage seconds -------------------------------------------------------------------------------------------

    def staged(self, stage: str, function, sets_kind: bool = False):
        clock, seconds, calls = time.perf_counter, self.stage_seconds, self.stage_calls

        def timed(ab, *args, **kwargs):
            before = self.kind
            if sets_kind:
                self.kind = type(args[1]).__name__  # (state, action)
            kind = self.kind
            began = clock()
            try:
                return function(ab, *args, **kwargs)
            finally:
                seconds[(kind, stage)] += clock() - began
                calls[(kind, stage)] += 1
                self.kind = before

        return timed

    # ---- pools ---------------------------------------------------------------------------------------------------

    def grouped(self, function):
        clock = time.perf_counter

        def timed(candidates, factor=None):
            began = clock()
            pool = function(candidates, factor)
            spent = clock() - began
            self.group_calls += 1
            self.group_seconds += spent
            if len(self.recent) >= 16:
                self.recent.pop(next(iter(self.recent)))
            self.recent[id(pool)] = (pool, spent)
            return pool

        return timed

    def signed(self, function):
        clock = time.perf_counter

        def timed(ab, part):
            began = clock()
            signature = function(ab, part)
            spent = clock() - began
            self.sig_calls += 1
            self.sig_seconds += spent
            if self.sig_calls % self.every == 0 and len(self.sample_head) < self.most:
                self.keep(ab, part, signature, spent)
            return signature

        return timed

    def keep(self, ab, part, signature, spent: float) -> None:
        from crafting_system.actions import allowed_by_tags, partners
        from crafting_system.items import Side

        if partners(part.pool):
            self.two_sided += 1
            return
        made = self.recent.get(id(part.pool))
        if made is not None and made[0] is part.pool:
            self.sample_seconds += made[1]
        else:
            self.unlinked += 1
        self.sample_seconds += spent
        self.sample_signature_seconds += spent
        if self.order is None:
            self.order = {mod_id: index for index, mod_id in enumerate(ab.data.mods)}
        influences, lucky, tag, blocked = part.retained.influences, part.rolls_lucky, part.tag, part.guaranteed_blocked
        rows = []
        for family in part.pool:
            group = self.families.setdefault(family.family, len(self.families)) * 2 + (family.side is Side.PREFIX)
            for entry in family.mods:
                mod = entry.mod
                label = self.labels.setdefault(ab._label(mod, influences, lucky), len(self.labels))
                weight = self.weights.setdefault(entry.weight, len(self.weights))
                flag = int(tag is not None and tag in mod.implicit_tags and allowed_by_tags(mod, blocked))
                key = (group << GROUP_SHIFT) | (label << LABEL_SHIFT) | (weight << 1) | flag
                ident = self.entry_ids.get(key)
                if ident is None:
                    ident = self.entry_ids[key] = len(self.entry_keys)
                    self.entry_keys.append(key)
                rows.append((self.order.get(mod.id, len(self.order)), ident))
        rows.sort()
        free = part.free
        head = (tag, blocked, len(part.retained.mods), free[Side.PREFIX], free[Side.SUFFIX], tuple(sorted(part.totals.items())))
        self.sample_entries.append([ident for _, ident in rows])
        self.sample_head.append(self.heads.setdefault(head, len(self.heads)))
        self.sample_today.append(self.today_ids.setdefault(signature, len(self.today_ids)))

    # ---- exact draws ---------------------------------------------------------------------------------------------

    def drawn(self, function):
        from crafting_system.actions import draw

        clock = time.perf_counter
        record = self.draws

        def timed(*args, **kwargs):
            if draw.NUMBER is float:  # the bound's build: the planner's own float mode
                record["float_calls_by_planner"] += 1
                return function(*args, **kwargs)
            began = clock()
            exact = function(*args, **kwargs)
            record["exact_seconds"] += clock() - began
            record["exact_calls"] += 1
            began = clock()
            with draw.floating():
                floats = function(*args, **kwargs)
            record["float_seconds_same_calls"] += clock() - began
            if exact.keys() != floats.keys():
                record["keys_differ"] += 1
                return exact
            worst = 0.0
            most = 0
            for outcome, chance in exact.items():
                error = abs(Fraction(floats[outcome]) - chance) / chance
                if error > worst:
                    worst = float(error)
                most = max(most, chance.denominator.bit_length())
                record["numerator_bits"][bucket(chance.numerator.bit_length())] += 1
            record["outcomes"] += len(exact)
            record["denominator_bits"][bucket(most)] += 1
            record["max_denominator_bits"] = max(record["max_denominator_bits"], most)
            record["worst_relative_error"] = max(record["worst_relative_error"], worst)
            record["worst_total_error"] = max(record["worst_total_error"], abs(sum(floats.values()) - 1.0))
            return exact

        return timed

    # ---- installing ----------------------------------------------------------------------------------------------

    def install(self) -> None:
        from crafting_system.abstraction import _kernel
        from crafting_system.actions import draw, pool

        ab = _kernel.Abstraction
        ab.kernel_key = self.staged("kernel_key", ab.kernel_key, sets_kind=True)
        ab.kernel = self.staged("kernel", ab.kernel, sets_kind=True)
        for name in ("_prepare", "_item_of", "_outcomes", "_signatures_of", "_splits_of"):
            setattr(ab, name, self.staged(name, getattr(ab, name)))
        ab._pool_signature = self.signed(ab._pool_signature)
        for original, wrapped in ((pool.group_pool, self.grouped(pool.group_pool)), (draw.exact_distribution, self.drawn(draw.exact_distribution))):
            for module in list(sys.modules.values()):
                if getattr(module, "__name__", "").startswith("crafting_system"):
                    for name, value in list(vars(module).items()):
                        if value is original:
                            setattr(module, name, wrapped)

    def arrays(self):
        starts = np.zeros(len(self.sample_entries) + 1, dtype=np.int64)
        np.cumsum([len(row) for row in self.sample_entries], out=starts[1:])
        entries = np.fromiter((ident for row in self.sample_entries for ident in row), dtype=np.int32, count=int(starts[-1]))
        return starts, entries, np.array(self.sample_head, dtype=np.int64), np.array(self.entry_keys, dtype=np.uint64)


def same_split(today: list[int], got) -> bool:
    """Whether two labellings split the pools the same way: equal today exactly when equal in the candidate."""
    pairs = set(zip(today, (int(value) for value in got)))
    return len(pairs) == len({a for a, _ in pairs}) == len({b for _, b in pairs})


def best_of(repeat: int, function, *args):
    best, result = None, None
    for _ in range(repeat):
        began = time.perf_counter()
        result = function(*args)
        spent = time.perf_counter() - began
        best = spent if best is None else min(best, spent)
    return best, result


def candidates(capture: Capture, repeat: int) -> dict:
    starts, entries, head, keys = capture.arrays()
    pools = len(head)
    out: dict = {"pools": pools, "candidates_in_them": int(len(entries)), "mean_candidates": round(len(entries) / pools, 1) if pools else None,
                 "distinct_signatures_today": len(set(capture.sample_today)), "flat_tables": {"entries": len(keys), "families": len(capture.families),
                 "labels": len(capture.labels), "weights": len(capture.weights), "heads": len(capture.heads)}}  # fmt: skip
    if not pools:
        return out
    if len(capture.labels) >= 1 << 21 or len(capture.weights) >= 1 << 20 or len(capture.families) >= 1 << 20:
        raise SystemExit("an id does not fit its bits in the sort key")
    today = capture.sample_today
    rows = {"python_today": {"seconds": round(capture.sample_seconds, 4), "pools_per_second": round(pools / capture.sample_seconds, 1),
                             "of_which_signature_seconds": round(capture.sample_signature_seconds, 4)}}  # fmt: skip

    def row(name: str, seconds: float, got, **extra) -> None:
        rows[name] = {"seconds": round(seconds, 5), "pools_per_second": round(pools / seconds, 1), "speed_up": round(capture.sample_seconds / seconds, 1),
                      "same_split_as_today": same_split(today, got), "distinct_signatures": len({int(v) for v in got}), **extra}  # fmt: skip

    import flat_python

    lists = (starts.tolist(), entries.tolist(), head.tolist(), [int(key) for key in keys])
    seconds, got = best_of(repeat, flat_python.signatures, *lists)
    row("flat_python", seconds, got)
    try:
        import flat_numba

        began = time.perf_counter()
        flat_numba.signatures(starts[:2], entries[: int(starts[1])], head[:1], keys)  # compiles (or loads its cache)
        compiled = time.perf_counter() - began
        seconds, got = best_of(repeat, flat_numba.signatures, starts, entries, head, keys)
        row("numba", seconds, got, first_call_seconds=round(compiled, 2))
    except Exception as error:  # the candidate is not installed, or did not compile: the row says so
        rows["numba"] = {"error": repr(error)[:400]}
    try:
        import flat_cython

        seconds, got = best_of(repeat, flat_cython.signatures, starts, entries, head, keys)
        row("cython", seconds, got)
    except Exception as error:
        rows["cython"] = {"error": repr(error)[:400]}
    out["rows"] = rows
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route")
    parser.add_argument("--case")
    parser.add_argument("--sample-every", type=int, default=8)
    parser.add_argument("--max-samples", type=int, default=60000)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out")
    args = parser.parse_args()
    from crafting_system.cli import make_plan
    from crafting_system.planner import _envelope

    data, target, prices, start_price, solver = profile_plan.inputs(args)
    name = (args.case or args.route).replace("/", "__")
    capture = Capture(args.sample_every, args.max_samples)
    capture.install()
    found: dict = {}
    run = _envelope.Search.run

    def kept_run(self):
        try:
            return run(self)
        finally:
            found["stats"] = {k: v for k, v in vars(self.stats).items() if k not in ("lower_history", "solve_info")}

    _envelope.Search.run = kept_run
    began = time.perf_counter()
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver=solver, with_risk=False)
    seconds = time.perf_counter() - began
    kinds = defaultdict(dict)
    for (kind, stage), spent in capture.stage_seconds.items():
        kinds[kind][stage] = {"calls": capture.stage_calls[(kind, stage)], "seconds": round(spent, 2)}
    draws = dict(capture.draws)
    draws["denominator_bits"], draws["numerator_bits"] = dict(draws["denominator_bits"]), dict(draws["numerator_bits"])
    for key in ("exact_seconds", "float_seconds_same_calls"):
        draws[key] = round(draws[key], 3)
    out = {
        "name": name, "platform": sys.platform, "machine": platform.processor() or platform.machine(), "cpus": os.cpu_count(), "python": sys.version.split()[0],
        "numpy": np.__version__, "plan_seconds_with_hooks": round(seconds, 1), "mean_remaining": plan.mean_remaining, "search": found,
        "stages_by_kind": {kind: kinds[kind] for kind in sorted(kinds, key=lambda k: -sum(s["seconds"] for n, s in kinds[k].items() if n in ("kernel_key", "kernel")))},
        "pools": {"group_pool_calls": capture.group_calls, "group_pool_seconds": round(capture.group_seconds, 2), "pool_signature_calls": capture.sig_calls,
                  "pool_signature_seconds": round(capture.sig_seconds, 2), "kept_every": args.sample_every, "two_sided_not_kept": capture.two_sided,
                  "kept_without_their_group_pool": capture.unlinked},
        "exact_draws": draws,
        "hot_loop": candidates(capture, args.repeat),
    }  # fmt: skip
    text = json.dumps(out, indent=1, default=str)
    print(text, flush=True)
    if args.out:
        folder = Path(args.out)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.bench.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
