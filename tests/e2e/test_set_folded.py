"""Folded (`>`) values: unchanged paragraphs keep their bytes; changed ones re-wrap (FR-032)."""

from tests.conftest import Theatre, assert_refused, assert_set

DOC = """\
doc: >
  The quick brown fox
  jumps over the dog.

  Second paragraph here
  stays put.
next: 1
"""
P1 = "The quick brown fox jumps over the dog."
P2 = "Second paragraph here stays put."


def _value(*paragraphs: str, end: str = "\\n") -> str:
    return '"' + "\\n".join(paragraphs) + end + '"'


def test_changed_paragraph_rewrapped_at_its_old_width(theatre: Theatre) -> None:
    new = "The quick brown fox jumps over the lazy sleeping dog."
    expected = DOC.replace("  jumps over the dog.\n", "  jumps over the lazy\n  sleeping dog.\n")
    assert_set(theatre, {"troupe.yml": DOC}, "doc", _value(new, P2), {"troupe.yml": expected})


def test_second_paragraph_changed_first_keeps_bytes(theatre: Theatre) -> None:
    expected = DOC.replace("  Second paragraph here\n  stays put.\n", "  Second paragraph gone\n")
    assert_set(
        theatre,
        {"troupe.yml": DOC},
        "doc",
        _value(P1, "Second paragraph gone"),
        {"troupe.yml": expected},
    )


def test_new_paragraph_wrapped_at_the_widest_old_line(theatre: Theatre) -> None:
    new = "New para text that wraps around"
    expected = DOC.replace(
        "  stays put.\n", "  stays put.\n\n  New para text that\n  wraps around\n"
    )
    assert_set(theatre, {"troupe.yml": DOC}, "doc", _value(P1, P2, new), {"troupe.yml": expected})


def test_word_longer_than_width_gets_its_own_line(theatre: Theatre) -> None:
    files = {"troupe.yml": "d: >-\n  ab cd\n"}
    assert_set(
        theatre,
        files,
        "d",
        "ab supercalifragilistic cd",
        {"troupe.yml": "d: >-\n  ab\n  supercalifragilistic\n  cd\n"},
    )


def test_strip_chomping_kept(theatre: Theatre) -> None:
    files = {"troupe.yml": "d: >-\n  a b\nnext: 1\n"}
    assert_set(theatre, files, "d", "a c", {"troupe.yml": "d: >-\n  a c\nnext: 1\n"})


def test_more_indented_line_refused(theatre: Theatre) -> None:
    assert_refused(theatre, {"troupe.yml": DOC}, "doc", _value(P1, "  indented"), 3, "doc")
