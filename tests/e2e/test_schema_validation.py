"""The configuration must validate against `.troupe/troupe.schema.json` (spec US4, FR-630 to
FR-634, D-64): invalid on load → exit 4; a `set` that would invalidate it → exit 3."""

import json
import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import Theatre, Watcher, Web, assert_failed, assert_refused, wait_for_history

SCHEMA = {
    "properties": {
        "temperature": {"type": "number"},
        "agents": {"additionalProperties": {"properties": {"model": {"enum": ["opus", "sonnet"]}}}},
    }
}


def write_schema(theatre: Theatre, schema: Any = SCHEMA) -> None:
    text = schema if isinstance(schema, str) else json.dumps(schema)
    theatre.write("troupe.schema.json", text)


def test_invalid_configuration_cannot_load(theatre: Theatre) -> None:
    write_schema(theatre)
    theatre.write("troupe.yml", "temperature: warm\nx: 1\n")
    before = theatre.snapshot()
    for args in (("get", "x"), ("show",), ("history",), ("set", "x", "2")):
        result = theatre.config(*args)
        assert_failed(result, 4, "troupe.schema.json")
        assert "temperature" in result.err, result
    assert theatre.snapshot() == before


def test_set_that_would_invalidate_is_refused(theatre: Theatre) -> None:
    write_schema(theatre)
    theatre.write("troupe.yml", "temperature: 0.2\n")
    events = theatre.events()
    assert_refused(theatre, {}, "temperature", "warm", 3, "troupe.schema.json")
    assert "temperature" in theatre.config("set", "temperature", "warm").err
    assert theatre.events() == events


def test_valid_set_succeeds(theatre: Theatre) -> None:
    write_schema(theatre)
    theatre.write("troupe.yml", "temperature: 0.2\n")
    assert theatre.config("set", "temperature", "0.5").code == 0
    assert theatre.read("troupe.yml") == "temperature: 0.5\n"


def test_invalid_remote_content_cannot_load(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder: {model: haiku}\n")
    write_schema(theatre)
    theatre.write("troupe.yml", f"agents: {web.url('agents.yaml')}\n")
    result = theatre.config("show")
    assert_failed(result, 4, "troupe.schema.json")
    assert "agents.coder.model" in result.err


@pytest.mark.parametrize(
    "schema",
    [
        "{",
        "[]",
        {"type": 5},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
        {"$ref": "https://example.com/s.json"},
        {"properties": {"a": {"$ref": "other.json#/x"}}},
        {"$dynamicRef": "https://example.com/s.json"},
    ],
)
def test_unusable_schema_cannot_load(theatre: Theatre, schema: Any) -> None:
    write_schema(theatre, schema)
    theatre.write("troupe.yml", "a: 1\n")
    assert_failed(theatre.config("get", "a"), 4, "troupe.schema.json")


def test_no_schema_means_no_validation(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "temperature: warm\n")
    assert theatre.config("get", "temperature").out == "warm\n"


def test_explicit_2020_12_dialect_is_accepted(theatre: Theatre) -> None:
    write_schema(theatre, {"$schema": "https://json-schema.org/draft/2020-12/schema", **SCHEMA})
    theatre.write("troupe.yml", "temperature: 1\n")
    assert theatre.config("get", "temperature").out == "1\n"


def test_format_is_not_asserted(theatre: Theatre) -> None:
    write_schema(theatre, {"properties": {"u": {"type": "string", "format": "uri"}}})
    theatre.write("troupe.yml", "u: not a uri\n")
    assert theatre.config("get", "u").out == "not a uri\n"


def test_internal_ref_is_followed_for_validation(theatre: Theatre) -> None:
    write_schema(
        theatre,
        {"$defs": {"num": {"type": "number"}}, "properties": {"t": {"$ref": "#/$defs/num"}}},
    )
    theatre.write("troupe.yml", "t: warm\n")
    assert_failed(theatre.config("get", "t"), 4, "troupe.schema.json")


def test_validation_sees_merged_overrides(theatre: Theatre) -> None:
    write_schema(theatre)
    theatre.write("coder.yaml", "model: haiku\n")
    theatre.write("troupe.yml", "agents:\n  coder:\n    $ref: file:coder.yaml\n    model: opus\n")
    assert theatre.config("get", "agents.coder.model").out == "opus\n"


def test_text_include_is_validated_as_a_string(theatre: Theatre) -> None:
    write_schema(theatre, {"properties": {"p": {"type": "string", "maxLength": 3}}})
    theatre.write("p.md", "too long\n")
    theatre.write("troupe.yml", "p: file:p.md\n")
    assert_failed(theatre.config("get", "p"), 4, "troupe.schema.json")


def test_watch_reports_invalid_then_recovers(
    theatre: Theatre, start_watch: Callable[..., Watcher]
) -> None:
    write_schema(theatre)
    theatre.write("troupe.yml", "temperature: 0.2\n")
    watcher = start_watch()
    theatre.write("troupe.yml", "temperature: warm\n")
    deadline = time.monotonic() + 5
    while "troupe.schema.json" not in watcher.err and time.monotonic() < deadline:
        time.sleep(0.05)
    assert "troupe.schema.json" in watcher.err
    since = time.monotonic()
    theatre.write("troupe.yml", "temperature: 0.7\n")

    def recorded(events: list[dict[str, Any]]) -> bool:
        return any((e["path"], e["new"]) == ("temperature", 0.7) for e in events)

    wait_for_history(theatre, recorded, since)
    assert watcher.running()
