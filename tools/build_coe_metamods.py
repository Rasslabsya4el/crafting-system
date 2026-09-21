"""Build the committed literal observation of the frozen CoE metamod table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from craftoracle.coe_metamods import build_metamod_table, serialize_metamod_table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    input_path = arguments.input.resolve()
    try:
        source_path = input_path.relative_to(ROOT).as_posix()
    except ValueError:
        source_path = arguments.input.as_posix()
    source = input_path.read_bytes().decode("utf-8")
    table = build_metamod_table(source, source_path)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(serialize_metamod_table(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
