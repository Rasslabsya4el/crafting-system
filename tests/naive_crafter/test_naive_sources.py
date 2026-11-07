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
KINDS = {"wiki", "coe", "datamined", "experiment", "owner"}
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

    assert set(outside) == {"dry_pool_leaves_fewer_mods", "add_refused_when_no_legal_mod"}
    for cite in outside.values():
        assert cite.kind == "coe" and cite.url == "https://www.craftofexile.com/packages/package.js"
        assert not any(token in cite.quote for token in ("{", "}", " = ", "var ", "return ")), cite.id  # prose: no braces, no assignment, no statement


def test_every_rule_is_read_by_an_action_and_every_action_reads_rules_that_exist():
    read = {rule for ids in rules.USED_BY.values() for rule in ids}

    assert read - set(rules.RULES) == set()
    assert set(rules.RULES) - read == set()


def test_every_kind_of_action_of_the_player_has_its_rules():
    assert set(rules.USED_BY) == {"draw", *ORBS.values(), "essence", "bench"} - {"restart"}


def test_the_laws_are_the_published_ones():
    assert rules.MAGIC_COUNTS == {1: 1, 2: 1}
    assert rules.RARE_COUNTS == {4: 8, 5: 3, 6: 1}
    assert rules.CAPACITY == {"normal": 0, "magic": 1, "rare": 3}


@pytest.mark.skipif(not CLAIMS.is_dir(), reason="the claim files are not in this checkout")
def test_every_quote_is_a_quote_of_the_claim_files():
    quotes = claim_quotes()
    made_up = [cite.id for cite in rules.RULES.values() if cite.in_claims and cite.quote not in quotes]

    assert made_up == []
