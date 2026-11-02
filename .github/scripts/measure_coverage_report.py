"""The coverage step of the measurement chain (ticket #399): which code no test runs, and the report.

Reads the combined coverage.json (`coverage json`), the source files under `--root`, and the pytest exit
codes of the slots (`exit-<slot>.txt`). Writes `summary.md`, `uncovered-functions.txt` and `headline.txt`
into `--out`. Standard library only.
"""

import argparse
import ast
import json
from pathlib import Path

TOP_FILES = 30


def file_rows(cov):
    """(path, statements, missing, percent) per file, the most missing statements first."""
    rows = []
    for path, info in cov["files"].items():
        summary = info["summary"]
        rows.append((path, summary["num_statements"], summary["missing_lines"], summary["percent_covered"]))
    return sorted(rows, key=lambda row: (-row[2], row[0]))


def is_docstring(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def functions_never_entered(source, executed):
    """(qualname, first_line) of each function none of whose body statements ran, in source order.

    The body is `node.body` without a leading docstring. Nested functions and methods are included; the qualname
    joins the enclosing classes and functions with dots (`Class.method`, `outer.inner`).
    """
    found = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = prefix + child.name
                body = child.body
                if body and is_docstring(body[0]):
                    body = body[1:]
                if not any(statement.lineno in executed for statement in body):
                    found.append((qualname, child.lineno))
                visit(child, qualname + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return sorted(found, key=lambda item: item[1])


def read_exit_codes(folder):
    """The pytest exit code of each slot, from the `exit-<slot>.txt` files, by slot number."""
    codes = {}
    for path in sorted(Path(folder).glob("exit-*.txt"), key=lambda p: int(p.stem.removeprefix("exit-"))):
        codes[int(path.stem.removeprefix("exit-"))] = int(path.read_text(encoding="utf-8").strip())
    return codes


def build_report(cov, root, exits):
    """The three texts of the report: (summary.md, uncovered-functions.txt, headline.txt)."""
    total = cov["totals"]["percent_covered"]
    uncovered = []  # (path, line, qualname), grouped by file
    for path in sorted(cov["files"]):
        executed = set(cov["files"][path]["executed_lines"])
        source = (root / path).read_text(encoding="utf-8")
        for qualname, line in functions_never_entered(source, executed):
            uncovered.append((path, line, qualname))
    files_with_uncovered = len({path for path, _, _ in uncovered})
    file_word = "file" if files_with_uncovered == 1 else "files"

    codes = read_exit_codes(exits)
    nonzero = {slot: code for slot, code in codes.items() if code != 0}
    if not codes:
        exit_lines = ["no exit files found"]
    elif not nonzero:
        exit_lines = ["all slots passed"]
    else:
        exit_lines = ["Non-zero pytest exit codes:"] + [f"- {slot}: {code}" for slot, code in nonzero.items()]

    lines = [
        "# coverage",
        "",
        f"Total: {total:.1f}% of statements covered.",
        f"Files: {len(cov['files'])}. Functions never entered: {len(uncovered)} (in {files_with_uncovered} {file_word}).",
        "",
        *exit_lines,
        "",
        "| file | statements | missing | percent |",
        "|---|---:|---:|---:|",
    ]
    for path, statements, missing, percent in file_rows(cov)[:TOP_FILES]:
        lines.append(f"| {path} | {statements} | {missing} | {percent:.1f} |")
    summary = "\n".join(lines) + "\n"

    functions = "".join(f"{path}:{line} {qualname}\n" for path, line, qualname in uncovered)
    headline = (
        f"Покрытие кода тестами: {total:.1f}%; функций, в которые не заходит ни один тест: "
        f"{len(uncovered)} (в {files_with_uncovered} файлах).\n"
    )
    return summary, functions, headline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", required=True, type=Path, help="coverage.json of the combined run")
    parser.add_argument("--root", required=True, type=Path, help="the repository root the paths are relative to")
    parser.add_argument("--exits", required=True, type=Path, help="folder with the exit-<slot>.txt files")
    parser.add_argument("--out", required=True, type=Path, help="folder to write the three files to")
    args = parser.parse_args(argv)

    cov = json.loads(args.json.read_text(encoding="utf-8"))
    summary, functions, headline = build_report(cov, args.root, args.exits)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    (args.out / "uncovered-functions.txt").write_text(functions, encoding="utf-8")
    (args.out / "headline.txt").write_text(headline, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
