"""Evaluate the lead-authored fixed crafting policies.

The recipes in this module are deliberately bounded templates from
``docs/design/night-policies.md``.  This module does not optimise, discover,
or generalise those recipes.  It combines the accepted action adapter, exact
draw DP, and cost calculators into JSON-ready policy records.
"""

from __future__ import annotations

from collections.abc import MutableMapping
import math

from craftoracle.actions import ActionData, action_distribution, prepare_roll
from craftoracle.costs import chain_cost, compound_geometric_cost, geometric_cost
from craftoracle.distributions import OutcomeClass, probability, scheduled_distribution
from craftoracle.item_model import ItemState, ModRef, resolve_pool
from craftoracle.harvest import prepare_harvest
from craftoracle.harvest_policies import estimate_renewal_cost_p90, renewal_metrics
from craftoracle.monte_carlo import estimate_compound_cost_p90


_ENVY = "Metadata/Items/Currency/CurrencyEssenceEnvy3"
_Q9_FLAGS = ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split")
_BASE_ASSUMPTIONS = (
    "ordinary PoE 3.29 scope; Q9 item flags are outside this slice",
    "PoB group resolution and first-match weights are provisional under Q16/Q17",
    "no generated tags or weight multipliers are modelled",
    "prices are caller-supplied invented inputs and no base market price is modelled",
    "tiers are exact-ID mappings for the selected base",
    "quality is a fixed input",
    "no PoB damage valuation or Craft of Exile exactness proof is claimed",
    "irreversible failure risk covers item destruction only; p90_over_budget is separate",
)


def evaluate_policies(
    spec: object,
    loadout: object,
    data: ActionData,
    *,
    finish_bench_index: int | None = None,
    distribution_cache: MutableMapping[object, dict[OutcomeClass, float]] | None = None,
) -> dict[str, object]:
    """Return ranked available policies and explicit unavailable candidates.

    ``distribution_cache`` is an optional caller-owned cache of *raw* exact
    stage distributions.  Its keys include all draw-affecting inputs and omit
    prices and threshold, so a caller may evaluate price or utility threshold
    variants without re-running an identical DP.  It is never global.
    """
    _validate_contract(spec, loadout, data)
    cache = {} if distribution_cache is None else distribution_cache
    unavailable: list[dict[str, object]] = []
    available: list[dict[str, object]] = []
    labels = _labels(spec)

    if _enabled_q9_flags(spec):
        raise NotImplementedError("out of tonight's slice: Q9")

    normal = _item(spec, "normal")
    rare = _item(spec, "rare")

    candidate = _chaos_policy(spec, loadout, data, normal, rare, labels, cache)
    _collect(candidate, available, unavailable)
    candidate = _alchemy_scour_policy(spec, loadout, data, normal, labels, cache)
    _collect(candidate, available, unavailable)

    for essence_id in sorted(getattr(loadout, "allowed_essences")):
        candidate = _essence_policy(spec, loadout, data, normal, labels, essence_id, cache)
        _collect(candidate, available, unavailable)

    candidate = _magic_policy(spec, loadout, data, normal, labels, cache)
    _collect(candidate, available, unavailable)

    protected = _protected_policy(spec, loadout, data, normal, rare, labels, cache)
    _collect(protected, available, unavailable)
    harvest_protected = _harvest_protected_policy(spec, loadout, data, normal, labels, cache)
    _collect(harvest_protected, available, unavailable)
    bench_candidate = _protected_bench_policy(
        spec,
        loadout,
        data,
        protected,
        finish_bench_index,
    )
    _collect(bench_candidate, available, unavailable)

    available.sort(key=lambda policy: (policy["expected_cost"], policy["cost_p90"], policy["id"]))
    return _result(available, unavailable, data, getattr(loadout, "unit"))


def _chaos_policy(spec, loadout, data, normal, rare, labels, cache):
    policy_id = "chaos-spam"
    name = "Chaos spam after discarded Alchemy"
    prices, reasons = _requirements(loadout, ("alchemy", "chaos"), ("alchemy", "chaos"))
    if reasons:
        return _unavailable(policy_id, name, reasons)
    distribution = _action_distribution(cache, data, "chaos", rare, labels)
    success = _success_probability(spec, distribution)
    if success == 0:
        return _unavailable(policy_id, name, ["target is unreachable from the Chaos trial distribution"])
    cost = geometric_cost(success, prices["chaos"], setup_cost=_base_cost(loadout) + prices["alchemy"])
    stage = _stage(
        "chaos trial",
        success,
        1 / success,
        ("chaos",),
        ("Continue on failure; stop only after the Chaos result passes the target.",),
        distribution,
    )
    return _policy(
        spec,
        loadout,
        policy_id,
        name,
        [
            _stage("discarded Alchemy setup", 1, 1, ("alchemy",), ("Discard this roll intentionally; do not evaluate it.",), _action_distribution(cache, data, "alchemy", normal, labels)),
            stage,
        ],
        cost.expected_cost,
        cost.cost_p90,
        cost.method,
        distribution,
        ("chaos",),
        (
            "Start normal and apply Alchemy once.",
            "Discard the Alchemy outcome intentionally, then repeat Chaos until target completion.",
        ),
        ("The setup roll is deliberately not an early stop.", "Each Chaos result is target-tested."),
    )


