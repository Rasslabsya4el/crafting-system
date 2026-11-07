"""Every rule the naive crafter plays carries its source, URL, quote and date, and the quote is a real one (OR-22, ticket #555).

`rules.py` holds the rules with their citations. Here: each citation is complete; every rule is read by some action and every action reads
only rules that are there; and every quote is one of the quotes of the project's claim files (`src/crafting_system/rules/claims/*.yaml`,
read as plain YAML, nothing of the planner's code), so a quote cannot be changed in one place and not the other, and no quote is made up.
"""

import datetime
import re
from pathlib import Path

import pytest
import yaml
from naive_crafter import rules
from naive_crafter.world import ORBS

CLAIMS = Path(__file__).resolve().parents[2] / "src" / "crafting_system" / "rules" / "claims"
KINDS = {"wiki", "coe", "datamined", "experiment", "owner", "official"}
TODAY = datetime.date(2026, 11, 7)


def claim_quotes() -> set[str]:
    quotes: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("quote"), str):
                quotes.add(node["quote"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted(CLAIMS.glob("*.yaml")):
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return quotes


@pytest.mark.parametrize("cite", list(rules.RULES.values()), ids=list(rules.RULES))
def test_a_rule_names_its_source_url_quote_and_date(cite):
    assert cite.statement.strip() and cite.quote.strip()
    assert cite.kind in KINDS
    assert re.fullmatch(r"https://\S+", cite.url)
    assert datetime.date.fromisoformat(cite.date_checked) <= TODAY
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", cite.patch)


def test_a_rule_that_is_approximate_says_so_and_there_are_two_where_no_first_party_statement_was_found():
    """Both are open points with an issue each (OR-29): the Royale copies, and the generation-weight multiplier (an owner decision of #28)."""
    assert sorted(cite.id for cite in rules.RULES.values() if cite.approximate) == ["generation_weight_multiplier", "royale_copies_do_not_spawn"]
    assert rules.RULES["generation_weight_multiplier"].kind == "owner"


def test_no_rule_rests_on_this_repository_alone_unless_it_says_it_is_an_owner_decision():
    ours = [cite.id for cite in rules.RULES.values() if "Rasslabsya4el/crafting-system" in cite.url and cite.kind != "owner"]

    assert ours == []


def test_a_quote_that_is_not_a_claim_quote_is_the_emulators_notice_or_a_place_and_never_code():
    outside = {cite.id: cite for cite in rules.RULES.values() if not cite.in_claims}

    assert set(outside) == {
        "dry_pool_leaves_fewer_mods",
        "add_refused_when_no_legal_mod",
        "fossil_factors_stack_per_tag",
        "annulment_removes_one_random_mod",
        "remove_crafted_mods_removes_all",
    }
    for cite in outside.values():
        assert cite.kind == "coe" and cite.url == "https://www.craftofexile.com/packages/package.js"
        assert not any(token in cite.quote for token in ("{", "}", " = ", "var ", "return ")), cite.id  # prose: no braces, no assignment, no statement


def test_every_rule_is_read_by_an_action_and_every_action_reads_rules_that_exist():
    read = {rule for ids in rules.USED_BY.values() for rule in ids}

    assert read - set(rules.RULES) == set()
    assert set(rules.RULES) - read == set()


def test_every_kind_of_action_of_the_player_has_its_rules():
    assert set(rules.USED_BY) == {"draw", *ORBS.values(), "essence", "bench", "remove_crafted", "fossil", "harvest"} - {"restart"}


def test_the_laws_are_the_published_ones():
    assert rules.MAGIC_COUNTS == {1: 1, 2: 1}
    assert rules.RARE_COUNTS == {4: 8, 5: 3, 6: 1}
    assert rules.CAPACITY == {"normal": 0, "magic": 1, "rare": 3}


@pytest.mark.skipif(not CLAIMS.is_dir(), reason="the claim files are not in this checkout")
def test_every_quote_is_a_quote_of_the_claim_files():
    quotes = claim_quotes()
    made_up = [cite.id for cite in rules.RULES.values() if cite.in_claims and cite.quote not in quotes]

    assert made_up == []


@pytest.mark.skipif(not CLAIMS.is_dir(), reason="the claim files are not in this checkout")
def test_the_tables_of_the_harvest_reforges_are_the_tables_of_the_claims():
    """`HARVEST_TAGS` and `HARVEST_COST` are copies of the claims' `value` tables (read as plain YAML): a change in one place and not the other fails here."""
    claims = {rule["id"]: rule for rule in yaml.safe_load((CLAIMS / "harvest_reforge.yaml").read_text(encoding="utf-8"))["rules"]}

    assert rules.HARVEST_TAGS == claims["harvest_reforge.tagged_rare_reforge_exists"]["value"]
    assert rules.HARVEST_COST == claims["harvest_reforge.lifeforce_cost"]["value"]


@pytest.mark.skipif(not CLAIMS.is_dir(), reason="the claim files are not in this checkout")
def test_every_rule_added_for_the_tickets_608_to_610_cites_the_claim_that_states_it():
    ids: set[str] = set()
    for path in sorted(CLAIMS.glob("*.yaml")):
        ids |= {rule["id"] for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]}
    unknown = {cite_id: claim for cite_id, claims in rules.CLAIM_OF.items() for claim in claims if claim not in ids}
    shared = {"rare_mod_count", "kept_mods_count_in_total", "bench_option_item_classes", "bench_option_cost", "fractured_mods_kept", "add_refused_when_no_legal_mod"}  # older rules of the first six orbs

    assert unknown == {}
    assert set(rules.CLAIM_OF) <= set(rules.RULES)
    for kind in ("fossil", "harvest", "exalted", "annulment", "fracturing", "remove_crafted"):
        assert [cite_id for cite_id in rules.USED_BY[kind] if cite_id not in shared and cite_id not in rules.CLAIM_OF] == [], kind


def test_the_rules_of_the_actions_added_for_the_tickets_608_to_610_all_exist():
    for kind in ("fossil", "harvest", "exalted", "annulment", "fracturing", "remove_crafted"):
        assert kind in rules.USED_BY and rules.USED_BY[kind], kind
