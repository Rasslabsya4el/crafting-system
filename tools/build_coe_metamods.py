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
    source = arguments.input.read_bytes().decode("utf-8")
    table = build_metamod_table(source, arguments.input.as_posix())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(serialize_metamod_table(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
