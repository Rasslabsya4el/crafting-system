"""Local launcher: put this worktree's src/, tests/ and research/312 first on the path, then run a script.

    python research/376/_local.py SCRIPT ARGS...

The Python of the shared local environment is installed editable against another worktree, so a plain run would import that
worktree's code; this puts the worktree of the script first. Only for quick local checks (CI and heavy runs use the checkout).
"""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "research" / "312"), str(ROOT / "research" / "376")]
os.environ.setdefault("CRAFTING_CACHE_DIR", r"C:\Coding\Crafting system\local\cache")
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
