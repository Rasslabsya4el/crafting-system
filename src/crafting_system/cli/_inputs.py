"""What the commands of the CLI share: loading the prices of a target and writing a JSON file."""

import json
from pathlib import Path

from crafting_system.config import Config
from crafting_system.prices import PriceFile, default_price_file_path, load_prices
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME


def load_target_prices(price_file: Path | None, config: Config) -> PriceFile:
    """The price file the target names, else the configured one, with `price_overrides.toml` beside it."""
    path = price_file if price_file is not None else default_price_file_path(config)
    return load_prices(path, path.parent / OVERRIDES_FILE_NAME)


def write_json(path: Path, document: dict) -> None:
    """Write `document` as UTF-8 JSON with LF line endings; infinity and NaN are an error (JSON has none)."""
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
