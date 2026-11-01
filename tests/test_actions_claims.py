"""`Action.claims` (ticket #143, ADR-0028): the registry claims an action reads, by default those its module holds."""

import dataclasses
import datetime
from collections.abc import Mapping

from crafting_system.actions import Action, ChaosOrb
from crafting_system.cli._offers import BuyStartItem
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.rules import Rule, SourceKind


def _rule(rule_id: str) -> Rule:
    return Rule(
        id=rule_id,
        statement="A toy claim.",
        source_kind=SourceKind.OWNER,
        url="https://example.org/toy",
        quote="A toy claim.",
        patch_verified="3.29.3.3",
        date_checked=datetime.date(2026, 11, 1),
    )


TOY_ONE = _rule("toy.one")
TOY_TWO = _rule("toy.two")
NOT_A_RULE = "toy.three"  # a string that looks like an id is not a claim


@dataclasses.dataclass(frozen=True)
class ToyAction(Action):
    def label(self, data: GameData | None = None) -> str:
        return "Toy"

    def outcomes(self, data: GameData, item: Item):  # noqa: ANN201
        raise NotImplementedError

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}


@dataclasses.dataclass(frozen=True)
class OverridingToy(ToyAction):
    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset({TOY_TWO.id})


def test_the_default_is_the_rules_held_by_the_module_of_the_class():
    assert ToyAction().claims() == {"toy.one", "toy.two"}


def test_an_override_wins():
    assert OverridingToy().claims() == {"toy.two"}


def test_the_data_argument_is_optional_and_ignored():
    assert ToyAction().claims(None) == ToyAction().claims()


def test_a_chaos_orb_reports_the_four_claims_of_its_module():
    assert ChaosOrb().claims() == {
        "chaos_orb.accepts_rare_only",
        "chaos_orb.rerolls_all_mods",
        "chaos_orb.refused_on_corrupted",
        "chaos_orb.cost",
    }


def test_the_restart_reads_no_claim():
    assert BuyStartItem(None).claims() == frozenset()  # type: ignore[arg-type]
