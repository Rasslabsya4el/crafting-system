"""The reviewed verdicts of the benchmark's review row (ticket #634) and the numbers of one use of an action (ticket #617).

A route below the review line that a person took apart prints `reviewed: real find (#591), ratio at review 0.057` and flags
"NEEDS A HUMAN AGAIN" when its ratio moves past the tolerance (either way), a hash of the target or of the route file changes, or the planner's
first divergent action changes. The per-use numbers are pinned on a toy action worked by hand and on the toy route of the divergence tests.
No test asserts a run time.
"""

import pytest
from cli_support import TODAY, price_file, read_json
from targets_support import DATA, EXAMPLES
from test_cli_benchmark import entry_of
from test_cli_benchmark_divergence import REFORGE, CHAOS, landing, run_with_config, tiny  # noqa: F401  (tiny is a fixture)

import crafting_system.cli._benchmark_verdicts as verdicts
from crafting_system.cli import main
from crafting_system.cli._benchmark import BENCHMARKS
from crafting_system.cli._benchmark_divergence import per_use_lines, review_lines, review_of
from crafting_system.cli._benchmark_use import per_use_of, use_numbers
from crafting_system.cli._benchmark_verdicts import COMPLETED, GUIDE, REAL_FIND, Reviewing, Verdict, text_hash
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.config import load_config
from crafting_system.solver import Action, Outcome

ROOT = EXAMPLES.parents[1]
FIND = Verdict("R08", GUIDE, REAL_FIND, (591,), 0.057, "2026-11-07", "t" * 16, "r" * 16, "Fossils Prismatic Fossil")
NO_BLOCK = {"count": 0, "shown": [], "more": None}


def reviewing(**changes):
    kept = {"tolerance": 0.2, "target_hash": FIND.target_hash, "route_hash": FIND.route_hash}
    return Reviewing(FIND, **{**kept, **changes})


# --- the verdict stands, or the row flags again --------------------------------------------------------------


def test_a_verdict_stands_while_nothing_it_was_reviewed_on_has_moved():
    block = reviewing().judge(0.060, FIND.planner_action)  # prices drifted by 5%: within the tolerance

    assert block["again"] is False and block["reasons"] == []
    assert (block["verdict"], block["issues"], block["ratio_at_review"], block["date"]) == (REAL_FIND, [591], 0.057, "2026-11-07")


@pytest.mark.parametrize("ratio, side", [(0.0700, "above"), (0.0450, "below")])
def test_a_ratio_that_moves_past_the_tolerance_either_way_flags_again(ratio, side):
    # the ratio at review 0.057 and a tolerance of 0.2 of it allow 0.0456 to 0.0684
    block = reviewing().judge(ratio, FIND.planner_action)

    assert block["again"] is True and len(block["reasons"]) == 1
    assert f"{side} the ratio at review 0.057" in block["reasons"][0] and "0.046 to 0.068" in block["reasons"][0]


def test_the_tolerance_is_the_one_given_and_is_a_share_of_the_ratio_at_review():
    assert reviewing(tolerance=0.5).judge(0.080, FIND.planner_action)["again"] is False  # 0.057 +- 0.0285
    assert reviewing(tolerance=0.05).judge(0.060, FIND.planner_action)["again"] is True  # 0.057 +- 0.00285


def test_a_changed_first_divergent_action_flags_again_even_at_the_same_ratio():
    block = reviewing().judge(0.057, "Fossils Dense Fossil + Shuddering Fossil")
    none = reviewing().judge(0.057, None)

    assert block["again"] is True and block["reasons"] == [
        "the planner's first divergent action is now Fossils Dense Fossil + Shuddering Fossil, it was Fossils Prismatic Fossil at the review"
    ]
    assert none["again"] is True and "is now none" in none["reasons"][0]


def test_a_changed_hash_of_the_target_or_of_the_route_flags_again_naming_which():
    target = reviewing(target_hash="x" * 16).judge(0.057, FIND.planner_action)
    route = reviewing(route_hash="x" * 16).judge(0.057, FIND.planner_action)
    both = reviewing(target_hash="x" * 16, route_hash="x" * 16).judge(0.057, FIND.planner_action)

    assert target["reasons"] == ["the target file text changed since the review"]
    assert route["reasons"] == ["the route file text changed since the review"]
    assert len(both["reasons"]) == 2


