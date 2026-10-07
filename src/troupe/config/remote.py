"""Refusing a change to remote content, and naming the include line to change instead (spec
FR-610, FR-611, D-60, D-70; research U-7).

The include line depends on the route PATH takes (one URL may be included in several places),
so it is found by walking PATH: the last include, on the way, that is written in a local file and
brings in remote content. With nested remote includes that is the outermost one.
"""

from pathlib import Path

from troupe.config.loader import Loaded
from troupe.config.paths import ConfigPath, is_index
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
    as_written,
)
from troupe.config.view import source_label
from troupe.errors import WriteRefused


def remote_site(loaded: Loaded, path: ConfigPath) -> LocatedScalar | None:
    """The include string, in a local file, through which PATH reaches remote content."""
    found: LocatedScalar | None = None
    node: Located | None = loaded.root
    for segment in path.segments:
        if isinstance(node, LocatedMapping):
            node = node.get(segment)
        elif isinstance(node, LocatedSequence) and is_index(segment):
            index = int(segment)
            node = node.items[index] if index < len(node.items) else None
        else:
            node = None
        if node is None:
            break
        include = _include_string(node)
        if include is not None and isinstance(include.file.path, Path) and _is_remote(node):
            found = include
    return found


def _include_string(node: Located) -> LocatedScalar | None:
    """The include string of an include root: the scalar-form string, or the `$ref` value (the
    loader sets `included_by` to it in mapping form too, step 5 research O-2)."""
    if isinstance(node, TextInclude):
        return node.include
    return node.included_by


def _is_remote(node: Located) -> bool:
    source = node.target if isinstance(node, TextInclude) else node.file
    return isinstance(source.path, str)


def refuse_remote(loaded: Loaded, path: ConfigPath, theatre: Path) -> WriteRefused | None:
    """The refusal for a `set` of PATH that would write remote content (FR-611); None if PATH
    does not reach remote content through a local include (the caller then keeps its own)."""
    site = remote_site(loaded, path)
    if site is None:
        return None
    line = int(site.node.start_mark.line) + 1
    return WriteRefused(
        f"{path}: comes from the remote include {as_written(site)} (line {line} of "
        f"{source_label(theatre, site.file)}); remote content is read-only — change that "
        "include line instead; no file was changed"
    )
