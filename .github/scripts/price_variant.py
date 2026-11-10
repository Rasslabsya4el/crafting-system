"""A copy of a price file with some prices set by hand, to ask what a plan does when a price is different (#616, #627).

    python .github/scripts/price_variant.py IN.json OUT.json "Shrieking Essence of Fear=8.8" "Screaming Essence of Spite=15"

Each named price becomes a hand price (source `override`, provenance `override`, today's league and the file's date); the others are untouched.
The input is only read. Nothing here goes to the network.
"""

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crafting_system.prices import PriceEntry, load_price_file, write_price_file  # noqa: E402
from crafting_system.prices.provenance import OVERRIDE, Provenance  # noqa: E402


def main(argv: list[str]) -> int:
    source, target, *changes = argv
    prices = load_price_file(Path(source))
    day = prices.fetched_at.date().isoformat()
    kept = dict(prices.prices)
    for change in changes:
        name, _, chaos = change.rpartition("=")
        if name not in kept:
            print(f"no price named {name!r}", file=sys.stderr)
            return 2
        kept[name] = PriceEntry(float(chaos), "override", f"set by hand for a sensitivity run (was {kept[name].chaos:g})", None, Provenance(OVERRIDE, prices.league, day))
    write_price_file(Path(target), replace(prices, prices=kept))
    print(f"wrote {target}: {len(changes)} prices set by hand")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
