"""A resonator with a Bloodstained Fossil passes the contract suite (ticket #261).

The fixture data of the contract suite (`contract_support.CONTRACT_DATA`, amulets) gets a Bloodstained and a Gilded record and three
corrupted implicits that amulets can get, as `test_actions_corrupting_toy.py` gives the toy one. `check_action` then runs every
check of the suite on a few sets and every fixture item: the outcomes sum to one, the finished items listed from the components
give each mod and each corrupted implicit the chance `chance_all` says, the sampler follows those chances, the kernel of the
compressed state equals the brute force on the finished items (layer 1), what the set declares agrees with what it does (it corrupts
and says so, every result is corrupted and final, it erases the crafted mods, it adds an implicit, it reads the implicits), and the
coarse state refuses it because it declares no block invariance.
"""

import dataclasses
import random

import pytest
from abstraction_pool import LIFE_1
from contract_support import CONTRACT_DATA, check_action, fixture_items

from crafting_system.actions import ApplyFossils, NotApplicableError, catalog, usable_fossils
from crafting_system.data import Weight

BLOODSTAINED = "Bloodstained Fossil"
GILDED = "Gilded Fossil"
CORRUPTED = {"ContractCorruptedAllRes": 1000, "ContractCorruptedChaosRes": 250, "ContractCorruptedFrenzy": 200}


def _data():
    scorched = next(record for record in CONTRACT_DATA.fossils.values() if record.name == "Scorched Fossil")
    blank = dataclasses.replace(scorched, positive_mod_weights=(), negative_mod_weights=())
    records = {
        record.id: record
        for record in (
            dataclasses.replace(blank, id="Metadata/Items/Currency/CurrencyDelveCraftingVaal", name=BLOODSTAINED),
            dataclasses.replace(blank, id="Metadata/Items/Currency/CurrencyDelveCraftingSellPrice", name=GILDED),
        )
    }
    template = CONTRACT_DATA.mods[LIFE_1]
    mods = dict(CONTRACT_DATA.mods)
    for mod_id, weight in CORRUPTED.items():
        mods[mod_id] = dataclasses.replace(
            template,
            id=mod_id,
            name=mod_id,
            type=mod_id,
            families=(mod_id,),
            generation_type="corrupted",
            domain="item",
            required_level=1,
            spawn_weights=(Weight("amulet", weight), Weight("default", 0)),
            generation_weights=(),
            implicit_tags=(),
        )
    return dataclasses.replace(CONTRACT_DATA, mods=mods, fossils={**CONTRACT_DATA.fossils, **records})


DATA = _data()
ITEMS = fixture_items()
SETS = [(BLOODSTAINED,), (BLOODSTAINED, GILDED, "Scorched Fossil"), (BLOODSTAINED, "Faceted Fossil")]
RARE_ITEMS = ["rare_junk", "rare_fractured", "rare_crafted", "rare_shaper"]  # junk to erase, a fractured mod to keep, a crafted mod to erase, an influence


@pytest.mark.parametrize("name", RARE_ITEMS)
@pytest.mark.parametrize("fossils", SETS, ids=lambda fossils: "+".join(name.removesuffix(" Fossil") for name in fossils))
def test_the_set_meets_the_contract(fossils, name):
    assert check_action(ApplyFossils(fossils), ITEMS[name], DATA)


@pytest.mark.parametrize("name", ["normal", "magic"])
def test_the_set_is_refused_where_the_game_refuses_it_and_the_kernel_agrees(name):
    assert not check_action(ApplyFossils((BLOODSTAINED, "Scorched Fossil")), ITEMS[name], DATA)


def test_the_catalog_lists_the_sets_on_the_rare_fixture_items_and_each_corrupts_or_not_as_it_says():
    item = ITEMS["rare_junk"]
    listed = [action for action in catalog(DATA, item) if isinstance(action, ApplyFossils) and BLOODSTAINED in action.fossils]
    assert listed and BLOODSTAINED in usable_fossils(DATA, item)
    assert all(action.adds(DATA, item).corrupts for action in listed)
    assert not any(action.adds(DATA, item).corrupts for action in catalog(DATA, item) if isinstance(action, ApplyFossils) and BLOODSTAINED not in action.fossils)


def test_a_result_is_final_no_action_of_the_catalog_applies_to_it():
    item = ITEMS["rare_junk"]
    result = ApplyFossils((BLOODSTAINED,)).outcomes(DATA, item).sample(random.Random(1))
    assert result.corrupted and result.implicits
    for action in catalog(DATA, result):
        with pytest.raises(NotApplicableError):
            action.outcomes(DATA, result)