def test_a_ratio_that_is_not_known_any_more_flags_again_and_a_route_without_a_verdict_has_no_block():
    assert reviewing().judge(None, FIND.planner_action)["again"] is True
    assert Reviewing(None, 0.2, "a", "b").judge(0.057, "x") is None


def test_a_hash_does_not_depend_on_the_line_ends_and_a_verdict_is_checked_when_made(tmp_path):
    unix, windows = tmp_path / "a.yaml", tmp_path / "b.yaml"
    unix.write_bytes(b"a: 1\nb: 2\n")
    windows.write_bytes(b"a: 1\r\nb: 2\r\n")
    changed = tmp_path / "c.yaml"
    changed.write_bytes(b"a: 1\nb: 3\n")

    assert text_hash(unix) == text_hash(windows) != text_hash(changed) and len(text_hash(unix)) == 16
    with pytest.raises(ValueError, match="must be one of real find"):
        Verdict("R08", GUIDE, "probably fine", (591,), 0.057, "2026-11-07", "a", "b", "x")
    with pytest.raises(ValueError, match="names no issue"):
        Verdict("R08", GUIDE, REAL_FIND, (), 0.057, "2026-11-07", "a", "b", "x")


# --- the words of the row -----------------------------------------------------------------------------------


def row(ratio, line=0.5, **changes):
    return review_lines("guide", review_of(ratio, line, reviewing(**changes).judge(ratio, FIND.planner_action)), NO_BLOCK)


def test_a_reviewed_route_prints_its_verdict_instead_of_needs_a_human():
    text = "\n".join(row(0.057))

    assert "reviewed: real find (#591), ratio at review 0.057" in text
    assert "NEEDS A HUMAN" not in text


def test_a_route_above_the_line_that_has_a_verdict_still_shows_it():
    text = "\n".join(row(0.6, line=0.5, tolerance=10))  # a wide tolerance, so that the verdict stands

    assert "planner mean / guide mean: 0.600" in text and "reviewed: real find (#591), ratio at review 0.057" in text
    assert "NEEDS A HUMAN" not in text


def test_a_verdict_that_no_longer_holds_prints_needs_a_human_again_with_the_reason_and_what_it_was():
    moved = "\n".join(row(0.075))
    hashed = "\n".join(row(0.057, target_hash="x" * 16))

    assert "NEEDS A HUMAN AGAIN: the ratio is 0.075, above the ratio at review 0.057" in moved
    assert "(reviewed as real find (#591) at ratio 0.057, 2026-11-07)" in moved and "reviewed:" not in moved
    assert "NEEDS A HUMAN AGAIN: the target file text changed since the review" in hashed
    assert "NEEDS A HUMAN:" not in moved + hashed  # the plain row is for a route nobody reviewed


def test_a_route_without_a_verdict_below_the_line_still_prints_needs_a_human_and_one_above_prints_nothing_more():
    below = "\n".join(review_lines("guide", review_of(0.25, 0.5), NO_BLOCK))
    above = review_lines("guide", review_of(0.75, 0.5), NO_BLOCK)

    assert "NEEDS A HUMAN: the planner costs 25.00% of the guide" in below and "AGAIN" not in below
    assert above == ["  planner mean / guide mean: 0.750 (review line 0.5)"]


def test_the_ratio_line_is_missing_but_the_again_row_is_not_when_a_reviewed_ratio_cannot_be_known():
    block = review_of(None, 0.5, reviewing().judge(None, FIND.planner_action))

    (line,) = review_lines("guide", block, NO_BLOCK)
    assert line.startswith("  NEEDS A HUMAN AGAIN: the ratio is not known now")
    assert review_lines("guide", review_of(None, 0.5), NO_BLOCK) == []


# --- the benchmark command ----------------------------------------------------------------------------------