def _alchemy_scour_policy(spec, loadout, data, normal, labels, cache):
    policy_id = "alchemy-scour"
    name = "Alchemy and Scour"
    prices, reasons = _requirements(loadout, ("alchemy", "scour"), ("alchemy", "scour"))
    if reasons:
        return _unavailable(policy_id, name, reasons)
    distribution = _action_distribution(cache, data, "alchemy", normal, labels)
    success = _success_probability(spec, distribution)
    if success == 0:
        return _unavailable(policy_id, name, ["target is unreachable from the Alchemy trial distribution"])
    cost = geometric_cost(success, prices["alchemy"], reset_cost=prices["scour"], setup_cost=_base_cost(loadout))
    return _policy(
        spec,
        loadout,
        policy_id,
        name,
        [_stage("alchemy trial", success, 1 / success, ("alchemy",), ("On failure Scour, then apply Alchemy again.",), distribution)],
        cost.expected_cost,
        cost.cost_p90,
        cost.method,
        distribution,
        ("alchemy", "scour"),
        ("Apply Alchemy to the normal item.", "After each failed result, Scour and repeat Alchemy."),
        ("Only failed Alchemy results pay Scour.",),
    )


def _essence_policy(spec, loadout, data, normal, labels, essence_id, cache):
    policy_id = _essence_id(essence_id)
    name = f"Essence spam: {essence_id.rsplit('/', 1)[-1]}"
    reasons: list[str] = []
    if essence_id not in data.essences:
        return _unavailable(policy_id, name, [f"unknown allowed essence: {essence_id}"])
    row = data.essences[essence_id]
    if row["tier"] == 8:
        return _unavailable(policy_id, name, ["unsourced: Q12 special essence behaviour"])
    if row["tier"] < 5:
        return _unavailable(policy_id, name, ["this repeat-on-rare essence policy requires tier 5 or higher"])
    base_type = _base_type(spec, data)
    if base_type not in row["mods"]:
        return _unavailable(policy_id, name, [f"essence has no forced mapping for base type {base_type}"])
    if row["mods"][base_type] not in data.mods:
        return _unavailable(policy_id, name, ["essence forced modifier is absent from the ordinary action data"])
    prices, reasons = _requirements(loadout, ("essence",), (essence_id,), essence_id=essence_id)
    if reasons:
        return _unavailable(policy_id, name, reasons)
    distribution = _action_distribution(cache, data, "essence", normal, labels, essence_id=essence_id)
    success = _success_probability(spec, distribution)
    if success == 0:
        return _unavailable(policy_id, name, ["target is unreachable from this forced essence mapping"])
    cost = geometric_cost(success, prices[essence_id], setup_cost=_base_cost(loadout))
    return _policy(
        spec,
        loadout,
        policy_id,
        name,
        [_stage("essence trial", success, 1 / success, (f"essence:{essence_id}",), ("Repeat the same tier-5-or-higher essence after each failed result.",), distribution)],
        cost.expected_cost,
        cost.cost_p90,
        cost.method,
        distribution,
        (essence_id,),
        ("Apply the stated essence to the normal base.", "Repeat the same essence until target completion."),
        ("The forced modifier mapping is read from ActionData.",),
    )


