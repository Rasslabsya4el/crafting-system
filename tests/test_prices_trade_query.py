"""The trade query model: exact JSON bodies, the hash, the buy spec and its YAML file (#39)."""

import json
import math
from pathlib import Path

import pytest

from crafting_system.prices.trade_query import (
    INFLUENCE_STAT_IDS,
    BuyMod,
    BuySpec,
    StatFilter,
    TradeQuery,
    TradeSpecError,
    build_query,
    load_buy_spec,
    query_hash,
)

R12_SPEC_FILE = Path(__file__).resolve().parent / "fixtures" / "trade" / "r12_buy_spec.yaml"

LIGHTNING_RES = "explicit.stat_1671376347"
FRACTURED_LIGHTNING_RES = "fractured.stat_1671376347"


def canonical(body: dict) -> str:
    return json.dumps(body, sort_keys=True)


def stats_of(body: dict) -> list[dict]:
    return body["query"]["stats"][0]["filters"]


# -- the query body -----------------------------------------------------------------------------


def test_an_empty_query_has_only_status_empty_stats_and_the_sort():
    assert TradeQuery().body() == {
        "query": {"status": {"option": "available"}, "stats": [{"type": "and", "filters": []}]},
        "sort": {"price": "asc"},
    }


def test_base_type_goes_to_query_type():
    body = TradeQuery(type="Onyx Amulet").body()

    assert body["query"]["type"] == "Onyx Amulet"
    assert "filters" not in body["query"]


def test_category_and_rarity_go_to_type_filters():
    body = TradeQuery(category="accessory.amulet", rarity="rare").body()

    assert body["query"]["filters"] == {
        "type_filters": {
            "filters": {"rarity": {"option": "rare"}, "category": {"option": "accessory.amulet"}}
        }
    }


def test_item_level_min_and_max_are_written_under_their_own_keys():
    body = TradeQuery(ilvl_min=75, ilvl_max=84).body()
    assert body["query"]["filters"] == {
        "misc_filters": {"filters": {"ilvl": {"min": 75, "max": 84}}}
    }

    only_max = TradeQuery(ilvl_max=84).body()
    assert only_max["query"]["filters"]["misc_filters"]["filters"]["ilvl"] == {"max": 84}


def test_boolean_misc_filters_are_true_false_options():
    body = TradeQuery(corrupted=False, mirrored=False, fractured=True).body()

    assert body["query"]["filters"]["misc_filters"]["filters"] == {
        "corrupted": {"option": "false"},
        "mirrored": {"option": "false"},
        "fractured_item": {"option": "true"},
    }


def test_stat_filters_carry_min_and_max_and_omit_value_when_neither_is_set():
    query = TradeQuery(
        stats=(
            StatFilter(LIGHTNING_RES, min=30),
            StatFilter("explicit.stat_2", min=1, max=2.5),
            StatFilter("explicit.stat_3"),
        )
    )

    assert stats_of(query.body()) == [
        {"id": LIGHTNING_RES, "disabled": False, "value": {"min": 30}},
        {"id": "explicit.stat_2", "disabled": False, "value": {"min": 1, "max": 2.5}},
        {"id": "explicit.stat_3", "disabled": False},
    ]


def test_an_integral_float_is_written_as_an_int_so_equal_queries_hash_equal():
    as_float = TradeQuery(stats=(StatFilter(LIGHTNING_RES, min=30.0),)).body()
    as_int = TradeQuery(stats=(StatFilter(LIGHTNING_RES, min=30),)).body()

    assert canonical(as_float) == canonical(as_int)


