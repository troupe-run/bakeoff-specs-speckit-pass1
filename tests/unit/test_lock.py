"""The theatre lock (research S-3): one exclusive lock under `.troupe/`."""

import fcntl
import os
from pathlib import Path

import pytest

from troupe.config import commands
from troupe.config.leaves import LeafEvent
from troupe.config.lineage import Actor, Lineage
from troupe.config.lock import LOCK_FILENAME, theatre_lock
from troupe.config.store import ConfigStore
from troupe.errors import LoadError


def _theatre(tmp_path: Path) -> Path:
    (tmp_path / ".troupe").mkdir()
    return tmp_path


def lock_is_free(path: Path) -> bool:
    """Whether another descriptor can take the lock right now."""
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


def test_lock_file_lives_next_to_the_event_store(tmp_path: Path) -> None:
    theatre = _theatre(tmp_path)
    with theatre_lock(theatre):
        assert (theatre / ".troupe" / LOCK_FILENAME).is_file()
    assert LOCK_FILENAME == "events.sqlite3.lock"


def test_lock_is_exclusive_while_held_and_released_after(tmp_path: Path) -> None:
    theatre = _theatre(tmp_path)
    path = theatre / ".troupe" / LOCK_FILENAME
    with theatre_lock(theatre):
        assert not lock_is_free(path)
    assert lock_is_free(path)


def test_read_only_lock_file_can_still_be_locked(tmp_path: Path) -> None:
    theatre = _theatre(tmp_path)
    path = theatre / ".troupe" / LOCK_FILENAME
    path.write_bytes(b"")
    path.chmod(0o444)
    with theatre_lock(theatre):
        assert not lock_is_free(path)


def test_missing_troupe_directory_reports_the_missing_configuration(tmp_path: Path) -> None:
    with pytest.raises(LoadError) as error, theatre_lock(tmp_path):
        pass
    assert str(tmp_path / ".troupe" / "troupe.yml") in error.value.message
    assert not (tmp_path / ".troupe").exists()


def test_unopenable_lock_file_names_it(tmp_path: Path) -> None:
    theatre = _theatre(tmp_path)
    (theatre / ".troupe" / LOCK_FILENAME).mkdir()
    with pytest.raises(LoadError) as error, theatre_lock(theatre):
        pass
    assert str(theatre / ".troupe" / LOCK_FILENAME) in error.value.message


def test_set_records_its_events_with_the_lock_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    theatre = _theatre(tmp_path)
    (theatre / ".troupe" / "troupe.yml").write_bytes(b"a: 1\n")
    commands.history(theatre, None)  # import, so the set below records exactly its own event
    held: list[bool] = []
    original = ConfigStore.record

    def record(self: ConfigStore, events: list[LeafEvent], lineage: Lineage) -> None:
        held.append(not lock_is_free(theatre / ".troupe" / LOCK_FILENAME))
        original(self, events, lineage)

    monkeypatch.setattr(ConfigStore, "record", record)
    commands.set_value(theatre, "a", "2", Actor("human", "t"), None)
    assert held and all(held)
    assert (theatre / ".troupe" / "troupe.yml").read_bytes() == b"a: 2\n"
