import pytest

from troupe.config.edit.render import (
    DOUBLE,
    PLAIN,
    SINGLE,
    can_plain,
    chomping_for,
    render_block,
    render_double,
    render_flow,
    render_inline,
    render_literal,
)
from troupe.config.scalars import NewNode, NewScalar, parse_value


@pytest.mark.parametrize(
    "text", ["abc", "a b", "a,b", "x-y", "-x", ":x", "a#b", "http://x", "日本"]
)
def test_plain_representable_in_block_context(text: str) -> None:
    assert can_plain(text, in_flow=False)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "0.2",
        "true",
        "null",
        "~",
        "12",
        " a",
        "a ",
        "a: b",
        "a #b",
        "#a",
        "-",
        "- a",
        "[a",
        "{a",
        "x:",
        "'a",
        '"a',
        "&a",
        "*a",
        "!a",
        "|",
        ">",
        "%a",
        "@a",
        "`a",
        "a\nb",
        "a\tb\x07",
    ],
)
def test_not_plain_representable(text: str) -> None:
    assert not can_plain(text, in_flow=False)


@pytest.mark.parametrize("text", ["a,b", "a[b", "a}b"])
def test_flow_indicators_are_not_plain_in_flow_context(text: str) -> None:
    assert not can_plain(text, in_flow=True)


def _inline(
    value: str | int | float | bool | None, style: str | None, spelling: str | None = None
) -> str:
    return render_inline(NewScalar(value, spelling), style, in_flow=False)


def test_style_kept_when_it_can_represent_the_value() -> None:
    assert _inline("reviewer", SINGLE) == "'reviewer'"
    assert _inline("reviewer", DOUBLE) == '"reviewer"'
    assert _inline("reviewer", PLAIN) == "reviewer"


def test_style_fallback_plain_then_single_then_double() -> None:
    assert _inline(3, SINGLE) == "3"
    assert _inline("2", PLAIN) == "'2'"
    assert _inline("it's: x", PLAIN) == "'it''s: x'"
    assert _inline("bell\x07", SINGLE) == '"bell\\a"'
    assert _inline("two\nlines", PLAIN) == '"two\\nlines"'


def test_non_strings_are_plain_in_their_command_line_spelling() -> None:
    assert _inline(1000.0, PLAIN, "1e3") == "1e3"
    assert _inline(0.75, DOUBLE) == "0.75"
    assert _inline(True, SINGLE) == "true"
    assert _inline(None, PLAIN) == "null"


def test_double_quoted_escapes_only_what_yaml_requires() -> None:
    assert render_double('a\\b"c') == '"a\\\\b\\"c"'
    assert render_double("tab\there\n") == '"tab\\there\\n"'
    assert render_double("\x07\x1b\x00\x7f\x85\x9f") == '"\\a\\e\\0\\x7f\\N\\x9f"'
    assert render_double("é 日本 ' 🎭 \u2028") == '"é 日本 \' 🎭 \u2028"'


@pytest.mark.parametrize(
    ("value", "old", "chomp"),
    [
        ("x", "", "-"),
        ("x\n", "", ""),
        ("x\n\n", "", "+"),
        ("x\n", "-", ""),
        ("x\n", "+", "+"),
        ("x", "+", "-"),
        ("\n", "", "+"),
    ],
)
def test_chomping(value: str, old: str, chomp: str) -> None:
    assert chomping_for(value, old) == chomp


def test_literal_block() -> None:
    assert render_literal("a\nb\n", 4, 2) == ("|", ["    a", "    b"])
    assert render_literal("a\n\nb", 2, 2) == ("|-", ["  a", "", "  b"])
    assert render_literal("a\n\n", 2, 2) == ("|+", ["  a", ""])
    assert render_literal("  indented\nx\n", 2, 2) == ("|2", ["    indented", "  x"])


def _node(text: str) -> NewNode:
    return parse_value(text)


def test_block_collections() -> None:
    assert render_block(_node("{a: 1, b: [x, {c: d, e: f}], g: {}}"), 2, 2) == [
        "  a: 1",
        "  b:",
        "    - x",
        "    - c: d",
        "      e: f",
        "  g: {}",
    ]


def test_flow_collections() -> None:
    assert render_flow(_node('{a: 1, b: [x, "y z", "1"], c: "m\\nn"}')) == (
        "{a: 1, b: [x, y z, '1'], c: \"m\\nn\"}"
    )