def test_the_whole_body_for_a_fractured_amulet():
    query = TradeQuery(
        category="accessory.amulet",
        rarity="rare",
        ilvl_min=75,
        corrupted=False,
        mirrored=False,
        fractured=True,
        stats=(StatFilter(FRACTURED_LIGHTNING_RES),),
        status="online",
    )

    assert query.body() == {
        "query": {
            "status": {"option": "online"},
            "stats": [
                {
                    "type": "and",
                    "filters": [{"id": FRACTURED_LIGHTNING_RES, "disabled": False}],
                }
            ],
            "filters": {
                "type_filters": {
                    "filters": {
                        "rarity": {"option": "rare"},
                        "category": {"option": "accessory.amulet"},
                    }
                },
                "misc_filters": {
                    "filters": {
                        "ilvl": {"min": 75},
                        "corrupted": {"option": "false"},
                        "mirrored": {"option": "false"},
                        "fractured_item": {"option": "true"},
                    }
                },
            },
        },
        "sort": {"price": "asc"},
    }


def test_the_order_of_stat_filters_does_not_change_the_body():
    first = StatFilter(LIGHTNING_RES, min=30)
    second = StatFilter("explicit.stat_2222222222", min=5)

    forward = TradeQuery(stats=(first, second)).body()
    backward = TradeQuery(stats=(second, first)).body()

    assert canonical(forward) == canonical(backward)


@pytest.mark.parametrize(
    "bad",
    [
        {"rarity": "legendary"},
        {"status": "offline"},
        {"ilvl_min": 80, "ilvl_max": 70},
        {"ilvl_min": 7.5},
        {"ilvl_max": True},
    ],
)
def test_a_query_that_cannot_be_built_is_refused(bad):
    with pytest.raises(TradeSpecError):
        TradeQuery(**bad)


@pytest.mark.parametrize("rarity", ["normal", "magic", "rare", "unique", "nonunique", "uniquefoil"])
def test_every_listed_rarity_is_accepted(rarity):
    body = TradeQuery(rarity=rarity).body()

    assert body["query"]["filters"]["type_filters"]["filters"]["rarity"] == {"option": rarity}


@pytest.mark.parametrize(
    "bad",
    [
        {"id": " "},
        {"id": LIGHTNING_RES, "min": math.nan},
        {"id": LIGHTNING_RES, "min": math.inf},
        {"id": LIGHTNING_RES, "min": 5, "max": 4},
        {"id": LIGHTNING_RES, "min": True},
    ],
)
def test_a_stat_filter_that_cannot_be_built_is_refused(bad):
    with pytest.raises(TradeSpecError):
        StatFilter(**bad)


# -- the hash -----------------------------------------------------------------------------------


def test_query_hash_is_a_stable_sha256_hex_of_the_league_and_the_body():
    body = TradeQuery(type="Onyx Amulet").body()

    assert query_hash("Allflame", body) == query_hash("Allflame", json.loads(json.dumps(body)))
    assert len(query_hash("Allflame", body)) == 64
    int(query_hash("Allflame", body), 16)


def test_query_hash_is_independent_of_key_order():
    body = TradeQuery(type="Onyx Amulet", ilvl_min=75).body()
    shuffled = json.loads(json.dumps(body, sort_keys=True))

    assert query_hash("Allflame", body) == query_hash("Allflame", shuffled)


def test_query_hash_changes_with_the_league_and_with_any_filter():
    def amulet(**changes) -> dict:
        fields = {"category": "accessory.amulet", "rarity": "rare", "ilvl_min": 75}
        fields.update(changes)
        return TradeQuery(**fields).body()

    hashes = {
        query_hash("Allflame", amulet()),
        query_hash("Standard", amulet()),
        query_hash("Allflame", amulet(ilvl_min=76)),
        query_hash("Allflame", amulet(category="accessory.ring")),
        query_hash("Allflame", amulet(rarity="magic")),
        query_hash("Allflame", amulet(stats=(StatFilter(LIGHTNING_RES),))),
    }

    assert len(hashes) == 6


# -- the buy spec -------------------------------------------------------------------------------


def amulet_spec(**changes) -> BuySpec:
    fields = {"name": "test amulet", "category": "accessory.amulet"}
    fields.update(changes)
    return BuySpec(**fields)


