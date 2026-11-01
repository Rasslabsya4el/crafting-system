"""The one contract every crafting action meets, so a new method is one file and needs no edit elsewhere (ticket #108).

An action is a frozen dataclass that subclasses `Action` and answers five questions (and a sixth, `claims`, that
the base class answers for it unless its file holds several actions):

* `label(data)`: its stable name, the one a route's `do:` and the CLI print ("Chaos Orb", "Harvest
  Reforge Lightning", an essence's own name). Two actions of a catalog can share a label only when
  their `variant` differs (two bench crafts that read alike, told apart by their mod id).
* `outcomes(data, item)`: the exact result on a concrete item (see `ActionOutcomes`), or an
  `ActionError` when the game refuses (`NotApplicableError`) or no admitted rule covers the item
  (`OutOfScopeError`).
* `resources(data)`: what one use consumes, by price-file name; read from claims of the registry.
* `reads(data)`: what of the item besides its fractured mods the result depends on (`Reads`).
* `adds(data, item)`: what the action puts on the item (`Adds`), so a planner can ask whether it can
  matter for a target without running it.
* `claims(data)`: the ids of the registry claims its result or price depends on, so an answer can name the
  ones marked `approximate` (ADR-0028). The default is every `Rule` held as a module-level constant of the
  module the class is defined in (the `X = get_rule("a.b")` every action file starts with), which is exact
  for a file of one action; an action whose file holds several that read different claims overrides it.

An optional seventh, `twin_key(data, item)`, lets a set of fossils name its twins without a pool (#118).

`abstraction` builds its states from `reads` and its kernels from `outcomes` alone; `cli` builds its
offers from the catalog (`catalog.py`), `resources` and `adds`; `simulator` calls `outcomes(...).sample`.
None of them imports a concrete action. The defaults of the base class are the safe ones: an action
that declares nothing reads every mod of the item and adds mods it does not name, which is exact but
makes the state space large and no filter can drop it.
"""

import random
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from crafting_system.data import GameData, Mod
from crafting_system.items import Item
from crafting_system.rules import Rule

from .draw import Outcome

if TYPE_CHECKING:
    from .outcomes import Outcomes


@dataclass(frozen=True)
class Reads:
    """What of the item an action reads besides its fractured mods (those every action sees).

    * `junk`: the result depends on, or keeps, the ordinary mods that are not fractured and not crafted
      (how many there are per side, and which families, if `families` says so). False means the action
      erases them all and redraws: the result holds none of them and does not look at them, so a state
      need not store them. An action that does not read the junk MUST erase it.
    * `families`: the families of the junk the result may depend on, as family names, when `junk` is
      true; None means any family (every family of the junk is told apart: exact, but the number of
      states grows). A bench craft names the families of its mod, because it is refused when one is
      on the item; Remove Crafted Mods reads the count only, so the empty set.
    * `pool_weight`: with `junk` true, the result depends on the families of the junk only through
      the weight they take out of the pool, because the action adds mods (an Augmentation, a Regal
      Orb, an Exalted Orb): a family on the item leaves the pool, so what counts is its side, the
      weights of its mods and what they give the goal. Families that match on those are alike, so a
      state keeps one kind per such family type instead of one per family; the number of states
      follows the number of family types, not of families. `families` still names the families told
      apart on top of that (a bench craft's). False means the families are told apart only as
      `families` says.
    * `needs_crafted`: the action can only be used on an item that holds a crafted mod (Remove
      Crafted Mods). A planner offers it only when the start item holds one or some other offered
      action adds one.
    * `block_invariant`: when the junk families that no requirement and no craft tells apart are
      pooled into blocks, the action's kernel pushed through the block map is the same for every
      member of a block (only its legality may differ). An approximate answer built on blocks (ADR-0023)
      uses an action only if it declares this; the default is False, which refuses. Declare it only
      with the proof: an erasing reroll, whose outcome depends on the flags and the fractured mods, a
      deterministic craft, and Annulment (a pool of `n` slots loses one with probability `n / N`,
      whatever families they hold). The contract suite compares the members of blocks on the fixture items.
    * `variants`: with `pool_weight`, the action's kernel on a member of a block depends on the member
      only through the pool weight its pooled families hold, as a linear-fractional function (every
      outcome probability is `(c_0 + sum_j c_j H_j) / (W - sum_j H_j)`, `H_j` the weight held in pool
      `j`), so the best and the worst backup over the members are reached at the lightest or the
      heaviest member of each pool (ADR-0023, "When the members differ: variants"). An approximate
      answer takes those extreme members as the variants of the block. The default is False, which
      refuses; an adding action that keeps the mods (Augmentation, Regal, Exalted) declares it.
    * `fractures`: the action may fracture a mod the item already holds (a Fracturing Orb), so a mod
      that was an ordinary slot becomes a fractured one. The compressed state then stores a fractured mod of
      a family told apart only by its family type as that type, not as a mod id (ticket #69).
    * `rerolls_values`: the action changes the rolled values of mods the item holds, in place (a Divine
      Orb), so the result depends on which mod each slot stands for. The compressed state then tells apart
      the mods that a roll requirement of the goal looks at, by mod id (ticket #71).
    * `implicits`, `quality`, `offer`: the result depends on the implicits of the item (an Eldritch Exalted Orb
      reads the dominant side, an Orb of Conflict both grades), on its catalyst quality, or on the unveil offer
      it holds (a Pick); the compressed state then stores that part of the item (ADR-0027, ticket #142). They
      default to False in the dataclass, as `junk` defaults to True only for the base class: an action that
      overrides `reads` says what it reads, and `Action.reads` itself (an action that declares nothing) reads all
      three, like it reads every mod. An action that reads the offer reads the veiled placeholder, a mod of the
      item, so it must read the junk too.
    """

    junk: bool = True
    families: frozenset[str] | None = None
    pool_weight: bool = False
    needs_crafted: bool = False
    block_invariant: bool = False
    variants: bool = False
    fractures: bool = False
    rerolls_values: bool = False
    implicits: bool = False
    quality: bool = False
    offer: bool = False

    @property
    def item_state(self) -> bool:
        """Whether the action reads the implicits, the quality or the offer of the item (ADR-0027)."""
        return self.implicits or self.quality or self.offer

    @classmethod
    def adding(cls, *, block_invariant: bool = False, variants: bool = False) -> "Reads":
        """The action keeps the junk and adds mods to it: the families count by the pool weight they take out."""
        return cls(junk=True, families=frozenset(), pool_weight=True, block_invariant=block_invariant, variants=variants)

    @classmethod
    def nothing(cls, *, block_invariant: bool = False) -> "Reads":
        """The action reads nothing of the junk (it erases it): rerolls."""
        return cls(junk=False, families=frozenset(), block_invariant=block_invariant)


