import math

import pytest

from troupe.config.scalars import Scalar, format_scalar, resolve_plain, scalars_equal


@pytest.mark.parametrize("text", ["null", "Null", "NULL", "~", ""])
def test_core_schema_nulls_resolve_to_none(text: str) -> None:
    assert resolve_plain(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
    ],
)
def test_core_schema_booleans(text: str, expected: bool) -> None:
    assert resolve_plain(text) is expected


@pytest.mark.parametrize("text", ["yes", "no", "on", "off", "y", "n", "tRUE"])
def test_yaml_1_1_booleans_are_strings(text: str) -> None:
    assert resolve_plain(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [("12", 12), ("-3", -3), ("+7", 7), ("0o17", 15), ("0x1F", 31), ("007", 7)],
)
def test_core_schema_integers(text: str, expected: int) -> None:
    value = resolve_plain(text)
    assert type(value) is int
    assert value == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0.2", 0.2), ("1e3", 1000.0), (".5", 0.5), ("-1.5E-2", -0.015), ("1.", 1.0)],
)
def test_core_schema_floats(text: str, expected: float) -> None:
    value = resolve_plain(text)
    assert type(value) is float
    assert value == expected


def test_core_schema_infinities_and_nan() -> None:
    assert resolve_plain(".inf") == math.inf
    assert resolve_plain("-.Inf") == -math.inf
    value = resolve_plain(".NaN")
    assert isinstance(value, float) and math.isnan(value)


@pytest.mark.parametrize("text", ["0x", "1_000", "0b101", "12:30", "1.2.3", "abc", "0o8"])
def test_non_numbers_are_strings(text: str) -> None:
    assert resolve_plain(text) == text


@pytest.mark.parametrize(
    ("value", "printed"),
    [
        ("opus", "opus\n"),
        ("ends\n", "ends\n"),
        ("two\n\n", "two\n\n"),
        ("", "\n"),
        (True, "true\n"),
        (False, "false\n"),
        (None, "null\n"),
        (42, "42\n"),
        (0.2, "0.2\n"),
        (1000.0, "1000.0\n"),
    ],
)
def test_format_scalar(value: Scalar, printed: str) -> None:
    assert format_scalar(value) == printed


def test_scalars_equal_is_type_exact() -> None:
    assert scalars_equal(1, 1)
    assert not scalars_equal(1, 1.0)
    assert not scalars_equal(1, True)
    assert not scalars_equal("1", 1)
    assert scalars_equal(math.nan, math.nan)
    assert scalars_equal([1, {"a": "b"}], [1, {"a": "b"}])
    assert not scalars_equal([1], [1.0])
