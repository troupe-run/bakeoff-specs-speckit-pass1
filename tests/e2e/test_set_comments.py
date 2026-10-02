"""End-of-line comments stay at their column when a value's length changes (FR-036)."""

from tests.conftest import Theatre, assert_set


def test_shrinking_value_keeps_comment_column(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 0.2000   # creative\nb: 1  # other\n"}
    assert_set(
        theatre, files, "a", "0.5", {"troupe.yml": "a: 0.5      # creative\nb: 1  # other\n"}
    )


def test_growing_value_keeps_comment_column(theatre: Theatre) -> None:
    files = {"troupe.yml": "  \nmodel:\n  temperature: 0.2   # creative\n"}
    assert_set(
        theatre,
        files,
        "model.temperature",
        "0.75",
        {"troupe.yml": "  \nmodel:\n  temperature: 0.75  # creative\n"},
    )


def test_value_reaching_the_column_gets_exactly_one_space(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1  # c\n"}
    assert_set(theatre, files, "a", "123456789", {"troupe.yml": "a: 123456789 # c\n"})


def test_columns_count_code_points(theatre: Theatre) -> None:
    files = {"troupe.yml": "name: 日本語   # jp\n"}
    assert_set(theatre, files, "name", "ab", {"troupe.yml": "name: ab    # jp\n"})


def test_hash_inside_a_quoted_value_is_not_a_comment(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 'x # y'   # real\n"}
    assert_set(theatre, files, "a", "z", {"troupe.yml": "a: 'z'       # real\n"})


def test_comment_after_flow_collection(theatre: Theatre) -> None:
    files = {"troupe.yml": "t: [a, b]     # tools\n"}
    assert_set(theatre, files, "t.0", "abc", {"troupe.yml": "t: [abc, b]   # tools\n"})


def test_other_comment_lines_untouched(theatre: Theatre) -> None:
    files = {"troupe.yml": "# head\na: 1 # c\n  # indented note\nb: 2\n"}
    assert_set(
        theatre, files, "a", "3", {"troupe.yml": "# head\na: 3 # c\n  # indented note\nb: 2\n"}
    )
