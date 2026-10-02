"""Replacing a scalar with a scalar: only the value's bytes change (FR-020, FR-026, FR-028)."""

from tests.conftest import Theatre, assert_set

MAIN = """\
# Theatre configuration — reviewed by hand
model:
  name: 'coder'
  temperature: 0.2
  label: "plain text"
  enabled: true

tools:
  - git
  - shell
"""


def _expect(old: str, new: str) -> str:
    assert old in MAIN
    return MAIN.replace(old, new, 1)


def test_plain_number_replaced(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.temperature",
        "0.75",
        {"troupe.yml": _expect("temperature: 0.2", "temperature: 0.75")},
    )


def test_single_quoted_style_kept(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.name",
        "reviewer",
        {"troupe.yml": _expect("'coder'", "'reviewer'")},
    )


def test_double_quoted_style_kept(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.label",
        "other words",
        {"troupe.yml": _expect('"plain text"', '"other words"')},
    )


def test_quoted_style_that_cannot_represent_a_number_falls_back_to_plain(theatre: Theatre) -> None:
    assert_set(
        theatre, {"troupe.yml": MAIN}, "model.name", "3", {"troupe.yml": _expect("'coder'", "3")}
    )


def test_plain_style_that_cannot_represent_a_string_falls_back_to_single(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.temperature",
        '"2"',
        {"troupe.yml": _expect("temperature: 0.2", "temperature: '2'")},
    )


def test_plain_value_that_would_read_as_a_boolean_is_quoted(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.enabled",
        '"true"',
        {"troupe.yml": _expect("enabled: true", "enabled: 'true'")},
    )


def test_single_quoted_falls_back_to_double_for_control_characters(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.name",
        '"bell\\a"',
        {"troupe.yml": _expect("'coder'", '"bell\\a"')},
    )


def test_double_quoted_writes_non_ascii_literally(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.label",
        '"café \\"best\\" 🎭"',
        {"troupe.yml": _expect('"plain text"', '"café \\"best\\" 🎭"')},
    )


def test_list_item(theatre: Theatre) -> None:
    assert_set(
        theatre, {"troupe.yml": MAIN}, "tools.0", "hg", {"troupe.yml": _expect("  - git", "  - hg")}
    )


def test_boolean_and_null(theatre: Theatre) -> None:
    assert_set(
        theatre,
        {"troupe.yml": MAIN},
        "model.enabled",
        "null",
        {"troupe.yml": _expect("enabled: true", "enabled: null")},
    )


def test_set_that_changes_nothing_writes_nothing(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 0x1F  # hex\nb: 'x'\n")
    events = len(theatre.history())
    before = theatre.snapshot()
    for path, value in (("a", "31"), ("b", "x")):
        assert theatre.config("set", path, value).code == 0
    assert theatre.snapshot() == before
    assert len(theatre.history()) == events


def test_scalars_inside_flow_collections(theatre: Theatre) -> None:
    files = {"troupe.yml": "limits: {cpu: 2, mem: '1G'}  # caps\ntools: [git, shell]\n"}
    assert_set(
        theatre,
        files,
        "limits.mem",
        "2G",
        {"troupe.yml": "limits: {cpu: 2, mem: '2G'}  # caps\ntools: [git, shell]\n"},
    )


def test_flow_scalar_that_needs_quoting_in_flow(theatre: Theatre) -> None:
    files = {"troupe.yml": "tools: [git, shell]\n"}
    assert_set(theatre, files, "tools.1", "a,b", {"troupe.yml": "tools: [git, 'a,b']\n"})


def test_multi_line_plain_scalar_replaced_whole(theatre: Theatre) -> None:
    files = {"troupe.yml": "desc: a long plain\n  scalar over lines\nnext: 1\n"}
    assert_set(theatre, files, "desc", "short", {"troupe.yml": "desc: short\nnext: 1\n"})


def test_crlf_file_keeps_crlf(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: 1\r\nb:\r\n  c: x\r\n"}
    assert_set(theatre, files, "b.c", "y", {"troupe.yml": "a: 1\r\nb:\r\n  c: y\r\n"})


def test_file_without_final_newline(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1"}, "a", "22", {"troupe.yml": "a: 22"})


def test_empty_value_gets_a_value(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\nb: 1\n"}
    assert_set(theatre, files, "a", "x", {"troupe.yml": "a: x\nb: 1\n"})


def test_keys_with_explicit_quotes_are_found(theatre: Theatre) -> None:
    files = {"troupe.yml": '"quoted key": 1\n'}
    assert_set(theatre, files, "quoted key", "2", {"troupe.yml": '"quoted key": 2\n'})
