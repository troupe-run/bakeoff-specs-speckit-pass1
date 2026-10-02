"""State lives only under .troupe/ and survives between commands; `uv run troupe` works."""

import subprocess
from pathlib import Path

from tests.conftest import Theatre

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
