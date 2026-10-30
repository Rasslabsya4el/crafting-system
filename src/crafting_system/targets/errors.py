"""The one error of the target layer.

Every failure of reading, checking or resolving a target file is a `TargetError`, which is a
`ValueError`. The message starts with `<file>:<line>: `, then the key path (`requirements[1].min_tier`)
and what is wrong, in words the owner of the file can act on.
"""


class TargetError(ValueError):
    """A target file that cannot be read, is not valid, or names something the game data does not have."""
