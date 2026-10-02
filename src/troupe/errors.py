"""Errors and their exit codes.

This module is the one place where exit codes are decided (Constitution Principle IV). Only the
CLI entry point turns these exceptions into a stderr message and an exit status.
"""


class TroupeError(Exception):
    """A failure the user must see. The message must name the offending path or file."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(TroupeError):
    """Bad command line: unknown command, missing argument, invalid PATH or VALUE."""

    exit_code = 2


class WriteRefused(TroupeError):
    """The requested change cannot be written safely; no file was changed."""

    exit_code = 3


class LoadError(TroupeError):
    """The configuration cannot be loaded."""

    exit_code = 4


class PathError(TroupeError):
    """The path does not exist, or is the wrong kind of node for the command."""

    exit_code = 5
