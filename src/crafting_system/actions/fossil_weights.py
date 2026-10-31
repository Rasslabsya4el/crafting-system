"""The weight factor that the fossils of a resonator give a mod: Craft of Exile's `poec_getModdedWeight` on the repoe tags.

Each fossil record has tag weights (`weight / 100` is the factor). For a mod with the tag set `T`
(its `implicit_tags`):

* a tag with weight 0 on any socketed fossil blocks the mod: its weight is 0, whatever else a fossil
  gives it (`BLOCK_WINS`);
* every tag in `T` that a fossil boosts (factor at least 1) is one term, so a fossil with two
  matching tags gives two terms (`BOOST_PER_MATCHING_TAG`, CHK-048); the terms of all fossils are
  summed, and the sum is 1 when no term applies (`FACTOR_STACKING`, D10);
* every tag in `T` that a fossil cuts (factor below 1) is one term of a product;
* a Corroded Fossil boosts a mod that has a hybrid tag (`bleed`, `poison`) and then no other fossil's
  boost or cut counts for the tags that the hybrid already covers, a block still does
  (`HYBRID_BYPASS`, D11);
* an Opulent Fossil drops a mod with no tags at all (`OPULENT_NO_TAGLESS`);
* a Sanctified Fossil multiplies the whole weight by `1 + (required level - 40) / 100`
  (`SANCTIFIED_LEVEL_FACTOR`, `SANCTIFIED_MULTIPLIES_WHOLE_WEIGHT`).

The factor is an exact `Fraction`, never rounded (`WEIGHTS_EXACT`, D13).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import Fossil, Mod
from crafting_system.rules import get_rule

FACTOR_STACKING = get_rule("fossils.factor_stacking")
WEIGHT_IS_PERCENT = get_rule("fossils.weight_is_percent_factor")
TAGS_ARE_IMPLICIT_TAGS = get_rule("fossils.tags_are_implicit_tags")
BOOST_PER_MATCHING_TAG = get_rule("fossils.boost_per_matching_tag")
BLOCK_WINS = get_rule("fossils.block_wins")
HYBRID_BYPASS = get_rule("fossils.hybrid_bypass")
WEIGHTS_EXACT = get_rule("fossils.weights_exact")
OPULENT_NO_TAGLESS = get_rule("fossils.opulent_no_tagless")
SANCTIFIED_LEVEL_FACTOR = get_rule("fossils.sanctified_level_factor")
SANCTIFIED_MULTIPLIES_WHOLE_WEIGHT = get_rule("fossils.sanctified_multiplies_whole_weight")

ONE = Fraction(1)
PERCENT = 100


@dataclass(frozen=True)
class FossilWeights:
    """The tag effects of a set of fossils and what the factor of a mod is under them.

    `boosts` maps a tag to the sum of the factors that the fossils give it, `cuts` a tag to the
    product of the factors below 1, `blocks` holds the tags of weight 0.
    """

    boosts: dict[str, Fraction]
    cuts: dict[str, Fraction]
    blocks: frozenset[str]
    opulent: bool = False
    sanctified: bool = False

    def factor(self, mod: Mod, *, tags_only: bool = False) -> Fraction:
        """The factor of `mod`: 0 for a blocked mod. With `tags_only` the Opulent and Sanctified rules are left out."""
        tags = frozenset(mod.implicit_tags)
        if tags & self.blocks:
            return Fraction(0)
        if self.opulent and not tags and not tags_only:
            return Fraction(0)
        covered: set[str] = set()
        for marker, hybrid in HYBRID_BYPASS.value.items():
            if marker in tags and marker in self.boosts:
                covered.update(hybrid)
        terms = [self.boosts[tag] for tag in tags if tag in self.boosts and tag not in covered]
        boost = sum(terms, Fraction(0)) if terms else ONE
        cut = ONE
        for tag in tags:
            if tag in self.cuts and tag not in covered:
                cut *= self.cuts[tag]
        factor = boost * cut
        if self.sanctified and not tags_only:
            factor *= ONE + Fraction(mod.required_level - SANCTIFIED_LEVEL_FACTOR.value, PERCENT)
        return factor


def fossil_weights(
    fossils: Iterable[Fossil],
    pair: Fossil | None = None,
    *,
    opulent: bool = False,
    sanctified: bool = False,
) -> FossilWeights:
    """The tag effects of `fossils`, and of one Tangled outcome record `pair` if given."""
    boosts: dict[str, Fraction] = {}
    cuts: dict[str, Fraction] = {}
    blocks: set[str] = set()
    records = [*fossils, *([] if pair is None else [pair])]
    for record in records:
        for entry in (*record.positive_mod_weights, *record.negative_mod_weights):
            if entry.weight == 0:
                blocks.add(entry.tag)
                continue
            factor = Fraction(entry.weight, PERCENT)
            if factor < 1:
                cuts[entry.tag] = cuts.get(entry.tag, ONE) * factor
            else:
                boosts[entry.tag] = boosts.get(entry.tag, Fraction(0)) + factor
    return FossilWeights(boosts, cuts, frozenset(blocks), opulent, sanctified)
