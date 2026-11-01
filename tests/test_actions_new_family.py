"""A new action family edits no shared file (ticket #334): a toy family in this one module is registered, documented and run by the shared suites.

The toy is an armour-only kind that removes one mod of a helmet at random, refuses an Eldritch implicit, and declares what it
reads. Everything it needs, it brings itself:

* the kind, with `applies_only_to` and `reads_item_state_while_not_planner` (its exemptions are declarations on the kind);
* a fixture item, registered with `contract_registry` (a family's `tests/contract_fixtures_<family>.py` does this in a real family);
* the docs, in the docstring of its own module; and a module added to `crafting_system.actions` is exported by its `__all__`.

The shared tests (`test_actions_contract.py`, `test_actions_item_state.py`) and the files that used to be edited per family
(`actions/__init__.py`, `contract_support.py`) name no kind. The functions they run are called here with the toy registered.
"""

import dataclasses
import pkgutil
import sys
from fractions import Fraction

import pytest
from contract_fixtures_influence import contract_helmet_data
from contract_registry import extra_item_registered, load_family_fixtures
from contract_support import (
    check_action,
    check_every_kind_applies_on_some_fixture_item,
    contract_pairs,
    extra_fixture_items,
    extra_pairs,
)
from influence_support import PLAIN, S1
from influence_support import helmet as contract_helmet
from influence_support import roll as roll_on_helmet
from item_state_support import check_kinds_declare_item_state

import crafting_system.actions as actions
from crafting_system.actions import Action, Adds, Finite, Kind, NotApplicableError, Reads, kinds, registered
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity

TOY = "toy-armour-polish"
TOY_ITEM = "toy_helmet"


@dataclasses.dataclass(frozen=True)
class ToyPolish(Action):
    """Removes one mod, each with the same chance, from an armour item with no Eldritch implicit; the rarity stays."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Polish"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Polish Orb": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), implicits=True)  # refused on an Eldritch implicit

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal()

    def outcomes(self, data: GameData, item: Item) -> Finite:
        base = data.base_items.get(item.base_id)
        if base is None or base.item_class != "Helmet":
            raise NotApplicableError("the toy works on a helmet only")
        if item.rarity is not Rarity.RARE or item.eldritch_implicits(data):
            raise NotApplicableError("the toy works on a rare item with no Eldritch implicit")
        removable = [entry for entry in item.mods if not entry.fractured]
        if not removable:
            raise NotApplicableError("the item holds no mod to remove")
        chance = Fraction(1, len(removable))
        results = tuple((chance, item.changed(data, mods=tuple(e for e in item.mods if e is not gone))) for gone in removable)
        return Finite(data, item, results)


def toy_members(data: GameData, item: Item):
    yield ToyPolish()


TOY_KIND = Kind(TOY, toy_members, order=900, planner=False, why_not="a toy", applies_only_to="armour", reads_item_state_while_not_planner="implicits")


@pytest.fixture
def toy_family():
    """The toy kind and its fixture item registered for a test and taken out after it; no shared file is edited."""
    load_family_fixtures()
    item = lambda: contract_helmet(roll_on_helmet(PLAIN, 1), roll_on_helmet(S1, 2))  # noqa: E731
    with registered(TOY_KIND), extra_item_registered(TOY_ITEM, (TOY,), contract_helmet_data, item):
        yield


def test_the_toy_is_registered_and_its_fixture_is_found_by_the_suite(toy_family):
    assert TOY in {entry.name for entry in kinds()}
    assert TOY_ITEM in extra_fixture_items()
    assert {kind for kind, _, _ in extra_pairs()} >= {TOY, "orb-of-dominance", "influenced-exalted-orb"}


def test_the_toy_is_gone_with_its_registration():
    assert TOY not in {entry.name for entry in kinds()} and TOY_ITEM not in extra_fixture_items()


def test_the_contract_suite_runs_the_toy_on_its_fixture_and_exempts_it_by_its_declaration(toy_family):
    pairs = [(kind, action, name) for kind, action, name in extra_pairs() if kind == TOY]
    assert pairs
    for _, action, name in pairs:
        fixture = extra_fixture_items()[name]
        assert check_action(action, fixture.item, fixture.data)  # every check of `test_the_action_meets_the_contract`
    assert any(kind == TOY for kind, _, _ in contract_pairs())  # asked about the amulets too, and refused there
    assert TOY in check_every_kind_applies_on_some_fixture_item()  # it applies on its helmet; on an amulet it must not


def test_the_item_state_suite_checks_what_the_toy_declares_about_the_implicits(toy_family):
    assert check_kinds_declare_item_state() == len(kinds())
    wrong = dataclasses.replace(TOY_KIND, reads_item_state_while_not_planner="quality")
    with registered(dataclasses.replace(wrong, name="toy-wrong")):
        with pytest.raises(AssertionError):
            check_kinds_declare_item_state()


def test_an_armour_only_declaration_that_is_false_is_caught(toy_family):
    class Everywhere(ToyPolish):
        def outcomes(self, data, item):
            return Finite(data, item, ((Fraction(1), item),))

    def everywhere(data, item):
        yield Everywhere()

    with registered(Kind("toy-everywhere", everywhere, order=901, applies_only_to="armour")):
        with pytest.raises(AssertionError, match="applies_only_to"):
            check_every_kind_applies_on_some_fixture_item()


def test_every_kind_is_run_by_the_contract_suite_unless_it_declares_a_class():
    covered = {kind for kind, _, _ in contract_pairs()} | {kind for kind, _, _ in extra_pairs()}
    limited = {entry.name for entry in kinds() if entry.applies_only_to}
    assert covered | limited == {entry.name for entry in kinds()}


def test_every_module_of_actions_documents_itself():
    missing = [
        info.name
        for info in pkgutil.iter_modules(actions.__path__)
        if not (getattr(sys.modules[f"{actions.__name__}.{info.name}"], "__doc__", "") or "").strip()
    ]
    assert not missing, f"a module of actions has no docstring (the docs of a family live there): {missing}"
    for family in ("eldritch", "influence", "bench", "fossil", "metamods", "divine"):
        assert len(sys.modules[f"{actions.__name__}.{family}"].__doc__) > 400, family  # the family's docs moved in, not out


def test_the_index_of_actions_does_not_name_a_family():
    index = actions.__doc__
    for family_class in ("EldritchImplicitCurrency", "InfluencedExaltedOrb", "BenchCraft", "ApplyFossils", "DivineOrb"):
        assert family_class not in index, family_class


def test_a_module_added_to_actions_is_exported_by_its_all(tmp_path, monkeypatch):
    (tmp_path / "toy_family_module.py").write_text('"""A toy family: its docs live here."""\n\n__all__ = ["ToyExport"]\n\nToyExport = 42\n')
    monkeypatch.setattr(actions, "__path__", [*actions.__path__, str(tmp_path)])
    monkeypatch.setattr(actions, "__all__", list(actions.__all__))
    monkeypatch.setattr(actions, "ToyExport", None, raising=False)
    monkeypatch.delitem(sys.modules, f"{actions.__name__}.toy_family_module", raising=False)
    before = set(actions.__all__)
    actions._export_modules()
    try:
        assert actions.ToyExport == 42 and set(actions.__all__) == before | {"ToyExport"}
        assert sys.modules[f"{actions.__name__}.toy_family_module"].__doc__.startswith("A toy family")
    finally:
        sys.modules.pop(f"{actions.__name__}.toy_family_module", None)
