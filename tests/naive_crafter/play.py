"""A guide's route played on concrete items, and its cost counted by Monte Carlo (ticket #555).

The route file is read as its header says: rules in order, and at every item the FIRST rule whose conditions hold is followed; an item
that meets the target is never acted on; an item no rule covers, or where the game refuses the rule's action, is a gap (unless the route says
`skip_refused: true`, then the next matching rule is tried). One play starts from the target's start item, spends the price of each use,
and ends when the item meets the target. A bought start item is not paid for at the start (the planner's mean leaves it out too) but a
`restart` pays its price and puts the start item back.

The conditions (`when`): `rarity`, `corrupted` (items here are never corrupted), `fractured` (`none`, a list of `{family: ...}`, or
`{without: [...]}`), `crafted_mods`, `open_prefixes` / `open_suffixes` (at least that many free slots) and `requirements`, each a selector
(`family:` or `stat:`) that names one line of the target and a `status`: `passing` (a mod of the item meets the line, judged by the goal
oracle), `below` (a mod of the line's family or stat is on the item and none meets the line), `absent` (no mod of it).
"""

from dataclasses import dataclass, field
from random import Random

import yaml
from oracle import goal_oracle as g

from .craft import Item, Refused, Unsupported
from .world import RESTART, World

ABSENT, BELOW, PASSING = 0, 1, 2
STATUS_CODES = {"absent": ABSENT, "below": BELOW, "passing": PASSING}
WHEN_KEYS = {"rarity", "corrupted", "fractured", "crafted_mods", "open_prefixes", "open_suffixes", "requirements"}
RARITIES = ("normal", "magic", "rare")
MAX_USES = 50_000_000  # uses in one play before it is called endless


class RouteError(ValueError):
    """A route file the player cannot read."""


class Gap(Exception):
    """An item that no rule covers, or where the game refuses the action of the rule: the route does not finish from here."""


class Judge:
    """What the target says of an item: the status of each line, and whether the item is the goal. The mods are judged by the goal oracle, once each."""

    def __init__(self, world: World):
        self.world = world
        self.oracle = world.oracle
        self.leaves = [leaf for node in world.target.requirements for leaf in g.leaves(node)]
        self.index = {leaf.path: i for i, leaf in enumerate(self.leaves)}
        self._codes: dict[tuple, tuple[int, ...]] = {}

    def mod_codes(self, held) -> tuple[int, ...]:
        """For one mod: per line, 2 when the mod meets the line, 1 when it only belongs to its family or stat, else 0."""
        key = (held.mod_id, held.values)
        found = self._codes.get(key)
        if found is None:
            omod = g.OMod(held.mod_id, held.values, held.fractured)
            codes = []
            for leaf in self.leaves:
                if self.oracle.counts(leaf, omod):
                    codes.append(PASSING)
                elif self.world.export.selects(held.mod_id, leaf.family, leaf.stat):
                    codes.append(BELOW)
                else:
                    codes.append(ABSENT)
            found = self._codes[key] = tuple(codes)
        return found

    def statuses(self, item: Item) -> list[int]:
        status = [ABSENT] * len(self.leaves)
        for held in item.mods:
            for i, code in enumerate(self.mod_codes(held)):
                if code > status[i]:
                    status[i] = code
        return status

    def goal(self, status: list[int]) -> bool:
        return all(self._met(node, status) for node in self.world.target.requirements)

    def _met(self, node, status: list[int]) -> bool:
        if isinstance(node, g.OReq):
            return status[self.index[node.path]] == PASSING
        return sum(self._met(member, status) for member in node.members) >= node.at_least

    def line_of(self, selector: dict, where: str) -> int:
        """The index of the one line of the target that `{family: ...}` or `{stat: ...}` names."""
        family, stat = selector.get("family"), selector.get("stat")
        if (family is None) == (stat is None):
            raise RouteError(f"{where}: a requirement names its line by `family` or by `stat`, one of them")
        found = [
            i
            for i, leaf in enumerate(self.leaves)
            if (family is not None and leaf.family == family) or (stat is not None and leaf.stat is not None and g.normal_text(leaf.stat) == g.normal_text(stat))
        ]
        if len(found) != 1:
            raise RouteError(f"{where}: {len(found)} lines of the target match {selector}")
        return found[0]


