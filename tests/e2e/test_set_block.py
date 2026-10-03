"""Multi-line strings and block scalars (FR-030)."""

from tests.conftest import Theatre, assert_refused, assert_set

KEYED = "a:\n  notes: short  # keep\n  next: 1\n"


def test_multi_line_string_replacing_plain_becomes_literal_block(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": KEYED},
        "a.notes",
        '"line one\\nline two\\n"',
        {"troupe.yml": "a:\n  notes: |      # keep\n    line one\n    line two\n  next: 1\n"},
    )


def test_without_trailing_newline_uses_strip_chomping(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": KEYED},
        "a.notes",
        '"one\\ntwo"',
        {"troupe.yml": "a:\n  notes: |-     # keep\n    one\n    two\n  next: 1\n"},
    )


def test_two_trailing_newlines_use_keep_chomping(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: x\n"}
    assert_set(theatre, files, "p", '"one\\n\\n"', {"troupe.yml": "p: |+\n  one\n\n"})


def test_quoted_list_item_becomes_literal_block(theatre: Theatre) -> None:
    files = {"troupe.yml": "items:\n- 'x'\n- y\n"}
    assert_set(
        theatre, files, "items.0", '"a\\nb\\n"', {"troupe.yml": "items:\n- |\n  a\n  b\n- y\n"}
    )


def test_literal_block_content_replaced_and_indicator_kept(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |  # c\n  old one\n  old two\n\nq: 1\n"}
    assert_set(
        theatre, files, "p", '"new one\\n"', {"troupe.yml": "p: |  # c\n  new one\n\nq: 1\n"}
    )


def test_strip_chomping_becomes_clip_when_value_ends_with_newline(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |-\n  x\nq: 1\n"}
    assert_set(theatre, files, "p", '"y\\n"', {"troupe.yml": "p: |\n  y\nq: 1\n"})


def test_clip_becomes_strip_for_a_single_line_value(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |\n    x\nq: 1\n"}
    assert_set(theatre, files, "p", "y", {"troupe.yml": "p: |-\n    y\nq: 1\n"})


def test_keep_chomping_kept_when_it_still_yields_the_value(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |+\n  x\n\nq: 1\n"}
    assert_set(theatre, files, "p", '"y\\n"', {"troupe.yml": "p: |+\n  y\nq: 1\n"})


def test_indentation_indicator_added_for_a_leading_space(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: x\n"}
    assert_set(
        theatre, files, "p", '"  indented\\nx\\n"', {"troupe.yml": "p: |2\n    indented\n  x\n"}
    )


def test_string_with_carriage_return_falls_back_to_double_quotes(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: x\n"}
    assert_set(theatre, files, "p", '"a\\r\\nb"', {"troupe.yml": 'p: "a\\r\\nb"\n'})


def test_block_scalar_replaced_by_number(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |\n  text\n  more\nq: 1\n"}
    assert_set(theatre, files, "p", "5", {"troupe.yml": "p: 5\nq: 1\n"})


def test_block_scalar_in_crlf_file(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |\r\n  old\r\nq: 1\r\n"}
    assert_set(
        theatre,
        files,
        "p",
        '"new\\nlines\\n"',
        {"troupe.yml": "p: |\r\n  new\r\n  lines\r\nq: 1\r\n"},
    )


def test_unchanged_lines_of_a_literal_block_are_untouched(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: |\n  same\n  old\n"}
    assert_set(theatre, files, "p", '"same\\nnew\\n"', {"troupe.yml": "p: |\n  same\n  new\n"})


def test_literal_followed_by_less_indented_comment(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\n  p: |\n    x\n# note\nb: 1\n"}
    assert_set(theatre, files, "a.p", '"y\\n"', {"troupe.yml": "a:\n  p: |\n    y\n# note\nb: 1\n"})


def test_refused_change_leaves_files_alone(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: >\n  some text\n"}
    assert_refused(theatre, files, "p", '" leading"', 3, "p")


def test_value_starting_with_a_spaces_only_line_gets_an_indentation_indicator(
    theatre: Theatre,
) -> None:
    files = {"troupe.yml": "k: x\n"}
    assert_set(theatre, files, "k", '"    \\nabc\\n"', {"troupe.yml": "k: |2\n      \n  abc\n"})
