"""Count the route page of a route: its steps, rows and size (tickets #465 and #466); run by the `Run a command` workflow.

    python .github/scripts/page_size.py --route r04|r14|... [--out DIR]

Makes the plan the way the planner does (`make_plan(solver="auto")`, exact), draws the route page of the planner's own policy
(`build_section(route_input(plan))`, rendered by `render_page`, the page the command writes without a buy spec or a given route)
and writes `<route>.page.json` with:

* `steps`: the rows after the start row (a step per player action since #466; one per exact chance, or one per state, before it);
* `rows`, `html_bytes`, `html_mb`: the page as a person gets it;
* `policy_states`, `view_states`, `lumped`: the policy and the lumped view the page is drawn from (`Plan.view_policy`);
* the seconds each phase took and the peak memory;

and `<route>.rows.txt`, one block per row: its title, its fields and the tier lines, so a page of a big route can be read without opening it.

Run it on two refs to compare the code before and after a change of the page: the numbers do not depend on the ref but on the
code of `cli/_route_flow.py` and `cli/_route_view.py`. Never run on a PC for R04 or R14: the plan walks for minutes to half an hour.
Run by `.github/scripts/heavy_dispatch.py`, see `docs/ci.md`.
"""

import argparse
import faulthandler
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from packed_routes import inputs, peak_mb, watch_memory

from crafting_system.cli import _packed, make_plan
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, _View, build_section, route_input


def rows_text(section) -> str:
    blocks = []
    for row in section.rows:
        lines = [f"{row.number}. {row.title}"]
        for field in row.fields:
            lines.append(f"    {field.label}: " + " | ".join(line.text for line in field.lines))
        lines += [f"    branch card: {branch.caption}" for branch in getattr(row, "branches", ())]  # a page before #466 has none
        blocks.append("\n".join(lines))
    return "\n".join(blocks) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--out")
    parser.add_argument("--profile", action="store_true", help="time the flow and each row before the page is drawn")
    arguments = parser.parse_args()
    threading.Thread(target=watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver="auto")
    planned = time.perf_counter()
    say(f"planned: {len(plan.policy):,} policy states, {len(plan.view_policy):,} in the view")
    faulthandler.dump_traceback_later(1200, exit=True, file=sys.stdout)  # the page takes a minute; if it takes twenty, show where it is and stop
    if arguments.profile:  # where the page spends its time: the flow, then each row; a stack every 5 minutes shows where a slow one sits
        faulthandler.dump_traceback_later(300, repeat=True, file=sys.stdout)
        view = _View(route_input(plan), data, None, "", True)
        say(f"flow: {len(view.flow.steps):,} steps, measured {view.flow.measured}, entered {view.flow.entered}")
        for step in view.flow.steps[:60]:
            before = time.perf_counter()
            view.step_row(step)
            say(f"row {step.number}: {len(step.states):,} states, {len(step.edges)} edges, {time.perf_counter() - before:.1f}s")
        faulthandler.cancel_dump_traceback_later()
    section = build_section(route_input(plan), data)
    drawn = time.perf_counter()
    say(f"section: {len(section.rows):,} rows")
    html = render_page(Page(arguments.route, (section,)))
    rendered = time.perf_counter()
    faulthandler.cancel_dump_traceback_later()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    result = {
        "route": arguments.route,
        "commit": commit,
        "steps": len(section.rows) - 1,
        "rows": len(section.rows),
        "html_bytes": len(html.encode("utf-8")),
        "html_mb": round(len(html.encode("utf-8")) / 1_000_000, 3),
        "policy_states": len(plan.policy),
        "view_states": len(plan.view_policy),
        "lumped": plan.lumped,
        "plan_seconds": round(planned - began, 1),
        "section_seconds": round(drawn - planned, 1),
        "render_seconds": round(rendered - drawn, 1),
        "peak_mb": peak_mb(),
    }
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.page.json").write_text(text + "\n", encoding="utf-8")
        (out / f"{arguments.route}.rows.txt").write_text(rows_text(section), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
