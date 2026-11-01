"""A buy spec may name a corrupted implicit (ticket #257, ADR-0036): `implicit: true` on a buy mod searches the trade site's `implicit` group.

The corrupted mod, the explicit suffix that shares its family and the trade site's stat list are made up here; the shape of the stat list
(groups `explicit`, `implicit`, `fractured` with the same text in several of them) is the real one.
"""

import dataclasses
import json
from urllib.parse import parse_qs, urlparse

import pytest
from targets_corrupted_support import ALL_RES, DATA

from crafting_system.cli._route_trade import buy_step
from crafting_system.prices.trade_query import BuyMod, BuySpec, TradeSpecError, build_query, load_buy_spec
from crafting_system.prices.trade_stats import named_mods, parse_trade_stats, resolve_buy_mod

CORRUPTED = DATA.mods["ResistCorrupted"]
# an explicit suffix of the same family with another text: a family id alone could not be told apart without the `implicit` flag
SUFFIX = dataclasses.replace(DATA.mods["ColdResist1"], id="SharedFamilySuffix", families=CORRUPTED.families)
MODS = (SUFFIX, CORRUPTED)
STATS = parse_trade_stats(
    {
        "result": [
            {"id": "explicit", "entries": [{"id": "explicit.stat_res", "text": "+#% to all Elemental Resistances"}]},
            {"id": "implicit", "entries": [{"id": "implicit.stat_res", "text": "+#% to all Elemental Resistances"}]},
            {"id": "fractured", "entries": [{"id": "fractured.stat_res", "text": "+#% to all Elemental Resistances"}]},
        ]
    }
)


def test_a_buy_mod_is_not_an_implicit_unless_it_says_so():
    assert BuyMod("x").implicit is False
    assert BuyMod("x", implicit=True).implicit is True


def test_an_implicit_buy_mod_cannot_be_fractured():
    with pytest.raises(TradeSpecError, match="an implicit cannot be fractured"):
        BuyMod("x", fractured=True, implicit=True)


def test_a_buy_spec_names_an_implicit_only_for_a_corrupted_item():
    with pytest.raises(TradeSpecError, match="is an implicit, which a buy spec names only for a corrupted item"):
        BuySpec("Ring", base_type="Prismatic Ring", mods=(BuyMod(ALL_RES, implicit=True),))
    assert BuySpec("Ring", base_type="Prismatic Ring", corrupted=True, mods=(BuyMod(ALL_RES, implicit=True),)).corrupted


def test_a_buy_spec_file_reads_the_implicit_key_and_rejects_a_wrong_value(tmp_path):
    spec = tmp_path / "ring.yaml"
    spec.write_text(
        "name: Corrupted ring\nbase_type: Prismatic Ring\ncorrupted: true\nmods:\n  - stat: ResistFamily\n    implicit: true\n    minimum: 15\n"
        "  - stat: '+#% to Cold Resistance'\n",
        encoding="utf-8",
    )

    loaded = load_buy_spec(spec)
    assert loaded.corrupted is True
    assert [(mod.stat, mod.implicit, mod.minimum) for mod in loaded.mods] == [
        ("ResistFamily", True, 15),
        ("+#% to Cold Resistance", False, None),
    ]
    spec.write_text("name: x\nbase_type: y\nmods:\n  - stat: z\n    implicit: maybe\n", encoding="utf-8")
    with pytest.raises(TradeSpecError, match="implicit must be true or false"):
        load_buy_spec(spec)


def test_an_implicit_buy_mod_searches_the_implicit_group_and_the_others_do_not():
    assert resolve_buy_mod(BuyMod(ALL_RES, 15, implicit=True), MODS, STATS).id == "implicit.stat_res"
    assert resolve_buy_mod(BuyMod(ALL_RES, 15), MODS, STATS).id == "explicit.stat_res"
    assert resolve_buy_mod(BuyMod(ALL_RES, 15, fractured=True), MODS, STATS).id == "fractured.stat_res"
    assert resolve_buy_mod(BuyMod(ALL_RES, 15, implicit=True), MODS, STATS).min == 15


def test_a_family_or_mod_id_of_an_implicit_buy_mod_is_looked_up_among_the_implicit_mods_only():
    family = CORRUPTED.families[0]

    assert [mod.id for mod in named_mods(BuyMod(family, implicit=True), MODS)] == ["ResistCorrupted"]
    assert [mod.id for mod in named_mods(BuyMod(family), MODS)] == ["SharedFamilySuffix", "ResistCorrupted"]
    assert resolve_buy_mod(BuyMod(family, implicit=True), MODS, STATS).id == "implicit.stat_res"
    assert resolve_buy_mod(BuyMod("ResistCorrupted", implicit=True), MODS, STATS).id == "implicit.stat_res"
    with pytest.raises(TradeSpecError, match="different texts"):
        resolve_buy_mod(BuyMod(family), MODS, STATS)  # as before: the family holds a suffix of another text


def test_the_query_of_a_corrupted_spec_carries_the_implicit_filter_and_asks_for_a_corrupted_item():
    spec = BuySpec(
        "Corrupted ring", base_type="Prismatic Ring", corrupted=True, mods=(BuyMod(ALL_RES, 15, implicit=True),)
    )
    mod_filters = [resolve_buy_mod(mod, MODS, STATS) for mod in spec.mods]

    body = build_query(spec, mod_filters).body()["query"]
    assert body["stats"] == [{"type": "and", "filters": [{"id": "implicit.stat_res", "disabled": False, "value": {"min": 15}}]}]
    assert body["filters"]["misc_filters"]["filters"]["corrupted"] == {"option": "true"}


def test_the_buy_step_names_an_implicit_mod_and_links_the_implicit_search():
    spec = BuySpec(
        "Corrupted ring", base_type="Prismatic Ring", corrupted=True, mods=(BuyMod(ALL_RES, 15, implicit=True), BuyMod(ALL_RES))
    )

    step = buy_step(spec, "Mirage", MODS, STATS)

    assert step.accepts[-2:] == (f"implicit: {ALL_RES} (at least 15)", ALL_RES)
    assert "corrupted" in step.accepts and step.unresolved == ()
    query = json.loads(parse_qs(urlparse(step.url).query)["q"][0])["query"]
    assert sorted(found["id"] for found in query["stats"][0]["filters"]) == ["explicit.stat_res", "implicit.stat_res"]
