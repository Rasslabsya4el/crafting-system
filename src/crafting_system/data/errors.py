"""Errors of the data layer.

Every failure the layer raises on purpose is a `DataError`, so the command line (and later the
cli module) can catch one class, print the message and exit, while a plain bug still shows a
traceback.
"""


class DataError(Exception):
    """Base of every error the data layer raises on purpose."""


class HashMismatchError(DataError):
    """A file's size or sha256 differs from the pin: the data is not the pinned version."""


class MissingDataError(DataError):
    """A pinned file is not in the cache folder (fetch has not run yet)."""


class FetchError(DataError):
    """The network or the disk failed while fetching, storing or reading a cached pinned file
    (also raised when a cached file cannot be read in verify and load)."""


class RawFormatError(DataError):
    """A raw repoe-fork record does not have the shape the normalizer relies on."""
