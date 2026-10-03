"""`show`'s YAML view: layout, quoting, literal blocks, includes (spec FR-213 to FR-225)."""

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from troupe.config.commands import resolve
from troupe.config.loader import load
from troupe.config.paths import ConfigPath
from troupe.config.view import render


def write(root: Path, relpath: str, content: str | bytes) -> None:
    path = root / ".troupe" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)


def view(root: Path, main: str, path: str | None = None) -> str:
    write(root, "troupe.yml", main)
    loaded = load(root)
    node = loaded.root if path is None else resolve(loaded.root, ConfigPath.parse(path))
    return render(node, root, sources=False)


def read_back(text: str) -> Any:
    return YAML(typ="safe").load(text)


def test_flat_mapping(tmp_path: Path) -> None:
    assert view(tmp_path, "a: 1\nb: x\n") == "a: 1\nb: x\n"


def test_flow_mapping_becomes_block_and_original_quoting_is_dropped(tmp_path: Path) -> None:
    out = view(tmp_path, "model: {temperature: 0.2, name: 'opus'}\n")
    assert out == "model:\n  temperature: 0.2\n  name: opus\n"


def test_list_under_a_key_is_indented(tmp_path: Path) -> None:
    assert view(tmp_path, "tools: [git, shell]\n") == "tools:\n  - git\n  - shell\n"


def test_list_at_the_top_of_the_view(tmp_path: Path) -> None:
    assert view(tmp_path, "tools: [git, shell]\n", "tools") == "- git\n- shell\n"


def test_list_of_mappings_uses_the_compact_form(tmp_path: Path) -> None:
    out = view(tmp_path, "steps: [{name: a, run: x}, {name: b}]\n", "steps")
    assert out == "- name: a\n  run: x\n- name: b\n"


def test_nested_lists_use_the_compact_form(tmp_path: Path) -> None:
    assert view(tmp_path, "m: [[x, y], [z]]\n", "m") == "- - x\n  - y\n- - z\n"


def test_mapping_inside_a_list_inside_a_mapping(tmp_path: Path) -> None:
    out = view(tmp_path, "a:\n  - b: {c: 1}\n    d: [2]\n")
    assert out == "a:\n  - b:\n      c: 1\n    d:\n      - 2\n"
    assert read_back(out) == {"a": [{"b": {"c": 1}, "d": [2]}]}


def test_empty_collections_are_written_in_flow_form(tmp_path: Path) -> None:
    assert view(tmp_path, "e: {}\nl: []\n") == "e: {}\nl: []\n"
    assert view(tmp_path, "l: [[], {}]\n", "l") == "- []\n- {}\n"


def test_empty_configuration(tmp_path: Path) -> None:
    assert view(tmp_path, "") == "{}\n"


@pytest.mark.parametrize(
    "value", ["0.2", "true", "null", "", "a: b", "- x", " lead", "it's: x", "#c", "x #y", "~"]
)
def test_strings_that_need_quoting_are_quoted_and_read_back(tmp_path: Path, value: str) -> None:
    main = "k: " + ('"' + value.replace('"', '\\"') + '"') + "\n"
    out = view(tmp_path, main)
    assert out != f"k: {value}\n"
    assert read_back(out) == {"k": value}


@pytest.mark.parametrize("value", ["opus", "yes", "on", "a b", "x:y"])
def test_plain_strings_are_not_quoted(tmp_path: Path, value: str) -> None:
    assert view(tmp_path, f"k: '{value}'\n") == f"k: {value}\n"


def test_quoted_key_that_needs_quoting_stays_quoted(tmp_path: Path) -> None:
    out = view(tmp_path, "'true': 1\n")
    assert out == "'true': 1\n"
    assert read_back(out) == {"true": 1}


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("true", "true"),
        ("false", "false"),
        ("null", "null"),
        ("42", "42"),
        ("0x1F", "31"),
        ("1e3", "1000.0"),
        (".inf", ".inf"),
        ("-.inf", "-.inf"),
        (".nan", ".nan"),
    ],
)
def test_non_string_scalars(tmp_path: Path, text: str, shown: str) -> None:
    assert view(tmp_path, f"k: {text}\n") == f"k: {shown}\n"


def test_block_value_is_a_literal_block(tmp_path: Path) -> None:
    assert view(tmp_path, "notes: |\n    one\n    two\n") == "notes: |\n  one\n  two\n"