@dataclass(frozen=True)
class Adds:
    """What an action puts on the item, as far as a planner can tell without running it.

    * `named`: the ids of the mods it adds by name, the same on every use (a bench craft's mod, an
      essence's forced mod on this item class); None when it may add mods it does not name.
    * `crafted`: the named mods are crafted ones.
    * `draws`: it draws mods at random from the pool of the item.
    * `tag`: the mod tag a draw guarantees (a Harvest reforge), None for no guarantee.
    * `single_draw`: the first mod it draws is one draw over the pool of the item with only its
      fractured mods kept, among the mods with `tag` (all when None), so the weight share of ADR-0020
      is its chance (a Chaos Orb, a Harvest reforge).
    * `keeps_crafted`: a crafted mod on the item survives the action. The default is True, the safe
      value: a planner leaves out a bench craft that gives the goal nothing only when every other action
      it offers declares False (they erase the crafted mod, so the craft would only take a slot).
    * `wanted_only`: a planner offers it only for a target that wants a mod it names (`named`), whatever
      else the offers erase or keep (the aspect beasts: they add one fixed suffix and nothing else, so a
      target that does not want it gains nothing from its price and its slot).
    * `fractures`: one finished mod becomes fractured (a Fractured Fossil), so the fractured mods of the
      item change. The default is False; an action that fractures must say so, because pruning by bound
      (#118) holds the fractured mods of the start item fixed for every action it bounds.
    * `needs_roll_limit`: the action changes only rolled values (a Divine Orb), so it can matter only for a target
      with a roll limit (`min_roll`) on a mod that can occur on the item; a planner offers it only then (ticket #71).
      The default is False.
    * `implicits`, `quality`, `offer`: the action adds, replaces, removes or rerolls an implicit (an Ember, a Blessed
      Orb, an Orb of Conflict), sets or changes the catalyst quality (a catalyst), or draws or uses up the unveil
      offer (an Unveil, a Pick). The compressed state then stores that part of the item, so the change is seen
      (ADR-0027, ticket #142). The dataclass default is False, which says the action leaves it alone; `Action.adds`
      itself (an action that declares nothing) says True for all three, like it adds mods it does not name.
    * `corrupts`: the action corrupts the item and adds a corrupted implicit drawn from the corrupted pool of its class (a Vaal Orb,
      a Bloodstained resonator, the Locus of Corruption; ADR-0036). It needs `implicits`, since it puts an implicit on the item.
      A corrupted item takes no further action, so every outcome is a corrupted item that is the goal or a dead end, and the plan
      restarts from the start item as it does from any dead end. A planner offers such an action only for a target that asks for a
      corrupted implicit or allows a corrupted item (`Goal.takes_corrupted`); for any other target it is absent from the offers.
      The default is False, which says the action leaves the corruption as it was.
    * `keeps_mods`: with `corrupts`, every outcome that can still be the goal of a target that asks for a corrupted implicit holds
      the explicit mods the item held (a Vaal Orb and the Locus: their other outcomes, the brick among them, are dead ends for that
      target, ADR-0037). The outcome cannot meet an explicit requirement the item did not meet, so a planner offers the action for
      such a target only from a state in which every other requirement already passes (an exact pruning, ADR-0031, ADR-0036). A
      resonator that rerolls the explicit mods itself leaves it False and is never pruned this way. The default is False.

    `Adds` describes what the action puts on the item named in advance; for a drawn mod it says only
    that there is a draw, so pruning by proof (#118) goes through `outcomes` for those.
    """

    named: frozenset[str] | None = None
    crafted: bool = False
    draws: bool = True
    tag: str | None = None
    single_draw: bool = False
    keeps_crafted: bool = True
    wanted_only: bool = False
    fractures: bool = False
    needs_roll_limit: bool = False
    implicits: bool = False
    quality: bool = False
    offer: bool = False
    corrupts: bool = False
    keeps_mods: bool = False

    def __post_init__(self) -> None:
        if self.corrupts and not self.implicits:
            raise ValueError("an action that corrupts adds a corrupted implicit, so it must declare `implicits` too")
        if self.keeps_mods and not self.corrupts:
            raise ValueError("`keeps_mods` says what a corrupting action leaves of the explicit mods: it needs `corrupts`")

    @property
    def item_state(self) -> bool:
        """Whether the action changes the implicits, the quality or the offer of the item (ADR-0027)."""
        return self.implicits or self.quality or self.offer

    @classmethod
    def corrupting(cls, *, keeps_mods: bool = False, **fields) -> "Adds":
        """An action that corrupts the item and adds a corrupted implicit (ADR-0036): it draws, and it changes the implicits."""
        return cls(implicits=True, corrupts=True, keeps_mods=keeps_mods, **fields)

    @classmethod
    def removal(cls, *, keeps_crafted: bool = True) -> "Adds":
        """The action adds nothing (it only removes)."""
        return cls(named=frozenset(), draws=False, keeps_crafted=keeps_crafted)

    @classmethod
    def rerolling(cls) -> "Adds":
        """The action adds and removes no mod and changes values only (a Divine Orb).

        `named` stays None, not an empty set: an empty set would make it a craft that adds nothing, which a
        planner may leave out as useless, and a value reroll is not useless for a target with a roll limit.
        """
        return cls(named=None, draws=False, needs_roll_limit=True)

    @classmethod
    def erasing(cls, **fields) -> "Adds":
        """An action that erases every mod but the fractured ones (and so the crafted ones too)."""
        return cls(keeps_crafted=False, **fields)


