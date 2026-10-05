"""Existing values change where they live: the override if overridden, else the file they come
from (spec US3, FR-430 to FR-432, D-44)."""

from tests.conftest import Theatre, assert_refused, assert_set

MAIN = "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    model: sonnet\n"
CODER = "model: opus\neffort: low\n"
FILES = {"troupe.yml": MAIN, "agents/coder.yaml": CODER}


def test_overridden_value_changes_the_override(theatre: Theatre) -> None:
    expected = MAIN.replace("sonnet", "haiku")
    assert_set(theatre, FILES, "agents.coder.model", "haiku", {"troupe.yml": expected})


def test_value_not_overridden_changes_in_the_included_file(theatre: Theatre) -> None:
    expected = CODER.replace("low", "high")
    assert_set(theatre, FILES, "agents.coder.effort", "high", {"agents/coder.yaml": expected})


def test_setting_the_current_value_writes_and_records_nothing(theatre: Theatre) -> None:
    assert_set(theatre, FILES, "agents.coder.model", "sonnet", {})
    assert [e["op"] for e in theatre.history()] == ["import", "import"]


MERGED = "coder:\n  $ref: file:c.yaml\n  limits:\n    timeout: 30\n"


def test_replacing_a_mapping_with_included_and_override_keys_is_refused(theatre: Theatre) -> None:
    files = {"troupe.yml": MERGED, "c.yaml": "limits:\n  retries: 2\n"}
    assert_refused(theatre, files, "coder.limits", "{a: 1}", 3, "cannot remove included keys")
    assert "coder.limits" in theatre.config("set", "coder.limits", "{a: 1}").err  # SC-404


def test_replacing_a_mapping_whose_keys_are_all_overridden_writes_the_override(
    theatre: Theatre,
) -> None:
    files = {"troupe.yml": MERGED, "c.yaml": "limits:\n  timeout: 10\n"}
    expected = "coder:\n  $ref: file:c.yaml\n  limits:\n    timeout: 60\n    retries: 1\n"
    assert_set(
        theatre, files, "coder.limits", "{timeout: 60, retries: 1}", {"troupe.yml": expected}
    )


def test_replacing_an_override_only_mapping_writes_the_override(theatre: Theatre) -> None:
    files = {"troupe.yml": MERGED, "c.yaml": "model: m\n"}
    expected = "coder:\n  $ref: file:c.yaml\n  limits:\n    retries: 1\n"
    assert_set(theatre, files, "coder.limits", "{retries: 1}", {"troupe.yml": expected})


def test_replacing_a_mapping_form_include_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, FILES, "agents.coder", "{model: x}", 3, "agents.coder")


def test_overriding_text_include_writes_its_target(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "coder:\n  $ref: file:c.yaml\n  prompt: file:p.md\n",
        "c.yaml": "prompt: old\n",
        "p.md": "x\n",
    }
    assert_set(theatre, files, "coder.prompt", "new", {"p.md": "new"})


def test_set_on_a_ref_only_text_include_writes_its_target(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: {$ref: file:p.md}\n", "p.md": "old\n"}
    assert_set(theatre, files, "p", "new", {"p.md": "new"})