def test_a_buy_spec_has_the_documented_defaults():
    spec = amulet_spec()

    assert spec.rarity == "rare"
    assert spec.corrupted is False
    assert spec.influences == ()
    assert spec.mods == ()
    assert spec.base_type is None


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "  "},
        {"category": None},
        {"rarity": "legendary"},
        {"influences": ("shaper", "shaper")},
        {"influences": ("fractal",)},
        {"item_level_min": 80, "item_level_max": 70},
        {"mods": (BuyMod("LightningResistance", minimum=5),), "item_level_min": 1.5},
    ],
)
def test_a_buy_spec_that_cannot_be_built_is_refused(bad):
    with pytest.raises(TradeSpecError):
        amulet_spec(**bad)


def test_a_buy_spec_with_a_base_type_and_no_category_is_fine():
    assert BuySpec(name="x", base_type="Onyx Amulet").category is None


def test_a_buy_mod_with_a_blank_stat_or_non_finite_minimum_is_refused():
    with pytest.raises(TradeSpecError):
        BuyMod(" ")
    with pytest.raises(TradeSpecError):
        BuyMod("LightningResistance", minimum=math.inf)
    with pytest.raises(TradeSpecError):
        BuyMod("LightningResistance", minimum=math.nan)


def test_build_query_for_the_r12_start_item():
    spec = amulet_spec(
        item_level_min=75,
        mods=(BuyMod("LightningResistance", fractured=True),),
    )

    query = build_query(spec, [StatFilter(FRACTURED_LIGHTNING_RES)])

    assert query == TradeQuery(
        category="accessory.amulet",
        rarity="rare",
        ilvl_min=75,
        corrupted=False,
        mirrored=False,
        fractured=True,
        stats=(StatFilter(FRACTURED_LIGHTNING_RES),),
    )


def test_build_query_sets_fractured_only_when_a_spec_mod_is_fractured():
    spec = amulet_spec(mods=(BuyMod("LightningResistance", minimum=30),))

    body = build_query(spec, [StatFilter(LIGHTNING_RES, min=30)]).body()

    misc = body["query"]["filters"]["misc_filters"]["filters"]
    assert "fractured_item" not in misc
    assert misc["corrupted"] == {"option": "false"}
    assert misc["mirrored"] == {"option": "false"}
    assert stats_of(body) == [{"id": LIGHTNING_RES, "disabled": False, "value": {"min": 30}}]


def test_build_query_writes_corrupted_true_when_the_spec_wants_it():
    body = build_query(amulet_spec(corrupted=True), []).body()

    assert body["query"]["filters"]["misc_filters"]["filters"]["corrupted"] == {"option": "true"}


def test_build_query_adds_one_pseudo_stat_per_influence_with_minimum_one():
    spec = amulet_spec(influences=("shaper", "hunter"))

    body = build_query(spec, [StatFilter(LIGHTNING_RES)]).body()

    assert stats_of(body) == [
        {"id": LIGHTNING_RES, "disabled": False},
        {"id": "pseudo.pseudo_has_hunter_influence", "disabled": False, "value": {"min": 1}},
        {"id": "pseudo.pseudo_has_shaper_influence", "disabled": False, "value": {"min": 1}},
    ]


def test_influence_ids_cover_the_six_influences():
    assert INFLUENCE_STAT_IDS == {
        "shaper": "pseudo.pseudo_has_shaper_influence",
        "elder": "pseudo.pseudo_has_elder_influence",
        "crusader": "pseudo.pseudo_has_crusader_influence",
        "hunter": "pseudo.pseudo_has_hunter_influence",
        "redeemer": "pseudo.pseudo_has_redeemer_influence",
        "warlord": "pseudo.pseudo_has_warlord_influence",
    }


def test_build_query_carries_base_type_item_level_range_and_rarity():
    spec = BuySpec(
        name="x",
        base_type="Onyx Amulet",
        rarity="magic",
        item_level_min=68,
        item_level_max=75,
    )

    body = build_query(spec, []).body()

    assert body["query"]["type"] == "Onyx Amulet"
    assert body["query"]["filters"]["type_filters"]["filters"] == {"rarity": {"option": "magic"}}
    assert body["query"]["filters"]["misc_filters"]["filters"]["ilvl"] == {"min": 68, "max": 75}


