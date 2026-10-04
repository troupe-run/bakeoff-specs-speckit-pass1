"""Lineage of events recorded while `watch` runs (spec US1 scenario 6; edge case "set under
watch")."""

import time
from collections.abc import Callable
from typing import Any

from tests.conftest import Theatre, Watcher, recorded, wait_for_history

type Start = Callable[..., Watcher]
UNKNOWN = {"kind": "unknown", "id": None}


def test_watch_hand_edit_has_unknown_actor_via_file(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch(env={"TROUPE_ACTOR": "agent:w"})
    since = time.monotonic()
    theatre.write("troupe.yml", "a: 2\n")

    def has_set(events: list[dict[str, Any]]) -> bool:
        return any(e["op"] == "set" for e in events)

    wait_for_history(theatre, has_set, since)
    assert watcher.stop().code == 0
    event = theatre.events()[-1]
    assert (event["op"], event["actor"], event["via"]) == ("set", UNKNOWN, "file")


def test_set_under_watch_keeps_its_own_lineage(theatre: Theatre, start_watch: Start) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    watcher = start_watch()
    before = len(recorded(theatre))
    result = theatre.run("config", "set", "a", "3", env={"TROUPE_ACTOR": "human:alice"})
    assert result.code == 0, result
    time.sleep(3)
    assert watcher.stop().code == 0
    new = theatre.events()[before:]
    assert len(new) == 1
    assert (new[0]["via"], new[0]["actor"]) == ("cli", {"kind": "human", "id": "alice"})
