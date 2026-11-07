"""The page lint of `tests/oracle/page_lint.py` (ticket #543, rebuild step 2d): it keeps the owner's page rules, and it runs on every golden page.

Three things are tested here.
  * The lint is independent: it imports the standard library only, nothing from `crafting_system` (a scan of its source).
  * Each check fails on the counter-example of its rule and passes on its example. The fixtures are small HTML pages written below
    in the markup of the route page; the counter-example is the one `docs/owner-rules.md` names for the rule, and the example is a
    page that passes the whole lint.
  * Every `tests/golden/*.html` is judged by every check. A page that breaks a rule today is a strict `xfail` that names the issue
    (OR-29), so the day the page is fixed the case turns red until its entry leaves `KNOWN`.

The real pages of R04 and R14 are judged in `tests/test_cli_route_page_heavy.py`, in a heavy run.
"""

import ast
import re
import sys
from html import escape
from pathlib import Path

import pytest
from oracle import page_lint as pl

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = sorted((ROOT / "tests" / "golden").glob("*.html"))
LINT = Path(pl.__file__)

# --- the page lint reads the standard library only ---------------------------------------------------------------


def test_the_lint_imports_the_standard_library_only():
    tree = ast.parse(LINT.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"line {node.lineno}: a relative import"
            modules.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Name) and node.id in {"__import__", "importlib", "exec", "eval"}:
            pytest.fail(f"line {node.lineno}: {node.id}")
        elif isinstance(node, ast.Constant) and node.value in {"crafting_system", "importlib", "__import__"}:
            pytest.fail(f"line {node.lineno}: the string {node.value!r}")
    assert "crafting_system" not in modules
    assert modules <= set(sys.stdlib_module_names), modules - set(sys.stdlib_module_names)


def test_every_check_cites_its_rule_and_the_faults_it_finds_carry_it():
    for check in pl.CHECKS:
        match = re.match(r"\s*(OR-\d+|#\d+ and #\d+)", check.__doc__ or "")
        assert match, f"{check.__name__} does not open its docstring with the rule it keeps"
        assert pl.or_of(check) == match.group(1)
    assert {pl.or_of(check) for check in pl.CHECKS} <= {*(f"OR-{n}" for n in (7, 13, 15, 16, 17, 18, 19, 20, 23, 31)), "#481 and #553"}
    assert pl.or_of(pl.check_no_internal_names) == "#481 and #553"  # a decision of the main chat, not a rule of docs/owner-rules.md (which is not touched)


# --- the markup of the route page, for the fixtures --------------------------------------------------------------


def slot(text: str, tone: str = "m", note: str = "") -> str:
    shown = f'<span class="n"> · {escape(note)}</span>' if note else ""
    return f'<div class="s {tone}">{escape(text)}{shown}</div>'


ANY = slot("any mod or empty", "a")
EMPTY = slot("empty", "e")


def item(name: str = "Boots", rarity: str = "Rare", prefixes=(ANY, ANY, ANY), suffixes=(ANY, ANY, ANY), target: bool = False) -> str:
    properties = "".join(f'<span class="pl">{p}</span>' for p in (rarity, "item level 84"))
    return (
        f'<div class="cd{" tg" if target else ""}"><div class="nm">{escape(name)}</div><div class="pr">{properties}</div>'
        f'<div class="sd">Prefixes</div>{"".join(prefixes)}<div class="sd">Suffixes</div>{"".join(suffixes)}</div>'
    )


def fields(*pairs) -> str:
    cells = ""
    for label, *lines in pairs:
        cells += f'<div class="k">{escape(label)}</div><div class="v ml">{"".join(f"<div>{escape(line)}</div>" for line in lines)}</div>'
    return f'<div class="f">{cells}</div>'


GUARANTEE = "Not offered: Vaal Orb (the target takes no corrupted item). The plan is unaffected: nothing here could be used for this target."


