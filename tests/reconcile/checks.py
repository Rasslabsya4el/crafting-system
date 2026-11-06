"""The reconciliation: for one target, every fact written in two places, one named slot per fact.

`slots(target, spec)` lists the slot names from the two YAML files alone (no game data), so the set of
checks never depends on what the data says. `reconcile(...)` returns, for each slot, the disagreements
found there; an empty list means the places agree. A disagreement names both places and what each says
(`place_a`, `place_b`: a sentence) and the two values that differ (`value_a`, `value_b`: short text), which
`known.py` pins, so a known disagreement that changes also fails.

Slots (the rule behind all of them is OR-3, "the target, the buy spec and the price agree"):

- `target.base`: the base the target names exists in the game data.
- `start_price.written`, `buy_spec.exists`: a target says `start: given` or `start: bought` (OR-6, #505). A bought one has a
  price key (a row of `expected_keys.txt`) and a buy spec that carries that name; a given one needs neither. A target that does
  not say how its start item is had, or a bought one without them, is counted free by nobody: it is a disagreement (audit INPUTS-8).
- `buy.base`, `buy.category`, `buy.item_level`, `buy.rarity`, `buy.influence`: the target's start item
  against the buy spec whose `name` is the target's `start_price`.
- `buy.pool`: every base the spec accepts has the same mod pool as the target's base.
- `start_mod.<mod>.ladder`, `.values`: a start mod can spawn on every base the target names and has one tier on them (the tier is the
  game data's since #484: a target file writes none), and its hand-written values against the game data.
- `start_mod.<mod>.buy_mod`, `.buy_minimum`: a start mod against the buy spec's mod of the same text,
  and the spec's minimum against the tier (the tier the price was taken for).
- `buy_mod.<stat>.in_target`: a buy spec mod the target's start item does not have.
- `price.entry`, `price.base`, `price.item_level`, `price.source`, `price.pool`: the start-price entry
  against the target's base by base id (several bases share a name), item level (as the entry records
  it), the kind of price (a trade search, not a stand-in) and the mod pool of the bases it prices.
- `price.rarity`, `price.influence`, `price.corrupted`, `price.mods`: the rest of what the entry's own search asked for, read from the
  stored query (#470). The rarity, the influences (the `pseudo_has_<name>_influence` stats) and the corruption filter against the target's
  start item; the mods (each stat id read as the trade site's text through the recorded stat list, with its group `fractured`, `implicit`
  or `explicit` and its minimum) and the `fractured_item` filter against the buy spec's mods, which the other slots hold equal to the
  target's. An entry with no stored search (a poe.ninja or hand line) has nothing to read here: `price.source` is its row.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .export import REPO_ROOT, Export
from .files import (
    BuyMod,
    BuySpec,
    INFLUENCE_STAT,
    FileFormatError,
    PriceEntry,
    Target,
    buy_spec_of,
    price_files_of,
    priced_base_name,
    priced_category,
    priced_corrupted,
    priced_fractured_flag,
    priced_item_level,
    priced_rarity,
    priced_stats,
    read_price_entry,
    read_trade_stat_texts,
)
from .ladder import (
    TRADE_CATEGORY,
    base_ids_of,
    bases_named,
    bases_of_category,
    ladder,
    normalise_stat_text,
    pool_of,
    stat_ranges,
)

TRADE_SOURCE = "trade-api"


@dataclass(frozen=True)
class Disagreement:
    """Two places that say different things about one fact."""

    slot: str
    place_a: str
    place_b: str
    value_a: str = ""
    value_b: str = ""

    def __str__(self) -> str:
        return f"{self.slot}: {self.place_a}  <>  {self.place_b}  [{self.value_a} <> {self.value_b}]"

    @property
    def values(self) -> tuple[str, str]:
        return (self.value_a, self.value_b)


def short(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def slots(target: Target, spec: BuySpec | None) -> list[str]:
    """The slot names for this target and its buy spec, from the two files alone."""
    names = ["target.base", "start_price.written", "buy_spec.exists"]
    if spec is not None:
        names += ["buy.base", "buy.category", "buy.item_level", "buy.rarity", "buy.influence", "buy.pool"]
    for mod in target.start_mods:
        names += [f"start_mod.{mod.mod}.ladder", f"start_mod.{mod.mod}.values"]
        if spec is not None:
            names += [f"start_mod.{mod.mod}.buy_mod", f"start_mod.{mod.mod}.buy_minimum"]
    if spec is not None:
        names += [f"buy_mod.{normalise_stat_text(mod.stat)}.in_target" for mod in spec.mods if not mod.own]
    if target.start_price is not None:
        names += [
            "price.entry", "price.base", "price.item_level", "price.rarity", "price.influence", "price.corrupted", "price.mods",
            "price.source", "price.pool",
        ]  # fmt: skip
    return names


def check_ids(targets: list[Target], specs: list[BuySpec]) -> list[str]:
    """Every check as `<target>::<slot>`, in target order: what the committed expected set must equal."""
    return [f"{target.name}::{slot}" for target in targets for slot in slots(target, buy_spec_of(target, specs))]


def _find_buy_mod(spec: BuySpec, text: str) -> BuyMod | None:
    found = [mod for mod in spec.mods if normalise_stat_text(mod.stat) == text]
    if len(found) > 1:
        raise FileFormatError(f"{spec.path.name}: the mod {text!r} is listed {len(found)} times")
    return found[0] if found else None


def _text_of(export: Export, mod_id: str) -> str | None:
    mod = export.mods.get(mod_id)
    return normalise_stat_text(mod["text"]) if mod else None


def _ladder_on(export: Export, base_id: str, mod_id: str, influence: frozenset) -> dict[str, int]:
    """The natural ladder of `mod_id` on a base, with the item's influence tags."""
    base = export.bases[base_id]
    return ladder(export.mods, base["tags"], base["domain"], mod_id, influence, base["item_class"])


