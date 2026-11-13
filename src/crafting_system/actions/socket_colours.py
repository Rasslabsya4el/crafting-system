"""The Chromatic Orb, the Omen of Trichromatism and the bench's colour crafts: the actions that change the colours of the sockets of a weapon or armour (ticket #229, B6 S3).

Like the Jeweller's Orb and the Orb of Fusing of `socket_orbs.py` they are finish actions (ADR-0045): they change the **colours** of the sockets and
**nothing else**. The count, the link groups, every mod, the quality and the implicits are as they were; the contract suite checks it
(`Adds.socket_action(colours=True)`). They are not planner kinds (`planner=False`): the finish of a target that names sockets solves them on its
own and adds its value to every goal state (ticket #231, `abstraction/_finish.py`). The same refusals as the sibling actions: `NotApplicableError` for a corrupted item and for a class with no socket table, `OutOfScopeError`
for an item with no stated sockets or with an Abyssal-socket mod (`_accept` of `socket_orbs.py`).

**The roll** (ADR-0047, Siveran's formula; `sockets.chromatic_roll_then_force`, `sockets.chromatic_nonwhite_chance`, none of them marked): every socket is
rolled independently, non-white with `p = 0.00375 * max(item level - 14, 1) * (1 + min(quality, 30) / 100)` (`nonwhite_chance`; the quality is the plain
quality of the item) and white otherwise. A non-white socket takes its colour by the attribute requirements of the base (`colour_weights`,
`sockets.chromatic_natural_colour_weights`): with one attribute `a` that colour `0.9 (10 + a) / (a + 20)` and each other `0.05 + 0.9 * 5 / (a + 20)`; with two
attributes `0.9 a / total` and the missing colour `0.1`; with three `a / total`. **Only if every socket rolled white** the first socket is made non-white
(`sockets.chromatic_one_socket_always_coloured`: so a one-socket item is always coloured), with its colour drawn by the weights of the plan or, in the second
reading, by one third of the weights plus two thirds uniform (`sockets.chromatic_forced_socket_colour`, `approximate`): the **rule axis**
`chromatic_forced_colour` (ADR-0033; readings `siveran_weights`, the plan, and `flatter_second_reading`). The base's requirements are read from the
data (`BaseItem.attribute_requirements`) and ignore mods that change them (`sockets.chromatic_ignores_requirement_mods`, `approximate`). A base that asks for no
attribute at all has no weights in any admitted rule (`OutOfScopeError`).

**A Chromatic Orb cannot return the colours the item already has** (`sockets.chromatic_never_repeats_the_current_colours`, `approximate`): the result is
the roll conditioned on differing from the current colours, as an ordered list. It applies to every Chromatic Orb use, with the Omen too, and not to the bench.

**The Omen of Trichromatism** (`omen=True`) makes the next Chromatic Orb give at least one red, one green and one blue socket: the roll conditioned on
holding all three (`sockets.omen_of_trichromatism_conditions_the_roll`, `approximate`), and on differing from the current colours. It needs three sockets
and is refused below (`sockets.omen_of_trichromatism_below_three_sockets`, `approximate`); the kind does not offer it there. It rolls no forced colour (three
colours cannot come from the forced rule), so it has no axis.

**The bench's colour crafts** (`BenchSocketColours(minimum)`, 2, 3, 4 non-white sockets for 5, 20, 75 Chromatic Orbs, `sockets.bench_colour_cost`, exact) are the
independent roll conditioned on at least `minimum` non-white sockets (`sockets.bench_at_least_n_non_white_is_a_conditioned_roll`, `approximate`); they exclude no
colours, and ask for at least `minimum` sockets. A craft is priced as its orb count times the orb price, by the names of the game data.

**As a burn of Hinekora's Lock** (ticket #295, B8-3, ADR-0056): the plain Chromatic Orb declares `burn` (the Omen does not). It changes no mod and always changes the
colours, so `burn_outcomes` is its `outcomes` with one white socket assumed when the item states none (`burn.chromatic_socket_assumption`, `approximate`, listed
by `burn_claims`, not by `claims`); `burn_refusal` is the same refusals without rolling.

**Prices.** The Chromatic Orb and the Omen are priced by the name the game data gives them (`sockets.chromatic_orb_cost`, `sockets.omen_of_trichromatism_cost`;
`prices.price_names` holds the same names). **Memory Strands** (ADR-0041): none draws mods or spends strands, so each declares `StrandUse.untouched`.
"""

