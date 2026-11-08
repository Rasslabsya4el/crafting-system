"""The reviewed verdicts of the benchmark's review row (ticket #634).

`benchmark` prints a "needs a human" row for every route whose planner mean is below the review line of the guide's (`_benchmark_divergence`).
A person who took such a route apart writes the verdict here, in ONE file beside the list of routes (`_benchmark.BENCHMARKS`), not in the
route files, which stay the guide's words. The row then reads `reviewed: real find (#591), ratio at review 0.057` and stops asking, until
something it was reviewed on has moved:

* the ratio planner mean / guide mean moves from the ratio at review by more than the tolerance (`[benchmark] review_tolerance`, a share
  of the ratio at review, either way);
* the target file text or the route file text changed (a hash of each, with line ends read as `\\n` so that Windows and Linux agree);
* the planner's first divergent action changed.

Then the row says "NEEDS A HUMAN AGAIN" with each reason. A verdict is a prompt that a person has looked, never a cut of the search or a
proof (OR-12): it does not change a mean. A route above the review line keeps its verdict shown, so that a verdict is never lost silently.

A verdict belongs to one half of an entry: the `guide` (the route file as the guide wrote it) or the `completed route` (the route with a last rule
that restarts, `BenchmarkRoute.completed`, which is what has a finite mean for a guide with gaps). The hash is of the file that half evaluates.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

REAL_FIND = "real find"  # the planner is right and the guide wastes
GUIDE_WRONG = "the guide is wrong"  # the guide contradicts itself or the game
OUR_COMPLETION = "our completion"  # a rule we added to the guide (a restart) makes the cost
KINDS = (REAL_FIND, GUIDE_WRONG, OUR_COMPLETION)

GUIDE = "guide"
COMPLETED = "completed route"


@dataclass(frozen=True)
class Verdict:
    """What a person found on one route, and what it was reviewed on.

    `issues` are the issues that took the route apart; `ratio` and `date` are the ratio planner mean / guide mean and the day of the review.
    `target_hash` and `route_hash` are `text_hash` of the target file and of the route file evaluated; `planner_action` is the label of the
    planner's action at the first state where the route takes another one.
    """

    id: str
    side: str
    kind: str
    issues: tuple[int, ...]
    ratio: float
    date: str
    target_hash: str
    route_hash: str
    planner_action: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"verdict {self.kind!r} of {self.id}: must be one of {', '.join(KINDS)}")
        if self.side not in (GUIDE, COMPLETED):
            raise ValueError(f"side {self.side!r} of {self.id}: must be {GUIDE!r} or {COMPLETED!r}")
        if not (self.issues and self.ratio > 0):
            raise ValueError(f"the verdict of {self.id} names no issue or a ratio that is not above 0")

    @property
    def text(self) -> str:
        """`real find (#591)` or, for two issues, `real find (#599, #628)`."""
        return f"{self.kind} ({', '.join(f'#{number}' for number in self.issues)})"


def text_hash(path: Path) -> str:
    """The first 16 hex digits of the SHA-256 of the file's text, line ends read as `\\n`."""
    text = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(text).hexdigest()[:16]


def verdict_of(id: str, side: str) -> Verdict | None:
    """The verdict of one half of one route, or None when no person has reviewed it."""
    return next((each for each in VERDICTS if each.id == id and each.side == side), None)


@dataclass(frozen=True)
class Reviewing:
    """What the benchmark knows about one half of one route when it judges the verdict: the verdict, the tolerance and the hashes now."""

    verdict: Verdict | None
    tolerance: float
    target_hash: str
    route_hash: str

    def judge(self, ratio: float | None, planner_action: str | None) -> dict | None:
        """The verdict block of the entry, or None for a route with no verdict.

        `reasons` is empty while the verdict stands; each reason is a sentence for the row. `again` is true when there is any.
        """
        found = self.verdict
        if found is None:
            return None
        reasons = []
        if ratio is None:
            reasons.append("the ratio is not known now (a mean is missing)")
        elif abs(ratio - found.ratio) > self.tolerance * found.ratio:
            reasons.append(
                f"the ratio is {ratio:.3f}, {self._direction(ratio)} the ratio at review {found.ratio:.3f} by more than the tolerance {self.tolerance:g} "
                f"(allowed {found.ratio * (1 - self.tolerance):.3f} to {found.ratio * (1 + self.tolerance):.3f})"
            )
        if self.target_hash != found.target_hash:
            reasons.append("the target file text changed since the review")
        if self.route_hash != found.route_hash:
            reasons.append("the route file text changed since the review")
        if planner_action != found.planner_action:
            reasons.append(f"the planner's first divergent action is now {planner_action or 'none'}, it was {found.planner_action} at the review")
        return {
            "verdict": found.kind,
            "issues": list(found.issues),
            "text": found.text,
            "ratio_at_review": found.ratio,
            "date": found.date,
            "tolerance": self.tolerance,
            "planner_action_at_review": found.planner_action,
            "again": bool(reasons),
            "reasons": reasons,
        }

    def _direction(self, ratio: float) -> str:
        return "above" if ratio > self.verdict.ratio else "below"  # type: ignore[union-attr]


# --- the verdicts ----------------------------------------------------------------------------------
# One entry per reviewed half of a route. Write the hashes with `text_hash` of the files named in `BENCHMARKS`; a stale one is caught by
# tests/test_cli_benchmark_verdicts.py. Add an entry only after the route has been taken apart to the end (brief: every divergence group
# and every odds row), with the issue that did it.

VERDICTS: tuple[Verdict, ...] = (
    # #591: one Prismatic Fossil reaches the target as often as the guide's Dense + Shuddering pair, at 1/25 of the cost per use (2.27% and 2.24% in our
    # model; 2.31% and 2.40% in the emulator, #617). All 43 divergent states are this one choice. Ratio 0.0574 (heavy run 42395491917).
    Verdict("R08", GUIDE, REAL_FIND, (591,), 0.057, "2026-11-07", "1bb0bbe749c67183", "56dcd89a66b4e5a2", "Fossils Prismatic Fossil"),
    # #592: the same on the Life boots, Prismatic against Pristine + Shuddering, 1/22 of the cost per use. Ratio 0.0580.
    Verdict("R09", GUIDE, REAL_FIND, (592,), 0.058, "2026-11-07", "f672f6319b34e3e4", "7273002665b5cd82", "Fossils Prismatic Fossil"),
    # #599, #628: the completed route keeps to what the guide and the game force; what is left of the gap is the planner's own moves (the Annulment under
    # the craft, Rage to Exalted, Annulment to Exalted). The guide's own route has gaps, so its ratio is not known and it has no row. Ratio 0.3310.
    Verdict("R04", COMPLETED, REAL_FIND, (599, 628), 0.331, "2026-11-07", "724ef091ef9f78b5", "4f6c0229e2688042", "Exalted Orb"),
)