def _tiers_of(export: Export, base_ids: list[str], mod_id: str, influence: frozenset) -> dict[str, int | None]:
    """The tier of `mod_id` on each base id: None where the mod cannot spawn on the base."""
    return {base_id: _ladder_on(export, base_id, mod_id, influence).get(mod_id) for base_id in base_ids}


def _pool_differences(export: Export, target_ids: list[str], accepted_ids: list[str]) -> list[str]:
    """The accepted bases whose mod pool is not the pool of the target's base, with how many mods differ."""
    if not target_ids:
        return []
    cache = export.cache

    def pool(base_id: str) -> frozenset:
        base = export.bases[base_id]
        return pool_of(export.mods, base["tags"], base["domain"], cache)

    reference = pool(target_ids[0])
    return [
        f"{base_id} (+{len(pool(base_id) - reference)} -{len(reference - pool(base_id))})"
        for base_id in sorted(set(target_ids) | set(accepted_ids))
        if pool(base_id) != reference
    ]


def _with_own_implicits(export: Export, accepted: list[str], spec: BuySpec) -> list[str]:
    """The accepted bases that have every implicit the spec names as the base's own (the three Two-Toned Boots differ in theirs)."""
    wanted = {normalise_stat_text(mod.stat) for mod in spec.mods if mod.own}
    if not wanted:
        return accepted

    def reads(base_id: str) -> set[str]:
        return {normalise_stat_text(export.mods[mod_id]["text"]) for mod_id in export.bases[base_id].get("implicits", ()) if mod_id in export.mods}

    return [base_id for base_id in accepted if wanted <= reads(base_id)]


@lru_cache(maxsize=1)
def _recorded_stat_texts() -> dict[str, str]:
    return read_trade_stat_texts()


def _wanted_mods(spec: BuySpec) -> list[str]:
    """The mods the spec searches, each as `<group> <text> at least <minimum>` (the group is where the trade site lists the stat)."""
    return sorted(_mod_line(_group_of(mod), normalise_stat_text(mod.stat), mod.minimum) for mod in spec.mods)


def _group_of(mod: BuyMod) -> str:
    return "implicit" if mod.own or mod.implicit else "fractured" if mod.fractured else "explicit"


def _mod_line(group: str, text: str, minimum: float | None) -> str:
    return f"{group} {text} at least {minimum:g}" if minimum is not None else f"{group} {text} (no minimum)"


def _priced_mods(entry: PriceEntry, texts: dict[str, str]) -> tuple[list[str], list[str]]:
    """(the mods of the entry's search as `_mod_line` words, the influences it asks for): an influence is a pseudo stat, not a mod."""
    mods, influences = [], []
    for stat_id, minimum in priced_stats(entry):
        influence = INFLUENCE_STAT.match(stat_id)
        if influence:
            influences.append(influence.group(1))
            continue
        group = stat_id.split(".")[0]
        if stat_id not in texts:
            mods.append(f"{stat_id} (not in the recorded stat list)" + (f" at least {minimum:g}" if minimum is not None else ""))
            continue
        mods.append(_mod_line(group, normalise_stat_text(texts[stat_id]), minimum))
    return sorted(mods), sorted(influences)


