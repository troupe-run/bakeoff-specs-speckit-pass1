"""`get`: a missing path → exit 5 naming it; a collection → exit 5 pointing to `config show`."""

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
def test_get_exits_5_naming_the_path(ready: Theatre, path: str) -> None:
    before = ready.snapshot()
    assert_failed(ready.config("get", path), 5, path)
    assert ready.snapshot() == before


@pytest.mark.parametrize("path", ["model", "tools", "agents.coder"])
def test_get_of_a_collection_mentions_config_show(ready: Theatre, path: str) -> None:
    ready.write("troupe.yml", ready.read("troupe.yml") + "agents:\n  coder: file:c.yaml\n")
    ready.write("c.yaml", "model: x\n")
    result = ready.config("get", path)
    assert_failed(result, 5, path)
    assert "config show" in result.err, result
