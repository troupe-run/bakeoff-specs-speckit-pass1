"""`config watch` records hand edits as they happen (spec US2, FR-100 to FR-104)."""

import os
import time
from collections.abc import Callable
from typing import Any

from tests.conftest import Theatre, Watcher, recorded, wait_for_history

type Start = Callable[..., Watcher]


def _has(op: str, path: str, old: Any, new: Any) -> Callable[[list[dict[str, Any]]], bool]:
    def check(events: list[dict[str, Any]]) -> bool:
        return any((e["op"], e["path"], e["old"], e["new"]) == (op, path, old, new) for e in events)

    return check


def _edit(theatre: Theatre, relpath: str, content: str) -> float:
    """Write a file and return the moment just before the write."""
    since = time.monotonic()
    theatre.write(relpath, content)
    return since


def test_prints_one_watching_line_and_keeps_running(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    assert watcher.out == f"watching {theatre.root}\n"
    time.sleep(0.5)
    assert watcher.running()
    assert watcher.out == f"watching {theatre.root}\n"


def test_edit_made_right_after_the_line_is_recorded(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    start_watch()
    since = _edit(theatre, "troupe.yml", "a: 2\n")
    wait_for_history(theatre, _has("set", "a", 1, 2), since)


def test_edit_in_a_yaml_include_is_recorded(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("agents/coder.yaml", "model: opus\n")
    theatre.write("troupe.yml", "agents:\n  coder: file:agents/coder.yaml\n")
    start_watch()
    since = _edit(theatre, "agents/coder.yaml", "model: sonnet\n")
    wait_for_history(theatre, _has("set", "agents.coder.model", "opus", "sonnet"), since)


def test_edit_in_a_text_include_is_recorded(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("prompt.md", "Be terse.\n")
    theatre.write("troupe.yml", "prompt: file:prompt.md\n")
    start_watch()
    since = _edit(theatre, "prompt.md", "Be kind.\n")
    wait_for_history(theatre, _has("set", "prompt", "Be terse.\n", "Be kind.\n"), since)


def test_comment_and_formatting_edits_record_nothing(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\nb: [x, y]\n")
    start_watch()
    before = recorded(theatre)
    theatre.write("troupe.yml", "# note\na:   1   # one\n\nb:\n  - x\n  - 'y'\n")
    time.sleep(2.5)
    assert recorded(theatre) == before


def test_save_by_rename_is_recorded(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    start_watch()
    since = time.monotonic()
    temp = theatre.write(".troupe.yml.swp", "a: 2\n")
    os.replace(temp, theatre.root / ".troupe" / "troupe.yml")
    wait_for_history(theatre, _has("set", "a", 1, 2), since)


def test_include_added_by_hand_is_followed_and_watched(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    start_watch()
    theatre.write("c.yaml", "k: v\n")
    since = _edit(theatre, "troupe.yml", "a: 1\nc: file:c.yaml\n")
    wait_for_history(theatre, _has("set", "c.k", None, "v"), since)
    since = _edit(theatre, "c.yaml", "k: w\n")
    wait_for_history(theatre, _has("set", "c.k", "v", "w"), since)


def test_removed_include_is_no_longer_watched(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("c.yaml", "k: v\n")
    theatre.write("troupe.yml", "a: 1\nc: file:c.yaml\n")
    start_watch()
    since = _edit(theatre, "troupe.yml", "a: 1\n")
    wait_for_history(theatre, _has("remove", "c.k", "v", None), since)
    before = recorded(theatre)
    theatre.write("c.yaml", "k: w\n")
    time.sleep(2.5)
    assert recorded(theatre) == before


def test_include_outside_the_troupe_directory_is_watched(
    theatre: Theatre, start_watch: Start
) -> None:
    shared = theatre.root / "shared.yaml"
    shared.write_bytes(b"k: 1\n")
    theatre.write("troupe.yml", "s: file:../shared.yaml\n")
    start_watch()
    since = time.monotonic()
    shared.write_bytes(b"k: 2\n")
    wait_for_history(theatre, _has("set", "s.k", 1, 2), since)


def test_never_used_theatre_is_imported_before_the_line(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\nb: 2\n")
    start_watch()
    assert recorded(theatre) == [
        {"seq": 1, "op": "import", "path": "a", "old": None, "new": 1},
        {"seq": 2, "op": "import", "path": "b", "old": None, "new": 2},
    ]


def test_edits_made_before_watch_starts_are_reconciled_at_start(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    theatre.history()
    theatre.write("troupe.yml", "a: 2\n")
    start_watch()
    assert recorded(theatre)[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}]


def test_edit_in_an_include_of_an_include_is_recorded(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("agents/limits.yaml", "retries: 2\n")
    theatre.write("agents/coder.yaml", "model: opus\nlimits: file:limits.yaml\n")
    theatre.write("troupe.yml", "agents:\n  coder: file:agents/coder.yaml\n")
    start_watch()
    since = _edit(theatre, "agents/limits.yaml", "retries: 5\n")
    wait_for_history(theatre, _has("set", "agents.coder.limits.retries", 2, 5), since)
