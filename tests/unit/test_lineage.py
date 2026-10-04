"""Lineage values (spec FR-303, FR-305, FR-320 to FR-322; research L-3 to L-6)."""

import getpass
from datetime import UTC, datetime, timedelta, timezone

import pytest

from troupe.config.lineage import (
    UNKNOWN_ACTOR,
    Actor,
    Lineage,
    actor_from_env,
    format_at,
    login_name,
)
from troupe.errors import UsageError

AT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def test_actor_from_env_unset_is_human_with_login_name() -> None:
    assert actor_from_env({}, login=lambda: "dev") == Actor("human", "dev")


def test_actor_from_env_unset_with_unknown_login_has_null_id() -> None:
    assert actor_from_env({}, login=lambda: None) == Actor("human", None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("human:alice", Actor("human", "alice")),
        ("agent:coder-7", Actor("agent", "coder-7")),
        ("agent:team:coder", Actor("agent", "team:coder")),
        ("human: spaced ", Actor("human", " spaced ")),
        ("agent:café", Actor("agent", "café")),
    ],
)
def test_actor_from_env_accepts_human_and_agent(value: str, expected: Actor) -> None:
    assert actor_from_env({"TROUPE_ACTOR": value}, login=lambda: "dev") == expected


@pytest.mark.parametrize(
    "value",
    ["", "human", "human:", "agent:", "Human:alice", "AGENT:x", "robot:x", ":x", "unknown:x"],
)
def test_actor_from_env_rejects_anything_else(value: str) -> None:
    with pytest.raises(UsageError) as caught:
        actor_from_env({"TROUPE_ACTOR": value}, login=lambda: "dev")
    assert caught.value.exit_code == 2
    assert "TROUPE_ACTOR" in caught.value.message
    assert repr(value) in caught.value.message


@pytest.mark.parametrize("failure", [OSError("no login"), KeyError("uid"), ""])
def test_login_name_is_none_when_lookup_fails(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException | str
) -> None:
    def getuser() -> str:
        if isinstance(failure, BaseException):
            raise failure
        return failure

    monkeypatch.setattr(getpass, "getuser", getuser)
    assert login_name() is None


def test_login_name_is_getuser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(getpass, "getuser", lambda: "someone")
    assert login_name() == "someone"


def test_format_at_is_rfc3339_utc_with_z() -> None:
    assert format_at(datetime(2026, 10, 4, 9, 5, 7, 123, tzinfo=UTC)) == (
        "2026-10-04T09:05:07.000123Z"
    )


def test_format_at_converts_other_time_zones_to_utc() -> None:
    moment = datetime(2026, 10, 4, 11, 5, 7, tzinfo=timezone(timedelta(hours=2)))
    assert format_at(moment) == "2026-10-04T09:05:07.000000Z"


def test_begin_gives_fresh_change_and_current_at() -> None:
    before = datetime.now(UTC)
    first = Lineage.begin(UNKNOWN_ACTOR, "file")
    second = Lineage.begin(UNKNOWN_ACTOR, "file")
    after = datetime.now(UTC)
    assert first.change and second.change and first.change != second.change
    for lineage in (first, second):
        at = datetime.strptime(lineage.at, AT_FORMAT).replace(tzinfo=UTC)
        assert before <= at <= after
        assert (lineage.actor, lineage.via, lineage.reason) == (UNKNOWN_ACTOR, "file", None)


def test_begin_keeps_actor_via_and_reason() -> None:
    lineage = Lineage.begin(Actor("agent", "a"), "cli", "why")
    assert (lineage.actor, lineage.via, lineage.reason) == (Actor("agent", "a"), "cli", "why")
