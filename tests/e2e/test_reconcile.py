"""Every command except `history` reconciles first (spec US1, FR-110 to FR-122)."""

from typing import Any

import pytest

from tests.conftest import Theatre, assert_failed, set_ok


def _imported(theatre: Theatre, text: str) -> list[dict[str, Any]]:
    """Write the main file and import it (`history` imports but never reconciles)."""
    theatre.write("troupe.yml", text)
    return theatre.history()


def _show(theatre: Theatre, path: str) -> str:
    result = theatre.config("show", path)
    assert result.code == 0, result
    return result.out


def test_show_picks_up_a_hand_edit_and_records_it(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 2\n")
    assert _show(theatre, "a") == "2\n"
    assert theatre.history()[-1] == {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}


@pytest.mark.parametrize(
    "edited",
    [
        "# hand-written\na: 1  # one\nb: [x, y]\n",
        "a:   1\nb: [ x ,  y ]\n",
        "a: 1\nb: ['x', \"y\"]\n",
        "\n\na: 1\n\nb: [x, y]\n\n",
    ],
    ids=["comments", "spacing", "quoting", "blank-lines"],
)
def test_formatting_or_comment_edit_records_nothing(theatre: Theatre, edited: str) -> None:
    _imported(theatre, "a: 1\nb: [x, y]\n")
    before = theatre.config("history").out
    theatre.write("troupe.yml", edited)
    assert _show(theatre, "a") == "1\n"
    assert theatre.config("history").out == before


def test_shortened_list_records_a_remove(theatre: Theatre) -> None:
    _imported(theatre, "b: [x, y]\n")
    theatre.write("troupe.yml", "b: [x]\n")
    assert _show(theatre, "b.0") == "x\n"
    assert theatre.history()[2:] == [
        {"seq": 3, "op": "remove", "path": "b.1", "old": "y", "new": None}
    ]


def test_new_key_records_a_set_from_null(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 1\nc: 3\n")
    _show(theatre, "a")
    assert theatre.history()[1:] == [{"seq": 2, "op": "set", "path": "c", "old": None, "new": 3}]


def test_include_added_by_hand_is_followed(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\n")
    theatre.write("agents/coder.yaml", "model: opus\ntools: [git]\n")
    theatre.write("troupe.yml", 'a: 1\nagents: {coder: "file:agents/coder.yaml"}\n')
    _show(theatre, "a")
    assert theatre.history()[1:] == [
        {"seq": 2, "op": "set", "path": "agents.coder.model", "old": None, "new": "opus"},
        {"seq": 3, "op": "set", "path": "agents.coder.tools.0", "old": None, "new": "git"},
    ]


def test_set_records_pending_hand_edit_before_its_own_event(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\nb: 2\n")
    theatre.write("troupe.yml", "a: 2\nb: 2\n")
    set_ok(theatre, "b", "5")
    assert theatre.history()[2:] == [
        {"seq": 3, "op": "set", "path": "a", "old": 1, "new": 2},
        {"seq": 4, "op": "set", "path": "b", "old": 2, "new": 5},
    ]


def test_history_never_reconciles(theatre: Theatre) -> None:
    imported = _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 2\n")
    assert theatre.history() == imported
    assert theatre.history() == imported
    _show(theatre, "a")
    assert theatre.history()[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}]


def test_a_reconciled_edit_is_recorded_once(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 2\n")
    _show(theatre, "a")
    _show(theatre, "a")
    set_ok(theatre, "a", "2")
    assert len(theatre.history()) == 2


def test_text_include_edit_records_old_and_new_text(theatre: Theatre) -> None:
    theatre.write("prompt.md", "Be terse.\n")
    _imported(theatre, "prompt: file:prompt.md\n")
    theatre.write("prompt.md", "Be kind.\n")
    _show(theatre, "prompt")
    assert theatre.history()[1:] == [
        {"seq": 2, "op": "set", "path": "prompt", "old": "Be terse.\n", "new": "Be kind.\n"}
    ]


def test_swapped_include_target_records_only_differing_leaves(theatre: Theatre) -> None:
    theatre.write("a.yaml", "k: 1\nm: same\n")
    theatre.write("b.yaml", "k: 2\nm: same\n")
    _imported(theatre, "inc: file:a.yaml\n")
    theatre.write("troupe.yml", "inc: file:b.yaml\n")
    _show(theatre, "inc.k")
    assert theatre.history()[2:] == [{"seq": 3, "op": "set", "path": "inc.k", "old": 1, "new": 2}]


# Reconcile versus commands that fail (FR-122).


def test_reconcile_stands_when_show_then_fails_with_5(theatre: Theatre) -> None:
    _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 2\n")
    assert_failed(theatre.config("show", "missing.path"), 5, "missing")
    assert theatre.history()[1:] == [{"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}]


def test_reconcile_stands_when_set_is_refused_with_3(theatre: Theatre) -> None:
    theatre.write("agents/coder.yaml", "model: opus\n")
    _imported(theatre, "a: 1\nagents:\n  coder: file:agents/coder.yaml\n")
    theatre.write("troupe.yml", "a: 2\nagents:\n  coder: file:agents/coder.yaml\n")
    assert_failed(theatre.config("set", "agents.coder", "{a: 1}"), 3, "agents.coder")
    assert theatre.history()[2:] == [{"seq": 3, "op": "set", "path": "a", "old": 1, "new": 2}]


def test_usage_error_records_nothing(theatre: Theatre) -> None:
    imported = _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: 2\n")
    assert_failed(theatre.config("set", "a", "[b"), 2, "[b")
    assert theatre.history() == imported


def test_unloadable_configuration_records_nothing(theatre: Theatre) -> None:
    imported = _imported(theatre, "a: 1\n")
    theatre.write("troupe.yml", "a: [2\n")
    assert_failed(theatre.config("show", "a"), 4, "troupe.yml")
    theatre.write("troupe.yml", "a: 1\n")
    assert theatre.history() == imported


def test_reconcile_changes_no_configuration_file(theatre: Theatre) -> None:
    theatre.write("inc.yaml", "k: 1\n")
    _imported(theatre, "a: 1  # one\ninc: file:inc.yaml\n")
    theatre.write("troupe.yml", "a:   2  # two\ninc: file:inc.yaml\n")
    theatre.write("inc.yaml", "k: 3\n")
    before = theatre.snapshot()
    _show(theatre, "a")
    assert theatre.snapshot() == before


def test_scalar_replaced_by_collections_by_hand(theatre: Theatre) -> None:
    _imported(theatre, "m: plain\n")
    theatre.write("troupe.yml", "m: {k: 1, j: [x]}\n")
    _show(theatre, "m.k")
    assert theatre.history()[1:] == [
        {"seq": 2, "op": "set", "path": "m.k", "old": None, "new": 1},
        {"seq": 3, "op": "set", "path": "m.j.0", "old": None, "new": "x"},
        {"seq": 4, "op": "remove", "path": "m", "old": "plain", "new": None},
    ]


def test_collection_replaced_by_a_scalar_by_hand(theatre: Theatre) -> None:
    _imported(theatre, "m: {k: 1}\n")
    theatre.write("troupe.yml", "m: 3\n")
    _show(theatre, "m")
    assert theatre.history()[1:] == [
        {"seq": 2, "op": "set", "path": "m", "old": None, "new": 3},
        {"seq": 3, "op": "remove", "path": "m.k", "old": 1, "new": None},
    ]
