"""The profiler's own seconds grouped by kind of work (ticket #881): the table "What kind of work it is" of the note.

    python research/881/profile_groups.py research/881/results/prof-linux/run-ubuntu-latest-3/r04.cprofile.prof ...

Reads the dumps `profile_plan.py --mode cprofile` writes. A group is the own time (without what a function calls) of the functions of a file or
of a name; the groups overlap nowhere except that `isinstance` checks made from any file are their own group.
"""

import pstats
import sys

COMPARING = ("__eq__", "_richcmp", "__le__", "__lt__", "__ge__", "__gt__", "__hash__", "numerator", "denominator", "__bool__")


def path(key) -> str:
    return key[0].replace(chr(92), "/")


def main() -> None:
    for name in sys.argv[1:]:
        stats = pstats.Stats(name).stats  # {(file, line, function): (calls, primitive calls, own, cumulative, callers)}
        whole = sum(row[2] for row in stats.values())

        def total(test) -> float:
            return sum(row[2] for key, row in stats.items() if test(key))

        def fraction(key) -> bool:
            return "fractions.py" in key[0]

        groups = {
            "fractions: comparing and hashing": total(lambda k: fraction(k) and k[2] in COMPARING),
            "fractions: arithmetic and making": total(lambda k: fraction(k) and k[2] not in COMPARING),
            "math.gcd, math.lcm": total(lambda k: "math.gcd" in k[2] or "math.lcm" in k[2]),
            "hash and eq outside fractions": total(lambda k: not fraction(k) and (k[2] in ("__hash__", "__eq__") or "builtins.hash" in k[2])),
            "isinstance and abc checks": total(lambda k: "isinstance" in k[2] or "__instancecheck__" in k[2] or "_abc_instancecheck" in k[2]),
            "sorted, list.sort (own)": total(lambda k: "builtins.sorted" in k[2] or "'sort' of 'list'" in k[2]),
            "items/model.py (item building and checks)": total(lambda k: path(k).endswith("items/model.py")),
            "actions/pool.py": total(lambda k: path(k).endswith("actions/pool.py")),
            "abstraction/_kernel.py": total(lambda k: path(k).endswith("abstraction/_kernel.py")),
            "dataclasses.py, enum.py": total(lambda k: k[0].endswith("dataclasses.py") or k[0].endswith("enum.py")),
            "numpy and solver/": total(lambda k: "numpy" in k[0] or "numpy" in k[2] or "/solver/" in path(k)),
        }
        print(f"{name}: own seconds {whole:.1f}")
        for label, seconds in groups.items():
            print(f"   {label:<45} {seconds:7.1f}  {100 * seconds / whole:4.1f}%")
        for key, row in stats.items():
            if fraction(key) and key[2] in ("__eq__", "__le__", "__lt__", "__hash__"):
                print(f"   Fraction.{key[2]}: {row[0]:,} calls, {row[2]:.1f} s")


if __name__ == "__main__":
    main()
