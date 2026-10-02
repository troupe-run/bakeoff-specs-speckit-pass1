"""Replacing scalars with collections and back (FR-035, research B-3 to B-5)."""

from tests.conftest import Theatre, assert_set


def test_scalar_to_mapping_keeps_key_line_and_comment(theatre: Theatre) -> None:
    files = {"troupe.yml": "model: default  # pick one\nnext: 1\n"}
    assert_set(
        theatre,
        files,
        "model",
        "{name: x}",
        {"troupe.yml": "model:          # pick one\n  name: x\nnext: 1\n"},
    )


def test_scalar_to_list(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": "tools: none\n"},
        "tools",
        "[a, b]",
        {"troupe.yml": "tools:\n  - a\n  - b\n"},
    )


def test_block_mapping_to_scalar_keeps_trailing_comment_lines(theatre: Theatre) -> None:
    files = {"troupe.yml": "model:\n  name: x\n  # trailing about model\nnext: 1\n"}
    assert_set(
        theatre,
        files,
        "model",
        "off",
        {"troupe.yml": "model: off\n  # trailing about model\nnext: 1\n"},
    )


def test_list_to_list(theatre: Theatre) -> None:
    files = {"troupe.yml": "tools:\n  - a  # first\n  - b\nnext: 1\n"}
    assert_set(theatre, files, "tools", "[c]", {"troupe.yml": "tools:\n  - c\nnext: 1\n"})


def test_flow_to_flow_in_place(theatre: Theatre) -> None:
    files = {"troupe.yml": "tools: [a, b]  # c\n"}
    assert_set(theatre, files, "tools", "[x]", {"troupe.yml": "tools: [x]     # c\n"})


def test_compact_list_item_mapping_replaced(theatre: Theatre) -> None:
    files = {"troupe.yml": "l:\n  - a: 1\n    b: 2\n  - z\n"}
    assert_set(theatre, files, "l.0", "{c: 3}", {"troupe.yml": "l:\n  - c: 3\n  - z\n"})


def test_block_mapping_to_empty_mapping(theatre: Theatre) -> None:
    files = {"troupe.yml": "m:\n  a: 1\nn: 2\n"}
    assert_set(theatre, files, "m", "{}", {"troupe.yml": "m: {}\nn: 2\n"})


def test_list_item_scalar_to_mapping_compact(theatre: Theatre) -> None:
    files = {"troupe.yml": "l:\n  - x  # c\n"}
    assert_set(
        theatre, files, "l.0", "{a: 1, b: 2}", {"troupe.yml": "l:\n  - a: 1 # c\n    b: 2\n"}
    )


def test_mapping_to_multi_line_string(theatre: Theatre) -> None:
    files = {"troupe.yml": "m:\n  a: 1\nn: 2\n"}
    assert_set(theatre, files, "m", '"x\\ny\\n"', {"troupe.yml": "m: |\n  x\n  y\nn: 2\n"})
