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
    implicits:              # optional: a non-empty list; every entry must be met (ADR-0027)
      - stat: "#% chance to Avoid being Shocked"   # exact English stat text, or `family: <family id>`;
                            # only implicit mods take part (Eldritch ones and the base's own), never a prefix or suffix
        mod: AvoidShockEldritchImplicit3   # optional: one implicit mod; the only way to name an "in your Presence" variant
        min_grade: 3        # optional: whole number 1 (Lesser) to 6 (Perfect); Eldritch implicits only
        min_roll: 40        # optional: as for a requirement, the base roll the item stores
        corrupted: true     # optional (ADR-0036): resolve the entry among the corrupted implicit pool of the base at `item_level`
                            # (a Vaal Orb's implicit), and only there; the target then asks for a corrupted item
    quality:                # optional: the catalyst quality of a ring, amulet or belt (ADR-0029), or the plain quality of a
                            # weapon or armour (ADR-0049), which has no `type`
      type: intrinsic       # abrasive, accelerating, fertile, imbued, intrinsic, noxious, prismatic, tempering,
                            # turbulent, unstable, sinistral or dextral (any case)
      min_percent: 20       # whole number from 1 to 20 (weapon or armour: 1 to 30, but above 20 only a start item that holds it
                            # can meet it, since Whetstones and Scraps stop at 20)
    sockets:                # optional (ADR-0046): a weapon or armour, not jewellery; a requirement of the finish, not of the mods
      count: 6              # optional: at least this many sockets, 1 to 6 and at most the class maximum of the base
      links: 5              # optional: a linked group of at least this many sockets, 2 to 6, at most `count` when that is given
      colours:              # optional: at least this many sockets of each colour, counted in one linked group of at least `links`
        R: 1                #   sockets when `links` is given and over the whole item otherwise; the colours add up to at most
        G: 1                #   `links` (or `count` without `links`); each is a whole number from 1 to 6
        B: 1
    enchantment:            # optional: the enchantment wanted (ADR-0050); an item holds one, so only `any_of` exists
      any_of:               # non-empty list; the item meets the target when its enchantment is any one of them
        - "8% increased Explicit Life Modifier magnitudes"   # an enchantment by its exact English stat text (a two-line
                            # text joins its lines with a newline), by its game-data mod id, or
        - Life              # by a bare tag: the clean enchants of that tag (a positive magnitude on it, no socket rider,
                            # no downside). An enchant with a rider or a downside is named by its own text or id.
                            # The extra crafted slot ("Can have 1 additional Crafted Modifier") can be reached only by a
                            # start item that already holds it; no orb is planned for it (ADR-0053).
    start_item:             # optional; absent means a fresh normal item of the base, level and influence
      rarity: rare          # normal, magic or rare; default rare when mods are given, else normal
      corrupted: false      # optional
      mods:                 # optional; each mod by its game-data id, tier taken as written
        - mod: LightningResist2
          tier: 3           # whole number >= 1, stored as written (tier derivation is not built yet)
          values: [14]      # one whole number per stat; a bare number is allowed for one stat
          fractured: true   # optional; `crafted` is optional too
      implicits:            # optional; the implicits the item starts with (none are filled in from the base)
        - mod: AvoidShockEldritchImplicit3
          values: [40]      # one whole number per stat; a bare number is allowed for one stat
          grade: 3          # optional: 0 for a base implicit, 1 to 6 for an Eldritch one; taken from the mod if left out
      quality:              # optional: catalyst quality of the start item, `type` and `percent` (0 to 20); on a weapon or armour
        type: intrinsic     # the plain quality, `percent` alone (0 to 30, a random drop reaches 30)
        percent: 20
      sockets:              # optional (ADR-0046): a weapon or armour; at least one of the three keys
        colours: [R, G, B, W]   # one colour per socket in socket order: W, R, G or B (or white, red, green, blue)
        count: 4            # the number of sockets; all white when `colours` is left out; must agree with `colours`
        links: [3, 1]       # link group sizes in socket order, adding up to the sockets; default: no links
      enchantment: ArmourEnchantmentHeistLifeEffect1   # optional: the enchantment the item starts with, a mod id or its exact stat text
      veil_offer: [UnveiledPrefixLife1]   # optional: up to 3 mod ids offered for the one veiled placeholder in `mods`
      memory_strands: 57    # optional (ADR-0040): the Memory Strands count, a whole number from 0 to 100 (default 0); or a pasted item text
                            # holding the game's line "Memory Strands: 57". A start item with 1 or more turns the strand setting on.
    start_price: R12 start amulet   # optional: the name of the start item in the price file (what it costs to get)
    price_file: prices.json # optional path; a relative path counts from the target file's folder
    actions: [alteration-orb]  # optional: the kinds of actions the planner may use (default: every kind it offers by
                            # default); a name may also be the label of one action, e.g. "Essence of Insanity" (#70)
    item_level_floor: 84    # optional (ADR-0061): the lowest item level the planner may plan at; 1 to `item_level`. Without it the planner
                            # derives the floor from the tiers the requirements ask for (`floor.py`). It never goes below the derived one.
    tiers_top_at_item_level: true   # optional (ADR-0061): the tiers written are "the top tier at `item_level`", so the level is not lowered
    allow_corrupted: true   # optional (ADR-0036): a corrupted item may be the goal even with no corrupted implicit; without this key
                            # and without a `corrupted: true` implicit, a corrupted item is never a goal

