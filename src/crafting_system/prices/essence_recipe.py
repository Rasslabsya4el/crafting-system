"""The lower essence tiers priced from the vendor upgrade recipe (#885, the owner's decision of 2026-11-13).

Three essences of one tier and type make one of the next tier of the same type at a vendor (claim `essence.vendor_upgrade_recipe`),
so nobody trades the lower tiers: their market rows are few, inflated and odd (in the 3.29 file of league day 7 a Muttering Essence of
Fear stood at 87 Chaos, and many Wailing and Weeping essences above their own Deafening tier). The owner's decision: each essence type
keeps one market price, and the lower tiers are priced from the recipe. The rule, per essence type ("Essence of Fear"):

* the **highest tier the file has a market row for** (the Deafening one, wherever the file prices it) keeps its price: the type's
  one market price, the **anchor** of its chain;
* **every tier below it costs one third of the next tier up**: Shrieking = Deafening / 3, Screaming = Shrieking / 3, and so on down,
  **whatever row of its own the tier has, a cheaper one too**. A lower tier's market is thin in both directions: a cheap odd row
  (one seller, a fraction of a unit) is no more a price a plan can buy at than a dear one, and it would make a route look cheaper
  than it is. The row it replaces is kept in the new row's `detail`;
* a **hand price** (an override) and a default are the user's and the model's own numbers: kept, dearer or cheaper, and the tiers
  below are a third of them (it is the anchor of the tiers below it).

So no lower tier ever costs more than a third of its upper tier. A row the rule writes says so in the row (OR-7, OR-23): source
`upgrade-recipe`, the tier it is a third of and that tier's price, the anchor and how many tiers above it stands, the row it
replaced, and a provenance of kind `upgrade-recipe` with the league and day of the anchor. `price_marks` marks it as an approximate
input and judges the anchor in its place (its league, its day, its depth for a third of the uses per tier), since a recipe price is
as good as the market price it rests on and no better.

`wanted` names lower tiers the file has no row for (an essence a method spends): they get a row too, and so does every tier between
a named one and the anchor, since the chain passes through it. Two cases have a note and no change: a type whose anchor is not its
Deafening tier (nothing prices that row from above, so it stays whatever it is), and a type that has recipe rows but no market row
left to anchor them. A type the file prices at no tier stays unpriced, and the corrupted essences (Delirium, Horror, Hysteria,
Insanity) and Essence of Desolation, which have no tier, are not touched.

The hand prices live in a file of their own and are laid over the price file when it is read (`load_prices`), after any fetch: a
file that holds recipe rows has the rule applied again there, so an override of one tier reaches the tiers below it.
Pure: no I/O, no clock. Applying the rule twice gives the same file.
"""

from collections.abc import Iterable
from dataclasses import replace

from crafting_system.rules import get_rule

from .price_file import PriceEntry, PriceFile
from .price_marks import provenance_of
from .provenance import DEFAULT, OVERRIDE, RECIPE, Provenance

__all__ = ["PER_UPGRADE", "RECIPE_SOURCE", "TIERS", "apply_upgrade_recipe", "has_recipe_rows", "tier_of"]

VENDOR_UPGRADE_RECIPE = get_rule("essence.vendor_upgrade_recipe")
TIERS = ("Whispering", "Muttering", "Weeping", "Wailing", "Screaming", "Shrieking", "Deafening")  # lowest first, as the game names them
PER_UPGRADE: int = VENDOR_UPGRADE_RECIPE.value  # essences of one tier and type the vendor takes for one of the next tier
RECIPE_SOURCE = "upgrade-recipe"
_MIDDLE = " Essence of "


def tier_of(name: str) -> tuple[int, str] | None:
    """(the tier's place in `TIERS`, the essence type) of a tiered essence's name: "Shrieking Essence of Spite" is (5, "Essence of Spite");
    None for any other name ("Essence of Horror", "Deafening Catalyst")."""
    word, middle, kind = name.partition(_MIDDLE)
    if not middle or word not in TIERS or not kind:
        return None
    return TIERS.index(word), f"Essence of {kind}"