import itertools
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache

from crafting_system.data import BenchOption, GameData
from crafting_system.items import Item, PlainQuality, SocketColour, Sockets, class_maximum
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Axis, BurnKeeps, Reading, Reads, SocketRule
from .errors import NotApplicableError, OutOfScopeError
from .socket_orbs import SocketOutcomes, _accept, _bench_offers, _class_maximum_of, _cost, _offered, _outcomes
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY, StrandUse

__all__ = [
    "BenchSocketColours",
    "CHROMATIC_FORCED_COLOUR",
    "ChromaticOrb",
    "ColourOutcomes",
    "OMEN_MINIMUM_SOCKETS",
    "colour_roll",
    "colour_weights",
    "nonwhite_chance",
    "roll_colours",
]

CLASS_MAXIMUM = get_rule("sockets.class_maximum_sockets")
ROLL_THEN_FORCE = get_rule("sockets.chromatic_roll_then_force")
NONWHITE_CHANCE = get_rule("sockets.chromatic_nonwhite_chance")
NATURAL_COLOUR_WEIGHTS = get_rule("sockets.chromatic_natural_colour_weights")
COLOUR_BY_REQUIREMENTS = get_rule("sockets.chromatic_colour_weighted_by_requirements")
FORCED_SOCKET_COLOUR = get_rule("sockets.chromatic_forced_socket_colour")
ONE_SOCKET_ALWAYS_COLOURED = get_rule("sockets.chromatic_one_socket_always_coloured")
NEVER_REPEATS = get_rule("sockets.chromatic_never_repeats_the_current_colours")
IGNORES_REQUIREMENT_MODS = get_rule("sockets.chromatic_ignores_requirement_mods")
OMEN_OF_TRICHROMATISM = get_rule("sockets.omen_of_trichromatism")
OMEN_CONDITIONS_THE_ROLL = get_rule("sockets.omen_of_trichromatism_conditions_the_roll")
OMEN_BELOW_THREE_SOCKETS = get_rule("sockets.omen_of_trichromatism_below_three_sockets")
BENCH_COLOUR_COST = get_rule("sockets.bench_colour_cost")
BENCH_CONDITIONED_ROLL = get_rule("sockets.bench_at_least_n_non_white_is_a_conditioned_roll")
BENCH_ON_CORRUPTED_COSTS_VAAL = get_rule("sockets.bench_on_corrupted_costs_vaal")
CHROMATIC_ORB_COST = get_rule("sockets.chromatic_orb_cost")
OMEN_OF_TRICHROMATISM_COST = get_rule("sockets.omen_of_trichromatism_cost")
BURN_SOCKET_ASSUMPTION = get_rule("burn.chromatic_socket_assumption")

ONE = Fraction(1)
COLOURS = (SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE)  # strength, dexterity, intelligence
SIVERAN_WEIGHTS, FLATTER_SECOND_READING = "siveran_weights", "flatter_second_reading"
CHROMATIC_FORCED_COLOUR = Axis("chromatic_forced_colour", (SIVERAN_WEIGHTS, FLATTER_SECOND_READING), SIVERAN_WEIGHTS)
OMEN_MINIMUM_SOCKETS = 3
WHY_NOT_PLANNER = (
    "a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold: the finish is solved on its own for a target "
    "that names sockets and added to every goal state (`planner/_finish.py`), never searched over as a step of the mods"
)

Colours = tuple[SocketColour, ...]


@dataclass(frozen=True, eq=False)
class ColourOutcomes(SocketOutcomes):
    """The finished items of a colour action; `SocketOutcomes` with the colours asked about."""

    def chance_colours(self, *colours: SocketColour) -> Fraction:
        """The chance that the finished item holds at least one socket of each of `colours`."""
        wanted = set(colours)
        return sum((chance for sockets, chance in self.by_sockets.items() if wanted <= set(sockets.colours)), Fraction(0))

    def chance_non_white(self, at_least: int) -> Fraction:
        """The chance that the finished item holds at least `at_least` coloured (not white) sockets."""
        return sum(
            (chance for sockets, chance in self.by_sockets.items() if sum(c is not SocketColour.WHITE for c in sockets.colours) >= at_least), Fraction(0)
        )


# --- the roll ------------------------------------------------------------------------------------------


