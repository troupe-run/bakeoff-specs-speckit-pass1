"""The fixture web server itself serves and records what step 7's tests rely on."""

import urllib.error
import urllib.request

import pytest

from tests.conftest import Web


def test_web_serves_and_records(web: Web) -> None:
    web.write("a.yaml", "x: 1\n")
    with urllib.request.urlopen(web.url("a.yaml?rev=3"), timeout=5) as response:
        assert response.read() == b"x: 1\n"
    assert web.requests == ["/a.yaml?rev=3"]


def test_status_path(web: Web) -> None:
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(web.url("status/503"), timeout=5)
    assert raised.value.code == 503


def test_redirect_path(web: Web) -> None:
    web.write("b.md", "hi")
    with urllib.request.urlopen(web.url("redirect/b.md"), timeout=5) as response:
        assert response.read() == b"hi"