def has_recipe_rows(price_file: PriceFile) -> bool:
    """Whether the file was built under the rule: some row of it is a recipe row."""
    return any(entry.source == RECIPE_SOURCE for entry in price_file.prices.values())


def _is_own_number(entry: PriceEntry, price_file: PriceFile) -> bool:
    p = provenance_of(entry, price_file)
    return p is not None and p.kind in (OVERRIDE, DEFAULT)


def _replaced(existing: PriceEntry | None) -> dict[str, object] | None:
    """What the rule replaced at this name: the row there now, or, when that is the rule's own row, what it first replaced."""
    if existing is None:
        return None
    if existing.source != RECIPE_SOURCE:
        return {"chaos": existing.chaos, "source": existing.source}
    was = (existing.detail or {}).get("replaced")
    if isinstance(was, dict) and isinstance(was.get("chaos"), int | float) and not isinstance(was.get("chaos"), bool) and isinstance(was.get("source"), str):
        return {"chaos": was["chaos"], "source": was["source"]}
    return None


def _derived(upper_name: str, upper: PriceEntry, anchor_name: str, anchor: PriceEntry, steps: int, existing: PriceEntry | None, price_file: PriceFile) -> PriceEntry:
    rests_on = provenance_of(anchor, price_file)
    league = rests_on.league if rests_on is not None else price_file.league
    day = rests_on.date if rests_on is not None else price_file.fetched_at.date().isoformat()
    note = (
        f"vendor upgrade recipe (#885): one third of {upper_name} ({upper.chaos:.4g} Chaos); {PER_UPGRADE} essences of a tier make one of the"
        " next tier of the same type, so the lower tiers have no market of their own"
    )
    detail: dict[str, object] = {
        "league": league, "date": day, "recipe": "essence-upgrade", "of": upper_name, "of_chaos": upper.chaos, "per": PER_UPGRADE,
        "anchor": anchor_name, "steps": steps,
    }  # fmt: skip
    replaced = _replaced(existing)
    if replaced is not None:
        note += f"; it replaces the row of {replaced['chaos']:.4g} Chaos ({replaced['source']})"
        detail["replaced"] = replaced
    return PriceEntry(upper.chaos / PER_UPGRADE, RECIPE_SOURCE, note, detail, Provenance(RECIPE, league, day))


def apply_upgrade_recipe(price_file: PriceFile, wanted: Iterable[str] = ()) -> tuple[PriceFile, list[str]]:
    """`price_file` with the rule of this module applied, and its notes: one per row the rule wrote or changed ("<name>: <price> Chaos,
    one third of ..."), and one per type it could not price from its Deafening tier ("<name>: kept, ...").

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
        market = [index for index, name in tiers.items() if name in price_file.prices and price_file.prices[name].source != RECIPE_SOURCE]
        if not market:
            stale = [name for name in tiers.values() if name in price_file.prices]
            if stale:
                notes.append(f"{stale[0]}: kept, a recipe row of {kind} with no market row of its type left to rest on")
            continue  # no tier of the type has a market price to start from
        top = max(market)
        anchor_name, anchor, steps = tiers[top], price_file.prices[tiers[top]], 0
        if top != len(TIERS) - 1:
            notes.append(f"{anchor_name}: kept, the highest tier of {kind} the file has a market row for; no Deafening row prices it from above")
        upper_name, upper = anchor_name, anchor
        for index in range(top - 1, min(tiers) - 1, -1):
            name = f"{TIERS[index]} {kind}"
            existing = price_file.prices.get(name)
            if existing is not None and _is_own_number(existing, price_file):
                anchor_name, anchor, steps = name, existing, 0
                upper_name, upper = name, existing
                continue
            steps += 1
            made = _derived(upper_name, upper, anchor_name, anchor, steps, existing, price_file)
            if existing != made:
                was = "no row" if existing is None else f"{existing.chaos:.4g} Chaos ({existing.source})"
                notes.append(f"{name}: {made.chaos:.4g} Chaos, one third of {upper_name}; before: {was}")
            prices[name] = made
            upper_name, upper = name, made
    return replace(price_file, prices=prices), notes
