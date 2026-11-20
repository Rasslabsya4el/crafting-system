"""A resonator builds each distinct pool once (#1352).

`fossil._build` weighed and grouped the candidates for each Tangled outcome record (420 of them in the game data) and each forced choice,
though `FossilWeights.factor` reads of a mod only its tag set and (Sanctified) its required level: on R04 one key grouped 192,986 pools for
22,433 distinct ones. Now the weights are read on the classes (tag set, level) of the candidates, and a vector of factors met before takes
the pool it gave. Here: the outcomes are the ones built pool by pool, and fewer pools are grouped.
"""

import pytest
from test_actions_fossil import DATA, boots, roll

from crafting_system.actions import ApplyFossils
from crafting_system.actions import fossil
from crafting_system.actions.fossil_weights import FossilWeights

SETS = [("Tangled Fossil",), ("Tangled Fossil", "Scorched Fossil"), ("Sanctified Fossil", "Scorched Fossil"), ("Glyphic Fossil",), ("Opulent Fossil",)]
ITEMS = [boots(), boots(roll("CasterA", fractured=True), roll("LifeA"))]


def _components(outcomes):
    return [(share, part.forced, part.pool, dict(part.totals), part.retained) for share, part in outcomes.components]


@pytest.mark.parametrize("names", SETS)
@pytest.mark.parametrize("item", ITEMS, ids=["empty", "fractured"])
def test_the_outcomes_are_the_ones_built_pool_by_pool(names, item, monkeypatch):
    counted = []
    real = fossil.group_pool
    monkeypatch.setattr(fossil, "group_pool", lambda candidates, factor: counted.append(1) or real(candidates, factor))
    once = _components(ApplyFossils(names).outcomes(DATA, item))
    grouped_once = len(counted)
    counted.clear()
    # every vector a new one: each pair and choice groups its own pool, as before
    monkeypatch.setattr(FossilWeights, "class_factor", lambda self, tags, level: object())
    each = _components(ApplyFossils(names).outcomes(DATA, item))
    assert once == each
    assert grouped_once <= len(counted)
    if "Tangled Fossil" in names:
        assert grouped_once < len(counted)  # the fixture's records "1" and "1 again" weigh alike
