import pytest

from troupe.config.edit.folded import MoreIndented, rewrite, wrap

OLD = [
    "  The quick brown fox",
    "  jumps over the dog.",
    "",
    "  Second paragraph here",
    "  stays put.",
    "",
    "  Third one.",
]


def test_unchanged_paragraphs_keep_their_bytes() -> None:
    body = "The quick brown fox jumps over the dog.\nSecond paragraph here stays put.\nThird one."
    assert rewrite(OLD, 2, body) == OLD


def test_changed_paragraph_rewrapped_at_its_old_width() -> None:
    body = (
        "The quick brown fox jumps over the lazy sleeping dog.\n"
        "Second paragraph here stays put.\nThird one."
    )
    assert rewrite(OLD, 2, body) == [
        "  The quick brown fox",
        "  jumps over the lazy",
        "  sleeping dog.",
        *OLD[2:],
    ]


def test_new_paragraph_uses_the_blocks_widest_old_line() -> None:
    body = (
        "The quick brown fox jumps over the dog.\nSecond paragraph here stays put.\nThird one.\n"
        "A brand new paragraph that is rather long"
    )
    assert rewrite(OLD, 2, body)[-3:] == ["", "  A brand new paragraph", "  that is rather long"]


def test_removed_paragraph() -> None:
    body = "The quick brown fox jumps over the dog.\nThird one."
    assert rewrite(OLD, 2, body) == [*OLD[:3], "  Third one."]


def test_word_longer_than_width_takes_its_own_line() -> None:
    assert wrap("a bb supercalifragilistic c", 5) == ["a bb", "supercalifragilistic", "c"]


@pytest.mark.parametrize("body", [" leading space", "a\n  b", "two  x"])
def test_more_indented_lines_are_refused(body: str) -> None:
    with pytest.raises(MoreIndented):
        rewrite(["  abc"], 2, body)


def test_double_space_kept_when_the_break_falls_after_it() -> None:
    assert wrap("two  spaces here", 5) == ["two ", "spaces", "here"]
