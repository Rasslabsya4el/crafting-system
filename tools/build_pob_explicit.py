"""Build the deterministic, limited projection of PoB ModExplicit rows."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT / "src"))

from craftoracle.pob_data import build_pob_explicit_projection, serialize_projection


SOURCE_PATH = WORKTREE_ROOT / "sources/pob/Data/ModExplicit.lua"
OUTPUT_PATH = WORKTREE_ROOT / "data/pob_mod_explicit.json"


def build() -> Path:
    """Parse and validate all source bytes before replacing the output file."""
    source_bytes = SOURCE_PATH.read_bytes()
    source_text = source_bytes.decode("utf-8")
    projection = build_pob_explicit_projection(
        source_text, hashlib.sha256(source_bytes).hexdigest()
    )
    output_bytes = serialize_projection(projection)
    OUTPUT_PATH.write_bytes(output_bytes)
    return OUTPUT_PATH


def main() -> None:
    build()


if __name__ == "__main__":
    main()