def nonwhite_chance(item_level: int, quality: int = 0) -> Fraction:
    """The chance that one rolled socket is non-white: `0.00375 * max(item level - 14, 1) * (1 + min(quality, 30) / 100)` (Siveran's formula)."""
    value = NONWHITE_CHANCE.value
    slope = Fraction(value["slope_numerator"], value["slope_denominator"])
    factor = 1 + Fraction(min(quality, value["quality_cap"]), 100)
    return min(ONE, slope * max(item_level - value["level_offset"], 1) * factor)


def colour_weights(requirements: tuple[int, int, int]) -> tuple[Fraction, Fraction, Fraction]:
    """The chance of red, green and blue for a non-white socket of an item that asks `(strength, dexterity, intelligence)`; they sum to 1.

    One attribute `a`: that colour `0.9 (10 + a) / (a + 20)`, each other `0.05 + 0.9 * 5 / (a + 20)`; two attributes: `0.9 a / total`
    and the missing colour 0.1; three: `a / total`. `ValueError` for requirements of 0 in all three (no rule weights them).
    """
    total = sum(requirements)
    named = sum(1 for entry in requirements if entry > 0)
    if named == 0 or total < 0 or min(requirements) < 0:
        raise ValueError(f"attribute requirements {requirements!r} must hold at least one attribute and none below 0")
    nine_tenths = Fraction(9, 10)
    if named == 1:
        return tuple(  # type: ignore[return-value]
            nine_tenths * Fraction(10 + entry, total + 20) if entry > 0 else Fraction(1, 20) + nine_tenths * Fraction(5, total + 20) for entry in requirements
        )
    if named == 2:
        return tuple(nine_tenths * Fraction(entry, total) if entry > 0 else Fraction(1, 10) for entry in requirements)  # type: ignore[return-value]
    return tuple(Fraction(entry, total) for entry in requirements)  # type: ignore[return-value]


