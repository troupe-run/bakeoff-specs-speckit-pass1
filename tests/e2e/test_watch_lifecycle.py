"""`config watch` start, stop, output and broken files (spec FR-100, FR-105, FR-106, D-11)."""

import signal
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import Theatre, Watcher, assert_failed, recorded, wait_for_history

type Start = Callable[..., Watcher]


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_signal_stops_watch_with_exit_0(theatre: Theatre, start_watch: Start, sig: int) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    result = start_watch().stop(sig)
    assert result.code == 0, result
    assert result.out == f"watching {theatre.root}\n"
    assert result.err == ""


def test_signal_after_reconciling_still_exits_0_with_one_line(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    since = time.monotonic()
    theatre.write("troupe.yml", "a: 2\n")
    wait_for_history(theatre, lambda events: len(events) == 2, since)
    result = watcher.stop(signal.SIGTERM)
    assert (result.code, result.out, result.err) == (0, f"watching {theatre.root}\n", "")


@pytest.mark.parametrize(
    ("files", "mention"),
    [({"troupe.yml": "a: [1\n"}, "troupe.yml"), ({}, "troupe.yml")],
    ids=["syntax-error", "no-config"],
)
def test_unloadable_at_start_exits_4_without_the_line(
    theatre: Theatre, start_watch: Start, files: dict[str, str], mention: str
) -> None:
    for name, content in files.items():
        theatre.write(name, content)
    watcher = start_watch()
    result = watcher.stop()
    assert_failed(result, 4, mention)


def _error_lines(watcher: Watcher) -> list[str]:
    return [line for line in watcher.err.splitlines() if line.startswith("troupe: error:")]


def test_broken_file_while_watching_is_reported_once_and_survived(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    before = recorded(theatre)
    theatre.write("troupe.yml", "a: [1\n")
    deadline = time.monotonic() + 2.0
    while not _error_lines(watcher) and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(1.0)
    lines = _error_lines(watcher)
    assert len(lines) == 1, watcher.err
    assert "troupe.yml" in lines[0]
    assert watcher.running()
    assert recorded(theatre) == before
    since = time.monotonic()
    theatre.write("troupe.yml", "a: 3\n")
    wait_for_history(theatre, lambda events: events[-1]["new"] == 3, since)
    assert recorded(theatre)[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 3}]
    assert watcher.out == f"watching {theatre.root}\n"


def test_missing_include_target_is_picked_up_once_created(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    theatre.write("troupe.yml", "a: 1\nc: file:c.yaml\n")
    time.sleep(1.0)
    assert "c.yaml" in watcher.err
    since = time.monotonic()
    theatre.write("c.yaml", "k: v\n")
    wait_for_history(theatre, lambda events: events[-1]["path"] == "c.k", since)


def test_positional_argument_is_a_usage_error(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    result = start_watch("extra").stop()
    assert result.code == 2, result
    assert result.out == ""


def test_line_names_the_theatre_from_the_environment(
    theatre: Theatre, start_watch: Start, tmp_path: Path
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch(theatre_arg=False, cwd=tmp_path, env={"TROUPE_THEATRE": "theatre"})
    assert watcher.out == "watching theatre\n"


def test_line_names_the_absolute_current_directory_by_default(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch(theatre_arg=False, cwd=theatre.root)
    assert watcher.out == f"watching {theatre.root}\n"


def test_line_names_a_relative_theatre_as_given(
    theatre: Theatre, start_watch: Start, tmp_path: Path
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch("--theatre", "theatre", theatre_arg=False, cwd=tmp_path)
    assert watcher.out == "watching theatre\n"


def test_main_file_deleted_then_recreated(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    before = recorded(theatre)
    (theatre.root / ".troupe" / "troupe.yml").unlink()
    deadline = time.monotonic() + 2.0
    while not _error_lines(watcher) and time.monotonic() < deadline:
        time.sleep(0.02)
    lines = _error_lines(watcher)
    assert len(lines) == 1, watcher.err
    assert "troupe.yml" in lines[0]
    assert watcher.running()
    assert recorded(theatre) == before
    since = time.monotonic()
    theatre.write("troupe.yml", "a: 2\n")
    wait_for_history(theatre, lambda events: len(events) == 2, since)
    assert recorded(theatre)[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}]
