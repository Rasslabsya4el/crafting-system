"""The one contract every crafting action meets, so a new method is one file and needs no edit elsewhere (ticket #108).

An action is a frozen dataclass that subclasses `Action` and answers five questions:

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

`abstraction` builds its states from `reads` and its kernels from `outcomes` alone; `cli` builds its
offers from the catalog (`catalog.py`), `resources` and `adds`; `simulator` calls `outcomes(...).sample`.
None of them imports a concrete action. The defaults of the base class are the safe ones: an action
that declares nothing reads every mod of the item and adds mods it does not name, which is exact but
makes the state space large and no filter can drop it.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from crafting_system.data import GameData, Mod
from crafting_system.items import Item

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
      with the proof: an erasing reroll, whose outcome depends on the flags and the fractured mods, and
      a deterministic craft. The contract suite compares the members of blocks on the fixture items.
    """

    junk: bool = True
    families: frozenset[str] | None = None
    pool_weight: bool = False
    needs_crafted: bool = False
    block_invariant: bool = False

    @classmethod
    def adding(cls, *, block_invariant: bool = False) -> "Reads":
        """The action keeps the junk and adds mods to it: the families count by the pool weight they take out."""
        return cls(junk=True, families=frozenset(), pool_weight=True, block_invariant=block_invariant)

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

    `Adds` describes what the action puts on the item named in advance; for a drawn mod it says only
    that there is a draw, so pruning by proof (#118) goes through `outcomes` for those.
    """

    named: frozenset[str] | None = None
    crafted: bool = False
    draws: bool = True
    tag: str | None = None
    single_draw: bool = False
    keeps_crafted: bool = True

    @classmethod
    def removal(cls, *, keeps_crafted: bool = True) -> "Adds":
        """The action adds nothing (it only removes)."""
        return cls(named=frozenset(), draws=False, keeps_crafted=keeps_crafted)

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
    def components(self) -> tuple[tuple[Fraction, "Outcomes | Fixed"], ...]: ...

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


class Action(ABC):
    """Base of every action; subclass it as a frozen dataclass and fill in the five questions."""

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
        """What of the item the result depends on; the default is everything (see `Reads`)."""
        return Reads()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        """What the action puts on `item`; the default is mods it does not name.

        `data` and `item` may be None for an action whose additions depend on neither (an orb); one
        that needs them (an essence: its forced mod follows the item class) then answers `Adds()`.
        """
        return Adds()
