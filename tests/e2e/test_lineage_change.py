"""What else changed with it: `change` groups each unit's events (spec US2, FR-305, D-30)."""

from typing import Any

from tests.conftest import Theatre, set_ok


def _imported(theatre: Theatre, text: str = "a: 1\nb: [x, y]\n") -> list[dict[str, Any]]:
    theatre.write("troupe.yml", text)
    return theatre.events()


def _changes(events: list[dict[str, Any]]) -> set[str]:
    return {e["change"] for e in events}


def test_import_events_share_one_change(theatre: Theatre) -> None:
    events = _imported(theatre)
    assert len(events) == 3
    (change,) = _changes(events)
    assert isinstance(change, str) and change


def test_one_set_shares_one_change_across_set_and_remove(theatre: Theatre) -> None:
    imported = _imported(theatre)
    set_ok(theatre, "b", "[z]")
    own = theatre.events()[3:]
    assert [(e["op"], e["path"]) for e in own] == [("set", "b.0"), ("remove", "b.1")]
    assert len(_changes(own)) == 1
    assert _changes(own) != _changes(imported)


def test_one_hand_edit_reconcile_shares_one_change(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 2\nb: [w, y]\n")
    assert theatre.config("show").code == 0
    reconciled = theatre.events()[3:]
    assert [e["path"] for e in reconciled] == ["a", "b.0"]
    assert len(_changes(reconciled)) == 1


def test_reconcile_and_set_in_one_invocation_are_separate_changes(theatre: Theatre) -> None:
    _imported(theatre)
    theatre.write("troupe.yml", "a: 2\nb: [x, y]\n")
    set_ok(theatre, "c", "1")
    hand_edit, own = theatre.events()[3:]
    assert (hand_edit["path"], own["path"]) == ("a", "c")
    assert hand_edit["change"] != own["change"]


def test_first_set_on_a_fresh_theatre_separates_import_and_set(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\nb: [x, y]\n")
    set_ok(theatre, "a", "2")
    events = theatre.events()
    imports, own = events[:3], events[3:]
    assert {e["op"] for e in imports} == {"import"} and len(_changes(imports)) == 1
    assert len(own) == 1 and own[0]["change"] not in _changes(imports)


def test_changes_are_distinct_across_many_commands(theatre: Theatre) -> None:
    units: list[list[int]] = [[e["seq"] for e in _imported(theatre)]]
    commands = [("a", str(2 - i % 2)) for i in range(10)] + [("b", "[z, w, v]")]
    for path, value in commands:
        seen = len(theatre.history())
        set_ok(theatre, path, value)
        units.append([e["seq"] for e in theatre.history()[seen:]])
    assert all(units)
    by_change: dict[str, list[int]] = {}
    for event in theatre.events():
        by_change.setdefault(event["change"], []).append(event["seq"])
    assert sorted(by_change.values()) == sorted(units)
    assert len(by_change) == len(units) == 12


def test_filtered_history_keeps_change_values(theatre: Theatre) -> None:
    _imported(theatre)
    set_ok(theatre, "b", "[z]")
    set_ok(theatre, "a", "5")
    everything = theatre.events()
    filtered = theatre.events("b")
    assert filtered and all(line in everything for line in filtered)
    assert len(filtered) < len(everything)


def test_set_that_changes_nothing_leaves_no_change(theatre: Theatre) -> None:
    before = _imported(theatre)
    set_ok(theatre, "a", "1")
    assert theatre.events() == before
