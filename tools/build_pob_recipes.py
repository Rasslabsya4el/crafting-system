"""Build deterministic literal projections for PoB bench and essence tables."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT / "src"))

from craftoracle.pob_recipes import (
    build_pob_bench_projection,
    build_pob_essences_projection,
    serialize_projection,
)


BENCH_SOURCE_PATH = WORKTREE_ROOT / "sources/pob/Data/ModMaster.lua"
ESSENCE_SOURCE_PATH = WORKTREE_ROOT / "sources/pob/Data/Essence.lua"
BENCH_OUTPUT_PATH = WORKTREE_ROOT / "data/pob_bench.json"
ESSENCE_OUTPUT_PATH = WORKTREE_ROOT / "data/pob_essences.json"


def build() -> tuple[Path, Path]:
    """Validate both sources before replacing either deterministic JSON output."""
    bench_source = BENCH_SOURCE_PATH.read_bytes()
    essence_source = ESSENCE_SOURCE_PATH.read_bytes()
    bench_output = serialize_projection(build_pob_bench_projection(bench_source))
    essence_output = serialize_projection(build_pob_essences_projection(essence_source))
    BENCH_OUTPUT_PATH.write_bytes(bench_output)
    ESSENCE_OUTPUT_PATH.write_bytes(essence_output)
    return BENCH_OUTPUT_PATH, ESSENCE_OUTPUT_PATH


def _report(label: str, source: Path, output: Path) -> str:
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    return (
        f"{label}: records={json.loads(output_bytes)['source']['record_count']} "
        f"source_sha256={hashlib.sha256(source_bytes).hexdigest()} "
        f"output_bytes={len(output_bytes)} "
        f"output_sha256={hashlib.sha256(output_bytes).hexdigest()}"
    )


def main() -> None:
    bench_output, essence_output = build()
    print(_report("bench", BENCH_SOURCE_PATH, bench_output))
    print(_report("essences", ESSENCE_SOURCE_PATH, essence_output))


if __name__ == "__main__":
    main()
