# Twelve modules, each depending only on those listed before it

The code splits into twelve modules (eleven until the amendment below); each may depend only on modules listed before it:

1. `data`: fetch, pin and normalize repoe-fork; knows nothing of crafting.
2. `rules`: the registry of admitted mechanics with provenance (ADR-0004).
3. `items`: the concrete item.
4. `actions`: primitives, each with its exact outcome distribution and sampling on a concrete item.
5. `abstraction`: design D, compression, family types, pool signatures, the cached kernel (ADR-0009).
6. `solver`: the stochastic shortest path; branching in B3 (ADR-0010, ADR-0011).
7. `risk`: metrics of a fixed policy (ADR-0006).
8. `simulator`: runs a policy on concrete items (ADR-0019).
9. `prices`: the price file and its fetchers (ADR-0007).
10. `targets`: the YAML target and the goal check (ADR-0008).
11. `planner`: a target, prices and settings in, a plan out (the amendment below).
12. `report` / `cli` (ADR-0015).

Origin: [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q18.

## Amendment: the planner is a module of its own, the twelfth ([#880](https://github.com/Rasslabsya4el/crafting-system/issues/880), owner's direction of 2026-11-13)

The eleven modules had no place for planning itself. `make_plan` and everything under it (choosing a start, collecting and pricing the offers, picking how to search, the searches, their bounds, the socket finish, Hinekora's Lock, second items, the limits of an answer) grew inside `cli`, next to the code that parses arguments and prints: about 10,000 of its 17,000 lines. Two things made that a cost. The website of the direction of 2026-11-13 needs one thing to call that is not a command line. And the speed work rewrites exactly this code, so doing it inside `cli` would have meant moving it twice.

So planning is the module `planner`, between `targets` and `cli`:

- It has **one entry**, `plan_target(data, target, prices, settings)`, which returns a `Plan`. It loads no file, reads no date and prints nothing; the caller loads the game data, the target and the prices and gives the day and the limits of the run in the settings. The planner times its own stages against those limits and takes the number of worker processes from the shared `parallel` module; nothing else of the machine reaches a plan.
- It may import every module before it. It never imports `cli`.
- `cli` keeps the command line, the text report and the JSON policy, the route page with its own maths, given routes, `--verify` and the benchmark command. It imports the planner **only through its public names**, each by `from crafting_system.planner import name` (never a file inside it, and never the module object, through which a private file could be reached); `tests/test_layering.py` checks both the order and this. The list of public names is wider than the entry today, because `cli` still evaluates a given route on a plan's graph and tests still call the steps under the entry by name; [#883](https://github.com/Rasslabsya4el/crafting-system/issues/883) shrinks it.
- The move changed no behaviour: no recorded number, fixture or page changed with it. The solve paths, the shape of `Plan` and the place of the envelope search (still in `planner`, not in `solver`) are as they were; the tickets after #880 change those.

One seam is left open by the move and is [#882](https://github.com/Rasslabsya4el/crafting-system/issues/882): a finished plan lists what the route page cannot show of it (the reach chance of a state, the numbers of a step), and that maths is the page's and stays in `cli`. The planner may not import it, so `cli` names the function to the planner when it is imported (`planner.present_with`), and a plan finished with no presenter named is an error, never a plan with fewer limits.

### Considered options

- **Leave planning in `cli` and give it a public function there.** Rejected: the website would import the command line to plan, and nothing would stop presentation code and planning code from reading each other's private parts, which is how they grew together.
- **Put planning into `solver`.** Rejected: `solver` is generic and knows nothing of Path of Exile (`tests/test_solver_independence.py`), and planning reads `prices` and `targets`, which come after it.
- **Move the page's maths into the planner with the rest.** Rejected for this step: it is presentation, it is large, and it gets its own ticket; the seam above is the price.
