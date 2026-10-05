"""Mapping-form includes that cannot load, and `$ref` that is not an include (spec FR-403,
FR-407, D-42, D-43)."""

import pytest

from tests.conftest import Theatre, assert_failed

COMMANDS = [("get", "a"), ("show",), ("set", "a", "2"), ("history",)]


def _unloadable(theatre: Theatre, main: str, mention: str) -> None:
    theatre.write("troupe.yml", main)
    before = theatre.snapshot()
    for args in COMMANDS:
        assert_failed(theatre.config(*args), 4, mention)
    assert theatre.snapshot() == before


def test_text_include_with_overrides_exits_4_on_every_command(theatre: Theatre) -> None:
    theatre.write("prompts/system.md", "Be terse.\n")
    _unloadable(theatre, "a: 1\nprompt: {$ref: file:prompts/system.md, x: 1}\n", "troupe.yml")


def test_overrides_on_a_list_include_exit_4(theatre: Theatre) -> None:
    theatre.write("l.yaml", "[a, b]\n")
    _unloadable(theatre, "a: 1\nl: {$ref: file:l.yaml, x: 1}\n", "troupe.yml")


def test_overrides_on_an_empty_include_exit_4(theatre: Theatre) -> None:
    theatre.write("e.yaml", "")
    _unloadable(theatre, "a: 1\ne: {$ref: file:e.yaml, x: 1}\n", "troupe.yml")


def test_ref_to_a_missing_file_exits_4(theatre: Theatre) -> None:
    _unloadable(theatre, "a: 1\nc: {$ref: file:gone.yaml, x: 1}\n", "gone.yaml")


def test_ref_cycle_exits_4(theatre: Theatre) -> None:
    theatre.write("c.yaml", "back: {$ref: file:troupe.yml}\n")
    _unloadable(theatre, "a: 1\nc: {$ref: file:c.yaml}\n", "troupe.yml")


@pytest.mark.parametrize("value", ["abc", "3", "[file:c.yaml]"])
def test_ref_that_is_not_an_include_is_an_ordinary_mapping(theatre: Theatre, value: str) -> None:
    theatre.write("c.yaml", "x: 1\n")
    theatre.write("troupe.yml", f"a: {{$ref: {value}, y: 2}}\n")
    assert theatre.config("get", "a.y").out == "2\n"
    assert_failed(theatre.config("get", "a.x"), 5, "a.x")