def goal(*pairs, route: str = "Cheapest policy of the planner", leaves=(("Corrupting methods", GUARANTEE),), target: str | None = None) -> str:
    """The first row: the goal card with its part "What this answer leaves out" (when `leaves`), and the target item."""
    out = ""
    if leaves:
        groups = "".join(f'<div class="k">{escape(label)}</div><div class="v ml"><div>{escape(text)}</div></div>' for label, text in leaves)
        out = f'<div><div class="sd">{pl.LEAVES_OUT}</div>{groups}</div>'
    card = f'<div class="cd tg"><h3>Route goal</h3>{fields(("Route", route), *pairs)}{out}</div>'
    return f'<div class="rw">{card}{target or item(prefixes=(slot("+# to maximum Life", "w", "T1"), ANY, ANY), target=True)}</div>'


def step(number: int, title: str, *pairs, after: str | None = None) -> str:
    card = f'<div class="cd" id="s{number}"><h3>{number}. {escape(title)}</h3>{fields(*pairs)}</div>'
    return f'<div class="ar">↓</div><div class="rw">{card}{after or item()}</div>'


def route(*rows: str, anchor: str = "policy", heading: str = "") -> str:
    return f'<section id="{anchor}">{f"<h2>{heading}</h2>" if heading else ""}{"".join(rows)}</section>'


def page(*routes: str) -> str:
    return f"<!doctype html><html><head><title>t</title><style>.s{{color:red}}</style></head><body><main><h1>t</h1>{''.join(routes)}</main></body></html>"


def lint_of(html: str, check) -> list[pl.Fault]:
    return check(pl.read_page(html))


LIFE = slot("+(130-144) to maximum Life", "w", "T1")
TIERS = "+# to maximum Life: T1 ≈0.93% (target) · T2 to T10 ≈0.93% each · none ≈91%"  # the line of the V01 golden, step 3
TWO_ACTIONS = (
    step(1, "Orb of Augmentation", ("Accepts", "other mods: any"), ("Chance per use", "100%")),
    step(2, "Regal Orb", ("Goal", "+(130-144) to maximum Life · T1"), ("Chance per use", "≈0.93%"), ("Tier chances", TIERS)),
)

# --- one counter-example and one example for each check ----------------------------------------------------------

COUNTER: dict[str, dict[str, str]] = {}
EXAMPLE: dict[str, dict[str, str]] = {}


def fixtures(check, counter: dict[str, str], example: dict[str, str]) -> None:
    COUNTER[check.__name__] = counter
    EXAMPLE[check.__name__] = example


AUG = step(1, "Orb of Augmentation", ("Accepts", "other mods: any"), ("Chance per use", "100%"))
FOSSIL_STEP = step(1, "Fossil: Prismatic", ("Cost per use", "1 × Prismatic Fossil 5.87 c"))
LEAGUE = "league Allflame, fetched 2026-11-07"
FOSSIL_PRICE = "Prismatic Fossil: 5.87 Chaos, poe.ninja exchange, Allflame, 2026-11-07, 34 units behind it"
fixtures(
    pl.check_price_source_shown,
    counter={
        "R04: the Prices line is the league and a date, and a step buys a fossil": page(route(goal(("Prices", "league Allflame, fetched 2026-10-31")), FOSSIL_STEP)),
        "a price that names no source": page(route(goal(("Prices", LEAGUE, "Prismatic Fossil: 5.87 Chaos")), FOSSIL_STEP)),
        "a previous league's price with no mark": page(route(goal(("Prices", LEAGUE, "Shrieking Essence of Fear: 0.34 Chaos, poe.ninja, previous league, Mirage, 2026-06-13")), AUG)),
    },
    example={
        "the price names its source and the step's resource is in the list": page(route(goal(("Prices", LEAGUE, FOSSIL_PRICE)), FOSSIL_STEP)),
        "a previous league's price marked approximate": page(route(goal(("Prices", LEAGUE, "Shrieking Essence of Fear: 0.34 Chaos, poe.ninja, previous league, Mirage, 2026-06-13; approximate: previous league's price (Mirage, 2026-06-13)")), AUG)),
        "a Chaos Orb has no price line": page(route(goal(("Prices", LEAGUE)), step(1, "Chaos Orb", ("Cost per use", "1 × Chaos Orb 1 c")))),
    },
)

