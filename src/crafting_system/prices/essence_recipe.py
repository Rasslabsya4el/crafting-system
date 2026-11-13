"""The lower essence tiers priced from the vendor upgrade recipe (#885, the owner's decision of 2026-11-13).

Three essences of one tier and type make one of the next tier of the same type at a vendor, so nobody trades the lower tiers: their
market rows are few, inflated and odd (in the 3.29 file of league day 7 a Muttering Essence of Fear stood at 87 Chaos, and many
Wailing and Weeping essences above their own Deafening tier). The rule, per essence type ("Essence of Fear"):

* the **highest tier the file prices** (the Deafening one, wherever the game has it) keeps its price: it is the type's one market price;
* **every tier below it costs one third of the next tier up**: Shrieking = Deafening / 3, Screaming = Shrieking / 3, and so on down;
* a lower tier's own row **wins only when it is cheaper and a plain fact**: a market reading of the file's own league and day, as
  `price_marks` judges it (not a previous league's price, not a stand-in of another day, not a thin market). A player buys the
  cheaper of the two, and a marked row is no evidence of a cheaper market. The next tier down is then a third of that row;
* a hand price (an override) and a default are the user's and the model's own numbers: kept, and the tier below is a third of them.

So no lower tier ever costs more than a third of its upper tier. A row the rule writes says so in the row (OR-7, OR-23): source
`upgrade-recipe`, the tier it is a third of and that tier's price in `detail`, the row it replaced, and a provenance of kind
`upgrade-recipe` with the league and day of the price it rests on, which `price_marks` marks as an approximate input.

`wanted` names lower tiers the file has no row for (an essence a method spends): they get a row too, and so does every tier between
a named one and the type's priced top, since the chain passes through it. A type the file prices at no tier stays unpriced, and the
corrupted essences (Delirium, Horror, Hysteria, Insanity) and Essence of Desolation, which have no tier, are not touched.
Pure: no I/O, no clock. Applying the rule twice gives the same file.
"""

from collections.abc import Iterable
from dataclasses import replace

from .price_file import PriceEntry, PriceFile
from .price_marks import MARKET_KINDS, price_marks, provenance_of
from .provenance import DEFAULT, OVERRIDE, RECIPE, Provenance

__all__ = ["PER_UPGRADE", "RECIPE_SOURCE", "TIERS", "apply_upgrade_recipe", "tier_of"]

TIERS = ("Whispering", "Muttering", "Weeping", "Wailing", "Screaming", "Shrieking", "Deafening")  # lowest first, as the game names them
PER_UPGRADE = 3  # essences of one tier and type the vendor takes for one of the next tier
RECIPE_SOURCE = "upgrade-recipe"
_MIDDLE = " Essence of "


def tier_of(name: str) -> tuple[int, str] | None:
    """(the tier's place in `TIERS`, the essence type) of a tiered essence's name: "Shrieking Essence of Spite" is (5, "Essence of Spite");
    None for any other name ("Essence of Horror", "Deafening Catalyst")."""
    word, middle, kind = name.partition(_MIDDLE)
    if not middle or word not in TIERS or not kind:
        return None
    return TIERS.index(word), f"Essence of {kind}"


def _is_own_number(entry: PriceEntry, price_file: PriceFile) -> bool:
    p = provenance_of(entry, price_file)
    return p is not None and p.kind in (OVERRIDE, DEFAULT)


def _is_plain_reading(entry: PriceEntry, price_file: PriceFile) -> bool:
    """A recorded market reading of the file's own league and day with no mark against it; its depth is not judged (no plan is at hand)."""
    p = provenance_of(entry, price_file)
    return p is not None and p.recorded and p.kind in MARKET_KINDS and not price_marks(entry, price_file, 0.0)


def _derived(name: str, upper_name: str, upper: PriceEntry, existing: PriceEntry | None, price_file: PriceFile) -> PriceEntry:
    rests_on = provenance_of(upper, price_file)
    league = rests_on.league if rests_on is not None else price_file.league
    day = rests_on.date if rests_on is not None else price_file.fetched_at.date().isoformat()
    note = (
        f"vendor upgrade recipe (#885): one third of {upper_name} ({upper.chaos:.4g} Chaos); {PER_UPGRADE} essences of a tier make one of the"
        " next tier of the same type, so the lower tiers have no market of their own"
    )
    detail: dict[str, object] = {"league": league, "date": day, "recipe": "essence-upgrade", "of": upper_name, "of_chaos": upper.chaos, "per": PER_UPGRADE}
    replaced = None
    if existing is not None and existing.source != RECIPE_SOURCE:
        replaced = {"chaos": existing.chaos, "source": existing.source}
    elif existing is not None and isinstance((existing.detail or {}).get("replaced"), dict):  # the rule applied again: what it first replaced is kept
        replaced = dict(existing.detail["replaced"])
    if replaced is not None:
        note += f"; it replaces the row of {replaced['chaos']:.4g} Chaos ({replaced['source']})"
        detail["replaced"] = replaced
    return PriceEntry(upper.chaos / PER_UPGRADE, RECIPE_SOURCE, note, detail, Provenance(RECIPE, league, day))


def apply_upgrade_recipe(price_file: PriceFile, wanted: Iterable[str] = ()) -> tuple[PriceFile, list[str]]:
    """`price_file` with the rule of this module applied, and one note per row the rule wrote or changed, in the file's order of types.

    `wanted` are names that need a price whether or not the file has a row for them; a name of it that is no tiered essence is ignored.
    """
    types: dict[str, dict[int, str]] = {}
    for name in (*price_file.prices, *wanted):
        found = tier_of(name)
        if found is not None:
            types.setdefault(found[1], {})[found[0]] = name
    prices = dict(price_file.prices)
    notes: list[str] = []
    for kind, tiers in types.items():
        priced = [index for index, name in tiers.items() if name in price_file.prices]
        if not priced:
            continue  # no tier of the type has a price to start from
        top = max(priced)
        upper_name, upper = tiers[top], price_file.prices[tiers[top]]
        for index in range(top - 1, min(tiers) - 1, -1):
            name = f"{TIERS[index]} {kind}"
            existing = price_file.prices.get(name)
            limit = upper.chaos / PER_UPGRADE
            if existing is not None and (_is_own_number(existing, price_file) or (existing.chaos < limit and _is_plain_reading(existing, price_file))):
                upper_name, upper = name, existing
                continue
            made = _derived(name, upper_name, upper, existing, price_file)
            if existing != made:
                was = "no row" if existing is None else f"{existing.chaos:.4g} Chaos ({existing.source})"
                notes.append(f"{name}: {made.chaos:.4g} Chaos, one third of {upper_name}; before: {was}")
            prices[name] = made
            upper_name, upper = name, made
    return replace(price_file, prices=prices), notes
