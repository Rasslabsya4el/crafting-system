from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from craftoracle.distributions import OutcomeClass
from craftoracle.plan_inputs import load_loadout, load_spec


ROOT = Path(__file__).resolve().parents[1]


def _mod_rows() -> dict[str, dict[str, str]]:
    return {
        "IncreasedLife9": {"group": "IncreasedLife"},
        "ChaosResist6": {"group": "ChaosResistance"},
        "FireResist8": {"group": "FireResistance"},
        "ColdResist8": {"group": "ColdResistance"},
        "LightningResist8": {"group": "LightningResistance"},
        "LocalAddedFireDamageTwoHand10": {"group": "LocalFireDamageTwoHand"},
        "LocalAddedFireDamageTwoHand9": {"group": "LocalFireDamageTwoHand"},
        "LocalIncreasedAttackSpeed5": {"group": "LocalIncreasedAttackSpeed"},
        "LocalIncreasedAttackSpeed4": {"group": "LocalIncreasedAttackSpeed"},
    }


def _accepted_pob_rows() -> dict[str, dict]:
    document = json.loads((ROOT / "data/pob_mod_families.json").read_text(encoding="utf-8"))
    return {
        row["id"]: row
        for row in document["mods"]
        if row["source_path"] == "sources/pob/Data/ModExplicit.lua"
    }


def _outcome(*labels: str) -> OutcomeClass:
    return OutcomeClass(labels, prefixes=0, suffixes=0)


def _helmet_document() -> dict:
    return {
        "schema_version": 1,
        "name": "test helmet",
        "base": "Royal Burgonet",
        "item_level": 86,
        "quality": 20,
        "tier_ids": {
            "IncreasedLife": [["IncreasedLife9"]],
            "ChaosResistance": [["ChaosResist6"]],
            "FireResistance": [["FireResist8"]],
            "ColdResistance": [["ColdResist8"]],
            "LightningResistance": [["LightningResist8"]],
        },
        "required_mods": [
            {"group": "IncreasedLife", "max_tier": 1},
            {"group": "ChaosResistance", "max_tier": 1},
        ],
        "any_of": [[
            {"group": "FireResistance", "max_tier": 1},
            {"group": "ColdResistance", "max_tier": 1},
            {"group": "LightningResistance", "max_tier": 1},
        ]],
        "sources": ["S24", "S27"],
    }


