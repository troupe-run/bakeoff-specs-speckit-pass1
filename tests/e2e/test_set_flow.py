"""Flow collections: new entries go after the last entry, on its line (FR-034)."""

from tests.conftest import Theatre, assert_set


def test_new_key_in_flow_mapping(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "limits: {cpu: 2}\n"},
        "limits.mem",
        "4",
        {"troupe.yml": "limits: {cpu: 2, mem: 4}\n"},
    )


def test_append_to_flow_sequence(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "tools: [git, shell]\n"},
        "tools.2",
        "lint",
        {"troupe.yml": "tools: [git, shell, lint]\n"},
    )


def test_append_to_multi_line_flow_sequence_on_the_last_entrys_line(theatre: Theatre) -> None:
    files = {"troupe.yml": "tools: [\n  git,\n  shell\n]\n"}
    assert_set(
        theatre, files, "tools.2", "lint", {"troupe.yml": "tools: [\n  git,\n  shell, lint\n]\n"}
    )


def test_append_to_empty_flow_sequence(theatre: Theatre) -> None:
    assert_set(
        theatre, {"troupe.yml": "tools: []\n"}, "tools.0", "lint", {"troupe.yml": "tools: [lint]\n"}
    )


def test_new_key_in_empty_flow_mapping(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "m: {}\n"}, "m.a", "1", {"troupe.yml": "m: {a: 1}\n"})


def test_new_collection_in_flow_parent_is_flow(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "m: {a: 1}\n"},
        "m.b",
        "{c: [x, y]}",
        {"troupe.yml": "m: {a: 1, b: {c: [x, y]}}\n"},
    )


def test_new_multi_line_string_in_flow_parent_is_double_quoted(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "m: {a: 1}\n"},
        "m.b",
        '"x\\ny"',
        {"troupe.yml": 'm: {a: 1, b: "x\\ny"}\n'},
    )


def test_new_string_copies_sibling_style_in_flow(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "t: ['a']\n"}, "t.1", "b", {"troupe.yml": "t: ['a', 'b']\n"})


def test_comment_after_flow_collection_returns_to_its_column(theatre: Theatre) -> None:
    files = {"troupe.yml": "t: [a]       # c\nu: [a]  # d\n"}
    assert_set(theatre, files, "t.1", "b", {"troupe.yml": "t: [a, b]    # c\nu: [a]  # d\n"})
    assert_set(theatre, {}, "u.1", "b", {"troupe.yml": "t: [a, b]    # c\nu: [a, b] # d\n"})


def test_intermediate_mappings_inside_flow_parent(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "m: {a: 1}\n"},
        "m.x.y",
        "2",
        {"troupe.yml": "m: {a: 1, x: {y: 2}}\n"},
    )