fixtures(
    pl.check_cut_guarantee,
    counter={
        "R13/R14: Cheapest policy of the planner, no word of the kinds left out": page(route(goal(leaves=()), *TWO_ACTIONS)),
        "a cut that names what is left out and not what still holds": page(route(goal(leaves=(("Corrupting methods", "Not offered: Vaal Orb (the target takes no corrupted item)."),)), *TWO_ACTIONS)),
    },
    example={"a target with an actions: key prints the plan is the cheapest among the named ones": page(route(goal(leaves=(("Methods the target does not name", "Not offered, 23 in all: Chaos Orb and 22 more (kinds this target does not name). The plan is the cheapest among the kinds offered."),)), *TWO_ACTIONS))},
)

fixtures(
    pl.check_mod_format,
    counter={
        "the tier before the mod": page(route(goal(), step(1, "Orb of Alchemy", after=item(prefixes=(slot("T1 +(130-144) to maximum Life", "w"), ANY, ANY))))),
        "a note that is not in the one format": page(route(goal(), step(1, "Orb of Alchemy", after=item(prefixes=(slot("+(130-144) to maximum Life", "w", "tier 1 of 10"), ANY, ANY))))),
        "a bench craft with a spawn tier (R05)": page(route(goal(), step(1, "Benchcraft: +# to maximum Life", after=item(suffixes=(slot("+(35-44) to maximum Life", "c", "T1"), ANY, ANY))))),
        "a base id inside the text": page(route(goal(), step(1, "Orb of Alchemy", after=item(prefixes=(slot("+(35-44) to Dexterity [DexMasterLifeCrafted1]", "m", "T2"), ANY, ANY))))),
    },
    example={
        "V01: the same shape in every card": page(route(goal(), step(1, "Orb of Alchemy", after=item(prefixes=(LIFE, slot("+1 to Level of all Minion Skill Gems", "m", "T2"), ANY))), step(2, "Chaos Orb", after=item(prefixes=(LIFE, slot("(16-20)% chance to Avoid Elemental Ailments", "c", "crafted"), ANY))))),
        "the notes the page uses": page(route(goal(), step(1, "Orb of Alchemy", after=item(prefixes=(slot("+(51-58) to Strength", "w", "essence only"), slot("+# to maximum Life", "w", "tier too low, in some"), slot("36% chance to Avoid being Shocked", "w", "grade 2 (Greater)")))))),
    },
)

fixtures(
    pl.check_bench_line_is_its_craft,
    counter={"R05: the bench step draws another mod's text": page(route(goal(), step(1, "Benchcraft: +# to maximum Life", after=item(suffixes=(slot("+(35-44) to Dexterity", "c", "crafted"), ANY, ANY)))))},
    example={"the crafted line is the craft": page(route(goal(), step(1, "Benchcraft: +# to maximum Life", after=item(suffixes=(slot("+# to maximum Life", "c", "crafted"), ANY, ANY))), step(2, "Benchcraft: Remove Crafted Mods", after=item())))},
)