@runtime_checkable
class ActionOutcomes(Protocol):
    """What `Action.outcomes` returns: the whole result, in four ways in.

    * `chance_all(mod_ids)`: the exact chance that the finished item holds all of these mods.
    * `distribution(label)`: the exact distribution of the new mods seen through `label`
      (`Outcome`s that sum to exactly 1); a deterministic action has one outcome of probability 1.
    * `sample(rng)`: one finished item from a seeded `random.Random`, with values rolled.
    * `components` / `fractures`: the mixture the kernel is built from (see `Fixed` and `Outcomes`):
      `(probability, part)` pairs that sum to 1, each part a pool draw (`Outcomes`) or a fixed
      result (`Fixed`), and whether one finished mod is fractured.
    """

    @property
    def components(self) -> tuple[tuple[Fraction, "Outcomes | Fixed | Rerolled"], ...]: ...

    @property
    def fractures(self) -> bool: ...

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction: ...

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]: ...

    def sample(self, rng: random.Random) -> Item: ...


@dataclass(frozen=True, eq=False)
class Fixed:
    """A result with no random draw: the finished `result` item, every mod added rolled at its lowest values.

    A part of `ActionOutcomes.components` for a deterministic action (a bench craft, Remove Crafted
    Mods, an Orb of Scouring). The kernel finds what it kept by looking for the mods of the item the
    action was given; any other mod of `result` is a new one.
    """

    data: GameData
    result: Item

    @property
    def retained(self) -> Item:
        return self.result


