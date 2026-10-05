"""Lists stay in the file that holds them: overrides cannot address list items (spec US4,
FR-424)."""

from tests.conftest import Theatre, assert_set

SCALAR_FORM = "agents:\n  coder: file:agents/coder.yaml\n"
OVERRIDES = (
    "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    tools: [lint]\n"
    "    steps:\n      - name: x\n"
)
CODER = "tools: [git, shell]\nsteps:\n  - name: build\n"


def test_append_goes_to_the_included_file_holding_the_list(theatre: Theatre) -> None:
    files = {"troupe.yml": SCALAR_FORM, "agents/coder.yaml": CODER}
    expected = CODER.replace("shell]", "shell, lint]")
    assert_set(theatre, files, "agents.coder.tools.2", "lint", {"agents/coder.yaml": expected})


def test_key_inside_an_included_list_item_is_written_there(theatre: Theatre) -> None:
    files = {"troupe.yml": SCALAR_FORM, "agents/coder.yaml": CODER}
    expected = CODER + "    retries: 3\n"
    assert_set(theatre, files, "agents.coder.steps.0.retries", "3", {"agents/coder.yaml": expected})


def test_append_to_an_override_list_goes_to_the_including_file(theatre: Theatre) -> None:
    files = {"troupe.yml": OVERRIDES, "agents/coder.yaml": CODER}
    expected = OVERRIDES.replace("[lint]", "[lint, fmt]")
    assert_set(theatre, files, "agents.coder.tools.1", "fmt", {"troupe.yml": expected})


def test_key_inside_an_item_of_an_override_list(theatre: Theatre) -> None:
    files = {"troupe.yml": OVERRIDES, "agents/coder.yaml": CODER}
    expected = OVERRIDES + "        r: 1\n"
    assert_set(theatre, files, "agents.coder.steps.0.r", "1", {"troupe.yml": expected})
