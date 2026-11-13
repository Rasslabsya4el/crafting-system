"""Time and measure each stage the CLI runs after the plan for R04 or R14 (ticket #70): report, text, JSON, route page, verify.

    python .github/scripts/cli_stages.py --route r04|r14 --out DIR [--stage report,text,json,page,verify,route]

Plans the route as `make_plan(budget=None, with_risk=False)` (`judges_route=True`: the stages judge a given route, so `auto` walks, #535) and gives it a risk without quantiles (the packed route's own rule for
a chain it cannot afford), then runs the stages in order and prints the seconds, the peak memory and the size of each product.
Never run on a PC. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packed_routes import inputs, peak_mb  # noqa: E402

from crafting_system.cli import make_plan  # noqa: E402

from crafting_system.planner import _packed
from crafting_system.planner._plan import add_risk  # noqa: E402
from crafting_system.cli._report import build_report, policy_document, render_text  # noqa: E402
from crafting_system.cli._route import evaluate_route, load_route
from crafting_system.cli._route_report import render_route_text, route_document  # noqa: E402
from crafting_system.cli._route_view import write_route_page  # noqa: E402
from crafting_system.cli._verify import verify  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ROUTES = {"r04": "r04-penetrating-quiver", "r14": "r14-hunter-bow"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True, choices=tuple(ROUTES))
    parser.add_argument("--out", required=True)
    parser.add_argument("--stage", default="report,text,json,page,verify,route")
    parser.add_argument("--runs", type=int, default=200)
    arguments = parser.parse_args()
    began = time.perf_counter()
    stages = arguments.stage.split(",")
    stages += [f"{name}_{kind}" for name in ("route", "route_as_written") for kind in ("text", "json", "page")]
    result: dict = {"route": arguments.route}

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, with_risk=False, judges_route=True)  # the stages judge the guide's route: `auto` walks (#535)
    plan = add_risk(plan)
    say(f"planned: mean {plan.mean_remaining!r}, {len(plan.policy):,} policy states, shown as {len(plan.view_policy):,}, risk {plan.risk.mean.value!r}, p90 {plan.risk.p90!r}")

    def stage(name: str, function):
        if name not in stages:
            return None
        started = time.perf_counter()
        try:
            value = function()
        except Exception as error:  # noqa: BLE001 - a stage that fails is a finding, the others still run
            result[name] = {"seconds": round(time.perf_counter() - started, 1), "peak_mb": peak_mb(), "error": f"{type(error).__name__}: {error}"[:500]}
            say(f"{name} FAILED: {result[name]}")
            return None
        result[name] = {"seconds": round(time.perf_counter() - started, 1), "peak_mb": peak_mb()}
        say(f"{name}: {result[name]}")
        return value

    report = stage("report", lambda: build_report(plan, data))
    if report is not None:
        result["report"]["states"] = len(report.states)
        result["report"]["transitions"] = sum(len(state.transitions) for state in report.states)
        say(f"report: {result['report']}")
        text = stage("text", lambda: render_text(report, None, target_name=ROUTES[arguments.route]))
        if text is not None:
            result["text"]["lines"] = text.count("\n")
            result["text"]["bytes"] = len(text)
        document = stage("json", lambda: json.dumps(policy_document(report, None, target_name=ROUTES[arguments.route])))
        if document is not None:
            result["json"]["bytes"] = len(document)
        stage("page", lambda: write_route_page(out / "page.html", report, data, target_name=ROUTES[arguments.route]))
        page = out / "page.html"
        if page.exists():
            result["page"]["bytes"] = page.stat().st_size
    check = stage("verify", lambda: verify(data, plan, runs=arguments.runs))
    if check is not None:
        result["verify"].update(agrees=check.agrees, reason=check.reason, simulated_mean=check.report.cost.value, computed_mean=check.computed_mean)
        say(f"verify: {result['verify']}")
    if "route" in stages:
        for name, suffix in (("route", "-restart"), ("route_as_written", "")):
            path = ROOT / "examples" / "routes" / f"{ROUTES[arguments.route]}{suffix}.yaml"
            route = load_route(path, plan, data)
            given = stage(name, lambda: evaluate_route(plan, route, data))
            if given is not None and report is not None:
                stage(f"{name}_text", lambda: render_route_text(report, route, given, data, file_name=path.name))
                stage(f"{name}_json", lambda: json.dumps(route_document(report, route, given, data, file_name=path.name)))
                stage(f"{name}_page", lambda: write_route_page(out / f"{name}.html", report, data, route=route, given=given, target_name="route"))
    (out / f"{arguments.route}.stages.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
