import pytest

from troupe.config.scalars import NewScalar, parse_value, plain_value
from troupe.config.scalars import Value as V
from troupe.errors import UsageError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.2", 0.2),
        ("true", True),
        ("null", None),
        ("abc", "abc"),
        ('"0.2"', "0.2"),
        ("{a: 1}", {"a": 1}),
        ("[a, b]", ["a", "b"]),
        ('"line one\\nline two\\n"', "line one\nline two\n"),
        ("'it''s'", "it's"),
        ("yes", "yes"),
        ("[]", []),
        ("{}", {}),
        ("{a: [1, {b: c}]}", {"a": [1, {"b": "c"}]}),
    ],
)
def test_value_parses_as_one_yaml_1_2_flow_node(text: str, expected: V) -> None:
    value = plain_value(parse_value(text))
    assert value == expected
    assert type(value) is type(expected)


def test_plain_scalars_keep_their_spelling() -> None:
    assert parse_value("1e3") == NewScalar(1000.0, "1e3")
    assert parse_value('"x"') == NewScalar("x", None)


@pytest.mark.parametrize("text", ["[a", "", "a: b", "- x", "|\n  x\n", "{a: 1", "a\n---\nb"])
def test_values_that_are_not_one_flow_node_are_usage_errors(text: str) -> None:
    with pytest.raises(UsageError):
        parse_value(text)
