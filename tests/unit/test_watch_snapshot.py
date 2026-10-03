"""The `watching` line is a promise (spec FR-102, research S-4): an edit made after the files
were parsed, even before the line is printed, is still seen."""

import threading
from pathlib import Path

from troupe.config.loader import Loaded, load
from troupe.config.watch import run_watch


def test_edit_between_parse_and_announce_is_reconciled(tmp_path: Path) -> None:
    (tmp_path / ".troupe").mkdir()
    config = tmp_path / ".troupe" / "troupe.yml"
    config.write_bytes(b"a: 1\n")
    stop = threading.Event()
    syncs: list[Loaded] = []

    def sync() -> Loaded:
        loaded = load(tmp_path)
        if not syncs:
            config.write_bytes(b"a: 2\n")  # lands after the parse, before the snapshot
        else:
            stop.set()
        syncs.append(loaded)
        return loaded

    timer = threading.Timer(3.0, stop.set)
    timer.start()
    try:
        run_watch(tmp_path, sync, lambda: None, stop, lambda message: None)
    finally:
        timer.cancel()
    assert len(syncs) == 2


def test_unchanged_files_are_not_reconciled_again(tmp_path: Path) -> None:
    (tmp_path / ".troupe").mkdir()
    (tmp_path / ".troupe" / "troupe.yml").write_bytes(b"a: 1\n")
    stop = threading.Event()
    calls: list[int] = []

    def sync() -> Loaded:
        calls.append(1)
        return load(tmp_path)

    timer = threading.Timer(1.0, stop.set)
    timer.start()
    run_watch(tmp_path, sync, lambda: None, stop, lambda message: None)
    assert len(calls) == 1
