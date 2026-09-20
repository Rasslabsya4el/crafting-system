from __future__ import annotations

import pytest

from tools.coe_inventory import (
    CMethodParseError,
    UnresolvedReference,
    extract_cmethods,
    inventory_methods,
    parse_cmethods_source,
    render_inventory,
)


def test_inventory_walks_nested_subsets_in_source_order() -> None:
    source = (
        'var poec_cmethods={"currency":{"name":"Currency","subset":'
        '{"a":{"name":"A"},"b":{"name":"B","subset":"custom","nosim":!0}}}};'
    )

    parsed = parse_cmethods_source(source)
    inventory = inventory_methods(parsed, source)

    assert [node.path for node in inventory.nodes] == [
        "currency",
        "currency.a",
        "currency.b",
    ]
    assert inventory.total_nodes == 3
    assert inventory.leaf_nodes == 2
    assert inventory.custom_subsets == 1
    assert inventory.nodes[2].nosim is True


def test_strings_references_and_minified_booleans_are_preserved() -> None:
    source = r'''var poec_cmethods={
      "currency":{"name":"A { brace } and \\\"quote\\\"","required":{
        "bgroup":poec_constants.constraints.example},"cannot":{"blocked":!1},
        "subset":{"a":{"name":"A","nosim":!0}}}
    };'''

    parsed = parse_cmethods_source(source)
    root = parsed.entries[0].value
    assert root["name"] == 'A { brace } and \\"quote\\"'
    assert isinstance(root["required"]["bgroup"], UnresolvedReference)
    assert root["required"]["bgroup"].expression == "poec_constants.constraints.example"
    assert root["cannot"]["blocked"] is False
    assert root["subset"]["a"]["nosim"] is True


def test_options_include_defaults_and_choice_values() -> None:
    source = (
        'var poec_cmethods={"method":{"name":"Method","options":['
        '{"id":"mode","default":"x","choices":[{"value":"x"},{"value":"y"}]}]}};'
    )

    inventory = inventory_methods(parse_cmethods_source(source), source)

    assert inventory.option_count == 1
    assert inventory.choice_count == 2
    assert inventory.nodes[0].options[0].id == "mode"
    assert inventory.nodes[0].options[0].default == "x"
    assert inventory.nodes[0].options[0].choices == ("x", "y")


@pytest.mark.parametrize(
    "source",
    [
        'var poec_cmethods={"method":{"name":"Method"};',
        'var poec_cmethods={"method":{"name":function(){}}};',
    ],
)
def test_unbalanced_and_executable_values_are_rejected(source: str) -> None:
    with pytest.raises(CMethodParseError):
        parse_cmethods_source(source)


def test_rendering_is_byte_deterministic() -> None:
    source = (
        'var poec_cmethods={"currency":{"name":"Currency","subset":'
        '{"a":{"name":"A"}}}};\nfunction poec_simApplyCraftGO(){}'
    )
    inventory = inventory_methods(parse_cmethods_source(source), source)

    first = render_inventory(inventory, source, "package.js")
    second = render_inventory(inventory, source, "package.js")

    assert first == second
    assert "currency.a" in first
    assert "poec_simApplyCraftGO | 2" in first


def test_extracts_only_the_cmethods_assignment() -> None:
    source = (
        'var ignored={"x":function(){}};var poec_cmethods='
        '{"method":{"name":"Method"}};function later(){return function(){}}'
    )

    parsed = extract_cmethods(source)

    assert list(parsed) == ["method"]
