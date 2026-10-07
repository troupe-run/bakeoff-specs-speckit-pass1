"""Literals: strings never read as includes — tagged `!literal`, or `format: uri` in the schema
via `properties`, `additionalProperties` or `items` (spec US3, FR-620 to FR-623, D-64, D-66,
D-67). Nothing is fetched or read for a literal."""

import json
import time
from collections.abc import Callable
from typing import Any

from tests.conftest import Theatre, Watcher, Web, assert_failed, wait_for_history

URI = {"type": "string", "format": "uri"}


def write_schema(theatre: Theatre, schema: dict[str, Any]) -> None:
    theatre.write("troupe.schema.json", json.dumps(schema))


def test_format_uri_via_properties(theatre: Theatre, web: Web) -> None:
    url = web.url("v1.yaml")
    write_schema(theatre, {"properties": {"api": {"properties": {"endpoint": URI}}}})
    theatre.write("troupe.yml", f"api: {{endpoint: {url}}}\n")
    assert theatre.config("get", "api.endpoint").out == f"{url}\n"
    assert web.requests == []


def test_format_uri_via_items(theatre: Theatre, web: Web) -> None:
    write_schema(theatre, {"properties": {"mirrors": {"type": "array", "items": URI}}})
    theatre.write("troupe.yml", f"mirrors: [{web.url('a.yaml')}, {web.url('b.md')}]\n")
    assert theatre.config("get", "mirrors.1").out == f"{web.url('b.md')}\n"
    assert web.requests == []


def test_format_uri_via_additional_properties(theatre: Theatre, web: Web) -> None:
    write_schema(
        theatre, {"properties": {"agents": {"additionalProperties": {"properties": {"home": URI}}}}}
    )
    theatre.write("troupe.yml", f"agents:\n  coder:\n    home: {web.url('h.yaml')}\n")
    assert theatre.config("get", "agents.coder.home").out == f"{web.url('h.yaml')}\n"
    assert web.requests == []


def test_literal_tag_without_a_schema(theatre: Theatre, web: Web) -> None:
    url = web.url("guide.yaml")
    theatre.write("troupe.yml", f"docs: !literal {url}\nnotes: !literal file:missing.md\n")
    assert theatre.config("get", "docs").out == f"{url}\n"
    assert theatre.config("get", "notes").out == "file:missing.md\n"
    assert web.requests == []


def test_history_has_plain_strings(theatre: Theatre, web: Web) -> None:
    url = web.url("guide.yaml")
    theatre.write("troupe.yml", f"docs: !literal {url}\n")
    assert theatre.history() == [
        {"seq": 1, "op": "import", "path": "docs", "old": None, "new": url}
    ]


def test_format_uri_in_an_included_file(theatre: Theatre, web: Web) -> None:
    write_schema(theatre, {"properties": {"a": {"properties": {"u": URI}}}})
    theatre.write("troupe.yml", "a: file:a.yaml\n")
    theatre.write("a.yaml", f"u: {web.url('u.yaml')}\n")
    assert theatre.config("get", "a.u").out == f"{web.url('u.yaml')}\n"
    assert web.requests == []


def test_format_uri_inside_an_override(theatre: Theatre, web: Web) -> None:
    write_schema(theatre, {"properties": {"a": {"properties": {"u": URI}}}})
    theatre.write("troupe.yml", f"a:\n  $ref: file:a.yaml\n  u: {web.url('u.yaml')}\n")
    theatre.write("a.yaml", "k: 1\n")
    assert theatre.config("get", "a.u").out == f"{web.url('u.yaml')}\n"
    assert web.requests == []


def test_ref_value_is_still_an_include_under_a_format_uri_position(
    theatre: Theatre, web: Web
) -> None:
    web.write("c.yaml", "model: opus\n")
    # No `type`: the include makes `coder` a mapping, which `format` alone does not forbid.
    write_schema(theatre, {"properties": {"coder": {"format": "uri"}}})
    theatre.write("troupe.yml", f"coder: {{$ref: {web.url('c.yaml')}}}\n")
    assert theatre.config("get", "coder.model").out == "opus\n"


def test_literal_ref_value_makes_an_ordinary_mapping(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "c: {$ref: !literal file:x.yaml, k: 1}\n")
    assert theatre.config("get", "c.$ref").out == "file:x.yaml\n"


def test_literal_tag_on_a_number_gives_a_string(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "n: !literal 5\n")
    assert theatre.history()[0]["new"] == "5"


def test_literal_tag_on_a_mapping_cannot_load(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "x: 1\na: !literal {b: 1}\n")
    result = theatre.config("get", "x")
    assert_failed(result, 4, "troupe.yml")
    assert "line 2" in result.err


def test_pattern_properties_are_not_followed(theatre: Theatre, web: Web) -> None:
    web.write("p.yaml", "k: 1\n")
    # No `type`: the value is fetched as a mapping, which `format` alone does not forbid.
    write_schema(theatre, {"patternProperties": {"^p": {"format": "uri"}}})
    theatre.write("troupe.yml", f"p: {web.url('p.yaml')}\n")
    assert theatre.config("get", "p.k").out == "1\n"


def test_show_prints_a_literal_untagged(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "docs: !literal https://example.com/x.yaml\n")
    assert theatre.config("show").out == "docs: https://example.com/x.yaml\n"


def test_a_schema_change_is_reconciled(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    url = web.url("x.yaml")
    theatre.write("troupe.yml", f"a: {url}\n")
    theatre.config("get", "a.k")
    write_schema(theatre, {"properties": {"a": URI}})
    assert theatre.config("get", "a").out == f"{url}\n"
    events = [(e["op"], e["path"], e["new"]) for e in theatre.history()[1:]]
    assert events == [("set", "a", url), ("remove", "a.k", None)]


def test_watch_sees_the_schema_file(
    theatre: Theatre, web: Web, start_watch: Callable[..., Watcher]
) -> None:
    web.write("x.yaml", "k: 1\n")
    url = web.url("x.yaml")
    theatre.write("troupe.yml", f"a: {url}\n")
    start_watch()
    since = time.monotonic()
    write_schema(theatre, {"properties": {"a": URI}})

    def literal_recorded(events: list[dict[str, Any]]) -> bool:
        return any((e["op"], e["path"], e["new"]) == ("set", "a", url) for e in events)

    wait_for_history(theatre, literal_recorded, since)


def test_literal_tag_on_a_folded_scalar(theatre: Theatre, web: Web) -> None:
    url = web.url("x.yaml")
    theatre.write("troupe.yml", f"a: !literal >-\n  {url}\n  y\n")
    assert theatre.config("get", "a").out == f"{url} y\n"
    assert web.requests == []
