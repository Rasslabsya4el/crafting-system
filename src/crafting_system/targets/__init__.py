"""The YAML target and the goal check (ADR-0008). May import only: data, rules, items, actions, abstraction, solver, risk, simulator, prices.

A target file is a YAML mapping. `load_target(path, data)` and `parse_target(text, data)` turn it into
a `Target`; `Target.is_met_by(item)` says whether a concrete item meets it. Examples with comments are
in `examples/targets/`. Every problem raises `TargetError`, worded `<file>:<line>: <key path>: <what is
wrong>`; list entries in key paths count from 0.

Keys (unknown keys are errors, with a close-match hint):

    base: Paua Amulet       # required: the English name of a base item (case-sensitive), or a base id
    item_level: 84          # required: a whole number from 1 to 100
    influence: []           # optional: shaper, elder, crusader, hunter, redeemer, warlord (any case)
    requirements:           # required: a non-empty list; every entry must be met
      - stat: "+1 to Level of all Lightning Skill Gems"   # exact English stat text, or
      - family: LightningResistance                       # a family id (repoe `groups`)
        mod: Intelligence8  # optional: one mod (game-data id) of the family or stat, so exactly that tier of it
        min_tier: 2         # optional: whole number >= 1; tier 1 is best, so 2 accepts tiers 1 and 2
        min_roll: 40        # optional: a number (single-stat mods) or a list, one number or null per stat
        not_crafted: true   # optional: true or false, default false
      - at_least: 2         # a "k of n" entry: 1 <= k <= len(of)
        of: [...]           # requirements or nested at_least entries
    start_item:             # optional; absent means a fresh normal item of the base, level and influence
      rarity: rare          # normal, magic or rare; default rare when mods are given, else normal
      corrupted: false      # optional
      mods:                 # optional; each mod by its game-data id, tier taken as written
        - mod: LightningResist2
          tier: 3           # whole number >= 1, stored as written (tier derivation is not built yet)
          values: [14]      # one whole number per stat; a bare number is allowed for one stat
          fractured: true   # optional; `crafted` is optional too
    start_price: R12 start amulet   # optional: the name of the start item in the price file (what it costs to get)
    price_file: prices.json # optional path; a relative path counts from the target file's folder

Exactly one of `family` and `stat` names a requirement's mod. `stat` is compared after normalising both
sides (a range such as `(10-24)` becomes `#`, `[X|Y]` markup becomes `Y`), so `+# to maximum Life`
and `+(10-24) to maximum Life` are the same, and it selects every tier and variant of that text. `family`
selects every mod of the family. Rolls (`min_roll`, `values`) are the raw numbers of the game data, for
example life regeneration is per minute. How a mod got on the item does not matter unless `not_crafted`
is set. The members of an `at_least` group are checked independently, so one mod can satisfy two of
them (say a family and a stat text that select the same mod); groups may nest 20 levels deep. Merge keys
(`<<`), anchors (`&name`) and aliases (`*name`) are not supported.
Whether a mod can spawn on the base is not checked here; that belongs to `actions`.
"""

from pathlib import Path

from crafting_system.data import GameData

from .errors import TargetError
from .model import KOfN, Node, Requirement, Target
from .parse import parse_target_text

__all__ = ["KOfN", "Node", "Requirement", "Target", "TargetError", "load_target", "parse_target"]


def parse_target(
    text: str, data: GameData, source: str = "<target>", base_dir: Path | None = None
) -> Target:
    """Parse the YAML `text` of a target against `data`.

    `source` names the file in error messages; `base_dir` is what a relative `price_file` counts from
    (None leaves it as written). Raises `TargetError` for anything wrong with the text.
    """
    return parse_target_text(text, data, source, base_dir)


def load_target(path: Path, data: GameData) -> Target:
    """Read the UTF-8 target file at `path` and parse it; a relative `price_file` counts from its folder."""
    source = str(path)
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        raise TargetError(f"{source}: the target file does not exist") from None
    except UnicodeDecodeError:
        raise TargetError(f"{source}: the target file is not UTF-8 text") from None
    except OSError as problem:
        raise TargetError(f"{source}: the target file cannot be read ({problem.strerror or problem})") from None
    return parse_target_text(text, data, source, path.parent)
