import pytest

from troupe.config.paths import ConfigPath, dotted_is_within, is_index
from troupe.errors import UsageError


def test_path_splits_on_dots_and_digit_segments_are_indexes() -> None:
    path = ConfigPath.parse("a.b.0")
    assert path.segments == ("a", "b", "0")
    assert is_index("0") and is_index("12")
    assert not is_index("b") and not is_index("1a") and not is_index("-1") and not is_index("٣")
    assert path.dotted == "a.b.0"


@pytest.mark.parametrize("text", ["", "a..b", ".a", "a."])
def test_empty_segments_are_usage_errors(text: str) -> None:
    with pytest.raises(UsageError):
        ConfigPath.parse(text)


def test_within_means_equal_or_below() -> None:
    assert dotted_is_within("b", "b")
    assert dotted_is_within("b.0", "b")
    assert not dotted_is_within("bb", "b")
    assert not dotted_is_within("a.b", "b")
