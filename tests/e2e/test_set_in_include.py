"""`set --in-include`: a new key goes into the included file, by step 1's rule (step 5 CR-B,
FR-460 to FR-466, D-50, D-51)."""

from pathlib import Path

import pytest

from tests.conftest import Theatre, assert_set

FLAG = ("--in-include",)
SCALAR_FORM = "agents:\n  coder: file:agents/coder.yaml  # c\n"


def test_new_key_goes_into_the_included_file(theatre: Theatre) -> None:
    files = {"troupe.yml": SCALAR_FORM, "agents/coder.yaml": "model: sonnet\n"}
    expected = {"agents/coder.yaml": "model: sonnet\ntemperature: 0.3\n"}
    assert_set(theatre, files, "agents.coder.temperature", "0.3", expected, FLAG)


def test_missing_intermediates_are_created_in_the_included_file(theatre: Theatre) -> None:
    files = {"troupe.yml": SCALAR_FORM, "agents/coder.yaml": "model: sonnet\n"}
    expected = {"agents/coder.yaml": "model: sonnet\nlimits:\n  retries: 3\n"}
    assert_set(theatre, files, "agents.coder.limits.retries", "3", expected, FLAG)


MERGED = "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    limits: {timeout: 30}\n"
SHARED_LIMITS = "limits:\n  retries: 2\n"


def test_merged_ancestor_gets_the_key_in_its_shared_part(theatre: Theatre) -> None:
    files = {"troupe.yml": MERGED, "agents/coder.yaml": SHARED_LIMITS}
    expected = {"agents/coder.yaml": SHARED_LIMITS + "  backoff: 2\n"}
    assert_set(theatre, files, "agents.coder.limits.backoff", "2", expected, FLAG)


def test_without_the_flag_the_same_key_is_an_override(theatre: Theatre) -> None:
    files = {"troupe.yml": MERGED, "agents/coder.yaml": SHARED_LIMITS}
    expected = {"troupe.yml": MERGED.replace("{timeout: 30}", "{timeout: 30, backoff: 2}")}
    assert_set(theatre, files, "agents.coder.limits.backoff", "2", expected)


def test_nested_includes_write_the_deepest_file(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "agents:\n  coder: file:coder.yaml\n",
        "coder.yaml": "model: file:model.yaml\n",
        "model.yaml": "name: m\n",
    }
    expected = {"model.yaml": "name: m\ntemp: 1\n"}
    assert_set(theatre, files, "agents.coder.model.temp", "1", expected, FLAG)


def test_mapping_form_without_overrides_writes_the_included_file(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: {$ref: file:c.yaml}\n", "c.yaml": "a: 1\n"}
    assert_set(theatre, files, "coder.t", "1", {"c.yaml": "a: 1\nt: 1\n"}, FLAG)


def test_ancestor_only_in_an_override_stays_in_that_file(theatre: Theatre) -> None:
    main = "coder:\n  $ref: file:c.yaml\n  extra:\n    a: 1\n"
    files = {"troupe.yml": main, "c.yaml": "x: 1\n"}
    assert_set(theatre, files, "coder.extra.b", "2", {"troupe.yml": main + "    b: 2\n"}, FLAG)


def test_flow_mapping_in_the_included_file(theatre: Theatre) -> None:
    files = {"troupe.yml": SCALAR_FORM, "agents/coder.yaml": "{model: x}\n"}
    expected = {"agents/coder.yaml": "{model: x, temperature: 0.3}\n"}
    assert_set(theatre, files, "agents.coder.temperature", "0.3", expected, FLAG)


def test_file_included_twice_gets_the_key_under_both_paths(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: file:common.yaml\nb: file:common.yaml\n", "common.yaml": "x: 1\n"}
    assert_set(theatre, files, "a.y", "2", {"common.yaml": "x: 1\ny: 2\n"}, FLAG)
    assert theatre.config("get", "b.y").out == "2\n"
    changes = [(e["op"], e["path"], e["new"]) for e in theatre.history() if e["op"] != "import"]
    assert changes == [("set", "a.y", 2), ("set", "b.y", 2)]


def test_step_1_fixture_passes_again_with_the_flag(theatre: Theatre) -> None:
    """SC-462: step 1's new-key-in-include result, which CR-A changed, is what the flag gives."""
    files = {
        "troupe.yml": "agents:\n  coder: file:agents/coder.yaml\n",
        "agents/coder.yaml": "model: sonnet\n",
    }
    expected = {"agents/coder.yaml": "model: sonnet\nretries: 3\n"}
    assert_set(theatre, files, "agents.coder.retries", "3", expected, FLAG)


# D-50: on anything but a new key under included content, the flag changes nothing.

OVERRIDDEN = (
    "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    model: sonnet\n"
    "    prompt: file:p.md\nown:\n  a: 1\n"
)
SHARED = "model: opus\neffort: low\ntools: [git]\nsteps:\n  - name: build\n"


def _outcome(root: Path, path: str, value: str, *options: str) -> tuple[object, ...]:
    theatre = Theatre(root)
    for name, content in {
        "troupe.yml": OVERRIDDEN,
        "agents/coder.yaml": SHARED,
        "p.md": "old\n",
    }.items():
        theatre.write(name, content)
    result = theatre.config("set", path, value, *options)
    events = [
        (e["op"], e["path"], e["old"], e["new"], e["via"], e["reason"]) for e in theatre.events()
    ]
    return result.code, result.out, theatre.snapshot(), events


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("agents.coder.model", "haiku"),  # existing value, overridden
        ("agents.coder.effort", "high"),  # existing value, not overridden
        ("own.b", "2"),  # new key, ancestor in the main file
        ("agents.coder.tools.1", "lint"),  # list append in the shared file
        ("agents.coder.steps.0.retries", "3"),  # key inside a list item of the shared file
        ("agents.coder.prompt", "new"),  # text include target
        ("agents.coder", "{a: 1}"),  # refused either way
    ],
)
def test_flag_changes_nothing_else(tmp_path: Path, path: str, value: str) -> None:
    plain = _outcome(tmp_path / "plain", path, value)
    flagged = _outcome(tmp_path / "flag", path, value, *FLAG)
    assert flagged == plain
    expected_code = 3 if path == "agents.coder" else 0
    assert plain[0] == expected_code
