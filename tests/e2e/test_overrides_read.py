"""Reading mapping-form includes: every command sees the merged value (spec US2, FR-400 to
FR-408)."""

import pytest

from tests.conftest import Theatre, assert_failed

CODER = "model: opus\neffort: low\ntools: [git, shell]\nlimits: {retries: 2, timeout: 10}\n"
MAIN = """\
agents:
  coder: {$ref: file:agents/coder.yaml, model: sonnet, tools: [lint], limits: {timeout: 30}}
"""


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("agents/coder.yaml", CODER)
    return theatre


def out(theatre: Theatre, *args: str) -> str:
    result = theatre.config(*args)
    assert (result.code, result.err) == (0, ""), result
    return result.out


def test_overridden_scalar_is_the_override(ready: Theatre) -> None:
    assert out(ready, "get", "agents.coder.model") == "sonnet\n"
    assert out(ready, "get", "agents.coder.effort") == "low\n"  # merged with the included file


def test_override_list_replaces_the_included_list(ready: Theatre) -> None:
    assert out(ready, "get", "agents.coder.tools.0") == "lint\n"
    assert out(ready, "get", "agents.coder.effort") == "low\n"  # merged with the included file
    assert_failed(ready.config("get", "agents.coder.tools.1"), 5, "agents.coder.tools.1")


def test_mappings_merge_recursively(ready: Theatre) -> None:
    assert out(ready, "show", "agents.coder.limits") == "retries: 2\ntimeout: 30\n"


def test_sources_name_the_file_each_value_is_written_in(ready: Theatre) -> None:
    assert out(ready, "show", "agents.coder", "--sources") == (
        "model: sonnet # from .troupe/troupe.yml\n"
        "effort: low # from .troupe/agents/coder.yaml\n"
        "tools:\n"
        "  - lint # from .troupe/troupe.yml\n"
        "limits:\n"
        "  retries: 2 # from .troupe/agents/coder.yaml\n"
        "  timeout: 30 # from .troupe/troupe.yml\n"
    )


def test_ref_only_text_include_prints_the_text(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: {$ref: file:prompts/system.md}\n")
    theatre.write("prompts/system.md", "Be terse.\n")
    assert out(theatre, "get", "prompt") == "Be terse.\n"


def test_import_lists_merged_leaves_in_included_order_and_no_ref(ready: Theatre) -> None:
    ready.write(
        "troupe.yml", MAIN.replace("limits: {timeout: 30}}", "limits: {timeout: 30}, z: 1}")
    )
    events = ready.history()
    assert [(e["op"], e["path"], e["new"]) for e in events] == [
        ("import", "agents.coder.model", "sonnet"),
        ("import", "agents.coder.effort", "low"),
        ("import", "agents.coder.tools.0", "lint"),
        ("import", "agents.coder.limits.retries", 2),
        ("import", "agents.coder.limits.timeout", 30),
        ("import", "agents.coder.z", 1),
    ]


def test_ref_segment_is_a_missing_path(ready: Theatre) -> None:
    assert_failed(ready.config("show", "agents.coder.$ref"), 5, "agents.coder.$ref")


def test_override_value_that_is_an_include_is_followed(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "coder:\n  $ref: file:c.yaml\n  prompt: file:p.md\n")
    theatre.write("c.yaml", "prompt: old\nmodel: m\n")
    theatre.write("p.md", "From the override.\n")
    assert out(theatre, "get", "coder.prompt") == "From the override.\n"
    assert out(theatre, "get", "coder.model") == "m\n"


def test_nested_mapping_form_in_an_override(theatre: Theatre) -> None:
    theatre.write(
        "troupe.yml", "coder:\n  $ref: file:c.yaml\n  model:\n    $ref: file:m.yaml\n    b: 3\n"
    )
    theatre.write("c.yaml", "model: {a: 1}\n")
    theatre.write("m.yaml", "c: 2\n")
    assert out(theatre, "show", "coder") == "model:\n  a: 1\n  c: 2\n  b: 3\n"
