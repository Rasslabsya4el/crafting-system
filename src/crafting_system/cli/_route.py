"""Given routes: a crafting route written down as rules and evaluated exactly as a fixed policy.

A guide states no cost, so the cost of its route is found by writing the route as a YAML file and
evaluating it with `risk.evaluate` at the same prices as the solver's policy (ADR-0013). The file:

    name: R12, PoE Vault guide        # optional
    rules:                            # required, non-empty; in every state the FIRST rule that matches is followed
      - when:                         # optional; no `when` matches every state
          rarity: rare                # normal, magic or rare, or a list of them
          corrupted: false
          fractured: none             # or [{family: LightningResistance}]: every listed family is fractured on the item
          crafted_mods: false         # the item holds a crafted mod or metamod
          open_suffixes: 1            # at least this many free suffixes (open_prefixes likewise); needs a bench action offered
          requirements:               # the status of a requirement of the target, named by its selector
            - stat: "+1 to Level of all Lightning Skill Gems"    # or `family: ID`, as the target writes it
              status: absent          # absent, below or passing, or a list of them
        do: Harvest Reforge Lightning # an action as the solver prints it, or `restart`

`restart` buys the start item again: an action that costs the start price and ends in the start state.
Conditions speak only of what the compressed state holds; one it cannot answer yet (mods per side, metamods)
is refused, not guessed. `open_prefixes` and `open_suffixes` count the free slots of a side, which the state holds only
when a bench action is offered (the other mods are then kept as slots); without one they are refused. A goal state is never acted on. A reachable state that no rule
covers (or where the game refuses the rule's action) is a GAP: it has no policy entry, so the route
never finishes from there, which `risk.evaluate` reports as a success chance below 1 and an infinite
mean. Errors are worded `<file>:<line>: <key path>: <problem>`, as the target loader's are.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from crafting_system.abstraction import CompressedState, Status
from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.items import Rarity, Side, capacity
from crafting_system.risk import RiskReport
from crafting_system.solver import Action, Outcome
from crafting_system.targets import KOfN, Requirement, TargetError
from crafting_system.targets.lines import LineList, LineMap, load_with_lines
from crafting_system.targets.parse import describe
from crafting_system.targets.resolve import Resolver, Unresolved, close_matches, quoted

from ._plan import Plan, evaluate_risk, offer_action
from ._reach import policy_states

RESTART = "restart"
TOP_KEYS = ("name", "rules")
RULE_KEYS = ("when", "do")
WHEN_KEYS = ("rarity", "corrupted", "fractured", "crafted_mods", "open_prefixes", "open_suffixes", "requirements")
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
    crafted: bool | None = None
    statuses: tuple[tuple[int, frozenset[Status]], ...] = ()  # (index of the requirement leaf, statuses allowed)
    open_slots: tuple[tuple[Side, int, int], ...] = ()  # (side, capacity of the side, free slots wanted at least)

    def matches(self, state: CompressedState, data: GameData) -> bool:
        if self.rarities is not None and state.flags.rarity not in self.rarities:
            return False
        if self.corrupted is not None and state.flags.corrupted != self.corrupted:
            return False
        if self.crafted is not None and state.crafted != self.crafted:
            return False
        if self.no_fractured and state.fractured:
            return False
        if self.fractured_families:  # a mod fractured mid-route may be held as its family type ("~3"): it names no family here
            held = {family for entry in state.fractured if entry.mod_id in data.mods for family in data.mods[entry.mod_id].families}
            if not held.issuperset(self.fractured_families):
                return False
        for side, room, wanted in self.open_slots:
            held = sum(entry.mod_id in data.mods and data.mods[entry.mod_id].generation_type == side.value for entry in state.fractured)
            held += sum(slot.side is side for slot in state.slots)
            if room - held < wanted:
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
    name: str | None
    source: str
    rules: tuple[Rule, ...]


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
    """The route as a fixed policy: its entries, the exact risk, the gaps, where it first parts from the solver, the time spent."""

    policy: dict[CompressedState, Action[CompressedState]]
    risk: RiskReport
    gaps: tuple[Gap, ...]
    divergence: Divergence | None
    seconds: float


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
        entries = root["rules"]
        line = root.key_lines["rules"]
        if not isinstance(entries, LineList):
            self.fail(line, "rules", f"must be a list of rules, got {describe(entries)}")
        if not entries:
            self.fail(line, "rules", "must hold at least one rule")
        rules = tuple(
            self.read_rule(entry, f"rules[{index}]", entries.item_lines[index]) for index, entry in enumerate(entries)
        )
        return Route(name, self.source, rules)

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
            if not self.plan.start_price.chaos > 0:
                self.fail(
                    line,
                    path,
                    "`restart` buys the start item again for the start price, which is 0 here; the solver needs "
                    "every action to cost more than 0. Give the start item a price",
                )
            return label
        known = [priced.label for priced in self.plan.offers]
        if label in known:
            return label
        for dropped in self.plan.dropped:
            if dropped.label == label:
                self.fail(
                    line,
                    path,
                    f"{describe(label)} has no price: missing {', '.join(dropped.missing)}. "
                    "Price it or remove the rule",
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
        if "fractured" in when:
            fields.update(self.read_fractured(when["fractured"], f"{path}.fractured", when.key_lines["fractured"]))
        if "requirements" in when:
            fields["statuses"] = self.read_statuses(
                when["requirements"], f"{path}.requirements", when.key_lines["requirements"]
            )
        return When(**fields)

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
    for rule in route.rules:
        if not rule.when.matches(state, data):
            continue
        if rule.do == RESTART:
            return Action(RESTART, plan.start_price.chaos, (Outcome(plan.start, 1),))
        priced = next(offer for offer in plan.offers if offer.label == rule.do)
        try:
            return offer_action(plan.abstraction, priced, state)
        except ActionError as problem:  # the game refuses it here, or no admitted rule covers it
            return f"{rule.do} cannot be used here (rule at line {rule.line}): {problem}"
    return "no rule matches this state"


def evaluate_route(plan: Plan, route: Route, data: GameData) -> RouteResult:
    """The route as a fixed policy from `plan.start`, with its exact risk, gaps and first divergence from the solver.

    Breadth-first from the start: at every reachable non-goal state the first matching rule gives the
    action, built as the solver builds its own (same kernel, same integer weights). A state with no
    action (no rule matches, or the game refuses the action) is a gap and has no policy entry.
    """
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
    risk = evaluate_risk(policy, plan.start, plan.is_goal, plan.mean_remaining)  # the route costs at least the solver's mean

    divergence = None
    for state in policy_states(plan.start, plan.policy, plan.is_goal):
        if plan.is_goal(state) or state not in plan.policy:
            continue
        choice = choices[state] if state in choices else _decide(plan, route, data, state)
        if isinstance(choice, str):
            continue  # a gap, not a divergence
        if choice.label != plan.policy[state].label:
            divergence = Divergence(state, str(plan.policy[state].label), str(choice.label))
            break
    return RouteResult(policy, risk, tuple(gaps), divergence, time.perf_counter() - began)
