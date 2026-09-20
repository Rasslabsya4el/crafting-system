"""Build the literal, limited PoB item-base tag projection for five classes."""

from __future__ import annotations

import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT / "src"))

from craftoracle.pob_bases import build_pob_bases_projection, serialize_projection


SOURCE_FILENAMES = ("helmet.lua", "bow.lua", "ring.lua", "body.lua", "gloves.lua")
BASES_DIRECTORY = WORKTREE_ROOT / "sources/pob/Data/Bases"
OUTPUT_PATH = WORKTREE_ROOT / "data/pob_bases.json"


def build() -> Path:
    """Validate all five sources before replacing the deterministic JSON file."""
    sources = [
        (f"sources/pob/Data/Bases/{filename}", (BASES_DIRECTORY / filename).read_bytes())
        for filename in SOURCE_FILENAMES
    ]
    output_bytes = serialize_projection(build_pob_bases_projection(sources))
    OUTPUT_PATH.write_bytes(output_bytes)
    return OUTPUT_PATH


def main() -> None:
    build()


if __name__ == "__main__":
    main()
