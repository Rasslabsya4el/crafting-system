"""Paid fracture-Life then Deafening Envy policy mathematics.

This is the bounded Royal Burgonet86 template documented in
``docs/design/family-policies.md``.  Fracture selection uses the accepted
concrete adapter from ``docs/mechanics/fracturing.md``; Envy's forced Chaos6
mapping comes from ``docs/mechanics/essences.md`` and PoB Essence.lua.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
import math

import numpy as np

from craftoracle.actions import ActionData, action_distribution, prepare_roll
from craftoracle.distributions import OutcomeClass, probability
from craftoracle.fracturing import fracture_distribution
from craftoracle.item_model import ItemState, ModRef
import craftoracle.policies as _fixed


_ENVY = "Metadata/Items/Currency/CurrencyEssenceEnvy3"
_LIFE = "IncreasedLife9"
_FRACTURE_DEMONSTRATION = (_LIFE, "ChaosResist6", "FireResist8", "ColdResist8")
_SAMPLES = 50_000
_SEED = 20260921
_CONFIDENCE = 0.99


@dataclass(frozen=True)
class FractureLifeMetrics:
    """Exact renewal moments for one selected early-stop choice."""

    mean_cost: float
    expected_bases: float
    expected_alchemies: float
    expected_scours: float
    expected_fracturings: float
    expected_envies: float
    wrong_fracture_risk_per_trial: float
    expected_discarded_bases: float
    irreversible_item_destruction_risk: float = 0.0


@dataclass(frozen=True)
class FractureLifeCostEstimate:
    """Seeded empirical p90 with its 99% DKW probability-space bracket."""

    mean_cost: float
    p90: float
    interval_lower: float
    interval_upper: float
    samples: int
    seed: int
    confidence: float
    dkw_epsilon: float
    sample_mean: float
    sample_standard_error: float
    method: str = "estimated-dkw-fracture-life-renewal-monte-carlo"


@dataclass(frozen=True)
class FractureLifeDistributions:
    """The three exact action distributions required by this template.

    ``preparation_probability`` is the four-mod Life9 gate excluding already
    complete outcomes.  The finishing distribution is terminal-only by
    design: Envy has discarded every non-fractured preparation identity.
    """

    preparation_distribution: Mapping[OutcomeClass, float]
    preparation_early_probability: float
    preparation_full_gate_probability: float
    preparation_probability: float
    fracture_probability: float
    finishing_distribution: Mapping[OutcomeClass, float]
    finishing_probability: float


def fracture_life_metrics(
    early_probability: float,
    preparation_probability: float,
    fracture_probability: float,
    finishing_probability: float,
    base_price: float,
    alchemy_price: float,
    scour_price: float,
    fracturing_price: float,
    envy_price: float,
) -> FractureLifeMetrics:
    """Evaluate the exact mean and action counts in the documented renewal law."""
    u, v, f, p = _inputs(
        early_probability, preparation_probability, fracture_probability, finishing_probability
    )
    base, alchemy, scour, fracturing, envy = (
        _nonnegative(value, name)
        for value, name in (
            (base_price, "base_price"), (alchemy_price, "alchemy_price"),
            (scour_price, "scour_price"), (fracturing_price, "fracturing_price"),
            (envy_price, "envy_price"),
        )
    )
    s, z = u + v, u + v * f
    if s == 0 or z == 0:
        raise ValueError("fracture-Life policy is unreachable")
    if v * f and p == 0:
        raise ValueError("fracture-Life finishing distribution has zero target probability")

    bases = s / z
    alchemies = 1 / z
    scours = (1 - s) / z
    fracturings = v / z
    envies = 0.0 if v * f == 0 else v * f / (z * p)
    numerator = s * base + alchemy + (1 - s) * scour + v * fracturing
    if v * f:
        numerator += v * f * envy / p
    mean = numerator / z
    return FractureLifeMetrics(
        mean,
        bases,
        alchemies,
        scours,
        fracturings,
        envies,
        1 - f,
        v * (1 - f) / z,
    )


def estimate_fracture_life_cost_p90(
    early_probability: float,
    preparation_probability: float,
    fracture_probability: float,
    finishing_probability: float,
    base_price: float,
    alchemy_price: float,
    scour_price: float,
    fracturing_price: float,
    envy_price: float,
    *,
    samples: int = _SAMPLES,
    seed: int = _SEED,
    confidence: float = _CONFIDENCE,
) -> FractureLifeCostEstimate:
    """Sample the documented finite random-variable cost law reproducibly."""
    metrics = fracture_life_metrics(
        early_probability, preparation_probability, fracture_probability, finishing_probability,
        base_price, alchemy_price, scour_price, fracturing_price, envy_price,
    )
    u, v, f, p = _inputs(
        early_probability, preparation_probability, fracture_probability, finishing_probability
    )
    count = _positive_integer(samples, "samples")
    parsed_seed = _integer(seed, "seed")
    coverage = _probability(confidence, "confidence")
    if coverage >= 1:
        raise ValueError("confidence must be in [0, 1)")
    epsilon = math.sqrt(math.log(2 / (1 - coverage)) / (2 * count))
    if epsilon >= 0.1:
        raise ValueError("samples are insufficient to bracket the 0.9 quantile")

    s, z = u + v, u + v * f
    rng = np.random.default_rng(parsed_seed)
    _validate_sampler_probability(s, "early_probability + preparation_probability")
    _validate_sampler_probability(z / s, "completion probability per prepared base")
    if v * f:
        _validate_sampler_probability(p, "finishing_probability")
    bases = rng.geometric(z / s, size=count)
    alchemies = rng.negative_binomial(bases, s) + bases
    if np.any(bases < 1) or np.any(alchemies < bases):
        raise ValueError("int64 Monte Carlo count overflow")
    fracture_finishes = rng.binomial(1, v * f / z, size=count)
    envy_counts = np.zeros(count, dtype=np.int64)
    finish_count = int(fracture_finishes.sum())
    if finish_count:
        envy_counts[fracture_finishes.astype(bool)] = rng.geometric(p, size=finish_count)
    if np.any(envy_counts < 0):
        raise ValueError("int64 Monte Carlo count overflow")
    costs = (
        base_price * bases
        + alchemy_price * alchemies
        + scour_price * (alchemies - bases)
        + fracturing_price * (bases - 1 + fracture_finishes)
        + envy_price * envy_counts
    )
    if not np.isfinite(costs).all():
        raise ValueError("fracture-Life cost samples are not finite")
    ordered = np.sort(costs)
    return FractureLifeCostEstimate(
        metrics.mean_cost,
        _higher_quantile(ordered, 0.9),
        _higher_quantile(ordered, max(0.0, 0.9 - epsilon)),
        _higher_quantile(ordered, min(1.0, 0.9 + epsilon)),
        count,
        parsed_seed,
        coverage,
        epsilon,
        float(np.mean(costs)),
        float(np.std(costs, ddof=1) / math.sqrt(count)),
    )


def fracture_life_distributions(
    spec: object,
    data: ActionData,
    *,
    distribution_cache: MutableMapping[object, Mapping[OutcomeClass, float]] | None = None,
) -> FractureLifeDistributions:
    """Derive the selected template's exact distributions from accepted actions.

    The optional caller-owned cache deliberately keys by resolved draw inputs,
    including labels, and never by ``ActionData`` object identity or prices.
    """
    _validate_selected_target(spec, data)
    labels = dict(getattr(spec, "labels"))
    cache = {} if distribution_cache is None else distribution_cache
    normal = ItemState("Royal Burgonet", 86, "normal")
    preparation = _cached_distribution(cache, "alchemy", normal, data, labels)
    early = probability(preparation, getattr(spec, "matches"))
    life_label = labels[_LIFE]
    gate = lambda outcome: outcome.prefixes + outcome.suffixes == 4 and life_label in outcome.labels
    full_gate = probability(preparation, gate)
    prepared = probability(preparation, lambda outcome: gate(outcome) and not getattr(spec, "matches")(outcome))

    demonstration = ItemState(
        "Royal Burgonet", 86, "rare", tuple(_mod_ref(data, mod_id) for mod_id in _FRACTURE_DEMONSTRATION)
    )
    fractures = fracture_distribution(demonstration, data)
    fracture = math.fsum(mass for outcome, mass in fractures.items() if outcome.fractured_mod_id == _LIFE)
    if fracture <= 0:
        raise ValueError("Life9 is not eligible for the selected fracture demonstration")

    life_only = ItemState(
        "Royal Burgonet", 86, "rare", (_mod_ref(data, _LIFE),), fractured=True, fractured_mod_id=_LIFE
    )
    finishing = _cached_distribution(cache, "essence", life_only, data, labels, essence_id=_ENVY)
    return FractureLifeDistributions(
        preparation,
        early,
        full_gate,
        prepared,
        fracture,
        finishing,
        probability(finishing, getattr(spec, "matches")),
    )


def fracture_life_envy_policy(spec: object, loadout: object, data: ActionData, cache: MutableMapping[object, object]) -> dict[str, object]:
    """Compare the two documented Alchemy early-completion choices."""
    policy_id = "fracture-life-envy"
    name = "Paid Life9 fracture then Deafening Envy"
    try:
        _validate_selected_target(spec, data)
    except (ValueError, NotImplementedError) as error:
        return _fixed._unavailable(policy_id, name, [str(error)])
    prices, reasons = _fixed._requirements(
        loadout, ("alchemy", "scour", "fracturing", "essence"),
        ("alchemy", "scour", "fracturing", _ENVY), essence_id=_ENVY,
    )
    if reasons:
        return _fixed._unavailable(policy_id, name, reasons)
    try:
        distributions = fracture_life_distributions(spec, data, distribution_cache=cache)
    except (ValueError, NotImplementedError) as error:
        return _fixed._unavailable(policy_id, name, [str(error)])
    candidates: list[dict[str, object]] = []
    for early_stop in (False, True):
        u = distributions.preparation_early_probability if early_stop else 0.0
        v = distributions.preparation_probability if early_stop else distributions.preparation_full_gate_probability
        try:
            metrics = fracture_life_metrics(
                u, v, distributions.fracture_probability,
                distributions.finishing_probability, _fixed._base_cost(loadout), prices["alchemy"],
                prices["scour"], prices["fracturing"], prices[_ENVY],
            )
            estimate = estimate_fracture_life_cost_p90(
                u, v, distributions.fracture_probability,
                distributions.finishing_probability, _fixed._base_cost(loadout), prices["alchemy"],
                prices["scour"], prices["fracturing"], prices[_ENVY],
            )
        except ValueError as error:
            return _fixed._unavailable(policy_id, name, [str(error)])
        candidates.append({"early_stop": early_stop, "preparation_probability": v, "metrics": metrics, "estimate": estimate})
    selected = min(candidates, key=lambda row: (row["metrics"].mean_cost, row["estimate"].p90, not row["early_stop"]))
    u = distributions.preparation_early_probability if selected["early_stop"] else 0.0
    v = selected["preparation_probability"]
    z = u + v * distributions.fracture_probability
    final = _terminal_mixture(
        spec, distributions.preparation_distribution, u / z,
        distributions.finishing_distribution, v * distributions.fracture_probability / z,
    )
    metrics = selected["metrics"]
    estimate = selected["estimate"]
    stages = [
        _fixed._stage(
            "Alchemy preparation", v + u, metrics.expected_alchemies,
            ("alchemy", "scour"),
            ("Stop on a complete Alchemy outcome." if selected["early_stop"] else "Discard complete Alchemy outcomes until the four-mod Life9 gate.",),
            distributions.preparation_distribution,
        ),
        _fracture_stage(distributions.fracture_probability, metrics.expected_fracturings),
        _fixed._stage("Deafening Envy finish", distributions.finishing_probability, metrics.expected_envies,
                      (_ENVY,), ("Envy rerolls non-fractured identities; only retained Life9 continues.",), distributions.finishing_distribution),
    ]
    policy = _fixed._policy(
        spec, loadout, policy_id, name, stages, metrics.mean_cost, estimate.p90,
        estimate.method, final, ("alchemy", "scour", "fracturing", _ENVY),
        ("Prepare exactly four ordinary explicits including Life9.", "Fracture uniformly, replacing wrong-fracture items.", "Repeat Deafening Envy after the desired Life9 fracture."),
        ("Uniform fracture selection is reimplemented-from-CoE; wrong fractures have caller salvage 0.", "Irreversible item-destruction risk is 0; discarded bases are reported separately."),
    )
    policy.update({
        "parameters": {"item_level": 86, "alchemy_early_stop": selected["early_stop"]},
        "candidate_count": 2,
        "parameter_audit": [{"parameters": {"item_level": 86, "alchemy_early_stop": row["early_stop"]}, "four_mod_life9": row["preparation_probability"], "expected_cost": row["metrics"].mean_cost, "cost_p90": row["estimate"].p90} for row in candidates],
        "gates": {"early_completion": u, "four_mod_life9": v, "life9_fracture": distributions.fracture_probability, "envy_finish": distributions.finishing_probability},
        "expected_action_counts": {"bases": metrics.expected_bases, "alchemy": metrics.expected_alchemies, "scour": metrics.expected_scours, "fracturing": metrics.expected_fracturings, "envy": metrics.expected_envies},
        "wrong_fracture_risk_per_trial": metrics.wrong_fracture_risk_per_trial,
        "expected_discarded_bases": metrics.expected_discarded_bases,
        "irreversible_item_destruction_risk": 0.0,
        "cost_p90_interval": [estimate.interval_lower, estimate.interval_upper],
        "cost_sample_count": estimate.samples, "cost_seed": estimate.seed, "cost_error_bound": estimate.dkw_epsilon,
        "cost_confidence": estimate.confidence,
        "cost_method_detail": "exact renewal mean; seeded DKW Monte Carlo p90 estimate",
        "source_confidence": "reimplemented-from-CoE",
        "sources": ["docs/design/family-policies.md fracture section", "docs/mechanics/fracturing.md uniform CoE 1/n", "docs/mechanics/essences.md Envy rare reroll"],
    })
    return policy


def _fracture_stage(fracture_probability: float, expected_attempts: float) -> dict[str, object]:
    """Represent desired/wrong scores without inventing real preparation identities."""
    return {
        "name": "uniform Life9 fracture",
        "probability": fracture_probability,
        "expected_attempts": expected_attempts,
        "actions": ["fracturing"],
        "decisions": ["Set aside every wrong-fracture item at salvage 0 and buy a replacement base."],
        "attempt_distribution": [
            {"labels": ["fracture:desired-Life9"], "probability": fracture_probability},
            {"labels": ["fracture:wrong"], "probability": 1 - fracture_probability},
        ],
        "attempt_distribution_condition": "score-only desired/wrong fracture outcomes; preparation affix identities and counts are intentionally not projected",
    }


def _terminal_mixture(spec, first, first_weight, second, second_weight):
    result: dict[OutcomeClass, float] = {}
    for distribution, weight in ((first, first_weight), (second, second_weight)):
        if not weight:
            continue
        selected = _fixed._selected_mass(spec, distribution)
        for outcome, mass in distribution.items():
            if _fixed._completes(spec, outcome):
                result[outcome] = result.get(outcome, 0.0) + weight * mass / selected
    return result


def _cached_distribution(cache, action, item, data, labels, *, essence_id=None):
    scenario = prepare_roll(action, item, data, labels, essence_id=essence_id)
    key = (
        "fracture-policy-action",
        action,
        essence_id,
        tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in scenario.entries),
        scenario.draw_counts,
        scenario.prefix_cap,
        scenario.suffix_cap,
        scenario.initial_prefixes,
        scenario.initial_suffixes,
        scenario.initial_labels,
        scenario.blocked_groups,
        tuple(sorted(labels.items())),
    )
    if key not in cache:
        cache[key] = action_distribution(action, item, data, labels, essence_id=essence_id)
    return cache[key]


def _validate_selected_target(spec: object, data: ActionData) -> None:
    if getattr(spec, "base", None) != "Royal Burgonet" or getattr(spec, "item_level", None) != 86:
        raise ValueError("fracture-Life policy only supports the ordinary Royal Burgonet86 helmet target")
    flags = getattr(spec, "flags", None)
    if not isinstance(flags, Mapping) or any(flags.values()):
        raise ValueError("fracture-Life policy only supports the ordinary Royal Burgonet86 helmet target")
    labels = getattr(spec, "labels", None)
    tier_ids = getattr(spec, "tier_ids", None)
    if not isinstance(labels, Mapping) or not isinstance(tier_ids, Mapping):
        raise ValueError("fracture-Life policy requires exact target tier mappings")
    required = {
        _LIFE: "IncreasedLife:1", "ChaosResist6": "ChaosResistance:1",
        "FireResist8": "FireResistance:1", "ColdResist8": "ColdResistance:1",
        "LightningResist8": "LightningResistance:1",
    }
    if any(labels.get(mod_id) != label for mod_id, label in required.items()):
        raise ValueError("fracture-Life policy only supports Life9/Chaos6/any elemental8")
    expected_tiers = {
        "IncreasedLife": ((_LIFE,),),
        "ChaosResistance": (("ChaosResist6",),),
        "FireResistance": (("FireResist8",),),
        "ColdResistance": (("ColdResist8",),),
        "LightningResistance": (("LightningResist8",),),
    }
    if dict(tier_ids) != expected_tiers or not _selected_predicate(spec):
        raise ValueError("fracture-Life policy only supports Life9/Chaos6/any elemental8")
    if any(mod_id not in data.mods for mod_id in _FRACTURE_DEMONSTRATION) or _ENVY not in data.essences:
        raise ValueError("fracture-Life policy requires accepted Life9, resistance, and Envy data")


def _selected_predicate(spec: object) -> bool:
    if getattr(spec, "value_table", None) is not None or getattr(spec, "threshold", None) is not None:
        return False
    required = _criteria_signature(getattr(spec, "required_mods", ()))
    alternatives = getattr(spec, "any_of", ())
    return (
        required == {("IncreasedLife", 1), ("ChaosResistance", 1)}
        and isinstance(alternatives, tuple)
        and len(alternatives) == 1
        and _criteria_signature(alternatives[0]) == {
            ("FireResistance", 1), ("ColdResistance", 1), ("LightningResistance", 1),
        }
    )


def _criteria_signature(criteria: object) -> set[tuple[object, object]] | None:
    if not isinstance(criteria, tuple):
        return None
    result = {(getattr(criterion, "group", None), getattr(criterion, "max_tier", None)) for criterion in criteria}
    return result if len(result) == len(criteria) else None


def _mod_ref(data: ActionData, mod_id: str) -> ModRef:
    row = data.mods[mod_id]
    return ModRef(mod_id, row["type"], row["group"])


def _inputs(u_raw, v_raw, f_raw, p_raw) -> tuple[float, float, float, float]:
    u = _probability(u_raw, "early_probability")
    v = _probability(v_raw, "preparation_probability")
    f = _probability(f_raw, "fracture_probability")
    p = _probability(p_raw, "finishing_probability")
    if u + v > 1:
        raise ValueError("early_probability + preparation_probability must not exceed one")
    return u, v, f, p


def _probability(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    value = float(value)
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return value


def _nonnegative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return float(value)


def _positive_integer(value: object, name: str) -> int:
    result = _integer(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _higher_quantile(ordered: np.ndarray, chance: float) -> float:
    rank = max(0, min(len(ordered) - 1, math.ceil(chance * len(ordered)) - 1))
    return float(ordered[rank])


def _validate_sampler_probability(chance: float, name: str) -> None:
    """Reject tails whose integer count representation could overflow NumPy."""
    minimum = 1.0 / np.iinfo(np.int64).max
    if chance < minimum:
        raise ValueError(f"{name} is too small for int64 Monte Carlo sampling")
