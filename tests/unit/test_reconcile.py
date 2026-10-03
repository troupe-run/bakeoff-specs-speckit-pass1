"""Reconcile (spec FR-110 to FR-116): files compared with the projection, one event per leaf."""

from pathlib import Path

import pytest

from troupe.config.leaves import LeafEvent, leaves
from troupe.config.loader import load
from troupe.config.store import ConfigStore
from troupe.config.sync import reconcile


def _theatre(tmp_path: Path, text: str | bytes) -> Path:
    (tmp_path / ".troupe").mkdir(exist_ok=True)
    _write(tmp_path, text)
    return tmp_path


def _write(theatre: Path, text: str | bytes, name: str = "troupe.yml") -> None:
    data = text.encode("utf-8") if isinstance(text, str) else text
    (theatre / ".troupe" / name).write_bytes(data)


def _imported(tmp_path: Path, text: str) -> Path:
    theatre = _theatre(tmp_path, text)
    ConfigStore(theatre).import_leaves(leaves(load(theatre).root))
    return theatre


def _reconcile(theatre: Path) -> list[LeafEvent]:
    return reconcile(load(theatre), ConfigStore(theatre))


def test_unchanged_files_record_nothing(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\nb: [x, y]\n")
    assert _reconcile(theatre) == []
    assert len(ConfigStore(theatre).history()) == 3


def test_changed_leaf_is_a_set_event(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\n")
    _write(theatre, "a: 2\n")
    assert _reconcile(theatre) == [LeafEvent("set", "a", 1, 2)]


def test_new_leaf_is_a_set_event_from_null(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\n")
    _write(theatre, "a: 1\nc: 3\n")
    assert _reconcile(theatre) == [LeafEvent("set", "c", None, 3)]


def test_missing_leaf_is_a_remove_event_to_null(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\nb: [x, y]\n")
    _write(theatre, "a: 1\nb: [x]\n")
    assert _reconcile(theatre) == [LeafEvent("remove", "b.1", "y", None)]


@pytest.mark.parametrize(
    ("edited", "new"),
    [("a: '1'\n", "1"), ("a: 1.0\n", 1.0), ("a: true\n", True)],
)
def test_type_only_change_is_a_change(tmp_path: Path, edited: str, new: object) -> None:
    theatre = _imported(tmp_path, "a: 1\n")
    _write(theatre, edited)
    events = _reconcile(theatre)
    assert len(events) == 1
    assert (events[0].op, events[0].path, events[0].old) == ("set", "a", 1)
    assert type(events[0].new) is type(new) and events[0].new == new


ORIGINAL = "a: x\nb: [x, y]\nc:\n  d: 1\n"


@pytest.mark.parametrize(
    "edited",
    [
        "# a comment\na: x   # another\nb: [x, y]\nc:\n  d: 1\n",
        "a: x\nb: [ x,   y ]\nc:\n    d: 1\n",
        "a: \"x\"\nb: ['x', y]\nc:\n  d: 1\n",
        "\na: x\n\nb: [x, y]\n\nc:\n  d: 1\n\n",
        "c:\n  d: 1\nb: [x, y]\na: x\n",
        "a: x\r\nb: [x, y]\r\nc:\r\n  d: 1\r\n",
        "a: x\nb:\n  - x\n  - y\nc: {d: 1}\n",
    ],
    ids=["comments", "indentation", "quoting", "blank-lines", "key-order", "crlf", "block-flow"],
)
def test_edit_that_changes_no_leaf_records_nothing(tmp_path: Path, edited: str) -> None:
    theatre = _imported(tmp_path, ORIGINAL)
    _write(theatre, edited)
    assert _reconcile(theatre) == []
    assert len(ConfigStore(theatre).history()) == 4


def test_sets_in_file_order_then_removes_in_projection_order(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\nb: 2\nc: 3\n")
    _write(theatre, "a: 1\nb: 2\nc: 3\nd: 4\n")
    assert _reconcile(theatre) == [LeafEvent("set", "d", None, 4)]
    # Projection order is now a, b, c, d; the file lists d before c.
    _write(theatre, "e: 5\nb: 2\nc: 30\n")
    assert _reconcile(theatre) == [
        LeafEvent("set", "e", None, 5),
        LeafEvent("set", "c", 3, 30),
        LeafEvent("remove", "a", 1, None),
        LeafEvent("remove", "d", 4, None),
    ]


def test_reconcile_events_are_persisted(tmp_path: Path) -> None:
    theatre = _imported(tmp_path, "a: 1\n")
    _write(theatre, "a: 2\n")
    _reconcile(theatre)
    records = ConfigStore(theatre).history()
    assert [(r.seq, r.op, r.path, r.old, r.new) for r in records] == [
        (1, "import", "a", None, 1),
        (2, "set", "a", 1, 2),
    ]
    assert ConfigStore(theatre).leaves() == {"a": 2}