def reconcile(
    target: Target, spec: BuySpec | None, export: Export, entries: list[PriceEntry], stat_texts: dict[str, str] | None = None
) -> dict[str, list[Disagreement]]:
    """Every slot of the target with the disagreements found there (empty list: the places agree).

    `stat_texts` is the trade site's stat list as {stat id: text}; by default the recorded one (`stats_full.json.gz`).
    """
    texts = _recorded_stat_texts() if stat_texts is None else stat_texts
    out: dict[str, list[Disagreement]] = {name: [] for name in slots(target, spec)}
    where_target = short(target.path)
    where_spec = short(spec.path) if spec else ""
    base_ids = base_ids_of(export.bases, target.base)

    def add(slot: str, place_a: str, place_b: str, value_a: str, value_b: str) -> None:
        out[slot].append(Disagreement(slot, place_a, place_b, str(value_a), str(value_b)))

    # --- the base exists; the start price and the buy spec exist ---------------------------------------------
    if not base_ids:
        add("target.base", f"{where_target}: base = {target.base!r}", "game data: no released base has this id or name", target.base, "no base")
    target_names = sorted({export.bases[i]["name"] for i in base_ids})
    target_classes = sorted({export.bases[i]["item_class"] for i in base_ids})
    if target.start not in ("bought", "given"):
        add("start_price.written", f"{where_target}: no `start:`", "the file does not say whether its start item is given or bought", "none", "not said")
    elif target.start == "bought" and target.start_price is None:
        add("start_price.written", f"{where_target}: start: bought", "no price key is written for it", "bought", "no price key")
    if target.start == "bought" and spec is None:
        named = f"start_price = {target.start_price!r}" if target.start_price else "no start_price"
        add("buy_spec.exists", f"{where_target}: start: bought, {named}", "no buy spec has this name", target.start_price or "none", "no buy spec")

    # --- the buy spec against the target's start item ---------------------------------------------------
    if spec is not None and base_ids:
        written = f"{where_target}: base = {target.base!r} ({', '.join(target_names)})"
        if spec.base_type is None:
            add("buy.base", written, f"{where_spec}: no base_type, so the price is for any {spec.category}", ", ".join(target_names), f"any {spec.category}")
        elif spec.base_type not in target_names:
            add("buy.base", written, f"{where_spec}: base_type = {spec.base_type!r}", ", ".join(target_names), spec.base_type)
        derived = sorted({TRADE_CATEGORY.get(item_class, f"?{item_class}") for item_class in target_classes})
        if spec.category not in derived:
            add("buy.category", f"{where_target}: base class {', '.join(target_classes)} = {', '.join(derived)}", f"{where_spec}: category = {spec.category!r}", ", ".join(derived), str(spec.category))
        accepted = bases_named(export.bases, spec.base_type) if spec.base_type else bases_of_category(export.bases, spec.category or "")
        accepted = _with_own_implicits(export, accepted, spec)
        different = _pool_differences(export, base_ids, accepted)
        if not accepted:
            add("buy.pool", written, f"{where_spec}: accepts no base of the game data", ", ".join(target_names), "no base")
        elif different:
            add("buy.pool", written, f"{where_spec}: accepts bases with another mod pool: {', '.join(different)}", ", ".join(target_names), "; ".join(different))
    if spec is not None:
        if spec.item_level_min != target.item_level:
            add("buy.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_spec}: item_level_min = {spec.item_level_min}", target.item_level, spec.item_level_min)
        if spec.rarity != target.rarity:
            add("buy.rarity", f"{where_target}: start item rarity = {target.rarity}", f"{where_spec}: rarity = {spec.rarity}", target.rarity, str(spec.rarity))
        if spec.influence != target.influence:
            add(
                "buy.influence",
                f"{where_target}: influence = {sorted(target.influence)}",
                f"{where_spec}: influence = {sorted(spec.influence)}",
                ",".join(sorted(target.influence)) or "none",
                ",".join(sorted(spec.influence)) or "none",
            )

    # --- each start mod against the game data and the buy spec ------------------------------------------
    own_texts = set()
    for mod in target.start_mods:
        record = export.mods.get(mod.mod)
        ladder_slot, values_slot = f"start_mod.{mod.mod}.ladder", f"start_mod.{mod.mod}.values"
        written = f"{where_target}: start_item mod {mod.mod}"
        derived_tier = None
        if record is None:
            add(ladder_slot, written, "game data: no mod has this id", mod.mod, "no mod")
            add(values_slot, written, "game data: no mod has this id", str(list(mod.values)), "no mod")
        else:
            own_texts.add(normalise_stat_text(record["text"]))
            tiers = _tiers_of(export, base_ids, mod.mod, target.influence)
            for base_id, tier in tiers.items():
                if tier is None:
                    add(ladder_slot, written, f"game data: {mod.mod} cannot spawn on {base_id}", mod.mod, f"cannot spawn on {base_id}")
            known = {tier for tier in tiers.values() if tier is not None}
            if len(known) > 1:
                add(ladder_slot, written, f"game data: the tier differs between the bases named {target.base!r}: {tiers}", mod.mod, f"differs: {sorted(known)}")
            elif known:
                derived_tier = next(iter(known))
            ranges = stat_ranges(record)
            if mod.values:
                if len(mod.values) != len(ranges):
                    add(values_slot, f"{written}: values = {list(mod.values)}", f"game data: {len(ranges)} stat(s) {ranges}", str(list(mod.values)), str(ranges))
                else:
                    for value, (low, high) in zip(mod.values, ranges, strict=True):
                        if not low <= value <= high:
                            add(values_slot, f"{written}: values = {list(mod.values)}", f"game data: range {ranges}", str(list(mod.values)), str(ranges))
                            break

        if spec is None:
            continue
        text = _text_of(export, mod.mod)
        buy = _find_buy_mod(spec, text) if text else None
        if buy is None:
            reason = "game data: no mod has this id" if text is None else f"{where_spec}: no mod with the text {text!r}"
            add(f"start_mod.{mod.mod}.buy_mod", written, reason, mod.mod, "not in the spec")
            continue
        if buy.fractured != mod.fractured:
            add(f"start_mod.{mod.mod}.buy_mod", f"{written}: fractured = {mod.fractured}", f"{where_spec}: {buy.stat!r} fractured = {buy.fractured}", f"fractured {mod.fractured}", f"fractured {buy.fractured}")
        ranges = stat_ranges(record)
        if len(ranges) != 1:
            raise FileFormatError(f"{mod.mod} has {len(ranges)} stats; the buy spec minimum check reads one-stat mods only")
        if derived_tier is None:
            continue  # the ladder slot already says why
        first = next(i for i, t in _tiers_of(export, base_ids, mod.mod, target.influence).items() if t is not None)
        lower = [
            stat_ranges(export.mods[other])[0][1]
            for other, tier in _ladder_on(export, first, mod.mod, target.influence).items()
            if tier > derived_tier
        ]
        floor = max(lower, default=None)
        ceiling = mod.values[0] if mod.values else ranges[0][1]
        slot = f"start_mod.{mod.mod}.buy_minimum"
        select = f"{where_spec}: {buy.stat!r} minimum = {buy.minimum}"
        wanted = f"game data: tier {derived_tier} is {ranges[0][0]}-{ranges[0][1]}, the tier below ends at {floor}; a minimum above {floor} and up to {ceiling} prices this tier"
        window = f"above {floor} and up to {ceiling}"
        if buy.minimum is None:
            add(slot, f"{written}: tier {derived_tier}", f"{select} (none): every tier of the mod matches. {wanted}", f"tier {derived_tier}: minimum {window}", "no minimum")
        elif (floor is not None and buy.minimum <= floor) or buy.minimum > ceiling:
            add(slot, f"{written}: tier {derived_tier}", f"{select}. {wanted}", f"tier {derived_tier}: minimum {window}", f"minimum {buy.minimum}")

    # --- buy spec mods the target does not have ---------------------------------------------------------
    if spec is not None:
        for buy in spec.mods:
            text = normalise_stat_text(buy.stat)
            if text not in own_texts and not buy.own:
                add(f"buy_mod.{text}.in_target", f"{where_spec}: mod {buy.stat!r}", f"{where_target}: the start item has no mod with this text", "not in the target", buy.stat)

    # --- the price entry ---------------------------------------------------------------------------------
    if target.start_price is not None:
        if not entries:
            add("price.entry", f"{where_target}: start_price = {target.start_price!r}", "committed price files: no file holds this name", target.start_price, "no entry")
        for entry in entries:
            where_entry = f"{short(entry.file)}: {entry.key!r}"
            name = priced_base_name(entry)
            category = priced_category(entry)
            priced_ids = bases_named(export.bases, name) if name else (bases_of_category(export.bases, category) if category else [])
            if name is None:
                add("price.base", f"{where_target}: base = {target.base!r}", f"{where_entry} names no base (category {category}), so it prices any base", ", ".join(target_names), f"any {category}" if category else "no base")
            elif len(priced_ids) != 1 or priced_ids != base_ids:
                shared = f"the name {name!r} is shared by {len(priced_ids)} bases {priced_ids}" if len(priced_ids) != 1 else f"the name {name!r} is base {priced_ids[0]}"
                target_side = f"{where_target}: base = {target.base!r}" + (f" (the name is shared by {base_ids})" if len(base_ids) > 1 else f" = {base_ids}")
                add("price.base", target_side, f"{where_entry}: {shared}; a price is keyed by name, not by base id", ", ".join(base_ids), ", ".join(priced_ids) or "no base")
            different = _pool_differences(export, base_ids, priced_ids)
            if different:
                add("price.pool", f"{where_target}: base = {target.base!r}", f"{where_entry} prices bases with another mod pool: {', '.join(different)}", ", ".join(target_names), "; ".join(different))
            level, origin = priced_item_level(entry)
            if level is None:
                add("price.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_entry}: records no item level", target.item_level, "none")
            elif origin == "label":
                add("price.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_entry}: only the key says item level {level}; the entry records none, so the check cannot tell", target.item_level, f"cannot tell (label {level})")
            elif level != target.item_level:
                add("price.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_entry}: item level {level} ({origin})", target.item_level, level)
            rarity = priced_rarity(entry)
            if rarity is not None and rarity != target.rarity:
                add("price.rarity", f"{where_target}: start item rarity = {target.rarity}", f"{where_entry}: the search asked for rarity {rarity}", target.rarity, rarity)
            if entry.query:  # a stand-in has no stored search: nothing here to read (its row is price.source)
                priced_mods, priced_influences = _priced_mods(entry, texts)
                if sorted(target.influence) != [name.lower() for name in priced_influences]:
                    add(
                        "price.influence", f"{where_target}: influence = {sorted(target.influence)}", f"{where_entry}: the search asked for influence {priced_influences}",
                        ",".join(sorted(target.influence)) or "none", ",".join(priced_influences) or "none",
                    )  # fmt: skip
                corrupted = priced_corrupted(entry)
                if corrupted != str(target.corrupted).lower():
                    shown = {"true": "corrupted", "false": "not corrupted"}.get(corrupted, corrupted)
                    add(
                        "price.corrupted", f"{where_target}: start item corrupted = {target.corrupted}", f"{where_entry}: the search asked for corrupted = {corrupted}",
                        "corrupted" if target.corrupted else "not corrupted", shown,
                    )  # fmt: skip
                if spec is not None:
                    wanted = _wanted_mods(spec)
                    if wanted != priced_mods:
                        add(
                            "price.mods", f"{where_spec}: mods {wanted}", f"{where_entry}: the search asked for mods {priced_mods}",
                            "; ".join(wanted) or "no mod", "; ".join(priced_mods) or "no mod",
                        )  # fmt: skip
                    fractured_wanted = any(mod.fractured for mod in spec.mods)
                    if priced_fractured_flag(entry) != fractured_wanted:
                        words = {True: "fractured_item: true", False: "fractured_item: not asked"}
                        add(
                            "price.mods", f"{where_spec}: a fractured mod is {'' if fractured_wanted else 'not '}wanted", f"{where_entry}: the search {'did' if priced_fractured_flag(entry) else 'did not'} ask for a fractured item",
                            words[fractured_wanted], words[not fractured_wanted],
                        )  # fmt: skip
            if entry.source != TRADE_SOURCE:
                add("price.source", f"{where_target}: start item bought on the trade site", f"{where_entry}: source {entry.source!r}, a stand-in for a trade price", "trade-api", str(entry.source))
    return out


def reconcile_files(
    target: Target, specs: list[BuySpec], export: Export, prices_dir: Path | None = None, stat_texts: dict[str, str] | None = None
) -> dict[str, list[Disagreement]]:
    """`reconcile` with the buy spec and the committed price entries found from the target's own keys."""
    spec = buy_spec_of(target, specs)
    files = price_files_of(target) if prices_dir is None else price_files_of(target, prices_dir)
    entries = [entry for path in files if (entry := read_price_entry(path, target.start_price))]
    return reconcile(target, spec, export, entries, stat_texts)