def _magic_policy(spec, loadout, data, normal, labels, cache):
    policy_id = "magic-regal-exalt"
    name = "Magic core, Regal, and three Exalts"
    currencies = ("transmute", "alteration", "augmentation", "regal", "exalted", "scour")
    prices, reasons = _requirements(loadout, currencies, currencies)
    if reasons:
        return _unavailable(policy_id, name, reasons)
    if tuple(data.rules["magic_caps"]) != (1, 1) or tuple(data.rules["rare_caps"]) != (3, 3):
        return _unavailable(policy_id, name, ["the fixed (2,1,1),(4,3,3) schedule requires ordinary 1/1 magic and 3/3 rare caps"])
    magic_weights = _count_weights(data.rules["magic_count_weights"])
    if set(magic_weights) != {1, 2}:
        return _unavailable(policy_id, name, ["the fixed magic cycle requires one- and two-mod Alteration count outcomes only"])
    augmentation_probability = magic_weights[1] / sum(magic_weights.values())

    magic = _item(spec, "magic")
    scenario = prepare_roll("alteration", magic, data, labels)
    magic_distribution = _scheduled_distribution(cache, data, scenario.entries, ((2, 1, 1),), labels, spec)
    regal_distribution = _scheduled_distribution(cache, data, scenario.entries, ((2, 1, 1), (1, 3, 3)), labels, spec)
    final_distribution = _scheduled_distribution(cache, data, scenario.entries, ((2, 1, 1), (4, 3, 3)), labels, spec)
    if not _all_terminal_counts(magic_distribution, 2) or not _all_terminal_counts(regal_distribution, 3) or not _all_terminal_counts(final_distribution, 6):
        return _unavailable(policy_id, name, ["the ordinary pool exhausts before the fixed paid magic, Regal, and Exalted cycle completes"])
    success = _success_probability(spec, final_distribution)
    if success == 0:
        return _unavailable(policy_id, name, ["target is unreachable after the fixed six-draw schedule"])

    low_trial = prices["alteration"] + prices["regal"] + 3 * prices["exalted"]
    high_trial = low_trial + prices["augmentation"]
    reset = prices["scour"] + prices["transmute"]
    setup = _base_cost(loadout) + prices["transmute"]
    try:
        cost = compound_geometric_cost(
            success,
            ((low_trial, magic_weights[2]), (high_trial, magic_weights[1])),
            reset_cost=reset,
            setup_cost=setup,
        )
        expected_cost = cost.expected_cost
        cost_p90 = cost.cost_p90
        cost_method = cost.method
        cost_metadata: dict[str, object] = {}
    except NotImplementedError as error:
        if str(error) != "cost convolution work limit":
            raise
        estimate = estimate_compound_cost_p90(
            success,
            low_trial,
            high_trial,
            augmentation_probability,
            reset_cost=reset,
            setup_cost=setup,
            samples=50_000,
            seed=20260921,
            confidence=0.99,
        )
        expected_cost = setup + ((1 - augmentation_probability) * low_trial + augmentation_probability * high_trial) / success + reset * (1 - success) / success
        cost_p90 = estimate.p90
        cost_method = "estimated p90; exact mean"
        cost_metadata = {
            "cost_p90_interval": [estimate.interval_lower, estimate.interval_upper],
            "cost_sample_count": estimate.samples,
            "cost_seed": estimate.seed,
            "cost_error_bound": estimate.dkw_epsilon,
        }

    outer_attempts = 1 / success
    stages = [
        _stage("transmute setup/reset", 1, outer_attempts, ("transmute",), ("First Transmute is setup; each failed cycle pays Scour then Transmute.",), _action_distribution(cache, data, "transmute", normal, labels)),
        _stage("magic completion", 1, outer_attempts, ("alteration", "augmentation?"), ("Augment only the one-mod Alteration branch; both branches finish with two magic draws.",), magic_distribution, target_probability_after_stage=_success_probability(spec, magic_distribution)),
        _stage("regal", 1, outer_attempts, ("regal",), ("Regal is a legal completion stage under the ordinary pool guard.",), regal_distribution, target_probability_after_stage=_success_probability(spec, regal_distribution)),
        _stage("final six draws", success, outer_attempts, ("exalted", "exalted", "exalted"), ("Evaluate only after the full fixed cycle; no early stop is claimed.",), final_distribution, target_probability_after_stage=success),
    ]
    policy = _policy(
        spec,
        loadout,
        policy_id,
        name,
        stages,
        expected_cost,
        cost_p90,
        cost_method,
        final_distribution,
        ("regal", "exalted", "scour"),
        (
            "Transmute once, then replace that setup roll with Alteration.",
            "Complete the magic item with optional Augmentation, Regal, and exactly three Exalts.",
            "After failure, Scour, Transmute, and restart the complete fixed cycle.",
        ),
        ("No target test changes the fixed cycle before its final draw.",),
    )
    policy.update(cost_metadata)
    return policy


def _protected_policy(spec, loadout, data, normal, rare, labels, cache):
    policy_id = "suffix-protected-life"
    name = "Envy suffix preparation and protected life"
    target_reason = _protected_target_reason(spec, data)
    if target_reason is not None:
        return _unavailable(policy_id, name, [target_reason])
    currencies = (_ENVY, "scour", "exalted")
    prices, reasons = _requirements(
        loadout,
        ("essence", "bench", "scour", "exalted"),
        currencies,
        essence_id=_ENVY,
        bench_index=729,
    )
    if reasons:
        return _unavailable(policy_id, name, reasons)
    if 729 not in data.bench:
        return _unavailable(policy_id, name, ["bench 729 is absent from ActionData"])
    lock = data.bench[729]
    if lock["type"] != "Prefix" or lock["group"] != "ItemGenerationCannotChangeSuffixes":
        return _unavailable(policy_id, name, ["bench 729 is not the required suffix-protection prefix craft"])
    base_type = _base_type(spec, data)
    if lock["types"].get(base_type) is not True:
        return _unavailable(policy_id, name, [f"bench 729 does not support base type {base_type}"])
    if tuple(data.rules["rare_caps"]) != (3, 3):
        return _unavailable(policy_id, name, ["protected policy requires ordinary 3/3 caps"])

    prefix_pool = resolve_pool(rare, data.bases, data.mods, "Prefix")
    suffix_pool = resolve_pool(rare, data.bases, data.mods, "Suffix")
    prefix_groups = {entry.group for entry in prefix_pool}
    suffix_groups = {entry.group for entry in suffix_pool}
    overlap = prefix_groups & suffix_groups
    if overlap:
        return _unavailable(policy_id, name, ["prefix/suffix group intersection prevents the required independent protected-prefix calculation"])
    life_id = "IncreasedLife9"
    life_weight = sum(entry.weight for entry in prefix_pool if entry.mod_id == life_id)
    prefix_weight = sum(entry.weight for entry in prefix_pool)
    if life_weight == 0 or prefix_weight == 0:
        return _unavailable(policy_id, name, ["required IncreasedLife9 prefix is absent from the ordinary prefix pool"])

    stage_one = _action_distribution(cache, data, "essence", normal, labels, essence_id=_ENVY)
    life_label = labels[life_id]
    chaos_label = labels["ChaosResist6"]
    elemental_labels = {labels[mod_id] for mod_id in ("FireResist8", "ColdResist8", "LightningResist8")}
    prepared = {
        outcome: mass
        for outcome, mass in stage_one.items()
        if chaos_label in outcome.labels
        and any(label in outcome.labels for label in elemental_labels)
        and outcome.suffixes == 3
        and outcome.prefixes <= 2
    }
    prepared_mass = math.fsum(prepared.values())
    if prepared_mass == 0:
        return _unavailable(policy_id, name, ["Envy cannot prepare the required full suffix state"])
    stage_one_probability = _normalized_mass(stage_one, prepared_mass)
    life_probability = life_weight / prefix_weight
    terminal = _protected_terminal_distribution(prepared, prepared_mass, life_label)
    bench_price, price_reason = _bench_price(loadout, 729)
    if price_reason is not None:
        return _unavailable(policy_id, name, [price_reason])
    try:
        cost = chain_cost(
            (
                (stage_one_probability, prices[_ENVY], 0, _base_cost(loadout)),
                (life_probability, bench_price + prices["scour"] + prices["exalted"], 0, 0),
            )
        )
    except NotImplementedError as error:
        if str(error) == "cost convolution work limit":
            return _unavailable(policy_id, name, ["cost convolution work limit for protected independent stages"])
        raise
    stages = [
        _stage(
            "prepare three suffixes",
            stage_one_probability,
            1 / stage_one_probability,
            (f"essence:{_ENVY}",),
            ("Keep only Chaos plus at least one elemental target with exactly three suffixes and at most two prefixes.",),
            stage_one,
        ),
        _stage(
            "roll protected life prefix",
            life_probability,
            1 / life_probability,
            ("bench:729", "scour", "exalted"),
            ("Craft suffix protection, Scour all prefixes including any natural life, then Exalt one prefix.",),
            _protected_stage_two_distribution(prepared, prepared_mass, life_label, life_probability),
        ),
    ]
    return _policy(
        spec,
        loadout,
        policy_id,
        name,
        stages,
        cost.expected_cost,
        cost.cost_p90,
        cost.method,
        terminal,
        (_ENVY, "bench:729", "scour", "exalted"),
        (
            "Repeat Deafening Envy until the stated full-suffix event occurs.",
            "Natural prefix life, when present, is intentionally Scoured before the protected Exalted draw.",
            "For each prefix attempt, craft Suffixes Cannot Be Changed, Scour, then Exalt once.",
        ),
        ("Stage 1 and Stage 2 are independent only after the explicit empty-prefix and disjoint-group guards.",),
    )