Sockets (ADR-0046): a start item that states no sockets gets one white, unlinked socket when the target names `sockets:` (and none
otherwise); `Target.start_sockets_assumed` says so. A socket target is refused on jewellery and other classes with no socket
table, with a count, link size or colour total above the class maximum of the base (naming it), with links above count or colours
above links, on a corrupted start item and on an item with an Abyssal Socket (a start mod or implicit, or a requirement that can
give one). `Target.is_met_by` checks the sockets, the planner does not plan them yet.

Exactly one of `family` and `stat` names a requirement's mod. `stat` is compared after normalising both
sides (a range such as `(10-24)` becomes `#`, `[X|Y]` markup becomes `Y`), so `+# to maximum Life`
and `+(10-24) to maximum Life` are the same, and it selects every tier and variant of that text. `family`
selects every mod of the family. Rolls (`min_roll`, `values`) are the raw numbers of the game data, for
example life regeneration is per minute. A requirement on a roll compares the base roll the item
stores, so a guide's value shown with catalyst quality is written as the base roll (35 Strength shown as
42 with 20% quality, since 35 x 1.2 = 42) plus a `quality` entry. The stat text of an implicit is resolved
among implicits only, so "#% chance to Avoid being Shocked" under `implicits:` never picks the suffix of the
same text, and without `mod` it skips the "in your Presence" variants. A start mod of a veiled placeholder
(domain `veiled`) may leave out `tier` and `values`: tier 1 and the canonical seed are used. How a mod got on the item does not matter unless `not_crafted`
is set. The members of an `at_least` group are checked independently, so one mod can satisfy two of
them (say a family and a stat text that select the same mod); groups may nest 20 levels deep. Merge keys
(`<<`), anchors (`&name`) and aliases (`*name`) are not supported.
Whether a mod can spawn on the base is not checked here; that belongs to `actions`.

Corruption (ADR-0036): a corrupted implicit that the pool cannot give at `item_level`, more corrupted implicits than the corrupting
kinds of `actions:` give (`vaal` and `fossil-set` one, `locus` two; not checked when the target buys its item, that is when it names
a `start_price` or its start item is corrupted), two of one mod group (the Locus never draws them), more implicits in all than the item
holds after the corrupting action, and a corrupted start item under a target that neither asks nor allows are errors when the file
is read. `Target.is_met_by` is false for a corrupted item unless the target asks for a corrupted implicit or allows one.
"""

from pathlib import Path

from crafting_system.data import GameData

from .errors import TargetError
from .floor import (
    ItemLevelFloor,
    ItemLevelOptions,
    LevelGroup,
    NodeLevel,
    floor_of,
    item_level_options,
    level_groups,
    refusal_at,
    target_at_level,
)
from .model import (
    Condition,
    EnchantmentRequirement,
    ImplicitRequirement,
    KOfN,
    Node,
    PlainQualityRequirement,
    QualityRequirement,
    Requirement,
    SocketRequirement,
    Target,
)
from .parse import parse_target_text

__all__ = [
    "Condition",
    "EnchantmentRequirement",
    "ImplicitRequirement",
    "ItemLevelFloor",
    "ItemLevelOptions",
    "KOfN",
    "LevelGroup",
    "NodeLevel",
    "Node",
    "PlainQualityRequirement",
    "QualityRequirement",
    "Requirement",
    "SocketRequirement",
    "Target",
    "TargetError",
    "floor_of",
    "item_level_options",
    "level_groups",
    "load_target",
    "parse_target",
    "refusal_at",
    "target_at_level",
]


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
