"""An invalid `TROUPE_ACTOR` is refused by every command before anything happens (spec FR-322,
FR-323, D-31, D-32, SC-303)."""

from collections.abc import Callable

import pytest

from tests.conftest import Theatre, Watcher, assert_failed, recorded
from troupe.config.store import STORE_FILENAME

INVALID = ["", "human", "human:", "agent:", "Human:alice", "robot:x", ":x", "unknown:x"]
SUBCOMMANDS = [("get", "a"), ("show",), ("show", "a"), ("set", "a", "9"), ("history",)]


def _store_exists(theatre: Theatre) -> bool:
    return (theatre.root / ".troupe" / STORE_FILENAME).exists()


@pytest.mark.parametrize("value", INVALID)
@pytest.mark.parametrize("args", SUBCOMMANDS, ids=" ".join)
def test_invalid_troupe_actor_on_a_new_theatre_exits_2_and_records_nothing(
    theatre: Theatre, value: str, args: tuple[str, ...]
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    before = theatre.snapshot()
    result = theatre.run("config", *args, env={"TROUPE_ACTOR": value})
    assert_failed(result, 2, "TROUPE_ACTOR")
    assert theatre.snapshot() == before
    assert not _store_exists(theatre)


@pytest.mark.parametrize("value", INVALID)
@pytest.mark.parametrize("args", SUBCOMMANDS, ids=" ".join)
def test_invalid_troupe_actor_with_a_pending_hand_edit_exits_2_and_records_nothing(
    theatre: Theatre, value: str, args: tuple[str, ...]
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    theatre.history()
    theatre.write("troupe.yml", "a: 2\n")
    before_files = theatre.snapshot()
    before_events = recorded(theatre)
    result = theatre.run("config", *args, env={"TROUPE_ACTOR": value})
    assert_failed(result, 2, "TROUPE_ACTOR")
    assert theatre.snapshot() == before_files
    assert recorded(theatre) == before_events


def test_invalid_troupe_actor_stops_watch(
    theatre: Theatre, start_watch: Callable[..., Watcher]
) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch(env={"TROUPE_ACTOR": "robot:x"})
    assert_failed(watcher.stop(), 2, "TROUPE_ACTOR")
    assert not _store_exists(theatre)