def test_quoted_multiline_string_becomes_a_strip_literal(tmp_path: Path) -> None:
    assert view(tmp_path, 'k: "x\\ny"\n') == "k: |-\n  x\n  y\n"


def test_keep_chomping_reads_back_exactly(tmp_path: Path) -> None:
    out = view(tmp_path, 'k: "x\\n\\n"\n')
    assert out.startswith("k: |+\n")
    assert read_back(out) == {"k": "x\n\n"}


def test_leading_space_gets_an_indentation_indicator(tmp_path: Path) -> None:
    out = view(tmp_path, 'k: "  lead\\nx\\n"\n')
    assert out.startswith("k: |2\n")
    assert read_back(out) == {"k": "  lead\nx\n"}


def test_literal_inside_a_list_item_mapping_reads_back(tmp_path: Path) -> None:
    out = view(tmp_path, 'l:\n  - k: "a\\n b\\n"\n    j: 1\n')
    assert out == "l:\n  - k: |\n      a\n       b\n    j: 1\n"
    assert read_back(out) == {"l": [{"k": "a\n b\n", "j": 1}]}


def test_single_line_text_include_is_still_a_literal_block(tmp_path: Path) -> None:
    write(tmp_path, "p.md", "Be terse.\n")
    assert view(tmp_path, "p: file:p.md\n") == "p: |\n  Be terse.\n"


def test_text_include_without_final_newline(tmp_path: Path) -> None:
    write(tmp_path, "p.md", "no newline")
    assert view(tmp_path, "p: file:p.md\n") == "p: |-\n  no newline\n"


def test_empty_text_include(tmp_path: Path) -> None:
    write(tmp_path, "p.md", "")
    out = view(tmp_path, "p: file:p.md\nq: 1\n")
    assert out.startswith("p: |-\n")
    assert read_back(out) == {"p": "", "q": 1}


def test_crlf_text_include_is_shown_as_its_lines(tmp_path: Path) -> None:
    write(tmp_path, "p.md", b"a\r\nb\r\n")
    assert view(tmp_path, "p: file:p.md\n") == "p: |\n  a\n  b\n"


def test_text_include_whose_text_starts_with_file_is_shown_as_text(tmp_path: Path) -> None:
    write(tmp_path, "p.md", "file:other.md\n")
    assert view(tmp_path, "p: file:p.md\n") == "p: |\n  file:other.md\n"


def test_yaml_includes_are_embedded_in_place_in_document_order(tmp_path: Path) -> None:
    write(tmp_path, "agents/coder.yaml", "model: sonnet\nlimits: file:limits.yaml\nz: 1\n")
    write(tmp_path, "agents/limits.yaml", "retries: 3\n")
    out = view(tmp_path, "a: 0\nagents: {coder: 'file:agents/coder.yaml'}\nb: 2\n")
    assert out == (
        "a: 0\nagents:\n  coder:\n    model: sonnet\n    limits:\n      retries: 3\n"
        "    z: 1\nb: 2\n"
    )


def test_empty_yaml_include_is_null(tmp_path: Path) -> None:
    write(tmp_path, "e.yaml", "")
    assert view(tmp_path, "k: file:e.yaml\n") == "k: null\n"


SPACE_FIRST = "    \nabc\n"  # a whitespace-only line longer than the content indentation


def test_text_include_starting_with_a_spaces_only_line_reads_back(tmp_path: Path) -> None:
    write(tmp_path, "p.md", SPACE_FIRST)
    out = view(tmp_path, "p: file:p.md\nq: 1\n")
    assert out == "p: |2\n      \n  abc\nq: 1\n"
    assert read_back(out) == {"p": SPACE_FIRST, "q": 1}


def test_string_starting_with_a_spaces_only_line_in_a_list_item_reads_back(tmp_path: Path) -> None:
    out = view(tmp_path, 'l:\n  - k: "  \\n\\nx"\n  - "   \\ny\\n"\n')
    assert read_back(out) == {"l": [{"k": "  \n\nx"}, "   \ny\n"]}


def test_top_level_text_include_starting_with_a_spaces_only_line_reads_back(
    tmp_path: Path,
) -> None:
    write(tmp_path, "p.md", SPACE_FIRST)
    write(tmp_path, "troupe.yml", "p: file:p.md\n")
    loaded = load(tmp_path)
    out = render(resolve(loaded.root, ConfigPath.parse("p")), tmp_path, sources=True)
    assert out == "|2 # from .troupe/p.md\n      \n  abc\n"
    assert read_back(out) == SPACE_FIRST
