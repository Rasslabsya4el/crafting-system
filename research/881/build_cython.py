"""Build the Cython candidates of ticket #881 (prototypes; no `src/` change).

    python research/881/build_cython.py flat                      # research/881/flat_cython.pyx, in place
    python research/881/build_cython.py source --out DIR [--only abstraction/_kernel.py,...]

`flat` builds the pool-signature loop on flat arrays (`flat_cython.pyx`).

`source` copies `src/crafting_system` to `DIR/crafting_system` and compiles its modules as they are, one by one (`cythonize -i`), with
`annotation_typing=False`: without it Cython reads `x: float` in a signature as a C double and would turn a `Fraction` into a float, which
changes the answers. A module that does not compile keeps its `.py` and is listed; `__init__.py` and `__main__.py` are never compiled. A plan
then runs on the copy with `CRAFTING_SOURCE=DIR` (`profile_plan.py`). It needs a C compiler (MSVC on Windows, gcc on Linux), `cython` and
`setuptools`; each module is one compiler process, one after the other.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FOLDERS = ("abstraction", "actions", "items", "data", "rules", "solver", "cli")  # where a plan spends its time


def cythonize(path: Path, cwd: Path, *directives: str) -> tuple[bool, str, float]:
    began = time.perf_counter()
    command = [sys.executable, "-m", "Cython.Build.Cythonize", "-i", "-3", *(part for d in directives for part in ("-X", d)), str(path)]
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return done.returncode == 0, (done.stdout + done.stderr)[-1500:], time.perf_counter() - began


def flat() -> None:
    ok, log, seconds = cythonize(HERE / "flat_cython.pyx", HERE)
    print(f"flat_cython: {'built' if ok else 'FAILED'} in {seconds:.0f} s", flush=True)
    (HERE / "flat_cython.c").unlink(missing_ok=True)
    shutil.rmtree(HERE / "build", ignore_errors=True)
    if not ok:
        print(log)
        raise SystemExit(1)


def source(out: Path, only: list[str] | None) -> None:
    package = out / "crafting_system"
    if package.exists():
        shutil.rmtree(package)
    shutil.copytree(ROOT / "src" / "crafting_system", package, ignore=shutil.ignore_patterns("__pycache__"))
    modules = sorted(
        path
        for folder in FOLDERS
        for path in (package / folder).rglob("*.py")
        if path.name not in ("__init__.py", "__main__.py") and (only is None or path.relative_to(package).as_posix() in only)
    )
    record = {"compiled": [], "failed": {}, "seconds": 0.0}
    began = time.perf_counter()
    for path in modules:
        name = path.relative_to(package).as_posix()
        ok, log, seconds = cythonize(path, out, "annotation_typing=False")
        print(f"{name}: {'built' if ok else 'FAILED'} in {seconds:.0f} s", flush=True)
        if ok:
            record["compiled"].append(name)
        else:
            record["failed"][name] = log[-600:]
        for extra in (path.with_suffix(".c"), path.with_suffix(".html")):
            extra.unlink(missing_ok=True)
    shutil.rmtree(out / "build", ignore_errors=True)
    record["seconds"] = round(time.perf_counter() - began, 1)
    (out / "compiled.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"compiled {len(record['compiled'])} of {len(modules)} modules in {record['seconds']} s; failed: {sorted(record['failed'])}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=("flat", "source"))
    parser.add_argument("--out")
    parser.add_argument("--only")
    args = parser.parse_args()
    if args.what == "flat":
        flat()
    else:
        source(Path(args.out).resolve(), args.only.split(",") if args.only else None)


if __name__ == "__main__":
    main()
