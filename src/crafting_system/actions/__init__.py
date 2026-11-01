"""Primitives, each with its exact outcome distribution and sampling on a concrete item. May import only: data, rules, items.

Every action subclasses `Action` (`contract.py`) and answers the questions of the contract: `label`, `outcomes`, `resources`,
`reads` and `adds`, and, when it needs them, `inputs` and `rule_axes`. A module registers its kinds with the `kind` decorator
(`catalog.py`), so a new method is one file and nothing outside `actions` imports a concrete action: `abstraction`, `cli` and
`simulator` use the contract and the catalog only. See ADR-0024 (extending to new methods and patches).

**This index does not change when a family is added** (ticket #334). Every module of this package is imported in sorted order and
the names in its `__all__` are exported here, so the public names stay importable from `crafting_system.actions`. The documentation
of a family is the docstring of its own module; read `help(crafting_system.actions.<module>)`:

* `contract`: the contract, the two-item actions and the rule axes; `catalog`: kinds and their declarations (`planner`,
  `opt_in`, `corrupting`, `applies_only_to`, `reads_item_state_while_not_planner`);
* `errors`: the two refusals; `outcomes`, `finite`, `mixture`, `draw`, `pool`, `add`, `rolls`: what an action returns and how it draws;
* one module per family of actions: `chaos`, `harvest*`, `essence`, `bench`, `fossil`, `magic`, `alchemy`, `exalted`, `annul`,
  `fracture`, `scour`, `divine`, `metamods`, `beasts`, `beast_mods`, `influence`, `eldritch`, `corrupted_pool`, and the ones added since.
"""

from importlib import import_module as _import_module
from pkgutil import iter_modules as _iter_modules

__all__ = ["default_actions"]


def _export_modules() -> None:
    """Import every module of the package in sorted order and export the names of its `__all__` (idempotent)."""
    exported = set(__all__)
    for info in sorted(_iter_modules(__path__), key=lambda found: found.name):
        module = _import_module(f"{__name__}.{info.name}")
        for name in getattr(module, "__all__", ()):
            globals()[name] = getattr(module, name)
            exported.add(name)
    __all__[:] = sorted(exported)


_export_modules()


def default_actions() -> tuple[Action, ...]:  # `Action`, `ChaosOrb` and `HarvestReforge` are exported by `_export_modules`
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return (ChaosOrb(), HarvestReforge("lightning"))
