"""Lineage survives restarts and never changes once recorded (spec US4, FR-306, SC-304)."""

import json

from tests.conftest import Theatre
from troupe.config.store import ConfigStore


def _set(theatre: Theatre, *args: str, actor: str) -> None:
    result = theatre.run("config", "set", *args, env={"TROUPE_ACTOR": actor})
    assert result.code == 0, result


def _history(theatre: Theatre, env: dict[str, str] | None = None) -> str:
    result = theatre.run("config", "history", env=env)
    assert result.code == 0, result
    return result.out


def test_lineage_is_identical_in_later_processes_whatever_their_actor(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\nb: [x, y]\n")
    _history(theatre)  # import
    _set(theatre, "a", "2", "--reason", "r1", actor="agent:a")
    theatre.write("troupe.yml", "a: 2\nb: [w, y]\n")
    assert theatre.config("show").code == 0  # reconcile
    _set(theatre, "b", "[z]", actor="human:b")
    earlier = _history(theatre)

    assert _history(theatre) == earlier
    other = _history(theatre, env={"TROUPE_ACTOR": "human:other", "LOGNAME": "someone-else"})
    assert other == earlier
    _set(theatre, "a", "3", actor="agent:c")
    later = _history(theatre)
    assert later.startswith(earlier) and later != earlier


def test_lineage_is_read_from_the_store(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    _set(theatre, "a", "2", "--reason", "r1", actor="agent:a")
    lines = [json.loads(line) for line in _history(theatre).splitlines()]
    records = ConfigStore(theatre.root).history()
    assert len(records) == len(lines) == 2
    for record, line in zip(records, lines, strict=True):
        lineage = record.lineage
        assert line["actor"] == {"kind": lineage.actor.kind, "id": lineage.actor.id}
        assert (line["via"], line["at"], line["reason"], line["change"]) == (
            lineage.via,
            lineage.at,
            lineage.reason,
            lineage.change,
        )
    assert records[1].lineage.actor.id == "a"
