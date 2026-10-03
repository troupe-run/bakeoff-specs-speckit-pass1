"""The first command imports the theatre (step 1 D-2), even a failing `get`; `get` reconciles."""

from tests.conftest import Theatre
from troupe.config.store import STORE_FILENAME


def test_first_get_imports(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert not (theatre.root / ".troupe" / STORE_FILENAME).exists()
    assert theatre.config("get", "a").code == 0
    assert (theatre.root / ".troupe" / STORE_FILENAME).exists()
    theatre.write("troupe.yml", "a: 2\n")  # a hand edit: not reconciled
    assert theatre.history() == [{"seq": 1, "op": "import", "path": "a", "old": None, "new": 1}]


def test_failing_get_still_imports(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    assert theatre.config("get", "nope").code == 5
    theatre.write("troupe.yml", "a: 2\n")
    assert [e["new"] for e in theatre.history()] == [1]


def test_get_reconciles_a_hand_edit_first(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "a: 1\n")
    theatre.history()  # import
    theatre.write("troupe.yml", "a: 2\n")
    assert theatre.config("get", "a").out == "2\n"
    assert theatre.history()[-1] == {"seq": 2, "op": "set", "path": "a", "old": 1, "new": 2}
