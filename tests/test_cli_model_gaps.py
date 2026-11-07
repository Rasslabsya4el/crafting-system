"""A model gap is not a game refusal (ticket #506, OR-13, OR-23, OR-26): the two families of `ActionError`, and the limit a gap becomes.

The root of the silent gaps was a missing distinction. `ActionError` has two subclasses, a game refusal (`NotApplicableError`: "the game does not
allow this here") and a model gap (`OutOfScopeError`: "our model has no rule for this here"), but 27 of the 34 `except` clauses caught the parent, so
a plan could leave an action out where the model had no rule and the answer did not say so. Now:

* `ActionError` is never raised itself (`test_the_base_of_the_two_families_cannot_be_raised`);
* every `except` clause that catches a refusal names the family it means, and `CLAUSES` lists them all with the family and the reason
  (`test_every_clause_names_the_family_it_means`, a scan of `src` that a new or changed clause fails until it is listed);
* the clauses that leave an action out of a plan write the gap (`Abstraction.gaps`) and keep a game refusal silent: a planted gap in each of them
  becomes a `Limit`, a planted game refusal does not (`test_a_model_gap_is_a_limit_and_a_game_refusal_is_not_*`);
* the clauses that mean a game refusal let a model gap through (`test_a_clause_for_a_game_refusal_lets_a_model_gap_through`).

The limits of the other rows of #467 and #480 are tested in `test_cli_limits_506.py`.
"""

import ast
import dataclasses
import json
import pathlib
from html import escape
from types import SimpleNamespace

import pytest
from cli_support import R12, price_file
from coarse_support import CRAFTS, REMOVE
from coarse_support import DATA as COARSE
from limits_support import of_kind, only
from targets_support import DATA
from test_cli_approximate import PRICES as APPROX_PRICES
from test_cli_approximate import RATES as APPROX_RATES
from test_cli_approximate import TARGET as APPROX_TARGET

import crafting_system
from crafting_system.abstraction import Abstraction, Coarsening, Gap, ModelGaps
from crafting_system.actions import ActionError, ChaosOrb, ConsumesInputsError, NotApplicableError, OutOfScopeError
from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.cli import _approx, _bound_prune, _donors, _plan
from crafting_system.cli._limits import SHOWN_LABELS, WITHIN_GAP, limit_text, model_gap_limits
from crafting_system.cli._offers import offer_of
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target, parse_target

SRC = pathlib.Path(crafting_system.__file__).parent
FAMILY = {"ActionError", "NotApplicableError", "OutOfScopeError"}
GAME, GAP, RECORDS, EITHER = "game", "gap", "records", "either"

