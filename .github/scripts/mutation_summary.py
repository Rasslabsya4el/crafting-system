"""Merge the results of the mutation rounds into the step's artifact (ticket #399, step 5).

Reads `plan.json` and every `results.jsonl` under a folder (one per job of every round), keeps the last record of
each mutant, and writes three files:
  summary.md     `# mutation`: totals per outcome, the modules ranked by survival rate, the first 40 survivors
  survivors.txt  every survivor: `file:line`, operator, original -> mutated
  headline.txt   one line of Russian for the diary

Survival % is survived / checked, where checked = killed + survived + timeout + error. A mutant that was skipped
(its test set failed clean or was too slow) or never started counts as "not reached". Many survivors are equivalent
mutants (the change does not alter any result, such as `x >= 1` on an integer that is never 0), so the rate is an
upper bound; the ranking and the list point at where to look.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PREFIX = "src/crafting_system/"
OUTCOMES = ("killed", "survived", "timeout", "error")
TOP_SURVIVORS = 40
TABLE_ROWS = 45
MIN_CHECKED_FOR_WORST = 10


def read_results(folder: Path) -> dict[int, dict]:
    """The last record of each mutant number under `folder`."""
    found: dict[int, dict] = {}
    for path in sorted(folder.rglob("results.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                found[int(record["id"])] = record
    return found


def short(module: str) -> str:
    return module.removeprefix(PREFIX)


def one_line(text: str, limit: int = 110) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def module_rows(plan: dict, results: dict[int, dict]) -> list[dict]:
    """One row per planned file with its counts, ranked by survival rate (modules with nothing checked last)."""
    rows = {
        file: {"module": short(file), "tier": info["tier"], "planned": info["mutants"], **dict.fromkeys(OUTCOMES, 0), "skipped": 0}
        for file, info in plan["files"].items()
    }  # fmt: skip
    for record in results.values():
        row = rows.get(record["file"])
        if row is not None:
            row[record["outcome"]] += 1
    for row in rows.values():
        row["checked"] = sum(row[name] for name in OUTCOMES)
        row["survival"] = row["survived"] / row["checked"] if row["checked"] else None
        row["not_reached"] = row["planned"] - row["checked"]
    listed = [row for row in rows.values() if row["planned"]]
    return sorted(listed, key=lambda row: (row["survival"] is None, -(row["survival"] or 0.0), row["tier"], row["module"]))


def worst_module(rows: list[dict]) -> str | None:
    """The module with the highest survival rate among those with enough checked mutants (else any with a rate)."""
    for floor in (MIN_CHECKED_FOR_WORST, 1):
        candidates = [row for row in rows if row["checked"] >= floor and row["survived"]]
        if candidates:
            return max(candidates, key=lambda row: (row["survival"], row["checked"]))["module"]
    return None


def survivors(plan: dict, results: dict[int, dict]) -> list[dict]:
    """Survivors in plan order, which is the module priority."""
    return [results[number] for number in sorted(results) if results[number]["outcome"] == "survived"]


def survivor_line(record: dict, width: int = 110) -> str:
    cut = " [tests cut]" if record.get("cut") else ""
    return (
        f"{short(record['file'])}:{record['line']}  {record['operator']}  "
        f"{one_line(record['original'], width)} → {one_line(record['mutated'], width)}{cut}"
    )


def headline(rows: list[dict], total: Counter) -> str:
    checked = sum(total[name] for name in OUTCOMES)
    if not checked:
        return "Мутантов проверено: 0; шаг ничего не успел проверить."
    percent = 100 * total["survived"] / checked
    worst = worst_module(rows)
    ending = f"хуже всего покрыт {worst}." if worst else "выживших нет."
    return f"Мутантов проверено: {checked}; выжило (тесты не заметили поломку): {total['survived']} ({percent:.1f}%); {ending}"


def build(plan: dict, results: dict[int, dict]) -> tuple[str, str, str]:
    """(summary.md, survivors.txt, headline.txt) texts."""
    rows = module_rows(plan, results)
    total = Counter(record["outcome"] for record in results.values())
    planned = len(plan["mutants"])
    checked = sum(total[name] for name in OUTCOMES)
    unreached_lines = sum(info["unreached"] for info in plan["files"].values())
    sources = Counter(plan["sets"][record["set"]]["source"] for record in results.values() if record["set"] in plan["sets"])

    lines = ["# mutation", ""]
    lines.append(
        f"Planned {planned} mutants of {len(plan['files'])} files; checked {checked}; "
        f"not reached {planned - checked} (deadline, or tests unusable: skipped {total['skipped']})."
    )
    lines.append("")
    lines.append("| outcome | mutants |")
    lines.append("|---|---|")
    for name in (*OUTCOMES, "skipped"):
        lines.append(f"| {name} | {total[name]} |")
    survival = f"{100 * total['survived'] / checked:.1f}%" if checked else "n/a"
    lines += ["", f"Survival: {total['survived']} of {checked} checked ({survival}). Many survivors are equivalent mutants, so this is an upper bound."]
    lines.append(
        f"Tests of a mutant came from: coverage contexts {sources['coverage']}, test files importing the module {sources['imports']}."
        f" Mutants on lines no test runs (not planned): {unreached_lines}."
        + (" The coverage data was missing, so the plan used the import-based tests." if not plan.get("coverage") else "")
    )
    lines += ["", "## Modules by survival rate", ""]
    lines.append("| module | tier | mutants | killed | survived | timeout | error | survival % | not reached |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in rows[:TABLE_ROWS]:
        rate = "-" if row["survival"] is None else f"{100 * row['survival']:.1f}"
        lines.append(
            f"| {row['module']} | {row['tier']} | {row['checked']} | {row['killed']} | {row['survived']} | {row['timeout']} | "
            f"{row['error']} | {rate} | {row['not_reached']} |"
        )
    if len(rows) > TABLE_ROWS:
        lines.append(f"\n{len(rows) - TABLE_ROWS} more modules, with a lower rate or nothing checked, are not listed.")
    lines.append("(`mutants` is the number checked: killed + survived + timeout + error.)")

    everyone = survivors(plan, results)
    lines += ["", f"## First {min(TOP_SURVIVORS, len(everyone))} survivors in module priority order (all {len(everyone)} are in survivors.txt)", ""]
    lines += [f"- `{survivor_line(record, 90)}`" for record in everyone[:TOP_SURVIVORS]]
    if not everyone:
        lines.append("- none")

    survivor_text = "\n".join(survivor_line(record, 300) for record in everyone) + ("\n" if everyone else "")
    return "\n".join(lines) + "\n", survivor_text, headline(rows, total) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True, help="folder holding every job's results.jsonl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    summary, survivor_text, line = build(plan, read_results(args.results))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    (args.out / "survivors.txt").write_text(survivor_text, encoding="utf-8")
    (args.out / "headline.txt").write_text(line, encoding="utf-8")
    print(line, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
