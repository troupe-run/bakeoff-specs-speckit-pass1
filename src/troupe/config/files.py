"""Finding, reading and writing the theatre's files."""

import contextlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from troupe.errors import LoadError, WriteRefused

TROUPE_DIR = ".troupe"
CONFIG_NAMES = ("troupe.yml", "troupe.yaml")
YAML_SUFFIXES = (".yml", ".yaml")
CRLF = "\r\n"
LF = "\n"


def is_yaml_name(path: Path) -> bool:
    """Include targets with these suffixes are embedded as YAML; others are text."""
    return path.name.endswith(YAML_SUFFIXES)


def find_config(theatre: Path) -> Path:
    """The theatre's configuration file: exactly one of CONFIG_NAMES under TROUPE_DIR."""
    directory = theatre / TROUPE_DIR
    found = [directory / name for name in CONFIG_NAMES if (directory / name).is_file()]
    if not found:
        names = " or ".join(str(directory / name) for name in CONFIG_NAMES)
        raise LoadError(f"no configuration file: expected {names}")
    if len(found) > 1:
        raise LoadError(f"ambiguous configuration: both {found[0]} and {found[1]} exist")
    return found[0]


def detect_newline(text: str) -> str:
    """A file "uses CRLF" when its first line ending is CRLF (spec D-6)."""
    index = text.find(LF)
    return CRLF if index > 0 and text[index - 1] == "\r" else LF


@dataclass(eq=False)
class SourceFile:
    path: Path
    text: str
    kind: Literal["yaml", "text"]

    @property
    def newline(self) -> str:
        return detect_newline(self.text)


def read_source(path: Path) -> SourceFile:
    """Read a file as UTF-8 text with its line endings untouched."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise LoadError(f"{path}: file not found") from None
    except IsADirectoryError:
        raise LoadError(f"{path}: is a directory, not a file") from None
    except OSError as error:
        raise LoadError(f"{path}: cannot read: {error.strerror}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise LoadError(f"{path}: not valid UTF-8") from None
    return SourceFile(path, text, "yaml" if is_yaml_name(path) else "text")


def check_writable(path: Path) -> None:
    """Refuse to replace a file the user could not write themselves (Constitution I).

    The atomic replace only needs the directory to be writable, so without this check a
    read-only file would be silently overwritten.
    """
    if not os.access(path, os.W_OK):
        raise WriteRefused(f"{path}: file is not writable; no file was changed")
    if not os.access(path.parent, os.W_OK):
        raise WriteRefused(f"{path}: its directory is not writable; no file was changed")


def atomic_write(path: Path, text: str) -> None:
    """Replace a file's content all at once, so it is never left half-written (spec D-8)."""
    data = text.encode("utf-8")
    if path.read_bytes() == data:
        return
    check_writable(path)
    try:
        _replace(path, data)
    except OSError as error:
        raise WriteRefused(f"{path}: cannot write: {error.strerror}; no file was changed") from None


def _replace(path: Path, data: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise
