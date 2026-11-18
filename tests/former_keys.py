"""The methods the target files of the repo named in their `actions:` key before #405, and the suite's use of them.

Since #405 a target names no methods (OR-5, OR-13, OR-41): the parser refuses the key, the run's setting says which methods a plan may use
(`PlanSettings.methods`, `--methods`), and a plan of these targets outside the suite (the command, the heavy benchmark, the site) offers
every beta method. The suite's tests of these routes were recorded with the key's methods, and with every method most of them give no plan
within CI's time and memory (as with the classic offers, `cli_support.CLASSIC_KINDS`). So the suite reads each of these files with the
methods its key named: `install` wraps the loader of target files (`crafting_system.targets.load_target`) for the whole session, and a
file listed here comes back planned with its former methods (`Target.actions`, as the planner's entry sets it from the setting). A test of
the default, every-method plan of one of these routes is the heavy benchmark's (#1109), or reads the file with `load_target_as_is`.

An entry leaves the list when the tests that plan its file pass with every method. Checked in #405's second PR: the two research targets
(research/218, research/312) left, since no test plans them (they are only parsed). The rest stay, because the tests that plan them are
too slow or too big with every method: the heavy benchmark's record of the site's plans (`tests/fixtures/heavy_benchmark/records.json`,
#1156) gives R04, R13, R14 and R24 no plan within the 10-minute net and R20 a plan of 35 million Chaos; the tests that plan J01, V01 and R07
did not finish in 2 minutes with every method; R06 (#516), R17 (#1182), the plain R08 and R09 (#1167) and the strand targets were not
re-checked; and the per-use cases of R08's and R09's top-tier boots (`test_coe_recorded_b1_core`) lose the sure bench step they pin.
Retiring the list is #1189.
"""

import dataclasses
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORMER_KEYS: dict[str, tuple[str, ...]] = {
    'docs/research/2026-11-01-strand-routes-files/targets/s01-es-ring-forum-guide.yaml': ('remembrance-orb', 'transmutation-orb', 'regal-orb', 'fossil-set', 'harvest-reforge', 'bench-craft', 'unravelling-orb'),
    'docs/research/2026-11-01-strand-routes-files/targets/s02-fire-res-ring-showcase.yaml': ('remembrance-orb', 'transmutation-orb', 'regal-orb', 'harvest-reforge', 'unravelling-orb'),
    'docs/research/2026-11-01-strand-routes-files/targets/s11-remembrance-belt.yaml': ('remembrance-orb', 'transmutation-orb', 'alteration-orb', 'augmentation-orb', 'regal-orb', 'bench-craft', 'remove-crafted-mods'),
    'docs/research/2026-11-01-strand-routes-files/targets/s13-unravelling-belt.yaml': ('unravelling-orb', 'transmutation-orb', 'alteration-orb', 'augmentation-orb', 'regal-orb', 'bench-craft', 'remove-crafted-mods'),
    'examples/targets/j01-cobalt-life-attack-speed.yaml': ('chaos-orb',),
    'examples/targets/r04-penetrating-quiver.yaml': ('Essence of Insanity', 'Deafening Essence of Rage', 'annulment-orb', 'fracturing-orb', 'exalted-orb', 'bench-craft', 'Bench craft Cannot roll Attack Modifiers', 'remove-crafted-mods'),
    'examples/targets/r06-strength-heavy-belt.yaml': ('Deafening Essence of Rage', 'annulment-orb', 'exalted-orb'),
    'examples/targets/r07-minion-wand.yaml': ('Fossils Corroded Fossil + Jagged Fossil + Metallic Fossil + Shuddering Fossil', 'annulment-orb', 'Bench craft Prefixes Cannot Be Changed', 'Bench craft Trigger a Socketed Spell when you Use a Skill, with a 8 second Cooldown / Spells Triggered this way have 150% more Cost', 'remove-crafted-mods', 'veiled-chaos-orb', 'unveil', 'pick'),
    'examples/targets/r08-energy-shield-boots.yaml': ('fossil-set', 'bench-craft'),
    'examples/targets/r09-life-boots.yaml': ('fossil-set', 'bench-craft'),
    'examples/targets/r13-life-resist-belt.yaml': ('alteration-orb', 'augmentation-orb', 'regal-orb', 'bench-craft', 'remove-crafted-mods'),
    'examples/targets/r14-hunter-bow.yaml': ('alteration-orb', 'augmentation-orb', 'regal-orb', 'annulment-orb', 'exalted-orb', 'bench-craft', 'Bench craft Can have up to 3 Crafted Modifiers', 'Bench craft Cannot roll Attack Modifiers', 'remove-crafted-mods'),
    'examples/targets/r17-lightning-talisman.yaml': ('transmutation-orb', 'alteration-orb', 'augmentation-orb', 'regal-orb', 'annulment-orb', 'imprint', 'restore', 'Harvest Add Remove Lightning', 'Bench craft Can have up to 3 Crafted Modifiers', 'Bench craft Prefixes Cannot Be Changed', 'Bench craft Cannot roll Attack Modifiers', 'remove-crafted-mods', 'exalted-orb', 'catalyst'),
    'examples/targets/r20-rf-helmet.yaml': ('Essence of Horror', 'annulment-orb', 'Bench craft Suffixes Cannot Be Changed', 'Harvest Reforge Fire', 'wild-bristle-matron', 'Harvest Reforge Influence'),
    'examples/targets/r24-avoid-shock-boots.yaml': ('Deafening Essence of Torment', 'annulment-orb', 'Harvest Add Remove Fire', 'Harvest Add Remove Cold', 'Harvest Add Remove Lightning', 'Bench craft Suffixes Cannot Be Changed', 'remove-crafted-mods', 'veiled-chaos-orb', 'unveil', 'pick'),
    'examples/targets/v01-minion-helmet.yaml': ('transmutation-orb', 'alteration-orb', 'augmentation-orb', 'regal-orb'),
    'tests/real_targets/r08-energy-shield-boots-top-tier.yaml': ('fossil-set', 'bench-craft'),
    'tests/real_targets/r09-life-boots-top-tier.yaml': ('fossil-set', 'bench-craft'),
}


def former_methods(path: Path | str) -> tuple[str, ...] | None:
    """The methods the key of the file at `path` named before #405, or None for a file that had no key."""
    try:
        relative = Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None
    return FORMER_KEYS.get(relative)


_AS_IS: list = []  # the loader before `install`


def install() -> None:
    """Read every file of `FORMER_KEYS` with its former methods, for the rest of the session (see the module text)."""
    import crafting_system.targets as targets

    if _AS_IS:
        return
    parse = targets.parse_target_text
    _AS_IS.append(parse)

    def parse_with_former_methods(text, data, source="target", *args, **kwargs):
        target = parse(text, data, source, *args, **kwargs)
        methods = former_methods(source)
        return target if methods is None else dataclasses.replace(target, actions=methods)

    targets.parse_target_text = parse_with_former_methods  # `load_target` reads it from its module: every importer of `load_target` sees it


def load_target_as_is(path: Path, data):
    """The target at `path` as the product reads it: no former methods (every beta method)."""
    import crafting_system.targets as targets

    return dataclasses.replace(targets.load_target(path, data), actions=None) if former_methods(path) is not None else targets.load_target(path, data)