four = tuple(slot(text, "w", "T2, at least 1 of 4") for text in ("+(42-45)% to Fire Resistance", "+(42-45)% to Cold Resistance", "+(42-45)% to Lightning Resistance", "+(100-114) to maximum Life"))
HEADING_OF_FOUR = '<div class="gh">at least 1 of 4 of these:</div>'
members = tuple(slot(text, "w", "T2") for text in ("+(42-45)% to Fire Resistance", "+(42-45)% to Cold Resistance", "+(42-45)% to Lightning Resistance", "+(100-114) to maximum Life"))
fixtures(
    pl.check_group_printed_once,
    counter={
        "R05: at least 1 of 4 flattened into four lines with notes": page(route(goal(target=item(prefixes=four, target=True)), *TWO_ACTIONS)),
        "a heading and a member that carries the group again": page(route(goal(target=item(suffixes=(HEADING_OF_FOUR, slot("+(42-45)% to Fire Resistance", "w", "T2, at least 1 of 4"), *members[1:]), target=True)), *TWO_ACTIONS)),
    },
    example={
        "the group is one line": page(route(goal(target=item(prefixes=(slot("Fire, Cold or Lightning Resistance or Life", "w", "T2, at least 1 of 4"), ANY, ANY), target=True)), *TWO_ACTIONS)),
        "the group is one heading with its members under it": page(route(goal(target=item(suffixes=(HEADING_OF_FOUR, *members), target=True)), *TWO_ACTIONS)),
    },
)

bought = step(1, "Buy Sorcerer Boots, item level 84", ("Cost per use", "17 c"), after=item("Sorcerer Boots", prefixes=(slot("30% increased Movement Speed", "w", "T2"), ANY, ANY)))
fixtures(
    pl.check_no_hidden_step,
    counter={
        "R08/R09: bought Normal boots, then a fossil on them (the Alchemy is on no page)": page(route(goal(), step(1, "Buy Sorcerer Boots", after=item("Boots", "Normal", (EMPTY,) * 3, (EMPTY,) * 3)), step(2, "Fossil: Pristine", after=item()))),
        "a Normal card that is Rare after a step that does not make it so": page(route(goal(), step(1, "Buy Sorcerer Boots", after=item("Boots", "Normal", (ANY,) * 3, (ANY,) * 3)), step(2, "Orb of Augmentation", after=item("Boots", "Rare")))),
        "an essence on a rare item, no word of the Scouring Orb": page(route(goal(), bought, step(2, "Shrieking Essence of Spite", ("Chance per use", "≈1.9%"), after=item()))),
    },
    example={
        "Alchemy between the Normal boots and the fossil": page(route(goal(), step(1, "Buy Sorcerer Boots", after=item("Boots", "Normal", (ANY,) * 3, (ANY,) * 3)), step(2, "Orb of Alchemy", after=item()), step(3, "Fossil: Pristine", after=item()))),
        "R14: a row that follows the step linking to it, not the restart above it": page(
            route(
                goal(),
                step(1, "Orb of Alchemy", ("Chance per use", "the target: ≈99.6%"), after=item()).replace("<div>the target: ≈99.6%</div>", '<div><a href="#s3">the target: ≈99.6%</a></div>'),
                step(2, "Restart: buy Thicket Bow again", after=item("Thicket Bow", "Normal", (EMPTY,) * 3, (EMPTY,) * 3)),
                step(3, "Benchcraft: +# to maximum Life", after=item(suffixes=(slot("+# to maximum Life", "c", "crafted"), ANY, ANY))),
            )
        ),
        "R10: the essence step notes that it reforges a rare without a Scouring Orb": page(route(goal(), bought, step(2, "Shrieking Essence of Spite", ("Note", "reforges a rare item and keeps only the fractured mod: no Scouring first, the item stays rare"), after=item()))),
    },
)

fixtures(
    pl.check_bought_item_not_empty,
    counter={"R10 as the owner rejected it: the bought boots drawn empty": page(route(goal(), step(1, "Buy Sorcerer Boots, item level 84", after=item("Sorcerer Boots", prefixes=(slot("30% increased Movement Speed", "w", "T2"), EMPTY, EMPTY), suffixes=(EMPTY, EMPTY, EMPTY)))))},
    example={
        "R10 as accepted: any mod or empty for the rest": page(route(goal(), bought)),
        "R04, R14: a bought Normal base has no mods to hide": page(route(goal(), step(1, "Buy Thicket Bow, normal, item level 78", after=item("Thicket Bow", "Normal", (EMPTY,) * 3, (EMPTY,) * 3)))),
    },
)