def _harvest_protected_policy(spec, loadout, data, normal, labels, cache):
    """Evaluate the sourced restart-on-full-prefix tagged-Harvest route."""
    policy_id = "suffix-protected-harvest-life"
    name = "Envy suffix preparation and protected Harvest life"
    target_reason = _protected_target_reason(spec, data)
    if target_reason is not None:
        return _unavailable(policy_id, name, [target_reason])
    prices, reasons = _requirements(
        loadout,
        ("essence", "bench", "harvest_reforge:life"),
        (_ENVY, "harvest_reforge:life"),
        essence_id=_ENVY,
        bench_index=729,
    )
    if reasons:
        return _unavailable(policy_id, name, reasons)
    lock_reason = _suffix_lock_reason(spec, data)
    if lock_reason is not None:
        return _unavailable(policy_id, name, [lock_reason])
    representatives, representative_reason = _harvest_suffix_representatives(spec, data)
    if representative_reason is not None:
        return _unavailable(policy_id, name, [representative_reason])
    assert representatives is not None

    stage_one = _action_distribution(cache, data, "essence", normal, labels, essence_id=_ENVY)
    prepared, preparation_p = _prepared_suffixes(stage_one, labels)
    if preparation_p == 0:
        return _unavailable(policy_id, name, ["Envy cannot prepare the required full suffix state"])
    life_label = labels["IncreasedLife9"]
    representative = ItemState(
        getattr(spec, "base"),
        getattr(spec, "item_level"),
        "rare",
        (*representatives, _bench_ref(data, 729)),
    )
    prefixes = _harvest_distribution(cache, data, representative, {"IncreasedLife9": life_label})
    p = _normalized_mass(prefixes, probability(prefixes, lambda outcome: life_label in outcome.labels))
    b = _normalized_mass(
        prefixes,
        probability(prefixes, lambda outcome: outcome.prefixes == 3 and life_label not in outcome.labels),
    )
    if p == 0:
        return _unavailable(policy_id, name, ["Harvest life reforge cannot roll IncreasedLife9"])
    terminal_attempt = _combine_harvest_prefixes(prepared, preparation_p, prefixes, life_label)
    bench_price, price_reason = _bench_price(loadout, 729)
    if price_reason is not None:
        return _unavailable(policy_id, name, [price_reason])
    reforge_cost = bench_price + prices["harvest_reforge:life"]
    metrics = renewal_metrics(
        preparation_p,
        prices[_ENVY],
        p,
        b,
        reforge_cost,
        base_cost=_base_cost(loadout),
    )
    estimate = estimate_renewal_cost_p90(
        preparation_p,
        prices[_ENVY],
        p,
        b,
        reforge_cost,
        base_cost=_base_cost(loadout),
        samples=50_000,
        seed=20260921,
        confidence=.99,
    )
    stages = [
        _stage(
            "prepare three suffixes",
            preparation_p,
            metrics.essence_attempts,
            (f"essence:{_ENVY}",),
            ("Keep Chaos plus at least one elemental target with exactly three suffixes and at most two prefixes.",),
            stage_one,
        ),
        _stage(
            "roll protected Harvest life prefix",
            p,
            metrics.reforge_attempts,
            ("bench:729", "harvest_reforge:life"),
            (
                "Before every Life reforge, craft a fresh Suffixes Cannot Be Changed lock; the reforge consumes that lock.",
                "On a non-full failure, retain the suffixes, relock them, and reforge again.",
                "On a failed three-prefix result, restart Envy preparation on the same base.",
            ),
            terminal_attempt,
            target_probability_after_stage=p,
        ),
    ]
    policy = _policy(
        spec,
        loadout,
        policy_id,
        name,
        stages,
        metrics.mean_cost,
        estimate.p90,
        "estimated p90 (seeded independent renewal MC); exact mean",
        terminal_attempt,
        (_ENVY, "bench:729", "harvest_reforge:life"),
        (
            "Repeat Deafening Envy until the stated three-suffix preparation occurs.",
            "Before each Life reforge, craft Suffixes Cannot Be Changed; the prefix lock is consumed by that reforge.",
            "Keep non-full failures protected; a failed full-prefix result returns to Envy preparation on the same base.",
        ),
        (
            "Success is tested only after the Harvest stage for this baseline.",
            "The base cost is charged once; each Envy, bench lock, and Harvest reforge is charged.",
        ),
    )
    policy.update({
        "full_prefix_failure_probability": b,
        "preparation_probability": preparation_p,
        "expected_reforge_attempts": metrics.reforge_attempts,
        "expected_preparations": metrics.preparations,
        "expected_essence_attempts": metrics.essence_attempts,
        "cost_p90_interval": [estimate.interval_lower, estimate.interval_upper],
        "cost_sample_count": estimate.samples,
        "cost_seed": estimate.seed,
        "cost_confidence": estimate.confidence,
        "cost_error_bound": estimate.dkw_epsilon,
        "_assumptions": (
            "Harvest uses the adopted S14 first-draw-only modifier-type filtering and S19 type-restriction support.",
            "The lock has no attack/caster blocker; only ordinary Q9-free items are evaluated.",
            "All ordinary suffix groups are checked against prefix groups before one concrete sourced suffix representative is reused.",
            "harvest_reforge:life=1 is an invented D21 price input; owner-provisional Sacred-price equality applies only to Minion, Elemental, Attribute, and Mana.",
        ),
    })
    return policy