def fresh_verdict(document, **changes):
    """A verdict for R12 made from what the benchmark printed: its ratio, its first divergent action and the hashes of its files now."""
    given = entry_of(document)["given_route"]
    bench = next(each for each in BENCHMARKS if each.id == "R12")
    kept = {
        "ratio": given["mean_ratio"]["ratio"],
        "target_hash": text_hash(ROOT / bench.target),
        "route_hash": text_hash(ROOT / bench.route),
        "planner_action": given["first_divergence"]["solver_action"],
    }
    kept.update(changes)
    return Verdict("R12", GUIDE, REAL_FIND, (591, 592), kept.pop("ratio"), "2026-11-07", **kept)


def run_reviewed(tmp_path, monkeypatch, capsys, name, **changes):
    """R12 benchmarked twice: once to read what a person would review, then with that verdict (changed by `changes`) in the list."""
    (tmp_path / name).mkdir()
    first = run_with_config(tmp_path / name)
    capsys.readouterr()
    monkeypatch.setattr(verdicts, "VERDICTS", (fresh_verdict(first, **changes),))
    (tmp_path / f"{name}-again").mkdir()
    again = run_with_config(tmp_path / f"{name}-again")
    return first, again, capsys.readouterr().out


def test_the_benchmark_prints_a_reviewed_route_as_reviewed_and_keeps_the_verdict_in_the_json(tmp_path, monkeypatch, capsys):
    first, again, text = run_reviewed(tmp_path, monkeypatch, capsys, "a")

    reviewed = entry_of(again)["given_route"]["mean_ratio"]["reviewed"]
    assert reviewed["again"] is False and reviewed["reasons"] == []
    assert reviewed["verdict"] == REAL_FIND and reviewed["issues"] == [591, 592] and reviewed["date"] == "2026-11-07"
    assert reviewed["ratio_at_review"] == pytest.approx(entry_of(first)["given_route"]["mean_ratio"]["ratio"])
    assert reviewed["tolerance"] == load_config({}).benchmark_review_tolerance == 0.2
    assert reviewed["planner_action_at_review"] == "Chaos Orb"
    assert "reviewed: real find (#591, #592), ratio at review" in text and "NEEDS A HUMAN" not in text


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"ratio": 1e-3}, "above the ratio at review 0.001"),  # the ratio at review is far from the one now
        ({"planner_action": REFORGE}, "the planner's first divergent action is now Chaos Orb"),
        ({"target_hash": "0" * 16}, "the target file text changed"),
        ({"route_hash": "0" * 16}, "the route file text changed"),
    ],
)
def test_a_reviewed_route_flags_again_when_the_ratio_the_action_or_a_hash_moved(tmp_path, monkeypatch, capsys, changes, reason):
    first, again, text = run_reviewed(tmp_path, monkeypatch, capsys, "m", **changes)

    block = entry_of(again)["given_route"]["mean_ratio"]["reviewed"]
    assert block["again"] is True and any(reason in each for each in block["reasons"])
    assert "NEEDS A HUMAN AGAIN" in text and "reviewed:" not in text.replace("reviewed as", "")


def test_a_route_with_no_verdict_has_none_in_the_json(tmp_path):
    given = entry_of(run_with_config(tmp_path))["given_route"]

    assert given["mean_ratio"]["reviewed"] is None


def test_the_review_tolerance_is_read_from_the_config_like_the_review_line(tmp_path):
    path = tmp_path / "crafting.toml"
    path.write_text("[benchmark]\nreview_tolerance = 0.35\n", encoding="utf-8")

    assert load_config(env={}, project_root=tmp_path).benchmark_review_tolerance == 0.35
    assert load_config(env={}, project_root=tmp_path).benchmark_review_ratio == 0.5
    assert load_config(env={}, project_root=tmp_path / "no-file").benchmark_review_tolerance == 0.2


