"""Play the long routes on a runner, and pool the tallies of a long simulation that ran on several runners, and judge the pool (tickets #555, #610).

    PYTHONPATH=tests python -m naive_crafter play  "R04 with restart" --seed 3 --seconds 3000 --out DIR [--off multimod ...]
    PYTHONPATH=tests python -m naive_crafter merge <folder> [--route R13] [--recorded tests/fixtures/naive_crafter/benchmark_means.json]

`tests/test_naive_crafter_routes.py` run with `NAIVE_RUNS`, `NAIVE_SEED` and `NAIVE_OUT` leaves one `naive-<route>-<seed>.json` per
route and runner: the exact mean and the exact spend of each step (from `risk.evaluate`'s side, the same on every runner) and the tally of that
runner's plays. `play` does the same for the four long routes of #610 without the planner: it plays a route for a number of plays or of seconds and leaves the
tally, with no exact side (that is the benchmark's, recorded in `tests/fixtures/naive_crafter/benchmark_means.json`, and `merge --recorded` adds it). With `--off LAW` the law of
`craft.Laws` is turned off (a mutation): `merge` then expects the route to leave the 4-standard-error line, or not to finish at all.

`merge` reads every such file under the folder (a downloaded run keeps one sub-folder per runner), adds the tallies of a route,
and prints the verdict on the mean and on each step with the pooled standard error (`tally.verdict_on`, 4 standard errors); for a route with gaps the chance of finishing
(`tally.finishing_verdict`: the planner's number is a lower bound). It exits 1 when any verdict disagrees (or a mutation survives), so a long simulation fails the way a short one does. It imports nothing of the planner.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path
from random import Random

from . import tally as t
from .craft import Laws
from .play import Judge, Player, read_route
from .world import load_world

REPO = Path(__file__).resolve().parents[2]
PRICES = REPO / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-10.json"
KEYS = REPO / "tests" / "reconcile" / "expected_keys.txt"
RECORDED = REPO / "tests" / "fixtures" / "naive_crafter" / "benchmark_means.json"
# the long routes: id -> (the route file, what is judged: the `mean` of a route that always finishes, or the chance to `finish` of one with gaps)
LONG = {
    "R04 with restart": ("r04-penetrating-quiver-restart", "mean"),
    "R14 with restart": ("r14-hunter-bow-restart", "mean"),
    "R04": ("r04-penetrating-quiver", "finish"),
    "R14": ("r14-hunter-bow", "finish"),
}
MUTANT_USES = 3_000_000  # uses in one play of a mutated route before it is called endless (an unmutated play of R04 is a few hundred thousand)


def file_stem(route_id: str) -> str:
    return route_id.replace(" ", "_")


def group_key(document: dict) -> tuple[str, tuple[str, ...]]:
    return document["route"], tuple(document.get("off") or ())


def play_long(route_id: str, seed: int, runs: int | None, seconds: float | None, off: tuple[str, ...], out: Path) -> Path:
    """Play a long route until `runs` plays or `seconds` have passed, and leave its tally in `out`."""
    stem, kind = LONG[route_id]
    laws = Laws(**{name: False for name in off}) if off else None
    world = load_world(REPO / "examples" / "targets" / f"{stem.removesuffix('-restart')}.yaml", PRICES, KEYS, laws=laws)
    judge = Judge(world)
    route = read_route((REPO / "examples" / "routes" / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    player = Player(world, route, judge)
    rng = Random(555_000 + seed)
    tally = t.Tally()
    started = datetime.datetime.now(datetime.UTC)

    def elapsed() -> float:
        return (datetime.datetime.now(datetime.UTC) - started).total_seconds()

    while (runs is None or tally.n + tally.stuck < runs) and (seconds is None or elapsed() < seconds):
        play, gap = player.try_play(rng, MUTANT_USES if off else 50_000_000)
        if gap is None:
            tally.add(play)
        else:
            tally.add_stuck()
            if kind == "mean" and not off:
                raise SystemExit(f"{route_id}: a play of a route with a restart met a gap: {gap}")
            if off and kind == "mean":
                break  # a mutated route that cannot finish is judged by that alone
    document = {"route": route_id, "kind": kind, "seed": seed, "off": list(off), "seconds": round(elapsed(), 1), "tally": tally.to_dict()}
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"naive-{file_stem(route_id)}-{seed}{''.join('-off-' + name for name in off)}.json"
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return path


def _pooled(folder: Path, route: str | None) -> dict[tuple[str, tuple[str, ...]], list[dict]]:
    documents: dict[tuple[str, tuple[str, ...]], list[dict]] = {}
    for path in sorted(folder.rglob("naive-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if route is None or document["route"] == route:
            documents.setdefault(group_key(document), []).append(document)
    return documents


def _recorded_numbers(recorded: Path | None) -> dict:
    return json.loads(recorded.read_text(encoding="utf-8"))["routes"] if recorded is not None and recorded.is_file() else {}


def _sum(found: list[dict]) -> t.Tally:
    pooled = t.Tally()
    for document in found:
        pooled = pooled.merge(t.Tally.from_dict(document["tally"]))
    return pooled


def _finishing(name: str, label: str, found: list[dict], numbers: dict) -> t.Verdict:
    """The verdict on the chance of finishing of a route with gaps: the exact one from the files or the recorded benchmark."""
    recorded = numbers.get(name, {})
    low = found[0].get("exact_success", recorded.get("success_low"))
    if low is None:
        raise SystemExit(f"{name}: no recorded chance of finishing (give --recorded)")
    if any(d.get("exact_success", low) != low for d in found):
        raise SystemExit(f"{name}: the runners recorded different chances of finishing, so their tallies are not of one thing")
    finished, total = _sum(found).finishing()
    return t.finishing_verdict(f"{label}, the chance of finishing ({total} plays)", low, finished, total, high=recorded.get("success_high", 1.0))


def merge_folder(folder: Path, route: str | None = None, recorded: Path | None = None) -> tuple[list[t.Verdict], dict[str, int]]:
    """The verdicts of the pooled tallies of the routes played as they are (no law off) in a folder, and the number of plays pooled per route."""
    numbers = _recorded_numbers(recorded)
    verdicts: list[t.Verdict] = []
    plays: dict[str, int] = {}
    for (name, off), found in sorted(_pooled(folder, route).items()):
        if off:
            continue
        pooled = _sum(found)
        if "exact_success" in found[0] or found[0].get("kind") == "finish":
            verdict = _finishing(name, name, found, numbers)
            plays[name] = pooled.finishing()[1]
            verdicts.append(verdict)
            continue
        if "exact_mean" in found[0]:
            exact_mean, exact_spend = found[0]["exact_mean"], found[0]["exact_spend"]
            if any(abs(d["exact_mean"] - exact_mean) > 1e-9 * max(1.0, abs(exact_mean)) or d["exact_spend"].keys() != exact_spend.keys() for d in found):
                raise SystemExit(f"{name}: the runners computed different exact sides, so their tallies are not of one thing")
        else:
            if name not in numbers:
                raise SystemExit(f"{name}: no recorded mean (give --recorded)")
            exact_mean, exact_spend = numbers[name]["mean_without_start"], {}
        plays[name] = pooled.n
        verdicts.append(t.verdict_on(f"{name}, the mean cost of the given route ({pooled.n} plays)", exact_mean, pooled.mean_se()))
        for label, spent in exact_spend.items():
            verdicts.append(t.verdict_on(f"{name}, step {label!r}", spent, pooled.spend_mean_se(label)))
    return verdicts, plays


def merge_mutants(folder: Path, route: str | None = None, recorded: Path | None = None) -> list[tuple[str, bool, str]]:
    """For each route played with a law off: (its name, whether the mutation was killed, why). Killed: it cannot finish, or it leaves the line."""
    numbers = _recorded_numbers(recorded)
    found_all: list[tuple[str, bool, str]] = []
    for (name, off), found in sorted(_pooled(folder, route).items()):
        if not off:
            continue
        label = name + "".join(f" with {law} off" for law in off)
        pooled = _sum(found)
        if found[0].get("kind") == "finish":
            verdict = _finishing(name, label, found, numbers)
            found_all.append((label, not verdict.agrees, str(verdict)))
        elif pooled.stuck:
            found_all.append((label, True, f"{pooled.stuck} play(s) could not finish"))
        else:
            if name not in numbers:
                raise SystemExit(f"{name}: no recorded mean (give --recorded)")
            verdict = t.verdict_on(f"{label}, the mean cost ({pooled.n} plays)", numbers[name]["mean_without_start"], pooled.mean_se())
            found_all.append((label, not verdict.agrees, str(verdict)))
    return found_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="naive_crafter")
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge", help="pool the tallies of a long simulation and judge the pool")
    merge.add_argument("folder", type=Path)
    merge.add_argument("--route", default=None, help="only this route id (R05, R08, R09, R10, R11, R12, R13, 'R04 with restart', 'R14 with restart', R04, R14)")
    merge.add_argument("--recorded", type=Path, default=RECORDED, help="the planner's numbers of the long routes (the benchmark's)")
    play = commands.add_parser("play", help="play a long route (R04, R14, with or without a restart) and leave its tally")
    play.add_argument("route", choices=sorted(LONG))
    play.add_argument("--seed", type=int, required=True)
    play.add_argument("--runs", type=int, default=None)
    play.add_argument("--seconds", type=float, default=None)
    play.add_argument("--off", action="append", default=[], help="a law of craft.Laws to turn off (a mutation); give it more than once for more laws")
    play.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "play":
        if arguments.runs is None and arguments.seconds is None:
            parser.error("give --runs or --seconds")
        path = play_long(arguments.route, arguments.seed, arguments.runs, arguments.seconds, tuple(arguments.off), arguments.out)
        print(f"wrote {path}")
        return 0
    verdicts, plays = merge_folder(arguments.folder, arguments.route, arguments.recorded)
    mutants = merge_mutants(arguments.folder, arguments.route, arguments.recorded)
    if not verdicts and not mutants:
        print(f"no naive-*.json under {arguments.folder}", file=sys.stderr)
        return 2
    for verdict in verdicts:
        print(("ok       " if verdict.agrees else "DISAGREES") + " " + str(verdict))
    for label, killed, why in mutants:
        print(("killed   " if killed else "SURVIVES ") + f" {label}: {why}")
    print(f"plays pooled per route: {plays}")
    return 0 if all(verdict.agrees for verdict in verdicts) and all(killed for _, killed, _ in mutants) else 1


if __name__ == "__main__":
    raise SystemExit(main())