def _suffix_lock_reason(spec, data):
    if 729 not in data.bench:
        return "bench 729 is absent from ActionData"
    lock = data.bench[729]
    if lock["type"] != "Prefix" or lock["group"] != "ItemGenerationCannotChangeSuffixes":
        return "bench 729 is not the required suffix-protection prefix craft"
    base_type = _base_type(spec, data)
    if lock["types"].get(base_type) is not True:
        return f"bench 729 does not support base type {base_type}"
    if lock["group"] in {"ItemGenerationCannotRollAttackAffixes", "ItemGenerationCannotRollCasterAffixes"}:
        return "bench 729 unexpectedly applies an attack/caster blocker"
    if tuple(data.rules["rare_caps"]) != (3, 3):
        return "protected Harvest policy requires ordinary 3/3 caps"
    return None


def _harvest_suffix_representatives(spec, data):
    selected = ("ChaosResist6", "FireResist8", "ColdResist8")
    ordinary = _item(spec, "rare")
    suffix_entries = resolve_pool(ordinary, data.bases, data.mods, "Suffix")
    eligible_suffixes = {entry.mod_id: entry for entry in suffix_entries}
    refs = []
    for mod_id in selected:
        row = data.mods.get(mod_id)
        if row is None or row.get("type") != "Suffix" or not isinstance(row.get("group"), str):
            return None, f"representative protected suffix {mod_id} is not an ordinary suffix with a source group"
        entry = eligible_suffixes.get(mod_id)
        if entry is None:
            return None, f"representative protected suffix {mod_id} is not in the eligible ordinary suffix pool"
        refs.append((mod_id, entry.group))
    suffix_groups = {group for _, group in refs}
    if len(suffix_groups) != len(refs):
        return None, "representative protected suffixes do not have distinct source groups"
    prefix_groups = {entry.group for entry in resolve_pool(ordinary, data.bases, data.mods, "Prefix")}
    all_suffix_groups = {entry.group for entry in suffix_entries}
    overlap = prefix_groups & all_suffix_groups
    if overlap:
        return None, "prefix/suffix group intersection prevents independent protected Harvest prefix calculation"
    return tuple(ModRef(mod_id, "Suffix", group) for mod_id, group in refs), None


def _bench_ref(data, index):
    row = data.bench[index]
    return ModRef(f"bench:{index}", row["type"], row["group"])


def _prepared_suffixes(stage_one, labels):
    chaos_label = labels["ChaosResist6"]
    elemental_labels = {labels[mod_id] for mod_id in ("FireResist8", "ColdResist8", "LightningResist8")}
    prepared = {
        outcome: mass
        for outcome, mass in stage_one.items()
        if chaos_label in outcome.labels
        and any(label in outcome.labels for label in elemental_labels)
        and outcome.suffixes == 3
        and outcome.prefixes <= 2
    }
    return prepared, _normalized_mass(stage_one, math.fsum(prepared.values()))