@dataclass(frozen=True)
class When:
    rarities: tuple[str, ...] | None = None
    no_fractured: bool = False
    fractured_families: tuple[str, ...] = ()
    fractured_without: tuple[str, ...] | None = None
    crafted: bool | None = None
    open_slots: tuple[tuple[str, int], ...] = ()
    statuses: tuple[tuple[int, frozenset[int]], ...] = ()

    def matches(self, item: Item, status: list[int], world: World) -> bool:
        if self.rarities is not None and item.rarity not in self.rarities:
            return False
        if self.crafted is not None and any(held.crafted for held in item.mods) != self.crafted:
            return False
        book = world.crafter.book
        fractured = [held for held in item.mods if held.fractured]
        if self.no_fractured and fractured:
            return False
        held_groups = {group for held in fractured for group in book.groups(held.mod_id)}
        if not set(self.fractured_families) <= held_groups:
            return False
        if self.fractured_without is not None and (not fractured or held_groups & set(self.fractured_without)):
            return False
        for side, wanted in self.open_slots:
            if world.crafter.free_slots(item, side) < wanted:
                return False
        return all(status[index] in allowed for index, allowed in self.statuses)


@dataclass(frozen=True)
class Rule:
    line: int
    when: When
    label: str


@dataclass(frozen=True)
class Route:
    name: str | None
    skip_refused: bool
    rules: tuple[Rule, ...]


def _names(value, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(entry, dict) and set(entry) == {"family"} for entry in value):
        raise RouteError(f"{where}: a list of `- family: ID` entries was expected")
    return tuple(entry["family"] for entry in value)


def read_when(block: dict, judge: Judge, where: str) -> When:
    unknown = set(block) - WHEN_KEYS
    if unknown:
        raise RouteError(f"{where}: unknown condition {sorted(unknown)}")
    rarities = block.get("rarity")
    if rarities is not None:
        rarities = tuple(rarities) if isinstance(rarities, list) else (rarities,)
        if not set(rarities) <= set(RARITIES):
            raise RouteError(f"{where}.rarity: {rarities} is not normal, magic or rare")
    if block.get("corrupted") not in (None, False):
        raise RouteError(f"{where}.corrupted: the items of this player are never corrupted")
    fractured = block.get("fractured")
    no_fractured, families, without = False, (), None
    if fractured == "none":
        no_fractured = True
    elif isinstance(fractured, list):
        families = _names(fractured, f"{where}.fractured")
    elif isinstance(fractured, dict) and set(fractured) == {"without"}:
        without = _names(fractured["without"], f"{where}.fractured.without")
    elif fractured is not None:
        raise RouteError(f"{where}.fractured: `none`, a list of families or `without:` was expected")
    slots = tuple(
        (side, int(block[key])) for side, key in (("prefix", "open_prefixes"), ("suffix", "open_suffixes")) if key in block
    )
    statuses = []
    for i, entry in enumerate(block.get("requirements") or ()):
        here = f"{where}.requirements[{i}]"
        wanted = entry.get("status")
        wanted = wanted if isinstance(wanted, list) else [wanted]
        if not wanted or any(name not in STATUS_CODES for name in wanted):
            raise RouteError(f"{here}.status: absent, below or passing (or a list of them) was expected")
        statuses.append((judge.line_of({k: v for k, v in entry.items() if k != "status"}, here), frozenset(STATUS_CODES[name] for name in wanted)))
    return When(rarities, no_fractured, families, without, block.get("crafted_mods"), slots, tuple(statuses))


def read_route(text: str, world: World, judge: Judge) -> Route:
    """The rules of a route file; every action is resolved now, so one this player lacks is an error at once (`Unsupported`)."""
    document = yaml.safe_load(text)
    if not isinstance(document, dict) or not document.get("rules"):
        raise RouteError("the route needs a non-empty `rules` list")
    rules = []
    for i, entry in enumerate(document["rules"]):
        where = f"rules[{i}]"
        label = entry.get("do")
        if not isinstance(label, str):
            raise RouteError(f"{where}.do: the name of an action was expected")
        world.action(label)
        rules.append(Rule(i, read_when(entry.get("when") or {}, judge, f"{where}.when"), label))
    return Route(document.get("name"), bool(document.get("skip_refused", False)), tuple(rules))


