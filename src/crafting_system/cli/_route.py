"""Given routes: a crafting route written down as rules and evaluated exactly as a fixed policy.

A guide states no cost, so the cost of its route is found by writing the route as a YAML file and
evaluating it with `risk.evaluate` at the same prices as the solver's policy (ADR-0013). The file:

    name: R12, PoE Vault guide        # optional
    skip_refused: true                # optional (default false): a rule whose action the game refuses at a state is passed over
                                      # to the next rule that matches, instead of leaving a gap (for a route completed by a last `restart`)
    rules:                            # required, non-empty; in every state the FIRST rule that matches is followed
      - when:                         # optional; no `when` matches every state
          rarity: rare                # normal, magic or rare, or a list of them
          corrupted: false
          fractured: none             # or [{family: LightningResistance}]: every listed family is fractured on the item;
                                      # or {without: [{family: Pierce}]}: some mod is fractured and none of the listed families is
          crafted_mods: false         # the item holds a crafted mod or metamod
          open_suffixes: 1            # at least this many free suffixes (open_prefixes likewise); needs a bench action offered
          imprints: 1                 # exactly this many imprints held (ADR-0060; 0 for none); needs an imprint action offered (#223)
          veil: prefix                # the item holds a veiled placeholder on that side: prefix, suffix, any, or none (an unveil offered)
          offer: none                 # no unveil offer is drawn; `drawn`: one is; or {shows: {stat: "..."}, at: 2}: the 2nd mod shown
                                      # (the one `Pick 2` takes) meets that requirement of the target (without `at`: any mod shown does)
          requirements:               # the status of a requirement of the target, named by its selector
            - stat: "+1 to Level of all Lightning Skill Gems"    # or `family: ID`, as the target writes it
              status: absent          # absent, below or passing, or a list of them
        do: Harvest Reforge Lightning # an action as the solver prints it, or `restart`

A plan that makes second items (a recombinator, ticket #225) reads the route on every item it makes: the target's own and each second item a
recombination consumes, which starts as a Normal item of the base. `when: {making: target}` is a rule for the target's own item, `when:
{making: [{family: ID}, ...]}` (or `stat:`) a rule for the second item that holds exactly those mods of the target, and a rule without
`making` is for any item. A recombination is named by its label, which names its second item ("Recombinator with a donor of ...").

`restart` buys the start item again: an action that costs the start price and ends in the start state. Only a bought start item has one; a given item is never bought again (OR-6).
Conditions speak only of what the compressed state holds; one it cannot answer yet (mods per side, metamods)
is refused, not guessed. `open_prefixes` and `open_suffixes` count the free slots of a side, which the state holds only
when a bench action is offered (the other mods are then kept as slots); without one they are refused. A goal state is never acted on. A reachable state that no rule
covers (or where the game refuses the rule's action) is a GAP: it has no policy entry, so the route
never finishes from there, which `risk.evaluate` reports as a success chance below 1 and an infinite
mean. Errors are worded `<file>:<line>: <key path>: <problem>`, as the target loader's are.

A COMPLETED ROUTE (tickets #599, #628). A guide with a gap never finishes, so the benchmark also evaluates the guide completed (`BenchmarkRoute.completed`, the
file `<route>-restart.yaml`): the guide's rules, in order, plus rules the guide does not have, each marked "NOT IN THE GUIDE" in the file with its reason, and
`skip_refused: true`. What it may add is any number of rules, each of which fills a gap of the guide with the guide's own loop plus the actions the game forces to take or re-enter that
loop (R14's removal of the crafts, #619); it never takes the planner's own move; and it never restarts where the guide's loop could keep the progress. The last clause is checked
(`_route_completion.py`): wherever a rule the guide does not have fires a `restart`, every action the guide's rules name must be refused by the game
there. `tests/test_route_completion.py` runs the check on hand-built items of every completed route in `examples/routes/`; `.github/scripts/completion_check.py`
runs it on every state the route reaches (R04 and R14, a heavy run). A guide rule that must change to keep the loop from cycling (R04's step 7 asks a free
prefix, or craft and remove would repeat for ever) is named in the file's header with the guide's own words.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from crafting_system.abstraction import CompressedState, Status
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.data import GameData
from crafting_system.items import Rarity, Side, capacity
from crafting_system.risk import RiskReport, lump
from crafting_system.solver import MAIN, Action, Outcome, Solution
from crafting_system.targets import KOfN, Requirement, TargetError
from crafting_system.targets.lines import LineList, LineMap, load_with_lines
from crafting_system.targets.parse import describe
from crafting_system.targets.resolve import Resolver, Unresolved, close_matches, quoted
from crafting_system.planner import UNPRICED, PackedPolicy, Plan, PlanError, evaluate_risk, free_action_cost, offer_action

from ._reach import policy_states

RESTART = "restart"
TOP_KEYS = ("name", "skip_refused", "rules")
RULE_KEYS = ("when", "do")
WHEN_KEYS = ("rarity", "corrupted", "fractured", "crafted_mods", "open_prefixes", "open_suffixes", "imprints", "veil", "offer", "requirements", "making")
VEIL_SIDES = {"prefix": "VeiledPrefix", "suffix": "VeiledSuffix"}  # the slot kind of the generic placeholder of each side (ADR-0026)
VEIL_KINDS = frozenset(VEIL_SIDES.values())
VEIL_VALUES = ("prefix", "suffix", "any", "none")
OFFER_VALUES = ("none", "drawn")
TARGET = "target"  # `making: target`: the rule is for the target's own item, not for a second item a recombination consumes
REQUIREMENT_KEYS = ("stat", "family", "status")
RARITIES = tuple(rarity.value for rarity in Rarity)
STATUSES = tuple(status.name.lower() for status in Status)

# Conditions a later ticket adds to the compressed state; until then a rule using one is refused.
REFUSED_KEYS = (
    "prefixes", "suffixes", "free_prefixes", "free_suffixes", "free_slots", "metamods", "mods_per_side",
    "prefix_count", "suffix_count", "crafted_prefixes", "crafted_suffixes",
)  # fmt: skip


class RouteError(ValueError):
    """A route file that cannot be read, is not valid, or names something the plan does not have."""


@dataclass(frozen=True)
class When:
    """The conditions of one rule; every one that is set must hold. `None`, `()` and False mean "not asked"."""

    rarities: frozenset[Rarity] | None = None
    corrupted: bool | None = None
    no_fractured: bool = False
    fractured_families: tuple[str, ...] = ()
    fractured_without: tuple[str, ...] = ()  # a mod is fractured and it is none of these families (a mod held as its family type counts as another)
    crafted: bool | None = None
    unopened: bool | None = None  # the bought listing whose mods are not drawn yet (ADR-0064): the one state the draw is taken in
    statuses: tuple[tuple[int, frozenset[Status]], ...] = ()  # (index of the requirement leaf, statuses allowed)
    open_slots: tuple[tuple[Side, int, int], ...] = ()  # (side, capacity of the side, free slots wanted at least)
    imprints: int | None = None  # the number of imprints held, exactly (#223)
    veil: str | None = None  # "prefix", "suffix", "any" or "none": the side of the veiled placeholder the item holds (ticket #146)
    offer: str | None = None  # "none" or "drawn": whether an unveil offer is drawn
    offer_shows: tuple[int, int | None] | None = None  # (index of the requirement leaf, position 1 to 3 or None for any): a mod shown meets the leaf
    making: frozenset[int] | None = None  # the item the rule is for: None any, empty the target's own, else a second item holding exactly these leaves (#225)

    def is_for(self, want: object) -> bool:
        """Whether the rule is for the item made towards `want`: `MAIN` (the target's own) or a donor's compressed want (a plan with donors, #225)."""
        if self.making is None:
            return True
        if want is MAIN:
            return not self.making
        passing = frozenset(index for index, status in enumerate(want.status) if status is Status.PASSING)
        return bool(self.making) and passing == self.making

    def matches(self, state: CompressedState, data: GameData) -> bool:
        if self.rarities is not None and state.flags.rarity not in self.rarities:
            return False
        if self.corrupted is not None and state.flags.corrupted != self.corrupted:
            return False
        if self.crafted is not None and state.crafted != self.crafted:
            return False
        if self.unopened is not None and state.flags.unopened != self.unopened:
            return False
        if self.no_fractured and state.fractured:
            return False
        if self.imprints is not None and len(state.imprints) != self.imprints:
            return False
        if self.fractured_families:  # a mod fractured mid-route may be held as its family type ("~3"): it names no family here
            held = {family for entry in state.fractured if entry.mod_id in data.mods for family in data.mods[entry.mod_id].families}
            if not held.issuperset(self.fractured_families):
                return False
        if self.fractured_without:
            if not state.fractured:
                return False
            held = {family for entry in state.fractured if entry.mod_id in data.mods for family in data.mods[entry.mod_id].families}
            if held.intersection(self.fractured_without):
                return False
        for side, room, wanted in self.open_slots:
            if any(entry.mod_id not in data.mods for entry in state.fractured):
                return False  # the side of a mod held as its family type is not known, so the free slots cannot be counted
            held = sum(data.mods[entry.mod_id].generation_type == side.value for entry in state.fractured)
            held += sum(slot.side is side for slot in state.slots)
            if room - held < wanted:
                return False
        if self.veil is not None:
            veils = {slot.kind for slot in state.slots if slot.kind in VEIL_KINDS and not slot.crafted}
            if (self.veil == "none") != (not veils) or (self.veil in VEIL_SIDES and VEIL_SIDES[self.veil] not in veils):
                return False
        if self.offer is not None and (self.offer == "drawn") != bool(state.offer):
            return False
        if self.offer_shows is not None:
            leaf, position = self.offer_shows
            shown = state.offer if position is None else state.offer[position - 1 : position]
            if not any(entry.contribution[leaf] is Status.PASSING for entry in shown):
                return False
        return all(state.status[index] in allowed for index, allowed in self.statuses)


@dataclass(frozen=True)
class Rule:
    """`do` is the label of a priced offer of the plan, or `RESTART`; `line` is where the rule starts in the file."""

    line: int
    when: When
    do: str


@dataclass(frozen=True)
class Route:
    """`skip_refused`: a rule whose action the game refuses at a state is passed over to the next rule that matches (the route's own key)."""

    name: str | None
    source: str
    rules: tuple[Rule, ...]
    skip_refused: bool = False


@dataclass(frozen=True)
class Gap:
    """A reachable non-goal state where the route does nothing, and why."""

    state: CompressedState
    reason: str


@dataclass(frozen=True)
class Divergence:
    """A state of the solver's main line where the route chooses another action than the solver."""

    state: CompressedState
    solver_action: str
    route_action: str


@dataclass(frozen=True)
class RouteResult:
    """The route as a fixed policy: its entries, the exact risk, the gaps, where it first parts from the solver, the time spent.

    `divergence` is the first state of the solver's main line where the route takes another action, `divergences` every such state in the same
    order (breadth first from the start), the first included (ticket #554).
    """

    policy: dict[CompressedState, Action[CompressedState]]
    risk: RiskReport
    gaps: tuple[Gap, ...]
    divergence: Divergence | None
    seconds: float
    chain: object | None = None  # the route on item states as arrays (`_route_chain.Chain`), set when it was read on a packed plan whose `policy` is a lumped view
    divergences: tuple[Divergence, ...] = ()
    product_policy: dict | None = None  # for a plan that makes donors (#225): the route over the product of the target and its donors, `policy` its own part


# --- reading -------------------------------------------------------------------------------------


def load_route(path: Path, plan: Plan, data: GameData) -> Route:
    """Read the UTF-8 route file at `path` for `plan`; every problem is a `RouteError`."""
    source = str(path)
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        raise RouteError(f"{source}: the route file does not exist") from None
    except UnicodeDecodeError:
        raise RouteError(f"{source}: the route file is not UTF-8 text") from None
    except OSError as problem:
        raise RouteError(f"{source}: the route file cannot be read ({problem.strerror or problem})") from None
    return parse_route(text, plan, data, source)


def parse_route(text: str, plan: Plan, data: GameData, source: str = "<route>") -> Route:
    """Parse the YAML `text` of a route against `plan` (its requirements, offers and start price) and `data`."""
    try:
        return _Reader(plan, data, source).read(load_with_lines(text, source))
    except TargetError as problem:  # the YAML itself is wrong
        raise RouteError(str(problem)) from None
    except RecursionError:
        raise RouteError(f"{source}:1: the file is nested too deeply to read") from None


def _requirements(plan: Plan) -> list[Requirement]:
    """The requirement leaves of the target in the order of `Plan.leaf_labels`."""
    found: list[Requirement] = []

    def walk(node: Requirement | KOfN) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        else:
            found.append(node)

    for node in plan.target.requirements:
        walk(node)
    return found


class _Reader:
    def __init__(self, plan: Plan, data: GameData, source: str) -> None:
        self.plan = plan
        self.data = data
        self.source = source
        self.leaves = _requirements(plan)

    def fail(self, line: int, path: str, problem: str) -> NoReturn:
        where = f"{path}: " if path else ""
        raise RouteError(f"{self.source}:{line}: {where}{problem}")

    # -- the file ---------------------------------------------------------------------------------

    def read(self, root: object) -> Route:
        if root is None:
            self.fail(1, "", "the file is empty; a route needs `rules:` with at least one rule")
        if not isinstance(root, LineMap):
            self.fail(1, "", f"the file must be a mapping of keys such as `rules:`, not {describe(root)}")
        self.check_keys(root, "", TOP_KEYS)
        if "rules" not in root:
            self.fail(root.line, "rules", "this key is required but missing")
        name = self.text(root, "name", "name") if "name" in root else None
        skip_refused = self.flag(root, "skip_refused", "skip_refused") if "skip_refused" in root else False
        entries = root["rules"]
        line = root.key_lines["rules"]
        if not isinstance(entries, LineList):
            self.fail(line, "rules", f"must be a list of rules, got {describe(entries)}")
        if not entries:
            self.fail(line, "rules", "must hold at least one rule")
        rules = tuple(
            self.read_rule(entry, f"rules[{index}]", entries.item_lines[index]) for index, entry in enumerate(entries)
        )
        opening = next((priced.label for priced in self.plan.offers if priced.offer.action.opens_listing), None)
        if opening is not None:  # ADR-0064: the draw of a bought item's mods is the market's, not the guide's; every route takes it first
            rules = (Rule(root.line, When(unopened=True), opening), *rules)
        return Route(name, self.source, rules, skip_refused)

    def read_rule(self, entry: object, path: str, line: int) -> Rule:
        if not isinstance(entry, LineMap):
            self.fail(line, path, f"must be a mapping with `when` and `do`, got {describe(entry)}")
        self.check_keys(entry, path, RULE_KEYS)
        if "do" not in entry:
            self.fail(entry.line, f"{path}.do", "this key is required but missing")
        when = self.read_when(entry["when"], f"{path}.when", entry.key_lines["when"]) if "when" in entry else When()
        return Rule(entry.line, when, self.read_action(entry, f"{path}.do"))

    # -- `do` ---------------------------------------------------------------------------------------

    def read_action(self, rule: LineMap, path: str) -> str:
        label = self.text(rule, "do", path)
        line = rule.key_lines["do"]
        if label == RESTART:
            if self.plan.start_price.given:
                self.fail(
                    line,
                    path,
                    "`restart` buys the start item again, and the target says its start item is given (`start: given`): "
                    "a given item is never bought again. Remove the rule, or write `start: bought` and give the item a price",
                )
            return label
        known = [priced.label for priced in self.plan.offers]
        if label in known:
            return label
        for limit in self.plan.limits:
            if limit.kind == UNPRICED and label in limit.labels:
                self.fail(
                    line,
                    path,
                    f"{describe(label)} has no price: "
                    + (f"missing {', '.join(limit.names)}" if limit.names else "no source lists a price for it")
                    + ". Price it or remove the rule",
                )
        near = close_matches(label, [*known, RESTART])
        hint = f"; did you mean {quoted(near[:1])}?" if near else ""
        self.fail(line, path, f"unknown action {describe(label)}; the known actions are {quoted([*known, RESTART])}{hint}")

    # -- `when` -------------------------------------------------------------------------------------

    def read_when(self, when: object, path: str, line: int) -> When:
        if not isinstance(when, LineMap):
            self.fail(line, path, f"must be a mapping of conditions such as `rarity: rare`, got {describe(when)}")
        for key in when:
            if key in REFUSED_KEYS:
                self.fail(
                    when.key_lines[key],
                    f"{path}.{key}",
                    "the compressed state does not hold this yet, so the condition cannot be checked "
                    "(a later ticket adds it to the state); leave it out of the rule",
                )
        self.check_keys(when, path, WHEN_KEYS)
        fields: dict[str, object] = {}
        if "rarity" in when:
            fields["rarities"] = self.read_rarities(when, f"{path}.rarity")
        for key, field in (("corrupted", "corrupted"), ("crafted_mods", "crafted")):
            if key in when:
                fields[field] = self.flag(when, key, f"{path}.{key}")
        open_slots = self.read_open_slots(when, path)
        if open_slots:
            fields["open_slots"] = open_slots
        if "imprints" in when:
            fields["imprints"] = self.read_imprints(when, f"{path}.imprints")
        if "fractured" in when:
            fields.update(self.read_fractured(when["fractured"], f"{path}.fractured", when.key_lines["fractured"]))
        if "veil" in when or "offer" in when:
            fields.update(self.read_veil(when, path))
        if "requirements" in when:
            fields["statuses"] = self.read_statuses(
                when["requirements"], f"{path}.requirements", when.key_lines["requirements"]
            )
        if "making" in when:
            fields["making"] = self.read_making(when, f"{path}.making")
        return When(**fields)

    def read_making(self, when: LineMap, path: str) -> frozenset[int]:
        """`making: target`, or a list of `stat` / `family` entries: the target's mods the second item holds, and nothing else (#225)."""
        value, line = when["making"], when.key_lines["making"]
        if self.plan.donors is None:
            self.fail(line, path, "the plan makes no second item (no offered action takes one), so a rule cannot be for one")
        if value == TARGET:
            return frozenset()
        if not isinstance(value, LineList) or not value:
            self.fail(line, path, f"must be `{TARGET}` or a list of `stat` or `family` entries naming the target's mods the second item holds")
        found = set()
        for index, entry in enumerate(value):
            where, at = f"{path}[{index}]", value.item_lines[index]
            if not isinstance(entry, LineMap):
                self.fail(at, where, f"must be a mapping with `stat` or `family`, got {describe(entry)}")
            self.check_keys(entry, where, ("stat", "family"))
            if ("stat" in entry) == ("family" in entry):
                self.fail(entry.line, where, "give exactly one of `stat` and `family`")
            found.add(self.leaf_of(entry, where))
        return frozenset(found)

    def read_open_slots(self, when: LineMap, path: str) -> tuple[tuple[Side, int, int], ...]:
        found = []
        for key, side in (("open_prefixes", Side.PREFIX), ("open_suffixes", Side.SUFFIX)):
            if key not in when:
                continue
            value, line = when[key], when.key_lines[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                self.fail(line, f"{path}.{key}", f"must be a whole number of free slots, 0 or more, got {describe(value)}")
            if not self.plan.abstraction.keeps_junk:
                self.fail(
                    line,
                    f"{path}.{key}",
                    "the states of this plan keep no mods besides the fractured ones (no bench action is offered), "
                    "so the free slots cannot be counted; leave the condition out",
                )
            room = capacity(self.data, self.plan.target.base_id, Rarity.RARE).of(side)
            found.append((side, room, value))
        return tuple(found)

    def read_imprints(self, when: LineMap, path: str) -> int:
        value, line = when["imprints"], when.key_lines["imprints"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            self.fail(line, path, f"must be a whole number of imprints held, 0 or more, got {describe(value)}")
        if not self.plan.abstraction.tracks_imprints:
            self.fail(
                line,
                path,
                "the states of this plan hold no imprint (no imprint action is offered: name `imprint` and `restore` in the target's "
                "`actions:`), so the imprints cannot be counted; leave the condition out",
            )
        return value

    def read_veil(self, when: LineMap, path: str) -> dict[str, object]:
        """`veil` and `offer` (ticket #146): what the state holds of the veiled placeholder and of the unveil offer (ADR-0026)."""
        first = "veil" if "veil" in when else "offer"
        if not self.plan.abstraction.tracks_offer:
            self.fail(
                when.key_lines[first],
                f"{path}.{first}",
                "the states of this plan hold no veil and no offer (no unveil is offered), so the condition cannot be checked; leave it out",
            )
        fields: dict[str, object] = {}
        if "veil" in when:
            value = when["veil"]
            if value not in VEIL_VALUES:
                self.fail(when.key_lines["veil"], f"{path}.veil", f"must be one of {quoted(VEIL_VALUES)}, got {describe(value)}")
            fields["veil"] = value
        if "offer" in when:
            value, line = when["offer"], when.key_lines["offer"]
            where = f"{path}.offer"
            if isinstance(value, LineMap):
                self.check_keys(value, where, ("shows", "at"))
                if "shows" not in value:
                    self.fail(value.line, f"{where}.shows", "this key is required but missing")
                shows = value["shows"]
                if not isinstance(shows, LineMap):
                    self.fail(value.key_lines["shows"], f"{where}.shows", f"must be a requirement such as {{stat: \"...\"}}, got {describe(shows)}")
                self.check_keys(shows, f"{where}.shows", ("stat", "family"))
                if ("stat" in shows) == ("family" in shows):
                    self.fail(shows.line, f"{where}.shows", "give exactly one of `stat` and `family`")
                leaf = self.leaf_of(shows, f"{where}.shows")
                position = None
                if "at" in value:
                    position = value["at"]
                    if type(position) is not int or position not in (1, 2, 3):
                        self.fail(value.key_lines["at"], f"{where}.at", f"must be 1, 2 or 3 (the mod `Pick 1`, `Pick 2` or `Pick 3` takes), got {describe(position)}")
                fields["offer_shows"] = (leaf, position)
                fields["offer"] = "drawn"
            elif value in OFFER_VALUES:
                fields["offer"] = value
            else:
                self.fail(line, where, f"must be one of {quoted(OFFER_VALUES)} or {{shows: <requirement>, at: 1}}, got {describe(value)}")
        return fields

    def read_rarities(self, when: LineMap, path: str) -> frozenset[Rarity]:
        value, line = when["rarity"], when.key_lines["rarity"]
        names = list(value) if isinstance(value, LineList) else [value]
        if not names:
            self.fail(line, path, f"must name at least one of {quoted(RARITIES)}")
        found = []
        for index, name in enumerate(names):
            where = f"{path}[{index}]" if isinstance(value, LineList) else path
            at = value.item_lines[index] if isinstance(value, LineList) else line
            if not isinstance(name, str) or name.lower() not in RARITIES:
                self.fail(at, where, f"must be one of {quoted(RARITIES)}, got {describe(name)}")
            found.append(Rarity(name.lower()))
        return frozenset(found)

    def read_fractured(self, value: object, path: str, line: int) -> dict[str, object]:
        if isinstance(value, str) and value == "none":
            return {"no_fractured": True}
        if isinstance(value, LineMap):
            self.check_keys(value, path, ("without",))
            if "without" not in value:
                self.fail(value.line, f"{path}.without", "this key is required but missing")
            inner = self.read_fractured(value["without"], f"{path}.without", value.key_lines["without"])
            if "fractured_families" not in inner:
                self.fail(value.key_lines["without"], f"{path}.without", "must be a list such as [{family: Pierce}]")
            return {"fractured_without": inner["fractured_families"]}
        if not isinstance(value, LineList):
            self.fail(line, path, f"must be `none` or a list such as [{{family: LightningResistance}}], got {describe(value)}")
        if not value:
            self.fail(line, path, "must be `none` or a list of at least one family")
        resolver = Resolver(self.data)
        families = []
        for index, entry in enumerate(value):
            where, at = f"{path}[{index}]", value.item_lines[index]
            if not isinstance(entry, LineMap):
                self.fail(at, where, f"must be a mapping such as `family: LightningResistance`, got {describe(entry)}")
            self.check_keys(entry, where, ("family",))
            if "family" not in entry:
                self.fail(entry.line, f"{where}.family", "this key is required but missing")
            family = self.text(entry, "family", f"{where}.family")
            try:
                resolver.mods_for_family(family)
            except Unresolved as problem:
                self.fail(entry.key_lines["family"], f"{where}.family", str(problem))
            families.append(family)
        return {"fractured_families": tuple(families)}

    def read_statuses(self, value: object, path: str, line: int) -> tuple[tuple[int, frozenset[Status]], ...]:
        if not isinstance(value, LineList):
            self.fail(line, path, f"must be a list of `stat` or `family` with a `status`, got {describe(value)}")
        found = []
        for index, entry in enumerate(value):
            where, at = f"{path}[{index}]", value.item_lines[index]
            if not isinstance(entry, LineMap):
                self.fail(at, where, f"must be a mapping with `stat` or `family` and `status`, got {describe(entry)}")
            self.check_keys(entry, where, REQUIREMENT_KEYS)
            if ("stat" in entry) == ("family" in entry):
                self.fail(entry.line, where, "give exactly one of `stat` and `family`")
            if "status" not in entry:
                self.fail(entry.line, f"{where}.status", "this key is required but missing")
            leaf = self.leaf_of(entry, where)
            found.append((leaf, self.read_status(entry, f"{where}.status")))
        return tuple(found)

    def leaf_of(self, entry: LineMap, path: str) -> int:
        """The index of the target's requirement leaf that `entry` names, by the selector as the target stores it."""
        kind = "stat" if "stat" in entry else "family"
        wanted = self.text(entry, kind, f"{path}.{kind}")
        matching = [index for index, leaf in enumerate(self.leaves) if getattr(leaf, kind) == wanted]
        if not matching:
            selectors = [
                f'stat "{leaf.stat}"' if leaf.stat is not None else f"family {leaf.family}" for leaf in self.leaves
            ]
            self.fail(
                entry.key_lines[kind],
                f"{path}.{kind}",
                f"no requirement of the target has {kind} {describe(wanted)}; the target's selectors are "
                + "; ".join(selectors),
            )
        if len(matching) > 1:
            self.fail(
                entry.key_lines[kind],
                f"{path}.{kind}",
                f"ambiguous: {len(matching)} requirements of the target have {kind} {describe(wanted)}"
                f" (leaves {', '.join(str(index) for index in matching)}), so a status cannot name one of them",
            )
        return matching[0]

    def read_status(self, entry: LineMap, path: str) -> frozenset[Status]:
        value, line = entry["status"], entry.key_lines["status"]
        names = list(value) if isinstance(value, LineList) else [value]
        if not names:
            self.fail(line, path, f"must name at least one of {quoted(STATUSES)}")
        found = []
        for name in names:
            if not isinstance(name, str) or name.lower() not in STATUSES:
                self.fail(line, path, f"must be one of {quoted(STATUSES)} (or a list of them), got {describe(name)}")
            found.append(Status[name.upper()])
        return frozenset(found)

    # -- small checks ---------------------------------------------------------------------------------

    def text(self, mapping: LineMap, key: str, path: str) -> str:
        value = mapping[key]
        if not isinstance(value, str) or not value.strip():
            self.fail(mapping.key_lines[key], path, f"must be non-empty text, got {describe(value)}")
        return value.strip()

    def flag(self, mapping: LineMap, key: str, path: str) -> bool:
        value = mapping[key]
        if not isinstance(value, bool):
            self.fail(mapping.key_lines[key], path, f"must be true or false, got {describe(value)}")
        return value

    def check_keys(self, mapping: LineMap, path: str, allowed: Iterable[str]) -> None:
        allowed = tuple(allowed)
        for key in mapping:
            if key in allowed:
                continue
            near = close_matches(key, allowed)
            hint = f"did you mean `{near[0]}`?" if near else f"the keys allowed here are {quoted(allowed)}"
            where = f"{path}.{key}" if path else key
            self.fail(mapping.key_lines[key], where, f"unknown key `{key}`; {hint}")


# --- evaluating ----------------------------------------------------------------------------------


def _decide(plan: Plan, route: Route, data: GameData, state: CompressedState) -> Action[CompressedState] | str:
    """The action the route takes in `state`, or the reason it takes none."""
    refusal = "no rule matches this state"
    for rule in route.rules:
        if not rule.when.matches(state, data):
            continue
        if rule.do == RESTART:
            return Action(RESTART, plan.start_price.chaos, (Outcome(plan.start, 1),))
        priced = next(offer for offer in plan.offers if offer.label == rule.do)
        try:
            return offer_action(plan.abstraction, priced, state)
        except (NotApplicableError, OutOfScopeError) as problem:  # either: the route's rule cannot be used here, and the line says why
            refusal = f"{rule.do} cannot be used here (rule at line {rule.line}): {problem}"
            if not route.skip_refused:
                return refusal
    return refusal


def evaluate_route(plan: Plan, route: Route, data: GameData) -> RouteResult:
    """The route as a fixed policy from `plan.start`, with its exact risk, gaps and divergences from the solver.

    Breadth-first from the start: at every reachable non-goal state the first matching rule gives the
    action, built as the solver builds its own (same kernel, same integer weights). A state with no
    action (no rule matches, or the game refuses the action) is a gap and has no policy entry.

    Raises `PlanError` for a plan made by the envelope search: judging a route needs the planner's action at every state the route reaches,
    and that search never decides the states it proves irrelevant, so the route would read as gaps there (#535). Such a plan is made with
    `make_plan(..., judges_route=True)`, which keeps `solver="auto"` on the walk (a route judged without the full walk is #732).
    """
    if plan.packed is not None and "envelope" in plan.packed.info:
        raise PlanError(
            "a given route is judged against the planner's choice at every state the route reaches, and the exact search used for this plan "
            "looks only at the states that can matter: plan it again with the search that walks every possible item (`--solver packed`)"
        )
    if plan.donors is not None:  # the route makes second items too: it is read on the product of the target and its donors (#225)
        return _evaluate_route_with_donors(plan, route, data)
    if isinstance(plan.policy, PackedPolicy):  # the walked graph is held: read the route there (R04's object chain does not fit, ticket #70)
        from ._route_packed import evaluate_route_packed

        return evaluate_route_packed(plan, route, data)
    began = time.perf_counter()
    choices: dict[CompressedState, Action[CompressedState] | str] = {}
    policy: dict[CompressedState, Action[CompressedState]] = {}
    gaps: list[Gap] = []
    order = [plan.start]
    seen = {plan.start}
    for state in order:  # the list grows while it is walked
        if plan.is_goal(state):
            continue
        choice = choices[state] = _decide(plan, route, data, state)
        if isinstance(choice, str):
            gaps.append(Gap(state, choice))
            continue
        policy[state] = choice
        for successor, weight in choice.outcomes:
            if weight > 0 and successor not in seen:
                seen.add(successor)
                order.append(successor)
    # The risk is read on one state per block of states that behave alike (`risk.lump`, #717): the same cost distribution, and the budget DP runs over
    # the blocks and not over every state (R13's route has 2,887 states; the DP over them took 4 to 18 minutes).
    lumped = lump(policy, plan.start, plan.is_goal)
    risk = evaluate_risk(lumped.policy, lumped.start, lumped.is_goal, plan.mean_remaining, free_cost=free_action_cost(plan.offers))  # the route costs at least the solver's mean

    divergences: list[Divergence] = []
    for state in policy_states(plan.start, plan.policy, plan.is_goal):
        if plan.is_goal(state) or state not in plan.policy:
            continue
        choice = choices[state] if state in choices else _decide(plan, route, data, state)
        if isinstance(choice, str):
            continue  # a gap, not a divergence
        if choice.label != plan.policy[state].label:
            divergences.append(Divergence(state, str(plan.policy[state].label), str(choice.label)))
    first = divergences[0] if divergences else None
    return RouteResult(policy, risk, tuple(gaps), first, time.perf_counter() - began, divergences=tuple(divergences))


def _decide_product(plan: Plan, route: Route, data: GameData, product: tuple) -> Action | str:
    """The action the route takes on the item of `product` (`("in", want, state)`), with its donors, or the reason it takes none (#225)."""
    _tag, want, state = product
    refusal = "no rule matches this state" if want is MAIN else "no rule matches this state of a second item"
    offered = None
    for rule in route.rules:
        if not rule.when.is_for(want) or not rule.when.matches(state, data):
            continue
        if offered is None:
            offered = {}
            for action in plan.donors.acquisition.actions(product):
                offered.setdefault(action.label, action)
        found = offered.get(rule.do)
        if found is not None:
            return found
        refusal = f"{rule.do} cannot be used here (rule at line {rule.line}): the game refuses it on this item"
        if not route.skip_refused:
            return refusal
    return refusal


def _evaluate_route_with_donors(plan: Plan, route: Route, data: GameData) -> RouteResult:
    """`evaluate_route` for a plan that makes donors (ticket #225): the route as a fixed policy of the product of the target and its donors.

    The walk starts at the target's own item and follows every outcome and every second item a recombination consumes; a second item is
    made by the rules that are for it (`making:`), each from a normal item of the base, as the planner makes it. A rule's action is the
    product's own (`DonorPlan.acquisition`), so a recombination costs its combine plus the run of its donor, as in the plan. The risk is
    measured on the whole product. `RouteResult.policy` is the target's own process (`main_view`), so the divergences are read where the
    target's item is; the second items' rules are judged only through the mean. A gap of a second item names its state.
    """
    from crafting_system.planner import main_view  # the same reading as the plan's

    began = time.perf_counter()
    donors = plan.donors
    choices: dict[tuple, Action | str] = {}
    policy: dict[tuple, Action] = {}
    gaps: list[Gap] = []
    order = [donors.start]
    seen = {donors.start}
    for product in order:
        if donors.acquisition.is_goal(product):
            continue
        choice = choices[product] = _decide_product(plan, route, data, product)
        if isinstance(choice, str):
            gaps.append(Gap(product[2], choice))
            continue
        policy[product] = choice
        for successor in (*(t for t, w in choice.outcomes if w > 0), *choice.extra_inputs):
            if successor not in seen:
                seen.add(successor)
                order.append(successor)
    risk = evaluate_risk(policy, donors.start, donors.acquisition.is_goal, plan.mean_remaining, free_cost=free_action_cost(plan.offers))
    values = {product: 0.0 for product in policy}
    own = main_view(Solution(values, policy, 0.0)).policy

    divergences: list[Divergence] = []
    for state in policy_states(plan.start, plan.policy, plan.is_goal):
        if plan.is_goal(state) or state not in plan.policy:
            continue
        product = ("in", MAIN, state)
        choice = choices[product] if product in choices else _decide_product(plan, route, data, product)
        if isinstance(choice, str):
            continue
        if choice.label != plan.policy[state].label:
            divergences.append(Divergence(state, str(plan.policy[state].label), str(choice.label)))
    first = divergences[0] if divergences else None
    return RouteResult(own, risk, tuple(gaps), first, time.perf_counter() - began, divergences=tuple(divergences), product_policy=policy)
