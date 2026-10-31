# Extending to new methods and patches

The owner requires flexibility across leagues ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81) Q11, 2026-10-31): new numbers in a league the same day, a changed rule of an existing method in a few hours, a brand-new method in one or two tickets, **without changes elsewhere in the system**. Until ticket [#108](https://github.com/Rasslabsya4el/crafting-system/issues/108) a new action touched `abstraction` (class lists and `isinstance` checks), `cli/_offers.py` (hand-wired offers and costs) and the cost rules of its own family. Now every action meets one contract, `actions` keeps a catalog, and everything else reads the contract.

## What each change touches

- **New numbers** (a weight, a price, a bench cost): the data pin (`data`, the patch-update skill) or the price file. No code.
- **A changed rule of an existing method**: its claim in `rules/claims/<family>.yaml` and, if the logic changes, the one action file and its tests. The cost of an orb or a reforge is a claim too (`chaos_orb.cost`, `harvest_reforge.lifeforce_cost`, ...), so a price-name change there is a claim edit; an essence, a fossil or a bench craft is priced under the name the game data gives it (`essence.cost`, `fossils.cost`, `bench_craft.option_cost`), so a new patch moves them with the data pin.
- **A brand-new method**: one file in `actions/` that subclasses `Action`, registers its kind with `@kind(...)`, and cites its claims; plus its tests. Nothing in `abstraction`, `cli` or `simulator` changes. A method that does not draw from a pool lists its results with `Finite`; one that draws uses `Outcomes`.

## The contract

An action answers five questions (`actions/contract.py`): `label(data)`, `outcomes(data, item)` (exact `distribution`, `chance_all` and `sample`, plus `components`, the mixture the kernel is built from), `resources(data)`, `reads(data)` and `adds(data, item)`. `abstraction` builds the state from the `reads` of the enabled actions and the kernel from `outcomes` alone; `cli` builds its offers from the catalog, `resources` and `adds`; `simulator` samples `outcomes`. `tests/test_actions_no_concrete_imports.py` fails when a module outside `actions` names a concrete action class.

`reads` is the one declaration that must be right: an action that reads nothing of the other mods **erases** them, which is why a state need not store them. An action that declares nothing reads every mod and tells every family apart: exact, but the state count can blow up. A new method is therefore correct by default and fast by declaration.

## The catalog and the planner

Each module registers its kinds, with an order number and a `planner` flag. `catalog(data, item)` lists the actions that can apply to the item or to what a policy makes of it; `planner_only` leaves out the kinds the planner cannot use yet (fossil sets, the orbs of magic items, Orb of Scouring, Orb of Alchemy), each with its reason. A new kind is offered by default. The planner's filters are over declarations, not classes: an action that only adds named crafted mods is offered when a mod it adds counts toward the target (the #60 rule), and an action that needs a crafted mod (`Reads.needs_crafted`) is offered when the start item holds one or another offered action adds one. Pruning for speed (#118) is a further filter over `adds` and `reads`; the claim history (#120) reads the claims.

## Verification

`tests/contract_support.py` runs on every kind of the catalog without being edited: outcomes sum to one; the finished items listed from `components` give each mod the chance `chance_all` says; the sampler follows it within five standard errors; the kernel equals the brute force on the compressed finished items (layer 1, ADR-0019); what an action declares agrees with what it does; its resources price an offer from a fixture price file; its label round-trips through a given route. A toy action defined only in `tests/test_actions_toy.py` is offered by the CLI, gets exact kernels, runs in the simulator and passes the same checks, which is the test that the contract is enough.

## Rejected

- A `typing.Protocol` alone: a new method could forget `reads` and silently be wrong. The base class gives the safe defaults.
- Kernel dispatch on the kind of outcome (a bench result, a resonator result): every new shape would need a kernel edit. The kernel reads the mixture of parts (`Fixed` or a pool draw) that every outcome exposes.
- The planner choosing actions by class or by a list in `cli`: the toy action would need an edit there.
