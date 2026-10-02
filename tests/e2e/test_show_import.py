"""The first command imports the theatre (spec D-2), even `show`, even one that fails."""

from tests.conftest import Theatre
from troupe.config.store import STORE_FILENAME


def test_first_show_imports(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert not (theatre.root / ".troupe" / STORE_FILENAME).exists()
    assert theatre.config("show", "a").code == 0
    assert (theatre.root / ".troupe" / STORE_FILENAME).exists()
    theatre.write("troupe.yml", "a: 2\n")  # a hand edit: not reconciled
    assert theatre.history() == [{"seq": 1, "op": "import", "path": "a", "old": None, "new": 1}]


def test_failing_show_still_imports(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert theatre.config("show", "nope").code == 5
    theatre.write("troupe.yml", "a: 2\n")
    assert [e["new"] for e in theatre.history()] == [1]
