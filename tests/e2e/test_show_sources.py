"""`show [PATH] --sources`: every scalar line names its file (spec FR-230 to FR-234)."""

import os
from pathlib import Path

import pytest

from tests.conftest import Theatre

MAIN = """\
# main
model: {temperature: 0.2, name: 'opus'}
agents:
  coder: file:agents/coder.yaml
prompt: file:prompts/system.md
"""

WHOLE = """\
model:
  temperature: 0.2 # from .troupe/troupe.yml
  name: opus # from .troupe/troupe.yml
agents:
  coder:
    model: sonnet # from .troupe/agents/coder.yaml
    tools:
      - git # from .troupe/agents/coder.yaml
      - shell # from .troupe/agents/coder.yaml
prompt: | # from .troupe/prompts/system.md
  Be terse.
  No jokes.
"""


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("agents/coder.yaml", "model: sonnet\ntools: [git, shell]\n")
    theatre.write("prompts/system.md", "Be terse.\nNo jokes.\n")
    return theatre


def sources(theatre: Theatre, *args: str) -> str:
    result = theatre.config("show", *args, "--sources")
    assert (result.code, result.err) == (0, ""), result
    return result.out


def test_whole_configuration(ready: Theatre) -> None:
    assert sources(ready) == WHOLE


def test_section(ready: Theatre) -> None:
    assert sources(ready, "agents") == (
        "coder:\n"
        "  model: sonnet # from .troupe/agents/coder.yaml\n"
        "  tools:\n"
        "    - git # from .troupe/agents/coder.yaml\n"
        "    - shell # from .troupe/agents/coder.yaml\n"
    )


def test_option_before_the_path(ready: Theatre) -> None:
    result = ready.config("show", "--sources", "agents")
    assert result.out == sources(ready, "agents")


def test_include_outside_the_troupe_directory(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "shared: file:../common/shared.yaml\n")
    (theatre.root / "common").mkdir()
    (theatre.root / "common" / "shared.yaml").write_text("k: v\n")
    assert sources(theatre, "shared") == "k: v # from common/shared.yaml\n"


def test_include_outside_the_theatre(theatre: Theatre, tmp_path: Path) -> None:
    (tmp_path / "elsewhere.yaml").write_text("k: v\n")
    theatre.write("troupe.yml", "x: file:../../elsewhere.yaml\n")
    assert sources(theatre) == "x:\n  k: v # from ../elsewhere.yaml\n"


def test_two_level_include_names_the_innermost_file(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "agents: {coder: 'file:agents/coder.yaml'}\n")
    theatre.write("agents/coder.yaml", "model: m\nlimits: file:limits.yaml\n")
    theatre.write("agents/limits.yaml", "retries: 3\n")
    assert sources(theatre, "agents.coder") == (
        "model: m # from .troupe/agents/coder.yaml\n"
        "limits:\n"
        "  retries: 3 # from .troupe/agents/limits.yaml\n"
    )


@pytest.mark.parametrize(
    ("main", "path", "expected"),
    [
        ("model: {temperature: 0.2}\n", "model.temperature", "0.2 # from .troupe/troupe.yml\n"),
        ('n: "0.2"\n', "n", "'0.2' # from .troupe/troupe.yml\n"),
        ("n: null\n", "n", "null # from .troupe/troupe.yml\n"),
    ],
)
def test_scalar_is_printed_as_yaml_with_its_source(
    theatre: Theatre, main: str, path: str, expected: str
) -> None:
    theatre.write("troupe.yml", main)
    assert sources(theatre, path) == expected


def test_text_include_scalar(ready: Theatre) -> None:
    assert sources(ready, "prompt") == (
        "| # from .troupe/prompts/system.md\n  Be terse.\n  No jokes.\n"
    )


def test_empty_collections_and_configuration_get_no_comment(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "e: {}\nl: []\n")
    assert sources(theatre) == "e: {}\nl: []\n"
    theatre.write("troupe.yml", "")
    assert sources(theatre) == "{}\n"


def test_list_of_mappings(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "steps: [{name: a, run: x}]\n")
    assert sources(theatre, "steps") == (
        "- name: a # from .troupe/troupe.yml\n  run: x # from .troupe/troupe.yml\n"
    )


def test_one_comment_per_scalar_leaf(ready: Theatre) -> None:
    leaves = [e for e in ready.history() if e["op"] == "import"]
    assert sources(ready).count("# from ") == len(leaves)


def test_theatre_reached_through_a_symlink(ready: Theatre, tmp_path: Path) -> None:
    link = tmp_path / "link"
    os.symlink(ready.root, link)
    result = ready.run("config", "show", "--sources", "--theatre", str(link), theatre=False)
    assert result.out == WHOLE


def test_same_file_included_twice_is_shown_in_full_under_both_keys(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:s.yaml\nb: file:s.yaml\n")
    theatre.write("s.yaml", "k: 1\n")
    assert sources(theatre) == (
        "a:\n  k: 1 # from .troupe/s.yaml\nb:\n  k: 1 # from .troupe/s.yaml\n"
    )
