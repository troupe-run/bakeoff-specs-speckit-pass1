"""`show [PATH]`: a scalar like `get`; a section or the whole configuration as YAML (spec FR-210 to
FR-225)."""

import pytest

from tests.conftest import Theatre, assert_failed

MAIN = """\
# main
model: {temperature: 0.2, name: 'opus'}
agents:
  coder: file:agents/coder.yaml
prompt: file:prompts/system.md
"""

WHOLE = """\
model:
  temperature: 0.2
  name: opus
agents:
  coder:
    model: sonnet
    tools:
      - git
      - shell
prompt: |
  Be terse.
  No jokes.
"""


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("agents/coder.yaml", "model: sonnet\ntools: [git, shell]\n")
    theatre.write("prompts/system.md", "Be terse.\nNo jokes.\n")
    return theatre


@pytest.mark.parametrize(
    "path", ["model.temperature", "model.name", "prompt", "agents.coder.model"]
)
def test_show_prints_a_scalar_like_get(ready: Theatre, path: str) -> None:
    shown = ready.config("show", path)
    got = ready.config("get", path)
    assert (shown.code, shown.out, shown.err) == (0, got.out, "")
    assert got.code == 0


def test_show_of_a_crlf_text_include_prints_its_exact_text(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: file:p.txt\n")
    theatre.write("p.txt", b"one\r\ntwo\r\n")
    assert theatre.config("show", "prompt").out == "one\r\ntwo\r\n"


def test_show_of_the_whole_configuration(ready: Theatre) -> None:
    result = ready.config("show")
    assert (result.code, result.out, result.err) == (0, WHOLE, "")


def test_show_of_a_section(ready: Theatre) -> None:
    assert ready.config("show", "agents.coder").out == "model: sonnet\ntools:\n  - git\n  - shell\n"


def test_show_of_a_list(ready: Theatre) -> None:
    assert ready.config("show", "agents.coder.tools").out == "- git\n- shell\n"


def test_show_of_a_list_of_mappings(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "steps: [{name: a, run: x}, {name: b}]\n")
    assert theatre.config("show", "steps").out == "- name: a\n  run: x\n- name: b\n"


@pytest.mark.parametrize(
    "path", ["missing", "model.name.x", "agents.coder.tools.9", "model.0", "prompt.x"]
)
def test_show_errors_exit_5_naming_the_path(ready: Theatre, path: str) -> None:
    assert_failed(ready.config("show", path), 5, path)


def test_show_writes_no_file(ready: Theatre) -> None:
    before = ready.snapshot()
    assert ready.config("show").code == 0
    assert ready.config("show", "--sources").code == 0
    assert ready.config("show", "agents", "--sources").code == 0
    assert ready.snapshot() == before


def test_show_reconciles_first(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    theatre.history()  # import
    theatre.write("troupe.yml", "a: 2\n")
    assert theatre.config("show").out == "a: 2\n"
    assert theatre.history()[-1] == {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}


def test_show_of_an_empty_configuration(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "")
    assert theatre.config("show").out == "{}\n"


def test_show_accepts_options_before_the_path(ready: Theatre) -> None:
    result = ready.run(
        "config", "show", "--theatre", str(ready.root), "agents.coder.tools", theatre=False
    )
    assert (result.code, result.out) == (0, "- git\n- shell\n")
