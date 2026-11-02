"""Shared helpers for the tests of the colour and quality actions (ticket #229, B6 S3; ADR-0047 and ADR-0049).

The items live in `sockets_support.socket_data()` (the contract data plus a helmet base); `colour_data()` makes that helmet a dexterity-intelligence one
of equal requirements, names the Chromatic Orb as the game does and adds the three bench colour options. The numbers the tests compare with are written out
here from ADR-0047 and the research (ticket #99), not read from the claims.
"""

import dataclasses
import functools
import math
from fractions import Fraction

from sockets_support import HELMET, socket_data

from crafting_system.data import BaseItem, CostEntry

CHROMATIC_ID = "Metadata/Items/Currency/CurrencyRerollSocketColours"
DEX_INT_REQUIREMENTS = (0, 61, 61)
BENCH_COLOUR_COSTS = {2: 5, 3: 20, 4: 75}  # ADR-0047, "The bench": Chromatic Orbs for at least 2, 3, 4 non-white sockets

# Siveran's data (https://siveran.github.io/poedata.csv, 2,836 six-socket results), aggregated by the research of ticket #99 and again for this
# ticket: (item level, quality, (strength, dexterity, intelligence) requirements, rows, rows by the number of non-white sockets).
SIVERAN_CELLS = (
    (2, 0, (180, 0, 0), 228, {1: 228}),
    (15, 20, (25, 0, 0), 301, {1: 301}),
    (26, 10, (0, 65, 0), 677, {1: 654, 2: 22, 3: 1}),
    (50, 20, (53, 0, 53), 454, {1: 348, 2: 87, 3: 15, 4: 3, 5: 1}),
    (85, 20, (0, 0, 160), 376, {1: 162, 2: 116, 3: 67, 4: 26, 5: 5}),
    (100, 0, (145, 0, 0), 381, {1: 150, 2: 107, 3: 91, 4: 27, 5: 6}),
    (100, 20, (145, 0, 0), 302, {1: 80, 2: 90, 3: 89, 4: 35, 5: 6, 6: 2}),
    (100, 60, (139, 65, 0), 117, {1: 22, 2: 39, 3: 34, 4: 16, 5: 5, 6: 1}),
)
CHI_SQUARED_95 = 3.841  # one degree of freedom: the 95% likelihood interval of the one parameter p


def quality_gain(item_level: int) -> float:
    """`f = max(1, min(30 e^(-ilvl/30) - 0.3, 20))`, the mean points of one Whetstone or Scrap (ADR-0049), restated."""
    return max(1.0, min(30 * math.exp(-item_level / 30) - 0.3, 20.0))


def expected_currency(item_level: int, target: int = 20) -> float:
    """The mean number of Whetstones or Scraps to `target` percent from 0, by value iteration over the gain law (an independent restatement)."""
    f = quality_gain(item_level)
    low = math.floor(f)
    law = {low: 1 - (f - low), low + 1: f - low} if f != low else {low: 1.0}
    mean = [0.0] * 21
    for quality in range(target - 1, -1, -1):
        mean[quality] = 1 + sum(chance * (mean[quality + points] if quality + points < target else 0.0) for points, chance in law.items() if chance)
    return mean[0]


def nonwhite_count_chances(count: int, chance: float) -> dict[int, float]:
    """The chance of k non-white sockets of `count` rolled with `chance` each, the first socket made non-white if none came out (an independent restatement)."""
    found = {k: math.comb(count, k) * chance**k * (1 - chance) ** (count - k) for k in range(count + 1)}
    found[1] += found.pop(0)
    return found


def log_likelihood(histogram: dict[int, int], chances: dict[int, float]) -> float:
    return sum(rows * math.log(chances[k]) for k, rows in histogram.items())


def best_log_likelihood(histogram: dict[int, int], count: int = 6) -> float:
    """The log-likelihood of the histogram at its best `p` (a one-dimensional search over the roll-then-force family)."""
    low, high = 1e-9, 1 - 1e-9
    for _ in range(200):  # golden-section search of a unimodal likelihood
        a, b = low + (high - low) * 0.382, low + (high - low) * 0.618
        if log_likelihood(histogram, nonwhite_count_chances(count, a)) < log_likelihood(histogram, nonwhite_count_chances(count, b)):
            low = a
        else:
            high = b
    return log_likelihood(histogram, nonwhite_count_chances(count, (low + high) / 2))


@functools.cache
def colour_data():
    """The socket data with the helmet a dexterity-intelligence base, the Chromatic Orb named as in the game and the bench's three colour options."""
    data = socket_data()
    bases = dict(data.base_items)
    bases[HELMET] = dataclasses.replace(bases[HELMET], attribute_requirements=DEX_INT_REQUIREMENTS)
    bases[CHROMATIC_ID] = BaseItem(CHROMATIC_ID, "Chromatic Orb", "StackableCurrency", "currency", 1, (), (), "released")
    template = next(option for option in data.bench_options if option.actions.change_socket_count is not None)
    none = dataclasses.replace(template.actions, change_socket_count=None, link_sockets=None, color_sockets=None)
    options = [option for option in data.bench_options if option.actions.color_sockets is None]
    for minimum, price in BENCH_COLOUR_COSTS.items():
        actions = dataclasses.replace(none, color_sockets="N" * minimum)
        options.append(dataclasses.replace(template, actions=actions, cost=(CostEntry(CHROMATIC_ID, price),)))
    return dataclasses.replace(data, base_items=bases, bench_options=tuple(options))


def chance_of(outcomes, colours) -> Fraction:
    """The chance that the result has exactly the colours `colours` (a tuple of `SocketColour`)."""
    return sum((chance for sockets, chance in outcomes.by_sockets.items() if sockets.colours == tuple(colours)), Fraction(0))
