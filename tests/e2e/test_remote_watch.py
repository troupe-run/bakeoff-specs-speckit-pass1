"""`watch` with remote includes: a failed fetch is reported like a broken file, but the URL is
not polled — it is fetched again only when a watched local file changes (spec D-65, research
U-6; step 2 D-13)."""

import time
from collections.abc import Callable
from typing import Any

from tests.conftest import Theatre, Watcher, Web, wait_for_history

type Start = Callable[..., Watcher]


def _wait_for_err(watcher: Watcher, text: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while text not in watcher.err and time.monotonic() < deadline:
        time.sleep(0.05)
    assert text in watcher.err, watcher.err


def _break_fetch(theatre: Theatre, web: Web, start_watch: Start) -> tuple[Watcher, str]:
    """A watcher whose configuration's URL include has just started failing (after a local
    edit made it be fetched again)."""
    web.write("x.yaml", "k: 1\n")
    url = web.url("x.yaml")
    theatre.write("troupe.yml", f"a: 1\nx: {url}\n")
    watcher = start_watch()
    (web.root / "x.yaml").unlink()
    theatre.write("troupe.yml", f"a: 2\nx: {url}\n")
    _wait_for_err(watcher, url)
    return watcher, url


def test_watch_reports_a_failed_fetch_and_keeps_running(
    theatre: Theatre, web: Web, start_watch: Start
) -> None:
    watcher, _ = _break_fetch(theatre, web, start_watch)
    time.sleep(0.5)
    assert watcher.running()


def test_watch_does_not_poll_a_failing_url(theatre: Theatre, web: Web, start_watch: Start) -> None:
    _break_fetch(theatre, web, start_watch)
    time.sleep(0.5)  # let any in-flight retry finish
    before = len(web.requests)
    time.sleep(2.0)
    assert len(web.requests) - before <= 1, web.requests


def test_watch_recovers_after_a_local_edit_once_the_url_serves(
    theatre: Theatre, web: Web, start_watch: Start
) -> None:
    watcher, url = _break_fetch(theatre, web, start_watch)
    web.write("x.yaml", "k: 5\n")
    since = time.monotonic()
    theatre.write("troupe.yml", f"a: 3\nx: {url}\n")

    def recovered(events: list[dict[str, Any]]) -> bool:
        changed = {(e["path"], e["new"]) for e in events}
        return {("a", 3), ("x.k", 5)} <= changed

    wait_for_history(theatre, recovered, since)
    assert watcher.running()