def _harvest_distribution(cache, data, item, labels):
    plan = prepare_harvest(item, data, "life", type_filter="first_only")
    key = (
        "harvest_reforge",
        _harvest_plan_signature(plan),
        "life",
        "first_only",
        tuple(sorted(labels.items())),
    )
    if key not in cache:
        cache[key] = action_distribution("harvest_reforge", item, data, labels, harvest_tag="life")
    return cache[key]


def _harvest_plan_signature(plan):
    return (
        plan.item,
        plan.retained,
        tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in plan.forced),
        tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in plan.ordinary),
        plan.counts,
        plan.prefix_cap,
        plan.suffix_cap,
    )


def _combine_harvest_prefixes(prepared, preparation_p, prefixes, life_label):
    """Attach each accepted suffix label class to its group-independent prefixes."""
    combined: dict[OutcomeClass, float] = {}
    for suffix_outcome, suffix_mass in prepared.items():
        suffix_labels = tuple(label for label in suffix_outcome.labels if label != life_label)
        for prefix_outcome, prefix_mass in prefixes.items():
            labels = tuple(sorted((*suffix_labels, *prefix_outcome.labels)))
            outcome = OutcomeClass(labels, prefix_outcome.prefixes, 3)
            combined[outcome] = combined.get(outcome, 0.0) + suffix_mass / preparation_p * prefix_mass
    return combined


def _protected_bench_policy(spec, loadout, data, protected, requested_index):
    index = 131 if requested_index is None else requested_index
    policy_id = _bench_id(index)
    name = f"Protected life with bench finish {index}"
    if not isinstance(protected, dict) or "reasons" in protected:
        reason = "protected policy is unavailable"
        if isinstance(protected, dict):
            reason = f"{reason}: {'; '.join(protected.get('reasons', []))}"
        return _unavailable(policy_id, name, [reason])
    if not isinstance(index, int) or isinstance(index, bool):
        return _unavailable(policy_id, name, ["finish_bench_index must be an integer"])
    reasons: list[str] = []
    if not _permits(loadout, ("bench",), bench_index=index):
        reasons.append(f"loadout does not permit bench {index}")
    if index not in data.bench:
        reasons.append(f"bench {index} is absent from ActionData")
    if reasons:
        return _unavailable(policy_id, name, reasons)
    row = data.bench[index]
    base_type = _base_type(spec, data)
    life_group = data.mods["IncreasedLife9"]["group"]
    suffix_groups = {entry.group for entry in resolve_pool(_item(spec, "rare"), data.bases, data.mods, "Suffix")}
    if row["types"].get(base_type) is not True:
        reasons.append(f"bench {index} does not support base type {base_type}")
    if row["type"] != "Prefix":
        reasons.append(f"bench {index} is not a Prefix craft")
    if row["group"] == life_group:
        reasons.append(f"bench {index} conflicts with the known life group")
    if row["group"] in suffix_groups:
        reasons.append(f"bench {index} conflicts with a possible ordinary suffix group")
    if reasons:
        return _unavailable(policy_id, name, reasons)
    bench_price, price_reason = _bench_price(loadout, index)
    if price_reason is not None:
        return _unavailable(policy_id, name, [price_reason])
    result = dict(protected)
    result["id"] = policy_id
    result["name"] = name
    result["expected_cost"] = protected["expected_cost"] + bench_price
    result["cost_p90"] = protected["cost_p90"] + bench_price
    result["cost_method"] = f"{protected['cost_method']}; deterministic bench finish"
    result["method"] = "exact conditional terminal distribution; " + result["cost_method"]
    result["rare_inputs"] = [*protected["rare_inputs"], f"bench:{index}"]
    result["steps"] = [*protected["steps"], f"Apply compatible Prefix bench craft {index} after the life prefix succeeds."]
    result["decision_points"] = [*protected["decision_points"], "Bench finish is an explicit optional deterministic variant."]
    result["within_budget"] = result["expected_cost"] <= _budget(loadout)
    result["p90_over_budget"] = result["cost_p90"] > _budget(loadout)
    bench_label = _labels(spec).get(f"bench:{index}")
    result["terminal_distribution"] = _bench_terminal_distribution(protected["terminal_distribution"], bench_label)
    result["stages"] = [
        *protected["stages"],
        _stage(
            "deterministic bench finish",
            1,
            1,
            (f"bench:{index}",),
            ("The known life prefix and three ordinary suffixes leave two Prefix slots and no retained crafts.",),
            _rows_distribution(result["terminal_distribution"]),
        ),
    ]
    return result


def _policy(spec, loadout, policy_id, name, stages, expected_cost, cost_p90, cost_method, final_distribution, rare_inputs, steps, decision_points):
    terminal = _conditional_distribution(spec, final_distribution)
    return {
        "id": policy_id,
        "name": name,
        "stages": stages,
        "expected_cost": expected_cost,
        "cost_p90": cost_p90,
        "cost_method": cost_method,
        "expected_utility": _conditional_expected_utility(spec, final_distribution),
        "expected_utility_condition": "conditional on completion",
        "irreversible_failure_risk": 0.0,
        "rare_inputs": list(rare_inputs),
        "assumptions": list(_BASE_ASSUMPTIONS),
        "steps": list(steps),
        "decision_points": list(decision_points),
        "within_budget": expected_cost <= _budget(loadout),
        "p90_over_budget": cost_p90 > _budget(loadout),
        "frontier": False,
        "method": f"exact conditional terminal distribution; {cost_method}",
        "cost_unit": getattr(loadout, "unit"),
        "terminal_distribution": _serialize_distribution(terminal),
        "terminal_distribution_condition": "conditional on completion",
    }


