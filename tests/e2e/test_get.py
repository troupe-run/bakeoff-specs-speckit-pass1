"""`get PATH` prints a scalar exactly as step 1's `show` did (spec FR-201, SC-201)."""

import pytest

from tests.conftest import Theatre

MAIN = """\
# theatre
model:
  name: opus
  temperature: 0.2   # creative
  enabled: true
  budget: null
  retries: 42
  big: 1e3
  answer: yes
  quoted: "0.2"
  single: 'it''s'
  notes: |
    line one
    line two
  stripped: |-
    no newline
  folded: >
    folded
    text
tools: [git, shell]
agents:
  coder: file:agents/coder.yaml
prompt: file:prompts/system.md
"""


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("agents/coder.yaml", "model: sonnet\nskills: file:skills/list.yaml\n")
    theatre.write("agents/skills/list.yaml", "- review\n- refactor\n")
    theatre.write("prompts/system.md", "Be terse.\n")
    return theatre


@pytest.mark.parametrize(
    ("path", "printed"),
    [
        ("model.name", "opus\n"),
        ("model.temperature", "0.2\n"),
        ("model.enabled", "true\n"),
        ("model.budget", "null\n"),
        ("model.retries", "42\n"),
        ("model.big", "1000.0\n"),
        ("model.answer", "yes\n"),
        ("model.quoted", "0.2\n"),
        ("model.single", "it's\n"),
        ("model.notes", "line one\nline two\n"),
        ("model.stripped", "no newline\n"),
        ("model.folded", "folded text\n"),
        ("tools.1", "shell\n"),
        ("agents.coder.model", "sonnet\n"),
        ("agents.coder.skills.1", "refactor\n"),
        ("prompt", "Be terse.\n"),
    ],
)
def test_get_prints_the_scalar(ready: Theatre, path: str, printed: str) -> None:
    result = ready.config("get", path)
    assert (result.code, result.out, result.err) == (0, printed, "")


def test_nested_include_path_is_relative_to_the_including_file(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:sub/one.yaml\n")
    theatre.write("sub/one.yaml", "b: file:two.yaml\n")
    theatre.write("sub/two.yaml", "c: deep\n")
    assert theatre.config("get", "a.b.c").out == "deep\n"


def test_text_include_prints_exact_bytes_including_crlf(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: file:p.txt\n")
    theatre.write("p.txt", b"one\r\ntwo\r\n")
    result = theatre.run("config", "get", "prompt")
    assert result.out == "one\r\ntwo\r\n"


def test_text_include_without_final_newline_gets_one(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: file:p.txt\n")
    theatre.write("p.txt", "no newline")
    assert theatre.config("get", "prompt").out == "no newline\n"


def test_empty_text_include_prints_a_newline(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: 'file:p.txt'\n")
    theatre.write("p.txt", "")
    assert theatre.config("get", "prompt").out == "\n"


def test_non_ascii_values_print_as_utf8(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "name: 日本語 ✓\n")
    assert theatre.config("get", "name").out == "日本語 ✓\n"


def test_crlf_config_file(theatre: Theatre) -> None:
    theatre.write("troupe.yml", b"a:\r\n  b: x\r\n")
    assert theatre.config("get", "a.b").out == "x\n"
