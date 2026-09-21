# Crafting oracle (prototype)

Given a Path of Exile 1 item spec, the prototype evaluates its reviewed ordinary-currency policies from a white base and reports their odds, expected cost, p90 cost, decisions, and input assumptions.

Generate readable, standalone Russian reports with fresh local validation evidence:

```powershell
python -m tools.collect_evidence --output-dir out/evidence
python -m craftoracle report examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --output-dir out/reports/helmet --evidence-dir out/evidence
python -m craftoracle report examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --output-dir out/reports/bow --evidence-dir out/evidence
```

Open `out/reports/helmet/index.html` or `out/reports/bow/index.html` in a browser.
No server or network is needed to read the report. Select a route to inspect its ordered
actions, stopping/restart rules, conditional probabilities and expected currency bill.
The report retains all candidates and provides the raw `plan.json`. Its evidence area
lists individual pytest cases, command logs and twelve offline Craft of Exile comparisons.
The ignored local PoB and CoE source snapshots are required to reproduce that evidence.
Missing evidence and evidence from another revision are explicitly labelled.

The example prices and bow utility points are invented inputs, not current market prices
or DPS. Mean cost is not a guaranteed budget. An estimated p90 is separate from its
uncertainty interval. Tests check the implementation and the documented model; the CoE
cases compare individual actions, not every complete multi-step route against the game.

From the repository root, run:

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json
```

Use `--json` for the same plan as JSON:

```powershell
python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json --json
```

Item files named `.yaml` accept the JSON-compatible YAML subset only: they are JSON documents with a `.yaml` extension. The bow example is a utility target, so its stopping threshold can be evaluated without changing its item target:

```powershell
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --threshold 100
```

Compare the documented utility stopping rules while retaining all policies and
marking their Pareto frontier:

```powershell
python -m craftoracle plan examples/bow_value_table.yaml --loadout data/loadouts/endgame.json --compare-thresholds 60,100 --json
```

`data/prices.example.json` contains invented chaos-equivalent prototype inputs, not trade prices. p90 is the 90th-percentile total cost, while an estimated p90 prints its DKW uncertainty interval, sample count, seed, and error bound. Results are exact only under the stated provisional ordinary-crafting assumptions; each plan prints those assumptions and the source notes from the selected inputs.

The default planner searches the documented finite choices within each template and prints
the selected parameters and candidate audit. Protected Exalt cycles try one, two or three
slams, with paid preparation after a full-prefix failure. Magic stage gates and early
stopping are part of the policy. This is a minimum-cost search within those grids, not a
global optimum over every possible crafting route. `policies.evaluate_fixed_policies`
retains the earlier fixed recipes for explicit benchmark comparisons.

Item level stays fixed unless `--item-level-range MIN:MAX` is supplied. The optional search
uses distinct eligible PoB pools, keeps the target tier IDs and holds the supplied base
price constant. An incomplete grid or level interval is reported explicitly. Combined
threshold searches keep separate level-search status for each stopping threshold.

The helmet plan includes protected-suffix Harvest Life with repeated lock costs and paid recovery after a full-prefix failure. Ordinary Harvest and 18 ordinary fossil types also have exact-distribution and seeded-sampling APIs. Harvest type blocking uses an explicit `first_only` model; `all_draws` is a sensitivity option while that narrower rule remains unresolved. Fossil positive factors use the owner's selected CoE additive model; multiplicative sensitivity remains available. Unsupported special recipes and item states raise an explicit error. Current exact recombination, Awakener conflict selection, unequal-tier Conflict, veiled offers, corruption and beast replacement rules retain the specific research gates in `docs/OPEN_QUESTIONS.md`.

The fossil policy compares every nonempty subset of the loadout's optional `allowed_fossils`
list (at most four supported IDs). Price each fossil with `fossil:<id>` and the whole
resonator with `resonator:<socket_count>`. It first tries Alchemy, stops on success, then
repeats the chosen full Chaotic recipe. The default four-fossil domain has15 combinations.
For the bow's invented utility thresholds60/100, Scorched is selected with mean costs
162.38/9739.88 and exact p90 costs372.5/22426.5. Full comparisons and limitations are in
`docs/research/goal2-results.md`.

`fracturing.fracture_distribution(item, data)` returns concrete item states for an ordinary
rare with at least four ordinary modifiers, including the selected `fractured_mod_id`.
`apply_fracturing(item, data, rng)` samples that same uniform CoE model directly. Basic
currency, Essence and Divine retain the identified fracture. For repeated roll samples,
prepare an immutable `actions.prepare_roll_plan(...)`, then call `sample_roll(plan, rng)`;
preparing a new plan reflects changed caller data. Fractured Harvest/fossil inputs remain
explicitly unsupported. A wrong fracture is a different resulting item, never a free retry.

The exact helmet demo also offers `fracture-life-envy`: prepare four modifiers including
Life9, fracture, then reroll with Deafening Envy. It pays for every replacement base after
a wrong fracture and compares early completion during Alchemy preparation. At the invented
Fracturing price1000, mean cost is4227.74 and estimated p90 is8744 [8500,9353.5]; direct
Envy remains cheaper. This template explicitly excludes other targets and item levels.

The twelve-case independent comparison against the frozen Craft of Exile calculator is documented in `docs/validation/coe_cases.md`. Reproduce it locally, with the ignored source cache present and no network requests:

```powershell
python -m tools.coe_validation
```

For ordinary jewellery quality finishing, provide the catalyst price in your chosen unit:

```powershell
python -m craftoracle quality --base "Paua Amulet" --item-level 86 --catalyst fertile --target-quality 20 --price 2 --json
```

The result gives exact distributions of application count, cost and final quality. At
ilvl86 the mean is14.42372357 applications and p90 is16; at the supplied price2, mean cost
is28.84744714 and p90 is32. This API covers quality/type state on ordinary jewellery;
modifier-magnitude valuation and special catalysts retain their documented limitations.

For bounded value-specific Divine outcomes, construct a `RolledItem` with one current integer value for each ranged affix. From the repository root, the reviewed Royal Burgonet example is:

```python
from pathlib import Path

from craftoracle.actions import load_action_data
from craftoracle.divine import RolledItem, divine_distribution
from craftoracle.item_model import ItemState, ModRef

data = load_action_data(Path.cwd())
life = ModRef("IncreasedLife9", "Prefix", "IncreasedLife")
chaos = ModRef("ChaosResist6", "Suffix", "ChaosResistance")
item = ItemState("Royal Burgonet", 86, "rare", (life, chaos))
rolled = RolledItem(item, (("IncreasedLife9", 130), ("ChaosResist6", 31)))
assert len(divine_distribution(rolled, data)) == 75
```

`divine_distribution(rolled, data)` enumerates at most 100,000 joint states. `apply_divine(rolled, data, rng=random.Random(seed))` remains available for reproducible samples beyond that bound. This API only accepts one inclusive integer range in one projected `stat_text` string per modifier; fixed numeric values, decimal values, and multi-stat shapes raise an explicit unsupported-shape error rather than being interpreted.

Start project work with `AGENTS.md`, then `docs/BRIEF.md` and `docs/STATE.md`.