def lacking(text: str, world: World) -> dict[str, str]:
    """For a route file: each action label this player cannot play, with the message that names the mechanic it lacks."""
    found: dict[str, str] = {}
    for rule in yaml.safe_load(text)["rules"]:
        label = rule["do"]
        if label in found:
            continue
        try:
            world.action(label)
        except Unsupported as missing:
            found[label] = str(missing)
    return found


def labels_of(route: Route) -> list[str]:
    seen: list[str] = []
    for rule in route.rules:
        if rule.label not in seen:
            seen.append(rule.label)
    return seen


@dataclass
class Play:
    """One play of a route: what it spent, in all and per action label, and how many uses of each."""

    cost: float = 0.0
    spend: dict[str, float] = field(default_factory=dict)
    uses: dict[str, int] = field(default_factory=dict)
    item: Item | None = None  # the item the play ended with (or stopped at, for a gap)


class Player:
    def __init__(self, world: World, route: Route, judge: Judge | None = None):
        self.world = world
        self.route = route
        self.judge = judge or Judge(world)

    def _use(self, label: str, item: Item, rng: Random) -> Item:
        action = self.world.action(label)
        crafter = self.world.crafter
        match action.kind:
            case "restart":
                return self.world.start_item
            case "transmutation":
                return crafter.transmute(item, rng)
            case "alteration":
                return crafter.alter(item, rng)
            case "augmentation":
                return crafter.augment(item, rng)
            case "regal":
                return crafter.regal(item, rng)
            case "chaos":
                return crafter.chaos(item, rng)
            case "essence":
                return crafter.essence(item, rng, action.record)
            case "bench":
                return crafter.bench(item, rng, action.mod_id)
            case "remove_crafted":
                return crafter.remove_crafted(item)
            case "fossil":
                return crafter.fossil(item, rng, action.fossils)
            case "harvest":
                return crafter.harvest(item, rng, action.tag)
            case "exalted":
                return crafter.exalt(item, rng)
            case "annulment":
                return crafter.annul(item, rng)
            case "fracturing":
                return crafter.fracture(item, rng)
        raise AssertionError(action.kind)

    def try_play(self, rng: Random, max_uses: int = MAX_USES) -> tuple[Play, str | None]:
        """One play that may end at a gap: the play so far, and the gap's message (None when the item met the target)."""
        play = Play()
        try:
            self.play(rng, max_uses, play)
        except Gap as gap:
            return play, str(gap)
        return play, None

    def play(self, rng: Random, max_uses: int = MAX_USES, into: Play | None = None) -> Play:
        world, judge, route = self.world, self.judge, self.route
        play = into if into is not None else Play()
        item = world.start_item
        for _ in range(max_uses):
            status = judge.statuses(item)
            play.item = item
            if judge.goal(status):
                return play
            for rule in route.rules:
                if not rule.when.matches(item, status, world):
                    continue
                try:
                    item = self._use(rule.label, item, rng)
                except Refused as refusal:
                    if route.skip_refused:
                        continue
                    raise Gap(f"rule {rule.line} ({rule.label!r}) is refused at {describe(item)}: {refusal}") from None
                cost = world.action(rule.label).cost
                play.cost += cost
                play.spend[rule.label] = play.spend.get(rule.label, 0.0) + cost
                play.uses[rule.label] = play.uses.get(rule.label, 0) + 1
                break
            else:
                raise Gap(f"no rule covers {describe(item)}")
        raise Gap(f"a play went on for {max_uses} uses without finishing")


def describe(item: Item) -> str:
    return f"a {item.rarity} item with " + (", ".join(f"{held.mod_id}{list(held.values)}" + ("*" if held.fractured else "") for held in item.mods) or "no mods")
