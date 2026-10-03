"""Shared fixtures: real theatres on disk, driven through the real `troupe` CLI."""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import IO, Any

import pytest

from troupe.config.store import STORE_FILENAME, ConfigStore

TROUPE = shutil.which("troupe")
COMMAND = [TROUPE] if TROUPE else [sys.executable, "-m", "troupe"]


class Theatre:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / ".troupe").mkdir(parents=True)

    def write(self, relpath: str, content: str | bytes) -> Path:
        """Write a file relative to `.troupe/` (bytes are written exactly)."""
        path = self.root / ".troupe" / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    def read(self, relpath: str) -> str:
        return (self.root / ".troupe" / relpath).read_bytes().decode("utf-8")

    def snapshot(self) -> dict[str, bytes]:
        """Exact bytes of every file under the theatre, except the event store's own files."""
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not path.name.startswith(STORE_FILENAME)
        }

    def run(
        self,
        *args: str,
        theatre: bool = True,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> "Result":
        argv = [*COMMAND, *args]
        if theatre:
            argv += ["--theatre", str(self.root)]
        environ = {k: v for k, v in os.environ.items() if k != "TROUPE_THEATRE"} | (env or {})
        done = subprocess.run(
            argv, capture_output=True, cwd=cwd or self.root, env=environ, check=False
        )
        return Result(done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8"))

    def config(self, *args: str) -> "Result":
        return self.run("config", *args)

    def history(self, path: str | None = None) -> list[dict[str, Any]]:
        result = self.config("history", *([path] if path else []))
        assert result.code == 0, result.err
        return [json.loads(line) for line in result.out.splitlines()]


class Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.code = code
        self.out = out
        self.err = err

    def __repr__(self) -> str:
        return f"Result(code={self.code}, out={self.out!r}, err={self.err!r})"


@pytest.fixture
def theatre(tmp_path: Path) -> Theatre:
    return Theatre(tmp_path / "theatre")


# `config watch` as a real background process (research S-9).

WATCH_START_TIMEOUT = 10.0
RECONCILE_WITHIN = 2.0  # the contract's promise


class _Drain:
    """Collects everything a pipe produces, on a thread, so the child never blocks on it."""

    def __init__(self, pipe: IO[bytes]) -> None:
        self._data = bytearray()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, args=(pipe,), daemon=True)
        self._thread.start()

    def _run(self, pipe: IO[bytes]) -> None:
        for chunk in iter(lambda: pipe.read1(4096), b""):  # type: ignore[attr-defined]
            with self._lock:
                self._data += chunk

    @property
    def text(self) -> str:
        with self._lock:
            return self._data.decode("utf-8")

    def join(self) -> str:
        self._thread.join(timeout=10)
        return self.text


class Watcher:
    def __init__(self, argv: list[str], cwd: Path, env: dict[str, str]) -> None:
        self.process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        assert self.process.stdout is not None and self.process.stderr is not None
        self._out = _Drain(self.process.stdout)
        self._err = _Drain(self.process.stderr)

    @property
    def out(self) -> str:
        return self._out.text

    @property
    def err(self) -> str:
        return self._err.text

    def first_line(self, timeout: float = WATCH_START_TIMEOUT) -> str:
        """The first stdout line, as soon as it is complete ("" if the process exits first)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            out = self.out
            if "\n" in out:
                return out[: out.index("\n") + 1]
            if self.process.poll() is not None:
                return self._out.join()
            time.sleep(0.01)
        raise AssertionError(f"watch printed no line within {timeout}s; stderr: {self.err!r}")

    def running(self) -> bool:
        return self.process.poll() is None

    def stop(self, sig: int = signal.SIGINT) -> Result:
        """Send `sig` and wait for the exit; returns the whole stdout and stderr."""
        if self.running():
            self.process.send_signal(sig)
        code = self.process.wait(timeout=10)
        return Result(code, self._out.join(), self._err.join())

    def kill(self) -> None:
        if self.running():
            self.process.kill()
            self.process.wait(timeout=10)


@pytest.fixture
def start_watch(theatre: Theatre) -> Iterator[Callable[..., Watcher]]:
    """Start `config watch`; returns the Watcher once it has printed its line (or exited).

    Any watcher still running when the test ends is killed.
    """
    started: list[Watcher] = []

    def start(
        *extra: str,
        theatre_arg: bool = True,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> Watcher:
        argv = [*COMMAND, "config", "watch", *extra]
        if theatre_arg:
            argv += ["--theatre", str(theatre.root)]
        environ = {k: v for k, v in os.environ.items() if k != "TROUPE_THEATRE"} | (env or {})
        watcher = Watcher(argv, cwd or theatre.root, environ)
        started.append(watcher)
        watcher.first_line()
        return watcher

    yield start
    for watcher in started:
        watcher.kill()


def recorded(theatre: Theatre) -> list[dict[str, Any]]:
    """The recorded history, read straight from the store: unlike `config history`, this never
    waits for the theatre lock and adds no process start-up time to a timing check."""
    return [
        {"seq": r.seq, "op": r.op, "path": r.path, "old": r.old, "new": r.new}
        for r in ConfigStore(theatre.root).history()
    ]


def wait_for_history(
    theatre: Theatre,
    predicate: Callable[[list[dict[str, Any]]], bool],
    since: float,
    within: float = RECONCILE_WITHIN,
) -> list[dict[str, Any]]:
    """Poll the recorded history until `predicate` holds; fail if it does not hold by
    `since + within` (`since` is a `time.monotonic()` taken just before the edit)."""
    while True:
        events = recorded(theatre)
        if predicate(events):
            return events
        if time.monotonic() > since + within:
            raise AssertionError(f"not recorded within {within}s; history: {events}")
        time.sleep(0.02)


def assert_failed(result: Result, code: int, mention: str) -> None:
    """A failure: the exit code, nothing on stdout, and stderr naming the path or file."""
    assert result.code == code, result
    assert result.out == "", result
    assert mention in result.err, result


def set_ok(theatre: Theatre, path: str, value: str) -> None:
    result = theatre.config("set", path, value)
    assert result.code == 0, result
    assert result.out == ""


def assert_set(
    theatre: Theatre, files: dict[str, str], path: str, value: str, expected: dict[str, str]
) -> None:
    """Write `files`, run `set PATH VALUE`, and check every file's exact bytes afterwards.

    `expected` lists the files that must change; every other file must keep its bytes.
    """
    for name, content in files.items():
        theatre.write(name, content)
    before = theatre.snapshot()
    set_ok(theatre, path, value)
    after = theatre.snapshot()
    wanted = dict(before)
    for name, content in expected.items():
        wanted[f".troupe/{name}"] = content.encode("utf-8")
    assert after == wanted


def assert_refused(
    theatre: Theatre, files: dict[str, str], path: str, value: str, code: int, mention: str
) -> None:
    """Write `files`, run a `set` that must fail, and check that no file changed."""
    for name, content in files.items():
        theatre.write(name, content)
    before = theatre.snapshot()
    result = theatre.config("set", path, value)
    assert_failed(result, code, mention)
    assert theatre.snapshot() == before