def _stage(name, chance, attempts, actions, decisions, distribution, *, target_probability_after_stage=None):
    stage = {
        "name": name,
        "probability": chance,
        "expected_attempts": attempts,
        "actions": list(actions),
        "decisions": list(decisions),
        "attempt_distribution": _serialize_distribution(distribution),
    }
    if target_probability_after_stage is not None:
        stage["target_probability_after_stage"] = target_probability_after_stage
    return stage


def _action_distribution(cache, data, action, item, labels, *, essence_id=None):
    scenario = prepare_roll(action, item, data, labels, essence_id=essence_id)
    key = (
        "action",
        action,
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


def _scheduled_distribution(cache, data, entries, stages, labels, spec):
    key = (
        "scheduled",
        _item(spec, "rare"),
        tuple(sorted(labels.items())),
        tuple(stages),
        tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in entries),
    )
    if key not in cache:
        cache[key] = scheduled_distribution(entries, stages, labels)
    return cache[key]


def _requirements(loadout, actions, currencies, *, essence_id=None, bench_index=None):
    reasons: list[str] = []
    if not _permits(loadout, actions, essence_id=essence_id, bench_index=bench_index):
        detail = []
        if essence_id is not None:
            detail.append(f"essence {essence_id}")
        if bench_index is not None:
            detail.append(f"bench {bench_index}")
        suffix = f" ({', '.join(detail)})" if detail else ""
        reasons.append(f"loadout does not permit required actions{suffix}")
    prices: dict[str, float] = {}
    for currency in currencies:
        try:
            prices[currency] = float(loadout.price(currency))
        except ValueError as error:
            reasons.append(str(error))
    return prices, reasons


def _bench_price(loadout, index):
    try:
        return float(loadout.bench_cost(index)), None
    except ValueError as error:
        return None, str(error)


def _permits(loadout, actions, *, essence_id=None, bench_index=None):
    return bool(loadout.permits(tuple(actions), essence_id=essence_id, bench_index=bench_index))


def _protected_target_reason(spec, data):
    if getattr(spec, "value_table", None) is not None:
        return "suffix-protected policy only implements the exact required-mod helmet target"
    expected_ids = {
        "IncreasedLife": (("IncreasedLife9",),),
        "ChaosResistance": (("ChaosResist6",),),
        "FireResistance": (("FireResist8",),),
        "ColdResistance": (("ColdResist8",),),
        "LightningResistance": (("LightningResist8",),),
    }
    observed = getattr(spec, "tier_ids", {})
    if observed != expected_ids:
        return "suffix-protected policy requires the exact IncreasedLife9, ChaosResist6, and elemental T1 ID mapping"
    required = {(criterion.group, criterion.max_tier) for criterion in getattr(spec, "required_mods", ())}
    any_of = getattr(spec, "any_of", ())
    elemental = {(criterion.group, criterion.max_tier) for group in any_of for criterion in group}
    if required != {("IncreasedLife", 1), ("ChaosResistance", 1)} or elemental != {
        ("FireResistance", 1), ("ColdResistance", 1), ("LightningResistance", 1)
    } or len(any_of) != 1 or len(any_of[0]) != 3:
        return "suffix-protected policy requires one life, one chaos, and elemental-any T1 criteria"
    for mod_id, side, group in (
        ("IncreasedLife9", "Prefix", "IncreasedLife"),
        ("ChaosResist6", "Suffix", "ChaosResistance"),
        ("FireResist8", "Suffix", "FireResistance"),
        ("ColdResist8", "Suffix", "ColdResistance"),
        ("LightningResist8", "Suffix", "LightningResistance"),
    ):
        row = data.mods.get(mod_id)
        if row is None or row.get("type") != side or row.get("group") != group:
            return f"target modifier {mod_id} does not have the required ordinary {side} group"
    return None


def _protected_terminal_distribution(prepared, prepared_probability, life_label):
    terminal: dict[OutcomeClass, float] = {}
    for outcome, mass in prepared.items():
        labels = tuple(sorted((*[label for label in outcome.labels if label != life_label], life_label)))
        finished = OutcomeClass(labels, 1, 3)
        terminal[finished] = terminal.get(finished, 0.0) + mass / prepared_probability
    return terminal


def _protected_stage_two_distribution(prepared, prepared_probability, life_label, chance):
    result: dict[OutcomeClass, float] = {}
    for outcome, mass in prepared.items():
        suffix_labels = tuple(label for label in outcome.labels if label != life_label)
        normalized = mass / prepared_probability
        hit = OutcomeClass(tuple(sorted((*suffix_labels, life_label))), 1, 3)
        miss = OutcomeClass(tuple(sorted(suffix_labels)), 1, 3)
        result[hit] = result.get(hit, 0.0) + normalized * chance
        result[miss] = result.get(miss, 0.0) + normalized * (1 - chance)
    return result


def _conditional_distribution(spec, distribution):
    selected_mass = _selected_mass(spec, distribution)
    if selected_mass == 0:
        raise ValueError("cannot serialize a zero-probability terminal distribution as a completed policy")
    return {outcome: mass / selected_mass for outcome, mass in distribution.items() if _completes(spec, outcome)}


