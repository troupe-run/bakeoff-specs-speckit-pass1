"""`history [PATH]`: events as JSON Lines, oldest first (FR-040 to FR-044)."""

import json

from tests.conftest import Theatre, set_ok

MAIN = "a: 1\nb: [x, y]\nbb: z\nc:\n  d: file:inc.yaml\ne: file:e.md\n"


def _ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("inc.yaml", "k: v\n")
    theatre.write("e.md", "text\n")
    return theatre


IMPORTS = [
    {"seq": 1, "op": "import", "path": "a", "old": None, "new": 1},
    {"seq": 2, "op": "import", "path": "b.0", "old": None, "new": "x"},
    {"seq": 3, "op": "import", "path": "b.1", "old": None, "new": "y"},
    {"seq": 4, "op": "import", "path": "bb", "old": None, "new": "z"},
    {"seq": 5, "op": "import", "path": "c.d.k", "old": None, "new": "v"},
    {"seq": 6, "op": "import", "path": "e", "old": None, "new": "text\n"},
]


def test_first_history_imports_one_event_per_leaf_in_document_order(theatre: Theatre) -> None:
    assert _ready(theatre).history() == IMPORTS


def test_output_is_json_lines_with_keys_in_order(theatre: Theatre) -> None:
    result = _ready(theatre).config("history")
    lines = result.out.splitlines()
    assert result.out.endswith("\n") and len(lines) == 6
    assert list(json.loads(lines[0])) == ["seq", "op", "path", "old", "new"]


def test_history_does_not_import_twice(theatre: Theatre) -> None:
    _ready(theatre)
    assert theatre.history() == IMPORTS
    assert theatre.history() == IMPORTS


def test_set_appends_a_set_event(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "a", "2")
    assert theatre.history()[6:] == [{"seq": 7, "op": "set", "path": "a", "old": 1, "new": 2}]


def test_shrinking_a_list_emits_set_then_remove(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "b", "[z]")
    assert theatre.history()[6:] == [
        {"seq": 7, "op": "set", "path": "b.0", "old": "x", "new": "z"},
        {"seq": 8, "op": "remove", "path": "b.1", "old": "y", "new": None},
    ]


def test_scalar_to_mapping_emits_set_for_new_leaves_and_remove_for_the_old(
    theatre: Theatre,
) -> None:
    set_ok(_ready(theatre), "a", "{p: 1, q: 2}")
    assert [(e["op"], e["path"], e["old"], e["new"]) for e in theatre.history()[6:]] == [
        ("set", "a.p", None, 1),
        ("set", "a.q", None, 2),
        ("remove", "a", 1, None),
    ]


def test_mapping_to_scalar_emits_removes(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "m:\n  a: 1\n  b: 2\n")
    set_ok(theatre, "m", "off")
    assert [(e["op"], e["path"]) for e in theatre.history()[2:]] == [
        ("set", "m"),
        ("remove", "m.a"),
        ("remove", "m.b"),
    ]


def test_text_include_change_is_a_set_of_the_string(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "e", '"new\\n"')
    assert theatre.history()[6:] == [
        {"seq": 7, "op": "set", "path": "e", "old": "text\n", "new": "new\n"}
    ]


def test_noop_and_failed_sets_emit_nothing(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "a", "1")
    assert theatre.config("set", "b.9", "x").code == 5
    assert theatre.config("set", "c.d", "x").code == 3
    assert theatre.history() == IMPORTS


def test_filter_by_path_prefix(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "b.1", "w")
    assert [e["path"] for e in theatre.history("b")] == ["b.0", "b.1", "b.1"]
    assert [e["path"] for e in theatre.history("b.1")] == ["b.1", "b.1"]
    assert [e["path"] for e in theatre.history("c")] == ["c.d.k"]


def test_filter_for_a_path_that_never_existed_prints_nothing(theatre: Theatre) -> None:
    result = _ready(theatre).config("history", "nope")
    assert (result.code, result.out) == (0, "")


def test_hand_edits_are_not_reconciled(theatre: Theatre) -> None:
    _ready(theatre).history()
    theatre.write("troupe.yml", MAIN.replace("a: 1", "a: 5"))
    assert theatre.history() == IMPORTS
    set_ok(theatre, "a", "6")
    assert theatre.history()[6:] == [{"seq": 7, "op": "set", "path": "a", "old": 5, "new": 6}]


def test_seq_stays_contiguous_over_many_sets(theatre: Theatre) -> None:
    _ready(theatre)
    for value in range(2, 12):
        set_ok(theatre, "a", str(value))
    seqs = [e["seq"] for e in theatre.history()]
    assert seqs == list(range(1, 17))


def test_non_ascii_strings_are_written_literally(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "name: café 🎭\n")
    assert theatre.config("history").out == (
        '{"seq": 1, "op": "import", "path": "name", "old": null, "new": "café 🎭"}\n'
    )


def test_first_set_imports_before_its_own_event(theatre: Theatre) -> None:
    set_ok(_ready(theatre), "a", "2")
    events = theatre.history()
    assert events[:6] == IMPORTS
    assert events[6]["op"] == "set"
