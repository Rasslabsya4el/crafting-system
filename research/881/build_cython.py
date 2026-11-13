"""Build the Cython candidates of ticket #881 (prototypes; no `src/` change).

    python research/881/build_cython.py flat                      # research/881/flat_cython.pyx, in place
    python research/881/build_cython.py source --out DIR [--only abstraction/_kernel.py,...]

`flat` builds the pool-signature loop on flat arrays (`flat_cython.pyx`).

`source` copies `src/crafting_system` to `DIR/crafting_system` and compiles its modules as they are, one by one (`cythonize -i`), with
`annotation_typing=False`: without it Cython reads `x: float` in a signature as a C double and would turn a `Fraction` into a float, which
changes the answers. A module that does not compile keeps its `.py` and is listed with the compiler's first
message; `__init__.py` and `__main__.py` are never compiled. Then the copy is tried (`--smoke`, a small route): while the plan raises, the compiled
module the error came from goes back to its `.py` and is listed as reverted (a compiled module can behave differently from its source), and
the mean of the plan is compared with the mean on the source. A plan then runs on the copy with `CRAFTING_SOURCE=DIR` (`profile_plan.py`). It needs a C compiler (MSVC on Windows, gcc on Linux), `cython` and
`setuptools`; each module is one compiler process, one after the other.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FOLDERS = ("abstraction", "actions", "items", "data", "rules", "solver", "planner", "cli")  # where a plan spends its time


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


def plan_once(route: str, folder: Path | None) -> tuple[float | None, str]:
    """The mean of a small plan on the source (`folder` None) or on the copy, and the end of what it printed."""
    env = dict(os.environ)
    env.pop("CRAFTING_SOURCE", None)
    if folder is not None:
        env["CRAFTING_SOURCE"] = str(folder)
    done = subprocess.run([sys.executable, str(HERE / "profile_plan.py"), "--route", route, "--mode", "plain"], env=env, capture_output=True, text=True)
    found = re.search(r'"mean_remaining": ([-0-9.e+]+)', done.stdout)
    return (float(found.group(1)) if done.returncode == 0 and found else None), (done.stdout + done.stderr)[-4000:]


def try_out(out: Path, package: Path, route: str) -> tuple[dict, dict]:
    """Plan `route` on the copy; while it raises, put the compiled module the error came from back to its `.py`."""
    reverted: dict[str, str] = {}
    wanted, _ = plan_once(route, None)
    for _ in range(40):
        mean, log = plan_once(route, out)
        if mean is not None:
            return reverted, {"route": route, "mean_on_source": wanted, "mean_on_copy": mean, "equal": mean == wanted}
        frames = re.findall(r'File "[^"]*crafting_system[/\\]([^"]+)\.py"', log)
        last = next((frame.replace(chr(92), "/") for frame in reversed(frames) if built_files(package, frame.replace(chr(92), "/"))), None)
        if last is None:
            return reverted, {"route": route, "error": log[-1200:]}
        for built in built_files(package, last):
            built.unlink()
        reverted[f"{last}.py"] = log.strip().splitlines()[-1][:300]
        print(f"{last}.py: reverted to its source ({reverted[f'{last}.py']})", flush=True)
    return reverted, {"route": route, "error": "still failing after 40 modules were reverted"}


def built_files(package: Path, module: str) -> list[Path]:
    path = package / module
    return [found for found in path.parent.glob(f"{path.name}.*") if found.suffix in (".so", ".pyd")]


def source(out: Path, only: list[str] | None, smoke: str | None) -> None:
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
            message = re.search(r"\.py:\d+:\d+: .*", log)
            record["failed"][name] = message.group(0)[:300] if message else log[-300:]
        for extra in (path.with_suffix(".c"), path.with_suffix(".html")):
            extra.unlink(missing_ok=True)
    shutil.rmtree(out / "build", ignore_errors=True)
    record["seconds"] = round(time.perf_counter() - began, 1)
    if smoke:
        record["reverted"], record["smoke"] = try_out(out, package, smoke)
        record["compiled"] = [name for name in record["compiled"] if name not in record["reverted"]]
    (out / "compiled.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"compiled {len(record['compiled'])} of {len(modules)} modules in {record['seconds']} s; failed: {sorted(record['failed'])}; {record.get('smoke')}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=("flat", "source"))
    parser.add_argument("--out")
    parser.add_argument("--only")
    parser.add_argument("--smoke", help="a small route to try the copy on, e.g. r13")
    args = parser.parse_args()
    if args.what == "flat":
        flat()
    else:
        source(Path(args.out).resolve(), args.only.split(",") if args.only else None, args.smoke)


if __name__ == "__main__":
    main()
