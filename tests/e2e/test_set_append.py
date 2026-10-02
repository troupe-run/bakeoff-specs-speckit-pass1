"""Appending to block lists (FR-023, FR-033)."""

from tests.conftest import Theatre, assert_refused, assert_set

TOOLS = "tools:\n  - git\n  - shell\n  # more later\nother: 1\n"


def test_append_goes_below_trailing_comment(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": TOOLS},
        "tools.2",
        "lint",
        {"troupe.yml": "tools:\n  - git\n  - shell\n  # more later\n  - lint\nother: 1\n"},
    )


def test_index_beyond_length_is_refused_with_exit_5(theatre: Theatre) -> None:
    assert_refused(theatre, {"troupe.yml": TOOLS}, "tools.3", "lint", 5, "tools.3")


def test_append_mapping_uses_compact_form(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": TOOLS},
        "tools.2",
        "{name: lint, args: [x]}",
        {
            "troupe.yml": (
                "tools:\n  - git\n  - shell\n  # more later\n"
                "  - name: lint\n    args:\n      - x\nother: 1\n"
            )
        },
    )


def test_append_in_an_included_file(theatre: Theatre) -> None:
    files = {"troupe.yml": "tools: file:tools.yaml\n", "tools.yaml": "- git\n"}
    assert_set(theatre, files, "tools.1", "hg", {"tools.yaml": "- git\n- hg\n"})


def test_append_copies_sibling_quoting(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "l:\n  - 'a'\n"},
        "l.1",
        "b",
        {"troupe.yml": "l:\n  - 'a'\n  - 'b'\n"},
    )


def test_append_to_unindented_list(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "tools:\n- git\nnext: 1\n"},
        "tools.1",
        "hg",
        {"troupe.yml": "tools:\n- git\n- hg\nnext: 1\n"},
    )


def test_append_multi_line_string(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "l:\n  - a\n"},
        "l.1",
        '"x\\ny\\n"',
        {"troupe.yml": "l:\n  - a\n  - |\n    x\n    y\n"},
    )


def test_append_after_a_keep_chomped_item_goes_below_its_blank_lines(theatre: Theatre) -> None:
    files = {"troupe.yml": "l:\n  - >+\n    t\n\nz: 1\n"}
    assert_set(theatre, files, "l.1", "x", {"troupe.yml": "l:\n  - >+\n    t\n\n  - x\nz: 1\n"})
