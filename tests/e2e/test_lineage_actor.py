"""Who changed it, and how: `actor` and `via` (spec US1, FR-302, FR-310, FR-311, FR-320, FR-321)."""

import os
import pwd

import pytest

from tests.conftest import Theatre

UNKNOWN = {"kind": "unknown", "id": None}


def _imported(theatre: Theatre, text: str = "a: 1\nb: [x, y]\n") -> Theatre:
    theatre.write("troupe.yml", text)
    theatre.events()
    return theatre


def test_import_events_have_unknown_actor_via_import(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\nb: [x, y]\n")
    events = theatre.events(env={"TROUPE_ACTOR": "agent:coder-7"})
    assert len(events) == 3
    for event in events:
        assert (event["actor"], event["via"]) == (UNKNOWN, "import")


@pytest.mark.parametrize(
    ("value", "actor"),
    [
        ("agent:coder-7", {"kind": "agent", "id": "coder-7"}),
        ("human:alice", {"kind": "human", "id": "alice"}),
        ("agent:team:coder", {"kind": "agent", "id": "team:coder"}),
        ("human:Zoë Q", {"kind": "human", "id": "Zoë Q"}),
    ],
)
def test_set_events_have_the_cli_actor(theatre: Theatre, value: str, actor: dict[str, str]) -> None:
    _imported(theatre)
    result = theatre.run("config", "set", "a", "2", env={"TROUPE_ACTOR": value})
    assert result.code == 0, result
    event = theatre.events()[-1]
    assert (event["path"], event["actor"], event["via"]) == ("a", actor, "cli")


def test_set_without_troupe_actor_uses_the_login_name(theatre: Theatre) -> None:
    _imported(theatre)
    assert theatre.run("config", "set", "a", "2", env={"LOGNAME": "dev"}).code == 0
    assert theatre.events()[-1]["actor"] == {"kind": "human", "id": "dev"}


def test_set_without_any_login_name_has_null_id(theatre: Theatre) -> None:
    """Environment-dependent: with every login variable removed, the login name comes from the
    password database, so this end-to-end path only exists for a uid without an entry. The
    fallback itself is covered by tests/unit/test_lineage.py (research L-6, spec D-34)."""
    try:
        pwd.getpwuid(os.getuid())
    except KeyError:
        pass
    else:
        pytest.skip("uid has a passwd entry; covered by tests/unit/test_lineage.py")
    _imported(theatre)
    drop = ("LOGNAME", "USER", "LNAME", "USERNAME")
    assert theatre.run("config", "set", "a", "2", drop=drop).code == 0
    assert theatre.events()[-1]["actor"] == {"kind": "human", "id": None}


def test_hand_edit_reconciled_by_a_command_has_unknown_actor_via_file(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 5\nb: [x, y]\n")
    result = theatre.run("config", "get", "a", env={"TROUPE_ACTOR": "agent:coder-7"})
    assert (result.code, result.out) == (0, "5\n")
    event = theatre.events()[-1]
    assert (event["path"], event["actor"], event["via"]) == ("a", UNKNOWN, "file")


def test_reconcile_then_set_in_one_command_have_their_own_via(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 5\nb: [x, y]\n")
    result = theatre.run("config", "set", "c", "5", env={"TROUPE_ACTOR": "human:alice"})
    assert result.code == 0, result
    hand_edit, own = theatre.events()[-2:]
    assert (hand_edit["path"], hand_edit["actor"], hand_edit["via"]) == ("a", UNKNOWN, "file")
    assert (own["path"], own["actor"], own["via"]) == (
        "c",
        {"kind": "human", "id": "alice"},
        "cli",
    )
