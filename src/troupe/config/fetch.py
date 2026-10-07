"""Fetching a remote include (spec FR-601, FR-602, D-63; research U-3).

Redirects are followed; only a 2xx final status succeeds; the whole response must arrive within
FETCH_TIMEOUT seconds and be UTF-8. No authentication, no cache between commands, no retries;
proxies come from the environment, as urllib does by default. Every failure is a LoadError
(exit 4) naming the URL and where it is included from.
"""

import time
import urllib.error
import urllib.request

from troupe.errors import LoadError

FETCH_TIMEOUT = 10.0  # seconds for the whole response (spec D-63)
_CHUNK = 64 * 1024


class FetchError(LoadError):
    """A remote include could not be fetched or read (exit 4). `watch` tells it from a broken
    local file: it does not poll URLs (spec D-65)."""


def fetch(url: str, included_from: str) -> str:
    """The body of `url` as text; `included_from` names the file (or URL) holding the include."""

    def failed(reason: str) -> FetchError:
        return FetchError(f"{included_from}: cannot fetch {url}: {reason}")

    deadline = time.monotonic() + FETCH_TIMEOUT
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as response:
            status = int(response.status)
            if not 200 <= status < 300:
                raise failed(f"HTTP {status}")
            chunks: list[bytes] = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise failed(f"no complete response within {FETCH_TIMEOUT:g} seconds")
                _set_timeout(response, remaining)
                chunk = response.read1(_CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
    except urllib.error.HTTPError as error:
        raise failed(f"HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise failed(str(error.reason)) from None
    except TimeoutError:
        raise failed(f"no complete response within {FETCH_TIMEOUT:g} seconds") from None
    except OSError as error:
        raise failed(error.strerror or str(error)) from None
    if time.monotonic() > deadline:
        raise failed(f"no complete response within {FETCH_TIMEOUT:g} seconds")
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError:
        raise failed("the response is not valid UTF-8") from None


def _set_timeout(response: object, seconds: float) -> None:
    """Bound the next read by the time left, so a slow trickle cannot outlast the deadline."""
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if sock is not None:
        sock.settimeout(seconds)
