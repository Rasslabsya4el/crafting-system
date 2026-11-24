"""The guide's recorded figure of a target that is a reference craft, for a page built with no guide's route given (#1596, OR-59).

A reference craft (`_benchmark.REFERENCES`) names its target file and its guide's route file. When the route's rules do not finish on the
target (they have gaps), the route file records the guide's cost (`recorded_cost`), and the proof sentence compares the plan's cost with it,
said as recorded. A page built from a plan alone (the plain command with no `--route`, the `page` command with no `--route`, the website)
looks the target up among the reference crafts and says that figure too, so a plan dearer than its guide is never shown without saying so
(the owner's condition for showing R17 at all, 2026-11-24). The target matches when it states the same item as the reference's file: the
price file it names and the run's methods setting are not the item, so they are left out of the comparison.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from crafting_system.config import find_project_root
from crafting_system.data import DataError, GameData
from crafting_system.targets import Target, TargetError, load_target

from ._route import recorded_cost_of


def _item(target: Target) -> Target:
    return replace(target, price_file=None, actions=None)


def reference_guide(data: GameData, target: Target, root: Path | None = None) -> float | None:
    """The recorded guide's cost of the reference craft whose target states the same item as `target`, or None (no such reference, or its
    route records no figure because its rules finish: its cost is then the route's own, given with `--route`). `root` is the project root
    (default: the one this package is in); a reference whose files cannot be read there is passed over."""
    from ._benchmark import REFERENCES  # the list of the reference crafts lives with the benchmark, which imports the page code

    root = find_project_root() if root is None else root
    wanted = _item(target)
    for bench in REFERENCES:
        if bench.route is None:
            continue
        try:
            reference = load_target(root / bench.target, data)
        except (TargetError, DataError):  # a reference file this install cannot read: not this target
            continue
        if _item(reference) == wanted:
            return recorded_cost_of(root / bench.route)
    return None