@dataclass(frozen=True, eq=False)
class Rerolled:
    """A result with the same mods, the values of some of them rerolled in place (a Divine Orb, ticket #71).

    A part of `ActionOutcomes.components`, like `Fixed`, for an action that changes values and nothing else.
    `given` is the item the action was used on and `retained` is that same item: no mod is added or removed.
    `changed` are the mods whose values are rerolled, as `(mod id, fractured, crafted)` keys of `given`'s
    mods (the fractured mods and the mods of a side that a lock protects are not in it). Each value of a
    changed mod is drawn uniformly over the integers of its stat's range, independently per stat; with
    `lucky` each value is rolled twice and the better one (the one nearer the stat's `max`) is kept.
    """

    data: GameData
    given: Item
    changed: frozenset[tuple[str, bool, bool]]
    lucky: bool = False

    @property
    def retained(self) -> Item:
        return self.given


class Action(ABC):
    """Base of every action; subclass it as a frozen dataclass and fill in the five questions.

    `claims` answers the sixth by itself (see the module docstring); override it only when the module of
    the class holds several actions that read different claims.
    """

    @property
    def variant(self) -> str:
        """What tells this action from another with the same `label` (a bench craft: its mod id); "" for none."""
        return ""

    @abstractmethod
    def label(self, data: GameData | None = None) -> str:
        """The stable name routes and the CLI use."""

    @abstractmethod
    def outcomes(self, data: GameData, item: Item) -> ActionOutcomes:
        """The exact result of one use on `item`; raises `NotApplicableError` or `OutOfScopeError`."""

    @abstractmethod
    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        """What one use consumes, by price-file name; read from claims. `data` may be None for an action that needs none."""

    def reads(self, data: GameData) -> Reads:
        """What of the item the result depends on; the default is everything (see `Reads`): every mod and the implicits, the quality and the offer."""
        return Reads(implicits=True, quality=True, offer=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        """What the action puts on `item`; the default is mods it does not name, and a change of the implicits, the quality and the offer.

        `data` and `item` may be None for an action whose additions depend on neither (an orb); one
        that needs them (an essence: its forced mod follows the item class) then answers `Adds()`.
        """
        return Adds(implicits=True, quality=True, offer=True)

    def twin_key(self, data: GameData, item: Item) -> Hashable | None:
        """A cheap key such that two actions of the catalog with equal, non-None keys give equal `outcomes`
        on every item of the same base, item level and rarity they apply to (their kernels are equal in every
        state), computed without building a pool. None (the default) says the action offers none; a planner
        then keeps it apart. Used by pruning (#118) to keep only the cheapest of a class of twins.
        """
        return None

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        """The ids of the registry claims the result or the price depends on.

        The default is every rule held as a constant of the module the class is defined in, of the modules
        of its base classes, and, for a module of this package, of the modules of the package it imports
        names from (`draw`, `outcomes`, `pool`, ...), one step and not transitively. It leans to naming too
        many rather than too few, since an approximate input missing from an answer hides an uncertainty
        (ADR-0028). A module that holds several actions reading different claims should override this with
        the exact ids. `data` may be None, as for `resources`; the default ignores it.
        """
        modules = {cls.__module__ for cls in type(self).__mro__ if cls not in (Action, ABC, object)}
        return frozenset().union(*(_module_claims(name) for name in modules))


PACKAGE = __name__.rpartition(".")[0]
SHARED_BY_ALL = frozenset({__name__, f"{PACKAGE}.catalog", f"{PACKAGE}.errors"})  # every action imports these: they say nothing about one


@cache
def _module_claims(name: str) -> frozenset[str]:
    """The rule ids held by module `name`, and by the modules of `actions` it imports names from when it is one."""
    modules = {name}
    if name.startswith(PACKAGE + "."):
        for value in vars(sys.modules[name]).values():
            origin = getattr(value, "__module__", None)
            if isinstance(origin, str) and origin.startswith(PACKAGE + ".") and origin not in SHARED_BY_ALL:
                modules.add(origin)
    return frozenset(
        value.id for module in modules for value in vars(sys.modules[module]).values() if isinstance(value, Rule)
    )