regal = ("Regal Orb", ("Goal", "+(130-144) to maximum Life · T1"), ("Accepts", "other mods: any"))
fixtures(
    pl.check_one_step_per_action,
    counter={"V01 before #466: the Regal states, one row each, with their own chances": page(route(goal(), step(1, regal[0], *regal[1:], ("Chance per use", "≈0.88%")), step(2, regal[0], *regal[1:], ("Chance per use", "≈0.95%"))))},
    example={"V01: 3 player actions, 3 steps": page(route(goal(), *TWO_ACTIONS, step(3, "Restart: make the start item at the vendor again", ("Cost per use", "8 c"))))},
)

shared = step(1, "Orb of Augmentation", ("Accepts", "other mods: any"), ("Chance per use", "100%"))
differs = step(2, "Chaos Orb", ("Chance per use", "≈3.1%"))
fixtures(
    pl.check_route_not_twice,
    counter={
        "the guide's route drawn after the plan's, step for step": page(route(goal(), shared, differs, heading="Cheapest policy of the planner"), route(goal(route="Given route: Guide"), shared, differs, anchor="given", heading="Given route")),
        "says the route is the same and draws it again": page(route(goal(("Given route", "Same as the given route (R10, PoE Vault guide)")), shared, heading="Cheapest policy of the planner"), route(goal(), step(1, "Essence of Greed"), anchor="given", heading="Given route")),
    },
    example={
        "R10, R11: Same as the given route, one section": page(route(goal(("Given route", "Same as the given route (R10, PoE Vault guide)")), shared, differs)),
        "a guide that differs: only the steps that differ": page(route(goal(), shared, differs, heading="Cheapest policy of the planner"), route(goal(route="Given route: Guide"), step(1, "Essence of Greed", ("Chance per use", "≈5.5%")), anchor="given", heading="Given route")),
    },
)

fixtures(
    pl.check_no_range,
    counter={
        "V01: a Regal row between 0.88% and 0.95%": page(route(goal(), step(1, "Regal Orb", ("Chance per use", "≈0.88% to ≈0.95%")))),
        "a range in words": page(route(goal(), step(1, "Regal Orb", ("Chance per use", "between 0.88% and 0.95%")))),
    },
    example={
        "V01: one chance, the mixture of the eight states": page(route(goal(), step(1, "Regal Orb", ("Chance per use", "≈0.93%")))),
        "a tier run is not a range of one chance": page(route(goal(), *TWO_ACTIONS)),
        "a case with an approximate input prints what it does not know": page(route(goal(("Approximate inputs", "No source says whether the base type stays. Source: the wiki and one forum thread, which disagree."), ), step(1, "Regal Orb", ("Chance per use", "≈0.88% to ≈0.95%")))),
    },
)

fixtures(
    pl.check_approximate_marked,
    counter={
        "a claim says APPROXIMATE in a step and is not listed": page(route(goal(), step(1, "Orb of Alchemy", ("Note", "APPROXIMATE: the weight is a guess")))),
        "an approximate input with only a name": page(route(goal(("Approximate inputs", "The base type")), shared)),
        "an approximate input with a statement and no source": page(route(goal(("Approximate inputs", "The vendor recipe keeps the base type of the item.")), shared)),
        "an approximate input with a source and no statement": page(route(goal(("Approximate inputs", "The base type. Source: the wiki and one forum thread.")), shared)),
        "an approximate input whose source is one word": page(route(goal(("Approximate inputs", "The vendor recipe keeps the base type of the item. Source: unknown.")), shared)),
    },
    example={
        "V01: the vendor claims listed as Approximate inputs, each with its statement and its source": page(route(goal(("Approximate inputs", "The vendor recipe keeps the base type of the input item. Source: the wiki does not say, and the one Reddit thread is split.")), shared)),
        "a claim with a spread": page(route(goal(("Approximate inputs", "One recombination costs 25,000 to 250,000 Dust. Source: player reports. Spread: the planner uses 100,000; reports range from 25,000 to 250,000.")), shared)),
    },
)

