"""New keys (FR-022, FR-027, FR-029, FR-031, FR-033)."""

from tests.conftest import Theatre, assert_set


def test_new_key_goes_below_trailing_comments_but_above_less_indented_ones(
    theatre: Theatre,
) -> None:
    files = {"troupe.yml": "model:\n  name: opus\n  # about name\n# top-level note\ntools: []\n"}
    assert_set(
        theatre,
        files,
        "model.temp",
        "0.5",
        {
            "troupe.yml": (
                "model:\n  name: opus\n  # about name\n  temp: 0.5\n# top-level note\ntools: []\n"
            )
        },
    )


def test_blank_line_before_the_next_section_stays_below(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\n  x: 1\n\nb: 2\n"}
    assert_set(theatre, files, "a.y", "2", {"troupe.yml": "a:\n  x: 1\n  y: 2\n\nb: 2\n"})


def test_new_top_level_key_after_trailing_comments(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1\n# end of file note\n"}
    assert_set(theatre, files, "b", "2", {"troupe.yml": "a: 1\n# end of file note\nb: 2\n"})


def test_key_quoting_copies_the_preceding_sibling_key(theatre: Theatre) -> None:
    files = {"troupe.yml": '"a": 1\n'}
    assert_set(theatre, files, "b", "2", {"troupe.yml": '"a": 1\n"b": 2\n'})


def test_string_value_copies_the_preceding_sibling_value(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 'x'\n"}
    assert_set(theatre, files, "b", "y", {"troupe.yml": "a: 'x'\nb: 'y'\n"})


def test_non_string_value_is_plain_whatever_the_sibling(theatre: Theatre) -> None:
    files = {"troupe.yml": 'a: "x"\n'}
    assert_set(theatre, files, "b", "3", {"troupe.yml": 'a: "x"\nb: 3\n'})


def test_without_sibling_minimal_quoting(theatre: Theatre) -> None:
    files = {"troupe.yml": ""}
    assert_set(theatre, files, "a.b", '"1"', {"troupe.yml": "a:\n  b: '1'\n"})


def test_key_that_needs_quotes(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1\n"}
    assert_set(theatre, files, "weird: key", "1", {"troupe.yml": "a: 1\n'weird: key': 1\n"})


def test_missing_intermediate_mappings_use_the_files_indentation(theatre: Theatre) -> None:
    files = {"troupe.yml": "model:\n    name: opus\n"}
    assert_set(
        theatre,
        files,
        "model.limits.retries",
        "3",
        {"troupe.yml": ("model:\n    name: opus\n    limits:\n        retries: 3\n")},
    )


def test_new_collection_value_in_block_style(theatre: Theatre) -> None:
    files = {"troupe.yml": "model:\n  name: opus\n"}
    assert_set(
        theatre,
        files,
        "model.tools",
        "[a, {b: c}]",
        {"troupe.yml": ("model:\n  name: opus\n  tools:\n    - a\n    - b: c\n")},
    )


def test_new_empty_collection_value(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1\n"}
    assert_set(theatre, files, "b", "{}", {"troupe.yml": "a: 1\nb: {}\n"})


def test_new_multi_line_string_is_a_literal_block(theatre: Theatre) -> None:
    files = {"troupe.yml": "model:\n  name: opus\n"}
    assert_set(
        theatre,
        files,
        "model.prompt",
        '"x\\ny\\n"',
        {"troupe.yml": ("model:\n  name: opus\n  prompt: |\n    x\n    y\n")},
    )


def test_file_without_final_newline(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1"}, "b", "2", {"troupe.yml": "a: 1\nb: 2"})


def test_comment_only_file(theatre: Theatre) -> None:
    files = {"troupe.yml": "# just a comment\n"}
    assert_set(theatre, files, "a", "1", {"troupe.yml": "# just a comment\na: 1\n"})


def test_new_key_under_an_include_becomes_an_override(theatre: Theatre) -> None:
    """Step 1 wrote this key into `coder.yaml`; step 5 CR-A keeps shared files shared."""
    files = {
        "troupe.yml": "agents:\n  coder: file:agents/coder.yaml\n",
        "agents/coder.yaml": "model: sonnet\n",
    }
    assert_set(
        theatre,
        files,
        "agents.coder.retries",
        "3",
        {"troupe.yml": "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    retries: 3\n"},
    )


def test_crlf_file_gets_crlf_lines(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\r\n  b: 1\r\n"}
    assert_set(theatre, files, "a.c.d", "2", {"troupe.yml": "a:\r\n  b: 1\r\n  c:\r\n    d: 2\r\n"})


def test_new_key_after_a_nested_block_and_its_literal(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\n  b:\n    c: |\n      text\n\nz: 1\n"}
    assert_set(
        theatre,
        files,
        "a.d",
        "x",
        {"troupe.yml": "a:\n  b:\n    c: |\n      text\n  d: x\n\nz: 1\n"},
    )


def test_new_key_in_compact_list_item_mapping(theatre: Theatre) -> None:
    files = {"troupe.yml": "l:\n  - a: 1\n    b: 2\n  - z\n"}
    assert_set(
        theatre, files, "l.0.c", "3", {"troupe.yml": "l:\n  - a: 1\n    b: 2\n    c: 3\n  - z\n"}
    )


def test_new_key_after_an_include_entry(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "agents:\n  coder: file:agents/coder.yaml\nnext: 1\n",
        "agents/coder.yaml": "model: x\n",
    }
    assert_set(
        theatre,
        files,
        "agents.reviewer",
        "y",
        {"troupe.yml": ("agents:\n  coder: file:agents/coder.yaml\n  reviewer: y\nnext: 1\n")},
    )


def test_new_key_after_a_keep_chomped_block_goes_below_its_blank_lines(theatre: Theatre) -> None:
    files = {"troupe.yml": "m:\n  a: |+\n    t\n\nn: 1\n"}
    assert_set(theatre, files, "m.b", "2", {"troupe.yml": "m:\n  a: |+\n    t\n\n  b: 2\nn: 1\n"})
    assert theatre.config("show", "m.a").out == "t\n\n"


def test_new_key_after_a_clip_block_stays_above_the_blank_separator(theatre: Theatre) -> None:
    files = {"troupe.yml": "m:\n  a: |\n    t\n\nn: 1\n"}
    assert_set(theatre, files, "m.b", "2", {"troupe.yml": "m:\n  a: |\n    t\n  b: 2\n\nn: 1\n"})
