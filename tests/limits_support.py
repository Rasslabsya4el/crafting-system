"""Reading the limits of an answer in tests (ticket #459): the limits of one kind, their labels, their reasons."""

from crafting_system.cli import Limit
from crafting_system.cli._limits import limit_text


def of_kind(limits, kind: str) -> list[Limit]:
    """The limits of `limits` that are of group `kind`, in the order they were written."""
    return [limit for limit in limits if limit.kind == kind]


def only(limits, kind: str) -> Limit:
    """The one limit of group `kind`; a test that expects one fails when there are none or several."""
    (found,) = of_kind(limits, kind)
    return found


def labels_of(limits, kind: str) -> set[str]:
    """Every label of every limit of group `kind`."""
    return {label for limit in of_kind(limits, kind) for label in limit.labels}


def sentences(limits) -> list[str]:
    """Each limit as the sentence the text report and the page print."""
    return [limit_text(limit) for limit in limits]


def notes(limits) -> list[Limit]:
    """The limits that say how the query was decided, how the tree is drawn or which percentile was not computed: what `Plan.note` held."""
    return [limit for limit in limits if limit.kind in ("how-solved", "display", "risk")]


def note_text(limits) -> str:
    """The sentences of `notes`, joined: for a test that looks for a phrase of the old note."""
    return " ".join(sentences(notes(limits)))
