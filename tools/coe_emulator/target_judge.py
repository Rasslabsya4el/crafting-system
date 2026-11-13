"""The planner's reading of a finished item against a target file, for the emulator checks (ticket #617).

    from target_judge import TargetJudge
    TargetJudge(data, "examples/targets/r08-energy-shield-boots.yaml").reading(["LocalIncreasedEnergyShieldPercent7_", ...])  # "goal", "short" or "other"

It is the joint "the target is met" count of `record.py` and `compare.py`: the item is the target (`goal`), or one sure bench craft short of it
(`short`: R08's top Energy Shield with an open prefix, whose Movement Speed the guide and the planner both craft at the bench), judged by
`crafting_system.cli._benchmark_use.reading_of`, the same function the review row of `benchmark` uses for the odds of one use. The plan is not solved;
the prices only make the offers exist, so the committed snapshot is used, or the price file the target names (V01, as `benchmark` reads it, #637).
The finished item is judged at the rarity the case was recorded at (`rarity`), which is not the start item's when the action is used later in the
craft (#637: an Exalted Orb on a rare helmet whose start item is a Normal one); without it, the start item's.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent

PRICES = "tests/fixtures/prices/routes-allflame-2026-07-31.json"  # the committed snapshot: it prices every offer the plan lists


class TargetJudge:
    """The reading of a finished item against a target file: `goal`, `short` (one sure bench craft short of it) or `other`."""

    def __init__(self, data, target_file: str, rarity: str | None = None) -> None:
        from crafting_system.cli._benchmark_use import sure_steps
        from crafting_system.planner._plan import make_plan
        from crafting_system.prices import load_price_file
        from crafting_system.targets import load_target

        root = HERE.parents[1]
        self.data = data
        self.target = load_target(root / target_file, data)
        prices = self.target.price_file if self.target.price_file is not None else root / PRICES
        self.plan = make_plan(data, self.target, load_price_file(prices), solve_it=False)
        self.rarity = rarity
        self.steps = sure_steps(self.plan)

    def reading(self, mod_ids: list[str]) -> str:
        from crafting_system.cli._benchmark_use import reading_of
        from crafting_system.items import ExplicitMod, Rarity

        mods = []
        for mod_id in mod_ids:
            mod = self.data.mods[mod_id]
            mods.append(ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in mod.stats), crafted=mod.domain == "crafted"))
        fields = {"mods": tuple(mods)} if self.rarity is None else {"mods": tuple(mods), "rarity": Rarity(self.rarity)}
        item = self.target.start_item.changed(self.data, **fields)
        return reading_of(self.plan, self.plan.abstraction.compress(item), self.steps)
