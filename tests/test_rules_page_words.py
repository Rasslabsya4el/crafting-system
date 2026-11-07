"""Every approximate claim says itself to a person in its own plain words (#553, #481; closes #605).

A page and the text report print an approximate input as its `page_statement` and its `page_source` and never as its id or its
`approximate_reason` (the reason is for the people who maintain the claim and goes to the JSON). This test reads the shipped registry:
no approximate claim lacks the two, none holds a ticket, issue or ADR number, a workflow word ("grill", "main chat"), a file name, a
dotted id or a snake_case token, and no two claims say the same thing (a page would print it twice).
"""

import pytest
from oracle import page_lint

from crafting_system.rules import load_registry

MARKED = sorted((rule for rule in load_registry().values() if rule.approximate), key=lambda rule: rule.id)


def test_the_registry_has_approximate_claims_to_hold():
    assert len(MARKED) > 100


@pytest.mark.parametrize("rule", MARKED, ids=lambda rule: rule.id)
def test_an_approximate_claim_has_a_statement_and_a_source_in_plain_words(rule):
    assert rule.page_statement.strip() and rule.page_source.strip()
    assert len(rule.page_statement.split()) >= 5, "the statement says what is approximate, in a sentence"
    assert rule.page_statement.rstrip().endswith("."), "the statement is a sentence"
    assert len(rule.page_source.split()) >= 2, "the source names the kind of evidence in words"
    assert not rule.page_source.rstrip().endswith("."), "the page adds the full stop after the source"
    assert rule.page_statement != rule.approximate_reason

    for field in ("page_statement", "page_source"):
        assert page_lint.internal_names_in(getattr(rule, field)) == [], (rule.id, field)


def test_no_two_approximate_claims_say_the_same_thing_to_a_person():
    said: dict[tuple[str, str], str] = {}
    for rule in MARKED:
        key = (rule.page_statement, rule.page_source)
        assert key not in said, f"{rule.id} says the same as {said[key]}"
        said[key] = rule.id
