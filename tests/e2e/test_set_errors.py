"""`set` failures: exit code, empty stdout, stderr naming the path, no file changed."""

import pytest

from tests.conftest import Theatre, assert_refused

MAIN = "model:\n  name: opus\n  budget:\ntools: [git, shell]\nprompt: file:p.md\n"


@pytest.mark.parametrize(
    ("path", "mention"),
    [
        ("model.name.x", "model.name.x"),  # through a scalar
        ("model.budget.x", "model.budget.x"),  # through a null scalar
        ("model.0", "model.0"),  # digit segment on a mapping
        ("tools.first", "tools.first"),  # key segment on a list
        ("tools.5", "tools.5"),  # index beyond the length
        ("tools.2.x", "tools.2"),  # nothing to append into
        ("prompt.x", "prompt.x"),  # through a text include
        ("model.new.0", "model.new.0"),  # cannot create lists
    ],
)
def test_wrong_path_exits_5(theatre: Theatre, path: str, mention: str) -> None:
    assert_refused(theatre, {"troupe.yml": MAIN, "p.md": "x"}, path, "1", 5, mention)


def test_invalid_value_exits_2(theatre: Theatre) -> None:
    assert_refused(theatre, {"troupe.yml": MAIN, "p.md": "x"}, "model.name", "{a: ", 2, "{a: ")


def test_failed_set_records_no_events(theatre: Theatre) -> None:
    theatre.write("troupe.yml", MAIN)
    theatre.write("p.md", "x")
    count = len(theatre.history())
    assert theatre.config("set", "tools.9", "x").code == 5
    assert theatre.config("set", "prompt", "[1]").code == 3
    assert len(theatre.history()) == count


def test_line_separator_is_written_literally_in_double_quotes(theatre: Theatre) -> None:
    theatre.write("troupe.yml", 'a: "x"\n')
    assert theatre.config("set", "a", '"x\\Ly"').code == 0
    assert theatre.read("troupe.yml") == 'a: "x\u2028y"\n'
    assert theatre.config("show", "a").out == "x\u2028y\n"
