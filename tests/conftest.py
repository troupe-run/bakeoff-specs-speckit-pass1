"""Shared fixtures: real theatres on disk, driven through the real `troupe` CLI."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from troupe.config.store import STORE_FILENAME

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

    def run(self, *args: str, theatre: bool = True, cwd: Path | None = None) -> "Result":
        argv = [*COMMAND, *args]
        if theatre:
            argv += ["--theatre", str(self.root)]
        done = subprocess.run(argv, capture_output=True, cwd=cwd or self.root, check=False)
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
