"""A remote include that cannot be fetched or read → exit 4, naming the URL and the file holding
the include; nothing changes (spec FR-602, FR-603, FR-650, D-61, D-63)."""

import time

import pytest

from tests.conftest import Theatre, Web, assert_failed, closed_port_url


def _assert_fetch_error(theatre: Theatre, url: str, holder: str = "troupe.yml") -> None:
    before = theatre.snapshot()
    result = theatre.config("get", "a")
    assert_failed(result, 4, url)
    assert holder in result.err, result
    assert theatre.snapshot() == before


def test_connection_refused(theatre: Theatre) -> None:
    url = closed_port_url("a.yaml")
    theatre.write("troupe.yml", f"a: {url}\n")
    _assert_fetch_error(theatre, url)


@pytest.mark.parametrize("code", [404, 500])
def test_non_success_status(theatre: Theatre, web: Web, code: int) -> None:
    url = web.url(f"status/{code}")
    theatre.write("troupe.yml", f"a: {url}\n")
    _assert_fetch_error(theatre, url)


def test_non_utf8_body(theatre: Theatre, web: Web) -> None:
    web.write("a.md", b"\xff\xfe")
    theatre.write("troupe.yml", f"a: {web.url('a.md')}\n")
    _assert_fetch_error(theatre, web.url("a.md"))


def test_invalid_yaml_body(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", "a: [\n")
    theatre.write("troupe.yml", f"a: {web.url('a.yaml')}\n")
    _assert_fetch_error(theatre, web.url("a.yaml"))


def test_stall_exceeds_ten_seconds(theatre: Theatre, web: Web) -> None:
    # Slow by nature: waits out troupe's 10-second fetch limit.
    theatre.write("troupe.yml", f"a: {web.url('stall')}\n")
    started = time.monotonic()
    _assert_fetch_error(theatre, web.url("stall"))
    assert time.monotonic() - started < 14


def test_slow_trickle_exceeds_ten_seconds(theatre: Theatre, web: Web) -> None:
    # Slow by nature: a body sent one byte a second never completes within the limit.
    web.write("long.md", "x" * 20)
    theatre.write("troupe.yml", f"a: {web.url('slow/long.md')}\n")
    started = time.monotonic()
    _assert_fetch_error(theatre, web.url("slow/long.md"))
    assert time.monotonic() - started < 14


def test_file_include_inside_remote_content(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", "x: file:local.yaml\n")
    theatre.write("local.yaml", "secret: 1\n")
    theatre.write("troupe.yml", f"a: {web.url('a.yaml')}\n")
    before = theatre.snapshot()
    result = theatre.config("get", "a.x.secret")
    assert_failed(result, 4, web.url("a.yaml"))
    assert "file:local.yaml" in result.err
    assert theatre.snapshot() == before


def test_url_include_cycle(theatre: Theatre, web: Web) -> None:
    web.write("a.yaml", f"b: {web.url('b.yaml')}\n")
    web.write("b.yaml", f"a: {web.url('a.yaml')}\n")
    theatre.write("troupe.yml", f"a: {web.url('a.yaml')}\n")
    result = theatre.config("get", "a")
    assert_failed(result, 4, "cycle")
    assert web.url("a.yaml") in result.err


def test_https_with_an_untrusted_certificate(theatre: Theatre, web_tls: Web) -> None:
    web_tls.write("a.yaml", "k: 1\n")
    theatre.write("troupe.yml", f"a: {web_tls.url('a.yaml')}\n")
    _assert_fetch_error(theatre, web_tls.url("a.yaml"))


def test_every_command_fails_alike(theatre: Theatre, web: Web) -> None:
    url = web.url("status/404")
    theatre.write("troupe.yml", f"a: {url}\nb: 1\n")
    before = theatre.snapshot()
    for args in (("get", "b"), ("show",), ("history",), ("set", "b", "2")):
        assert_failed(theatre.config(*args), 4, url)
    assert theatre.snapshot() == before


def test_the_including_file_is_named(theatre: Theatre, web: Web) -> None:
    url = web.url("status/404")
    theatre.write("troupe.yml", "a: file:inc.yaml\n")
    theatre.write("inc.yaml", f"x: {url}\n")
    _assert_fetch_error(theatre, url, holder="inc.yaml")


def test_nested_fetch_failure_names_the_local_include(theatre: Theatre, web: Web) -> None:
    outer, inner = web.url("a.yaml"), web.url("status/404")
    web.write("a.yaml", f"b: {inner}\n")
    theatre.write("troupe.yml", f"z: 0\nx: '{outer}'\n")
    result = theatre.config("get", "z")
    assert_failed(result, 4, inner)
    assert f"included through {outer} at line 2 of" in result.err, result
    assert ".troupe/troupe.yml" in result.err


def test_nested_invalid_yaml_names_the_local_include(theatre: Theatre, web: Web) -> None:
    outer, inner = web.url("a.yaml"), web.url("b.yaml")
    web.write("a.yaml", f"b: {inner}\n")
    web.write("b.yaml", "k: [\n")
    theatre.write("troupe.yml", f"x: {outer}\n")
    result = theatre.config("get", "x")
    assert_failed(result, 4, inner)
    assert f"included through {outer} at line 1 of" in result.err, result
