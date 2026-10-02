"""The `troupe config` subcommands: show, set, history."""

import json
from pathlib import Path

from troupe.config.edit.apply import apply_set
from troupe.config.leaves import leaves
from troupe.config.loader import Loaded, load
from troupe.config.paths import ConfigPath, dotted_is_within, is_index
from troupe.config.scalars import format_scalar, parse_value
from troupe.config.store import ConfigStore
from troupe.config.tree import Located, LocatedMapping, LocatedSequence, TextInclude
from troupe.errors import PathError


def open_theatre(theatre: Path) -> tuple[Loaded, ConfigStore]:
    """Load the configuration and import it on first use (spec D-2).

    The import stands even if the command then fails; importing is not reconciling, so a
    theatre that was imported before is never imported again.
    """
    loaded = load(theatre)
    store = ConfigStore(theatre)
    if not store.is_imported():
        store.import_leaves(leaves(loaded.root))
    return loaded, store


def node_kind(node: Located) -> str:
    if isinstance(node, LocatedMapping):
        return "a mapping"
    if isinstance(node, LocatedSequence):
        return "a list"
    if isinstance(node, TextInclude):
        return "a text include"
    return "a scalar"


def resolve(root: Located, path: ConfigPath) -> Located:
    """The node at `path`, or PathError naming the path (research B-1)."""
    node = root
    for depth, segment in enumerate(path.segments):
        here = ConfigPath(path.segments[: depth + 1])
        if isinstance(node, LocatedMapping):
            if is_index(segment):
                raise PathError(
                    f"{here}: {segment!r} is a list index but {_parent(path, depth)} is a mapping"
                )
            child = node.get(segment)
            if child is None:
                raise PathError(f"{here}: path not found")
            node = child
        elif isinstance(node, LocatedSequence):
            if not is_index(segment):
                raise PathError(
                    f"{here}: {_parent(path, depth)} is a list; {segment!r} is not an index"
                )
            index = int(segment)
            if index >= len(node.items):
                raise PathError(f"{here}: index out of range (list has {len(node.items)} items)")
            node = node.items[index]
        else:
            raise PathError(
                f"{here}: {_parent(path, depth)} is {node_kind(node)}, not a mapping or list"
            )
    return node


def _parent(path: ConfigPath, depth: int) -> str:
    return ConfigPath(path.segments[:depth]).dotted if depth else "the top level"


def show(theatre: Path, path_text: str) -> str:
    path = ConfigPath.parse(path_text)
    loaded, _ = open_theatre(theatre)
    node = resolve(loaded.root, path)
    if isinstance(node, (LocatedMapping, LocatedSequence)):
        raise PathError(f"{path}: is {node_kind(node)}, not a scalar")
    return format_scalar(node.value)


def set_value(theatre: Path, path_text: str, value_text: str) -> str:
    path = ConfigPath.parse(path_text)
    value = parse_value(value_text)
    loaded, store = open_theatre(theatre)
    events = apply_set(theatre, loaded, path, value, before_write=store.check_writable)
    store.record(events)
    return ""


def history(theatre: Path, path_text: str | None) -> str:
    if path_text is not None:
        ConfigPath.parse(path_text)
    _, store = open_theatre(theatre)
    lines = []
    for record in store.history():
        if path_text is not None and not dotted_is_within(record.path, path_text):
            continue
        entry = {
            "seq": record.seq,
            "op": record.op,
            "path": record.path,
            "old": record.old,
            "new": record.new,
        }
        lines.append(json.dumps(entry, ensure_ascii=False) + "\n")
    return "".join(lines)
