"""Usage errors → exit 2 with nothing on stdout."""

from pathlib import Path

import pytest

from tests.conftest import Theatre, assert_failed


@pytest.fixture
def ready(theatre: Theatre) -> Theatre:
    theatre.write("troupe.yml", "a: 1\n")
    return theatre


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("config",),
        ("config", "frobnicate"),
        ("config", "get"),
        ("config", "get", "a", "extra"),
        ("config", "get", "a", "--sources"),
        ("config", "get", "a", "--bogus"),
        ("config", "set", "a"),
        ("config", "show", "a", "extra"),
        ("config", "show", "a", "--bogus"),
    ],
)
def test_bad_command_lines_exit_2(ready: Theatre, args: tuple[str, ...]) -> None:
    result = ready.run(*args)
    assert result.code == 2, result
    assert result.out == ""
    assert result.err != ""


def test_invalid_value_exits_2_naming_the_value(ready: Theatre) -> None:
    before = ready.snapshot()
    assert_failed(ready.config("set", "a", "[unclosed"), 2, "[unclosed")
    assert ready.snapshot() == before


@pytest.mark.parametrize("path", ["a..b", ".a", "a."])
def test_empty_path_segment_exits_2_naming_the_path(ready: Theatre, path: str) -> None:
    assert_failed(ready.config("get", path), 2, path)


def test_theatre_option_before_positionals(ready: Theatre) -> None:
    result = ready.run("config", "get", "--theatre", str(ready.root), "a", theatre=False)
    assert (result.code, result.out) == (0, "1\n")


def test_theatre_defaults_to_current_directory(ready: Theatre) -> None:
    result = ready.run("config", "get", "a", theatre=False, cwd=ready.root)
    assert (result.code, result.out) == (0, "1\n")


def test_theatre_defaults_to_environment_variable(ready: Theatre, tmp_path: Path) -> None:
    other = Theatre(tmp_path / "other")
    other.write("troupe.yml", "a: 2\n")
    env = {"TROUPE_THEATRE": str(ready.root)}
    result = ready.run("config", "get", "a", theatre=False, cwd=other.root, env=env)
    assert (result.code, result.out) == (0, "1\n")
    result = ready.run("config", "get", "a", "--theatre", str(other.root), theatre=False, env=env)
    assert (result.code, result.out) == (0, "2\n")
    result = ready.run("config", "get", "a", theatre=False, env={"TROUPE_THEATRE": ""})
    assert (result.code, result.out) == (0, "1\n")


def test_negative_number_value(ready: Theatre) -> None:
    assert ready.config("set", "a", "-3").code == 0
    assert ready.read("troupe.yml") == "a: -3\n"