def _flatter(weights: tuple[Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    """The second reading of the forced colour: the natural weights' share plus the uniform share (`sockets.chromatic_forced_socket_colour`)."""
    value = FORCED_SOCKET_COLOUR.value
    natural = Fraction(value["second_reading_natural_third"], value["second_reading_natural_over"])
    uniform = Fraction(value["second_reading_uniform_third"], value["second_reading_uniform_over"])
    return tuple(natural * weight + uniform * Fraction(1, 3) for weight in weights)  # type: ignore[return-value]


@cache
def roll_colours(
    count: int,
    chance: Fraction,
    weights: tuple[Fraction, Fraction, Fraction],
    forced: tuple[Fraction, Fraction, Fraction] | None,
) -> Mapping[Colours, Fraction]:
    """The chance of each list of colours of `count` sockets from one roll: each socket non-white with `chance` and a colour by `weights`.

    With `forced` weights, a roll that comes out all white makes the first socket non-white with a colour by `forced` (the Chromatic Orb);
    with None the all-white roll stays (the bench's roll, which a condition cuts). The chances sum to 1.
    """
    per_socket = {SocketColour.WHITE: ONE - chance, **{colour: chance * weight for colour, weight in zip(COLOURS, weights, strict=True)}}
    found: dict[Colours, Fraction] = defaultdict(Fraction)
    for colours in itertools.product(per_socket, repeat=count):
        total = ONE
        for colour in colours:
            total *= per_socket[colour]
        if total == 0:
            continue
        if forced is not None and all(colour is SocketColour.WHITE for colour in colours):
            for colour, weight in zip(COLOURS, forced, strict=True):
                found[(colour, *colours[1:])] += total * weight  # it adds to the natural roll of the same list
        else:
            found[colours] += total
    return dict(found)


def _conditioned(roll: Mapping[Colours, Fraction], keep: Callable[[Colours], bool]) -> dict[Colours, Fraction]:
    """The chances of the colour lists `keep` accepts, renormalised to sum to 1."""
    kept = {colours: chance for colours, chance in roll.items() if keep(colours)}
    total = sum(kept.values(), Fraction(0))
    if total == 0:
        raise OutOfScopeError("no result of the roll meets the condition (the odds are zero)")
    return {colours: chance / total for colours, chance in kept.items()}


def colour_roll(
    data: GameData, base_id: str, item_level: int, quality: int, count: int, reading: Reading | None = None, *, forced: bool = True
) -> Mapping[Colours, Fraction]:
    """The roll of `count` sockets before any condition: a Chromatic Orb's (`forced`, the first socket made non-white when all came out white) or the bench's.

    Its odds are by `item_level` and the plain `quality` percent, its colours by the requirements of `base_id`; the forced colour is read at
    `reading` (the plan: Siveran's weights). The socket finish (`abstraction`, ticket #231) builds its shared tables from it; the actions condition it.
    Raises `OutOfScopeError` for a base that asks for no attribute.
    """
    requirements = data.base_items[base_id].attribute_requirements
    if not any(requirements):
        raise OutOfScopeError(
            "the base asks for no attribute, and the model has no rule for the colours of its sockets",
            detail="the base asks for no attribute, and no admitted rule weights the colours of its sockets (ADR-0047)",
        )
    weights = colour_weights(requirements)
    forced_weights = None
    if forced:
        second = reading is not None and reading.get(CHROMATIC_FORCED_COLOUR.name, SIVERAN_WEIGHTS) == FLATTER_SECOND_READING
        forced_weights = _flatter(weights) if second else weights
    return roll_colours(count, nonwhite_chance(item_level, quality), weights, forced_weights)


def _kept(roll: Mapping[Colours, Fraction], keep: Callable[[Colours], bool]) -> dict[Colours, Fraction] | None:
    """`_conditioned` for a rule: None where no result of the roll meets the condition, instead of the refusal."""
    kept = {colours: chance for colours, chance in roll.items() if keep(colours)}
    total = sum(kept.values(), Fraction(0))
    return None if total == 0 else {colours: chance / total for colours, chance in kept.items()}


def _roll_of(data: GameData, item: Item, sockets: Sockets, reading: Reading | None, *, forced_rule: bool) -> Mapping[Colours, Fraction]:
    """The roll of a Chromatic Orb (`forced_rule`) or of the bench on `item`: `colour_roll` at the item's item level and plain quality."""
    percent = item.quality.percent if isinstance(item.quality, PlainQuality) else 0
    return colour_roll(data, item.base_id, item.item_level, percent, sockets.count, reading, forced=forced_rule)


def _colour_outcomes(data: GameData, item: Item, sockets: Sockets, chances: Mapping[Colours, Fraction]) -> ColourOutcomes:
    """The result items for the colour lists in `chances` (they sum to 1), the count and the links of `sockets` as they were."""
    made = _outcomes(data, item, {Sockets(colours, sockets.links): chance for colours, chance in chances.items()})
    return ColourOutcomes(made.data, made.given, made.results)


# --- the actions ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChromaticOrb(Action):
    """One Chromatic Orb, or one used with the Omen of Trichromatism (`omen=True`)."""

    omen: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Chromatic Orb with Omen of Trichromatism" if self.omen else "Chromatic Orb"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: it draws no mod and the wiki's strand table has no row for it

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        found = dict(CHROMATIC_ORB_COST.value)
        if self.omen:
            found.update(OMEN_OF_TRICHROMATISM_COST.value)
        return found

    def reads(self, data: GameData) -> Reads:
        """The plain quality (the non-white chance), the count (a one-socket item is always coloured, the Omen needs three) and the colours (the result differs from them); the links are carried over."""
        return Reads(junk=True, families=frozenset(), quality=True, socket_count=True, socket_colours=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(colours=True)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        """The forced socket's colour has a second reading; the Omen's roll never forces one (three colours cannot come from it), so it has none."""
        return () if self.omen else (CHROMATIC_FORCED_COLOUR,)

    def burn(self, data: GameData | None = None) -> bool:
        """The plain Chromatic Orb is a burn of Hinekora's Lock (ADR-0056): it changes no mod and always changes the colours; the Omen is a dearer use of it."""
        return not self.omen

    def burn_claims(self, data: GameData | None = None) -> frozenset[str]:
        """The socket assumption of the burn (`burn.chromatic_socket_assumption`, approximate), listed on any answer that burns with a Chromatic Orb."""
        return frozenset({BURN_SOCKET_ASSUMPTION.id}) if self.burn(data) else frozenset()

    def _burn_item(self, data: GameData, item: Item) -> Item:
        """`item` as the burn sees it: one that states no sockets counts as having one white socket, for the burn only (`burn.chromatic_socket_assumption`).

        A real base of a socketed class always has a socket. A corrupted item and a class with no socket table are left as they are, and refused.
        """
        base = data.base_items.get(item.base_id)
        if item.sockets is not None or item.corrupted or base is None or class_maximum(base) is None:
            return item
        return item.changed(data, sockets=Sockets.unlinked((SocketColour.WHITE,)))

    def burn_refusal(self, data: GameData, item: Item, keeps: BurnKeeps) -> str | None:
        """The refusals of the Chromatic Orb on the item with the assumed socket, without rolling it: a corrupted item, a class with no sockets, an
        Abyssal Socket, and a base that asks for no attribute. The Omen is no burn."""
        if not self.burn(data):
            return f"{self.label(data)} is not a burn"
        try:
            _accept(data, self._burn_item(data, item), "Chromatic Orb")
        except (NotApplicableError, OutOfScopeError) as refusal:
            return str(refusal)
        if not any(data.base_items[item.base_id].attribute_requirements):
            return "the base asks for no attribute, and no admitted rule weights the colours of its sockets (ADR-0047)"
        return None

    def burn_outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> ColourOutcomes:
        """The colours the burn leaves: the Chromatic Orb on `item`, with one white socket assumed when the item states none."""
        return self.outcomes_under(data, self._burn_item(data, item), reading)  # type: ignore[return-value]

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        found = {
            CLASS_MAXIMUM, NONWHITE_CHANCE, NATURAL_COLOUR_WEIGHTS, COLOUR_BY_REQUIREMENTS, NEVER_REPEATS, IGNORES_REQUIREMENT_MODS, CHROMATIC_ORB_COST,
        }
        if self.omen:
            found |= {OMEN_OF_TRICHROMATISM, OMEN_CONDITIONS_THE_ROLL, OMEN_BELOW_THREE_SOCKETS, OMEN_OF_TRICHROMATISM_COST}
        else:
            found |= {ROLL_THEN_FORCE, ONE_SOCKET_ALWAYS_COLOURED, FORCED_SOCKET_COLOUR}
        return frozenset(rule.id for rule in found)

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> ColourOutcomes:
        """The colours the orb leaves: the roll (every socket independently, the first made non-white if all came out white) conditioned on differing from the current colours.

        With the Omen the roll is also conditioned on holding a red, a green and a blue socket. Raises `NotApplicableError` for a corrupted item, a
        class with no sockets and, with the Omen, an item with fewer than three sockets; `OutOfScopeError` for an item with no stated sockets or an
        Abyssal Socket and for a base that asks for no attribute.
        """
        sockets, _ = _accept(data, item, "Chromatic Orb")
        if self.omen and sockets.count < OMEN_MINIMUM_SOCKETS:
            raise NotApplicableError(f"the Omen of Trichromatism needs {OMEN_MINIMUM_SOCKETS} sockets, and the item has {sockets.count}")
        roll = _roll_of(data, item, sockets, reading, forced_rule=True)
        if self.omen:
            chances = _conditioned(roll, lambda colours: all(colour in colours for colour in COLOURS) and colours != sockets.colours)
        else:
            chances = _conditioned(roll, lambda colours: colours != sockets.colours)
        return _colour_outcomes(data, item, sockets, chances)

    def socket_rule(self, data: GameData, base_id: str, item_level: int, quality: int, reading: Reading | None = None) -> SocketRule | None:
        """The roll `outcomes` makes before it excludes the item's colours (with the Omen, conditioned on red, green and blue); None for a base that
        asks for no attribute, and the Omen refused below three sockets."""
        base = data.base_items.get(base_id)
        if _class_maximum_of(data, base_id) is None or base is None or not any(base.attribute_requirements):
            return None

        def roll(count: int):
            if self.omen and count < OMEN_MINIMUM_SOCKETS:
                return None
            rolled = colour_roll(data, base_id, item_level, quality, count, reading, forced=not self.omen)
            return _kept(rolled, lambda colours: all(colour in colours for colour in COLOURS)) if self.omen else rolled

        return SocketRule(roll=roll, excludes_current=True)


@dataclass(frozen=True)
class BenchSocketColours(Action):
    """The bench craft that gives at least `minimum` non-white sockets (2, 3 or 4), for the orbs of the option's price."""

    minimum: int

    def label(self, data: GameData | None = None) -> str:
        return f"Bench craft {self.minimum} coloured sockets"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(NOT_SPENT_BY, CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: a bench craft draws no mod and spends nothing

    def option(self, data: GameData) -> BenchOption:
        """The bench option that asks for this many non-white sockets; `ValueError` when the data has none."""
        for option in data.bench_options:
            if _minimum_of(option) == self.minimum:
                return option
        raise ValueError(f"the bench has no option that colours {self.minimum} sockets")

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("a bench craft is priced from the bench data, so it needs the data")
        return {entry.currency: entry.count for entry in _cost(data, self.option(data))}

    def reads(self, data: GameData) -> Reads:
        """The plain quality (the non-white chance) and the count (the craft needs `minimum` sockets); it excludes no colours, so it does not read them."""
        return Reads(junk=True, families=frozenset(), quality=True, socket_count=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(colours=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        found = {
            CLASS_MAXIMUM, NONWHITE_CHANCE, NATURAL_COLOUR_WEIGHTS, COLOUR_BY_REQUIREMENTS, IGNORES_REQUIREMENT_MODS, BENCH_COLOUR_COST,
            BENCH_CONDITIONED_ROLL, BENCH_ON_CORRUPTED_COSTS_VAAL,
        }
        return frozenset(rule.id for rule in found)

    def outcomes(self, data: GameData, item: Item) -> ColourOutcomes:
        """The colours the craft leaves: the independent roll conditioned on at least `minimum` non-white sockets (no forced socket, no excluded colours).

        Raises `NotApplicableError` for a corrupted item, a class the option is not offered for and an item with fewer sockets than `minimum`;
        `OutOfScopeError` for an item with no stated sockets or an Abyssal Socket and for a base that asks for no attribute.
        """
        option = self.option(data)
        sockets, _ = _accept(data, item, "bench craft")
        base = data.base_items[item.base_id]
        if base.item_class not in option.item_classes:
            raise NotApplicableError(f"the bench does not offer {self.minimum} coloured sockets for the item class {base.item_class}")
        if sockets.count < self.minimum:
            raise NotApplicableError(f"the item has {sockets.count} sockets, so {self.minimum} of them cannot be coloured")
        roll = _roll_of(data, item, sockets, None, forced_rule=False)
        chances = _conditioned(roll, lambda colours: sum(colour is not SocketColour.WHITE for colour in colours) >= self.minimum)
        return _colour_outcomes(data, item, sockets, chances)

    def socket_rule(self, data: GameData, base_id: str, item_level: int, quality: int, reading: Reading | None = None) -> SocketRule | None:
        """The roll `outcomes` makes (conditioned on enough coloured sockets, nothing excluded); None where the bench does not offer the craft for
        the class or the base asks for no attribute."""
        try:
            option = self.option(data)
        except ValueError:  # the bench data has no such option
            return None
        base = data.base_items.get(base_id)
        if not _bench_offers(data, base_id, option) or base is None or not any(base.attribute_requirements):
            return None

        def roll(count: int):
            if count < self.minimum:
                return None
            rolled = colour_roll(data, base_id, item_level, quality, count, forced=False)
            return _kept(rolled, lambda colours: sum(colour is not SocketColour.WHITE for colour in colours) >= self.minimum)

        return SocketRule(roll=roll)


def _minimum_of(option: BenchOption) -> int | None:
    """The minimum of non-white sockets a bench option asks for ("NN", "NNN", "NNNN" for 2, 3, 4), or None for an option that sets none."""
    text = option.actions.color_sockets
    return len(text) if text and set(text) == {"N"} else None


@kind(
    "chromatic-orb",
    order=104,
    planner=False,
    why_not=WHY_NOT_PLANNER,
    applies_only_to="weapon and armour",
    reads_item_state_while_not_planner="quality",
    burns=True,  # the plain orb is a burn (ticket #295)
)
def _chromatic_orb(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in CLASS_MAXIMUM.value["by_class"]:
        yield ChromaticOrb()
        if item.sockets is not None and item.sockets.count >= OMEN_MINIMUM_SOCKETS:  # sockets.omen_of_trichromatism_below_three_sockets: not offered below
            yield ChromaticOrb(omen=True)


@kind("bench-socket-colours", order=105, planner=False, why_not=WHY_NOT_PLANNER, applies_only_to="weapon and armour", reads_item_state_while_not_planner="quality")
def _bench_socket_colours(data: GameData, item: Item):
    for minimum in _offered(data, item, _minimum_of):
        yield BenchSocketColours(minimum)