# Every `except` clause of `src` that names a refusal, with the family it means (the scan is `clauses_found`).
# GAME: the game refuses and the clause is about that alone, so a model gap goes through it. GAP: only a model gap. RECORDS: a pair of clauses, the
# game refusal skipped silently and the model gap written in `Abstraction.gaps` (the plan says so). EITHER: both families, named, and why.
CLAUSES: list[tuple[str, str, tuple[str, ...], str, str]] = [
    ("abstraction/_bound.py", "reach_bound", ("OutOfScopeError",), GAP, "no bound is given for a pool the model cannot build"),
    ("abstraction/_coarse.py", "Coarsening._run_members", ("NotApplicableError", "OutOfScopeError"), EITHER, "the first refusal is kept and raised again by `variants`; a model gap wins over a game refusal"),
    ("abstraction/_coarse.py", "Coarsening.reachable", ("NotApplicableError", "OutOfScopeError"), EITHER, "a helper for tests, no caller in src: the blocks reachable by what can be applied"),
    ("abstraction/_estimate.py", "_Pilot.kernel_of", ("NotApplicableError", "OutOfScopeError"), EITHER, "the forecast only counts the graph; the build writes the gap"),
    ("abstraction/_estimate.py", "_Pilot.walked_kernel", ("NotApplicableError", "OutOfScopeError"), EITHER, "the forecast only counts the graph; the build writes the gap"),
    ("abstraction/_inputs.py", "_kernel_of", ("NotApplicableError",), GAME, "the game's refusal of the representative is another placement's: a gap in the model's average"),
    ("abstraction/_pattern.py", "_Universe._seed_named", ("NotApplicableError",), GAME, "the game refuses the offered action on the empty probe item: it adds no mod by name there, nothing is seeded"),
    ("abstraction/_pattern.py", "Pattern._ok", ("OutOfScopeError",), GAP, "a model gap while building the item of a member is raised: whether the member is an item is not known, so none is left out"),
    ("abstraction/_pattern.py", "_explore", ("NotApplicableError",), GAME, "the game refuses the action at this member (its kernel key): it is not an action of the member, counted in `refused_pairs`"),
    ("abstraction/_pattern.py", "_explore", ("OutOfScopeError",), GAP, "a model gap at a member (its kernel key): left out of the key only where `_gap_everywhere` says no member can take it, else the build refuses"),
    ("abstraction/_pattern.py", "_explore", ("NotApplicableError",), GAME, "the game refuses the action at this member (its kernel): it is not an action of the member, counted in `refused_pairs`"),
    ("abstraction/_pattern.py", "_explore", ("OutOfScopeError",), GAP, "a model gap at a member (its kernel): left out of the key only where `_gap_everywhere` says no member can take it, else the build refuses"),
    ("abstraction/_pattern.py", "_gap_everywhere", ("NotApplicableError", "OutOfScopeError"), EITHER, "asks whether any member of the key can take the action: a member refused by the game or by a gap cannot, whichever family"),
    ("abstraction/_kernel.py", "Abstraction.reachable", ("NotApplicableError", "OutOfScopeError"), EITHER, "a helper for tests, no caller in src: the states reachable by what can be applied"),
    ("abstraction/_kernel.py", "Abstraction._prepare", ("NotApplicableError",), GAME, "a game refusal may depend on the family of a fractured mod; a model gap is not asked that"),
    ("abstraction/_kernel.py", "Abstraction._refusal_depends_on_the_family", ("NotApplicableError",), GAME, "the other families of the fractured type are refused too"),
    ("actions/awakener.py", "_awakeners_orb", ("OutOfScopeError",), GAP, "an item class with no influence key lists no orb"),
    ("actions/contract.py", "Action.burn_refusal", ("NotApplicableError", "OutOfScopeError"), EITHER, "the refusal's own text is returned, whichever family"),
    ("actions/fossil.py", "usable_fossils", ("NotApplicableError", "OutOfScopeError"), EITHER, "no fossil is listed for the item; a gap met while listing is #511"),
    ("actions/fossil.py", "usable_fossils", ("NotApplicableError", "OutOfScopeError"), EITHER, "this fossil is not listed for the item; a gap met while listing is #511"),
    ("actions/fossil.py", "fossil_actions", ("NotApplicableError", "OutOfScopeError"), EITHER, "this set is not listed for the item; a gap met while listing is #511"),
    ("actions/recombinator.py", "junk_craft_for", ("NotApplicableError", "OutOfScopeError"), EITHER, "a craft that cannot be made on the item is not a candidate, whichever family"),
    ("actions/socket_colours.py", "ChromaticOrb.burn_refusal", ("NotApplicableError", "OutOfScopeError"), EITHER, "the refusal's own text is returned, whichever family"),
    ("cli/_approx.py", "BlockModel._build", ("NotApplicableError",), RECORDS, "a game refusal in a block: silent"),
    ("cli/_approx.py", "BlockModel._build", ("OutOfScopeError",), RECORDS, "a model gap in a block: written"),
    ("cli/_approx.py", "ExactModel.actions", ("NotApplicableError",), RECORDS, "a game refusal in an expanded state: silent"),
    ("cli/_approx.py", "ExactModel.actions", ("OutOfScopeError",), RECORDS, "a model gap in an expanded state: written"),
    ("cli/_bound_prune.py", "_raised", ("NotApplicableError",), GAME, "the game refuses the offer on the bare item: set aside as inapplicable"),
    ("cli/_bound_prune.py", "_raised", ("OutOfScopeError",), GAP, "no rule on the bare item proves nothing for the states: the offer stays in the search"),
    ("cli/_decide.py", "coarse_cause", ("OutOfScopeError",), GAP, "an action that declares no block invariance gives no coarse level; its text is the reason"),
    ("cli/_donors.py", "DonorModel._candidate", ("NotApplicableError",), RECORDS, "a game refusal: silent"),
    ("cli/_donors.py", "DonorModel._candidate", ("OutOfScopeError",), RECORDS, "a model gap: written"),
    ("cli/_main.py", "main", ("TargetError", "DataError", "PriceFileNotFound", "PlanError", "NotApplicableError", "OutOfScopeError", "ConvergenceError", "ValueError", "OSError"), EITHER, "one `Error:` line with the text of whichever error stopped the run"),
    ("cli/_offers.py", "_roll_limit_can_matter", ("NotApplicableError", "OutOfScopeError"), EITHER, "a pool that cannot be built is no proof the mod is out of reach, so the orb stays and nothing is left out"),
    ("cli/_packed.py", "walk", ("NotApplicableError",), RECORDS, "a game refusal: silent"),
    ("cli/_packed.py", "walk", ("OutOfScopeError",), RECORDS, "a model gap: written"),
    ("cli/_envelope_plan.py", "CraftingProblem.kernel_key", ("NotApplicableError",), RECORDS, "a game refusal: silent (the search leaves the offer out of the state, as the walk does)"),
    ("cli/_envelope_plan.py", "CraftingProblem.kernel_key", ("OutOfScopeError",), RECORDS, "a model gap: written in `Abstraction.gaps`, the offer is left out of the state"),
    ("cli/_envelope_plan.py", "CraftingProblem.kernel", ("NotApplicableError",), RECORDS, "a game refusal: silent"),
    ("cli/_envelope_plan.py", "CraftingProblem.kernel", ("OutOfScopeError",), RECORDS, "a model gap: written in `Abstraction.gaps`"),
    ("cli/_plan.py", "make_plan", ("OutOfScopeError", "NoPolicy", "BoundError"), GAP, "the envelope search cannot answer this target: the bound has no members for it (#507), no policy closed, or the bound fell; the text becomes the `PlanError`"),
    ("cli/_prune.py", "keyed_offers", ("NotApplicableError",), RECORDS, "a game refusal: silent"),
    ("cli/_prune.py", "keyed_offers", ("OutOfScopeError",), RECORDS, "a model gap: written"),
    ("cli/_prune.py", "solver_actions", ("NotApplicableError",), RECORDS, "a game refusal: silent"),
    ("cli/_prune.py", "solver_actions", ("OutOfScopeError",), RECORDS, "a model gap: written"),
    ("cli/_route.py", "_decide", ("NotApplicableError", "OutOfScopeError"), EITHER, "the route's rule cannot be used here, and the line says why"),
    ("cli/_route_completion.py", "losses_at_item.refused", ("NotApplicableError", "OutOfScopeError"), EITHER, "the action cannot be used on this item, for either reason: the check of a completed route counts it as refused"),
    ("cli/_route_packed.py", "_Reading.action", ("NotApplicableError", "OutOfScopeError"), EITHER, "the route has no action here; the gap line says the game refuses it or the walk left it out"),
    ("cli/_route_packed.py", "_Reading.action", ("NotApplicableError", "OutOfScopeError"), EITHER, "that offer is not a twin here"),
    ("cli/_route_sim.py", "route_policy.policy", ("NotApplicableError", "OutOfScopeError"), EITHER, "the rule's action cannot be used on this item: a gap of the route"),
    ("targets/corrupted.py", "CorruptedResolver._pools", ("NotApplicableError", "OutOfScopeError"), EITHER, "the target cannot ask for `corrupted: true` here, and the error says why"),
    ("targets/parse.py", "_Ladder.tiers", ("OutOfScopeError",), GAP, "an item class with no influence key: the tiers of the base"),
    ("targets/floor.py", "_change_points", ("NotApplicableError", "OutOfScopeError"), EITHER, "no pool to read, so every level counts and nothing is left out"),
]
# Clauses that catch the refusals through their parent `ValueError` (both families are ValueErrors) or through a tuple constant (`ROUTE_ERRORS`), in the
# packages that walk, solve and plan. Listed so they are not forgotten; `NOT_A_REFUSAL` says no action is called inside, or that the error is not a refusal.
NOT_A_REFUSAL = "not a refusal"
OTHERS: list[tuple[str, str, tuple[str, ...], str, str]] = [
    ("abstraction/_pattern.py", "Pattern._ok", ("ValueError", "ItemError"), NOT_A_REFUSAL, "`_item_of` of a state that no item has (two slots of a family, more slots than families): the member is not an item; no action is called"),
    ("abstraction/_prime.py", "prime", ("ValueError",), EITHER, "a request `kernel` would refuse is left to `kernel`, which raises it in its own order"),
    ("abstraction/_coarse.py", "Coarsening._name", ("ValueError",), NOT_A_REFUSAL, "`Action.label` of an unknown id: the repr is shown instead"),
    ("abstraction/_estimate.py", "_Pilot._name", ("ValueError",), NOT_A_REFUSAL, "`Action.label` of an unknown id: the repr is shown instead"),
    ("abstraction/_estimate.py", "_Pilot.walked_kernel", ("ValueError",), NOT_A_REFUSAL, "after the clause for both families: a kernel error that is no refusal makes the forecast refuse (`EstimateRefused`)"),
    ("abstraction/_kernel.py", "Abstraction._refusal_depends_on_the_family", ("ItemError", "ValueError"), NOT_A_REFUSAL, "the item cannot be built with another family: no other family is left to try; no action is called"),
    ("actions/corruption.py", "_vaal_orb", ("ValueError",), EITHER, "a class with no corrupted pool lists no Vaal Orb, whichever family refuses; a model gap met while listing is #511"),
    ("actions/recombinator.py", "Recombinator.outcomes", ("TypeError", "ValueError", "OverflowError"), NOT_A_REFUSAL, "the exponent of the reading is no number; no action is called"),
    ("cli/_benchmark.py", "benchmark_main", ("DataError", "ValueError", "OSError"), EITHER, "one `Error:` line with the text of whichever error stopped the command"),
    ("cli/_benchmark.py", "run_route", ("ValueError", "OSError", "DataError", "PriceFileNotFound", "ConvergenceError"), EITHER, "`ROUTE_ERRORS`: ValueError is the parent of both families and of every other error of a route; the entry carries the text of whichever"),
    ("cli/_decide.py", "measure_solve_rate_detail", ("ConvergenceError", "ValueError"), NOT_A_REFUSAL, "the solver on the pilot graph; it calls no action. Written as the reason the rate was guessed (M2)"),
    ("cli/_plan.py", "make_plan", ("ValueError",), EITHER, "`offers_for` failed: the text becomes the `PlanError`, whichever family or error it was"),
    ("cli/_plan.py", "make_plan", ("ValueError",), EITHER, "`climb` found no level: the text becomes the `PlanError`, whichever family or error it was"),
    ("cli/_report.py", "_leaf_chance", ("ValueError",), EITHER, "the chance of one use is left out of the line; display only, no plan is changed"),
    ("cli/_route_view.py", "_View.leaf_text", ("ValueError",), NOT_A_REFUSAL, "the trade site's stat list: no action is called"),
    ("cli/_route_view.py", "_trade_stats", ("OSError", "ValueError", "AttributeError"), NOT_A_REFUSAL, "the recorded stat list on disk: no action is called"),
    ("cli/_trade.py", "trade_main", ("TradeError", "TargetError", "DataError", "PriceFileNotFound", "ValueError", "OSError"), NOT_A_REFUSAL, "the trade command: no action is called"),
]
SCOPE = {"abstraction", "actions", "cli", "risk", "solver", "targets", "simulator"}  # the packages that walk, solve and plan


