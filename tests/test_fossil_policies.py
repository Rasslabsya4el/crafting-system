"""Exact checks for the bounded caller-selected fossil spam policy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from craftoracle.actions import ActionData
import craftoracle.fossil_policies as fossil_policies
import craftoracle.policies as fixed
from craftoracle.distributions import OutcomeClass
from craftoracle.fossil_policies import fossil_spam_p90, fossil_spam_policy
from craftoracle.plan_inputs import Loadout


def _mod(mod_id, group, weight, tags=()):
    return {
        "id": mod_id, "type": "Prefix", "group": group, "level": 1,
        "weightKey": ["default"], "weightVal": [weight], "modTags": list(tags),
        "source_path": "ModExplicit.lua",
    }


def _data() -> ActionData:
    return ActionData(
        {"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        {"A": _mod("A", "A", 1, ("fire",)), "B": _mod("B", "B", 1, ("cold",)), "C": _mod("C", "C", 2)},
        {}, {}, {"magic_caps": [1, 1], "rare_caps": [3, 3], "magic_count_weights": {"1": 1}, "rare_count_weights": {"1": 1}},
    )


def _spec():
    return SimpleNamespace(
        base="Base", item_level=1, flags={}, labels={"A": "A"}, tier_ids={}, required_mods=(), any_of=(), value_table=None, threshold=None,
        matches=lambda outcome: "A" in outcome.labels,
        utility=lambda outcome: float("A" in outcome.labels),
    )


def _loadout(*, actions=frozenset({"alchemy", "fossil"}), fossils=frozenset({13, 14}), values=None):
    prices = {"alchemy": 2.0, "fossil:1": 1.0, "fossil:12": 1.0, "fossil:13": 1.0, "fossil:14": 1.0, "resonator:1": 1.0, "resonator:2": 2.0, "resonator:3": 3.0, "resonator:4": 4.0}
    if values is not None:
        prices = values
    return Loadout(1, "fixture", actions, frozenset(), frozenset(), __import__("pathlib").Path("prices.json"), 100.0, 0.0, "c", prices, {}, "invented", ("fixture",), fossils)


def test_design_quantiles_match_the_documented_early_alchemy_mixture() -> None:
    # docs/design/family-policies.md: a=.25, p=.5, A=2, c=3, B=0.
    assert fossil_spam_p90(.25, .5, 2.0, 3.0) == pytest.approx(11.0)
    assert fossil_spam_p90(1.0, .5, 2.0, 3.0) == pytest.approx(2.0)
    assert fossil_spam_p90(0.0, .5, 2.0, 3.0) == pytest.approx(14.0)


def test_design_means_and_p90_are_real_policy_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    alchemy = {OutcomeClass(("A",), 1, 0): .25, OutcomeClass((), 0, 0): .75}
    fossils = {OutcomeClass(("A",), 1, 0): .5, OutcomeClass((), 0, 0): .5}
    monkeypatch.setattr(fixed, "_action_distribution", lambda *_args, **_kwargs: alchemy)
    monkeypatch.setattr(fossil_policies, "_fossil_distribution", lambda *_args: fossils)
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13}), values={**_loadout().values, "alchemy": 2.0, "fossil:13": 2.0, "resonator:1": 1.0}), _data(), {})
    assert policy["expected_cost"] == pytest.approx(6.5)
    assert policy["cost_p90"] == pytest.approx(11.0)

    no_early = {OutcomeClass((), 0, 0): 1.0}
    monkeypatch.setattr(fixed, "_action_distribution", lambda *_args, **_kwargs: no_early)
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13}), values={**_loadout().values, "alchemy": 2.0, "fossil:13": 2.0, "resonator:1": 1.0}), _data(), {})
    assert policy["expected_cost"] == pytest.approx(8.0)
    assert policy["cost_p90"] == pytest.approx(14.0)


def test_policy_prices_full_recipe_selects_cheapest_mean_and_keeps_terminal_mixture() -> None:
    policy = fossil_spam_policy(_spec(), _loadout(), _data(), {})

    assert policy["parameters"]["fossil_ids"] == [13]
    assert policy["candidate_count"] == 3
    assert policy["selected_recipe_price"] == pytest.approx(2.0)
    assert policy["expected_cost"] == pytest.approx(3.8)
    assert policy["expected_resonators"] == pytest.approx(.9)
    assert sum(row["probability"] for row in policy["terminal_distribution"]) == pytest.approx(1.0)
    assert policy["stages"][0]["probability"] == pytest.approx(.25)
    assert policy["stages"][1]["probability"] == pytest.approx(5 / 6)
    assert {tuple(row["parameters"]["fossil_ids"]) for row in policy["parameter_audit"]} == {(13,), (14,), (13, 14)}


def test_missing_permission_or_price_is_explicit_in_the_candidate_audit() -> None:
    denied = fossil_spam_policy(_spec(), _loadout(actions=frozenset({"alchemy"})), _data(), {})
    assert denied["reasons"] == ["loadout does not permit required actions"]

    missing = fossil_spam_policy(_spec(), _loadout(values={"alchemy": 2.0}), _data(), {})
    assert all("missing price" in row["unavailable_reason"] for row in missing["parameter_audit"])

    no_alchemy = fossil_spam_policy(_spec(), _loadout(values={"fossil:13": 1.0}), _data(), {})
    assert no_alchemy["reasons"] == ["missing price for currency: alchemy"]


def test_guaranteed_alchemy_skips_a_zero_probability_fossil_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    data = ActionData(
        {"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        {"A": _mod("A", "A", 1, ("fire",))}, {}, {},
        {"magic_caps": [1, 1], "rare_caps": [3, 3], "magic_count_weights": {"1": 1}, "rare_count_weights": {"1": 1}},
    )
    monkeypatch.setattr(fossil_policies, "_fossil_distribution", lambda *_args: (_ for _ in ()).throw(AssertionError("must not evaluate fossil tail")))
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13})), data, {})
    assert policy["expected_cost"] == pytest.approx(2.0)
    assert policy["cost_p90"] == pytest.approx(2.0)
    assert policy["expected_resonators"] == 0
    assert len(policy["stages"]) == 1


def test_zero_fossil_probability_is_unavailable_unless_alchemy_is_guaranteed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fossil_policies, "_fossil_distribution", lambda *_args: {OutcomeClass((), 0, 0): 1.0})
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13})), _data(), {})
    assert policy["reasons"] == ["no permitted fossil recipe can complete the target"]
    assert policy["parameter_audit"][0]["unavailable_reason"] == "target probability is zero"


def test_zero_recipe_price_has_the_deterministic_setup_quantile() -> None:
    prices = {**_loadout().values, "fossil:13": 0.0, "resonator:1": 0.0}
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13}), values=prices), _data(), {})
    assert policy["expected_cost"] == pytest.approx(2.0)
    assert policy["cost_p90"] == pytest.approx(2.0)


def test_all_fifteen_subsets_have_full_recipe_prices_by_socket_count() -> None:
    policy = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({1, 12, 13, 14})), _data(), {})
    prices = {}
    for row in policy["parameter_audit"]:
        prices.setdefault(len(row["parameters"]["fossil_ids"]), set()).add(row["recipe_price"])
    assert policy["candidate_count"] == 15
    assert prices == {1: {2.0}, 2: {4.0}, 3: {6.0}, 4: {8.0}}


def test_completion_mixture_keeps_distinct_labels_and_conditional_utility() -> None:
    spec = SimpleNamespace(
        value_table={"A": {1: 60.0}, "B": {1: 100.0}}, threshold=1.0,
        utility=lambda outcome: 60.0 if "A:1" in outcome.labels else 100.0 if "B:1" in outcome.labels else 0.0,
    )
    spec.matches = lambda outcome: spec.utility(outcome) >= spec.threshold
    alchemy = {OutcomeClass(("A:1",), 1, 0): .25, OutcomeClass((), 0, 0): .75}
    fossils = {OutcomeClass(("B:1",), 1, 0): .5, OutcomeClass((), 0, 0): .5}
    terminal = fossil_policies._completion_mixture(spec, alchemy, .25, fossils)
    assert terminal == {OutcomeClass(("A:1",), 1, 0): pytest.approx(.25), OutcomeClass(("B:1",), 1, 0): pytest.approx(.75)}
    assert fixed._conditional_expected_utility(spec, terminal) == pytest.approx(90.0)


def test_cache_reuses_raw_distribution_across_prices_and_invalidates_mutated_pool() -> None:
    data = _data()
    cache: dict = {}
    first = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13})), data, cache)
    second = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13}), values={**_loadout().values, "fossil:13": 9.0}), data, cache)
    first_size = len(cache)
    data.mods["C"]["weightVal"][0] = 100
    third = fossil_spam_policy(_spec(), _loadout(fossils=frozenset({13})), data, cache)
    assert first["stages"][-1]["probability"] == second["stages"][-1]["probability"]
    assert second["selected_recipe_price"] == pytest.approx(10.0)
    assert len(cache) == first_size + 2
    assert third["stages"][-1]["probability"] != first["stages"][-1]["probability"]


def test_cache_reuses_raw_distribution_across_changed_target_thresholds() -> None:
    data = _data()
    cache: dict = {}
    first = _spec()
    first.value_table = {"A": {1: 1.0}}
    first.threshold = 1.0
    first.utility = lambda outcome: float("A" in outcome.labels)
    first.matches = lambda outcome: first.utility(outcome) >= first.threshold
    fossil_spam_policy(first, _loadout(fossils=frozenset({13})), data, cache)
    changed = _spec()
    changed.value_table = {"A": {1: 1.0}}
    changed.threshold = 2.0
    changed.utility = lambda outcome: float("A" in outcome.labels)
    changed.matches = lambda outcome: changed.utility(outcome) >= changed.threshold
    second = fossil_spam_policy(changed, _loadout(fossils=frozenset({13})), data, cache)
    assert second["reasons"] == ["no permitted fossil recipe can complete the target"]
    assert len(cache) == 2


def test_work_limit_never_ranks_a_partial_subset_search(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((0.0, 1.0))
    monkeypatch.setattr(fossil_policies.time, "monotonic", lambda: next(ticks))
    policy = fossil_spam_policy(_spec(), _loadout(), _data(), {}, deadline=.5)
    assert policy["reasons"] == ["work limit"]
    assert policy["optimization_status"] == {"complete": False, "reason": "work limit"}
    assert len(policy["parameter_audit"]) == 3
    assert policy["parameter_audit"][0]["parameters"]["fossil_ids"] == [13]
    assert all(row.get("unavailable_reason") == "work limit" for row in policy["parameter_audit"][1:])


def test_work_limit_before_the_first_candidate_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fossil_policies.time, "monotonic", lambda: 1.0)
    policy = fossil_spam_policy(_spec(), _loadout(), _data(), {}, deadline=.5)
    assert policy["reasons"] == ["work limit"]
    assert all(row.get("unavailable_reason") == "work limit" for row in policy["parameter_audit"])
