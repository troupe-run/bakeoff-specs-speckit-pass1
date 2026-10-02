"""Every failure names the offending path or file on stderr, with stdout empty (FR-008)."""

import pytest

from tests.conftest import Theatre, assert_failed

FILES = {
    "troupe.yml": "a: 1\nl: [x]\ninc: file:inc.yaml\ntxt: file:t.md\nf: >\n  some words\n",
    "inc.yaml": "k: v\n",
    "t.md": "text",
}


@pytest.mark.parametrize(
    ("args", "code", "mention"),
    [
        (("show", "l"), 5, "l"),
        (("show", "a.b"), 5, "a.b"),
        (("show", "missing"), 5, "missing"),
        (("set", "l.5", "x"), 5, "l.5"),
        (("set", "inc", "x"), 3, "inc"),
        (("set", "txt", "[1]"), 3, "txt"),
        (("set", "f", '" x"'), 3, "f"),
        (("set", "a", "[oops"), 2, "[oops"),
        (("show", "a..b"), 2, "a..b"),
        (("history", "a..b"), 2, "a..b"),
    ],
)
def test_failures_name_the_path(
    theatre: Theatre, args: tuple[str, ...], code: int, mention: str
) -> None:
    for name, content in FILES.items():
        theatre.write(name, content)
    assert_failed(theatre.config(*args), code, mention)


@pytest.mark.parametrize(
    ("files", "mention"),
    [
        ({}, "troupe.yml"),
        ({"troupe.yml": "a: file:gone.yaml\n"}, "gone.yaml"),
        ({"troupe.yml": "a: [\n"}, "troupe.yml"),
        ({"troupe.yml": "a: file:x.yaml\n", "x.yaml": "b: file:x.yaml\n"}, "x.yaml"),
    ],
)
def test_load_failures_name_the_file(theatre: Theatre, files: dict[str, str], mention: str) -> None:
    for name, content in files.items():
        theatre.write(name, content)
    assert_failed(theatre.config("show", "a"), 4, mention)