def _conditional_expected_utility(spec, distribution):
    selected_mass = _selected_mass(spec, distribution)
    if getattr(spec, "value_table", None) is None:
        return 1.0
    selected = [
        (mass, float(spec.utility(outcome)))
        for outcome, mass in distribution.items()
        if _completes(spec, outcome)
    ]
    anchor = selected[0][1]
    return anchor + math.fsum(mass * (utility - anchor) for mass, utility in selected) / selected_mass


def _success_probability(spec, distribution):
    return _normalized_mass(distribution, _selected_mass(spec, distribution))


def _selected_mass(spec, distribution):
    # ``probability`` validates kernel mass and outcome classes.  Sum selected
    # and total mass with the same stable primitive before handing p to costs.
    probability(distribution, lambda outcome: _completes(spec, outcome))
    return math.fsum(mass for outcome, mass in distribution.items() if _completes(spec, outcome))


def _normalized_mass(distribution, selected_mass):
    """Normalize only after the kernel has accepted its <=1e-10 mass tolerance."""
    total_mass = math.fsum(distribution.values())
    if total_mass <= 0:
        raise ValueError("distribution has no mass")
    return selected_mass / total_mass


def _completes(spec, outcome):
    if getattr(spec, "value_table", None) is None:
        return bool(spec.matches(outcome))
    return float(spec.utility(outcome)) >= float(spec.threshold)


def _serialize_distribution(distribution):
    return [
        {
            "labels": list(outcome.labels),
            "prefixes": outcome.prefixes,
            "suffixes": outcome.suffixes,
            "probability": mass,
        }
        for outcome, mass in sorted(distribution.items())
    ]


def _bench_terminal_distribution(rows, bench_label):
    result = []
    for row in rows:
        labels = list(row["labels"])
        if bench_label is not None:
            labels.append(bench_label)
            labels.sort()
        result.append({**row, "labels": labels, "prefixes": 2, "suffixes": 3})
    return result


def _rows_distribution(rows):
    result: dict[OutcomeClass, float] = {}
    for row in rows:
        outcome = OutcomeClass(tuple(row["labels"]), row["prefixes"], row["suffixes"])
        result[outcome] = result.get(outcome, 0.0) + row["probability"]
    return result


def _item(spec, rarity):
    flags = getattr(spec, "flags")
    return ItemState(
        getattr(spec, "base"),
        getattr(spec, "item_level"),
        rarity,
        **{flag: bool(flags.get(flag, False)) for flag in _Q9_FLAGS},
    )


def _enabled_q9_flags(spec):
    flags = getattr(spec, "flags")
    return any(flags.get(flag, False) for flag in _Q9_FLAGS)


def _labels(spec):
    return dict(getattr(spec, "labels"))


def _base_type(spec, data):
    try:
        return data.bases[getattr(spec, "base")]["type"]
    except KeyError as error:
        raise ValueError(f"unknown base: {getattr(spec, 'base')}") from error


def _base_cost(loadout):
    return float(getattr(loadout, "base_cost"))


def _budget(loadout):
    return float(getattr(loadout, "budget"))


def _essence_id(essence_id):
    return f"essence-{essence_id.rsplit('/', 1)[-1]}"


def _bench_id(index):
    selected = 131 if index is None else index
    return f"suffix-protected-life-bench-{selected}"


def _unavailable(policy_id, name, reasons):
    return {"id": policy_id, "name": name, "reasons": list(reasons), "assumptions": list(_BASE_ASSUMPTIONS)}


def _collect(candidate, available, unavailable):
    if "reasons" in candidate:
        unavailable.append(candidate)
    else:
        available.append(candidate)


def _result(available, unavailable, data, unit):
    available.sort(key=lambda policy: (policy["expected_cost"], policy["cost_p90"], policy["id"]))
    unavailable.sort(key=lambda policy: policy["id"])
    assumptions = _assumptions(data, unit)
    for policy in [*available, *unavailable]:
        extra = policy.pop("_assumptions", ())
        policy["assumptions"] = [*assumptions, *extra]
    return {"ranked": available, "unavailable": unavailable, "assumptions": list(assumptions), "unit": unit}


def _assumptions(data, unit):
    rare = _count_weights(data.rules["rare_count_weights"])
    magic = _count_weights(data.rules["magic_count_weights"])
    return (
        *_BASE_ASSUMPTIONS,
        f"rare count weights are {_weight_text(rare)} from CoE evidence",
        f"magic count weights are {_weight_text(magic)} from CoE evidence",
        f"cost unit is {unit} from the input price file",
    )


def _count_weights(raw):
    return {int(count): float(weight) for count, weight in raw.items()}


def _weight_text(weights):
    return ", ".join(f"{count}:{weight:g}" for count, weight in sorted(weights.items()))


def _all_terminal_counts(distribution, total):
    return all(outcome.prefixes + outcome.suffixes == total for outcome in distribution)


def _validate_contract(spec, loadout, data):
    if not isinstance(data, ActionData):
        raise ValueError("data must be ActionData")
    required_spec = ("base", "item_level", "flags", "labels", "matches", "utility", "tier_ids", "required_mods", "any_of")
    required_loadout = ("allowed_essences", "price", "bench_cost", "permits", "base_cost", "budget", "unit")
    missing = [name for name in required_spec if not hasattr(spec, name)]
    missing.extend(name for name in required_loadout if not hasattr(loadout, name))
    if missing:
        raise ValueError(f"input contract missing: {', '.join(missing)}")
