"""Usage errors → exit 2 with nothing on stdout."""

from pathlib import Path

import pytest

from tests.conftest import Theatre, assert_failed
from troupe.config.store import STORE_FILENAME


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
        ("config", "set", "a", "2", "--reason"),
        ("config", "get", "a", "--reason", "x"),
        ("config", "show", "--reason", "x"),
        ("config", "history", "--reason", "x"),
        ("config", "watch", "--reason", "x"),
    ],
)
def test_bad_command_lines_exit_2(ready: Theatre, args: tuple[str, ...]) -> None:
    before = ready.snapshot()
    result = ready.run(*args)
    assert result.code == 2, result
    assert result.out == ""
    assert result.err != ""
    assert ready.snapshot() == before
    assert not (ready.root / ".troupe" / STORE_FILENAME).exists()


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


@pytest.mark.parametrize(
    "args",
    [
        ("get", "a", "--in-include"),
        ("show", "--in-include"),
        ("history", "--in-include"),
        ("watch", "--in-include"),
        ("set", "a", "2", "--in-include=yes"),
    ],
)
def test_in_include_only_as_a_flag_of_set(ready: Theatre, args: tuple[str, ...]) -> None:
    """Step 5 CR-B FR-466: every other use is an unknown option or a usage error."""
    before = ready.snapshot()
    assert_failed(ready.config(*args), 2, "--in-include")
    assert ready.snapshot() == before
    assert not (ready.root / ".troupe" / STORE_FILENAME).exists()


@pytest.mark.parametrize(
    "args",
    [
        ("set", "--in-include", "a", "2"),
        ("set", "a", "2", "--in-include"),
        ("set", "a", "2", "--in-include", "--in-include"),
    ],
)
def test_in_include_in_any_position_and_repeated(ready: Theatre, args: tuple[str, ...]) -> None:
    """Step 5 CR-B FR-460."""
    result = ready.config(*args)
    assert (result.code, result.out, result.err) == (0, "", ""), result
    assert ready.config("get", "a").out == "2\n"


def test_in_include_with_reason(ready: Theatre) -> None:
    """Step 5 CR-B FR-460, FR-465: the flag combines with --reason."""
    result = ready.config("set", "a", "3", "--in-include", "--reason", "why")
    assert result.code == 0, result
    assert ready.events()[-1]["reason"] == "why"
