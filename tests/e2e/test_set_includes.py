"""Writing through includes (FR-020, FR-021, FR-024)."""

from tests.conftest import Theatre, assert_refused, assert_set

MAIN = "agents:\n  coder: file:agents/coder.yaml\nprompt: file:prompts/system.md\n"
CODER = "model: sonnet  # m\n"


def _files() -> dict[str, str]:
    return {"troupe.yml": MAIN, "agents/coder.yaml": CODER, "prompts/system.md": "Be terse.\n"}


def test_value_in_a_yaml_include_changes_only_that_file(theatre: Theatre) -> None:
    assert_set(
        theatre,
        _files(),
        "agents.coder.model",
        "opus",
        {"agents/coder.yaml": "model: opus    # m\n"},
    )


def test_replacing_a_whole_included_value_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, _files(), "agents.coder", "{model: x}", 3, "agents.coder")


def test_replacing_a_whole_included_value_with_a_scalar_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, _files(), "agents.coder", "none", 3, "agents.coder")


def test_text_include_target_becomes_the_value_exactly(theatre: Theatre) -> None:
    assert_set(
        theatre, _files(), "prompt", '"New prompt\\n"', {"prompts/system.md": "New prompt\n"}
    )


def test_text_include_without_trailing_newline(theatre: Theatre) -> None:
    assert_set(theatre, _files(), "prompt", "short", {"prompts/system.md": "short"})


def test_crlf_text_target_keeps_crlf(theatre: Theatre) -> None:
    theatre.write("prompts/system.md", b"old\r\ntext\r\n")
    files = {"troupe.yml": MAIN, "agents/coder.yaml": CODER}
    assert_set(theatre, files, "prompt", '"a\\nb\\n"', {"prompts/system.md": "a\r\nb\r\n"})


def test_text_include_given_a_non_string_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, _files(), "prompt", "3", 3, "prompt")


def test_text_include_in_an_included_file_resolves_relative_to_it(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "a: file:sub/x.yaml\n",
        "sub/x.yaml": "p: file:p.md\n",
        "sub/p.md": "old",
    }
    assert_set(theatre, files, "a.p", "new", {"sub/p.md": "new"})


def test_file_included_twice_changes_once_and_both_paths_read_it(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: file:common.yaml\nb: file:common.yaml\n", "common.yaml": "x: 1\n"}
    assert_set(theatre, files, "a.x", "2", {"common.yaml": "x: 2\n"})
    assert theatre.config("show", "b.x").out == "2\n"
    events = [(e["op"], e["path"], e["new"]) for e in theatre.history() if e["op"] != "import"]
    assert events == [("set", "a.x", 2), ("set", "b.x", 2)]


def test_text_file_included_twice(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: file:t.md\nb: file:t.md\n", "t.md": "x"}
    assert_set(theatre, files, "b", "y", {"t.md": "y"})


def test_value_set_to_a_text_include_string(theatre: Theatre) -> None:
    files = {"troupe.yml": "p: x  # prompt\n", "o.md": "other\n"}
    assert_set(theatre, files, "p", "file:o.md", {"troupe.yml": "p: file:o.md # prompt\n"})
    assert theatre.config("show", "p").out == "other\n"
    assert theatre.history()[-1] == {
        "seq": 2,
        "op": "set",
        "path": "p",
        "old": "x",
        "new": "other\n",
    }


def test_value_set_to_a_yaml_include_string(theatre: Theatre) -> None:
    files = {"troupe.yml": "agents:\n  coder: none\n", "c.yaml": "model: m\n"}
    assert_set(
        theatre,
        files,
        "agents.coder",
        "file:c.yaml",
        {"troupe.yml": "agents:\n  coder: file:c.yaml\n"},
    )
    assert theatre.config("show", "agents.coder.model").out == "m\n"


def test_include_string_inside_a_new_collection(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1\n", "o.md": "hi"}
    assert_set(
        theatre, files, "b", "{p: 'file:o.md'}", {"troupe.yml": "a: 1\nb:\n  p: file:o.md\n"}
    )


def test_include_string_with_a_missing_target_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, {"troupe.yml": "p: x\n"}, "p", "file:gone.md", 3, "gone.md")


def test_include_string_that_would_form_a_cycle_is_refused(theatre: Theatre) -> None:
    assert_refused(theatre, {"troupe.yml": "p: x\n"}, "p", "file:troupe.yml", 3, "troupe.yml")
