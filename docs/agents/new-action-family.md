# Adding an action family: where each thing goes (ticket #334)

A new family of actions edits **no file that another family's PR also edits**. Every piece goes in the family's own files.

| What | Where | What not to edit |
| --- | --- | --- |
| The action, its kind, its claims | `src/crafting_system/actions/<module>.py`, registered with `@kind(...)` | the catalog, `abstraction`, `cli`, `simulator` |
| The public names | a list `__all__ = [...]` in the module; `actions/__init__.py` imports every module in sorted order and exports each `__all__` | `actions/__init__.py` |
| The docs of the family | the docstring of the module itself (what the family does, its refusals, its tickets and ADRs) | `actions/__init__.py`, whose docstring is a short index that names no family |
| An exemption | a declaration on the kind: `applies_only_to="armour"` for a kind that works on one item class only (the contract suite then does not ask it on the amulets of the fixture and fails if it applies to one); `reads_item_state_while_not_planner="implicits"` (or `"quality"`, `"offer"`) for a kind outside the planner that reads that part of the item state (the item-state suite then expects the declaration) | `tests/test_actions_contract.py`, `tests/test_actions_item_state.py`: they name no kind |
| Mods the fixture pool lacks | a module `tests/contract_fixtures_<family>.py` that calls `register_fixture_mods(source)` from `tests/contract_registry.py`; `contract_support.py` collects them | `tests/contract_support.py` |
| An item on a base of its own (a helmet, boots) | the same module: `register_extra_item(name, kinds, data, item)`; the kinds named are asked about that item and no other kind | `tests/contract_support.py` |
| The family's own tests and support code | `tests/test_actions_<family>.py`, `tests/<family>_support.py` | |

A `contract_fixtures_*.py` module imports `contract_registry` and its own support code, never `contract_support` at its top (it is
loaded while `contract_support` builds the fixture data); `data` and `item` are functions run late and may import it.

`tests/test_actions_new_family.py` is the worked example: a toy family in one module is registered, documented and run by the contract
and item-state suites with no edit to the shared files. A kind registered in the catalog is found by `test_actions_contract.py` and
`test_actions_item_state.py` without being named in them.
