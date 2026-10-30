"""Errors of the actions.

Every refusal an action raises on purpose is an `ActionError`, which is a `ValueError`. The message
names the reason in plain English. The two subclasses tell a caller what to do about it: a
`NotApplicableError` is the game refusing (nothing would be consumed, the planner must not offer
the action here), an `OutOfScopeError` is a state the admitted rules do not cover yet (the planner
must treat the action as unavailable, not as refused by the game).
"""


class ActionError(ValueError):
    """Base of every error an action raises on purpose."""


class NotApplicableError(ActionError):
    """The game refuses this action on this item; nothing is consumed."""


class OutOfScopeError(ActionError):
    """The item is in a state that no admitted rule covers yet, so no outcome is given."""
