"""Repository-root bootstrap for the source-layout :mod:`craftoracle` package."""

from pathlib import Path as _Path


__path__ = [str(_Path(__file__).resolve().parent.parent / "src" / "craftoracle")]