@pytest.mark.parametrize("value", ["0", "-0.1", "1", "1.0", "1.5", "20", '"fifth"', "true", "nan"])
def test_a_bad_review_tolerance_is_a_config_error_naming_the_key_and_the_range(tmp_path, value):
    """0 or less is no tolerance; 1 or more never flags a drop (the ratio cannot fall below 0): both are refused with the range."""
    path = tmp_path / "crafting.toml"
    path.write_text(f"[benchmark]\nreview_tolerance = {value}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"crafting\.toml.*review_tolerance.*above 0 and below 1"):
        load_config(env={}, project_root=tmp_path)


def test_a_tolerance_just_inside_the_range_is_read(tmp_path):
    path = tmp_path / "crafting.toml"
    path.write_text("[benchmark]\nreview_tolerance = 0.999\n", encoding="utf-8")

    assert load_config(env={}, project_root=tmp_path).benchmark_review_tolerance == 0.999


def test_the_project_config_states_the_tolerance():
    text = (ROOT / "crafting.toml").read_text(encoding="utf-8")

    assert "review_tolerance = 0.2" in text and "NEEDS A HUMAN AGAIN" in text


# --- the verdicts of the repository -------------------------------------------------------------------------


def test_r08_r09_and_r04_carry_their_verdicts_as_real_finds():
    found = {(each.id, each.side): each for each in verdicts.VERDICTS}

    assert found[("R08", GUIDE)].issues == (591,) and found[("R09", GUIDE)].issues == (592,)
    assert found[("R04", COMPLETED)].issues == (599, 628)
    assert {each.kind for each in found.values()} == {REAL_FIND}
    assert found[("R08", GUIDE)].ratio == pytest.approx(0.058, abs=1e-3) and found[("R09", GUIDE)].ratio == pytest.approx(0.058, abs=1e-3)
    assert found[("R04", COMPLETED)].ratio == pytest.approx(0.331, abs=1e-3)


# What the heavy runs 42395491917 (R04) and 42433997611 (R08, R09: the bought boots are drawn, #640) measured at the committed price snapshot: the ratio planner mean / guide mean and the
# planner's first divergent action. The verdicts were written from it.
MEASURED = {
    ("R08", GUIDE): (0.05781596927097446, "Fossils Prismatic Fossil"),
    ("R09", GUIDE): (0.058222611236752486, "Fossils Prismatic Fossil"),
    ("R04", COMPLETED): (0.33095397065170684, "Exalted Orb"),
}


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_the_verdicts_of_the_real_routes_stand_at_the_measured_ratios_and_flag_again_when_prices_move_them(key):
    """The benchmark prints R08, R09 and R04 reviewed at the numbers of the heavy run, and "NEEDS A HUMAN AGAIN" if a price moved a ratio by a quarter."""
    ratio, action = MEASURED[key]
    found = next(each for each in verdicts.VERDICTS if (each.id, each.side) == key)
    bench = next(each for each in BENCHMARKS if each.id == key[0])
    route = bench.route if key[1] == GUIDE else bench.completed
    here = Reviewing(found, 0.2, text_hash(ROOT / bench.target), text_hash(ROOT / route))

    standing = here.judge(ratio, action)
    text = "\n".join(review_lines(key[1], review_of(ratio, 0.5, standing), NO_BLOCK))
    moved = here.judge(ratio * 1.25, action)

    assert standing["again"] is False and f"reviewed: real find (#{found.issues[0]}" in text and "NEEDS A HUMAN" not in text
    assert moved["again"] is True and "above the ratio at review" in moved["reasons"][0]
    assert here.judge(ratio, "Orb of Alchemy")["again"] is True


def test_every_verdict_names_a_route_of_the_list_and_the_files_it_was_reviewed_on_are_unchanged():
    """A stale hash here means the target or the route changed since a person reviewed it: look again, then write the new hash and the date."""
    by_id = {bench.id: bench for bench in BENCHMARKS}
    seen = set()
    for each in verdicts.VERDICTS:
        assert (each.id, each.side) not in seen, "one verdict to a route half"
        seen.add((each.id, each.side))
        bench = by_id[each.id]
        route = bench.route if each.side == GUIDE else bench.completed
        assert route is not None, f"{each.id} has no {each.side}"
        assert text_hash(ROOT / bench.target) == each.target_hash, f"the target of {each.id} changed since its review"
        assert text_hash(ROOT / route) == each.route_hash, f"the {each.side} file of {each.id} changed since its review"
        assert each.planner_action and each.date.count("-") == 2 and all(number > 0 for number in each.issues)


# --- one use of an action (#617) ----------------------------------------------------------------------------


def toy_priced(*parts):
    """A priced offer worked by hand: each part is (resource, count, price of one), its cost the sum."""
    chaos = tuple((name, count, count * price, "test") for name, count, price in parts)
    return PricedOffer(Offer("toy", None, {name: count for name, count, _ in parts}), sum(part[2] for part in chaos), chaos)


def test_one_use_of_a_toy_action_has_the_chances_and_the_cost_worked_by_hand():
    # of 8 equal chances 1 ends in the goal, 2 in A (one bench craft short of it) and 5 in B: 1/8 = 12.5% and 2/8 = 25%.
    # A fossil (0.2) and a resonator (1.39) cost 1.59 together.
    action = Action("Fossils Prismatic Fossil", 1.59, (Outcome("goal", 1), Outcome("A", 2), Outcome("B", 5)))
    priced = toy_priced(("Prismatic Fossil", 1, 0.2), ("Potent Alchemical Resonator", 1, 1.39))

    use = use_numbers(action, priced, lambda state: state == "goal", lambda state: state == "A")

    assert use["chance"] == pytest.approx(0.125) and use["short"] == pytest.approx(0.25) and use["cost"] == pytest.approx(1.59)
    assert use["reach"] == pytest.approx(0.375)  # the one number: 1/8 + 2/8 = 3/8
    assert use["error"] is None and use["other_items"] == 0
    assert [(part["resource"], part["count"], part["chaos"]) for part in use["parts"]] == [
        ("Prismatic Fossil", 1, 0.2), ("Potent Alchemical Resonator", 1, 1.39)
    ]
    plain = use_numbers(action, priced, lambda state: state == "goal")
    assert plain["short"] is None and plain["reach"] == pytest.approx(0.125)  # a plan with no bench craft has no such reading


def test_the_row_tells_the_chance_and_the_cost_of_one_use_of_each_action_in_player_words():
    action = Action("Fossils Prismatic Fossil", 1.59, (Outcome("goal", 1), Outcome("A", 2), Outcome("B", 5)))
    dear = Action("Fossils Dense Fossil + Shuddering Fossil", 39.76, (Outcome("goal", 3), Outcome("A", 117)))  # 3/120 = 2.5%
    is_goal = lambda state: state == "goal"  # noqa: E731
    planner = use_numbers(action, toy_priced(("Prismatic Fossil", 1, 0.2), ("Potent Alchemical Resonator", 1, 1.39)), is_goal, lambda s: s == "A")
    guide = use_numbers(dear, toy_priced(("Dense Fossil", 1, 17.09), ("Shuddering Fossil", 1, 21.28), ("Resonator", 1, 1.39)), is_goal)
    first = {"state": "S1", "per_use": {"planner": planner, "guide": guide}}

    lines = per_use_lines(first, "guide")

    assert lines[0] == "    one use of each at the first divergence (S1):"
    assert lines[1] == (
        "      the planner's Fossils Prismatic Fossil: one use costs 1.59 Chaos (0.20 for 1 Prismatic Fossil + 1.39 for 1 Potent Alchemical Resonator),"
        " reaches the target with chance 37.50%: the item ends in the target, or is one certain bench craft away from it"
        " (12.50% in the target itself, 25.00% one certain bench craft away)"
    )
    assert lines[2] == (
        "      the guide's Fossils Dense Fossil + Shuddering Fossil: one use costs 39.76 Chaos "
        "(17.09 for 1 Dense Fossil + 21.28 for 1 Shuddering Fossil + 1.39 for 1 Resonator), ends in the target with chance 2.50%"
    )
    assert per_use_lines(None, "guide") == [] == per_use_lines({"state": "S1"}, "guide")


def test_an_action_the_plan_does_not_offer_says_why_instead_of_a_number(tiny):
    plan, result = tiny

    missing = per_use_of(plan, plan.start, "Fossils Prismatic Fossil")

    assert missing["chance"] is None and missing["cost"] is None and missing["error"] == "the plan does not offer it"
    row = per_use_lines({"state": "S1", "per_use": {"planner": missing, "guide": missing}}, "guide")[1]
    assert row.endswith("Fossils Prismatic Fossil cannot be used there: the plan does not offer it")


def test_an_action_the_game_refuses_at_the_state_says_so_in_the_words_of_the_refusal_and_the_row_goes_on(tiny, monkeypatch):
    """The toy plan: the planner's Harvest reforge is refused at the first divergence, the guide's Chaos Orb is not. No crash, the other side keeps its numbers."""
    import crafting_system.cli._benchmark_use as use_module
    import crafting_system.cli._benchmark_divergence as divergence_module
    from crafting_system.cli._report import number_states
    from crafting_system.actions import NotApplicableError, OutOfScopeError

    plan, result = tiny
    divergence = result.divergence
    real = use_module.offer_action

    def refusing(abstraction, priced, state, start=None):
        if priced.label == REFORGE:
            raise NotApplicableError("the item is not rare, and a Harvest reforge needs a rare item")
        return real(abstraction, priced, state, start)

    monkeypatch.setattr(use_module, "offer_action", refusing)
    first = divergence_module.first_divergence_of(plan, DATA, divergence, number_states(plan))
    lines = per_use_lines(first, "guide")

    assert first["per_use"]["planner"]["error"] == "the item is not rare, and a Harvest reforge needs a rare item"
    assert first["per_use"]["planner"]["chance"] is None and first["per_use"]["guide"]["error"] is None
    assert lines[1] == f"      the planner's {REFORGE} cannot be used there: the item is not rare, and a Harvest reforge needs a rare item"
    assert lines[2].startswith(f"      the guide's {CHAOS}: one use costs 1.00 Chaos") and "NotApplicable" not in "\n".join(lines)

    def out_of_scope(abstraction, priced, state, start=None):
        raise OutOfScopeError("no admitted rule covers a cluster jewel")

    monkeypatch.setattr(use_module, "offer_action", out_of_scope)
    gap = per_use_of(plan, divergence.state, CHAOS)
    assert gap["error"] == "no admitted rule covers a cluster jewel" and gap["reach"] is None


def test_the_first_divergence_of_the_toy_route_carries_the_numbers_of_both_actions(tiny, tmp_path, capsys):
    plan, result = tiny
    divergence = result.divergence

    planner = per_use_of(plan, divergence.state, divergence.solver_action)
    guide = per_use_of(plan, divergence.state, divergence.route_action)

    assert (planner["action"], guide["action"]) == (REFORGE, CHAOS)
    # a Chaos Orb is one Chaos by definition: one part, one use, one Chaos
    assert guide["cost"] == 1.0 and guide["parts"] == [{"resource": "Chaos Orb", "count": 1, "chaos": 1.0, "source": "fixed"}]
    assert guide["chance"] == pytest.approx(float(landing(plan, result.policy[plan.start], None)), rel=1e-12)
    assert planner["chance"] == pytest.approx(float(landing(plan, plan.policy[plan.start], None)), rel=1e-12)
    assert planner["cost"] == pytest.approx(sum(part["chaos"] for part in planner["parts"])) and planner["cost"] > 0


def test_the_benchmark_json_and_text_carry_the_numbers_at_the_first_divergence(tmp_path, capsys):
    document = run_with_config(tmp_path, review_ratio=1.0)  # the line is the top: R12's planner is below it, so the row is printed
    text = capsys.readouterr().out

    first = entry_of(document)["given_route"]["first_divergence"]
    # at lifeforce 0.2 the planner rerolls with a Chaos Orb (one Chaos by definition) and the guide with the Harvest reforge
    assert first["solver_action"] == "Chaos Orb" and first["route_action"] == REFORGE
    assert first["per_use"]["planner"]["cost"] == 1.0 and first["per_use"]["guide"]["cost"] > 1.0
    assert 0.0 < first["per_use"]["planner"]["chance"] < 1.0
    assert "one use of each at the first divergence" in text
    assert "the guide's Harvest Reforge Lightning: one use costs" in text and "ends in the target with chance" in text
    assert "bench craft" not in text  # R12 offers no bench craft: the reading does not apply


# --- the start boots of R08 and R09, on the real game data (#617, from #591 and #592) ----------------------

PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
PRISMATIC = "Fossils Prismatic Fossil"
# route -> (target, the guide's pair, [cost of Prismatic, cost of the pair], [chance of reaching the target for each], resources of the pair)
START_BOOTS = {
    "R08": ("r08-energy-shield-boots", "Fossils Dense Fossil + Shuddering Fossil", (1.59, 39.76), (0.022706, 0.022393), ("Dense Fossil", "Shuddering Fossil")),
    "R09": ("r09-life-boots", "Fossils Pristine Fossil + Shuddering Fossil", (1.59, 34.77), (0.024021, 0.026979), ("Pristine Fossil", "Shuddering Fossil")),
}


@pytest.fixture(scope="module", params=sorted(START_BOOTS))
def boots(request):
    from abstraction_support import real_game_data

    from crafting_system.cli import make_plan
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    data = real_game_data()
    target = load_target(ROOT / "examples" / "targets" / f"{START_BOOTS[request.param][0]}.yaml", data)
    plan = make_plan(data, target, load_price_file(PRICES), solve_it=False)
    return request.param, plan


def the_boots_after_the_draw(plan):
    """The item the fossil is used on: since #640 the plan starts at the unopened listing, where only the draw works, and the fossil acts on the rare boots it opens to."""
    return plan.abstraction.compress(plan.target.start_item) if plan.start.flags.unopened else plan.start


def test_one_use_on_the_start_boots_has_equal_odds_and_a_cost_25_times_apart(boots):
    """#591, #592: the Prismatic Fossil and the guide's pair reach the target about as often, at 25 and 22 times the cost per use: the whole of the ratio."""
    route, plan = boots
    _, pair, (cheap_cost, dear_cost), (cheap_odds, dear_odds), pair_parts = START_BOOTS[route]

    cheap = per_use_of(plan, the_boots_after_the_draw(plan), PRISMATIC)
    dear = per_use_of(plan, the_boots_after_the_draw(plan), pair)

    assert cheap["cost"] == pytest.approx(cheap_cost) and dear["cost"] == pytest.approx(dear_cost)
    assert [part["resource"] for part in cheap["parts"]] == ["Primitive Chaotic Resonator", "Prismatic Fossil"]
    assert {part["resource"] for part in dear["parts"]} == {"Potent Chaotic Resonator", *pair_parts}
    assert sum(part["chaos"] for part in dear["parts"]) == pytest.approx(dear_cost)
    # reaching the target: the item is it, or one sure bench craft (the Movement Speed) short of it
    assert cheap["chance"] + cheap["short"] == pytest.approx(cheap_odds, abs=2e-4)
    assert dear["chance"] + dear["short"] == pytest.approx(dear_odds, abs=2e-4)
    assert dear["cost"] / cheap["cost"] > 20
    assert 0.85 < (cheap["chance"] + cheap["short"]) / (dear["chance"] + dear["short"]) < 1.15
    assert cheap["chance"] < 0.002 < cheap["short"]  # the cheap set almost never rolls the Movement Speed itself: its odds are the bench craft


def test_the_row_of_the_start_boots_tells_both_numbers(boots):
    route, plan = boots
    pair = START_BOOTS[route][1]
    first = {
        "state": "S1",
        "per_use": {
            "planner": per_use_of(plan, the_boots_after_the_draw(plan), PRISMATIC),
            "guide": per_use_of(plan, the_boots_after_the_draw(plan), pair),
        },
    }

    lines = per_use_lines(first, "guide")

    assert lines[1].startswith(
        "      the planner's Fossils Prismatic Fossil: one use costs 1.59 Chaos (1.39 for 1 Primitive Chaotic Resonator + 0.20 for 1 Prismatic Fossil), "
        "reaches the target with chance 2."
    )
    assert "reaches the target with chance 2." in lines[1] and "or is one certain bench craft away from it (0." in lines[1]
    assert "reaches the target with chance 2." in lines[2] and "certain bench craft" in lines[2]
    assert f"the guide's {pair}: one use costs " in lines[2] and "Shuddering Fossil" in lines[2]
