"""State lives only under .troupe/ and survives between commands; `uv run troupe` works."""

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import Theatre, assert_failed
from troupe.config.store import STORE_FILENAME

REPO = Path(__file__).resolve().parents[2]


def _all_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_commands_create_files_only_under_troupe_dir(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\nb: file:b.txt\n")
    theatre.write("b.txt", "text")
    outside = theatre.root / "notes.md"
    outside.write_text("mine")
    before = theatre.snapshot()
    files_before = _all_files(theatre.root)
    assert theatre.config("show", "a").code == 0
    assert theatre.config("history").code == 0
    new_files = _all_files(theatre.root) - files_before
    assert new_files and all(name.startswith(".troupe/") for name in new_files)
    assert theatre.snapshot() == before


def test_set_leaves_no_temporary_files(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert theatre.config("show", "a").code == 0
    files_before = _all_files(theatre.root)
    assert theatre.config("set", "a", "2").code == 0
    assert _all_files(theatre.root) == files_before


def test_written_file_keeps_its_permissions(theatre: Theatre) -> None:
    path = theatre.write("troupe.yml", "a: 1\n")
    path.chmod(0o640)
    assert theatre.config("set", "a", "2").code == 0
    assert path.stat().st_mode & 0o777 == 0o640


def test_uv_run_troupe_from_repository_root(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "greeting: hello\n")
    done = subprocess.run(
        ["uv", "run", "troupe", "config", "show", "greeting", "--theatre", str(theatre.root)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (done.returncode, done.stdout) == (0, "hello\n"), done.stderr


needs_permissions = pytest.mark.skipif(
    os.geteuid() == 0, reason="file permissions do not bind the root user"
)


@needs_permissions
def test_read_only_config_file_is_not_replaced(theatre: Theatre) -> None:
    path = theatre.write("troupe.yml", "a: 1\n")
    assert theatre.config("show", "a").code == 0
    path.chmod(0o444)
    before = theatre.snapshot()
    result = theatre.config("set", "a", "2")
    assert_failed(result, 3, "troupe.yml")
    assert theatre.snapshot() == before
    assert path.stat().st_mode & 0o777 == 0o444


@needs_permissions
def test_unwritable_directory_of_the_target_file_is_refused(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: file:inc/x.yaml\n")
    theatre.write("inc/x.yaml", "b: 1\n")
    assert theatre.config("show", "a.b").code == 0
    directory = theatre.root / ".troupe" / "inc"
    directory.chmod(0o555)
    try:
        before = theatre.snapshot()
        assert_failed(theatre.config("set", "a.b", "2"), 3, "x.yaml")
        assert theatre.snapshot() == before
    finally:
        directory.chmod(0o755)


@needs_permissions
def test_unwritable_troupe_directory_fails_cleanly_naming_the_store(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    directory = theatre.root / ".troupe"
    directory.chmod(0o555)
    try:
        before = theatre.snapshot()
        for args in (("show", "a"), ("set", "a", "2"), ("history",)):
            result = theatre.config(*args)
            assert_failed(result, 4, STORE_FILENAME)
            assert "Traceback" not in result.err
        assert theatre.snapshot() == before
    finally:
        directory.chmod(0o755)


@needs_permissions
def test_store_that_became_read_only_refuses_set_before_changing_files(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert theatre.config("show", "a").code == 0
    stores = list((theatre.root / ".troupe").glob(STORE_FILENAME + "*"))
    for store in stores:
        store.chmod(0o444)
    try:
        before = theatre.snapshot()
        assert_failed(theatre.config("set", "a", "2"), 3, STORE_FILENAME)
        assert theatre.snapshot() == before
    finally:
        for store in stores:
            store.chmod(0o644)
