"""`show`'s YAML, with and without `--sources`, reads back as the configuration (spec FR-214)."""

from typing import Any

import pytest
from ruamel.yaml import YAML

from tests.conftest import Theatre
from troupe.config.commands import resolve
from troupe.config.loader import load
from troupe.config.paths import ConfigPath
from troupe.config.scalars import Value, scalars_equal
from troupe.config.tree import Located, LocatedMapping, LocatedSequence, TextInclude

MAIN = """\
# every kind of value
flags: {on: true, off: false, none: ~, n: 42, hex: 0x10, f: 1.5, big: 1e3}
odd: [.inf, -.inf, .nan]
strings:
  plain: opus
  number_like: "0.2"
  bool_like: 'true'
  empty: ""
  colon: "a: b"
  dash: "- x"
  hash: "x #y"
  quote: "it's"
  both: "it's \\"q\\""
  tab: "a\\tb"
  lead: " lead"
  unicode: 日本語 ✓
block: |
  line one
    indented
  line three
kept: "x\\n\\n"
leading: "  lead\\nx\\n"
nested:
  - [a, [b, c]]
  - {k: v, l: [1, {m: n}]}
  - []
  - {}
agents: {coder: "file:agents/coder.yaml"}
prompt: file:prompts/system.md
bare: file:prompts/bare.txt
shared: file:../common/shared.yaml
"""


def plain(node: Located) -> Value:
    if isinstance(node, LocatedMapping):
        return {str(key.value): plain(value) for key, value in node.entries}
    if isinstance(node, LocatedSequence):
        return [plain(item) for item in node.items]
    if isinstance(node, TextInclude):
        return node.value
    return node.value


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", MAIN)
    theatre.write("agents/coder.yaml", "model: sonnet\nlimits: file:limits.yaml\n")
    theatre.write("agents/limits.yaml", "retries: 3\ntools: [git]\n")
    theatre.write("prompts/system.md", "Be terse.\n\n  No jokes.\n")
    theatre.write("prompts/bare.txt", "no newline")
    common = theatre.root / "common"
    common.mkdir()
    (common / "shared.yaml").write_text("k: v\n")
    return theatre


def read_back(text: str) -> Any:
    return YAML(typ="safe").load(text)


@pytest.mark.parametrize("path", [None, "agents", "strings", "nested", "nested.1"])
@pytest.mark.parametrize("sources", [False, True])
def test_show_reads_back_as_the_configuration(
    ready: Theatre, path: str | None, sources: bool
) -> None:
    args = [*([path] if path else []), *(["--sources"] if sources else [])]
    result = ready.config("show", *args)
    assert result.code == 0, result
    root = load(ready.root).root
    expected = plain(root if path is None else resolve(root, ConfigPath.parse(path)))
    assert scalars_equal(read_back(result.out), expected), result.out


def test_crlf_text_include_reads_back_with_lf(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "p: file:p.md\n")
    theatre.write("p.md", b"a\r\nb\r\n")
    assert read_back(theatre.config("show").out) == {"p": "a\nb\n"}
