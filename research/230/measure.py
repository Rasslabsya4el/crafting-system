"""Sizes, time and peak memory of the finish encodings.  One JSON line per mode: python measure.py MODE [ARGS]."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fractions import Fraction as F

from fin import Cfg, Target
from mem import peak_mb
from red import Red
import dedicated

ALL = ("JEW", "JEWO", "FUSE", "CONN", "CHROM", "TRI", "BC", "BL", "BK")
NOOMEN = ("JEW", "FUSE", "CHROM", "BC", "BL", "BK")
THIRDS = (F(1, 3),) * 3


def emit(**kw):
    kw["peak_mb"] = round(peak_mb())
    print(json.dumps(kw), flush=True)


def six(name, links, count):
    """Six-socket class, ilvl 84, quality 20, from one white socket; dedicated routine."""
    acts, prices = (ALL, {"omen": 50}) if name == "omen50" else (NOOMEN, {})
    cfg = Cfg(classmax=6, colour_w=THIRDS, actions=acts, prices=prices)
    tgt = Target(count=count, links=links, req=(1, 1, 1))
    red = Red(cfg, tgt)
    key = red.key_of_raw((1, (0,), (1,)))
    t = time.time()
    B = dedicated.build(red, key)
    tb = time.time() - t
    t = time.time()
    V, it, _, nres = dedicated.solve_anderson(B)
    ts = time.time() - t
    out = dict(mode="six", prices=name, links=links, count=count, states=B.N - 1, small_edges=B.n_small_edges,
               dense_edges=B.dense_edges, shell_entries=B.n_shell_entries, wide_actions=B.n_wide_actions,
               build_s=round(tb, 1), solve_s=round(ts, 2), sweeps=it, residual=nres, value=V[1])
    if len(sys.argv) > 5 and sys.argv[5] == "plain":
        t = time.time()
        V2, it2, _ = dedicated.solve(B, max_sweeps=60000)
        out.update(plain_s=round(time.time() - t, 1), plain_sweeps=it2, plain_value=V2[1])
    emit(**out)


def fixture_model(sockets, shared):
    cfg = Cfg(classmax=sockets, colour_w=THIRDS, actions=("FUSE", "CHROM"))
    red = Red(cfg, Target(links=3, req=(1, 1, 1)))
    return cfg, red, red.key_of_raw((sockets, (0,) * sockets, (1,) * sockets))


def solve_mode(shared, sockets):
    from crafting_system.solver import Action, solve
    cfg, red, key = fixture_model(sockets, shared)
    table_cache = {}

    class M:
        def is_goal(self, k):
            return red.is_goal(k)

        def actions(self, k):
            if not shared:
                return [Action(l, c, tuple(o)) for l, c, o in red.actions_int(k)]
            out = [Action(l, c, tuple(o)) for l, c, o in red.small(k)]
            for w in red.wide(k):
                label, cost, mode, excl = w
                tab, real, D = red.chrom_table(k[0], mode)
                sh = (k[0], k[2], mode)
                if sh not in table_cache:  # one tuple shared by every state of the shell
                    table_cache[sh] = tuple(((k[0], c, k[2]), wt) for c, wt in tab)
                e = real.get(excl, 0) if excl is not None else 0
                # the excluded outcome is the state itself: a self-loop with the cost scaled by (1 - e/D) is exact
                out.append(Action(label, cost * (1 - e / D), table_cache[sh]))
            return out

    t = time.time()
    sol = solve(M(), [key])
    emit(mode="solver.solve", shared=shared, sockets=sockets, value=sol.values[key], secs=round(time.time() - t, 1),
         states=len(sol.values))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "six":
        six(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif mode == "solve":
        solve_mode(sys.argv[2] == "shared", int(sys.argv[3]))
