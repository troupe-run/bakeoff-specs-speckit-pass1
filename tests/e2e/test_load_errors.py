"""Configuration that cannot be loaded → exit 4, naming the file; nothing is changed."""

from tests.conftest import Theatre, assert_failed


def _assert_load_error(theatre: Theatre, mention: str) -> None:
    before = theatre.snapshot()
    for args in (("show", "a"), ("set", "a", "1"), ("history",)):
        assert_failed(theatre.config(*args), 4, mention)
    assert theatre.snapshot() == before


def test_missing_config_file(theatre: Theatre) -> None:
    _assert_load_error(theatre, "troupe.yml")


def test_both_config_files(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    theatre.write("troupe.yaml", "a: 2\n")
    _assert_load_error(theatre, "troupe.yaml")


def test_troupe_yaml_alone_is_the_config_file(theatre: Theatre) -> None:
    theatre.write("troupe.yaml", "a: 1\n")
    assert theatre.config("show", "a").out == "1\n"


def test_yaml_syntax_error_names_the_file(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\nb: [unclosed\n")
    _assert_load_error(theatre, "troupe.yml")


def test_syntax_error_in_an_included_file_names_that_file(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:inc/broken.yaml\n")
    theatre.write("inc/broken.yaml", "x: [\n")
    _assert_load_error(theatre, "broken.yaml")


def test_top_level_list_cannot_be_loaded(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "- a\n- b\n")
    _assert_load_error(theatre, "troupe.yml")


def test_missing_include_target_names_the_target(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:missing.yaml\n")
    _assert_load_error(theatre, "missing.yaml")


def test_missing_text_include_target(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "prompt: file:prompts/none.md\n")
    _assert_load_error(theatre, "none.md")


def test_include_cycle(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:a.yaml\n")
    theatre.write("a.yaml", "b: file:b.yaml\n")
    theatre.write("b.yaml", "c: file:a.yaml\n")
    _assert_load_error(theatre, "a.yaml")


def test_self_include(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:troupe.yml\n")
    _assert_load_error(theatre, "troupe.yml")


def test_nonexistent_theatre_directory(theatre: Theatre) -> None:
    missing = theatre.root / "nowhere"
    result = theatre.run("config", "show", "a", "--theatre", str(missing), theatre=False)
    assert_failed(result, 4, "nowhere")
    assert not missing.exists()


def test_empty_config_file_loads_as_an_empty_mapping(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "")
    assert_failed(theatre.config("show", "x"), 5, "x")
    assert theatre.history() == []


def test_diamond_include_is_not_a_cycle(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:common.yaml\nb: file:common.yaml\n")
    theatre.write("common.yaml", "x: 1\n")
    assert theatre.config("show", "b.x").out == "1\n"