priced = "Not offered: Harvest Reforge Fire, Harvest Reforge Life (no price for Wild Crystallised Lifeforce). The plan is the cheapest among the actions that have a price."
fixtures(
    pl.check_no_dropped_for_price,
    counter={"an action with an unpriced resource is dropped, not estimated": page(route(goal(leaves=(("Actions with no price", priced),)), shared))},
    example={"no action is dropped for a price": page(route(goal(), shared))},
)

fixtures(
    pl.check_tier_lines,
    counter={
        "the chances do not sum to 1": page(route(goal(), step(1, "Regal Orb", ("Tier chances", "+# to maximum Life: T1 ≈20% (target) · T2 to T4 ≈10% each · none ≈40%")))),
        "equal chances not joined": page(route(goal(), step(1, "Regal Orb", ("Tier chances", "+# to maximum Life: T1 ≈10% (target) · T2 ≈10% · T3 ≈10% · none ≈70%")))),
        "the target's tier is not marked": page(route(goal(), step(1, "Regal Orb", ("Tier chances", "+# to maximum Life: T1 ≈10% · T2 to T3 ≈10% each · none ≈70%")))),
        "no none": page(route(goal(), step(1, "Regal Orb", ("Tier chances", "+# to maximum Life: T1 ≈50% (target) · T2 50%")))),
        "a gap in the tiers": page(route(goal(), step(1, "Regal Orb", ("Tier chances", "+# to maximum Life: T1 ≈50% (target) · T3 ≈20% · none ≈30%")))),
    },
    example={
        "V01: the target's tier apart, the rest joined": page(route(goal(), *TWO_ACTIONS)),
        "R10: every tier is the target": page(route(goal(), step(1, "Shrieking Essence of Spite", ("Note", "reforges a rare, no Scouring first"), ("Tier chances", "+# to Intelligence: T2 100% · none 0% · every tier is the target")))),
    },
)

fixtures(
    pl.check_tier_step_has_tier_line,
    counter={"R04: the Exalted Orb has a goal and a chance and only that": page(route(goal(), step(1, "Exalted Orb", ("Goal", "+# to maximum Life · T1"), ("Chance per use", "13%"))))},
    example={
        "the step shows the chance of each tier": page(route(goal(), *TWO_ACTIONS)),
        "an Annulment or a Fracturing Orb adds no mod, so no tier to show": page(route(goal(), step(1, "Orb of Annulment", ("Goal", "+# to maximum Life · T1"), ("Chance per use", "≈25%")), step(2, "Fracturing Orb", ("Goal", "+# to maximum Life · T1"), ("Chance per use", "≈25%")))),
        "a bench craft has no chance to show": page(route(goal(), step(1, "Benchcraft: +# to maximum Life", ("Goal", "+# to maximum Life · crafted"), ("Cost per use", "1 c"), after=item(suffixes=(slot("+# to maximum Life", "c", "crafted"), ANY, ANY))))),
    },
)

