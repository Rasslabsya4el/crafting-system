# Crafting oracle (prototype)

Given a Path of Exile 1 item spec, the prototype evaluates its reviewed ordinary-currency policies from a white base and reports their odds, expected cost, p90 cost, decisions, and input assumptions.

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

`data/prices.example.json` contains invented chaos-equivalent prototype inputs, not trade prices. p90 is the 90th-percentile total cost, while an estimated p90 prints its DKW uncertainty interval, sample count, seed, and error bound. Results are exact only under the stated provisional ordinary-crafting assumptions; each plan prints those assumptions and the source notes from the selected inputs. Families outside the reviewed slice, including harvest, fossils, eldritch, awakened, recombinator, veiled, corruption, beast, catalyst, and other Q9-bound item states, remain explicitly blocked rather than estimated.

Start project work with `AGENTS.md`, then `docs/BRIEF.md` and `docs/STATE.md`.
