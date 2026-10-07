"""URL includes load like file includes (spec US1, FR-600 to FR-605, D-62, D-63, D-65)."""

from tests.conftest import Theatre, Web


def test_yaml_url_is_embedded(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder:\n  model: opus\n")
    theatre.write("troupe.yml", f"agents: {web.url('agents.yaml')}\n")
    result = theatre.config("get", "agents.coder.model")
    assert (result.code, result.out) == (0, "opus\n"), result


def test_other_url_is_a_text_include(theatre: Theatre, web: Web) -> None:
    web.write("prompts/system.md", "Be brief.\n")
    theatre.write("troupe.yml", f"prompt: {web.url('prompts/system.md')}\n")
    assert theatre.config("get", "prompt").out == "Be brief.\n"


def test_text_include_keeps_its_exact_text(theatre: Theatre, web: Web) -> None:
    web.write("p.txt", "a\r\nb  \r\n")
    theatre.write("troupe.yml", f"prompt: {web.url('p.txt')}\n")
    theatre.config("get", "prompt")
    assert theatre.events("prompt")[0]["new"] == "a\r\nb  \r\n"


def test_yaml_is_decided_by_the_url_path_not_the_query(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder: {model: opus}\n")
    theatre.write("troupe.yml", f"agents: {web.url('agents.yaml?rev=3')}\n")
    assert theatre.config("get", "agents.coder.model").out == "opus\n"
    assert "/agents.yaml?rev=3" in web.requests


def test_show_sources_names_the_url(theatre: Theatre, web: Web) -> None:
    url = web.url("agents.yaml")
    web.write("agents.yaml", "coder:\n  model: opus\n")
    theatre.write("troupe.yml", f"agents: {url}\nname: x\n")
    result = theatre.config("show", "--sources")
    assert result.out == (
        f"agents:\n  coder:\n    model: opus # from {url}\nname: x # from .troupe/troupe.yml\n"
    ), result


def test_overrides_apply_to_a_url_include(theatre: Theatre, web: Web) -> None:
    web.write("coder.yaml", "model: opus\neffort: low\n")
    theatre.write(
        "troupe.yml", f"agents:\n  coder: {{$ref: {web.url('coder.yaml')}, model: sonnet}}\n"
    )
    assert theatre.config("get", "agents.coder.model").out == "sonnet\n"
    assert theatre.config("get", "agents.coder.effort").out == "low\n"


def test_import_records_remote_leaves(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder:\n  model: opus\n")
    theatre.write("troupe.yml", f"agents: {web.url('agents.yaml')}\n")
    assert theatre.history() == [
        {"seq": 1, "op": "import", "path": "agents.coder.model", "old": None, "new": "opus"}
    ]


def test_quoted_url_is_an_include(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", "k: v\n")
    theatre.write("troupe.yml", f"a: '{web.url('a.yaml')}'\n")
    assert theatre.config("get", "a.k").out == "v\n"


def test_http_and_https_prefixes_only(theatre: Theatre, web: Web) -> None:
    theatre.write("troupe.yml", f"a: {web.url('a.yaml').upper()}\nb: ftp://x/y.yaml\n")
    assert theatre.config("get", "b").out == "ftp://x/y.yaml\n"
    assert web.requests == []


def test_nested_remote_include(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", f"coder: {web.url('coder.yaml')}\n")
    web.write("coder.yaml", "model: opus\n")
    theatre.write("troupe.yml", f"agents: {web.url('agents.yaml')}\n")
    assert theatre.config("get", "agents.coder.model").out == "opus\n"


def test_remote_include_from_a_local_included_file(theatre: Theatre, web: Web) -> None:
    web.write("coder.yaml", "model: opus\n")
    theatre.write("troupe.yml", "agents: file:agents.yaml\n")
    theatre.write("agents.yaml", f"coder: {web.url('coder.yaml')}\n")
    assert theatre.config("get", "agents.coder.model").out == "opus\n"


def test_same_url_twice_is_fetched_once(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    theatre.write("troupe.yml", f"a: {web.url('x.yaml')}\nb: {web.url('x.yaml')}\n")
    assert theatre.config("get", "b.k").out == "1\n"
    assert web.requests.count("/x.yaml") == 1


def test_set_rechecks_without_fetching_again(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    theatre.write("troupe.yml", f"a: {web.url('x.yaml')}\nb: 2\n")
    assert theatre.config("set", "b", "3").code == 0
    assert web.requests.count("/x.yaml") == 1


def test_fetched_on_every_command(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    theatre.write("troupe.yml", f"a: {web.url('x.yaml')}\n")
    theatre.config("get", "a.k")
    web.write("x.yaml", "k: 2\n")
    assert theatre.config("get", "a.k").out == "2\n"


def test_empty_yaml_body_is_null(theatre: Theatre, web: Web) -> None:
    web.write("e.yaml", "")
    theatre.write("troupe.yml", f"a: {web.url('e.yaml')}\n")
    assert theatre.config("get", "a").out == "null\n"


def test_empty_text_body_is_the_empty_string(theatre: Theatre, web: Web) -> None:
    web.write("e.md", "")
    theatre.write("troupe.yml", f"a: {web.url('e.md')}\n")
    theatre.config("get", "a")
    assert theatre.events("a")[0]["new"] == ""


def test_redirect_is_followed(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder: {model: opus}\n")
    theatre.write("troupe.yml", f"agents: {web.url('redirect/agents.yaml')}\n")
    assert theatre.config("get", "agents.coder.model").out == "opus\n"


def test_https_include(theatre: Theatre, web_tls: Web) -> None:
    web_tls.write("agents.yaml", "coder: {model: opus}\n")
    theatre.write("troupe.yml", f"agents: {web_tls.url('agents.yaml')}\n")
    result = theatre.run("config", "get", "agents.coder.model", env=web_tls.env)
    assert (result.code, result.out) == (0, "opus\n"), result


def test_remote_change_is_reconciled_as_a_file_change(theatre: Theatre, web: Web) -> None:
    web.write("x.yaml", "k: 1\n")
    theatre.write("troupe.yml", f"a: {web.url('x.yaml')}\n")
    theatre.config("get", "a.k")
    web.write("x.yaml", "k: 2\n")
    theatre.config("get", "a.k")
    last = theatre.events()[-1]
    assert (last["op"], last["path"], last["old"], last["new"]) == ("set", "a.k", 1, 2)
    assert last["via"] == "file"
    assert last["actor"] == {"kind": "unknown", "id": None}