SRC = " Source: the wiki and one forum thread."
CANDIDATE = {  # name -> (a statement with the internal form in it, the same thing said in words); both lines carry a source, so the whole lint passes the plain one
    "a dotted claim id": ("harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot is read from the wiki." + SRC, "A tagged reforge can be refused when the tag has no mod on a free side." + SRC),
    "a dotted claim id without an underscore": ("conflict.odds are a fit to a sample of 525 uses." + SRC, "The odds of an Orb of Conflict are a fit to a sample of 525 uses." + SRC),
    "a file name": ("The count is read from package.js in the emulator." + SRC, "The count is read from the code of the emulator." + SRC),
    "a Metadata/ path": ("Metadata/Items/Armours/Boots/BootsStr1 keeps its base type." + SRC, "The Sorcerer Boots base keeps its base type." + SRC),
    "a ticket number": ("The reason is in #543 for this claim." + SRC, "The reason is the audit of the pages for this claim." + SRC),
    "an issue or ticket number": ("The choice follows research ticket 86 for this claim." + SRC, "The choice follows the older guide for this claim." + SRC),
    "an ADR number": ("The roll is the simplest reading in ADR-0048 here." + SRC, "The roll is the simplest reading here." + SRC),
    "a workflow word": ("The default of grill B3 is used for this claim." + SRC, "The default of the planner is used for this claim." + SRC),
    "a workflow word, the main chat": ("The claim was settled by the main chat for now." + SRC, "The claim was settled by the planner's own choice for now." + SRC),
    "a base id in brackets": ("Penetrating Arrow Quiver [QuiverNew5] is bought as the start item." + SRC, "The Penetrating Arrow Quiver is bought as the start item." + SRC),
    "a snake_case token": ("The claim spend_law_uniform_everywhere says so." + SRC, "The claim says so in the memory strands post." + SRC),
    "a snake_case token with one underscore": ("The cap is read at elemental_cap = coe for this recipe." + SRC, "The cap is read at the elemental recipe cap of Craft of Exile for this recipe." + SRC),
}


fixtures(
    pl.check_no_internal_names,
    counter={name: page(route(goal(("Approximate inputs", internal)), shared)) for name, (internal, _) in CANDIDATE.items()},
    example={name: page(route(goal(("Approximate inputs", plain)), shared)) for name, (_, plain) in CANDIDATE.items()},
)


def test_every_check_has_a_counter_example_and_an_example():
    assert set(COUNTER) == set(EXAMPLE) == {check.__name__ for check in pl.CHECKS}
    for name in COUNTER:
        assert COUNTER[name] and EXAMPLE[name], name


@pytest.mark.parametrize("check", pl.CHECKS, ids=lambda check: check.__name__)
def test_a_check_fails_on_the_counter_example_of_its_rule(check):
    for case, html in COUNTER[check.__name__].items():
        faults = lint_of(html, check)
        assert faults, f"{pl.or_of(check)} {check.__name__} passes: {case}"
        assert {fault.or_id for fault in faults} == {pl.or_of(check)}, case


@pytest.mark.parametrize("check", pl.CHECKS, ids=lambda check: check.__name__)
def test_a_check_passes_on_the_example_of_its_rule_and_the_page_passes_the_whole_lint(check):
    for case, html in EXAMPLE[check.__name__].items():
        assert lint_of(html, check) == [], case
        assert pl.lint(pl.read_page(html)) == [], case  # the example is a clean page, so a counter-example fails by its own fault only


@pytest.mark.parametrize("name", sorted(CANDIDATE))
def test_the_check_of_internal_names_fails_on_an_internal_name_and_passes_on_words(name):
    internal, plain = CANDIDATE[name]
    assert pl.check_no_internal_names(pl.read_page(page(route(goal(("Approximate inputs", internal)), shared)))), name
    assert pl.check_no_internal_names(pl.read_page(page(route(goal(("Approximate inputs", plain)), shared)))) == [], name


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("vendor.gem_qualification_is_uncorrupted_skill_gems", "a dotted claim id"),
        ("conflict.odds", "a dotted claim id"),
        ("package.js", "a file name"),
        ("issue 93", "an issue or ticket number"),
        ("research ticket 86", "an issue or ticket number"),
        ("ADR-0041", "an ADR number"),
        ("grill B3", "a workflow word"),
        ("the main chat", "a workflow word"),
        ("the owner's in-game list", "a workflow word"),
        ("#182", "a ticket number"),
        ("spend_law_uniform", "a snake_case token"),
        ("elemental_cap", "a snake_case token"),
        ("group_conflict", "a snake_case token"),
    ],
)
def test_every_form_of_an_internal_name_is_found_and_named(text, kind):
    assert kind in {found for found, _ in pl.internal_names_in(f"The claim, {text}, is read.")}


