"""Many plays of a route counted, and the verdict on a mean (ticket #555).

A `Tally` holds, over the plays, the number, the sum and the sum of squares of the cost, and the same per action label (the spend of
that label in a play, zero when it was not used) with its number of uses. From these come the mean, its standard error (the sample
standard deviation over the square root of the number of plays) and the standard error of each label's mean spend. Tallies add, so a
long simulation is split over runners (each with its own seed) and the parts are merged.

The verdict on a mean is stated in one place, `verdict`: the estimate agrees with the exact value when they differ by at most `K` of its
own standard errors (`K` = 4, the false-alarm chance of one comparison being about 6e-5). Nothing widens it: a disagreement is a
failure that names the step.
"""

import json
import math
from dataclasses import dataclass, field
from random import Random

from .play import Play, Player

K = 4.0  # standard errors
SLACK = 1e-9  # relative, for the float error of an exact value when the standard error is zero (a step that costs the same in every play)


@dataclass
class Tally:
    n: int = 0
    total: float = 0.0
    total_sq: float = 0.0
    spend: dict[str, list[float]] = field(default_factory=dict)  # label -> [sum, sum of squares]
    uses: dict[str, int] = field(default_factory=dict)
    stuck: int = 0  # plays that ended at a gap of the route (only a route with gaps has any); `n` counts the plays that finished

    def add_stuck(self) -> None:
        self.stuck += 1

    def finishing(self) -> tuple[int, int]:
        """(plays that met the target, plays in all)."""
        return self.n, self.n + self.stuck

    def add(self, play: Play) -> None:
        self.n += 1
        self.total += play.cost
        self.total_sq += play.cost * play.cost
        for label, spent in play.spend.items():
            pair = self.spend.setdefault(label, [0.0, 0.0])
            pair[0] += spent
            pair[1] += spent * spent
        for label, count in play.uses.items():
            self.uses[label] = self.uses.get(label, 0) + count

    def merge(self, other: "Tally") -> "Tally":
        merged = Tally(self.n + other.n, self.total + other.total, self.total_sq + other.total_sq, stuck=self.stuck + other.stuck)
        for source in (self.spend, other.spend):
            for label, (spent, squares) in source.items():
                pair = merged.spend.setdefault(label, [0.0, 0.0])
                pair[0] += spent
                pair[1] += squares
        for source in (self.uses, other.uses):
            for label, count in source.items():
                merged.uses[label] = merged.uses.get(label, 0) + count
        return merged

    # -- the estimates ---------------------------------------------------------------------------------------

    @staticmethod
    def _mean_se(n: int, total: float, total_sq: float) -> tuple[float, float]:
        if n < 2:
            return (total / n if n else 0.0), math.inf
        mean = total / n
        variance = max(0.0, (total_sq - n * mean * mean) / (n - 1))
        return mean, math.sqrt(variance / n)

    def mean_se(self) -> tuple[float, float]:
        return self._mean_se(self.n, self.total, self.total_sq)

    def spend_mean_se(self, label: str) -> tuple[float, float]:
        spent, squares = self.spend.get(label, [0.0, 0.0])
        return self._mean_se(self.n, spent, squares)

    def uses_mean(self, label: str) -> float:
        return self.uses.get(label, 0) / self.n if self.n else 0.0

    def to_dict(self) -> dict:
        return {"n": self.n, "total": self.total, "total_sq": self.total_sq, "spend": self.spend, "uses": self.uses, "stuck": self.stuck}

    @classmethod
    def from_dict(cls, document: dict) -> "Tally":
        return cls(
            document["n"], document["total"], document["total_sq"], {k: list(v) for k, v in document["spend"].items()}, dict(document["uses"]), document.get("stuck", 0)
        )

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


def simulate(player: Player, runs: int, seed: int, max_uses: int | None = None) -> Tally:
    """`runs` plays of the route, from a generator seeded with `seed`."""
    rng = Random(seed)
    tally = Tally()
    for _ in range(runs):
        tally.add(player.play(rng) if max_uses is None else player.play(rng, max_uses))
    return tally


def simulate_finishing(player: Player, runs: int, seed: int, max_uses: int | None = None) -> Tally:
    """`runs` plays of a route that may have gaps: a play that ends at a gap is counted as stuck, one that meets the target is added."""
    rng = Random(seed)
    tally = Tally()
    for _ in range(runs):
        play, gap = player.try_play(rng) if max_uses is None else player.try_play(rng, max_uses)
        if gap is None:
            tally.add(play)
        else:
            tally.add_stuck()
    return tally


def finishing_verdict(name: str, low: float, finished: int, total: int, k: float = K, high: float = 1.0) -> "Verdict":
    """The chance that a play of a route with gaps meets the target, against the planner's bracket `[low, high]`.

    `risk.evaluate` of a route with a reachable gap (`_evaluate.py`: the chain is not proper) runs a grid of costs and reports the success probability as a bracket,
    `Estimate(absorbed, absorbed, max(absorbed, absorbed + unresolved))`; the benchmark prints the `value`, the low end (issue #683). So the share of naive plays
    that finished must lie inside the bracket, widened by `k` binomial standard errors taken at the end it is outside of; inside it, it agrees.
    """
    share = finished / total if total else 0.0
    bound = low if share < low else high if share > high else None
    spread = math.sqrt(bound * (1 - bound) / total) if bound is not None and total and 0 < bound < 1 else 0.0
    text = f"{name} (the planner's bracket is [{low:.4g}, {high:.4g}]; {finished} of {total} plays finished, {share:.4g})"
    return Verdict(text, share if bound is None else bound, share, spread, k)


@dataclass(frozen=True)
class Verdict:
    name: str
    exact: float
    estimate: float
    se: float
    k: float = K

    @property
    def distance(self) -> float:
        """How far the estimate is from the exact value, in its own standard errors (infinite when the error is zero and they differ)."""
        gap = abs(self.estimate - self.exact)
        if gap <= SLACK * max(1.0, abs(self.exact)):
            return 0.0
        return gap / self.se if self.se > 0 else math.inf

    @property
    def agrees(self) -> bool:
        return self.distance <= self.k

    def __str__(self) -> str:
        return f"{self.name}: exact {self.exact:.6g}, simulated {self.estimate:.6g} +- {self.se:.3g} ({self.distance:.2f} standard errors; the limit is {self.k:g})"


def verdict_on(name: str, exact: float, mean_se: tuple[float, float], k: float = K) -> Verdict:
    return Verdict(name, exact, mean_se[0], mean_se[1], k)
