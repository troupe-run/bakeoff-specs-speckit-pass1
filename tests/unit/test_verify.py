"""Verify-before-write (research R-7): a wrong edit is refused and nothing is written."""

from pathlib import Path

import pytest

from troupe.config.edit import apply
from troupe.config.edit.planner import EditPlan
from troupe.config.loader import load
from troupe.config.paths import ConfigPath
from troupe.config.scalars import NewScalar, Value
from troupe.errors import WriteRefused


def _theatre(tmp_path: Path, text: str) -> Path:
    (tmp_path / ".troupe").mkdir()
    (tmp_path / ".troupe" / "troupe.yml").write_text(text)
    return tmp_path


def _plan_returning(monkeypatch: pytest.MonkeyPatch, new_text: str, expected: Value) -> None:
    def fake_plan(loaded, path, value, *, in_include=False):  # type: ignore[no-untyped-def]
        node = loaded.root.get("a")
        return EditPlan(loaded.root.file, new_text, node, path, (), expected)

    monkeypatch.setattr(apply, "plan_set", fake_plan)


@pytest.mark.parametrize(
    ("new_text", "why"),
    [
        ("a: 2\nb: 9\n", "b would change too"),
        ("a: '2'\nb: 1\n", "would not read back"),
        ("a: [2\nb: 1\n", "would not load back"),
    ],
)
def test_wrong_edit_is_refused_and_nothing_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, new_text: str, why: str
) -> None:
    theatre = _theatre(tmp_path, "a: 1\nb: 1\n")
    _plan_returning(monkeypatch, new_text, 2)
    with pytest.raises(WriteRefused, match=why):
        apply.apply_set(theatre, load(theatre), ConfigPath.parse("a"), NewScalar(2, "2"))
    assert (theatre / ".troupe" / "troupe.yml").read_text() == "a: 1\nb: 1\n"


def test_correct_edit_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    theatre = _theatre(tmp_path, "a: 1\nb: 1\n")
    _plan_returning(monkeypatch, "a: 2\nb: 1\n", 2)
    events = apply.apply_set(theatre, load(theatre), ConfigPath.parse("a"), NewScalar(2, "2"))
    assert (theatre / ".troupe" / "troupe.yml").read_text() == "a: 2\nb: 1\n"
    assert [(e.op, e.path, e.old, e.new) for e in events] == [("set", "a", 1, 2)]