@pytest.mark.parametrize("text", ["poe.ninja", "pathofexile.com", "3.29.3.3", "e.g. a belt", "Source: the wiki.", "ilvl 84.", "T1 to T3"])
def test_a_name_a_person_may_read_is_not_an_internal_name(text):
    assert pl.internal_names_in(text) == []


def test_the_check_of_internal_names_is_one_of_the_checks_and_cites_the_issues_of_its_decision():
    assert pl.check_no_internal_names in pl.CHECKS
    assert {fault.or_id for fault in pl.check_no_internal_names(pl.read_page(page(route(goal(("Approximate inputs", "a.b_c_d: x")), shared))))} == {"#481 and #553"}


def test_the_lint_reads_the_text_and_the_structure_of_the_v01_page():
    read = pl.read_page_file(ROOT / "tests" / "golden" / "v01_minion_helmet.html")
    (only,) = read.routes
    assert [s.title for s in only.steps] == ["Vendor recipe: Helmet with +1 to Minion Skill Gems, 1 recipe", "Orb of Augmentation", "Regal Orb", "Restart: make the start item at the vendor again"]
    regal_step = only.steps[2]
    assert [line.text for line in regal_step.lines("Chance per use")] == ["≈0.93%"]
    assert regal_step.after.rarity == "Rare" and len(regal_step.branches) == 1
    assert only.leaves_out and only.has_leaves_out_heading
    assert [slot_.note for slot_ in only.target.slots[:2]] == ["T2", "T1"]


# --- every golden page, every check -------------------------------------------------------------------------------

ISSUE_UNPRICED = 552  # the issue #543 filed; OR-29 (#550 and #551, the other two, are fixed: no golden page is a known fault of their checks)

KNOWN: dict[tuple[str, str], int] = {  # (golden page, check) -> the issue that holds the fault; a strict xfail names it
    **{(name, "check_no_dropped_for_price"): ISSUE_UNPRICED for name in ("given_route_differs", "r12_fixture", "r12_fixture_given_route", "real_r05", "real_r10", "real_r11")},
}
JUDGES = pl.CHECKS  # check_no_internal_names is one of them since #553: no golden page is a known fault of it


def golden_cases():
    cases = []
    for path in GOLDEN:
        for check in JUDGES:
            issue = KNOWN.get((path.stem, check.__name__))
            marks = [pytest.mark.xfail(strict=True, reason=f"#{issue}")] if issue else []
            cases.append(pytest.param(path, check, marks=marks, id=f"{path.stem}-{check.__name__}"))
    return cases


@pytest.mark.parametrize(("path", "check"), golden_cases())
def test_a_golden_page_keeps_the_rule_of_every_check(path, check):
    page = pl.read_page_file(path)
    assert page.routes and all(route.steps for route in page.routes), "the lint read no route or no step: a page it cannot read passes every check"
    faults = check(page)
    assert faults == [], "\n".join(map(str, faults[:10]))


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<html><body><main><h1>t</h1></main></body></html>",
        "<html><body>" + page(route(goal(), *TWO_ACTIONS)).replace('class="rw"', 'class="row"') + "</body></html>",  # the builder renames a class
        "<html><body>" + page(route(goal(), *TWO_ACTIONS)).replace("<section", "<article").replace("</section", "</article") + "</body></html>",
    ],
    ids=["empty", "no section", "a renamed row class", "a renamed section tag"],
)
def test_a_page_the_lint_cannot_read_raises_instead_of_passing(html):
    with pytest.raises(pl.PageUnreadable):
        pl.read_page(html)


def test_every_known_fault_is_a_golden_page_that_exists_and_names_an_issue():
    assert KNOWN and all(isinstance(issue, int) and issue > 0 for issue in KNOWN.values())
    stems = {path.stem for path in GOLDEN}
    assert {name for name, _ in KNOWN} <= stems
    assert {check for _, check in KNOWN} <= {check.__name__ for check in JUDGES}
