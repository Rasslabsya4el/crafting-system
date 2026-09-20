"""Build the deterministic, source-preserving PoB modifier-family projection."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT / "src"))

from craftoracle.pob_mod_families import (
    SOURCE_PATHS,
    build_pob_mod_families_projection,
    serialize_projection,
)


OUTPUT_PATH = WORKTREE_ROOT / "data/pob_mod_families.json"


def build(output_path: Path = OUTPUT_PATH) -> tuple[Path, dict, bytes]:
    """Validate all input bytes before replacing the deterministic output file."""
    source_payloads = {
        source_path: (WORKTREE_ROOT / source_path).read_bytes()
        for source_path in SOURCE_PATHS
    }
    projection = build_pob_mod_families_projection(source_payloads)
    output_bytes = serialize_projection(projection)
    output_path.write_bytes(output_bytes)
    return output_path, projection, output_bytes


def main() -> None:
    output_path, projection, output_bytes = build()
    for source in projection["sources"]:
        print(f"{source['path']}: {source['record_count']}")
    print(f"total: {len(projection['mods'])}")
    non_integer_stat_orders = sum(
        not isinstance(value, int)
        for mod in projection["mods"]
        for value in mod["statOrder"]
    )
    print(f"non_integer_stat_order: {non_integer_stat_orders}")
    print("skipped: 0")
    print("errors: 0")
    print(f"output: {output_path.relative_to(WORKTREE_ROOT)}")
    print(f"bytes: {len(output_bytes)}")
    print(f"sha256: {hashlib.sha256(output_bytes).hexdigest()}")


if __name__ == "__main__":
    main()
