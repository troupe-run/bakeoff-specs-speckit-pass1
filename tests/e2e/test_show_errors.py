"""`show` of a missing path or a collection → exit 5 naming the path."""

import pytest

from tests.conftest import Theatre, assert_failed


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", "model:\n  name: opus\ntools: [git, shell]\nprompt: file:p.md\n")
    theatre.write("p.md", "hi\n")
    return theatre


@pytest.mark.parametrize(
    "path",
    [
        "model",  # a mapping
        "tools",  # a list
        "missing",
        "model.missing",
        "tools.2",  # index out of range
        "model.0",  # digit segment on a mapping
        "tools.first",  # key segment on a list
        "model.name.x",  # below a scalar
        "prompt.x",  # below a text include
    ],
)
def test_show_exits_5_naming_the_path(ready: Theatre, path: str) -> None:
    before = ready.snapshot()
    assert_failed(ready.config("show", path), 5, path)
    assert ready.snapshot() == before