def test_build_query_is_independent_of_the_order_of_mod_filters():
    spec = amulet_spec()
    a = StatFilter(LIGHTNING_RES, min=30)
    b = StatFilter("explicit.stat_2222222222")

    assert canonical(build_query(spec, [a, b]).body()) == canonical(build_query(spec, [b, a]).body())


# -- the YAML file ------------------------------------------------------------------------------


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "spec.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_committed_r12_spec_loads():
    assert load_buy_spec(R12_SPEC_FILE) == BuySpec(
        name="R12 start amulet",
        category="accessory.amulet",
        item_level_min=75,
        mods=(BuyMod("LightningResistance", fractured=True),),
    )


def test_a_full_spec_file_loads_every_key(tmp_path):
    path = write(
        tmp_path,
        """
name: Full
base_type: Onyx Amulet
category: accessory.amulet
rarity: magic
item_level_min: 60
item_level_max: 86
influence: [shaper, elder]
corrupted: true
mods:
  - stat: LightningResistance
    minimum: 30
    fractured: true
  - stat: "+# to maximum Life"
""",
    )

    assert load_buy_spec(path) == BuySpec(
        name="Full",
        base_type="Onyx Amulet",
        category="accessory.amulet",
        rarity="magic",
        item_level_min=60,
        item_level_max=86,
        influences=("shaper", "elder"),
        corrupted=True,
        mods=(
            BuyMod("LightningResistance", minimum=30, fractured=True),
            BuyMod("+# to maximum Life"),
        ),
    )


def test_a_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_buy_spec(tmp_path / "nope.yaml")


def test_an_unknown_key_names_the_file_and_the_key(tmp_path):
    path = write(tmp_path, "name: x\ncategory: accessory.amulet\nsockets: 6\n")

    with pytest.raises(TradeSpecError) as error:
        load_buy_spec(path)

    assert str(path) in str(error.value)
    assert "sockets" in str(error.value)


def test_an_unknown_mod_key_names_the_file_and_the_key(tmp_path):
    path = write(tmp_path, "name: x\ncategory: a.b\nmods:\n  - stat: A\n    tier: 1\n")

    with pytest.raises(TradeSpecError) as error:
        load_buy_spec(path)

    assert str(path) in str(error.value)
    assert "tier" in str(error.value)


@pytest.mark.parametrize(
    "text",
    [
        "name: x\ncategory: a.b\nitem_level_min: high\n",
        "name: x\ncategory: a.b\nitem_level_min: true\n",
        "name: x\ncategory: a.b\ncorrupted: maybe\n",
        "name: x\ncategory: a.b\ninfluence: shaper\n",
        "name: x\ncategory: a.b\ninfluence: [1]\n",
        "name: x\ncategory: a.b\nmods: LightningResistance\n",
        "name: x\ncategory: a.b\nmods: [LightningResistance]\n",
        "name: x\ncategory: a.b\nmods:\n  - minimum: 5\n",
        "name: x\ncategory: a.b\nmods:\n  - stat: A\n    minimum: lots\n",
        "name: x\ncategory: a.b\nmods:\n  - stat: A\n    fractured: 1\n",
        "name: 5\ncategory: a.b\n",
        "category: a.b\n",
        "- just\n- a list\n",
        "name: [unclosed\n",
        "",
    ],
)
def test_a_spec_file_of_the_wrong_shape_is_refused_naming_the_file(tmp_path, text):
    path = write(tmp_path, text)

    with pytest.raises(TradeSpecError) as error:
        load_buy_spec(path)

    assert str(path) in str(error.value)


def test_a_spec_that_fails_validation_names_the_file_too(tmp_path):
    path = write(tmp_path, "name: x\ncategory: a.b\nrarity: legendary\n")

    with pytest.raises(TradeSpecError) as error:
        load_buy_spec(path)

    assert str(path) in str(error.value)
    assert "legendary" in str(error.value)
