"""A `set` while `watch` runs records exactly its own events; every change is recorded once
(spec US3, FR-130, FR-131)."""

import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.conftest import Theatre, Watcher, recorded, set_ok, wait_for_history
from troupe.config.lock import theatre_lock

type Start = Callable[..., Watcher]

SETTLE = 3.0  # longer than the contract's 2 s: anything watch would record has been recorded


def _added_by(theatre: Theatre, action: Callable[[], None]) -> list[dict[str, Any]]:
    before = len(recorded(theatre))
    action()
    time.sleep(SETTLE)
    return recorded(theatre)[before:]


def test_set_under_watch_records_one_event(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    start_watch()
    assert _added_by(theatre, lambda: set_ok(theatre, "a", "2")) == [
        {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}
    ]


def test_set_replacing_a_list_under_watch(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "b: [x, y]\n")
    start_watch()
    assert _added_by(theatre, lambda: set_ok(theatre, "b", "[z]")) == [
        {"seq": 3, "op": "set", "path": "b.0", "old": "x", "new": "z"},
        {"seq": 4, "op": "remove", "path": "b.1", "old": "y", "new": None},
    ]


def test_set_of_a_text_include_under_watch(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("prompt.md", "Be terse.\n")
    theatre.write("troupe.yml", "prompt: file:prompt.md\n")
    start_watch()
    assert _added_by(theatre, lambda: set_ok(theatre, "prompt", '"Be kind.\\n"')) == [
        {"seq": 2, "op": "set", "path": "prompt", "old": "Be terse.\n", "new": "Be kind.\n"}
    ]


FILES = {
    "troupe.yml": "a: 1\nb: [x, y]\ntools:\n  - git\nm: plain\nprompt: file:prompt.md\n",
    "prompt.md": "Be terse.\n",
}
SETS = [
    ("a", "2"),
    ("a", "3"),
    ("n", "1"),
    ("tools.1", "lint"),
    ("b", "[z]"),
    ("prompt", '"New prompt\\n"'),
    ("m", "{k: 1}"),
    ("a", "3"),  # changes nothing
    ("m.k", "2"),
    ("c.d", "x"),
    ("tools.0", "hg"),
]


def test_many_sets_under_watch_match_the_same_sets_without(
    theatre: Theatre, start_watch: Start, tmp_path: Path
) -> None:
    unwatched = Theatre(tmp_path / "unwatched")
    for target in (theatre, unwatched):
        for name, content in FILES.items():
            target.write(name, content)
    start_watch()
    for path, value in SETS:
        set_ok(theatre, path, value)
        set_ok(unwatched, path, value)
    time.sleep(SETTLE)
    history = theatre.history()
    assert history == unwatched.history()
    assert [e["seq"] for e in history] == list(range(1, len(history) + 1))
    assert len(history) > len(SETS)


def test_hand_edit_then_set_records_each_change_once(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\nc: 0\n")
    start_watch()

    def edit_then_set() -> None:
        theatre.write("troupe.yml", "a: 2\nc: 0\n")
        set_ok(theatre, "c", "1")

    added = _added_by(theatre, edit_then_set)
    assert sorted((e["path"], e["old"], e["new"]) for e in added) == [("a", 1, 2), ("c", 0, 1)]
    assert [e["seq"] for e in added] == [3, 4]


def test_watch_waits_for_the_theatre_lock(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    start_watch()
    with theatre_lock(theatre.root):
        theatre.write("troupe.yml", "a: 2\n")
        time.sleep(1.0)
        assert len(recorded(theatre)) == 1
        since = time.monotonic()
    events = wait_for_history(theatre, lambda events: len(events) == 2, since)
    time.sleep(1.0)
    assert recorded(theatre) == events
    assert events[1] == {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}


def test_signal_during_a_reconcile_lets_it_finish(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    with theatre_lock(theatre.root):
        theatre.write("troupe.yml", "a: 2\n")
        time.sleep(0.5)  # watch has seen the change and is waiting for the lock to reconcile
        watcher.process.send_signal(signal.SIGTERM)
        time.sleep(0.5)
        assert watcher.running()
        assert len(recorded(theatre)) == 1
    result = watcher.stop()
    assert (result.code, result.out, result.err) == (0, f"watching {theatre.root}\n", "")
    assert recorded(theatre)[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}]
