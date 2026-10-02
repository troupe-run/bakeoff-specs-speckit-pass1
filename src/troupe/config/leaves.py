"""Leaves of the configuration (the unit of events) and the events a change produces."""

from dataclasses import dataclass
from typing import Literal

from troupe.config.scalars import Scalar, Value, scalars_equal
from troupe.config.tree import Located, LocatedMapping, LocatedScalar, LocatedSequence, TextInclude

type Op = Literal["import", "set", "remove"]


@dataclass(frozen=True)
class LeafEvent:
    op: Op
    path: str
    old: Scalar
    new: Scalar


def leaves(node: Located, prefix: str = "") -> dict[str, Scalar]:
    """Every scalar leaf by dotted path, in document order with includes expanded in place.

    Empty collections have no leaves (research B-12).
    """
    result: dict[str, Scalar] = {}
    _collect(node, prefix, result)
    return result


def _join(prefix: str, segment: str) -> str:
    return f"{prefix}.{segment}" if prefix else segment


def _collect(node: Located, prefix: str, out: dict[str, Scalar]) -> None:
    if isinstance(node, LocatedMapping):
        for key, value in node.entries:
            _collect(value, _join(prefix, str(key.node.value)), out)
    elif isinstance(node, LocatedSequence):
        for index, item in enumerate(node.items):
            _collect(item, _join(prefix, str(index)), out)
    else:
        out[prefix] = node.value


def to_value(node: Located) -> Value:
    if isinstance(node, LocatedMapping):
        return {str(key.node.value): to_value(value) for key, value in node.entries}
    if isinstance(node, LocatedSequence):
        return [to_value(item) for item in node.items]
    if isinstance(node, (LocatedScalar, TextInclude)):
        return node.value
    raise TypeError(node)


def written_value(node: Located) -> Value:
    """The value as written in the files: includes appear as their `file:` strings."""
    if node.included_by is not None:
        return node.included_by.value
    if isinstance(node, TextInclude):
        return node.include.value
    if isinstance(node, LocatedMapping):
        return {str(key.node.value): written_value(value) for key, value in node.entries}
    if isinstance(node, LocatedSequence):
        return [written_value(item) for item in node.items]
    return node.value


def diff_events(before: dict[str, Scalar], after: dict[str, Scalar]) -> list[LeafEvent]:
    """`set` events in `after` order, then `remove` events in `before` order (spec D-3)."""
    events: list[LeafEvent] = []
    for path, new in after.items():
        if path not in before:
            events.append(LeafEvent("set", path, None, new))
        elif not scalars_equal(before[path], new):
            events.append(LeafEvent("set", path, before[path], new))
    for path, old in before.items():
        if path not in after:
            events.append(LeafEvent("remove", path, old, None))
    return events
