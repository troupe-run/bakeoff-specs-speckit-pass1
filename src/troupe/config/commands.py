"""The `troupe config` subcommands: get, show, set, history, watch."""

import json
import signal
import threading
from collections.abc import Callable
from pathlib import Path

from troupe.config import view
from troupe.config.edit.apply import apply_set
from troupe.config.leaves import leaves
from troupe.config.loader import Loaded, load
from troupe.config.lock import theatre_lock
from troupe.config.paths import ConfigPath, dotted_is_within, is_index
from troupe.config.scalars import format_scalar, parse_value
from troupe.config.store import ConfigStore
from troupe.config.sync import reconcile as reconcile_files
from troupe.config.tree import (
    Located,
    LocatedMapping,
    LocatedScalar,
    LocatedSequence,
    TextInclude,
)
from troupe.config.watch import run_watch
from troupe.errors import PathError


def open_theatre(theatre: Path, *, reconcile: bool) -> tuple[Loaded, ConfigStore]:
    """Load the configuration; import it on first use (step 1 D-2), else reconcile if asked.

    This is what every command does before its own work. Every command except `history`
    reconciles, so hand edits made while nothing was running are recorded (step 2 FR-120,
    superseding step 1 D-1); `history` reports only what has been recorded (FR-121). The import
    or reconcile stands even if the command then fails. Call with `theatre_lock` held.
    """
    loaded = load(theatre)
    store = ConfigStore(theatre)
    if not store.is_imported():
        store.import_leaves(leaves(loaded.root))
    elif reconcile:
        reconcile_files(loaded, store)
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


def use_show_hint(path: ConfigPath, node: Located) -> str:
    """`get` refuses a mapping or list and points to `show`, which prints it (spec FR-202)."""
    return (
        f"{path}: is {node_kind(node)}, not a scalar; use `troupe config show {path}` to print it"
    )


def get(theatre: Path, path_text: str) -> str:
    """Print the scalar at PATH, as step 1's `show` did (spec FR-200 to FR-204)."""
    path = ConfigPath.parse(path_text)
    with theatre_lock(theatre):
        loaded, _ = open_theatre(theatre, reconcile=True)
    node = resolve(loaded.root, path)
    if isinstance(node, (LocatedMapping, LocatedSequence)):
        raise PathError(use_show_hint(path, node))
    return format_scalar(node.value)


def show(theatre: Path, path_text: str | None, *, sources: bool) -> str:
    """Print a scalar like `get`, anything else as YAML (spec FR-210 to FR-234)."""
    path = None if path_text is None else ConfigPath.parse(path_text)
    with theatre_lock(theatre):
        loaded, _ = open_theatre(theatre, reconcile=True)
    node = loaded.root if path is None else resolve(loaded.root, path)
    if not sources and isinstance(node, (LocatedScalar, TextInclude)):
        return format_scalar(node.value)
    return view.render(node, theatre, sources=sources)


def set_value(theatre: Path, path_text: str, value_text: str) -> str:
    path = ConfigPath.parse(path_text)
    value = parse_value(value_text)
    # The lock spans load, write and record, so the write-back is recorded before `watch` can
    # load it, and `watch` then finds nothing to record (spec FR-130).
    with theatre_lock(theatre):
        loaded, store = open_theatre(theatre, reconcile=True)
        events = apply_set(theatre, loaded, path, value, before_write=store.check_writable)
        store.record(events)
    return ""


def history(theatre: Path, path_text: str | None) -> str:
    if path_text is not None:
        ConfigPath.parse(path_text)
    with theatre_lock(theatre):
        _, store = open_theatre(theatre, reconcile=False)
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


def watch(
    theatre: Path, display: str, announce: Callable[[str], None], report: Callable[[str], None]
) -> str:
    """Record hand edits as they happen, until SIGINT or SIGTERM (spec FR-100 to FR-106)."""
    stop = threading.Event()
    # The handlers only set a flag, so a reconcile in progress always finishes (research S-6).
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())

    def sync() -> Loaded:
        with theatre_lock(theatre):
            loaded, _ = open_theatre(theatre, reconcile=True)
        return loaded

    run_watch(theatre, sync, lambda: announce(f"watching {display}\n"), stop, report)
    return ""