def _names(node) -> tuple[str, ...]:
    if node is None:
        return ()
    if isinstance(node, ast.Tuple):
        return tuple(name for each in node.elts for name in _names(each))
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    return ()


class _Handlers(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.found: list[tuple[str, tuple[str, ...], ast.ExceptHandler]] = []

    def _enter(self, node) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _enter

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.found.append((".".join(self.scope) or "<module>", _names(node.type), node))
        self.generic_visit(node)


def handlers_in(path: pathlib.Path) -> list[tuple[str, tuple[str, ...], ast.ExceptHandler]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {  # a module-level tuple of errors: `except ROUTE_ERRORS` catches what it holds
        target.id: _names(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    finder = _Handlers()
    finder.visit(tree)
    return [(function, constants.get(caught[0], caught) if len(caught) == 1 else caught, node) for function, caught, node in finder.found]


def clauses_found() -> list[tuple[str, str, tuple[str, ...], ast.ExceptHandler]]:
    """Every `except` clause of `src` that names a refusal family, or `ValueError` (their parent) in the packages that walk, solve and plan.

    A clause that names a tuple constant (`except ROUTE_ERRORS`) is read through it.
    """
    found = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        for function, caught, node in handlers_in(path):
            if FAMILY & set(caught) or ("ValueError" in caught and relative.split("/")[0] in SCOPE):
                found.append((relative, function, caught, node))
    return found


def test_every_clause_names_the_family_it_means():
    found = [(file, function, caught) for file, function, caught, _ in clauses_found()]
    listed = [(file, function, caught) for file, function, caught, _, _ in (*CLAUSES, *OTHERS)]

    assert sorted(found) == sorted(listed)  # a clause added, removed or changed is listed here with the family it means, or this fails
    assert not [clause for clause in found if "ActionError" in clause[2]]  # none catches the parent: it cannot tell the two families apart
    assert all(reason for *_, reason in (*CLAUSES, *OTHERS))


def test_a_clause_that_leaves_an_action_out_of_a_plan_writes_the_gap_and_keeps_the_game_refusal_silent():
    by_place = {}
    for file, function, caught, node in clauses_found():
        by_place.setdefault((file, function), []).append((caught, node))
    records = {(file, function) for file, function, _, family, _ in CLAUSES if family == RECORDS}

    assert len(records) == 8  # keyed_offers, solver_actions, the packed walk, the donors, the block model, the exact model and the two of the envelope search
    for place in records:
        game, gap = [(caught, node) for caught, node in by_place[place] if len(caught) == 1]
        assert game[0] == ("NotApplicableError",) and gap[0] == ("OutOfScopeError",), place
        assert not _writes_a_gap(game[1]), place
        assert _writes_a_gap(gap[1]), place


def _writes_a_gap(handler: ast.ExceptHandler) -> bool:
    """Whether the clause calls `<...>.gaps.note(...)`."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "note":
            owner = node.func.value
            if isinstance(owner, ast.Attribute) and owner.attr == "gaps":
                return True
    return False


def test_the_clauses_that_mean_a_game_refusal_name_only_it():
    meant = {(file, function) for file, function, _, family, _ in CLAUSES if family == GAME}
    for file, function, caught, _ in clauses_found():
        if (file, function) in meant and len(caught) == 1 and caught != ("OutOfScopeError",):
            assert caught == ("NotApplicableError",), (file, function)


def test_the_base_of_the_two_families_cannot_be_raised():
    with pytest.raises(TypeError, match="NotApplicableError .* OutOfScopeError"):
        raise ActionError("refused")
    assert issubclass(NotApplicableError, ActionError) and issubclass(OutOfScopeError, ActionError)
    assert issubclass(ConsumesInputsError, OutOfScopeError) and not issubclass(ConsumesInputsError, NotApplicableError)
    assert str(OutOfScopeError("no rule")) == "no rule"  # the subclasses keep their message


# --- the planted gap: a clause that records ----------------------------------------------------------------------------

LEFT_OUT = "Harvest Reforge Defence"  # an action of R12 that the planted refusal is about


@pytest.fixture
def refusing(monkeypatch):
    """`refusing(error, "kernel_key")`: the offer `LEFT_OUT` raises `error` in `Abstraction.kernel_key` (or `kernel`) from now on; the others are as they are."""

    def plant(error, method="kernel_key"):
        real = getattr(Abstraction, method)

        def planted(self, state, action):
            if action.label(self.data) == LEFT_OUT:
                raise error(f"planted: {error.__name__} for {LEFT_OUT}")
            return real(self, state, action)

        monkeypatch.setattr(Abstraction, method, planted)

    return plant


def plan_of(**options):
    return make_plan(DATA, load_target(R12, DATA), price_file(), **options)


def gaps_of(plan):
    return of_kind(plan.limits, "model-gap")


@pytest.mark.parametrize("method", ["kernel_key", "kernel"])
def test_a_model_gap_is_a_limit_and_a_game_refusal_is_not_in_the_object_walk(refusing, monkeypatch, method):
    if method == "kernel":
        monkeypatch.setattr(_plan, "MERGE_EQUAL", False)  # no key is built, so `solver_actions` meets the refusal in `offer_action`
    refusing(NotApplicableError, method)
    game = plan_of(solver="object")  # the object solver alone: "auto" walks the graph on packed arrays first, which would write the gap too
    refusing(OutOfScopeError, method)
    gap = plan_of(solver="object")

    assert not gaps_of(game) and not game.abstraction.gaps  # the plan is exact under a game refusal, and says nothing
    (limit,) = gaps_of(gap)
    assert limit.labels == (f"{LEFT_OUT} in 1 state",) and "planted: OutOfScopeError" in limit.reason()
    assert limit.guarantee == "The plan is the cheapest among the actions the model can apply in each state. An action the model has no rule for could make it cheaper."
    assert gap.abstraction.gaps.entries() == (Gap(LEFT_OUT, 1, f"planted: OutOfScopeError for {LEFT_OUT}", False),)
    assert LEFT_OUT not in {action.label for action in gap.policy.values()}  # the plan still answers, with the actions the model can apply


def test_a_model_gap_is_a_limit_and_a_game_refusal_is_not_in_the_packed_walk(refusing):
    refusing(NotApplicableError, "kernel")
    game = plan_of(solver="packed")
    refusing(OutOfScopeError, "kernel")
    gap = plan_of(solver="packed")

    assert game.packed is not None and not gaps_of(game)
    (limit,) = gaps_of(gap)
    assert limit.labels == (f"{LEFT_OUT} in 1 state",)


def approximate_plan(monkeypatch, error=None):
    """The coarse fixture of `test_cli_approximate` planned approximately; with `error`, Remove Crafted Mods raises it in every kernel."""
    names = set()
    for action in (*CRAFTS, REMOVE):
        names |= set(offer_of(action, action.label(COARSE), COARSE).resources)
    prices = dataclasses.replace(APPROX_PRICES, prices={name: PriceEntry(2.0, "test") for name in names})
    keys = json.dumps(["chaos-orb", "remove-crafted-mods", *(craft.label(COARSE) for craft in CRAFTS)])
    target = parse_target(APPROX_TARGET + f"actions: {keys}\n", COARSE, source="t.yaml")
    exact = make_plan(COARSE, target, prices)
    forecast = exact.abstraction.estimate([exact.start], [priced.offer.action for priced in exact.offers])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    budget = (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2
    if error is not None:
        real = Abstraction.kernel
        refused = REMOVE.label(COARSE)

        def planted(self, state, action):
            if action.label(self.data) == refused:
                raise error("planted")
            return real(self, state, action)

        monkeypatch.setattr(Abstraction, "kernel", planted)
    return make_plan(COARSE, target, prices, budget=budget, rates=APPROX_RATES), REMOVE.label(COARSE)


def test_a_model_gap_in_a_block_is_a_limit_of_an_approximate_answer_that_claims_only_the_gap(monkeypatch):
    game, refused = approximate_plan(monkeypatch, NotApplicableError)
    assert game.approximation is not None and not gaps_of(game)
    monkeypatch.undo()
    gap, refused = approximate_plan(monkeypatch, OutOfScopeError)

    assert gap.approximation is not None
    (limit,) = gaps_of(gap)
    assert any(label.startswith(refused) for label in limit.labels)
    assert all(" group of states" in label or " groups of states" in label for label in limit.labels)  # blocks are counted as blocks, not as item states
    assert WITHIN_GAP in limit.guarantee and not limit.guarantee.startswith("The plan is the cheapest")  # the cheapness is that of the answer that made it


def one_offer(plan):
    return [next(priced for priced in plan.offers if priced.label == LEFT_OUT)]


@pytest.mark.parametrize("error, written", [(NotApplicableError, False), (OutOfScopeError, True)])
def test_the_block_model_writes_a_model_gap_of_a_block_and_not_a_game_refusal(error, written):
    plan = plan_of()

    class Blocks:  # what `BlockModel` asks of a coarsening
        abstraction = plan.abstraction

        def require_invariant(self, action):
            pass

        def variants(self, block, action, bound):
            raise error("planted")

    model = _approx.BlockModel(Blocks(), plan.start, one_offer(plan), "lower")

    assert model.actions(plan.start) == []  # left out of the block either way
    assert bool(plan.abstraction.gaps) is written
    assert not written or plan.abstraction.gaps.entries()[0].label == LEFT_OUT


@pytest.mark.parametrize("error, written", [(NotApplicableError, False), (OutOfScopeError, True)])
def test_the_exact_model_of_a_tail_cut_writes_a_model_gap_of_a_state_and_not_a_game_refusal(monkeypatch, error, written):
    plan = plan_of()
    monkeypatch.setattr(Abstraction, "kernel", lambda self, state, action: (_ for _ in ()).throw(error("planted")))

    exact = _approx.ExactModel(plan.abstraction, plan.start, one_offer(plan))

    assert exact.actions(plan.start) == []
    assert bool(plan.abstraction.gaps) is written


def test_a_model_gap_of_the_donor_model_is_written_and_a_game_refusal_is_not(monkeypatch):
    plan = plan_of()
    priced = next(each for each in plan.offers if each.label == LEFT_OUT)
    model = _donors.DonorModel(plan.abstraction, plan.start, [])
    for error, written in ((NotApplicableError, False), (OutOfScopeError, True)):
        plan.abstraction.gaps = ModelGaps()
        monkeypatch.setattr(Abstraction, "inputs", lambda self, state, action, error=error: (_ for _ in ()).throw(error("planted")))
        assert model._candidate(plan.start, priced) is None
        assert bool(plan.abstraction.gaps) is written


def test_the_bound_pruning_keeps_an_offer_the_model_has_no_rule_for_and_sets_aside_one_the_game_refuses(monkeypatch):
    """The pruning used to call both "the game refuses it on this item wherever it can be", which a model gap does not make true (K14, OR-13)."""
    from fractions import Fraction

    kinds = {}
    for error in (NotApplicableError, OutOfScopeError):
        monkeypatch.setattr(_bound_prune, "keeps_shape", lambda *args, error=error: (_ for _ in ()).throw(error("planted")))
        kinds[error] = _bound_prune._raised(SimpleNamespace(data=None), None, None, (), ChaosOrb(), _bound_prune.REROLL, 0, Fraction(1), 1)

    assert kinds[NotApplicableError][0] == _bound_prune.REFUSED  # proved never usable: set aside, and said so
    assert kinds[OutOfScopeError][0] == _bound_prune.TERMINAL  # not proved: it stays in the search, where its gap is written


def test_a_clause_for_a_game_refusal_lets_a_model_gap_through(monkeypatch):
    plan = plan_of()
    ability = plan.abstraction
    asked = []
    monkeypatch.setattr(Abstraction, "_refusal_depends_on_the_family", lambda self, *args: asked.append(args))
    chaos = ChaosOrb()
    for error in (OutOfScopeError, NotApplicableError):
        asked.clear()
        monkeypatch.setattr(ChaosOrb, "outcomes_under", lambda self, data, item, reading=None, error=error: (_ for _ in ()).throw(error("planted")))
        ability._prepared_by.clear()
        with pytest.raises(error):
            ability.kernel(plan.start, chaos)
        assert bool(asked) is (error is NotApplicableError)  # `_prepare` asks whether a game refusal depends on a fractured family; a gap is no refusal


def test_a_model_gap_is_not_hidden_by_a_game_refusal_in_a_block():
    from crafting_system.abstraction import Coarsening

    class Held:
        pass

    refusals = [NotApplicableError("the game refuses"), OutOfScopeError("the model has no rule")]
    plan = plan_of()
    coarse = Coarsening(plan.abstraction)
    members = iter(["first", "second"])
    calls = []

    def kernel(member, action):
        calls.append(member)
        raise refusals[len(calls) - 1]

    plan.abstraction.kernel = kernel  # type: ignore[method-assign]
    found = coarse._run_members(list(members), ChaosOrb(), False)

    assert isinstance(found.error, OutOfScopeError)  # the second member's gap wins over the first member's game refusal


# --- the limit: G6, the text, the JSON and the page --------------------------------------------------------------------


def test_g6_an_action_that_consumes_other_items_is_a_limit_of_its_own_and_a_plain_gap_is_not_one():
    from cli_support import R12 as target_path
    from contract_support import CONTRACT_DATA
    from inputs_support import TOY_ORB, ToyGraft
    from test_actions_inputs import _offers_with
    from crafting_system.prices import PriceEntry

    prices = dataclasses.replace(price_file(), prices={**price_file().prices, TOY_ORB: PriceEntry(0.0001, "test")})
    plan = make_plan(CONTRACT_DATA, load_target(target_path, CONTRACT_DATA), prices, offers=_offers_with(ToyGraft(with_axis=False)))

    consumes = only(plan.limits, "consumes-items")
    assert consumes.labels == ("Toy Graft",) and "consume other items" in consumes.why
    assert consumes.guarantee.startswith("The plan is the cheapest among the actions that consume no other item.")
    assert not of_kind(plan.limits, "model-gap")  # the same refusal is not counted twice
    assert plan.abstraction.gaps.entries()[0].consumes_inputs is True
    assert "Toy Graft" not in {action.label for action in plan.policy.values()}


def test_a_plan_with_a_model_gap_shows_it_in_the_text_the_json_and_the_page(refusing):
    refusing(OutOfScopeError)
    plan = plan_of()
    report = build_report(plan, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    (limit,) = gaps_of(plan)
    assert limit_text(limit) in text  # the text names every label and says what the answer still guarantees
    (entry,) = [each for each in document["limits"] if each["kind"] == "model-gap"]
    assert entry["labels"] == list(limit.labels) and entry["guarantee"] == limit.guarantee and entry["why"] == limit.reason()
    assert escape(limit_text(limit, SHOWN_LABELS)) in page
    assert "Actions the model has no rule for in some states" in page


def test_the_guarantee_of_a_model_gap_is_the_gapped_one_on_an_approximate_answer():
    limit = model_gap_limits([Gap("Fusing", 3, "no rule", False)])[0]
    gapped = dataclasses.replace(limit, guarantee=limit.approximate, approximate="")

    assert limit.guarantee.startswith("The plan is the cheapest") and WITHIN_GAP in gapped.guarantee
    assert limit.labels == ("Fusing in 3 states",) and model_gap_limits([]) == ()
    assert model_gap_limits([Gap("Fusing", 3, "no rule", False, True), Gap("Fusing", 1, "no rule", False, True)])[0].labels == ("Fusing in 3 groups of states", "Fusing in 1 group of states")


def test_the_causes_of_many_gaps_are_named_three_at_a_time():
    gaps = [Gap(f"Orb {n}", 1, f"cause {n}", False) for n in range(5)]

    (limit,) = model_gap_limits(gaps)

    assert limit.names == ("cause 0", "cause 1", "cause 2", "2 more causes")
    assert len(limit.labels) == 5


def test_a_state_met_again_counts_once():
    gaps = ModelGaps()
    for _ in range(3):
        gaps.note("Orb", "state-1", OutOfScopeError("no rule"))
    gaps.note("Orb", "state-2", OutOfScopeError("no rule"))

    assert gaps.entries() == (Gap("Orb", 2, "no rule", False),)
    assert not ModelGaps()

