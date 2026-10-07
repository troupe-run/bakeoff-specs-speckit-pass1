"""Include strings, URL kinds and the write guard (spec FR-600, FR-601, FR-610; research U-1,
U-2, U-4)."""

from pathlib import Path

import pytest

from troupe.config.edit.literals import mark
from troupe.config.files import RemoteSource, SourceFile, is_yaml_url, local_path
from troupe.config.includes import LITERAL_TAG, FileRef, UrlRef, include_ref
from troupe.config.paths import ConfigPath
from troupe.config.scalars import NewNode, NewScalar
from troupe.config.schema import Schema
from troupe.errors import WriteRefused


def test_file_prefix() -> None:
    assert include_ref("file:agents/coder.yaml") == FileRef("agents/coder.yaml")


def test_https_and_http_prefixes() -> None:
    assert include_ref("https://example.com/a.yaml") == UrlRef("https://example.com/a.yaml")
    assert include_ref("http://example.com/a.md") == UrlRef("http://example.com/a.md")


@pytest.mark.parametrize("text", ["HTTPS://x", " https://x", "ftp://x", "File:x", "https:/x"])
def test_prefix_is_case_sensitive_and_exact(text: str) -> None:
    assert include_ref(text) is None


@pytest.mark.parametrize("value", [5, None, True, 1.5])
def test_non_strings_are_never_includes(value: object) -> None:
    assert include_ref(value) is None


@pytest.mark.parametrize(
    ("url", "yaml"),
    [
        ("https://h/a.yaml?rev=3", True),
        ("https://h/a.yml#x", True),
        ("https://h/a.md", False),
        ("https://h/a.YAML", False),
        ("https://h/a?x=.yaml", False),
    ],
)
def test_is_yaml_url_ignores_query_and_fragment(url: str, yaml: bool) -> None:
    assert is_yaml_url(url) is yaml


def test_local_path_refuses_a_url() -> None:
    with pytest.raises(RemoteSource) as raised:
        local_path(SourceFile("https://h/a.yaml", "", "yaml"))
    assert raised.value.exit_code == 3
    assert raised.value.url == "https://h/a.yaml"


def test_local_path_gives_a_local_path() -> None:
    assert local_path(SourceFile(Path("/x/a.yaml"), "", "yaml")) == Path("/x/a.yaml")


# --- literals.mark (spec FR-640 to FR-643, D-68, D-69) ---


def _schema(document: dict[str, object]) -> Schema:
    return Schema(Path("/t/.troupe/troupe.schema.json"), document)


URI = {"format": "uri"}


def test_mark_tags_include_like_strings() -> None:
    marked = mark(NewScalar("https://x"), ConfigPath.parse("a"), None, include=False)
    assert marked == NewScalar("https://x", tag=LITERAL_TAG)
    plain = NewScalar("plain")
    assert mark(plain, ConfigPath.parse("a"), None, include=False) == plain
    assert mark(NewScalar(5), ConfigPath.parse("a"), None, include=False) == NewScalar(5)


def test_mark_respects_format_uri() -> None:
    schema = _schema({"properties": {"a": {"properties": {"u": URI}}}})
    marked = mark(NewScalar("https://x"), ConfigPath.parse("a.u"), schema, include=False)
    assert marked == NewScalar("https://x")


def test_mark_nested_paths() -> None:
    schema = _schema({"properties": {"b": {"properties": {"l": {"items": URI}}}}})
    value: NewNode = {"l": [NewScalar("https://x")], "v": NewScalar("file:y")}
    marked = mark(value, ConfigPath.parse("b"), schema, include=False)
    assert marked == {"l": [NewScalar("https://x")], "v": NewScalar("file:y", tag=LITERAL_TAG)}


def test_mark_include_flag() -> None:
    value = NewScalar("https://x")
    assert mark(value, ConfigPath.parse("a"), None, include=True) == value
    schema = _schema({"properties": {"a": URI}})
    with pytest.raises(WriteRefused):
        mark(value, ConfigPath.parse("a"), schema, include=True)
