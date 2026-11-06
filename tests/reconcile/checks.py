"""The reconciliation: for one target, every fact written in two places, one named slot per fact.

`slots(target, spec)` lists the slot names from the two YAML files alone (no game data), so the set of
checks never depends on what the data says. `reconcile(...)` returns, for each slot, the disagreements
found there; an empty list means the places agree. A disagreement names both places and what each says,
which is also the row of the disagreement table.

Slots:

- `target.base`: the base the target names exists in the game data.
- `buy.base`, `buy.category`, `buy.item_level`, `buy.rarity`, `buy.influence`: the target's start item
  against the buy spec whose `name` is the target's `start_price`.
- `start_mod.<mod>.tier`, `.values`: a start mod's hand-written tier and values against the game data.
- `start_mod.<mod>.buy_mod`, `.buy_minimum`: a start mod against the buy spec's mod of the same text,
  and the spec's minimum against the tier (OR-3: the tier the price was taken for).
- `buy_mod.<stat>.in_target`: a buy spec mod the target's start item does not have.
- `price.entry`, `price.base`, `price.item_level`: the start-price entry against the target's base, by
  base id (several bases share a name), and item level.
"""

from dataclasses import dataclass
from pathlib import Path

from .export import REPO_ROOT, Export
from .files import (
    BuyMod,
    BuySpec,
    FileFormatError,
    PriceEntry,
    Target,
    buy_spec_of,
    price_files_of,
    priced_base_name,
    priced_category,
    priced_item_level,
    read_price_entry,
)
from .ladder import TRADE_CATEGORY, base_ids_of, bases_named, ladder, normalise_stat_text, stat_ranges


@dataclass(frozen=True)
class Disagreement:
    """Two places that say different things about one fact."""

    slot: str
    place_a: str
    place_b: str

    def __str__(self) -> str:
        return f"{self.slot}: {self.place_a}  <>  {self.place_b}"


