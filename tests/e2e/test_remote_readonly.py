"""Remote content is read-only: a change to it exits 3 and names the include line to change
instead; new keys become local overrides (spec US2, FR-610 to FR-613, D-60, D-70)."""

import pytest

from tests.conftest import Theatre, Web, assert_failed, assert_refused, assert_set

CODER = "model: opus\ntools: [git]\nsteps:\n- name: build\n"


@pytest.fixture
def url(web: Web) -> str:
    web.write("coder.yaml", CODER)
    return web.url("coder.yaml")


def main(url: str) -> str:
    return f'# team config\nagents:\n  coder: "{url}"  # team\n'


def assert_remote_refused(
    theatre: Theatre, files: dict[str, str], path: str, value: str, url: str, where: str, line: int
) -> None:
    """Exit 3, stderr naming the include string, its file and line; no file or event changes."""
    for name, content in files.items():
        theatre.write(name, content)
    events = theatre.events()
    before = theatre.snapshot()
    result = theatre.config("set", path, value)
    assert_failed(result, 3, url)
    assert where in result.err and f"line {line} " in result.err, result
    assert theatre.snapshot() == before
    assert theatre.events() == events


def test_changing_a_remote_value_names_the_include_line(theatre: Theatre, url: str) -> None:
    assert_remote_refused(
        theatre, {"troupe.yml": main(url)}, "agents.coder.model", "sonnet", url,
        ".troupe/troupe.yml", 3,
    )  # fmt: skip


def test_a_new_key_becomes_a_local_override(theatre: Theatre, url: str) -> None:
    assert_set(
        theatre,
        {"troupe.yml": main(url)},
        "agents.coder.temperature",
        "0.3",
        {
            "troupe.yml": (
                f'# team config\nagents:\n  coder:  # team\n    $ref: "{url}"\n'
                "    temperature: 0.3\n"
            )
        },
    )
    assert theatre.config("get", "agents.coder.temperature").out == "0.3\n"


def test_a_local_override_changes(theatre: Theatre, url: str) -> None:
    files = {"troupe.yml": f"agents:\n  coder:\n    $ref: {url}\n    model: sonnet\n"}
    expected = f"agents:\n  coder:\n    $ref: {url}\n    model: haiku\n"
    assert_set(theatre, files, "agents.coder.model", "haiku", {"troupe.yml": expected})


@pytest.mark.parametrize(
    ("path", "value"), [("agents.coder.tools.1", "lint"), ("agents.coder.steps.0.retries", "3")]
)
def test_list_changes_in_remote_content_are_refused(
    theatre: Theatre, url: str, path: str, value: str
) -> None:
    assert_remote_refused(
        theatre, {"troupe.yml": main(url)}, path, value, url, ".troupe/troupe.yml", 3
    )


def test_a_remote_text_include_is_refused(theatre: Theatre, web: Web) -> None:
    web.write("system.md", "Be brief.\n")
    url = web.url("system.md")
    assert_remote_refused(
        theatre, {"troupe.yml": f"prompt: {url}\n"}, "prompt", "New text", url,
        ".troupe/troupe.yml", 1,
    )  # fmt: skip


def test_the_local_file_holding_the_url_is_named(theatre: Theatre, url: str) -> None:
    files = {"troupe.yml": "agents: file:agents.yaml\n", "agents.yaml": f"# x\ncoder: {url}\n"}
    assert_remote_refused(
        theatre, files, "agents.coder.model", "sonnet", url, ".troupe/agents.yaml", 2
    )


def test_in_include_new_key_is_refused(theatre: Theatre, url: str) -> None:
    files = {"troupe.yml": main(url)}
    assert_refused(
        theatre, files, "agents.coder.temperature", "0.3", 3, url, options=("--in-include",)
    )


def test_nested_remote_new_key_names_the_outermost_include(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", f"b: {web.url('b.yaml')}\n")
    web.write("b.yaml", "k: 1\n")
    outer = web.url("a.yaml")
    assert_remote_refused(
        theatre, {"troupe.yml": f"x: {outer}\n"}, "x.b.new", "2", outer, ".troupe/troupe.yml", 1
    )


def test_replacing_a_whole_remote_include_is_refused(theatre: Theatre, url: str) -> None:
    assert_refused(theatre, {"troupe.yml": main(url)}, "agents.coder", "{a: 1}", 3, url)


def test_expanding_an_alias_in_remote_content_is_refused(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", "d: &x {m: 1}\ne: *x\n")
    url = web.url("a.yaml")
    assert_refused(
        theatre, {"troupe.yml": f"agents: {url}\n"}, "agents.e.m", "2", 3, url,
        options=("--expand-alias",),
    )  # fmt: skip


def test_the_include_on_the_path_taken_is_named(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    url = web.url("x.yaml")
    files = {"troupe.yml": f"a: {url}\nb: {url}\n"}
    assert_remote_refused(theatre, files, "b.k", "9", url, ".troupe/troupe.yml", 2)


def test_quoted_include_is_shown_without_its_quotes(theatre: Theatre, url: str) -> None:
    theatre.write("troupe.yml", f"a: '{url}'\n")
    result = theatre.config("set", "a.model", "x")
    assert f"remote include {url} (" in result.err, result


def test_mapping_form_remote_include_names_the_ref_line(theatre: Theatre, web: Web) -> None:
    web.write("c.yaml", "model: opus\n")
    url = web.url("c.yaml")
    files = {"troupe.yml": f"a: 1\ncoder:\n  $ref: {url}\n  effort: low\n"}
    assert_remote_refused(theatre, files, "coder.model", "x", url, ".troupe/troupe.yml", 3)
    assert_set(
        theatre, {}, "coder.effort", "high",
        {"troupe.yml": f"a: 1\ncoder:\n  $ref: {url}\n  effort: high\n"},
    )  # fmt: skip
