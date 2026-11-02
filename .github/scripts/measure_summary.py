"""The report of the measurement chain (ticket #399): every step's summary.md under one heading per step.

`download-artifact` with a pattern puts each artifact in a folder named after it, so step `bloat` is read from
`<art>/measure-bloat/summary.md`. `build_report` is the whole report, a pure function; `main` writes it to `<out>/report.md`.
"""

import argparse
import json
from pathlib import Path

STEPS = ["bloat", "routes", "coverage", "repeats", "mutation"]


def build_report(art_dir, results) -> str:
    """The report text: a title, then for each step `## <step> (<result>)` and its summary.md (or `No summary.`)."""
    art_dir = Path(art_dir)
    lines = ["# Measurement week report", ""]
    for step in STEPS:
        lines += [f"## {step} ({results.get(step, 'unknown')})", ""]
        path = art_dir / f"measure-{step}" / "summary.md"
        if path.is_file():
            lines += [path.read_text(encoding="utf-8").rstrip(), ""]
        else:
            lines += ["No summary.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write the measurement chain's report.md (#399).")
    parser.add_argument("--art", required=True, help="folder of the downloaded artifacts")
    parser.add_argument("--out", required=True, help="folder to write report.md into")
    parser.add_argument("--results", required=True, help='JSON of step name to job result, e.g. {"bloat": "success"}')
    args = parser.parse_args(argv)
    results = json.loads(args.results)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(build_report(args.art, results), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
