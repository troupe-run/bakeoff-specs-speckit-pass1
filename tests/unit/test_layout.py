from typing import Any

from ruamel.yaml import YAML

from troupe.config.edit.layout import (
    Lines,
    find_comment,
    indent_step,
    inline_replace,
    insertion_line,
    scalar_spans,
)


def _compose(text: str) -> Any:
    return YAML(typ="rt").compose(text)


def _replace(text: str, old: str, new: str) -> str:
    start = text.index(old)
    lines = Lines(text)
    s, e, r = inline_replace(lines, start, start + len(old), new, scalar_spans(_compose(text)))
    return text[:s] + r + text[e:]


def test_comment_found_only_outside_scalars() -> None:
    text = 'a: "x # y"  # c\n'
    lines = Lines(text)
    assert find_comment(lines, 0, 0, scalar_spans(_compose(text))) == text.rindex("#")


def test_comment_keeps_its_column_when_the_value_shrinks_or_grows() -> None:
    assert _replace("a: 0.2000   # c\n", "0.2000", "0.2") == "a: 0.2      # c\n"
    assert _replace("a: 1        # c\n", "1", "12345") == "a: 12345    # c\n"


def test_exactly_one_space_when_the_value_reaches_the_comment() -> None:
    assert _replace("a: 1  # c\n", "1", "123456789") == "a: 123456789 # c\n"


def test_columns_count_code_points() -> None:
    assert _replace("n: 日本  # c\nm: 1\n", "日本", "x") == "n: x   # c\nm: 1\n"


def test_no_comment_means_plain_replacement() -> None:
    assert _replace("a: 1\n", "1", "22") == "a: 22\n"


def test_indent_step_detection() -> None:
    def step(text: str) -> int:
        return indent_step(_compose(text), Lines(text))

    assert step("a:\n    b: 1\n") == 4
    assert step("a:\n  b:\n    c: 1\n") == 2
    assert step("a: 1\n") == 2
    assert step("a:\n- x\nb:\n   - y\n") == 3


def test_insertion_goes_below_trailing_comments_but_stops_at_less_indented_ones() -> None:
    text = "a:\n  b: 1\n  # about b\n\n  # more\n# top-level note\nc: 2\n"
    assert insertion_line(Lines(text), 1, 2) == 4
    text = "a:\n  b: 1\n\nc: 2\n"
    assert insertion_line(Lines(text), 1, 2) == 1
