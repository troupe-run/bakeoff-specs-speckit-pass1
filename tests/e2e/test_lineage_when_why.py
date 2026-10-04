"""When and why: `at` and `set --reason` (spec US3, FR-303, FR-304, FR-330, FR-331, D-35, D-36)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import Result, Theatre, set_ok

AT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _imported(theatre: Theatre, text: str = "a: 1\nb: [x, y]\n") -> Theatre:
    theatre.write("troupe.yml", text)
    theatre.events()
    return theatre


def _set(theatre: Theatre, *args: str, env: dict[str, str] | None = None) -> None:
    result = theatre.run("config", "set", *args, env=env)
    assert (result.code, result.out) == (0, ""), result


def test_reason_is_recorded_on_the_sets_events(theatre: Theatre) -> None:
    _set(_imported(theatre), "a", "2", "--reason", "raise for load test")
    assert theatre.events()[-1]["reason"] == "raise for load test"


def test_reason_is_null_without_reason_and_on_import_and_file_events(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 2\nb: [x, y]\n")
    _set(theatre, "a", "3")
    events = theatre.events()
    assert events[-1]["via"] == "cli" and events[-1]["reason"] is None
    assert {e["via"] for e in events[:-1]} == {"import", "file"}
    assert all(e["reason"] is None for e in events)


def test_reason_applies_to_every_event_of_the_set(theatre: Theatre) -> None:
    _set(_imported(theatre), "b", "[z]", "--reason", "trim")
    own = theatre.events()[3:]
    assert [(e["op"], e["reason"]) for e in own] == [("set", "trim"), ("remove", "trim")]


def test_reason_does_not_apply_to_the_reconcile_in_the_same_command(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 2\nb: [x, y]\n")
    _set(theatre, "c", "1", "--reason", "x")
    hand_edit, own = theatre.events()[3:]
    assert (hand_edit["path"], hand_edit["reason"]) == ("a", None)
    assert (own["path"], own["reason"]) == ("c", "x")


@pytest.mark.parametrize(
    "reason",
    ["", "line one\nline two", 'say "hi"', "café 🎭", "--looks-like-an-option"],
    ids=["empty", "newline", "quotes", "non-ascii", "option-like"],
)
def test_reason_text_is_kept_exactly(theatre: Theatre, reason: str) -> None:
    _set(_imported(theatre), "a", "2", f"--reason={reason}")
    raw = theatre.config("history").out.splitlines()[-1]
    assert json.loads(raw)["reason"] == reason


def _bounded(
    theatre: Theatre, command: Callable[[], Result], env_note: str = ""
) -> tuple[datetime, datetime]:
    before = datetime.now(UTC)
    result = command()
    after = datetime.now(UTC)
    assert result.code == 0, (env_note, result)
    return before, after


def _at(event: dict[str, Any]) -> datetime:
    at = event["at"]
    assert isinstance(at, str) and at.endswith("Z")
    return datetime.strptime(at, AT_FORMAT).replace(tzinfo=UTC)


def test_at_is_rfc3339_utc_within_the_command(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    lo, hi = _bounded(theatre, lambda: theatre.config("history"))
    assert lo <= _at(theatre.events()[-1]) <= hi  # import
    theatre.write("troupe.yml", "a: 2\n")
    lo, hi = _bounded(theatre, lambda: theatre.config("get", "a"))
    event = theatre.events()[-1]
    assert event["via"] == "file" and lo <= _at(event) <= hi  # reconcile
    lo, hi = _bounded(theatre, lambda: theatre.config("set", "a", "3"))
    event = theatre.events()[-1]
    assert event["via"] == "cli" and lo <= _at(event) <= hi  # set


def test_at_is_shared_within_a_unit(theatre: Theatre) -> None:
    _imported(theatre)
    set_ok(theatre, "b", "[z]")
    events = theatre.events()
    assert len({e["at"] for e in events[:3]}) == 1
    assert len({e["at"] for e in events[3:]}) == 1


def test_at_is_utc_whatever_the_time_zone(theatre: Theatre) -> None:
    _imported(theatre)
    lo, hi = _bounded(
        theatre,
        lambda: theatre.run("config", "set", "a", "2", env={"TZ": "America/New_York"}),
    )
    assert lo <= _at(theatre.events()[-1]) <= hi