def short(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def slots(target: Target, spec: BuySpec | None) -> list[str]:
    """The slot names for this target and its buy spec, from the two files alone."""
    names = ["target.base"]
    if spec is not None:
        names += ["buy.base", "buy.category", "buy.item_level", "buy.rarity", "buy.influence"]
    for mod in target.start_mods:
        names += [f"start_mod.{mod.mod}.tier", f"start_mod.{mod.mod}.values"]
        if spec is not None:
            names += [f"start_mod.{mod.mod}.buy_mod", f"start_mod.{mod.mod}.buy_minimum"]
    if spec is not None:
        names += [f"buy_mod.{normalise_stat_text(mod.stat)}.in_target" for mod in spec.mods]
    if target.start_price is not None:
        names += ["price.entry", "price.base", "price.item_level"]
    return names


def _find_buy_mod(spec: BuySpec, text: str) -> BuyMod | None:
    found = [mod for mod in spec.mods if normalise_stat_text(mod.stat) == text]
    if len(found) > 1:
        raise FileFormatError(f"{spec.path.name}: the mod {text!r} is listed {len(found)} times")
    return found[0] if found else None


def _text_of(export: Export, mod_id: str) -> str | None:
    mod = export.mods.get(mod_id)
    return normalise_stat_text(mod["text"]) if mod else None


def _tiers_of(export: Export, base_ids: list[str], mod_id: str) -> dict[str, int | None]:
    """The tier of `mod_id` on each base id: None where the mod cannot spawn on the base."""
    result = {}
    for base_id in base_ids:
        tiers = ladder(export.mods, export.bases[base_id]["tags"], mod_id)
        result[base_id] = tiers.get(mod_id)
    return result


def reconcile(
    target: Target, spec: BuySpec | None, export: Export, entries: list[PriceEntry]
) -> dict[str, list[Disagreement]]:
    """Every slot of the target with the disagreements found there (empty list: the places agree)."""
    out: dict[str, list[Disagreement]] = {name: [] for name in slots(target, spec)}
    where_target = short(target.path)
    where_spec = short(spec.path) if spec else ""
    base_ids = base_ids_of(export.bases, target.base)

    def add(slot: str, place_a: str, place_b: str) -> None:
        out[slot].append(Disagreement(slot, place_a, place_b))

    # --- the base exists --------------------------------------------------------------------------------
    if not base_ids:
        add("target.base", f"{where_target}: base = {target.base!r}", "game data: no released base has this id or name")
    target_names = sorted({export.bases[i]["name"] for i in base_ids})
    target_classes = sorted({export.bases[i]["item_class"] for i in base_ids})

    # --- the buy spec against the target's start item ---------------------------------------------------
    if spec is not None and base_ids:
        written = f"{where_target}: base = {target.base!r} ({', '.join(target_names)})"
        if spec.base_type is None:
            add("buy.base", written, f"{where_spec}: no base_type, so the price is for any {spec.category}")
        elif spec.base_type not in target_names:
            add("buy.base", written, f"{where_spec}: base_type = {spec.base_type!r}")
        derived = sorted({TRADE_CATEGORY.get(item_class, f"?{item_class}") for item_class in target_classes})
        if spec.category not in derived:
            add("buy.category", f"{where_target}: base class {', '.join(target_classes)} = {', '.join(derived)}", f"{where_spec}: category = {spec.category!r}")
    if spec is not None:
        if spec.item_level_min != target.item_level:
            add("buy.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_spec}: item_level_min = {spec.item_level_min}")
        if spec.rarity != target.rarity:
            add("buy.rarity", f"{where_target}: start item rarity = {target.rarity}", f"{where_spec}: rarity = {spec.rarity}")
        if spec.influence != target.influence:
            add(
                "buy.influence",
                f"{where_target}: influence = {sorted(target.influence)}",
                f"{where_spec}: influence = {sorted(spec.influence)}",
            )

    # --- each start mod against the game data and the buy spec ------------------------------------------
    own_texts = set()
    for mod in target.start_mods:
        record = export.mods.get(mod.mod)
        tier_slot, values_slot = f"start_mod.{mod.mod}.tier", f"start_mod.{mod.mod}.values"
        written = f"{where_target}: start_item mod {mod.mod}"
        derived_tier = None
        if record is None:
            add(tier_slot, written, "game data: no mod has this id")
            add(values_slot, written, "game data: no mod has this id")
        else:
            own_texts.add(normalise_stat_text(record["text"]))
            tiers = _tiers_of(export, base_ids, mod.mod)
            for base_id, tier in tiers.items():
                if tier is None:
                    add(tier_slot, written, f"game data: {mod.mod} cannot spawn on {base_id}")
            known = {tier for tier in tiers.values() if tier is not None}
            if len(known) > 1:
                add(tier_slot, written, f"game data: the tier differs between the bases named {target.base!r}: {tiers}")
            elif known:
                derived_tier = next(iter(known))
                if mod.tier is not None and mod.tier != derived_tier:
                    first = next(i for i, t in tiers.items() if t is not None)
                    size = len(ladder(export.mods, export.bases[first]["tags"], mod.mod))
                    add(tier_slot, f"{written}: tier = {mod.tier}", f"game data: tier {derived_tier} of {size} on {first} (by required level)")
            ranges = stat_ranges(record)
            if mod.values:
                if len(mod.values) != len(ranges):
                    add(values_slot, f"{written}: values = {list(mod.values)}", f"game data: {len(ranges)} stat(s) {ranges}")
                else:
                    for value, (low, high) in zip(mod.values, ranges, strict=True):
                        if not low <= value <= high:
                            add(values_slot, f"{written}: values = {list(mod.values)}", f"game data: range {ranges}")
                            break

        if spec is None:
            continue
        text = _text_of(export, mod.mod)
        buy = _find_buy_mod(spec, text) if text else None
        if buy is None:
            reason = "game data: no mod has this id" if text is None else f"{where_spec}: no mod with the text {text!r}"
            add(f"start_mod.{mod.mod}.buy_mod", written, reason)
            continue
        if buy.fractured != mod.fractured:
            add(f"start_mod.{mod.mod}.buy_mod", f"{written}: fractured = {mod.fractured}", f"{where_spec}: {buy.stat!r} fractured = {buy.fractured}")
        ranges = stat_ranges(record)
        if len(ranges) != 1:
            raise FileFormatError(f"{mod.mod} has {len(ranges)} stats; the buy spec minimum check reads one-stat mods only")
        if derived_tier is None:
            continue  # the tier slot already says why
        first = next(i for i, t in _tiers_of(export, base_ids, mod.mod).items() if t is not None)
        lower = [
            stat_ranges(export.mods[other])[0][1]
            for other, tier in ladder(export.mods, export.bases[first]["tags"], mod.mod).items()
            if tier > derived_tier
        ]
        floor = max(lower, default=None)
        ceiling = mod.values[0] if mod.values else ranges[0][1]
        slot = f"start_mod.{mod.mod}.buy_minimum"
        select = f"{where_spec}: {buy.stat!r} minimum = {buy.minimum}"
        wanted = f"game data: tier {derived_tier} is {ranges[0][0]}-{ranges[0][1]}, the tier below ends at {floor}; a minimum above {floor} and up to {ceiling} prices this tier"
        if buy.minimum is None:
            add(slot, f"{written}: tier {derived_tier}", f"{select} (none): every tier of the mod matches. {wanted}")
        elif (floor is not None and buy.minimum <= floor) or buy.minimum > ceiling:
            add(slot, f"{written}: tier {derived_tier}", f"{select}. {wanted}")

    # --- buy spec mods the target does not have ---------------------------------------------------------
    if spec is not None:
        for buy in spec.mods:
            text = normalise_stat_text(buy.stat)
            if text not in own_texts:
                add(f"buy_mod.{text}.in_target", f"{where_spec}: mod {buy.stat!r}", f"{where_target}: the start item has no mod with this text")

    # --- the price entry ---------------------------------------------------------------------------------
    if target.start_price is not None:
        if not entries:
            add("price.entry", f"{where_target}: start_price = {target.start_price!r}", "committed price files: no file holds this name")
        target_ids = base_ids
        for entry in entries:
            where_entry = f"{short(entry.file)}: {entry.key!r}"
            name = priced_base_name(entry)
            priced_ids = bases_named(export.bases, name) if name else []
            if name is None:
                add("price.base", f"{where_target}: base = {target.base!r}", f"{where_entry} names no base (category {priced_category(entry)}), so it prices any base")
            elif len(priced_ids) != 1 or priced_ids != target_ids:
                shared = f"the name {name!r} is shared by {len(priced_ids)} bases {priced_ids}" if len(priced_ids) != 1 else f"the name {name!r} is base {priced_ids[0]}"
                target_side = f"{where_target}: base = {target.base!r}" + (f" (the name is shared by {target_ids})" if len(target_ids) > 1 else f" = {target_ids}")
                add("price.base", target_side, f"{where_entry}: {shared}; a price is keyed by name, not by base id")
            level = priced_item_level(entry)
            if level != target.item_level:
                add("price.item_level", f"{where_target}: item_level = {target.item_level}", f"{where_entry}: item level {level}")
    return out


def reconcile_files(target: Target, specs: list[BuySpec], export: Export, prices_dir: Path | None = None) -> dict[str, list[Disagreement]]:
    """`reconcile` with the buy spec and the committed price entries found from the target's own keys."""
    spec = buy_spec_of(target, specs)
    files = price_files_of(target) if prices_dir is None else price_files_of(target, prices_dir)
    entries = [entry for path in files if (entry := read_price_entry(path, target.start_price))]
    return reconcile(target, spec, export, entries)