def _write_json(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_committed_helmet_target_and_defaults() -> None:
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", _accepted_pob_rows())

    assert spec.quality == 20
    assert spec.flags == {
        "corrupted": False,
        "influenced": False,
        "fractured": False,
        "synthesised": False,
        "mirrored": False,
        "split": False,
    }
    assert spec.matches(_outcome("IncreasedLife:1", "ChaosResistance:1", "ColdResistance:1"))
    assert not spec.matches(_outcome("ChaosResistance:1", "ColdResistance:1"))
    assert not spec.matches(_outcome("IncreasedLife:1", "ColdResistance:1"))
    assert not spec.matches(_outcome("IncreasedLife:1", "ChaosResistance:1"))


def test_bow_value_table_predicates_and_utility(tmp_path: Path) -> None:
    spec = load_spec(ROOT / "examples/bow_value_table.yaml", _accepted_pob_rows())
    fire_t1 = _outcome("LocalFireDamageTwoHand:1")
    both_t1 = _outcome("LocalFireDamageTwoHand:1", "LocalIncreasedAttackSpeed:1")
    both_t2 = _outcome("LocalFireDamageTwoHand:2", "LocalIncreasedAttackSpeed:2")
    absent = _outcome()

    assert spec.utility(fire_t1) == 60
    assert spec.utility(both_t1) == 100
    assert spec.utility(both_t2) == 65
    assert spec.utility(absent) == 0
    assert spec.matches(fire_t1)
    assert spec.matches(both_t2)
    assert spec.matches(both_t1)

    document = json.loads((ROOT / "examples/bow_value_table.yaml").read_text(encoding="utf-8"))
    document["threshold"] = 100
    alternate = load_spec(_write_json(tmp_path / "bow-threshold.yaml", document), _mod_rows())
    assert not alternate.matches(fire_t1)
    assert not alternate.matches(both_t2)
    assert alternate.matches(both_t1)


def test_loadout_price_and_permissions(tmp_path: Path) -> None:
    loadout = load_loadout(ROOT / "data/loadouts/endgame.json")

    assert loadout.bench_cost(131) == 2
    assert loadout.bench_cost(729) == 200
    assert loadout.permits("bench", bench_index=131)
    assert loadout.permits("bench", bench_index=729)
    assert not loadout.permits("harvest")
    classic_tags = {
        "fire", "cold", "lightning", "physical", "life", "defence", "chaos",
        "attack", "caster", "speed", "critical",
    }
    extra_tags = {"minion", "elemental", "attribute", "mana"}
    assert all(loadout.permits(f"harvest_reforge:{tag}") for tag in classic_tags | extra_tags)
    assert loadout.price("harvest_reforge:life") == 1
    assert all(loadout.price(f"harvest_reforge:{tag}") == 100 for tag in extra_tags)
    assert loadout.price("harvest_add_remove_sacred") == 100
    assert not loadout.permits("divine")  # A listed price never grants permission.
    assert loadout.permits("essence", essence_id="Metadata/Items/Currency/CurrencyEssenceEnvy3")

    prices = json.loads((ROOT / "data/prices.example.json").read_text(encoding="utf-8"))
    prices["values"]["divine"] = 2
    _write_json(tmp_path / "prices-two-divine.json", prices)
    loadout_document = json.loads((ROOT / "data/loadouts/endgame.json").read_text(encoding="utf-8"))
    loadout_document["prices_file"] = "prices-two-divine.json"
    adjusted = load_loadout(_write_json(tmp_path / "loadout.json", loadout_document))
    assert adjusted.bench_cost(729) == 4
    with pytest.raises(ValueError, match="missing price"):
        loadout.price("harvest_lifeforce")


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda document: document.__setitem__("schema_version", 2), "schema_version"),
        (lambda document: document["tier_ids"]["IncreasedLife"].__setitem__(0, ["ChaosResist6"]), "group"),
        (lambda document: document["required_mods"][0].__setitem__("max_tier", 2), "tier"),
        (lambda document: document["tier_ids"]["IncreasedLife"].__setitem__(0, ["NoSuchMod"]), "unknown mod"),
        (lambda document: document.__setitem__("value_table", {"IncreasedLife": {"1": 1}}), "mode"),
        (lambda document: document.__setitem__("unknown", True), "unknown top-level"),
        (lambda document: document["tier_ids"]["IncreasedLife"].append(["IncreasedLife9"]), "ambiguous"),
    ],
)
def test_spec_rejects_invalid_schema_and_target(tmp_path: Path, mutate, error: str) -> None:
    document = _helmet_document()
    mutate(document)

    with pytest.raises(ValueError, match=error):
        load_spec(_write_json(tmp_path / "spec.yaml", document), _mod_rows())


def test_spec_rejects_nonfinite_threshold_q9_flags_and_non_json_yaml(tmp_path: Path) -> None:
    document = _helmet_document()
    document.pop("required_mods")
    document.pop("any_of")
    document["value_table"] = {"IncreasedLife": {"1": 1}}
    document["threshold"] = math.nan
    document["values_note"] = "test value input"
    with pytest.raises(ValueError, match="finite"):
        load_spec(_write_json(tmp_path / "nonfinite.yaml", document), _mod_rows())

    document = _helmet_document()
    document["flags"] = {"corrupted": True}
    with pytest.raises(NotImplementedError, match="Q9"):
        load_spec(_write_json(tmp_path / "q9.yaml", document), _mod_rows())

    yaml_path = tmp_path / "unsupported.yaml"
    yaml_path.write_text("schema_version: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON-compatible YAML"):
        load_spec(yaml_path, _mod_rows())


def test_paths_and_invalid_price_data_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository root"):
        load_spec(Path("../outside.yaml"), _mod_rows())

    escaped_loadout = {
        "schema_version": 1,
        "name": "escaped price path",
        "allowed_actions": [],
        "allowed_essences": [],
        "allowed_bench": [],
        "prices_file": "../../../outside.json",
        "budget": 0,
        "base_cost": 0,
    }
    with pytest.raises(ValueError, match="repository root"):
        load_loadout(_write_json(tmp_path / "escaped-loadout.json", escaped_loadout))

    price_document = {
        "schema_version": 1,
        "unit": "chaos-equivalent",
        "values": {"divine": math.inf},
        "bench_recipes": {},
        "note": "test input",
        "sources": ["input"],
    }
    _write_json(tmp_path / "bad-prices.json", price_document)
    loadout_document = {
        "schema_version": 1,
        "name": "test",
        "allowed_actions": ["bench"],
        "allowed_essences": [],
        "allowed_bench": [],
        "prices_file": "bad-prices.json",
        "budget": 0,
        "base_cost": 0,
    }
    with pytest.raises(ValueError, match="finite"):
        load_loadout(_write_json(tmp_path / "loadout.json", loadout_document))
