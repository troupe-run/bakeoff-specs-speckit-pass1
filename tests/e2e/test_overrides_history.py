"""Overrides in history, reconcile and watch (spec FR-440, FR-441)."""

import time
from collections.abc import Callable

from tests.conftest import Theatre, Watcher, wait_for_history

type Start = Callable[..., Watcher]

SCALAR_FORM = "agents:\n  coder: file:agents/coder.yaml\n"
MAPPING_FORM = "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    model: x\n"


def _changes(theatre: Theatre) -> list[tuple[str, str, object, object]]:
    return [
        (e["op"], e["path"], e["old"], e["new"]) for e in theatre.history() if e["op"] != "import"
    ]


def test_hand_written_override_is_reconciled_as_one_set(theatre: Theatre) -> None:
    theatre.write("agents/coder.yaml", "model: opus\neffort: low\n")
    theatre.write("troupe.yml", SCALAR_FORM)
    theatre.history()
    theatre.write("troupe.yml", MAPPING_FORM)
    assert theatre.config("get", "agents.coder.model").out == "x\n"
    assert _changes(theatre) == [("set", "agents.coder.model", "opus", "x")]


def test_removing_the_override_records_the_included_value_back(theatre: Theatre) -> None:
    theatre.write("agents/coder.yaml", "model: opus\n")
    theatre.write("troupe.yml", MAPPING_FORM)
    theatre.history()
    theatre.write("troupe.yml", SCALAR_FORM)
    assert theatre.config("get", "agents.coder.model").out == "opus\n"
    assert _changes(theatre) == [("set", "agents.coder.model", "x", "opus")]


def test_watch_follows_a_file_reached_only_through_ref(
    theatre: Theatre, start_watch: Start
) -> None:
    theatre.write("agents/coder.yaml", "model: opus\neffort: low\n")
    theatre.write("troupe.yml", MAPPING_FORM)
    start_watch()
    since = time.monotonic()
    theatre.write("agents/coder.yaml", "model: opus\neffort: high\n")
    wait_for_history(
        theatre,
        lambda events: any(
            (e["op"], e["path"], e["new"]) == ("set", "agents.coder.effort", "high") for e in events
        ),
        since,
    )
